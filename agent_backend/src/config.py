# src/config.py
from pathlib import Path

# --- 1. 定义千问 API 的基础信息 ---
qwen_api_key = "sk-c305adc976b3489f90458ebe54356d9c"
qwen_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# --- 2. 核心大模型配置 (保留原变量名 OLLAMA_LLM_CONFIG) ---
# 用于需要强大推理能力的 Agent（原先指向本地大模型，现指向 qwen-max）
OLLAMA_LLM_CONFIG = {
    "config_list": [
        {
            "model": "qwen-max", 
            "base_url": qwen_base_url,
            "api_key": qwen_api_key,
        }
    ],
    "temperature": 0.1,
    "timeout": 120,
}

# --- 3. 小模型配置 (保留原变量名 OLLAMA_SMALL_LLM_CONFIG) ---
# 既然千问 API 很便宜，我们直接让 Dispatcher 也用最聪明的模型
OLLAMA_SMALL_LLM_CONFIG = OLLAMA_LLM_CONFIG 

# --- 4. 视觉大模型配置 (保留原变量名 OLLAMA_VLM_CONFIG) ---
# 用于 Vision Agent 解析超声图像（指向千问专属视觉模型 qwen-vl-max）
OLLAMA_VLM_CONFIG = {
    "config_list": [
        {
            "model": "qwen-vl-max",
            "base_url": qwen_base_url,
            "api_key": qwen_api_key,
        }
    ],
    "temperature": 0.1,
    "timeout": 120,
}

# --- 5. 路径与密钥配置 (保持昨天的本地化修改) ---
BASE_DIR = Path(__file__).resolve().parents[1]
VECTOR_DB_PATH = str(BASE_DIR / "vector_db")
KNOWLEDGE_BASE_PATH = str(BASE_DIR / "data" / "medical_documents") 
PATIENT_DB_PATH = str(BASE_DIR / "data" / "patient_database.json")
TAVILY_API_KEY = "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"