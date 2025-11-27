"""
OCR 调试插件：用于在没有 DragPlugin 时测试 OCR 功能
"""
from __future__ import annotations

from tkinter import messagebox
from typing import override

from glueous_plugin import Plugin


class OCRDebugPlugin(Plugin):
    """
    OCR 调试插件：显示当前页面的 OCR 识别结果，用于测试。
    """

    name = "OCRDebugPlugin"
    
    description = """
# OCRDebugPlugin

- name: OCRDebugPlugin
- author: Glueous Reader
- hotkeys: `Ctrl+Shift+D`
- menu entrance: `工具 → OCR → 显示当前页OCR结果`

## Function

用于调试 OCR 功能：
- 显示当前页面的 OCR 识别结果
- 在画布上绘制识别到的文本框
- 显示识别文本和置信度

## Api

None

## Depend

Python extension library: None

Other plugins:
- TabPlugin
- OCRPlugin

## Others

这是一个临时调试工具，在 DragPlugin 完成后可以移除。
"""

    hotkeys = ["<Control-Shift-D>"]

    def __init__(self, context):
        super().__init__(context)


    def show_ocr_results(self) -> None:
        """
        显示当前页面的 OCR 识别结果。
        """
        current_tab = self.context.get_current_tab()
        if not current_tab or not current_tab.doc:
            messagebox.showwarning("提示", "请先打开一个文档")
            return
        
        # 获取 OCR 插件
        ocr_plugin = None
        for plugin in self.context._reader.plugin_manager.plugins:
            if plugin.name == "OCRPlugin":
                ocr_plugin = plugin
                break
        
        if not ocr_plugin:
            messagebox.showerror("错误", "未找到 OCRPlugin")
            return
        
        file_path = current_tab.file_path
        page_no = current_tab.page_no
        
        # 获取 OCR 结果
        ocr_results = ocr_plugin.get_cached_ocr_result(file_path, page_no)
        
        if ocr_results is None:
            # 触发识别
            messagebox.showinfo("提示", "该页面尚未识别，开始识别...")
            ocr_results = ocr_plugin.perform_ocr_on_page(file_path, page_no)
        
        if not ocr_results:
            messagebox.showinfo("结果", f"第 {page_no + 1} 页没有识别到文本")
            return
        
        # 在画布上绘制识别框
        self.draw_ocr_boxes(current_tab, ocr_results)
        
        # 显示文本信息
        text_summary = f"第 {page_no + 1} 页 OCR 结果：\n\n"
        text_summary += f"共识别到 {len(ocr_results)} 个文本块\n\n"
        
        for i, result in enumerate(ocr_results[:10]):  # 只显示前10个
            confidence = result.get("confidence", 0)
            text = result["text"]
            text_summary += f"{i+1}. [{confidence:.2f}] {text}\n"
        
        if len(ocr_results) > 10:
            text_summary += f"\n... 还有 {len(ocr_results) - 10} 个文本块"
        
        messagebox.showinfo("OCR 结果", text_summary)


    def draw_ocr_boxes(self, tab, ocr_results) -> None:
        """
        在画布上绘制 OCR 识别框。
        """
        import tkinter as tk
        
        # 清除之前的调试框
        tab.canvas.delete("ocr_debug")
        
        for result in ocr_results:
            bbox = result["bbox"]  # [x0, y0, x1, y1] in page coordinates
            confidence = result.get("confidence", 0)
            
            # 转换为画布坐标（考虑缩放）
            x0 = bbox[0] * tab.zoom
            y0 = bbox[1] * tab.zoom
            x1 = bbox[2] * tab.zoom
            y1 = bbox[3] * tab.zoom
            
            # 根据置信度选择颜色
            if confidence > 0.8:
                color = "green"
            elif confidence > 0.5:
                color = "orange"
            else:
                color = "red"
            
            # 绘制矩形框
            tab.canvas.create_rectangle(
                x0, y0, x1, y1,
                outline=color,
                width=2,
                tags="ocr_debug"
            )
            
            # 绘制文本
            tab.canvas.create_text(
                x0, y0 - 5,
                text=result["text"][:20],  # 只显示前20个字符
                anchor=tk.SW,
                fill=color,
                tags="ocr_debug",
                font=("Arial", 8)
            )


    def clear_ocr_boxes(self) -> None:
        """
        清除画布上的 OCR 调试框。
        """
        current_tab = self.context.get_current_tab()
        if current_tab:
            current_tab.canvas.delete("ocr_debug")
            messagebox.showinfo("完成", "已清除调试框")


    def test_get_text(self) -> None:
        """
        测试重载后的 get_text 方法。
        """
        current_tab = self.context.get_current_tab()
        if not current_tab or not current_tab.doc:
            messagebox.showwarning("提示", "请先打开一个文档")
            return
        
        page = current_tab.page
        
        # 获取文本
        text = page.get_text()
        
        # 显示前500个字符
        preview = text[:500] + ("..." if len(text) > 500 else "")
        
        messagebox.showinfo(
            "get_text() 测试",
            f"文本长度: {len(text)} 字符\n\n预览:\n{preview}"
        )


    @override
    def loaded(self) -> None:
        """
        插件加载时执行：注册调试菜单项。
        """
        self.context.add_menu_command(
            path=["工具", "OCR"],
            label="显示当前页OCR结果",
            command=self.show_ocr_results,
            accelerator="Ctrl+Shift+D"
        )
        
        self.context.add_menu_command(
            path=["工具", "OCR"],
            label="清除调试框",
            command=self.clear_ocr_boxes
        )
        
        self.context.add_menu_command(
            path=["工具", "OCR"],
            label="测试 get_text()",
            command=self.test_get_text
        )


    @override
    def run(self) -> None:
        """
        快捷键触发时执行。
        """
        self.show_ocr_results()


    @override
    def unloaded(self) -> None:
        """
        插件卸载时执行。
        """
        # 清除调试框
        self.clear_ocr_boxes()
