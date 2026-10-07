import importlib
import os
import sys
import traceback

PLUGINS_DIR = "plugins"


class PluginManager:
    def __init__(self, main_app):
        self.main_app = main_app
        self.loaded_plugins = {}
        self.failed_plugins = {}
        self.agent_tools = []  # 传给 OpenAI API 的 tools 列表
        self.agent_tool_map = {}  # 工具名 -> 回调函数的映射

    def load_all_plugins(self):
        """扫描并动态加载 plugins 目录下的所有插件"""
        self.loaded_plugins.clear()
        self.failed_plugins.clear()
        self.agent_tools.clear()
        self.agent_tool_map.clear()

        if not os.path.exists(PLUGINS_DIR):
            os.makedirs(PLUGINS_DIR, exist_ok=True)
            return

        plugins_abs_path = os.path.abspath(PLUGINS_DIR)
        if plugins_abs_path not in sys.path:
            sys.path.insert(0, plugins_abs_path)

        for item in os.listdir(PLUGINS_DIR):
            item_path = os.path.join(PLUGINS_DIR, item)
            module_name = None

            if os.path.isdir(item_path):
                if os.path.exists(os.path.join(item_path, "main.py")) or os.path.exists(
                        os.path.join(item_path, "__init__.py")):
                    module_name = item
            elif item.endswith(".py") and not item.startswith("__"):
                module_name = item[:-3]

            if module_name:
                self._load_single_plugin(module_name)

        self._notify_user_on_startup()

    def _load_single_plugin(self, module_name):
        try:
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
            else:
                module = importlib.import_module(module_name)

            if hasattr(module, "setup") and callable(module.setup):
                plugin_instance = module.setup(self.main_app)
                self.loaded_plugins[module_name] = plugin_instance

                # 1. 优先尝试从模块顶层获取 get_tools
                get_tools_func = getattr(module, "get_tools", None)

                # 2. 从子模块 (如 main.py) 里尝试获取
                if not get_tools_func and hasattr(module, "main"):
                    get_tools_func = getattr(module.main, "get_tools", None)

                # 3. 从插件实例对象本身尝试获取
                if not get_tools_func and hasattr(plugin_instance, "get_tools"):
                    get_tools_func = getattr(plugin_instance, "get_tools", None)

                # 提取并注册工具
                if get_tools_func and callable(get_tools_func):
                    tools, tool_map = get_tools_func()
                    self.agent_tools.extend(tools)
                    self.agent_tool_map.update(tool_map)

                print(f"[INFO] ✅ 插件 [{module_name}] 加载成功！")
            else:
                raise AttributeError("插件未找到必要的入口函数 `setup(app)`")

        except Exception as e:
            error_details = traceback.format_exc()
            self.failed_plugins[module_name] = str(e)
            print(f"[ERROR] ❌ 插件 [{module_name}] 加载失败并已跳过:\n{error_details}")

    def execute_tool(self, tool_name, arguments):
        """执行 Agent 触发的 Tool，并返回结果"""
        if tool_name in self.agent_tool_map:
            try:
                func = self.agent_tool_map[tool_name]
                result = func(**arguments)
                return str(result)
            except Exception as e:
                return f"执行工具 [{tool_name}] 报错: {e}"
        return f"未知工具 [{tool_name}]"

    def _notify_user_on_startup(self):
        success_count = len(self.loaded_plugins)
        fail_count = len(self.failed_plugins)

        if fail_count > 0:
            failed_names = ", ".join(self.failed_plugins.keys())
            msg = f"⚠️ 部分插件加载失败: {failed_names}"
            print(f"[WARNING] {msg}")
            if hasattr(self.main_app, "show_bubble_message"):
                self.main_app.show_bubble_message(msg)
        elif success_count > 0:
            print(f"[INFO] 所有插件加载完成，已注册 {len(self.agent_tools)} 个 AI Agent 工具函数。")