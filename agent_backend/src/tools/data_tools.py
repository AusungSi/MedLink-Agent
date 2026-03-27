import json
import logging
import base64
import os
import requests
import chromadb
from ..config import PATIENT_DB_PATH
from ..rag_utils import RagUtils


def retrieve_context_from_db(query: str, rag_util: RagUtils) -> str:
    """从医疗知识库中检索通用的医学知识。"""
    return rag_util.query(query, top_k=3)

def retrieve_patient_records(patient_name: str, query_content: str, rag_util: RagUtils, in_memory_client: chromadb.Client) -> str:    
    """
    (直连真实数据库的动态检索版) 查询指定病人的病历信息。
    步骤: 1. 从 Flask API 提取该病人的全部真实病历记录。 2. 动态创建内存向量库。 3. 在库中进行语义搜索。
    """
    logging.info(f"正在为病人 '{patient_name}' 执行【动态检索】，查询: '{query_content}'")

    # --- 第1步: 通过内部API从真实数据库提取该病人的全部记录 ---
    try:
        url = f"http://127.0.0.1:5000/api/chat/internal/records/{patient_name}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 404:
            return f"在数据库中未找到病人 '{patient_name}' 的任何就诊记录。"
        elif response.status_code != 200:
            return f"系统提示：查询病历失败，后端返回状态码 {response.status_code}"
        
        patient_encounters = response.json()
        if not patient_encounters:
             return f"在数据库中未找到病人 '{patient_name}' 的任何就诊记录。"
             
    except Exception as e:
        logging.error(f"❌ 数据库接口连接失败: {e}")
        return f"系统提示：查询病历时发生网络错误: {str(e)}"

    # --- 第2步: 动态地为该病人的记录创建内存向量库 ---
    documents = []
    metadatas = []
    ids = []
    
    # 将每一次病历序列化为需要 Embed 的纯文本段落
    for encounter in patient_encounters:
        doc_text_parts = []
        doc_text_parts.append(f"【就诊时间】: {encounter['created_at']}")
        if encounter.get('chief_complaint'):
            doc_text_parts.append(f"主诉: {encounter['chief_complaint']}")
        if encounter.get('history_present_illness'):
            doc_text_parts.append(f"现病史: {encounter['history_present_illness']}")
        if encounter.get('past_medical_history'):
            doc_text_parts.append(f"既往史: {encounter['past_medical_history']}")
        if encounter.get('diagnosis'):
            doc_text_parts.append(f"诊断结论: {encounter['diagnosis']}")
        
        final_doc_text = "\n".join(doc_text_parts)
        documents.append(final_doc_text)
        metadatas.append({"date": encounter['created_at']})
        ids.append(str(encounter['id']))

    # 使用传入的 rag_util 生成 embedding
    def ollama_embed_func(texts: list[str]) -> list[list[float]]:
        return [rag_util._get_embedding(text) for text in texts]

    # 对病人姓名进行Base64编码，以生成一个安全的集合名称
    safe_patient_name = base64.urlsafe_b64encode(patient_name.encode('utf-8')).decode('utf-8')
    collection_name = f"patient-{safe_patient_name}-temp-records"[:63]

    logging.info(f"为病人 '{patient_name}' 创建临时集合，包含 {len(documents)} 份历史病历。")

    temp_collection = in_memory_client.get_or_create_collection(
        name=collection_name,
        embedding_function=None
    )

    if temp_collection.count() > 0:
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
    logging.info(f"正在为查询文本生成 embedding: '{query_content}'")
    query_embedding = ollama_embed_func([query_content])[0]

    if query_embedding:
        results = temp_collection.query(
            query_embeddings=[query_embedding],
            # 找到最相关的 3 次病历（如果总数不足3次则取总数）
            n_results=min(3, len(documents)) 
        )
    else:
        logging.error("无法为查询文本生成 embedding，检索失败。")
        return "内部错误：无法为查询文本生成语义向量。"

    if not results or not results['documents'] or not results['documents'][0]:
        return f"在病人 '{patient_name}' 的所有病历中，未找到与 '{query_content}' 相关的内容。"

    # 格式化输出最终最相关的几份病历返回给大模型
    context = "\n\n====================\n\n".join(results['documents'][0])
    return f"根据病人 '{patient_name}' 的历史病历数据库，检索到与“{query_content}”最相关的记录如下：\n\n{context}"