# 文件: src/autogen_kernel/session_manager.py (替换为以下全部内容)

import asyncio
import uuid
from typing import Dict, Any, List
import autogen
from queue import Queue
from .agents import Human_User_Proxy, Orchestrator, groupchat

SESSIONS: Dict[str, Any] = {}

class AutoGenSession:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.queue = Queue()
        # 使用内容哈希来追踪已发送消息，更可靠
        self.sent_message_hashes = set()

        # 为每个会话创建独立的代理实例
        self.user_proxy = autogen.UserProxyAgent(
            name=Human_User_Proxy.name,
            system_message=Human_User_Proxy.system_message,
            human_input_mode="NEVER",
            llm_config=False,
            code_execution_config=False,
            # --- 【核心修正】监听最终的 'TERMINATE' 信号，而不是过程中的 'EXECUTION_COMPLETE' ---
            is_termination_msg=lambda x: "TERMINATE" in x.get("content", "")
        )
        self.orchestrator = Orchestrator
        
        # print(f"[{self.session_id}] Initializing new session. Performing deep reset...")
        
        # # 1. 重置群聊本身（清空消息列表）
        # groupchat.reset()
        
        # # 2. 【关键】重置群聊内部的所有成员智能体
        # for agent in groupchat.agents:
        #     agent.reset()
        
        # # 3. 重置作为入口的用户代理和协调器
        # self.user_proxy.reset()
        # self.orchestrator.reset()
        
        # print(f"[{self.session_id}] All components have been reset for the new session.")
        self._register_agent_callbacks()

    def _register_agent_callbacks(self):
        """
        为所有Agent注册回调，用于实时发送中间消息。
        """
        def message_callback(recipient, messages: List[Dict], sender, config):
            # 确保消息列表不为空
            if not messages or not messages[-1]:
                return False, None

            last_message = messages[-1]
            content = last_message.get("content", "")
            
            # --- 【这是唯一的、最终的修复】 ---
            
            # 1. 优先从消息字典的 "name" 字段获取发言者。
            #    在GroupChat中，这记录了真正的原始发言者。
            speaker_name = last_message.get("name")
            
            # 2. 如果消息中没有 "name" 字段（例如在群聊之外的某些交互），
            #    我们才回退到使用 sender.name 作为备用方案。
            if not speaker_name:
                speaker_name = sender.name if sender else "UnknownAgent"
            
            # --- 【修复结束】 ---

            # 使用内容的哈希值来判断是否重复
            # 将修正后的 speaker_name 加入哈希计算，可以防止不同Agent说同样的话时被错误地过滤掉
            content_hash = hash(content + speaker_name)
            if content_hash in self.sent_message_hashes:
                return False, None
            
            # 我们只关心有名有姓的 Agent 的发言，并且内容不为空
            if speaker_name and content:
                self.queue.put({
                    "type": "agent_message",
                    "speaker": speaker_name, # <-- 使用我们修正后的 speaker_name
                    "content": content,
                    "tool_calls": last_message.get("tool_calls")
                })
                self.sent_message_hashes.add(content_hash)

            return False, None

        # 为所有相关代理注册回调
        # 为了确保回调能被所有地方触发，我们给Orchestrator和其内部的所有代理都注册上
        all_agents = self.orchestrator.groupchat.agents + [self.user_proxy, self.orchestrator]
        for agent in all_agents:
            if isinstance(agent, autogen.ConversableAgent):
                agent.register_reply(autogen.Agent, message_callback)

    async def start_chat(self, initial_question: str):
        """
        启动对话，并在结束后从 GroupChat 的最终历史记录中校对并补发消息。
        """
        try:
            loop = asyncio.get_event_loop()
            
            await loop.run_in_executor(
                None,
                lambda: self.user_proxy.initiate_chat(
                    recipient=self.orchestrator,
                    message=initial_question,
                )
            )

            # --- 从 GroupChat 获取最完整的历史记录进行校对 ---
            print(f"[{self.session_id}] Chat finished. Reconciling history from GroupChat.")
            
            chat_history = groupchat.messages
            
            for message in chat_history:
                content = message.get("content", "")
                content_hash = hash(content)

                if content and content_hash not in self.sent_message_hashes:
                    print(f"[{self.session_id}] Found unsent final message in GroupChat history. Sending now.")
                    
                    speaker_name = message.get("name", "UnknownAgent")
                    
                    # 忽略那些没有实际内容的中间消息
                    if not content.strip() or speaker_name == 'Human_User_Proxy' and 'tool_responses' in message:
                        continue

                    self.queue.put({
                        "type": "agent_message",
                        "speaker": speaker_name,
                        "content": content,
                        "tool_calls": message.get("tool_calls")
                    })
                    self.sent_message_hashes.add(content_hash)

        except Exception as e:
            error_content = f"An error occurred during the conversation: {str(e)}"
            self.queue.put({"type": "error", "content": error_content})
            print(f"Error in session {self.session_id}: {e}", flush=True)
        finally:
            print(f"Session {self.session_id} finished. Sending end signal.", flush=True)
            self.queue.put({"type": "session_end"})
            
            # print(f"[{self.session_id}] Performing deep reset of all agents and groupchat...")
            
            # # 1. 重置群聊本身（清空消息列表）
            # groupchat.reset()
            
            # # 2. 重置会话中使用的代理
            # self.user_proxy.reset()
            # self.orchestrator.reset()
            
            # # 3. 【关键补充】重置群聊内部的所有成员智能体
            # for agent in groupchat.agents:
            #     agent.reset()
            
            # print(f"[{self.session_id}] All components have been reset.")

def create_new_session() -> str:
    session = AutoGenSession()
    SESSIONS[session.session_id] = session
    return session.session_id

def get_session(session_id: str) -> AutoGenSession:
    return SESSIONS.get(session_id)