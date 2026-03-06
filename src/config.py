# src/config.py

# 用于AutoGen中需要强大推理能力Agent（如CMO, Orchestrator）的配置
# 使用您服务器上的 qwen3:8b 或更强的模型
OLLAMA_LLM_CONFIG = {
    "config_list": [
        {
            "model": "qwen3:30b",          # <-- 您的主要大模型
            "base_url": "http://localhost:11434/v1",
            "api_key": "ollama",
        }
    ],
    "cache_seed": None, # 设置为None以禁用缓存
}

# 用于AutoGen中需要高效指令遵循能力Agent（如Dispatcher）的配置
# 使用一个更小、更快的模型
OLLAMA_SMALL_LLM_CONFIG = {
    "config_list": [
        {
            "model": "qwen3:4b",          # <-- 您的高效小模型
            "base_url": "http://localhost:11434/v1",
            "api_key": "ollama",
        }
    ],
    "cache_seed": None, # 设置为None以禁用缓存
}

# 用于VLM Agent或工具的配置
OLLAMA_VLM_CONFIG = {
    "config_list": [
        {
            "model": "gemma3:12b",  # <-- 你部署的VLM模型名称
            "base_url": "http://localhost:11434/v1",
            "api_key": "ollama",
        }
    ],
    "cache_seed": None,
}


# 知识库和向量数据库的路径配置
VECTOR_DB_PATH = "./vector_db"
KNOWLEDGE_BASE_PATH = "/root/autodl-tmp/pdf" # <-- 请确保这是您存放PDF的正确路径
PATIENT_DB_PATH = "./data/patient_database.json"
TAVILY_API_KEY = "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"