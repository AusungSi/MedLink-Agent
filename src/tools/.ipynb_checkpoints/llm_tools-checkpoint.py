import os
import base64
import logging
import json
import requests
from ..config import OLLAMA_VLM_CONFIG


def _call_vlm_api(image_path: str, prompt: str) -> str:
    """
    一个通用的辅助函数，用于调用Ollama VLM API。
    【修正版】此版本可以正确解析AutoGen的标准LLM配置格式。
    """
    logging.info(f"开始调用VLM API分析图片: {image_path}")

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

    # --- [核心修正] ---
    # 3. 从AutoGen标准配置中提取模型名称和API地址
    try:
        # 从config_list的第一个配置项中提取信息
        vlm_config = OLLAMA_VLM_CONFIG["config_list"][0]
        model_name = vlm_config["model"]
        
        # 从base_url构建完整的 /api/generate URL
        # 使用 rstrip('/') 确保URL拼接正确，无论base_url末尾是否有斜杠
        base_url = vlm_config.get("base_url", "http://localhost:11434/v1").rstrip('/')
        # 注意：多模态调用通常使用 /api/generate 而不是 /v1/chat/completions
        # 我们需要将 v1 替换为 api
        if base_url.endswith("/v1"):
            base_url = base_url[:-3] # 移除 '/v1'
        
        api_url = f"{base_url}/api/generate"

    except (KeyError, IndexError) as e:
        error_msg = f"错误：VLM配置格式不正确或不完整。请检查src/config.py中的OLLAMA_VLM_CONFIG。错误: {e}"
        logging.error(error_msg)
        return error_msg
    # --- [核心修正结束] ---

    # 4. 构建API请求体
    payload = {
        "model": model_name,
        "prompt": prompt,
        "images": [encoded_image],
        "stream": True
    }

    # 5. 发送请求并处理流式响应
    try:
        logging.info(f"向Ollama VLM模型 '{model_name}' (at {api_url}) 发送请求...")
        response = requests.post(
            api_url,
            json=payload,
            stream=True
        )
        response.raise_for_status()

        full_response = []
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                full_response.append(chunk.get("response", ""))
                if chunk.get("done"):
                    break
        
        final_text = "".join(full_response).strip()
        logging.info("成功接收并解析了VLM的完整响应。")
        return final_text

    except requests.exceptions.RequestException as e:
        error_msg = f"错误：调用Ollama VLM API时发生网络错误: {e}"
        logging.error(error_msg)
        return error_msg
    except json.JSONDecodeError as e:
        error_msg = f"错误：解析Ollama VLM API的响应时失败: {e}"
        logging.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"错误：处理VLM API调用时发生未知错误: {e}"
        logging.error(error_msg)
        return error_msg

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
