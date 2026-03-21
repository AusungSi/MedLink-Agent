import os
import base64
import logging
import json
import requests
from ..config import OLLAMA_VLM_CONFIG
# ==========================================
    # [团队协作与部署备注]
    # 现状说明：前端通过聊天框上传图片后，传给 AI 的是该图片的静态访问 URL (http://...)。
    # 本地转换逻辑：为了让 VLM 能够分析图片，我们需要先将图片转为 Base64。
    # 因此，这里通过字符串解析，将前端的 URL 强行映射回了本地的物理上传目录 (backend/uploads/chat_files/)。
    # 
    # ⚠️ 未来生产环境优化建议：
    # 如果未来项目上云，前后端分离部署，或者使用了阿里云 OSS/腾讯云 COS 等对象存储，
    # 本地的物理路径将失效。届时请将此段逻辑重构为：
    # "通过 requests.get(image_path) 直接下载 URL 的二进制数据，并在内存中转为 Base64"。
    # ==========================================
from urllib.parse import urlparse # 新增：用于解析URL
from ..config import OLLAMA_VLM_CONFIG, BASE_DIR # 新增：导入BASE_DIR
def _call_vlm_api(image_path: str, prompt: str) -> str:
    """
    一个通用的辅助函数，用于调用Ollama VLM API。
    【修正版】此版本可以正确解析AutoGen的标准LLM配置格式。
    """
    logging.info(f"开始调用VLM API分析图片: {image_path}")

    # --- [新增：URL 转本地路径逻辑] ---
    if image_path.startswith("http"):
        try:
            # 1. 从 URL 中提取文件名 (例如: 5_1774057894_R.jpg)
            filename = os.path.basename(urlparse(image_path).path)
            
            # 2. 构建本地物理路径
            # 根据您的描述，文件存储在 D:\CCCC\medical_qa\backend\uploads\chat_files
            # 而 agent_backend/src/config.py 中的 BASE_DIR 指向 D:\CCCC\medical_qa\agent_backend
            # 所以我们需要跳出 agent_backend 进入 backend
            project_root = os.path.dirname(BASE_DIR) # 获取 D:\CCCC\medical_qa
            local_path = os.path.join(project_root, "backend", "uploads", "chat_files", filename)
            
            logging.info(f"检测到 URL，已转换为本地路径: {local_path}")
            image_path = local_path
        except Exception as e:
            logging.warning(f"尝试解析 URL 路径失败: {e}，将尝试原始路径。")
    # --- [路径修复结束] ---

    # 1. 检查图片路径
    if not os.path.exists(image_path):
        error_msg = f"错误：找不到指定的图片文件：{os.path.abspath(image_path)}"
        logging.error(error_msg)
        return error_msg

    # 2. 读取并编码图片为Base64
    try:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        error_msg = f"错误：读取或编码图片文件时失败: {e}"
        logging.error(error_msg)
        return error_msg


    # --- 3. 配置解析与接口适配 ---
    vlm_config = OLLAMA_VLM_CONFIG["config_list"][0]
    model_name = vlm_config["model"]
    base_url = vlm_config.get("base_url", "").rstrip('/')
    api_key = vlm_config.get("api_key", "ollama")

    # 判断是 阿里云/OpenAI 接口 还是 本地 Ollama 接口
    is_openai_compatible = "dashscope" in base_url or base_url.endswith("/v1")

    try:
        if is_openai_compatible:
            # --- 方案 A: OpenAI 兼容模式 (适用于 DashScope/Qwen-VL) ---
            api_url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                    ]
                }]
            }
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']

        else:
            # --- 方案 B: 本地 Ollama 原生模式 ---
            # 如果是本地，则手动处理路径
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]
            api_url = f"{base_url}/api/generate"
            payload = {"model": model_name, "prompt": prompt, "images": [encoded_image], "stream": False}
            response = requests.post(api_url, json=payload, timeout=60)
            response.raise_for_status()
            return response.json().get("response", "").strip()

    except Exception as e:
        logging.error(f"VLM 调用失败: {e}")
        return f"错误：VLM 服务请求失败: {e}"
    

# 工具1: 总结现有图文报告
def summarize_medical_report(image_path: str, report_text: str) -> str:
    """
    结合一张医学影像图片和一份已有的报告文本，生成一份简明扼要的摘要。
    适用于对历史报告进行快速回顾和总结。
    """
    logging.info(f"正在为图片 '{image_path}' 和提供的文本生成摘要。")
    prompt = f"""
    你是一位资深的放射科医生。请结合下面的医学影像和已经存在的诊断报告文本，给出一份简明扼要的摘要，总结最重要的发现。

    --- 原始报告文本 ---
    {report_text}
    --- 报告文本结束 ---

    请开始你的摘要：
    """
    return _call_vlm_api(image_path=image_path, prompt=prompt)

# 工具2: 从新影像生成报告
def generate_report_from_image(image_path: str, requested_focus: str = "常规检查") -> str:
    """
    根据一张新的医学影像图片（如CT、X光），生成一份全新的诊断报告文本。
    适用于对本次就诊的新检查进行初步分析。
    """
    logging.info(f"正在为新图片 '{image_path}' 生成诊断报告，检查重点: {requested_focus}")
    prompt = f"""
    你是一位资深的放射科医生。请仔细分析下面的医学影像，并生成一份详细、专业的诊断报告。
    
    本次检查的重点是：{requested_focus}。

    你的报告应包含以下结构清晰的部分：
    1.  **影像所见 (Image Findings):** 对影像内容的客观、详细描述。
    2.  **诊断意见 (Impression):** 基于影像所见得出的初步诊断结论。

    请开始撰写报告：
    """
    return _call_vlm_api(image_path=image_path, prompt=prompt)