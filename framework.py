import json5
from typing import Dict, Any, List, Callable

class AIFCFramework:
    def __init__(self):
        self.functions: Dict[str, Callable] = {}
        self.descriptions: Dict[str, str] = {}
        self.params_docs: Dict[str, Dict] = {}
        self.return_docs: Dict[str, Dict] = {}

    def create_function(
        self,
        name: str,
        func: Callable,
        description: str,
        params_dict: Dict[str, str],
        return_dict: Dict[str, str]
    ) -> None:
        self.functions[name] = func
        self.descriptions[name] = description
        self.params_docs[name] = params_dict
        self.return_docs[name] = return_dict

    def generate_system_prompt(self) -> str:
        """生成包含函数说明和连续 FC 支持的系统提示词"""
        prompt = """
请首先判断用户的问题是否需要调用函数来回答。即使用户未明确要求调用函数，若问题可通过函数回答，则必须调用函数。
如果需要调用函数，请**仅返回以下格式的JSON，不添加任何其他文本**：
[
    {
        "func": "函数名称",
        "args": {
            "参数名": "参数值"
        }
    }
]
若需调用多个函数，则返回：
[
    {
        "func": "函数名称1",
        "args": {
            "参数名1": "参数值1"
        }
    },
    {
        "func": "函数名称2",
        "args": {
            "参数名2": "参数值2"
        }
    }
]
**如果在接收到函数调用的结果后，仍然需要进一步的信息或操作，可以再次调用函数。**
**当你认为已经获得足够的信息来回答用户的问题时，请用自然语言提供最终的回答。**
函数可能返回单个或多个结果。
可用函数列表：\n\n"""

        for func_name in self.functions:
            prompt += f"{func_name} - {self.descriptions[func_name]}\n"
            prompt += "参数:\n"
            for param, desc in self.params_docs[func_name].items():
                prompt += f"- {param}: {desc}\n"
            prompt += "返回:\n"
            for ret, desc in self.return_docs[func_name].items():
                prompt += f"- {ret}: {desc}\n"
            prompt += "\n"

        return prompt

    def parse_ai_response(self, content: str) -> List[Dict[str, Any]]:
        try:
            results = []
            current_pos = 0
            
            while current_pos < len(content):
                # 查找下一个 JSON 开始位置
                start_positions = []
                for char in ['{', '[']:
                    pos = content.find(char, current_pos)
                    if pos != -1:
                        start_positions.append(pos)
                start_positions = [content.find(char, current_pos) for char in ['{', '[']]
                start_positions = [pos for pos in start_positions if pos != -1]
                
                if not start_positions:
                    break
                    
                json_start = min(start_positions)
                
                # 从开始位置往后查找对应的结束符号
                bracket_map = {'{': '}', '[': ']'}
                start_char = content[json_start]
                end_char = bracket_map[start_char]
                end_char = '}' if start_char == '{' else ']'
                
                count = 0
                for i in range(json_start, len(content)):
                    if content[i] == start_char:
                        count += 1
                    elif content[i] == end_char:
                        count -= 1
                        if count == 0:
                            json_content = content[json_start:i+1]

                            parsed = json5.loads(json_content)
                            if isinstance(parsed, dict):
                                parsed = [parsed]
                                
                            if isinstance(parsed, list):
                                for function_call in parsed:
                                    if "func" in function_call and "args" in function_call:
                                        result = self.execute_function(
                                            function_call.get('func'),
                                            function_call.get('args', {})
                                        )
                                        results.append(result)
                                    else:
                                        results.append({"error": "Invalid function call format"})
                            
                            current_pos = i + 1
                            break
                else:
                    results.append({"error": "Invalid JSON format"})
                    break

            return results
            
        except Exception as e:
            print([{"error": str(e)}])
            return []

    def execute_function(self, func_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if func_name not in self.functions:
            return {
                "error": f"Function {func_name} not found",
                "type": "error",
                "value": "Function not registered"
            }
        try:
            result = self.functions[func_name](**args)
            return self.format_result(result)
        except Exception as e:
            print("Function execution failed, error:", str(e))
            return {
                "error": str(e),
                "type": "error",
                "value": "Execution failed"
            }

    def format_result(self, result: Any) -> Dict[str, Any]:
        """格式化函数返回结果"""
        if isinstance(result, dict) and "type" in result and "value" in result:
            return result
        if isinstance(result, dict):
            return {
                "type": "dict",
                "value": json5.dumps(result, ensure_ascii=False)
            }
        return {
            "type": str(type(result).__name__),
            "value": str(result)
        }