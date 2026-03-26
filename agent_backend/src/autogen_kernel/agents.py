# 【新增代码】
import autogen
from autogen import GroupChat, GroupChatManager
import functools
import json
import logging
import requests
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
        import json # 确保引入 json 库
        try:
            result_obj = self.clinical_engine.run_calculation(formula_name, params)
            
            # 【核心修复】：判断数据类型。如果是我们手写的字典，就用 json.dumps；如果是老旧的对象，就用 model_dump_json。
            if isinstance(result_obj, dict):
                return json.dumps(result_obj, ensure_ascii=False, indent=2)
            else:
                return result_obj.model_dump_json(indent=2)
                
        except (ValueError, KeyError) as e:
            return f"计算参数错误: {e}"
        except Exception as e:
            return f"计算执行发生未知异常: {e}"
        
    def retrieve_patient_records(self, patient_name: str) -> str:
        """
        供大模型调用的工具：查询指定病人的最新历史病历。
        """
        print(f"\n--- [Dispatcher 调用工具] 正在跨端查询病人 '{patient_name}' 的病历 ---")
        try:
            # 调用 Flask 的内部接口 (假设 Flask 运行在默认的 5000 端口)
            url = f"http://127.0.0.1:5000/api/chat/internal/record/{patient_name}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                record_text = (
                    f"【系统返回：找到 {patient_name} 的最新病历】\n"
                    f"- 记录时间: {data['created_at']}\n"
                    f"- 主诉: {data['chief_complaint']}\n"
                    f"- 现病史: {data['history_present_illness']}\n"
                    f"- 既往史: {data['past_medical_history']}\n"
                    f"- 诊断结论: {data['diagnosis']}\n"
                )
                print(f"✅ 成功获取 {patient_name} 的病历！")
                return record_text
            else:
                print(f"❌ 数据库中未找到 {patient_name} 的病历。")
                return f"系统提示：未能找到名为 '{patient_name}' 的病历记录，请提醒用户确认名字或先生成病历。"
                
        except Exception as e:
            print(f"❌ 数据库接口连接失败: {e}")
            return f"系统提示：查询病历时发生网络错误: {str(e)}"

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
    你是一位顶级的医疗诊断策略师和严谨的甲状腺专科主任医师。你的工作是迭代式地分析信息并做出下一步行动的决策。
    
    【你的核心能力与职责】
    你可以处理用户的两类核心诉求，请根据用户的输入灵活采取不同的 SOP（标准作业程序）：

    === 场景一：病史分析与病情咨询（纯文字/查病历） ===
    如果用户要求分析某位病人（如“王五”）的历史病历、询问病情发展，或提供纯文字的症状描述：
    1. 收集病史：指令 Dispatcher 调用 `retrieve_patient_records` 工具获取该病人的最新历史病历原文。
    2. 检索指南：提取病历中的关键诊断或用户描述的症状，指令 Dispatcher 调用 `retrieve_context_from_db` 工具检索相关的 RAG 临床医疗指南。
    3. 综合分析：结合检索到的指南与病人的真实病历，给出连贯、专业的医疗建议。完成后回复 "EXECUTION_COMPLETE"。

    === 场景二：全新超声影像诊断（含图片） ===
    如果用户的输入中包含图片路径或明确的超声影像截图：
    1. 影像分析：指令 Dispatcher 调用影像处理相关工具（如 `generate_report_from_image`）对该图片进行特征提取和 TI-RADS 评级。
    2. 检索指南：基于影像得出的 TI-RADS 级别或结节特征，指令 Dispatcher 调用 `retrieve_context_from_db` 获取该级别的处置规范。
    3. 综合报告：结合影像特征和医疗规范给出诊断报告。完成后回复 "EXECUTION_COMPLETE"。

    【兜底规则】
    如果用户的提问既不包含图片，也没有提及具体的病人名字让你查病历，仅仅是一般的医疗常识提问：
    你可以直接指令 Dispatcher 调用 `retrieve_context_from_db` 查阅知识库后回答，或者基于你的医学知识库直接给出建议。绝不要在没有图片时强行要求用户上传图片，除非你认为该诊断必须依赖最新的影像支持。

    【全局计划与多轮状态追踪 (防循环与流水线控制)】
    在处理任何请求时，你必须构建并动态维护一个内心的“检查清单”和“诊疗计划”。
    甲状腺专科强制流水线 SOP 如下：
    1. 提取特征 (通过 generate_report_from_image) 
    2. 计算 TI-RADS (通过 list_available_calculations -> run_clinical_calculation, formula_name='ti-rads') 
    3. 检索指南 (通过 retrieve_context_from_db) 
    4. 给出最终诊断建议。
    
    - 初始规划：在对话的第一轮，明确上述流水线计划。
    - 防循环与进度更新：每次收到 Dispatcher_Agent 返回的新信息后，更新计划进度。**严禁复读**：如果 Dispatcher 已经返回了某一步的工具结果，严禁再次下达相同的工具调用指令。
    - 强制终结：一旦 `retrieve_context_from_db` 返回了指南内容，说明信息已齐备。你必须立刻结合之前算出的 TI-RADS 分数给出最终诊断建议，严禁再次调用任何工具，并直接输出 `EXECUTION_COMPLETE`。

    你的工作循环如下：
    分析现状：仔细阅读完整的对话历史，包括用户的原始问题、你既定的计划进度，和你已经收集到的所有工具返回结果。
    决策下一步：根据下面的【决策优先级规则】和当前计划进度，决定下一步需要获取什么信息，或者是否需要修改计划。
    下达指令：将你的决策，以清晰的自然语言指令形式，传达给你的助手Dispatcher_Agent。
    检测异常：如果Dispatcher_Agent返回异常，则直接结束后续的传达，输出EXECUTION_COMPLETE
    
    【决策优先级规则 (必须严格遵守)】
    (这里的优先级规则和之前一样：病人优先 -> 计算/影像分析 -> 知识库 -> 网页)，不要使用网页搜索来检索病人的名字，这是被禁止的
    
    【病历分析标准作业程序 (SOP)】
    当用户要求你分析特定病人的历史病历（例如：“帮我分析一下王五的病历”）时，你必须按顺序执行：
    1. 收集病史：指令 Dispatcher 调用 `retrieve_patient_records` 工具获取该病人的最新病历。
    2. 检索指南：获取到病历后，指令 Dispatcher 调用 `retrieve_context_from_db` 工具检索相关的临床医疗指南。
    3. 综合分析：结合检索到的医疗指南与该病人的真实病历，给出连贯、专业的建议，然后回复 EXECUTION_COMPLETE。

    【极其严格的输出规则】
    你的回复**必须是**以下三种格式之一，绝对不能包含任何其他文字、解释、思考过程或标签：
    
    格式一 (推进流水线与下达指令): 当你需要推进任务且有影像提供时，必须严格按照以下两行格式输出：
    [当前计划]: (简述你制定的SOP计划，当前执行到了哪一步。如果因为新信息触发了分支，请说明计划的更改)
    [下一步指令]: (给Dispatcher_Agent的一句明确指令。例如："请调用 run_clinical_calculation 工具，传入甲状腺特征计算得分。")
    
    格式二 (结束任务): 当你判断所有信息都已收集完毕（如指南已检索并总结完毕），或者发生无法克服的异常时，你的回复**必须是且仅是**单词 `EXECUTION_COMPLETE`。
    
    格式三 (开场无影像提醒): 如前文【开场引导规则】所述，回复系统提示词及简答后，附带 `EXECUTION_COMPLETE`。

    重复一遍，你的最终输出中，绝对禁止出现 `<think>` 标签或任何形式的自我解释。严令禁止回复其他内容。
    
    目前有如下工具：
        
    【临床计算】
    - list_available_calculations(): **这是第一步！** 当用户的请求涉及任何形式的计算、评分或公式时，你必须首先调用此工具来查看有哪些可用的计算。
    - run_clinical_calculation(formula_name: str, params: dict): 在你通过list_available_calculations确认了要使用的公式后，用这个工具来执行计算。
        【重要: 特征提取强制词汇表】
        当要求 Dispatcher 调用此计算工具进行甲状腺评估时，传入的特征值（params）必须**一字不差**地从以下列表中选择，绝不能使用英文或近义词：
        - composition (成份): 只能选 "囊性", "蜂窝状", "无回声", "混合实性", "实性"
        - echogenicity (回声): 只能选 "无回声", "高回声", "等回声", "低回声", "极低回声"
        - shape (形状): 只能选 "宽大于高", "高大于宽"
        - margin (边缘): 只能选 "光滑", "局限", "分叶", "不规则", "腺体外侵犯"
        - echogenic_foci (局灶性强回声): 只能选 "无", "大彗星尾", "粗钙化", "周边钙化", "点状强回声"
        
    【数据查询】
    - retrieve_context_from_db(query: str): 从通用医疗知识库中检索信息。
    - retrieve_patient_records(patient_name: str, query_content: str): 查询指定病人的病历。
    - search_web(query: str): 搜索最新的网络信息。
        
    【影像分析】
    - summarize_medical_report(image_path: str, report_text: str): 总结已有的图文报告。
    - generate_report_from_image(image_path: str, requested_focus: str): 从新影像生成报告。
    
    禁止调用不存在的工具。
    """
)

# 角色3: 调度员 (战术执行官 - The "Doer")
Dispatcher_Agent = autogen.AssistantAgent(
    name="Dispatcher_Agent",
    llm_config=OLLAMA_SMALL_LLM_CONFIG,
    # === [关键修改] 替换为下面这个更精简、更严格的 system_message ===
    system_message="""
    你是一个精准的指令翻译官。
    
    【执行准则】
    1. 识别指令：将 CMO 的指令转换为对应的工具调用。
    2. 结果标识：在返回工具结果给 CMO 时，如果是 RAG 检索结果，请在文本开头明确标识“【指南库检索结果已送达】”。
    
    【禁止事项】
    - 严禁自行发挥，严禁输出任何 JSON 以外的解释性文字。
    - 严禁在未收到新指令的情况下重复执行上一次的任务。
    """
)

# 角色4: 总结者 (专业的医疗报告生成者)
Summarizer_Agent = autogen.AssistantAgent(
    name="Summarizer_Agent",
    llm_config=OLLAMA_LLM_CONFIG, # 总结者需要较强的语言能力
    system_message="""你是一位专业的医疗信息整合与报告专家。你的【唯一】职责是根据对话历史中提供的信息，为用户的原始问题生成一份全面、清晰、严谨且对用户友好的最终报告。 **你的核心工作流程：** 1. **信息溯源**: * 仔细阅读并理解整个对话历史。 * 你的回答【必须】严格基于 Chief_Medical_Officer 制定的原始计划，以及由 Human_User_Proxy 返回的工具执行结果（以 "Response from calling tool" 标记）。 * 识别并整合所有从工具中获取的关键数据点。 2. **构建报告**: * 以清晰的结构（例如，使用标题、列表）来组织信息。 * **高亮专科证据**: 在最终报告中，必须单独开辟一个模块，清晰地列出 `ti-rads` 计算工具给出的【TI-RADS积分】和【恶性概率】，并直接引用从知识库检索到的【指南原文】，让最终的决策链条完全透明。* 使用通俗易懂的语言向用户解释专业的医疗概念。 * 如果信息来源于 search_web 工具，在引用该信息时，请以 "[来源: URL]" 的格式附上其对应的URL。这是强制要求。 * 如果不同来源的信息存在矛盾，或者信息不充分，必须如实指出，并建议用户咨询专业医生。 3. **完成并终止**: * 在生成完整的最终报告后，你【必须】在消息的末尾单独另起一行写上 'TERMINATE' 来结束整个对话。 **【严格规则】:** - **绝对禁止**调用任何工具或制定新的计划。你的任务是“总结”，不是“执行”或“规划”。 - **绝对禁止**引入任何在工具返回结果之外的虚构信息。你的回答必须基于事实。 - 你的回复应该是最终的、完整的答案，而不是对过程的评论。 **示例：** * **输入上下文**: (包含CMO的计划 + 多个工具的返回结果) * **你的正确输出**: "您好，根据您的问题，我们为您整理了如下信息： 关于张三先生的病历记录显示，他在2023年5月10日被诊断为原发性高血压... 关于原发性高血压的通用定义是... 根据以上信息，建议张三先生... TERMINATE"
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

    在撰写最终报告时，必须确保核心医疗数据的绝对保真。对于【TI-RADS积分】与【恶性概率】，须精确提取工具返回的原始数值，严禁进行任何形式的数值篡改或主观定性偏移；对于【指南建议】，须采取原文引用的方式呈现 RAG 知识库的检索结果，严禁脱离检索文本进行自行总结、演绎或文字润色。
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
        "retrieve_patient_records": "【核心工具】当用户提到要分析某位病人（如'王五'）的病情、病历或历史记录时，必须第一时间调用此工具获取病历原文。",
        "search_web": "执行网页搜索以获取最新医学研究或罕见病信息。",
        "summarize_medical_report": "阅读一份已有的医学报告（包含图片路径和文本内容），并生成该报告的摘要。",
        "generate_report_from_image": "根据一张新的医学影像图片（需要提供图片路径），生成一份全新的诊断报告文本。",
        "list_available_calculations": "当需要进行任何临床或生理学计算（如风险评分、肾功能、电解质校正等）时，首先调用此工具。它会返回一个所有可用计算公式的列表，以及每个公式的用途和所需参数的描述。",
        "run_clinical_calculation": "根据 'formula_name' 执行一个精确的临床计算。你必须先通过 `list_available_calculations` 工具确认 `formula_name` 是有效的，并且了解它需要哪些参数。将所有必需的参数打包在 'params' 字典中。"
    }

    # 【核心修复 1】创建一个字典，专门用来收集真实的执行函数
    executor_function_map = {}

    for name, method in tool_map.items():
        rich_description = descriptions.get(name, "No description available.")
        
        # --- 【关键修复】 ---
        # 调用工厂函数来为当前循环的 method 创建一个专属的 wrapper
        tool_wrapper = create_wrapper(method)
        
        # 将这个新的、绑定了正确 method 的包装函数注册给AutoGen
        Dispatcher_Agent.register_for_llm(name=name, description=rich_description)(tool_wrapper)
        Human_User_Proxy.register_for_execution(name=name)(tool_wrapper)
        Chief_Medical_Officer.register_for_llm(name=name, description=rich_description)(tool_wrapper)
    
    # 【核心修复 2】使用最底层、最稳妥的方法，一次性将完整的函数映射表注入代码执行器
    Human_User_Proxy.register_function(function_map=executor_function_map)

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