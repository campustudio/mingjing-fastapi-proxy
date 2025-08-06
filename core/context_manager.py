# core/context_manager.py

from typing import List, Dict, Any

class ContextManager:
    def __init__(self, max_context_length: int = 10):
        """
        上下文管理器
        :param max_context_length: 最大保存的对话轮数
        """
        self.user_contexts: Dict[str, List[Dict[str, Any]]] = {}
        self.max_context_length = max_context_length
    
    def get_user_context(self, user_id: str = "default_user") -> List[Dict[str, Any]]:
        """获取用户的对话上下文"""
        return self.user_contexts.get(user_id, [])
    
    def add_message_to_context(self, message: Dict[str, Any], user_id: str = "default_user"):
        """
        添加消息到上下文
        :param message: 消息对象，包含 role 和 content
        :param user_id: 用户ID
        """
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = []
        
        # 避免重复添加相同的消息
        context = self.user_contexts[user_id]
        if not context or context[-1] != message:
            context.append(message)
            
            # 保持上下文长度在限制范围内
            if len(context) > self.max_context_length * 2:  # *2 因为每轮对话包含user和assistant
                # 移除最旧的一轮对话（保留system消息）
                while len(context) > self.max_context_length * 2:
                    if context[0].get("role") != "system":
                        context.pop(0)
                    else:
                        # 如果第一个是system消息，移除第二个
                        if len(context) > 1:
                            context.pop(1)
                        else:
                            break
    
    def build_context_messages(self, current_messages: List[Dict[str, Any]], user_id: str = "default_user") -> List[Dict[str, Any]]:
        """
        构建包含上下文的完整消息列表
        :param current_messages: 当前请求的消息
        :param user_id: 用户ID
        :return: 合并上下文后的消息列表
        """
        # 先添加当前用户消息到上下文
        for msg in current_messages:
            if msg.get("role") == "user":
                self.add_message_to_context(msg, user_id)
        
        # 获取更新后的上下文
        context = self.get_user_context(user_id)
        
        # 构建完整的消息列表
        # 1. 找到system消息（从当前消息中）
        system_messages = [msg for msg in current_messages if msg.get("role") == "system"]
        
        # 2. 获取历史上下文（排除system消息）
        context_messages = [msg for msg in context if msg.get("role") != "system"]
        
        # 3. 构建最终消息列表：system + 历史上下文（已包含当前用户消息）
        final_messages = system_messages + context_messages
        
        return final_messages
    
    def add_assistant_response(self, response_content: str, user_id: str = "default_user"):
        """
        添加助手回复到上下文
        :param response_content: 助手回复内容
        :param user_id: 用户ID
        """
        assistant_message = {
            "role": "assistant", 
            "content": response_content
        }
        self.add_message_to_context(assistant_message, user_id)
    
    def clear_context(self, user_id: str = "default_user"):
        """清空用户上下文"""
        if user_id in self.user_contexts:
            del self.user_contexts[user_id]

# 全局上下文管理器实例
context_manager = ContextManager()
