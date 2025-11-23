"""
AI 总结插件：使用大语言模型生成文档或选中区域的总结
"""

import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext, filedialog
from typing import Any, Dict, Optional, override
import threading

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import tiktoken
except ImportError:
    tiktoken = None

from glueous_plugin import Plugin


def count_tokens(text: str) -> int:
    """
    计算文本的 token 数量。
    """
    if tiktoken is None:
        # 如果无法导入 tiktoken，使用字符数估算（中文约1.5字符=1token，英文约4字符=1token）
        # 这里使用保守估计：3字符=1token
        return len(text) // 3
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # 如果无法计算，返回字符数作为估计
        return len(text) // 3


class SummaryResultDialog(tk.Toplevel):
    """
    总结结果显示对话框，支持复制和保存
    """

    def __init__(self, parent: tk.Tk, summary_text: str, title: str = "AI 总结"):
        super().__init__(parent)
        self.parent = parent
        self.title(title)
        self.geometry("600x400")
        self.summary_text = summary_text

        # 创建界面
        self._create_widgets()
        self._layout_widgets()

        # 设置模态对话框
        self.transient(parent)
        self.grab_set()

    def _create_widgets(self):
        """创建界面组件"""
        # 主框架
        self.main_frame = ttk.Frame(self, padding="10")

        # 文本显示区域
        self.text_label = ttk.Label(self.main_frame, text="总结内容：", font=("Arial", 10))
        self.text_area = scrolledtext.ScrolledText(
            self.main_frame,
            wrap=tk.WORD,
            width=70,
            height=15,
            font=("Arial", 10)
        )
        self.text_area.insert("1.0", self.summary_text)
        self.text_area.config(state=tk.NORMAL)  # 允许编辑（用于复制）

        # 按钮框架
        self.button_frame = ttk.Frame(self.main_frame)
        self.copy_button = ttk.Button(self.button_frame, text="复制", command=self._on_copy, width=12)
        self.save_button = ttk.Button(self.button_frame, text="保存", command=self._on_save, width=12)
        self.close_button = ttk.Button(self.button_frame, text="关闭", command=self.destroy, width=12)

    def _layout_widgets(self):
        """布局界面组件"""
        # 主框架
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 标签
        self.text_label.pack(anchor="w", pady=(0, 5))

        # 文本区域
        self.text_area.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 按钮
        self.button_frame.pack(fill=tk.X)
        self.close_button.pack(side=tk.RIGHT, padx=(5, 0))
        self.save_button.pack(side=tk.RIGHT, padx=(5, 0))
        self.copy_button.pack(side=tk.RIGHT, padx=(5, 0))

    def _on_copy(self):
        """复制文本到剪贴板"""
        try:
            text = self.text_area.get("1.0", tk.END).strip()
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
                messagebox.showinfo("成功", "已复制到剪贴板")
            else:
                messagebox.showwarning("提示", "没有可复制的内容")
        except Exception as e:
            messagebox.showerror("错误", f"复制失败: {str(e)}")

    def _on_save(self):
        """保存文本到文件"""
        try:
            text = self.text_area.get("1.0", tk.END).strip()
            if not text:
                messagebox.showwarning("提示", "没有可保存的内容")
                return

            file_path = filedialog.asksaveasfilename(
                title="保存总结",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )

            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                messagebox.showinfo("成功", f"已保存到: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")


class SummaryLengthDialog(tk.Toplevel):
    """
    总结长度配置对话框
    """

    # 预设的长度选项
    LENGTH_OPTIONS = [
        ("简短", "short"),
        ("中等", "medium"),
        ("详细", "detailed"),
    ]

    def __init__(self, parent: tk.Tk, current_length: str = "medium"):
        super().__init__(parent)
        self.parent = parent
        self.title("配置总结长度")
        self.geometry("300x200")
        self.result: Optional[str] = None

        # 当前选择
        self.length_var = tk.StringVar(value=current_length)

        # 创建界面
        self._create_widgets()
        self._layout_widgets()

        # 设置模态对话框
        self.transient(parent)
        self.grab_set()
        self.wait_window(self)

    def _create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 说明标签
        label = ttk.Label(main_frame, text="选择总结长度：", font=("Arial", 10))

        # 单选按钮
        self.radio_frame = ttk.Frame(main_frame)
        for label_text, value in self.LENGTH_OPTIONS:
            radio = ttk.Radiobutton(
                self.radio_frame,
                text=label_text,
                variable=self.length_var,
                value=value
            )
            radio.pack(anchor="w", pady=5)

        # 按钮
        button_frame = ttk.Frame(main_frame)
        self.confirm_button = ttk.Button(button_frame, text="确认", command=self._on_confirm, width=10)
        self.cancel_button = ttk.Button(button_frame, text="取消", command=self._on_cancel, width=10)

        self.label = label
        self.button_frame = button_frame

    def _layout_widgets(self):
        """布局界面组件"""
        main_frame = self.label.master

        self.label.pack(anchor="w", pady=(0, 10))
        self.radio_frame.pack(fill=tk.X, pady=(0, 20))
        self.button_frame.pack(fill=tk.X)
        self.confirm_button.pack(side=tk.RIGHT, padx=(5, 0))
        self.cancel_button.pack(side=tk.RIGHT)

    def _on_confirm(self):
        """确认按钮"""
        self.result = self.length_var.get()
        self.destroy()

    def _on_cancel(self):
        """取消按钮"""
        self.result = None
        self.destroy()


class SummaryPlugin(Plugin):
    """
    AI 总结插件：使用大语言模型生成文档或选中区域的总结
    """

    name = "SummaryPlugin"
    description = """
# SummaryPlugin

- name: SummaryPlugin
- author: Glueous Reader
- hotkeys: None
- menu entrance: `工具 → AI总结`, `工具 → 配置总结长度`

## Function

When the user selects "AI总结" from the menu bar, call the large language model API to generate a summary of the selected area or the entire document.

- If text is selected, generate a summary of the selected area.
- If no text is selected, generate a summary of the entire document.

Display the AI-generated summary in a popup window, where users can copy, save, etc.

Users can configure the summary length in the menu bar.

## Api

None

## Depend

Python extension library:
- openai

Other plugins:
- TabPlugin
- AIConfigurePlugin
- SelectPlugin or DragPlugin (for get_selected_text)

## Others

The summary length configuration is saved in ReaderAccess.data.
"""

    hotkeys = []

    # 总结长度提示词映射
    LENGTH_PROMPTS = {
        "short": "请用简短的语言（50-100字）总结以下内容：",
        "medium": "请用中等长度的语言（200-300字）总结以下内容：",
        "detailed": "请用详细的语言（500-800字）总结以下内容：",
    }

    # 默认总结长度
    DEFAULT_LENGTH = "medium"

    # 存储在 ReaderAccess.data 中的键名
    _DATA_LENGTH_KEY: str = "summary_length"

    def __init__(self, context):
        super().__init__(context)
        if OpenAI is None:
            print("警告：未安装 openai 库，请运行：pip install openai")
            self.disable()

    def get_summary_length(self) -> str:
        """
        获取用户配置的总结长度

        Returns:
            str: 总结长度，"short", "medium", 或 "detailed"
        """
        return self.context.data.get(self._DATA_LENGTH_KEY, self.DEFAULT_LENGTH)

    def set_summary_length(self, length: str) -> None:
        """
        设置总结长度

        Args:
            length: 总结长度，"short", "medium", 或 "detailed"
        """
        if length in self.LENGTH_PROMPTS:
            self.context.data[self._DATA_LENGTH_KEY] = length

    def get_text_to_summarize(self) -> str:
        """
        获取需要总结的文本

        Returns:
            str: 选中文本或当前页面的文本（限制范围以避免token过多）
        """
        # 尝试获取选中文本
        try:
            selected_text = self.context.get_selected_text()
            if selected_text and selected_text.strip():
                text = selected_text.strip()
                print(f"[调试] 使用选中文本，长度: {len(text)} 字符, token数: {count_tokens(text)}")
                return text
        except Exception as e:
            print(f"获取选中文本失败: {e}")

        # 如果没有选中文本，只获取当前页面的文本（而不是整个文档）
        current_tab = self.context.get_current_tab()
        if current_tab is None or current_tab.doc is None:
            return ""

        # 只获取当前页面的文本
        try:
            if hasattr(current_tab, 'page') and current_tab.page is not None:
                page_text = current_tab.page.get_text()
                if page_text and page_text.strip():
                    text = page_text.strip()
                    print(f"[调试] 使用当前页文本，长度: {len(text)} 字符, token数: {count_tokens(text)}")
                    return text
        except Exception as e:
            print(f"获取当前页文本失败: {e}")

        # 如果当前页也没有文本，尝试获取前3页（作为备选方案）
        all_text = []
        max_pages = min(3, len(current_tab.doc))  # 最多提取3页
        for i in range(max_pages):
            try:
                page = current_tab.doc[i]
                page_text = page.get_text()
                if page_text and page_text.strip():
                    all_text.append(page_text.strip())
            except Exception as e:
                print(f"获取第 {i + 1} 页文本失败: {e}")

        if all_text:
            text = "\n\n".join(all_text)
            print(f"[调试] 使用前{len(all_text)}页文本，长度: {len(text)} 字符, token数: {count_tokens(text)}")
            return text

        return ""

    def call_ai_api(self, text: str, length: str) -> str:
        """
        调用 AI API 生成总结

        Args:
            text: 要总结的文本
            length: 总结长度

        Returns:
            str: AI 生成的总结
        """
        # 获取 AI 配置
        config = self.context.get_AI_configuration()

        if not config.get("url") or not config.get("api_key") or not config.get("model"):
            raise ValueError("AI 配置不完整，请先在'工具 → AI配置'中配置")

        # 检查文本是否为空
        if not text or not text.strip():
            raise ValueError("要总结的文本为空，请先选择文本或打开包含文本的文档")

        # 构建提示词
        prompt = self.LENGTH_PROMPTS.get(length, self.LENGTH_PROMPTS["medium"])
        
        # 计算token数并检查限制
        # API限制通常是整个请求的token数，包括prompt和文本
        # 根据错误信息，最大是129024，但为了安全，我们留一些余量
        MAX_INPUT_TOKENS = 129000  # 留24个token的余量
        MIN_INPUT_TOKENS = 1
        
        prompt_tokens = count_tokens(prompt)
        text_tokens = count_tokens(text)
        total_tokens = prompt_tokens + text_tokens
        
        print(f"[调试] Prompt tokens: {prompt_tokens}, 文本 tokens: {text_tokens}, 总计: {total_tokens}")
        print(f"[调试] 文本长度: {len(text)} 字符")
        
        # 检查token数是否在有效范围内
        if total_tokens < MIN_INPUT_TOKENS:
            raise ValueError(f"输入文本过短（{text_tokens} tokens），无法生成总结。请选择更多文本。")
        
        # 初始化要使用的文本
        text_to_use = text
        
        # 检查是否超过限制
        if total_tokens > MAX_INPUT_TOKENS:
            print(f"[调试] 文本超过限制，开始截断...")
            # 需要截断文本
            available_tokens = MAX_INPUT_TOKENS - prompt_tokens - 100  # 再留100个token的余量
            if available_tokens < MIN_INPUT_TOKENS:
                raise ValueError(f"提示词过长（{prompt_tokens} tokens），无法添加文本内容。请选择更短的文本。")
            
            print(f"[调试] 可用 tokens: {available_tokens}")
            
            # 截断文本：使用二分查找找到合适的截断位置
            if text_tokens > available_tokens:
                # 先尝试截断到估算的长度
                # 计算字符/token比例
                chars_per_token = len(text) / text_tokens if text_tokens > 0 else 3
                estimated_chars = int(available_tokens * chars_per_token * 0.9)  # 留10%余量
                
                print(f"[调试] 估算字符/token比例: {chars_per_token:.2f}, 估算截断长度: {estimated_chars} 字符")
                
                if estimated_chars < len(text):
                    # 使用二分查找找到合适的截断位置
                    left, right = 0, min(estimated_chars * 2, len(text))  # 搜索范围
                    best_text = text[:left]
                    
                    # 二分查找
                    while left < right:
                        mid = (left + right) // 2
                        test_text = text[:mid]
                        test_tokens = count_tokens(test_text)
                        
                        if test_tokens <= available_tokens:
                            best_text = test_text
                            left = mid + 1
                        else:
                            right = mid
                    
                    text_to_use = best_text
                    final_text_tokens = count_tokens(text_to_use)
                    print(f"[调试] 截断完成。原始: {text_tokens} tokens ({len(text)} 字符), 截断后: {final_text_tokens} tokens ({len(text_to_use)} 字符)")
                    
                    # 如果截断后还是超过限制，使用更激进的方法
                    if final_text_tokens > available_tokens:
                        # 直接截断到更小的长度
                        aggressive_chars = int(available_tokens * chars_per_token * 0.7)
                        text_to_use = text[:aggressive_chars]
                        # 继续减少直到符合要求
                        max_iterations = 100  # 防止无限循环
                        iteration = 0
                        while count_tokens(text_to_use) > available_tokens and len(text_to_use) > 0 and iteration < max_iterations:
                            text_to_use = text_to_use[:-max(100, len(text_to_use) // 10)]  # 每次减少至少100字符或10%
                            iteration += 1
                        print(f"[调试] 激进截断后: {count_tokens(text_to_use)} tokens ({len(text_to_use)} 字符)")
        
        # 再次检查截断后的总token数
        final_text_tokens = count_tokens(text_to_use)
        final_total_tokens = prompt_tokens + final_text_tokens
        print(f"[调试] 最终: 文本 {final_text_tokens} tokens, 总计 {final_total_tokens} tokens")
        
        if final_total_tokens > MAX_INPUT_TOKENS:
            raise ValueError(
                f"即使截断后，总token数（{final_total_tokens}）仍超过限制（{MAX_INPUT_TOKENS}）。\n"
                f"提示词: {prompt_tokens} tokens, 文本: {final_text_tokens} tokens。\n"
                f"这可能是因为PDF文件提取的文本有问题。建议：\n"
                f"1. 只选择部分文本进行总结\n"
                f"2. 检查PDF文件是否有异常内容"
            )
        if final_total_tokens < MIN_INPUT_TOKENS:
            raise ValueError(f"截断后文本过短（{final_text_tokens} tokens），无法生成总结。")
        
        full_prompt = f"{prompt}\n\n{text_to_use}"

        # 创建 OpenAI 客户端
        client = OpenAI(
            api_key=config["api_key"],
            base_url=config["url"]
        )

        # 调用 API
        try:
            response = client.chat.completions.create(
                model=config["model"],
                messages=[
                    {"role": "user", "content": full_prompt}
                ],
                stream=config.get("stream", False)
            )

            # 处理响应
            if config.get("stream", False):
                # 流式响应
                summary = ""
                chunk_count = 0
                last_chunk = None
                finish_reason = None
                
                for chunk in response:
                    chunk_count += 1
                    last_chunk = chunk
                    try:
                        if (chunk.choices and 
                            len(chunk.choices) > 0 and 
                            chunk.choices[0].delta):
                            # 检查是否有 content
                            if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                                summary += chunk.choices[0].delta.content
                            # 检查 finish_reason
                            if hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason:
                                finish_reason = chunk.choices[0].finish_reason
                    except Exception as e:
                        print(f"处理流式响应 chunk 时出错: {e}")
                        continue
                
                # 如果没有任何内容，提供更详细的错误信息
                if not summary:
                    if chunk_count == 0:
                        raise ValueError("API 没有返回任何数据流，请检查网络连接和 API 配置")
                    else:
                        error_msg = f"API 返回了 {chunk_count} 个数据块，但内容为空"
                        if finish_reason:
                            error_msg += f"。完成原因: {finish_reason}"
                        error_msg += "。可能是文本过长、API 配置问题或模型不支持流式响应。建议：1) 关闭流式响应重试；2) 检查文本是否过长；3) 检查 API 配置。"
                        raise ValueError(error_msg)
                return summary
            else:
                # 非流式响应
                if not response.choices or len(response.choices) == 0:
                    raise ValueError("API 返回的响应中没有 choices")
                if not response.choices[0].message:
                    raise ValueError("API 返回的响应中 message 为空")
                if not response.choices[0].message.content:
                    raise ValueError("API 返回的响应中 content 为空")
                return response.choices[0].message.content

        except Exception as e:
            raise Exception(f"调用 AI API 失败: {str(e)}")

    def generate_summary(self) -> None:
        """
        生成总结的主方法
        """
        # 检查是否有文档打开
        current_tab = self.context.get_current_tab()
        if current_tab is None:
            messagebox.showwarning("提示", "请先打开一个文档")
            return

        # 获取要总结的文本
        try:
            text = self.get_text_to_summarize()
            if not text or not text.strip():
                messagebox.showwarning("提示", "没有可总结的内容")
                return
        except Exception as e:
            messagebox.showerror("错误", f"获取文本失败: {str(e)}")
            return

        # 获取总结长度
        length = self.get_summary_length()

        # 显示进度提示
        progress_window = tk.Toplevel(self.context._reader.root)
        progress_window.title("生成总结中...")
        progress_window.geometry("300x100")
        progress_window.transient(self.context._reader.root)
        progress_window.grab_set()  # 设置为模态窗口
        progress_label = ttk.Label(progress_window, text="正在调用 AI 生成总结，请稍候...")
        progress_label.pack(pady=20)
        progress_window.update()

        # 在新线程中调用 AI API（避免阻塞 UI）
        summary_result = [None]
        error_result = [None]
        finished = [False]

        def on_complete():
            """在主线程中处理结果"""
            progress_window.destroy()
            if error_result[0]:
                messagebox.showerror("错误", error_result[0])
            elif summary_result[0] is None:
                messagebox.showerror("错误", "生成总结失败")
            else:
                # 显示结果
                SummaryResultDialog(self.context._reader.root, summary_result[0], "AI 总结")

        def call_api():
            """在子线程中调用 API"""
            try:
                summary = self.call_ai_api(text, length)
                summary_result[0] = summary
            except Exception as e:
                error_result[0] = str(e)
            finally:
                finished[0] = True
                # 在主线程中执行回调
                self.context._reader.root.after(0, on_complete)

        thread = threading.Thread(target=call_api, daemon=True)
        thread.start()

        # 设置超时检查
        def timeout_check():
            if not finished[0]:
                finished[0] = True
                error_result[0] = "生成总结超时（超过60秒）"
                self.context._reader.root.after(0, on_complete)

        self.context._reader.root.after(60000, timeout_check)  # 60秒超时

    def configure_length(self) -> None:
        """
        配置总结长度
        """
        current_length = self.get_summary_length()
        dialog = SummaryLengthDialog(self.context._reader.root, current_length)

        if dialog.result:
            self.set_summary_length(dialog.result)
            # 创建长度选项的字典映射
            length_dict = {value: label for label, value in SummaryLengthDialog.LENGTH_OPTIONS}
            length_name = length_dict.get(dialog.result, dialog.result)
            messagebox.showinfo("成功", f"总结长度已设置为: {length_name}")

    @override
    def loaded(self) -> None:
        """
        插件加载时：注册菜单项
        """
        # 注册菜单项
        self.context.add_menu_command(
            path=["工具"],
            label="AI总结",
            command=self.generate_summary
        )

        self.context.add_menu_command(
            path=["工具"],
            label="配置总结长度",
            command=self.configure_length
        )

    @override
    def run(self) -> None:
        """插件执行方法"""
        self.generate_summary()

    @override
    def unloaded(self) -> None:
        """插件卸载时执行（无需清理）"""
        pass

