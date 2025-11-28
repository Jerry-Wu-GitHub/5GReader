"""
AI 配置插件：允许用户配置 AI 模型参数
"""

from dataclasses import dataclass
import os
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, Optional, override
import webbrowser

try:
    from openai import OpenAI
except ImportError:
    messagebox.showerror("错误", "缺少 openai 库，请安装: pip install openai")

from glueous import ReaderAccess
from glueous_plugin import Plugin



def set_windows_env_variable(key, value, scope='user'):
    """
    在 Windows 上设置永久环境变量
    scope: 'user' (用户级) 或 'system' (系统级，需要管理员权限)
    """
    try:
        # 使用 setx 命令
        cmd = ['setx', key, value]
        if scope == 'system':
            cmd.insert(1, '/M')  # 系统级变量需要 /M 参数

        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ 成功设置环境变量: {key} (scope: {scope})")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 设置失败: {e.stderr.decode()}")
        return False



@dataclass
class AIConfiguration:
    """
    大模型调用配置数据类
    """
    url        : str
    api_key    : str
    model      : str
    max_tokens : int
    stream     : bool
    concurrent : bool

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式，方便直接用于API调用
        """
        return {
            "url"        : self.url,
            "api_key"    : self.api_key,
            "model"      : self.model,
            "max_tokens" : self.max_tokens,
            "stream"     : self.stream,
            "concurrent" : self.concurrent,
        }



class AIConfigDialog(tk.Toplevel):
    """
    大模型配置输入对话框。
    """

    MAX_TOKENS_WARNING_THRESHOLD = 128

    HELP_WEBSITE = "https://github.com/Jerry-Wu-GitHub/GlueousReader/blob/main/docs/AIConfigure.md"


    def __init__(self, context: ReaderAccess, parent: tk.Tk, title: str = "AI Config", **kwargs: Dict[str, Any]):
        """
        Params:

        - `parent`: 父组件。
        - `title`: 窗口标题。
        - `kwargs`: 初始文本或选项。
        """

        super().__init__(parent)
        self.context = context
        self.parent = parent
        self.title(title)
        self.geometry("450x480")
        self.resizable(True, False)

        # 初始化变量
        self.url_var        = tk.StringVar(value  = kwargs.get("url"       , ""))
        self.api_key_var    = tk.StringVar(value  = kwargs.get("api_key"   , ""))
        self.model_var      = tk.StringVar(value  = kwargs.get("model"     , ""))
        self.max_tokens_var = tk.StringVar(value  = str(kwargs.get("max_tokens", 0)))
        self.stream_var     = tk.BooleanVar(value = kwargs.get("stream"    , False))
        self.concurrent_var = tk.BooleanVar(value = kwargs.get("concurrent", True))

        self.config_result: Optional[AIConfiguration] = None

        # 创建界面
        self._create_widgets()
        self._layout_widgets()

        # 设置模态对话框
        self.transient(parent)
        self.grab_set()
        self.wait_window(self)


    def _create_widgets(self):
        """
        创建所有界面组件。
        """

        # 主框架
        main_frame = ttk.Frame(self, padding = "20")
        main_frame.pack(fill = tk.BOTH, expand = True)

        # url 输入框
        self.url_label        = ttk.Label(main_frame, text = "url:",        font = ("Arial", 12))
        self.url_entry        = ttk.Entry(main_frame, textvariable = self.url_var,        width = 50, font = ("Arial", 12))

        # api_key 输入框
        self.api_key_label    = ttk.Label(main_frame, text = "api_key:",    font = ("Arial", 12))
        self.api_key_entry    = ttk.Entry(main_frame, textvariable = self.api_key_var,    width = 50, font = ("Arial", 12), show = "*")

        # model 输入框
        self.model_label      = ttk.Label(main_frame, text = "model:",      font = ("Arial", 12))
        self.model_entry      = ttk.Entry(main_frame, textvariable = self.model_var,      width = 50, font = ("Arial", 12))

        # max_tokens 输入框
        self.max_tokens_label = ttk.Label(main_frame, text = "单次最大发出 token 数:", font = ("Arial", 12))
        self.max_tokens_entry = ttk.Entry(main_frame, textvariable = self.max_tokens_var, width = 50, font = ("Arial", 12))

        # stream 单选框
        self.stream_check = tk.Checkbutton(
            main_frame,
            text     = "stream",
            variable = self.stream_var,
            command  = self._on_stream_toggle,
            font     = ("Arial", 12)
        )

        # concurrent 单选框
        self.concurrent_check = tk.Checkbutton(
            main_frame,
            text     = "并发请求",
            variable = self.concurrent_var,
            font     = ("Arial", 12)
        )

        # 按钮框架
        self.button_frame = ttk.Frame(main_frame)
        self.confirm_button = ttk.Button(self.button_frame, text = "确认", command = self._on_confirm,           width = 8)
        self.verify_button  = ttk.Button(self.button_frame, text = "验证", command = self._verify_configuration, width = 8)
        self.cancel_button  = ttk.Button(self.button_frame, text = "取消", command = self._on_cancel,            width = 8)

        # 链接标签（蓝色、下划线）
        self.help_link = tk.Label(
            main_frame,
            text   = "How to configure?",
            fg     = "blue",  # 文字颜色：蓝色
            cursor = "hand2",  # 鼠标悬停时显示“手”形指针
            font   = ("SimHei", 10)
        )
        self.help_link.config(state = "normal")  # 确保标签可交互

        # 绑定点击事件（左键点击触发 self.help 函数）
        self.help_link.bind("<Button-1>", self.show_help_in_browser)


    def _layout_widgets(self):
        """布局所有界面组件"""
        # 使用网格布局
        main_frame = self.url_label.master

        # url 行
        self.url_label       .grid(row =  0, column = 0, sticky = "w",   pady = (0, 5))
        self.url_entry       .grid(row =  1, column = 0, columnspan = 2, sticky = "ew", pady = (0, 15))

        # api_key 行
        self.api_key_label   .grid(row =  2, column = 0, sticky = "w",   pady = (0, 5))
        self.api_key_entry   .grid(row =  3, column = 0, columnspan = 2, sticky = "ew", pady = (0, 15))

        # model 行
        self.model_label     .grid(row =  4, column = 0, sticky = "w",   pady = (0, 5))
        self.model_entry     .grid(row =  5, column = 0, columnspan = 2, sticky = "ew", pady = (0, 15))

        # max_tokens 行
        self.max_tokens_label.grid(row =  6, column = 0, sticky = "w",   pady = (0, 5))
        self.max_tokens_entry.grid(row =  7, column = 0, columnspan = 2, sticky = "ew", pady = (0, 15))

        # stream 行
        self.stream_check    .grid(row =  8, column = 0, columnspan = 2, sticky = "w", pady = (0, 20))

        # concurrent 行
        self.concurrent_check.grid(row =  9, column = 0, columnspan = 2, sticky = "w", pady = (0, 20))

        # 按钮行
        self.button_frame    .grid(row = 10, column = 0, columnspan = 2, pady = (10, 0))
        self.cancel_button .pack(side = "right")
        self.verify_button .pack(side = "right", padx = (0, 10))
        self.confirm_button.pack(side = "right", padx = (0, 10))

        # help_link 行
        self.help_link       .grid(row = 11, column = 0, sticky = "w",   pady = (0, 5))

        # 设置列权重
        main_frame.columnconfigure(1, weight=1)


    def _on_stream_toggle(self):
        """流式传输选项切换时的处理"""
        is_stream = self.stream_var.get()
        if is_stream:
            messagebox.showinfo("提示", "已启用流式传输模式\n注意：部分模型可能不支持此功能")


    def _validate_input(self) -> bool:
        """验证用户输入"""
        if not self.url_var.get().strip():
            messagebox.showerror("错误", "请输入 url")
            self.url_entry.focus()
            return False

        if not self.api_key_var.get().strip():
            messagebox.showerror("错误", "请输入 api_key")
            self.api_key_entry.focus()
            return False

        if not self.model_var.get().strip():
            messagebox.showerror("错误", "请输入 model")
            self.model_entry.focus()
            return False

        try:
            max_tokens = int(self.max_tokens_var.get().strip())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的 max tokens")
            self.max_tokens_entry.focus()
            return False

        if max_tokens <= 0:
            messagebox.showerror("错误", "max tokens 应该是一个正整数")
            self.max_tokens_entry.focus()
            return False

        if max_tokens < self.MAX_TOKENS_WARNING_THRESHOLD:
            messagebox.showwarning("警告", "max tokens 过小，可能会导致部分功能无法正常执行")

        return True


    def _verify_configuration(self) -> bool:
        """
        验证 AI 配置是否有效。
        """
        config = self.get_config_result().to_dict()

        try:
            # 检查必填字段
            if not self._validate_input():
                return False

            client = OpenAI(
                base_url   = config["url"],
                api_key    = config["api_key"],
            )

            # 发送一个简单的测试请求
            response = client.chat.completions.create(
                model      = config["model"],
                messages   = [{"role": "user", "content": "Hello, who are you?"}],
                max_tokens = 10,  # 限制token数量以减少消耗
                stream     = False
            )

            # 检查响应是否有效
            if not response.choices or not response.choices[0].message.content:
                messagebox.showerror("错误", "API 响应无效")
                return False

            messagebox.showinfo("成功", "AI 配置验证通过")
            return True

        except Exception as e:
            messagebox.showerror("错误", f"配置验证失败: {str(e)}")
            return False


    def get_config_result(self) -> AIConfiguration:
        return AIConfiguration(
            url        = self.url_var       .get().strip(),
            api_key    = self.api_key_var   .get().strip(),
            model      = self.model_var     .get().strip(),
            max_tokens = int(self.max_tokens_var.get().strip()),
            stream     = self.stream_var    .get(),
            concurrent = self.concurrent_var.get(),
        )


    def _on_confirm(self):
        """确认按钮点击事件"""
        if self._validate_input():
            self.config_result = self.get_config_result()
            self.destroy()


    def show_help_in_browser(self, event = None) -> None:
        """点击帮助链接时打开帮助网页"""
        webbrowser.open(self.HELP_WEBSITE)


    def _on_cancel(self):
        """取消按钮点击事件"""
        self.destroy()



def ask_AI_configuration(context: ReaderAccess, parent: Optional[tk.Tk] = None, **kwargs) -> Optional[AIConfiguration]:
    """
    弹出大模型配置对话框并返回配置
    
    Args:
        parent: 父窗口
        
    Returns:
        包含用户输入配置的LLMConfig对象，用户取消时返回None
    """
    if parent is None:
        parent = tk.Tk()
        parent.withdraw()  # 隐藏主窗口

    dialog = AIConfigDialog(context, parent, **kwargs)
    return dialog.config_result



class AIConfigurePlugin(Plugin):
    """
    AI 配置插件：允许用户设置大语言模型的参数
    """

    name = "AIConfigurePlugin"
    description = """
# AIConfigurePlugin

- name: AIConfigurePlugin
- author: Jerry
- hotkeys: None
- menu entrance: `工具 → AI配置`

## Function

Allow users to configure parameters for calling large language models, such as `url`, `model`, `api_key`, etc.

The configuration information will be saved in `ReaderAccess.data` and can be restored after program restart.

Specifically, to protect privacy, the api_key field will be stored in the environment variable.

## Api

- `context.get_AI_configuration()`: Obtain the user's AI configuration parameters.

## Depend

Python extension library: None

Other plugins: None

## Others

The configuration parameters are saved in JSON format in config/data.json.

The `api_key` field is saved in the environment variable.
"""

    hotkeys = []

    # 默认配置
    DEFAULT_CONFIGURATION: Dict[str, Any] = {
        "url"        : ""    ,
        "api_key"    : ""    ,
        "model"      : ""    ,
        "max_tokens" : 8192  ,
        "stream"     : True  ,
        "concurrent" : True  ,
    }

    # 存在 ReaderAccess.data 中的键名
    _DATA_CONFIG_KEY         : str = "ai_configuration"

    _ENVIRONMENT_API_KEY_KEY : str = "GLUEOUS_READER_AI_API_KEY"


    def get_AI_configuration(self) -> Dict[str, Any]:
        """
        获取用户的AI配置参数

        Returns:
            Dict[str, Any]: AI配置参数，例如：
            {
                "url"       : "https://api-inference.modelscope.cn/v1/chat/completions",
                "api_key"   : "12345678",
                "model"     : "Qwen/Qwen3-Coder-30B-A3B-Instruct",
                "max_tokens": 8192,
                "stream"    : True,
                "concurrent": True
            }
        """
        # 从数据中获取配置，如果没有则返回默认配置
        configuration = self.context.data.get(self._DATA_CONFIG_KEY, self.DEFAULT_CONFIGURATION).copy()

        # 从环境变量中读入 api_key，并加入 configuration 中
        api_key_from_env = os.environ.get(self._ENVIRONMENT_API_KEY_KEY, "")
        configuration["api_key"] = api_key_from_env

        return configuration


    @override
    def loaded(self) -> None:
        """
        插件加载时：注册菜单项，从数据文件恢复配置
        """
        # 注册菜单项
        self.context.add_menu_command(
            path    = ["工具"],
            label   = "AI配置",
            command = self.run
        )

        # 提供获取配置的方法
        self.context.get_AI_configuration = self.get_AI_configuration


    @override
    def run(self) -> None:
        try:
            # 获取当前配置
            current_configuration = self.get_AI_configuration()

            # 创建配置对话框
            new_configuration: AIConfiguration = ask_AI_configuration(
                context = self.context,
                parent = self.context._reader.root,
                **current_configuration
            )

            if new_configuration:
                # 保存配置
                self._save_configuration(new_configuration.to_dict())
                self.context.print("AI配置已保存")

        except Exception as e:
            messagebox.showerror("错误", f"配置失败: {str(e)}")


    def _save_configuration(self, config: Dict[str, Any]) -> None:
        """
        url、model、stream、max_tokens、concurrent 保存到 ReaderAccess.data ，api_key 永久保存到环境变量，保证下次重启程序仍能访问

        Args:
            config: 要保存的配置字典
        """
        # url、model、stream 保存到 ReaderAccess.data
        self.context.data[self._DATA_CONFIG_KEY] = {
            "url"        : config["url"],
            "model"      : config["model"],
            "max_tokens" : config["max_tokens"],
            "stream"     : config["stream"],
            "concurrent" : config["concurrent"],
        }

        # 将 api_key 永久保存到环境变量中
        set_windows_env_variable(self._ENVIRONMENT_API_KEY_KEY, config["api_key"], "user")
        os.environ[self._ENVIRONMENT_API_KEY_KEY] = config["api_key"]


    @override
    def unloaded(self) -> None:
        pass
