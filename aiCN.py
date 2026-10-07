import websocket
import json
from typing import Dict, List, Callable, Optional
import platform
import subprocess
from framework import AIFCFramework

class OpenAIAPI:
    def __init__(self, api_key: str, api_url: str = "wss://chat.breathai.top/api/chat"):
        self.api_key = api_key
        self.api_url = api_url
        self.ws = None
        self.fc_framework = AIFCFramework()
        self.message_history: List[Dict[str, str]] = []

    def register(self, description: str, params_dict: Dict[str, str], return_dict: Dict[str, str]):
        """装饰器，用于注册函数"""
        def decorator(func: Callable):
            self.fc_framework.create_function(func.__name__, func, description, params_dict, return_dict)
            return func
        return decorator

    def register_function(self, name: str, func: Callable, description: str, 
                         params_dict: Dict[str, str], return_dict: Dict[str, str]):
        """手动注册函数"""
        self.fc_framework.create_function(name, func, description, params_dict, return_dict)

    def add_to_history(self, role: str, content: str):
        self.message_history.append({"role": role, "content": content})

    def get_messages_with_history(self, system_prompt: str, current_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.message_history)
        if current_prompt is not None:
            messages.append({"role": "user", "content": current_prompt})
        return messages

    def _connect_websocket(self,system_prompt):
        """建立WebSocket连接"""
        if not self.ws or not self.ws.connected:
            self.ws = websocket.create_connection(self.api_url)
            # 发送认证消息
            auth_message = {
                "token": self.api_key,
                "id": -1
            }
            self.ws.send(json.dumps(auth_message))
                        # 构造mask消息
            mask_payload = {
                "type": "mask",
                "message": json.dumps([
                    {
                        "role": "system",
                        "content": system_prompt
                    }
                ]),
                "model": "event"
            }

            # 发送mask消息
            self.ws.send(json.dumps(mask_payload))

    def _process_conversation(self, system_prompt: str, temperature: float, depth: int = 0, 
                            model: str = "deepseek-v3-free", max_tokens: int = 4000, 
                            context: int = 8, web: bool = True,
                            top_p: float = 1.0, top_k: int = 5, 
                            presence_penalty: float = 0.0, frequency_penalty: float = 0.0,
                            repetition_penalty: float = 1.0) -> Optional[str]:
        """使用WebSocket处理AI响应"""
        if depth > 10:
            return "错误：超过最大递归深度。"

        try:
            self._connect_websocket(system_prompt)

            # 构造chat消息
            chat_payload = {
                "type": "chat",
                "message": self.get_messages_with_history(system_prompt, None)[-1]["content"],
                "web": web,
                "model": model,
                "context": context,
                "ignore_context": False,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "presence_penalty": presence_penalty,
                "frequency_penalty": frequency_penalty,
                "repetition_penalty": repetition_penalty
            }

            self.ws.send(json.dumps(chat_payload))

            # 接收流式响应
            complete_response = ""
            while True:
                response = self.ws.recv()
                result = json.loads(response)

                if "message" in result:
                    complete_response += result["message"]

                # 检查是否是最后一条消息
                if result.get("end", False) is True:
                    break

            self.add_to_history("assistant", complete_response)

            function_results = self.fc_framework.parse_ai_response(complete_response)
            if not function_results:
                return complete_response
        
            self.add_to_history("function", json.dumps(function_results, ensure_ascii=False))
            return self._process_conversation(system_prompt, temperature, depth + 1, model, max_tokens, context, web, top_p, top_k, presence_penalty, frequency_penalty, repetition_penalty)
        except Exception as e:
            print(f"WebSocket错误: {e}")
            return None

    def chat(self, prompt: str, temperature: float = 0.7, max_tokens: int = 4000, 
             model: str = "deepseek-v3-free", context: int = 8, web: bool = True,
             top_p: float = 1.0, top_k: int = 5, 
             presence_penalty: float = 0.0, frequency_penalty: float = 0.0,
             repetition_penalty: float = 1.0) -> Optional[str]:
        """启动对话，调用递归处理函数"""
        system_prompt = self.fc_framework.generate_system_prompt()
        self.add_to_history("user", prompt)
        return self._process_conversation(
            system_prompt=system_prompt,
            temperature=temperature,
            depth=0,
            model=model,
            max_tokens=max_tokens,
            context=context,
            web=web,
            top_p=top_p,
            top_k=top_k,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            repetition_penalty=repetition_penalty
        )

    def close_websocket(self):
        self.message_history.clear()
        if self.ws:
            self.ws.close()
            self.ws = None

# 创建 API 客户端
api_key = "Enter your api key here" # 替换为你的token
client = OpenAIAPI(api_key)

# 使用装饰器注册函数
@client.register(
    description='系统运行命令,当前系统为' + platform.system() + ' 例如:用户:"我的系统架构是什么?",则可调用该函数"',
    params_dict={'command': '要运行的命令'},
    return_dict={'value': '命令执行结果'}
)
def run_command(command: str):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {'value': result.stdout, 'status': 'success' if result.stderr == '' else 'error'}

def main():
    while True: 
        response = client.chat(input("Please enter the message:"))
        print(response)
    # return response

# 示例运行
if __name__ == "__main__":
    print(main())
