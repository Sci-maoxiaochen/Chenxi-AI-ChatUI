import os

# 窗口与 UI 配置
WINDOW_WIDTH = 200
WINDOW_HEIGHT = 200

# 皮肤配置
DEFAULT_SKIN = "default"
CURRENT_SKIN = DEFAULT_SKIN

# 日志配置
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# 确保日志目录存在
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)