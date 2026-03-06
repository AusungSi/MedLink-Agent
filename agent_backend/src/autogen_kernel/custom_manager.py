# 文件路径: src/autogen_kernel/custom_manager.py

import autogen
from typing import Dict, Any, Optional

class CustomGroupChatManager(autogen.GroupChatManager):
    """
    自定义的 GroupChatManager，旨在解决两个核心问题：
    1. 状态污染：确保在每次对话开始时，内部状态（如对话历史）是干净的。
    2. Speaker丢失：在工具执行后，保留真实的执行者（speaker）身份，而不是统一显示为 Orchestrator。
    """

    def run_chat(self, messages: list[dict], sender: autogen.Agent, config: Any | None = None) -> tuple[bool, Any | None]:
        """
        重写 run_chat 方法，以在对话开始时强制重置智能体状态。
        这是解决多测试用例之间状态污染的关键。
        """
        # 当 GroupChatManager 接收到由 initiate_chat 发来的第一条消息时，
        # 意味着一个新的对话任务开始了。此时是重置所有成员状态的最佳时机。
        if len(self.groupchat.messages) <= 1:
            print(f"[{self.name}] New chat detected. Resetting all agents in the group chat.")
            self.groupchat.reset()
            for agent in self.groupchat.agents:
                agent.reset()

        return super().run_chat(messages, sender, config)

    def send(self, message: str | Dict, recipient: autogen.Agent, request_reply: bool | None = None, silent: bool | None = False) -> bool | None:
        """
        重写 send 方法，以拦截和修正工具执行后的返回消息。
        """
        # Autogen 内部，当一个工具调用被执行后，UserProxyAgent 会调用 GroupChatManager 的 send 方法，
        # 并将工具的输出作为 message 的内容。此时的 recipient 是 GroupChatManager 自己。
        # 我们在这里拦截这个过程。
        
        # 检查消息是否是工具调用的结果（通常是一个字符串或字典）
        # 并且发送者是 UserProxyAgent（工具执行者）
        if recipient == self and isinstance(message, (str, dict)):
            # 这是 Human_User_Proxy 执行完工具后返回结果的时刻
            
            # Autogen 的默认行为是将这个结果包装成一条新消息，
            # 但 speaker 会变成 GroupChatManager (Orchestrator)。
            # 我们不希望这样，因为这会破坏我们的 custom_speaker_selection_func 逻辑。
            # Human_User_Proxy 自身在执行完工具后，已经通过 register_reply 将结果
            # 作为自己的发言加入了对话历史。
            # 因此，我们在这里要做的就是 *什么都不做*，直接返回，
            # 防止 GroupChatManager 额外生成一条错误的 "Orchestrator" 消息。
            
            # 这个 silent=True 的调用可以被认为是工具执行后，执行者自己对结果的“内部确认”。
            # 我们阻止它被广播，因为它已经被正确地记录了。
            print(f"[{self.name}] Intercepted tool result message. Suppressing redundant message generation.")
            return True # 返回 True 表示消息处理成功，但我们实际上阻止了它

        return super().send(message, recipient, request_reply, silent)