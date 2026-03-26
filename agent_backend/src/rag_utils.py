# src/rag_utils.py
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
import chromadb
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging
import requests # 导入 requests 库
import json
import logging
from sentence_transformers import SentenceTransformer
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RagUtils:
    def __init__(self, ollama_model_name: str, db_path: str, source_dir: str):
        self.db_path = db_path
        self.source_dir = source_dir
        
        logging.info("正在唤醒本地 RTX 5060 显卡，加载开源中文向量模型...")
        # 自动下载并加载北京智源研究院（BAAI）开源的霸榜级中文模型 (仅需几百MB)
        # 它会自动检测你的 5060 并将其载入显存 (CUDA)
        self.embedding_model = SentenceTransformer('BAAI/bge-base-zh-v1.5', device='cuda')
        logging.info("✅ 本地 Embedding 模型已成功部署至显存！完全脱离公网环境。")

        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="medical_knowledge_base",
            metadata={"hnsw:space": "cosine"}
        )
        self._build_knowledge_base_if_needed()

    def _get_embedding(self, text: str):
        """完全本地断网计算向量，榨干 5060 算力"""
        try:
            # encode 返回的是 numpy 数组，必须转为 list 才能存入 ChromaDB
            vector = self.embedding_model.encode(text, normalize_embeddings=True)
            return vector.tolist()
        except Exception as e:
            logging.error(f"本地显卡向量化失败: {e}")
            return None
    """
    def __init__(self, ollama_model_name: str, db_path: str, source_dir: str):
        self.ollama_model_name = ollama_model_name
        self.ollama_api_url = "http://localhost:11434/api/embeddings" # 定义Ollama API地址
        
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="medical_knowledge_base",
            metadata={"hnsw:space": "cosine"}
        )
        self.source_dir = source_dir
        self._build_knowledge_base_if_needed()

    def _get_embedding(self, text: str):
        try:
            payload = {
                "model": self.ollama_model_name,
                "prompt": text
            }
            response = requests.post(self.ollama_api_url, json=payload)
            response.raise_for_status() # 如果请求失败 (例如 404, 500), 会抛出异常
            return response.json()["embedding"]
        except requests.exceptions.RequestException as e:
            logging.error(f"调用Ollama embedding API失败: {e}")
            return None
    """
    def _build_knowledge_base_if_needed(self):
        """
        【高效优化版】
        1. 快速路径检查：仅通过文件名对比，快速识别新文件，避免不必要的IO。
        2. 逐一处理：一次只加载一个新文件到内存，处理完毕后释放，防止OOM。
        3. 健壮性：单个文件处理失败时，会记录错误并自动跳过，不影响其他文件。
        """
        logging.info("启动高效知识库检查...")
        import os
        from langchain_community.document_loaders import PyPDFLoader

        # --- 第1步：快速路径检查 ---
        
        # 1a. 获取数据库中所有已处理过的文件的源路径
        processed_files_paths = set()
        try:
            total_count = self.collection.count()
            if total_count > 0:
                logging.info(f"数据库中共有 {total_count} 个片段，正在分批核对元数据...")
                
                # 采用分批读取（每次 500 条），完美避开 SQLite 的 999 变量限制
                batch_size = 500
                for offset in range(0, total_count, batch_size):
                    batch_data = self.collection.get(
                        include=["metadatas"], 
                        limit=batch_size, 
                        offset=offset
                    )
                    for meta in batch_data['metadatas']:
                        if meta and 'source' in meta:
                            processed_files_paths.add(meta['source'])
                
                logging.info(f"核对完成！数据库中已记录 {len(processed_files_paths)} 个原始文件。")
            else:
                logging.info("数据库为空，准备执行首次入库。")
        except Exception as e:
            logging.error(f"分批获取元数据失败！将假定数据库为空。错误详情: {e}")

        # 1b. 获取磁盘上所有PDF文件的绝对路径
        all_disk_files_paths = {
            os.path.abspath(os.path.join(self.source_dir, f))
            for f in os.listdir(self.source_dir) if f.endswith('.pdf')
        }
        logging.info(f"在目录 '{self.source_dir}' 中发现 {len(all_disk_files_paths)} 个PDF文件。")
        
        # 1c. 计算出需要处理的新文件路径
        new_files_to_process = sorted(list(all_disk_files_paths - processed_files_paths))

        if not new_files_to_process:
            logging.info("知识库已是最新，无需更新。检查完成。")
            return

        logging.info(f"发现 {len(new_files_to_process)} 个新文件需要处理:")
        for file_path in new_files_to_process:
            logging.info(f"  -> {os.path.basename(file_path)}")

        # --- 第2步 & 第3步：逐一处理新文件并处理错误 ---
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        total_new_chunks = 0

        for i, file_path in enumerate(new_files_to_process):
            file_name = os.path.basename(file_path)
            logging.info(f"\n--- [处理新文件 {i+1}/{len(new_files_to_process)}] 开始处理: {file_name} ---")
            
            try:
                # 2a. 加载单个文件
                logging.info(f"正在加载并分割文件...")
                pdf_loader = PyPDFLoader(file_path)
                docs = pdf_loader.load_and_split(text_splitter) # 直接加载并用同一个splitter分割
                
                if not docs:
                    logging.warning(f"文件 {file_name} 未能分割出任何文本片段，已跳过。")
                    continue
                
                logging.info(f"文件分割成 {len(docs)} 个片段，准备进行向量化...")

                # 2b. 向量化单个文件的所有片段
                embeddings = []
                successful_docs = []
                for doc_chunk in docs:
                    embedding = self._get_embedding(doc_chunk.page_content)
                    if embedding:
                        embeddings.append(embedding)
                        successful_docs.append(doc_chunk)
                    else:
                        logging.warning(f"未能为 {file_name} 的一个片段获取embedding，已跳过该片段。")
                
                if not embeddings:
                    logging.error(f"未能为文件 {file_name} 的任何片段生成embedding，已跳过整个文件。")
                    continue

                # 2c. 准备ID和元数据并写入数据库
                ids = [f"{file_path}_chunk_{j}" for j in range(len(successful_docs))]
                documents = [doc.page_content for doc in successful_docs]
                metadatas = [doc.metadata for doc in successful_docs]
                
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas
                )
                logging.info(f"成功将 {len(ids)} 个新片段从文件 {file_name} 添加到数据库。")
                total_new_chunks += len(ids)

            except Exception as e:
                # 3. 健壮的错误处理
                logging.error(f"处理文件 {file_name} 时发生严重错误，已完全跳过此文件。错误详情: {e}", exc_info=True)
                # exc_info=True会把详细的错误堆栈也打印出来，方便调试
                continue # 继续处理下一个文件

        logging.info(f"\n{'='*20} 知识库增量更新完成！总共新增了 {total_new_chunks} 个文档片段。 {'='*20}")
    
    def query(self, user_query: str, top_k: int = 3) -> str:
        logging.info(f"正在为查询 '{user_query}' 执行RAG检索...")
        query_embedding = self._get_embedding(user_query)
        
        if not query_embedding:
            return "抱歉，无法为您的查询生成向量，检索失败。"

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        context = "\n\n---\n\n".join(results['documents'][0])
        logging.info("已成功检索到相关上下文。")
        return context