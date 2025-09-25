'''
基础模型，使用火山的deepseekv3
用来判断用户意图，进行工具调用等
'''
import os
import json
from typing import List, Dict, Any, Optional, Union, Callable
import time
from openai import OpenAI
from config import SYSTEM_PROMPT




class ChatBot:
    def __init__(
        self, 
        api_key: str = None, 
        base_url: str = "https://api.openai.com/v1", 
        model: str = "gpt-3.5-turbo",
        system_message: str = SYSTEM_PROMPT
    ):
        """
        初始化ChatBot类
        
        Args:
            api_key: OpenAI API密钥，如果为None则从环境变量OPENAI_API_KEY获取
            base_url: API基础URL，可自定义为其他兼容OpenAI API的服务
            model: 使用的模型名称或推理接入点ID
            system_message: 系统预设指令
        """
        self.api_key = api_key 
        if not self.api_key:
            raise ValueError("API key is required. Either pass it directly or set OPENAI_API_KEY environment variable.")
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            base_url=base_url,
            api_key=self.api_key
        )
        
        self.model = model
        self.conversation_history = [{"role": "system", "content": system_message}]
        self.tools = []
        self.function_map = {}
         
    def set_system_message(self, message: str) -> None:
        """
        更新系统预设指令
        
        Args:
            message: 新的系统预设指令
        """
        if self.conversation_history and self.conversation_history[0]["role"] == "system":
            self.conversation_history[0]["content"] = message
        else:
            self.conversation_history.insert(0, {"role": "system", "content": message})
    
    def get_system_message(self) -> str:
        """获取当前系统预设指令"""
        for msg in self.conversation_history:
            if msg["role"] == "system":
                return msg["content"]
        return ""
    
    def clear_history(self, keep_system_message: bool = True) -> None:
        """
        清除对话历史
        
        Args:
            keep_system_message: 是否保留系统预设指令
        """
        if keep_system_message:
            system_msg = self.get_system_message()
            self.conversation_history = [{"role": "system", "content": system_msg}] if system_msg else []
        else:
            self.conversation_history = []
    
    def chat(self, message: str, stream: bool = False) -> Any:
        """
        发送消息给LLM并获取回复
        
        Args:
            message: 用户消息
            stream: 是否使用流式响应
            
        Returns:
            完整的API响应
        """
        # 添加用户消息到历史
        self.conversation_history.append({"role": "user", "content": message})
        
        # 准备请求参数
        params = {
            "model": self.model,
            "messages": self.conversation_history,
            "stream": stream
        }
        
        # 如果有工具定义，添加到请求中
        if self.tools:
            params["tools"] = self.tools
            params["tool_choice"] = "auto"
        
        try:
            if not stream:
                # 非流式请求
                response = self.client.chat.completions.create(**params)
                
                # 获取助手消息
                assistant_message = {
                    "role": "assistant",
                    "content": response.choices[0].message.content
                }
                
                # 添加助手消息到历史
                self.conversation_history.append(assistant_message)
                
                # 返回助手消息内容
                return response.choices[0].message.content
            else:
                # 流式响应处理
                stream_response = self.client.chat.completions.create(**params)

                collected_content = ""
                
                for chunk in stream_response:
                    if not chunk.choices:
                        continue
                    
                    delta = chunk.choices[0].delta
                    if delta.content:
                        print(delta.content, end="", flush=True)
                        collected_content += delta.content
                
                print()  # 换行
                
                # 添加到历史
                self.conversation_history.append({
                    "role": "assistant", 
                    "content": collected_content
                })
                
                # 注意：流式响应不处理工具调用，如需工具调用，应使用非流式模式
                return stream_response
        
        except Exception as e:
            print(f"Error during API call: {e}")
            error_message = f"API call failed: {str(e)}"
            self.conversation_history.append({"role": "assistant", "content": error_message})
            return {"error": error_message}
    
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """获取完整对话历史"""
        return self.conversation_history
    

# 使用示例
def main():

    # 初始化聊天机器人，设置系统预设指令
    bot = ChatBot(
        api_key="sk-",
        base_url="http://192.168.20.94:8000/v1",  # 可以替换为其他兼容OpenAI API的服务地址
        model="qwen2.5-HA-0.5B-ctx-ax650",  # 替换为你的推理接入点ID
        system_message=SYSTEM_PROMPT
    )
    
    print("欢迎使用AI聊天机器人! 输入'exit'退出。")
    print(f"系统指令: {bot.get_system_message()}")
    print("-------------------------------------")
    
    while True:
        user_input = input("\n你: ")
        if user_input.lower() in ['exit', 'quit', 'bye']:
            print("机器人: 再见!")
            break
        
        # 处理特殊命令
        if user_input.startswith("/system "):
            # 更改系统指令
            new_system = user_input[8:]
            bot.set_system_message(new_system)
            print(f"系统指令已更新为: {new_system}")
            continue
        
        if user_input == "/clear":
            # 清除对话历史
            bot.clear_history()
            print("对话历史已清除。")
            continue
        
        if user_input == "/history":
            # 显示完整对话历史
            print("\n对话历史:")
            for msg in bot.get_conversation_history():
                role = msg['role']
                content = msg.get('content', '')
                # 确保内容正确显示中文
                print(f"{role}: {content[:100]}{'...' if len(content) > 100 else ''}")
                
            continue

        # 默认使用流式响应进行普通对话
        print("\n机器人: ", end="")
        # user_input += 'no_think'
        response = bot.chat(user_input, stream=False)
        print(response)
        

if __name__ == "__main__":
    main()
