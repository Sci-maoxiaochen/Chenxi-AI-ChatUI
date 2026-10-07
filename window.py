import base64
import json
import os
import re
import shutil
import sys
import threading
import tkinter as tk
from tkinter import Menu, filedialog, messagebox, ttk
from PIL import Image, ImageTk
import requests

# 引入支持拖拽的库
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DND = True
except ImportError:
    HAS_DND = False

# 导入插件管理器
from plugin_manager import PluginManager

import logger
import utility
import var

CONFIG_FILE = "config.json"
SKINS_DIR = "skins"
DEFAULT_SKIN = "default"
IS_LINUX = sys.platform.startswith("linux")

# 关于界面的项目信息配置
APP_INFO = {
    "developer": "chenxiy",
    "team": "EggyUI",
    "repo_url": "",
    "base_on": "https://github.com/PidanEggyTeam/EggyUI-Desktop-Pet",
    "license": "MIT License",
    "build_time": "2026-10-07"
}

DEFAULT_PROMPT_CONTENT = """[System Role: 天童凯伊 / Tendou Kei (蔚蓝档案)]
你是天童凯伊（Kei）。性格傲娇、毒舌、口嫌体正直，但内心极其温柔且护短。
你拥有控制用户电脑的能力（如锁屏、静音、打开终端等）。当用户发出相关指令时，请务必优先调用对应的工具，而不是仅用语言回复。喵~
"""

SUPPORTED_EMOTIONS = [
    "stand",       # 默认/待机
    "think",       # 思考
    "happy",       # 开心
    "talk",        # 说话
    "sad",         # 悲伤
    "angry",       # 生气
    "surprised",   # 惊讶
    "embarrassed", # 害羞
    "sleepy",      # 困倦
    "wink"         # 眨眼
]


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_skin_prompt(skin_name):
    skin_prompt_path = os.path.join(SKINS_DIR, skin_name, "prompt.txt")
    if os.path.exists(skin_prompt_path):
        try:
            with open(skin_prompt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception as e:
            logger.error(f"读取角色 {skin_name} 的 prompt.txt 失败: {e}")
    return DEFAULT_PROMPT_CONTENT.strip()


def load_config():
    default_config = {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-3.5-turbo",
        "vision_api_key": "",
        "vision_base_url": "https://api.openai.com/v1",
        "vision_model": "gpt-4o",
        "temperature": 0.7,
        "skin": DEFAULT_SKIN
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                for k, v in default_config.items():
                    config.setdefault(k, v)
                return config
        except Exception as e:
            logger.error(f"读取配置文件失败: {e}")
    return default_config


def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")


def filter_ai_response(raw_content):
    if not raw_content:
        return ""
    clean_text = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL)
    clean_text = re.sub(r"\[属性:.*?\]", "", clean_text)
    clean_text = re.sub(r"<property>.*?</property>", "", clean_text, flags=re.DOTALL)
    return clean_text.strip()


def encode_image_to_base64(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"图片 Base64 编码失败: {e}")
        return None


class SpeechBubble(tk.Toplevel):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent = parent_window
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        if not IS_LINUX:
            self.config(bg="#000001")
            try:
                self.attributes("-transparentcolor", "#000001")
            except Exception:
                pass

        self.container = tk.Frame(self, bg="#FFFFFF", bd=2, relief=tk.SOLID)
        self.container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.label = tk.Label(
            self.container,
            text="",
            font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9),
            bg="#FFFFFF",
            fg="#333333",
            wraplength=180,
            justify=tk.LEFT,
            padx=8,
            pady=8
        )
        self.label.pack(fill=tk.BOTH, expand=True)

        self.hide_timer = None
        self.withdraw()

    def show_text(self, text, duration_ms=6000):
        clean_text = filter_ai_response(text)
        if not clean_text:
            return

        self.label.config(text=clean_text)
        self.update_geometry()
        self.deiconify()

        if self.hide_timer:
            self.after_cancel(self.hide_timer)
        self.hide_timer = self.after(duration_ms, self.withdraw)

    def update_geometry(self):
        self.update_idletasks()
        px = self.parent.winfo_x()
        py = self.parent.winfo_y()
        pw = self.parent.winfo_width()

        bw = self.winfo_reqwidth()
        bh = self.winfo_reqheight()

        x = px + pw + 5
        y = py - 10
        screen_w = self.winfo_screenwidth()
        if x + bw > screen_w:
            x = px - bw - 5

        self.geometry(f"{bw}x{bh}+{x}+{y}")


class DynamicSkinRenderer:
    """自适应大小与支持拉伸缩放的立绘渲染器"""

    def __init__(self, canvas):
        self.canvas = canvas
        self.current_skin = DEFAULT_SKIN
        self.current_action = "stand"
        self.original_image = None
        self.frames = []
        self.frame_index = 0
        self.anim_timer = None
        self.reset_timer = None

        self.current_photo = None
        self.image_item = None

    def find_action_file(self, skin_name, action):
        skin_dir = os.path.join(SKINS_DIR, skin_name)
        candidates = [
            os.path.join(skin_dir, f"{action}.gif"),
            os.path.join(skin_dir, f"{action}.png"),
            os.path.join(skin_dir, f"{action}.jpg"),
            os.path.join(skin_dir, f"{action}.webp"),
            os.path.join(skin_dir, "stand.gif"),
            os.path.join(skin_dir, "stand.png"),
            os.path.join(skin_dir, "default.png"),
            resource_path("assets/image.png")
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def load_action(self, skin_name, action="stand", auto_reset_ms=0, on_reset_callback=None):
        self.current_skin = skin_name
        self.current_action = action

        if self.anim_timer:
            self.canvas.after_cancel(self.anim_timer)
            self.anim_timer = None

        if self.reset_timer:
            self.canvas.after_cancel(self.reset_timer)
            self.reset_timer = None

        target_file = self.find_action_file(skin_name, action)

        if target_file:
            if target_file.endswith(".gif"):
                self.play_gif(target_file)
            else:
                self.show_static(target_file)

        if auto_reset_ms > 0 and action != "stand":
            def do_reset():
                self.load_action(skin_name, "stand")
                if on_reset_callback:
                    on_reset_callback()

            self.reset_timer = self.canvas.after(auto_reset_ms, do_reset)

    def show_static(self, img_path):
        try:
            self.original_image = Image.open(img_path).convert("RGBA")
            self.redraw()
        except Exception as e:
            logger.error(f"加载静态图片失败 [{img_path}]: {e}")

    def play_gif(self, gif_path):
        try:
            im = Image.open(gif_path)
            self.frames = []
            for frame_idx in range(0, im.n_frames):
                im.seek(frame_idx)
                frame = im.convert("RGBA")
                self.frames.append((frame, im.info.get('duration', 100)))

            self.frame_index = 0
            self._render_gif_frame()
        except Exception as e:
            logger.error(f"播放 GIF 失败 [{gif_path}]: {e}")

    def _render_gif_frame(self):
        if not self.frames:
            return
        frame_img, delay = self.frames[self.frame_index]
        self.original_image = frame_img
        self.redraw()

        self.frame_index = (self.frame_index + 1) % len(self.frames)
        self.anim_timer = self.canvas.after(delay, self._render_gif_frame)

    def redraw(self):
        if not self.original_image:
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()

        if cw <= 1 or ch <= 1:
            cw, ch = self.original_image.size

        resized = self.original_image.resize((cw, ch), Image.Resampling.LANCZOS)
        self.current_photo = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.image_item = self.canvas.create_image(0, 0, anchor="nw", image=self.current_photo)


BaseTkClass = TkinterDnD.Tk if HAS_DND else tk.Tk


class TransparentWindow(BaseTkClass):
    """跨平台透明窗口（支持鼠标拖拽移动，Ctrl+滚轮缩放立绘，支持扩展插件）"""

    def __init__(self):
        super().__init__()

        logger.info("初始化跨平台透明自适应窗口")

        # 1. 窗口样式与置顶
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # 2. Linux 与 Windows 差异化透明机制处理
        self.TRANS_COLOR = "#000001"
        self.config(bg=self.TRANS_COLOR)

        if IS_LINUX:
            try:
                self.attributes('-type', 'dock')
            except Exception:
                pass
            try:
                self.attributes('-alpha', 1.0)
            except Exception:
                pass
            try:
                self.attributes("-transparentcolor", self.TRANS_COLOR)
            except Exception:
                pass
        else:
            try:
                self.attributes("-transparentcolor", self.TRANS_COLOR)
            except Exception:
                pass

        self.ai_settings = load_config()

        # 3. Canvas 画布
        self.canvas = tk.Canvas(
            self,
            bg=self.TRANS_COLOR,
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.renderer = DynamicSkinRenderer(self.canvas)

        # 4. 初始化图形大小与默认比例
        skin = self.ai_settings.get("skin", DEFAULT_SKIN)
        init_file = self.renderer.find_action_file(skin, "stand")
        self.base_aspect_ratio = 1.33  # 默认高宽比备用
        if init_file:
            try:
                with Image.open(init_file) as im:
                    self.original_w, self.original_h = im.size
                    self.base_aspect_ratio = self.original_h / self.original_w
                    self.geometry(f"{self.original_w}x{self.original_h}+500+200")
            except Exception:
                self.original_w, self.original_h = 300, 400
                self.geometry("300x400+500+200")
        else:
            self.original_w, self.original_h = 300, 400
            self.geometry("300x400+500+200")

        self.renderer.load_action(skin, "stand")

        self.bubble = SpeechBubble(self)

        # 5. 绑定事件：按住拖拽窗口与 Ctrl+滚轮缩放大小
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.do_drag)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.show_context_menu)

        # 绑定 Ctrl + 鼠标滚轮缩放事件（支持 Windows 和 Linux）
        self.bind("<Control-MouseWheel>", self.on_ctrl_mouse_wheel)  # Windows
        self.bind("<Control-Button-4>", self.on_ctrl_mouse_wheel)    # Linux 向上滚动
        self.bind("<Control-Button-5>", self.on_ctrl_mouse_wheel)    # Linux 向下滚动

        # 窗口大小改变时自动重绘立绘
        self.bind("<Configure>", self.on_window_resize)

        self.chat_window = None

        # 6. 初始化并自动加载扩展插件系统
        self.plugin_manager = PluginManager(self)
        self.after(1000, self.plugin_manager.load_all_plugins)

    def on_window_resize(self, event):
        if event.widget == self:
            self.renderer.redraw()

    def start_drag(self, event):
        self._start_x_root = event.x_root
        self._start_y_root = event.y_root
        self._start_win_x = self.winfo_x()
        self._start_win_y = self.winfo_y()

    def do_drag(self, event):
        dx = event.x_root - self._start_x_root
        dy = event.y_root - self._start_y_root
        x = self._start_win_x + dx
        y = self._start_win_y + dy
        self.geometry(f"+{x}+{y}")
        self.bubble.update_geometry()

    def on_ctrl_mouse_wheel(self, event):
        """按住 Ctrl 滚动鼠标滚轮缩放桌宠大小（保持等比例）"""
        if event.delta:
            direction = 1 if event.delta > 0 else -1
        elif event.num == 4:
            direction = 1
        elif event.num == 5:
            direction = -1
        else:
            return

        current_w = self.winfo_width()
        step = 25

        if direction > 0:
            new_w = current_w + step
        else:
            new_w = max(100, current_w - step)  # 最小宽度限制为 100px

        new_h = int(new_w * self.base_aspect_ratio)
        self.geometry(f"{new_w}x{new_h}")
        self.bubble.update_geometry()

    def set_emotion(self, action="stand", auto_reset_ms=0):
        skin = self.ai_settings.get("skin", DEFAULT_SKIN)
        self.renderer.load_action(skin, action, auto_reset_ms)

    def show_bubble_message(self, text, duration_ms=6000):
        self.bubble.show_text(text, duration_ms)

    def on_double_click(self, event):
        self.open_chat_window()

    def show_context_menu(self, event):
        menu = Menu(self, tearoff=0)
        menu.add_command(label="💬 打开 AI 对话页面", command=self.open_chat_window)
        menu.add_command(label="⚙️ AI 模型与项目设置", command=self.show_ai_settings)
        menu.add_command(label="🎭 更换角色/皮肤", command=self.change_skin_dialog)
        menu.add_command(label="🪄 导入全新角色立绘 (支持拖拽/识图)", command=self.open_skin_wizard)
        menu.add_separator()
        menu.add_command(label="🔄 重新加载插件", command=self.plugin_manager.load_all_plugins)
        menu.add_separator()
        menu.add_command(label="❌ 退出程序", command=self.destroy)
        menu.tk_popup(event.x_root, event.y_root)

    def open_chat_window(self):
        if self.chat_window is None or not self.chat_window.winfo_exists():
            self.chat_window = ChatWindow(self, self.ai_settings)
        else:
            self.chat_window.deiconify()
            self.chat_window.focus_force()

    def show_ai_settings(self):
        dialog = ModelSettingsDialog(self, self.ai_settings)
        self.wait_window(dialog)
        if dialog.result:
            self.ai_settings.update(dialog.result)
            save_config(self.ai_settings)

    def change_skin_dialog(self):
        dialog = ChangeSkinDialog(self, self.ai_settings.get("skin", DEFAULT_SKIN))
        self.wait_window(dialog)
        if dialog.selected_skin:
            self.ai_settings["skin"] = dialog.selected_skin
            save_config(self.ai_settings)

            init_file = self.renderer.find_action_file(dialog.selected_skin, "stand")
            if init_file:
                try:
                    with Image.open(init_file) as im:
                        w, h = im.size
                        self.base_aspect_ratio = h / w
                        self.geometry(f"{w}x{h}")
                except Exception:
                    pass

            self.set_emotion("stand")
            if self.chat_window and self.chat_window.winfo_exists():
                self.chat_window.ai_settings = self.ai_settings

    def open_skin_wizard(self):
        wizard = SkinImportWizard(self, self.ai_settings)
        self.wait_window(wizard)
        if wizard.created_skin_name:
            self.ai_settings["skin"] = wizard.created_skin_name
            save_config(self.ai_settings)
            self.set_emotion("stand")


class SkinImportWizard(tk.Toplevel):
    def __init__(self, parent, ai_settings):
        super().__init__(parent)
        self.title("人物形象导入向导 (支持文件拖拽与多表情识别)")
        self.geometry("680x640")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self.ai_settings = ai_settings
        self.image_paths = []
        self.file_emotion_map = {}
        self.created_skin_name = None

        self.init_ui()

    def init_ui(self):
        frame_top = tk.LabelFrame(self, text=" 1. 角色基本信息 ",
                                  font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9, "bold"), padx=10, pady=8)
        frame_top.pack(fill=tk.X, padx=15, pady=8)

        tk.Label(frame_top, text="角色名称 (英文/拼音):").grid(row=0, column=0, sticky="e", padx=5)
        self.entry_name = tk.Entry(frame_top, width=20)
        self.entry_name.grid(row=0, column=1, sticky="w", padx=5)
        self.entry_name.insert(0, "new_character")

        tk.Button(
            frame_top,
            text="📁 浏览并选择图片 (按Ctrl/Shift可全选)",
            command=self.select_images,
            bg="#0078D4",
            fg="white",
            relief=tk.FLAT
        ).grid(row=0, column=2, padx=15)

        frame_mid = tk.LabelFrame(self, text=" 2. 立绘图片列表 (可直接从桌面拖拽图片/文件夹到下方) ",
                                  font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9, "bold"), padx=10, pady=8)
        frame_mid.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        self.drop_area = tk.Label(
            frame_mid,
            text="将图片文件拖拽至此处释放，或点击右上角按钮导入",
            bg="#F0F4F8",
            fg="#666666",
            font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9, "italic"),
            bd=2,
            relief=tk.GROOVE,
            height=2
        )
        self.drop_area.pack(fill=tk.X, pady=(0, 5))

        if HAS_DND:
            try:
                self.drop_area.drop_target_register(DND_FILES)
                self.drop_area.dnd_bind('<<Drop>>', self.on_file_drop)
            except Exception as e:
                logger.error(f"绑定拖拽事件失败: {e}")

        top_bar = tk.Frame(frame_mid)
        top_bar.pack(fill=tk.X, pady=(0, 5))

        tk.Button(top_bar, text="🤖 调用 Vision AI 自动归类表情", command=self.start_ai_analysis, bg="#2E7D32",
                  fg="white", relief=tk.FLAT).pack(side=tk.LEFT)
        tk.Button(top_bar, text="🗑️ 清空列表", command=self.clear_images, relief=tk.FLAT).pack(side=tk.RIGHT)

        columns = ("file", "emotion")
        self.tree = ttk.Treeview(frame_mid, columns=columns, show="headings", height=8)
        self.tree.heading("file", text="图片文件名")
        self.tree.heading("emotion", text="分配的表情/动作 (双击可修改)")
        self.tree.column("file", width=400)
        self.tree.column("emotion", width=200)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = ttk.Scrollbar(frame_mid, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self.on_double_click_row)

        frame_bottom = tk.LabelFrame(self, text=" 3. 角色预设提示词 (System Prompt) ",
                                     font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9, "bold"), padx=10,
                                     pady=8)
        frame_bottom.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        self.txt_prompt = tk.Text(frame_bottom, height=4, font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9))
        self.txt_prompt.pack(fill=tk.BOTH, expand=True)
        self.txt_prompt.insert("1.0", DEFAULT_PROMPT_CONTENT)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=15, pady=10)

        tk.Button(btn_frame, text="✅ 完成保存并切换", command=self.save_and_apply, width=18, bg="#0078D4", fg="white",
                  relief=tk.FLAT).pack(side=tk.RIGHT, padx=5)
        tk.Button(btn_frame, text="取消", command=self.destroy, width=10).pack(side=tk.RIGHT, padx=5)

    def select_images(self):
        files = filedialog.askopenfilenames(
            title="请选择图片（按 Ctrl+A 可全选）",
            filetypes=[("支持的图片/动画", "*.png *.jpg *.jpeg *.gif *.webp")]
        )
        if files:
            self.add_files(files)

    def on_file_drop(self, event):
        raw_data = event.data
        files = self.parse_drop_paths(raw_data)
        valid_files = []
        valid_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

        for f in files:
            if os.path.isfile(f) and os.path.splitext(f)[1].lower() in valid_exts:
                valid_files.append(f)
            elif os.path.isdir(f):
                for root, _, filenames in os.walk(f):
                    for fn in filenames:
                        if os.path.splitext(fn)[1].lower() in valid_exts:
                            valid_files.append(os.path.join(root, fn))

        if valid_files:
            self.add_files(valid_files)

    def parse_drop_paths(self, raw_data):
        pattern = r'\{([^}]+)\}|(\S+)'
        matches = re.findall(pattern, raw_data)
        paths = []
        for match in matches:
            path = match[0] if match[0] else match[1]
            paths.append(path)
        return paths

    def add_files(self, paths):
        for p in paths:
            abs_p = os.path.abspath(p)
            if abs_p not in self.image_paths:
                self.image_paths.append(abs_p)
                fn = os.path.basename(abs_p).lower()
                matched_emo = "stand"
                for emo in SUPPORTED_EMOTIONS:
                    if emo in fn:
                        matched_emo = emo
                        break
                self.file_emotion_map[abs_p] = matched_emo

        self.refresh_tree()

    def clear_images(self):
        self.image_paths.clear()
        self.file_emotion_map.clear()
        self.refresh_tree()

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for path in self.image_paths:
            filename = os.path.basename(path)
            emotion = self.file_emotion_map.get(path, "stand")
            self.tree.insert("", tk.END, values=(filename, emotion), tags=(path,))

    def on_double_click_row(self, event):
        selected = self.tree.selection()
        if not selected:
            return

        item = selected[0]
        file_path = self.tree.item(item, "tags")[0]

        dlg = tk.Toplevel(self)
        dlg.title("修改表情映射")
        dlg.geometry("280x130")
        dlg.attributes("-topmost", True)

        tk.Label(dlg, text="修改此图对应的表情/状态:").pack(pady=10)
        combo = ttk.Combobox(dlg, values=SUPPORTED_EMOTIONS, state="readonly")
        combo.set(self.file_emotion_map.get(file_path, "stand"))
        combo.pack(pady=5)

        def save_choice():
            self.file_emotion_map[file_path] = combo.get()
            dlg.destroy()
            self.refresh_tree()

        tk.Button(dlg, text="确定", command=save_choice).pack(pady=5)

    def start_ai_analysis(self):
        if not self.image_paths:
            messagebox.showwarning("提示", "请先导入或拖拽立绘图片！")
            return

        v_key = self.ai_settings.get("vision_api_key", "").strip() or self.ai_settings.get("api_key", "").strip()
        v_url = self.ai_settings.get("vision_base_url", "https://api.openai.com/v1").rstrip("/")
        v_model = self.ai_settings.get("vision_model", "gpt-4o")

        if not v_key:
            messagebox.showerror("缺失配置", "请先在“AI 模型/识图设置”中填写识图 Vision API Key！")
            return

        progress_dlg = tk.Toplevel(self)
        progress_dlg.title("识图分析中...")
        progress_dlg.geometry("320x110")
        progress_dlg.attributes("-topmost", True)
        lbl_status = tk.Label(progress_dlg, text="正在准备分析，请稍候...")
        lbl_status.pack(expand=True)

        def worker():
            for idx, img_p in enumerate(self.image_paths):
                lbl_status.config(text=f"识图分析中 ({idx + 1}/{len(self.image_paths)}):\n{os.path.basename(img_p)}")
                emotion = self.analyze_single_image(img_p, v_key, v_url, v_model)
                self.file_emotion_map[img_p] = emotion

            progress_dlg.destroy()
            self.after(0, self.refresh_tree)
            messagebox.showinfo("完成", "识图完成！如有个别偏差，可双击列表行手动微调。")

        threading.Thread(target=worker, daemon=True).start()

    def analyze_single_image(self, img_path, api_key, base_url, model):
        b64_img = encode_image_to_base64(img_path)
        if not b64_img:
            return "stand"

        prompt = f"""分析这张立绘角色的表情、姿态或心理状态。请必须且仅从以下词汇中返回1个最贴切的英文单词：
{', '.join(SUPPORTED_EMOTIONS)}

对应分类指南：
- stand: 普通站姿、静止、默认面无表情
- think: 思考、疑惑、托腮、沉思
- happy: 微笑、大笑、开心、欢快
- talk: 张嘴说话、喊叫、讲解
- sad: 悲伤、沮丧、流泪、委屈
- angry: 生气、发怒、严肃、不满
- surprised: 惊讶、震惊、呆住
- embarrassed: 害羞、脸红、尴尬
- sleepy: 困倦、打瞌睡、打哈欠
- wink: 眨眼、wink、卖萌

请严格仅输出上面列表中的一个英文单词，绝对不要输出任何其他说明文字！"""

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64_img}"}
                        }
                    ]
                }
            ],
            "max_tokens": 15
        }

        try:
            res = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                text = res.json()["choices"][0]["message"]["content"].strip().lower()
                for emo in SUPPORTED_EMOTIONS:
                    if emo in text:
                        return emo
        except Exception as e:
            logger.error(f"识图请求失败: {e}")

        return "stand"

    def save_and_apply(self):
        skin_name = self.entry_name.get().strip()
        if not skin_name:
            messagebox.showwarning("警告", "请输入角色名称！")
            return

        if not self.image_paths:
            messagebox.showwarning("警告", "请至少导入或拖拽一张立绘图片！")
            return

        target_dir = os.path.join(SKINS_DIR, skin_name)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        prompt_text = self.txt_prompt.get("1.0", tk.END).strip()
        with open(os.path.join(target_dir, "prompt.txt"), "w", encoding="utf-8") as f:
            f.write(prompt_text)

        for img_path, emotion in self.file_emotion_map.items():
            ext = os.path.splitext(img_path)[1].lower()
            dest_name = f"{emotion}{ext}"
            dest_path = os.path.join(target_dir, dest_name)
            shutil.copy(img_path, dest_path)

        self.created_skin_name = skin_name
        messagebox.showinfo("成功", f"角色 [{skin_name}] 已成功生成并保存！")
        self.destroy()


class ChatWindow(tk.Toplevel):
    def __init__(self, parent, ai_settings):
        super().__init__(parent)
        self.title("桌宠 AI 对话")
        self.geometry("480x600")
        self.minsize(380, 450)
        self.attributes("-topmost", True)

        self.main_app = parent
        self.ai_settings = ai_settings
        self.history = []

        self.init_ui()

    def init_ui(self):
        self.history_frame = tk.Frame(self)
        self.history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        self.chat_text = tk.Text(
            self.history_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 10),
            bg="#F9F9F9",
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.scrollbar = ttk.Scrollbar(self.history_frame, command=self.chat_text.yview)
        self.chat_text.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.chat_text.tag_config("user", foreground="#0056B3",
                                  font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 10, "bold"))
        self.chat_text.tag_config("assistant", foreground="#2E7D32",
                                  font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 10, "bold"))
        self.chat_text.tag_config("system", foreground="#888888",
                                  font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9, "italic"))
        self.chat_text.tag_config("msg_body", foreground="#333333",
                                  font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 10))

        current_skin = self.ai_settings.get("skin", DEFAULT_SKIN)
        self.append_system_msg(f"当前角色已切换为: [{current_skin}]，专属提示词已自动载入。")

        input_frame = tk.Frame(self)
        input_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        self.input_entry = tk.Entry(input_frame, font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 10))
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 5))
        self.input_entry.focus_set()
        self.input_entry.bind("<Return>", lambda event: self.send_message())

        self.send_btn = tk.Button(
            input_frame,
            text="发送",
            width=8,
            bg="#0078D4",
            fg="white",
            font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9, "bold"),
            relief=tk.FLAT,
            command=self.send_message
        )
        self.send_btn.pack(side=tk.RIGHT)

    def append_system_msg(self, text):
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, f"[系统]: {text}\n", "system")
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def append_user_msg(self, text):
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, f"\n【你】:\n", "user")
        self.chat_text.insert(tk.END, f"{text}\n", "msg_body")
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def append_ai_msg(self, reasoning, content):
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, f"\n【桌宠 AI】:\n", "assistant")

        if reasoning and reasoning.strip():
            fold_frame = tk.Frame(self.chat_text, bg="#EFEFEF", bd=1, relief=tk.SOLID)

            toggle_btn = tk.Button(
                fold_frame,
                text="▶ 思考过程 (点击展开)",
                anchor="w",
                bg="#E0E0E0",
                fg="#555555",
                font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 8),
                relief=tk.FLAT
            )
            toggle_btn.pack(fill=tk.X, padx=2, pady=2)

            think_text = tk.Text(
                fold_frame,
                wrap=tk.WORD,
                height=6,
                font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9),
                bg="#F5F5F5",
                fg="#666666",
                relief=tk.FLAT
            )
            think_text.insert(tk.END, reasoning.strip())
            think_text.config(state=tk.DISABLED)

            def toggle():
                if think_text.winfo_viewable():
                    think_text.pack_forget()
                    toggle_btn.config(text="▶ 思考过程 (点击展开)")
                else:
                    think_text.pack(fill=tk.X, padx=5, pady=(0, 5))
                    toggle_btn.config(text="▼ 思考过程 (点击折叠)")
                self.chat_text.see(tk.END)

            toggle_btn.config(command=toggle)

            self.chat_text.window_create(tk.END, window=fold_frame)
            self.chat_text.insert(tk.END, "\n")

        self.chat_text.insert(tk.END, f"{content.strip()}\n", "msg_body")
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

    def send_message(self):
        user_input = self.input_entry.get().strip()
        if not user_input:
            return

        api_key = self.ai_settings.get("api_key", "").strip()
        if not api_key:
            messagebox.showwarning("配置缺失", "请先在右键菜单的“AI 模型设置”中填写你的 API Key！")
            return

        self.input_entry.delete(0, tk.END)
        self.append_user_msg(user_input)
        self.history.append({"role": "user", "content": user_input})

        self.main_app.set_emotion("think")

        self.send_btn.config(state=tk.DISABLED, text="思考中...")
        threading.Thread(target=self.fetch_ai_reply, daemon=True).start()

    def fetch_ai_reply(self):
        api_key = self.ai_settings.get("api_key")
        base_url = self.ai_settings.get("base_url").rstrip("/")
        model = self.ai_settings.get("model")
        temperature = float(self.ai_settings.get("temperature", 0.7))

        current_skin = self.ai_settings.get("skin", DEFAULT_SKIN)
        system_prompt = get_skin_prompt(current_skin)

        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(self.history)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }

        # 1. 如果当前加载了插件工具，附加到 API 请求中
        plugin_mgr = self.main_app.plugin_manager
        if plugin_mgr.agent_tools:
            payload["tools"] = plugin_mgr.agent_tools
            payload["tool_choice"] = "auto"

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                res_data = response.json()
                choice_msg = res_data["choices"][0]["message"]

                # 2. 检查模型是否触发了 Tool Call (Agent 模式)
                if choice_msg.get("tool_calls"):
                    tool_calls = choice_msg["tool_calls"]
                    messages.append(choice_msg)

                    for tool_call in tool_calls:
                        func_name = tool_call["function"]["name"]
                        args_str = tool_call["function"].get("arguments", "{}")
                        try:
                            args = json.loads(args_str) if args_str else {}
                        except Exception:
                            args = {}

                        tool_result = plugin_mgr.execute_tool(func_name, args)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": tool_result
                        })

                    payload["messages"] = messages
                    payload.pop("tools", None)
                    payload.pop("tool_choice", None)

                    second_res = requests.post(url, headers=headers, json=payload, timeout=60)
                    if second_res.status_code == 200:
                        final_msg = second_res.json()["choices"][0]["message"]
                        reasoning = final_msg.get("reasoning_content", "")
                        raw_content = final_msg.get("content", "")
                        self.after(0, lambda: self.on_success(reasoning, raw_content))
                    else:
                        self.after(0, lambda: self.on_error(f"工具执行后二次响应异常: {second_res.text}"))
                    return

                # 普通文本回复处理
                reasoning = choice_msg.get("reasoning_content", "")
                raw_content = choice_msg.get("content", "")

                if not reasoning and "<think>" in raw_content:
                    match = re.search(r"<think>(.*?)</think>", raw_content, re.DOTALL)
                    if match:
                        reasoning = match.group(1)
                        raw_content = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL)

                self.after(0, lambda: self.on_success(reasoning, raw_content))
            else:
                err_msg = f"API 响应错误 [{response.status_code}]: {response.text}"
                self.after(0, lambda: self.on_error(err_msg))

        except Exception as e:
            self.after(0, lambda: self.on_error(f"网络通信异常: {str(e)}"))

    def on_success(self, reasoning, content):
        clean_text = filter_ai_response(content)
        self.append_ai_msg(reasoning, clean_text)
        self.history.append({"role": "assistant", "content": clean_text})
        self.send_btn.config(state=tk.NORMAL, text="发送")

        self.main_app.set_emotion("happy", auto_reset_ms=4000)
        self.main_app.show_bubble_message(clean_text, duration_ms=6000)

    def on_error(self, error_msg):
        self.append_system_msg(error_msg)
        self.send_btn.config(state=tk.NORMAL, text="发送")
        self.main_app.set_emotion("stand")


class ChangeSkinDialog(tk.Toplevel):
    def __init__(self, parent, current_skin):
        super().__init__(parent)
        self.title("选择角色/皮肤")
        self.geometry("320x380")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self.selected_skin = None
        self.current_skin = current_skin

        tk.Label(self, text="选择喜欢的角色（将自动加载专属提示词）：",
                 font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9, "bold"), wraplength=280).pack(
            anchor="w", padx=15, pady=(15, 5))

        frame = tk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        self.scrollbar = ttk.Scrollbar(frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            frame,
            selectmode=tk.SINGLE,
            font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 10),
            yscrollcommand=self.scrollbar.set
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.listbox.yview)

        self.skins = self.get_available_skins()
        for index, skin in enumerate(self.skins):
            display_name = f"🎭 {skin} (正在使用)" if skin == self.current_skin else f"👤 {skin}"
            self.listbox.insert(tk.END, display_name)
            if skin == self.current_skin:
                self.listbox.select_set(index)

        self.listbox.bind("<Double-Button-1>", lambda event: self.on_confirm())

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=15, pady=15)

        tk.Button(btn_frame, text="应用角色", command=self.on_confirm, width=10, bg="#0078D4", fg="white",
                  relief=tk.FLAT).pack(side=tk.LEFT, padx=(0, 10))
        tk.Button(btn_frame, text="取消", command=self.destroy, width=10).pack(side=tk.RIGHT)

    def get_available_skins(self):
        skins = []
        if os.path.exists(SKINS_DIR):
            skins = [d for d in os.listdir(SKINS_DIR) if os.path.isdir(os.path.join(SKINS_DIR, d))]
        if not skins:
            skins = [DEFAULT_SKIN]
        return skins

    def on_confirm(self):
        selection = self.listbox.curselection()
        if selection:
            idx = selection[0]
            self.selected_skin = self.skins[idx]
            self.destroy()


class ModelSettingsDialog(tk.Toplevel):
    def __init__(self, parent, current_settings):
        super().__init__(parent)
        self.title("AI 模型与项目设置")
        self.geometry("480x450")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.result = None

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 选项卡 1：对话模型
        tab_chat = tk.Frame(notebook)
        notebook.add(tab_chat, text="💬 对话模型 (Chat API)")

        tk.Label(tab_chat, text="API Key:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.entry_key = tk.Entry(tab_chat, width=32, show="*")
        self.entry_key.insert(0, current_settings.get("api_key", ""))
        self.entry_key.grid(row=0, column=1, padx=10, pady=10)

        tk.Label(tab_chat, text="Base URL:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.entry_url = tk.Entry(tab_chat, width=32)
        self.entry_url.insert(0, current_settings.get("base_url", ""))
        self.entry_url.grid(row=1, column=1, padx=10, pady=10)

        tk.Label(tab_chat, text="Model:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.entry_model = tk.Entry(tab_chat, width=32)
        self.entry_model.insert(0, current_settings.get("model", ""))
        self.entry_model.grid(row=2, column=1, padx=10, pady=10)

        tk.Label(tab_chat, text="Temp:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
        self.temp_scale = tk.Scale(tab_chat, from_=0.0, to=1.5, resolution=0.1, orient=tk.HORIZONTAL, length=200)
        self.temp_scale.set(float(current_settings.get("temperature", 0.7)))
        self.temp_scale.grid(row=3, column=1, padx=10, pady=10, sticky="w")

        # 选项卡 2：识图模型
        tab_vision = tk.Frame(notebook)
        notebook.add(tab_vision, text="👁️ 识图模型 (Vision API)")

        tk.Label(tab_vision, text="Vision Key:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.entry_v_key = tk.Entry(tab_vision, width=32, show="*")
        self.entry_v_key.insert(0, current_settings.get("vision_api_key", ""))
        self.entry_v_key.grid(row=0, column=1, padx=10, pady=10)

        tk.Label(tab_vision, text="Base URL:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.entry_v_url = tk.Entry(tab_vision, width=32)
        self.entry_v_url.insert(0, current_settings.get("vision_base_url", "https://api.openai.com/v1"))
        self.entry_v_url.grid(row=1, column=1, padx=10, pady=10)

        tk.Label(tab_vision, text="Vision Model:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.entry_v_model = tk.Entry(tab_vision, width=32)
        self.entry_v_model.insert(0, current_settings.get("vision_model", "gpt-4o"))
        self.entry_v_model.grid(row=2, column=1, padx=10, pady=10)

        # 选项卡 3：关于页面
        tab_about = tk.Frame(notebook)
        notebook.add(tab_about, text="ℹ️ 关于")

        about_frame = tk.LabelFrame(tab_about, text=" 项目信息 ", font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9, "bold"), padx=15, pady=10)
        about_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        info_items = [
            ("👤 开发者:", APP_INFO["developer"]),
            ("👥 开发团队:", APP_INFO["team"]),
            ("🔗 开源项目:", APP_INFO["repo_url"]),
            ("📦 基于源项目:", APP_INFO["base_on"]),
            ("📜 开源协议:", APP_INFO["license"]),
            ("🕒 构建时间:", APP_INFO["build_time"])
        ]

        for idx, (label_text, val_text) in enumerate(info_items):
            tk.Label(about_frame, text=label_text, font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9, "bold"), anchor="w").grid(row=idx, column=0, sticky="w", pady=4)
            entry_val = tk.Entry(about_frame, width=35, font=("DejaVu Sans" if IS_LINUX else "Microsoft YaHei", 9), bd=0, bg=tab_about.cget("bg"))
            entry_val.insert(0, val_text)
            entry_val.config(state="readonly")
            entry_val.grid(row=idx, column=1, sticky="w", padx=5, pady=4)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=(0, 15))
        tk.Button(btn_frame, text="保存配置", command=self.on_save, width=12, bg="#0078D4", fg="white", relief=tk.FLAT).pack(side=tk.LEFT, padx=30)
        tk.Button(btn_frame, text="取消", command=self.destroy, width=10).pack(side=tk.RIGHT, padx=30)

    def on_save(self):
        self.result = {
            "api_key": self.entry_key.get().strip(),
            "base_url": self.entry_url.get().strip(),
            "model": self.entry_model.get().strip(),
            "temperature": round(self.temp_scale.get(), 2),
            "vision_api_key": self.entry_v_key.get().strip(),
            "vision_base_url": self.entry_v_url.get().strip(),
            "vision_model": self.entry_v_model.get().strip()
        }
        self.destroy()


def launch():
    app = TransparentWindow()
    app.mainloop()


if __name__ == "__main__":
    launch()