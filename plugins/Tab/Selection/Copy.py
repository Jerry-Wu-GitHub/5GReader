"""
复制选中文本插件：实现复制 PDF 中选中的文本到剪贴板
"""

from tkinter import messagebox
import tkinter as tk

import pyperclip

from glueous_plugin import Plugin


class CopyPlugin(Plugin):
    """
    复制插件：实现复制 PDF 中选中的文本到剪贴板
    """

    name = "CopyPlugin"
    description = """
# CopyPlugin

- name: CopyPlugin
- author: Jerry
- hotkeys: `Ctrl+C`
- menu entrance: `选择 → 复制到剪贴板`

## Function

Copy the selected text from the PDF to the system clipboard.

If no text is selected, nothing will be done.

## Api

None

## Depend

Python extension library:
- pyperclip

Other plugins:
- TabPlugin
- SelectPlugin or DragPlugin
- ContextMenu

## Others

None
"""

    hotkeys = ["<Control-c>"]


    def loaded(self) -> None:
        """
        插件加载时：注册菜单项和快捷键
        """
        # 添加到顶部菜单栏
        self.context.add_menu_command(
            path = ["选择"],
            label = "复制到剪贴板",
            command = self.run,
            accelerator = "Ctrl+C"
        )

        # 添加到上下文菜单
        self.context.context_menu_manager.add_context_menu_command(
            context = self.context.Tab.CANVAS_CONTEXT_NAME,
            path = [],
            label = "复制",
            command = self.run
        )


    def run(self) -> None:
        """
        执行复制操作。

        如果没有选中文本，则什么都不做。
        """
        try:
            # 获取选中的文本
            selected_text = self.context.get_selected_text()

            if not selected_text:
                self.context.print("没有被选中的文本")
                return

            # 复制到剪贴板
            pyperclip.copy(selected_text)

            self.context.print("复制成功")

        except Exception as e:
            messagebox.showerror("错误", f"复制失败: {str(e)}")


    def unloaded(self) -> None:
        """
        插件卸载时清理
        """
        pass
