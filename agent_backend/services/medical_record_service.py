# 文件路径: services/medical_record_service.py

import json
import autogen
from typing import Dict, Any
import functools
from fastapi import HTTPException
import re # 导入正则表达式模块

# 导入核心依赖
# 假设您的项目结构是 services 和 src 同级
from agent_backend.src.autogen_kernel.agents import ToolExecutor
from agent_backend.src.config import OLLAMA_LLM_CONFIG

def run_record_generation_workflow(
    patient_name: str, 
    chat_context: str,
    tool_executor: ToolExecutor
) -> Dict[str, Any]:
    """
    执行一个一次性的、专门用于生成新版JSON格式病历的AutoGen工作流。
    这个工作流是同步的，并且经过高度优化以确保输出格式的稳定性。
    """
    print(f"开始为病人 '{patient_name}' 生成新版JSON格式病历...")

    # ... (前面的 generator_system_message, generator_agent, temp_user_proxy, 工具注册等代码保持不变)
    generator_system_message = f"""
    你是一个专业的医疗记录生成引擎。你的唯一任务是：
    1. 接收一个病人姓名：'{patient_name}'。
    2. 调用 `retrieve_patient_records` 工具，并使用 "查询该病人的所有记录" 作为查询词，来获取该病人的全部健康信息。
    3. 根据从工具返回的信息，将内容整理并填充到一个结构化的JSON对象中。
    仔细阅读以下病人 '{patient_name}' 的【真实问诊对话记录】：
    
    <<< 问诊记录开始 >>>
    {chat_context}
    <<< 问诊记录结束 >>>

    【极其严格的输出规则】
    - 你的最终回复 **必须** 是一个单一的、完整的、可以被直接解析的JSON对象。
    - **绝对不能** 在JSON对象之外包含任何文字、解释、思考过程、或代码块标记（例如 ```json）。
    - 你的输出必须严格以 `{{` 开始，并以 `}}` 结束。

    【JSON输出格式模板】
    你必须严格遵循下面的JSON结构，并根据查询到的信息填充每个字段的内容。如果某项信息缺失，请使用空字符串 "" 作为值。
    {{
      "patient_name": "{patient_name}",
      "chief_complaint": "主诉：病人本次就诊最主要的问题或症状。",
      "history_of_present_illness": "现病史：围绕主诉的详细描述，包括症状的起始时间、性质、诱因、演变过程等。",
      "past_medical_history": "既往史：病人过去曾患有的重要疾病、手术史、输血史、过敏史等。",
      "personal_history": "个人史：病人的生活习惯，如出生地、居住地、职业、吸烟、饮酒史等。",
      "family_history": "家庭史：直系亲属（父母、兄弟姐妹、子女）的重要健康状况或遗传病史。",
      "diagnosis": "诊断：根据所有信息得出的初步或最终诊断结论。"
    }}
    """

    generator_agent = autogen.AssistantAgent(
        name="MedicalRecordGenerator_Agent",
        llm_config=OLLAMA_LLM_CONFIG,
        system_message=generator_system_message,
    )

    temp_user_proxy = autogen.UserProxyAgent(
        name="Temp_Executor_Proxy",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=2,
        code_execution_config={"use_docker": False},
        is_termination_msg=lambda x: x.get("content", "").strip().endswith("}"),
    )

    retrieve_patient_records_func = functools.partial(tool_executor.retrieve_patient_records)
    temp_user_proxy.register_for_execution(name="retrieve_patient_records")(retrieve_patient_records_func)
    generator_agent.register_for_llm(
        name="retrieve_patient_records", 
        description="查询指定病人的病历信息。"
    )(retrieve_patient_records_func)

    initial_prompt = f"请提取上述真实对话记录中的信息，为病人 '{patient_name}' 生成符合模板的纯净JSON格式病历。不要调用任何工具，直接分析文本并输出结果。"
    
    temp_user_proxy.initiate_chat(
        recipient=generator_agent,
        message=initial_prompt,
    )

    final_message = temp_user_proxy.last_message(generator_agent)
    if not final_message or not final_message.get("content"):
        print(f"错误：未能从Agent获取任何回复内容。")
        raise HTTPException(status_code=500, detail="模型未返回任何内容。")

    content = final_message.get("content", "").strip()

    # ==============================================================================
    #  【核心修改】健壮的解析逻辑：先移除 <think> 标签，再解析 JSON
    # ==============================================================================
    try:
        # 步骤 1: 使用正则表达式查找并移除 <think>...</think> 块。
        # re.DOTALL 标志让 '.' 可以匹配包括换行在内的任意字符。
        # 我们将匹配到的 <think> 块替换为空字符串。
        # 使用 rstrip() 移除替换后可能留下的尾随空格和换行符。
        json_only_string = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        
        # 步骤 2: 检查处理后的字符串是否为空
        if not json_only_string:
            raise ValueError("在移除<think>标签后，剩余内容为空。")
        
        # 步骤 3: 解析剩余的、应该是纯净JSON的字符串
        parsed_json = json.loads(json_only_string)
        
        print(f"成功为病人 '{patient_name}' 生成并解析了新版JSON病历（已移除think标签）。")
        return parsed_json

    except (json.JSONDecodeError, ValueError) as e:
        error_message = f"无法为病人 '{patient_name}' 生成有效的JSON病历。"
        print(f"{error_message} 错误信息: {e}")
        print(f"原始输出: {content}")
        raise HTTPException(
            status_code=500,
            detail=f'{{"error": "{error_message}", "raw_output": "{content}"}}'
        )

# ==============================================================================
#  测试代码块 (当直接运行此文件时执行)
# ==============================================================================
if __name__ == "__main__":
    import asyncio

    # 1. 定义一个用于测试的模拟类
    class MockToolExecutor:
        def retrieve_patient_records(self, patient_name: str, query_content: str) -> str:
            print("\n" + "="*50)
            print(f"--- [模拟工具被调用] ---")
            print(f"--- 正在为病人 '{patient_name}' 查询记录，查询内容: '{query_content}' ---")
            
            fake_patient_data = """
            患者姓名：李四，性别：女，年龄：45岁。
            主诉：因“上腹部隐痛伴反酸、嗳气2周”前来就诊。
            现病史：患者近2周来感觉上腹部有隐隐作痛，饭后较为明显，同时伴有反酸水、打嗝的情况。无恶心、呕吐，无黑便。自行服用“奥美拉唑”后症状稍有缓解，但停药后复发。
            既往史：否认高血压、糖尿病等慢性病史。10年前曾因“急性阑尾炎”行手术治疗。无药物过敏史。
            个人史：普通公司职员，工作压力较大，饮食不规律。无吸烟、饮酒史。
            家庭史：父母均体健，否认家族遗传病史。
            初步诊断：考虑为“慢性胃炎”。建议行胃镜检查。
            """
            print("--- [模拟工具返回的数据] ---\n" + fake_patient_data)
            print("="*50 + "\n")
            return fake_patient_data

    # 2. 编写测试主函数
    async def main_test():
        print("--- 开始直接测试 run_record_generation_workflow 函数 ---")
        test_patient_name = "李四"
        mock_executor = MockToolExecutor()

        try:
            # 调用函数，它内部现在已经包含了新的解析逻辑
            result = run_record_generation_workflow(
                patient_name=test_patient_name,
                tool_executor=mock_executor
            )
            print("\n" + "#"*50)
            print("### 函数成功返回，最终的JSON输出为: ###")
            print("#"*50)
            print(json.dumps(result, indent=2, ensure_ascii=False))

        except HTTPException as e:
            # 特别处理FastAPI的HTTPException，以更友好的方式打印其内容
            print(f"\n--- 函数执行出错 (HTTPException) ---")
            print(f"状态码: {e.status_code}")
            # 尝试将detail解析为JSON以美化输出
            try:
                error_detail = json.loads(e.detail)
                print(f"错误详情: {json.dumps(error_detail, indent=2, ensure_ascii=False)}")
            except:
                print(f"错误详情: {e.detail}")
        except Exception as e:
            print(f"\n--- 函数执行出错 ---")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误信息: {e}")

    # 3. 执行测试
    asyncio.run(main_test())
