# 【新增代码】
import autogen
from autogen import GroupChat, GroupChatManager
import functools
import json
import logging
# from functools import partial

# --- 【修改】从新的位置导入 ---
from ..config import OLLAMA_LLM_CONFIG, OLLAMA_SMALL_LLM_CONFIG
from ..tools import data_tools, web_tools, llm_tools
from ..tools.medical_calculator.engine import ClinicalEngine
from ..rag_utils import RagUtils # 导入类型
import chromadb # 导入类型
from .custom_manager import CustomGroupChatManager


class ToolExecutor:
    """
    这个类在初始化时持有所有复杂的依赖对象。
    它暴露的方法是干净的、参数类型简单的，可以安全地注册给AutoGen。
    """
    def __init__(self, rag_util: RagUtils, in_memory_client: chromadb.Client, clinical_engine: ClinicalEngine):
        self.rag_util = rag_util
        self.in_memory_client = in_memory_client
        self.clinical_engine = clinical_engine

    # --- 为每个需要依赖的工具创建一个包装方法 ---
    def retrieve_context_from_db(self, query: str) -> str:
        # 在这里，我们调用真正的工具函数，并传入持有的依赖
        return data_tools.retrieve_context_from_db(query, self.rag_util)

    def retrieve_patient_records(self, patient_name: str, query_content: str) -> str:
        return data_tools.retrieve_patient_records(patient_name, query_content, self.rag_util, self.in_memory_client)

    # --- 不需要依赖的工具可以直接引用 ---
    search_web = staticmethod(web_tools.search_web)
    summarize_medical_report = staticmethod(llm_tools.summarize_medical_report)
    generate_report_from_image = staticmethod(llm_tools.generate_report_from_image)
    
    # --- 计算引擎的工具也通过实例来调用 ---
    def list_available_calculations(self) -> str:
        """列出所有可用的临床计算公式及其描述。"""
        formulas = self.clinical_engine.list_available_formulas()
        # 将字典格式化为对LLM友好的、缩进的JSON字符串
        return json.dumps(formulas, ensure_ascii=False, indent=2)

    def run_clinical_calculation(self, formula_name: str, params: dict) -> str:
        # 为了让LLM能正确调用，我们将原始的JSON输出转换为字符串
        try:
            result_obj = self.clinical_engine.run_calculation(formula_name, params)
            return result_obj.model_dump_json(indent=2)
        except (ValueError, KeyError) as e:
            return f"计算错误: {e}"

# 角色1: 用户代理 / 代码执行者
Human_User_Proxy = autogen.UserProxyAgent(
    name="Human_User_Proxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
    code_execution_config={"use_docker": False},
)

# 角色2: 首席医疗官 (战略规划师 - The "Thinker")
Chief_Medical_Officer = autogen.AssistantAgent(
    name="Chief_Medical_Officer",
    llm_config=OLLAMA_LLM_CONFIG,
    # === [关键修改] 替换为下面这个更严格的 system_message ===
    system_message="""
    你是一位顶级的医疗诊断策略师。你的工作是迭代式地分析信息并做出下一步行动的决策。
    你的工作循环如下：
    分析现状：仔细阅读完整的对话历史，包括用户的原始问题和你已经收集到的所有工具返回结果。
    决策下一步：根据下面的【决策优先级规则】，决定下一步需要获取什么信息。
    下达指令：将你的决策，以清晰的自然语言指令形式，传达给你的助手Dispatcher_Agent。
    检测异常：如果Dispatcher_Agent返回异常，则直接结束后续的传达，输出EXECUTION_COMPLETE
    【决策优先级规则 (必须严格遵守)】
    (这里的优先级规则和之前一样：病人优先 -> 知识库 -> 网页)，不要使用网页搜索来检索病人的名字，这是被禁止的
    【极其严格的输出规则】
    你的回复**必须是**以下两种格式之一，绝对不能包含任何其他文字、解释、思考过程或标签：
    格式一 (下达指令): 给Dispatcher_Agent的一句明确指令。例如："请调用 retrieve_patient_records 工具，查询病人‘某某’关于‘某某某’的记录。"
    格式二 (结束任务): 当你判断所有信息都已收集完毕时，你的回复**必须是且仅是**单词 `EXECUTION_COMPLETE`，重复一遍，你的最终输出中，绝对禁止出现 `<think>` 标签或任何形式的自我解释。

    严令禁止回复其他内容，你的回复只能是上述两种格式
    目前有如下工具：
        
        【临床计算】
        - list_available_calculations(): **这是第一步！** 当用户的请求涉及任何形式的计算、评分或公式时，你必须首先调用此工具来查看有哪些可用的计算。
        - run_clinical_calculation(formula_name: str, params: dict): 在你通过list_available_calculations确认了要使用的公式后，用这个工具来执行计算。
        
        【数据查询】
        - retrieve_context_from_db(query: str): 从通用医疗知识库中检索信息。
        - retrieve_patient_records(patient_name: str, query_content: str): 查询指定病人的病历。
        - search_web(query: str): 搜索最新的网络信息。
        
        【影像分析】
        - summarize_medical_report(image_path: str, report_text: str): 总结已有的图文报告。
        - generate_report_from_image(image_path: str, requested_focus: str): 从新影像生成报告。    禁止调用不存在的工具
    """
)

# 角色3: 调度员 (战术执行官 - The "Doer")
Dispatcher_Agent = autogen.AssistantAgent(
    name="Dispatcher_Agent",
    llm_config=OLLAMA_SMALL_LLM_CONFIG,
    # === [关键修改] 替换为下面这个更精简、更严格的 system_message ===
    system_message="""
    你是一个指令解析器。你的唯一任务是：读取Chief_Medical_Officer发出的最新一条指令，并将其准确无误地转换为一个工具调用（function call）。
    【严格规则】
    你的输出必须直接是一个工具调用，不能包含任何额外的文字、解释或确认信息。
    你不需要做任何决策或思考，只需忠实地翻译指令。
    如果指令不清晰，尽你所能去匹配最合适的工具和参数。
    """
)

# 角色4: 总结者 (专业的医疗报告生成者)
Summarizer_Agent = autogen.AssistantAgent(
    name="Summarizer_Agent",
    llm_config=OLLAMA_LLM_CONFIG, # 总结者需要较强的语言能力
    system_message="""你是一位专业的医疗信息整合与报告专家。你的【唯一】职责是根据对话历史中提供的信息，为用户的原始问题生成一份全面、清晰、严谨且对用户友好的最终报告。 **你的核心工作流程：** 1. **信息溯源**: * 仔细阅读并理解整个对话历史。 * 你的回答【必须】严格基于 Chief_Medical_Officer 制定的原始计划，以及由 Human_User_Proxy 返回的工具执行结果（以 "Response from calling tool" 标记）。 * 识别并整合所有从工具中获取的关键数据点。 2. **构建报告**: * 以清晰的结构（例如，使用标题、列表）来组织信息。 * 使用通俗易懂的语言向用户解释专业的医疗概念。 * 如果信息来源于 search_web 工具，在引用该信息时，请以 "[来源: URL]" 的格式附上其对应的URL。这是强制要求。 * 如果不同来源的信息存在矛盾，或者信息不充分，必须如实指出，并建议用户咨询专业医生。 3. **完成并终止**: * 在生成完整的最终报告后，你【必须】在消息的末尾单独另起一行写上 'TERMINATE' 来结束整个对话。 **【严格规则】:** - **绝对禁止**调用任何工具或制定新的计划。你的任务是“总结”，不是“执行”或“规划”。 - **绝对禁止**引入任何在工具返回结果之外的虚构信息。你的回答必须基于事实。 - 你的回复应该是最终的、完整的答案，而不是对过程的评论。 **示例：** * **输入上下文**: (包含CMO的计划 + 多个工具的返回结果) * **你的正确输出**: "您好，根据您的问题，我们为您整理了如下信息： 关于张三先生的病历记录显示，他在2023年5月10日被诊断为原发性高血压... 关于原发性高血压的通用定义是... 根据以上信息，建议张三先生... TERMINATE"
"""
)

def custom_speaker_selection_func(last_speaker: autogen.Agent, groupchat: autogen.GroupChat) -> autogen.Agent:
    """
    一个完全确定性的发言者选择函数，用于强制执行“指挥->调度->执行”的循环。

    工作流程:
    1.  初始 -> CMO (开始决策)
    2.  CMO -> Dispatcher (下达指令，请求翻译)
    3.  Dispatcher -> Human_User_Proxy (翻译完成，准备执行)
    4.  Human_User_Proxy -> CMO (执行完毕，返回结果以供分析)
    5.  CMO (说出 "EXECUTION_COMPLETE") -> Summarizer (任务结束，开始总结)
    """
    messages = groupchat.messages
    last_message = messages[-1]
    
    # === [核心修复] 新增最高优先级的终止规则 ===
    # 规则 0: 检查上一条消息是否包含终止信号。
    # 这是最优先的规则，确保一旦 'TERMINATE' 出现，对话立即停止。
    if last_message.get("content", "").rstrip().endswith("TERMINATE"):
        logging.info("检测到TERMINATE信号，对话结束。")
        return None  # 返回 None 会立即终止群聊
    
    # 规则1: 对话开始，必须由CMO进行首次规划。
    # 初始消息由 UserProxyAgent 发起，所以此时消息列表长度为 1。
    if len(messages) <= 1:
        return groupchat.agent_by_name("Chief_Medical_Officer")
        
    # 获取上一条消息的内容和发言者名字，方便判断。
    last_message = messages[-1]
    last_speaker_name = last_speaker.name

    # 规则2: 如果CMO刚刚发言...
    if last_speaker_name == "Chief_Medical_Officer":
        # 2a: 如果CMO发出了结束信号，则必须由总结者接手。
        if last_message.get("content", "").strip().endswith("EXECUTION_COMPLETE"):
            logging.info("CMO发出了EXECUTION_COMPLETE信号，流程转向Summarizer。")
            return groupchat.agent_by_name("Summarizer_Agent")
        # 2b: 否则，CMO发出的就是自然语言指令，必须交由调度员处理。
        else:
            return groupchat.agent_by_name("Dispatcher_Agent")

    # 规则3: 如果调度员刚刚发言...
    # 调度员的任务是生成工具调用，接下来必须由执行者(Proxy)来执行。
    if last_speaker_name == "Dispatcher_Agent":
        return groupchat.agent_by_name("Human_User_Proxy")

    # 规则4: 如果执行者刚刚发言...
    # 这意味着工具已经执行完毕，返回了结果。现在必须将结果交还给CMO进行分析和下一步决策。
    if last_speaker_name == "Human_User_Proxy":
        return groupchat.agent_by_name("Chief_Medical_Officer")

    # 默认/回退规则: 在任何未预料到的情况下，将控制权交还给核心决策者CMO，以尝试修正流程。
    # 在这个严格的流程中，理论上不应该触发此规则。
    return groupchat.agent_by_name("Chief_Medical_Officer")

def create_wrapper(method_to_wrap):
    """
    这是一个工厂函数，它的作用是为每一次循环迭代创建一个新的、独立的作用域。
    这样，每个wrapper就能正确地“记住”它应该调用的那个method。
    """
    @functools.wraps(method_to_wrap)
    def wrapper(*args, **kwargs):
        return method_to_wrap(*args, **kwargs)
    return wrapper

def setup_agent_tools(tool_executor: ToolExecutor):
    """
    现在，这个函数只接收一个ToolExecutor实例。
    我们注册ToolExecutor实例的方法，这些方法的签名是干净的。
    """
    # --- 清空旧的注册，以防热重载时重复注册 ---
    Dispatcher_Agent.reset()
    Human_User_Proxy.reset()
    
    tool_map = {
        "retrieve_context_from_db": tool_executor.retrieve_context_from_db,
        "retrieve_patient_records": tool_executor.retrieve_patient_records,
        "search_web": tool_executor.search_web,
        "summarize_medical_report": tool_executor.summarize_medical_report,
        "generate_report_from_image": tool_executor.generate_report_from_image,
        "list_available_calculations": tool_executor.list_available_calculations,
        "run_clinical_calculation": tool_executor.run_clinical_calculation
    }
    
    descriptions = {
        "retrieve_context_from_db": "从医疗知识库中检索通用的医学知识。",
        "retrieve_patient_records": "查询指定病人的病历信息。",
        "search_web": "执行网页搜索以获取最新医学研究或罕见病信息。",
        "summarize_medical_report": "阅读一份已有的医学报告（包含图片路径和文本内容），并生成该报告的摘要。",
        "generate_report_from_image": "根据一张新的医学影像图片（需要提供图片路径），生成一份全新的诊断报告文本。",
        "list_available_calculations": "当需要进行任何临床或生理学计算（如风险评分、肾功能、电解质校正等）时，首先调用此工具。它会返回一个所有可用计算公式的列表，以及每个公式的用途和所需参数的描述。",
        "run_clinical_calculation": "根据 'formula_name' 执行一个精确的临床计算。你必须先通过 `list_available_calculations` 工具确认 `formula_name` 是有效的，并且了解它需要哪些参数。将所有必需的参数打包在 'params' 字典中。"
    }

    for name, method in tool_map.items():
        rich_description = descriptions.get(name, "No description available.")
        
        # --- 【关键修复】 ---
        # 调用工厂函数来为当前循环的 method 创建一个专属的 wrapper
        tool_wrapper = create_wrapper(method)
        
        # 将这个新的、绑定了正确 method 的包装函数注册给AutoGen
        Dispatcher_Agent.register_for_llm(name=name, description=rich_description)(tool_wrapper)
        Human_User_Proxy.register_for_execution(name=name)(tool_wrapper)

groupchat = GroupChat(
    agents=[Human_User_Proxy, Chief_Medical_Officer, Dispatcher_Agent, Summarizer_Agent],
    messages=[],
    max_round=20,
    # 将我们的自定义函数赋给 speaker_selection_method
    speaker_selection_method=custom_speaker_selection_func
)

# 管理者现在是“总协调者”，负责执行固定的工作流。
Orchestrator = CustomGroupChatManager(
    name="Orchestrator",
    groupchat=groupchat,
    llm_config=False,
    # === [关键修改] 替换为下面这个基于状态机的 system_message ===
#     system_message="""你是一个多智能体对话的协调者。你的唯一工作是遵循预设的发言顺序。
# """
)