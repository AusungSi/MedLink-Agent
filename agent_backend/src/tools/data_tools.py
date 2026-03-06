import json
import logging
import base64
import os
import chromadb
from ..config import PATIENT_DB_PATH
from ..rag_utils import RagUtils


def retrieve_context_from_db(query: str, rag_util: RagUtils) -> str:
    """从医疗知识库中检索通用的医学知识。"""
    return rag_util.query(query, top_k=3)

def retrieve_patient_records(patient_name: str, query_content: str, rag_util: RagUtils, in_memory_client: chromadb.Client) -> str:    
    """
    (动态检索版) 查询指定病人的病历信息。
    步骤: 1. 提取该病人的全部记录。 2. 动态创建内存向量库。 3. 在库中进行语义搜索。
    """
    logging.info(f"正在为病人 '{patient_name}' 执行【动态检索】，查询: '{query_content}'")

    # --- 第1步: 从原始数据源提取该病人的全部记录 ---
    try:
        with open(PATIENT_DB_PATH, 'r', encoding='utf-8') as f:
            all_patients_data = json.load(f)
    except FileNotFoundError:
        import os
        return f"错误：找不到病人数据库文件。尝试查找的路径为: {os.path.abspath(PATIENT_DB_PATH)}。"

    patient_data = all_patients_data.get(patient_name)
    if not patient_data or not patient_data.get("encounters"):
        return f"在数据库中未找到病人 '{patient_name}' 的任何就诊记录。"

    patient_encounters = patient_data.get("encounters")

    # --- 第2步: 动态地为该病人的记录创建内存向量库 ---

    # 将每一次encounter序列化为文档
    documents = []
    metadatas = []
    ids = []
    for encounter in patient_encounters:
        doc_text_parts = []
        doc_text_parts.append(f"在 {encounter['date']} 的{encounter['encounter_type']}中:")
        if encounter.get('diagnosis'):
            doc_text_parts.append(f"诊断为 {encounter['diagnosis']}")
        if encounter.get('medications'):
            med_texts = [f"{med['name']}({med['dosage']})" for med in encounter['medications']]
            doc_text_parts.append(f"用药包括 {', '.join(med_texts)}")
        if encounter.get('lab_reports'):
            report_texts = [f"{rep['report_name']}结果是{rep['result_summary']}" for rep in encounter['lab_reports']]
            doc_text_parts.append(f"检查有 {'; '.join(report_texts)}")
        
        final_doc_text = " ".join(doc_text_parts)
        documents.append(final_doc_text)
        metadatas.append({"date": encounter['date']})
        ids.append(encounter['encounter_id'])

    # 使用Ollama的Embedding函数接口
    # 注意: rag_util._get_embedding 是我们自己写的requests版本，这里用一个更通用的方式
    # 我们需要一个符合chromadb规范的embedding function
    # 我们可以把rag_util._get_embedding包装一下，或者直接在这里实现
    def ollama_embed_func(texts: list[str]) -> list[list[float]]:
        return [rag_util._get_embedding(text) for text in texts]

    # 对病人姓名进行Base64编码，以生成一个安全的集合名称
    safe_patient_name = base64.urlsafe_b64encode(patient_name.encode('utf-8')).decode('utf-8')
    collection_name = f"patient-{safe_patient_name}-temp-records" # 使用连字符更常见

    # 确保名称长度不会超限（虽然对于base64编码的姓名来说基本不可能）
    collection_name = collection_name[:63] # ChromaDB v0.4.x 的一个常见长度限制

    logging.info(f"为病人 '{patient_name}' 创建临时集合，安全名称为: '{collection_name}'")

    temp_collection = in_memory_client.get_or_create_collection(
        name=collection_name,
        embedding_function=None
    )

    if temp_collection.count() > 0:
        logging.info(f"集合 '{collection_name}' 中存在旧数据，将执行删除并重建。")
        in_memory_client.delete_collection(name=collection_name)
        temp_collection = in_memory_client.create_collection(name=collection_name)

    # 向量化并添加数据
    embeddings = ollama_embed_func(documents)
    temp_collection.add(
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

    # --- 第3步: 在这个临时的内存库中进行语义搜索 ---
    # 步骤 3a: 手动为用户的查询文本生成查询向量
    logging.info(f"正在为查询文本生成 embedding: '{query_content}'")
    query_embedding = ollama_embed_func([query_content])[0] # ollama_embed_func接收列表，返回列表，所以我们取第一个元素

    # 步骤 3b: 使用 `query_embeddings` 参数进行查询，而不是 `query_texts`
    if query_embedding:
        results = temp_collection.query(
            query_embeddings=[query_embedding], # <-- 使用查询向量
            n_results=min(3, len(documents))
        )
    else:
        logging.error("无法为查询文本生成 embedding，检索失败。")
        results = None # 或者返回一个空的结果结构
    # =======================================================


    if not results or not results['documents'] or not results['documents'][0]:
        return f"在病人 '{patient_name}' 的病历中未找到与 '{query_content}' 语义相关的内容。"

    # 格式化输出
    context = "\n\n---\n\n".join(results['documents'][0])
    return f"根据病人 '{patient_name}' 的病历，检索到以下语义最相关的记录：\n{context}"
