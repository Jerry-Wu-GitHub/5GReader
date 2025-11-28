"""
鼠标拖动：划词或拖动页面
"""

from typing import override
from types import MethodType
import tkinter as tk
from tkinter import messagebox

import fitz

from glueous import ReaderAccess
from glueous_plugin import Plugin


class DragPlugin(Plugin):
    """
    绑定鼠标拖动事件。
    判断拖动起点是否落在文字上：
    - 若是，视为划词
    - 否则，视为拖动页面
    """

    name = "DragPlugin"
    description = """
# DragPlugin

- name: DragPlugin
- author: Little Liu
- hotkeys: `鼠标拖动`
- menu entrance: None

## Function

绑定鼠标拖动事件到当前活跃 canvas。
判断拖动起点是否落在文字上：
- 若是，视为划词，绘制选择区域
- 否则，视为拖动页面

当接近窗口边缘时，还要滚动。

## Api

- `context.get_selected_text(format=None, **kwargs)` - 获得选中区域内的文字

## Depend

Python extension library:
- fitz (PyMuPDF)

Other plugins:
- TabPlugin
"""

    hotkeys = []

    def __init__(self, context):
        super().__init__(context)
        self.drag_enabled = True  # 默认开启拖拽

    @staticmethod
    def get_selected_text(access: ReaderAccess, format=None, **kwargs) -> str:
        """
        获取选中区域的文字
        """
        current_tab = access.get_current_tab()
        # 优先使用统一的 selection 对象
        if current_tab and hasattr(current_tab, 'selection') and current_tab.selection:
            sel = current_tab.selection
            page = sel.get("page")
            rect = sel.get("rect")
            if page and rect:
                if format is None:
                    format = "text"
                return page.get_text(format, clip=rect, **kwargs)

        # 兼容旧逻辑
        if current_tab is None or not hasattr(current_tab, '_drag_selection_rect'):
            return ""

        selection_rect = current_tab._drag_selection_rect
        if not selection_rect:
            return ""

        return ""

    @staticmethod
    def _is_on_text(tab, canvas_x, canvas_y) -> bool:
        """
        判断画布坐标 (canvas_x, canvas_y) 是否落在文字上
        """
        try:
            # 使用 ViewPlugin 提供的转换服务
            if hasattr(tab, "canvas_to_page_loc"):
                page, point = tab.canvas_to_page_loc(canvas_x, canvas_y)
                if page and point:
                    # 获取点附近的文字块
                    # 使用 get_text("dict") 检查点是否在任何 block 内
                    # 优化：只检查点周围的一小块区域
                    blocks = page.get_text("blocks", clip=fitz.Rect(point.x-1, point.y-1, point.x+1, point.y+1))
                    return len(blocks) > 0

            return False
        except Exception:
            return False

    def setup_drag_event(self, access: ReaderAccess) -> None:
        """
        为当前 tab 的 canvas 绑定鼠标拖动事件
        """
        current_tab = access.get_current_tab()
        if current_tab is None:
            return

        canvas = current_tab.canvas

        # 初始化拖动状态
        if not hasattr(current_tab, '_drag_state'):
            current_tab._drag_state = {
                "start": None,
                "is_text_selection": False,
                "selection_rect": None,
                "canvas_id": None,
                "highlight_ids": [],  # 新增：存储高亮图形ID列表
            }
            current_tab._drag_selection_rect = None
            # 确保 selection 属性存在
            if not hasattr(current_tab, 'selection'):
                current_tab.selection = None

        state = current_tab._drag_state

        def on_mouse_down(event):
            # 【修改】检查是否有 Ctrl 键，有则忽略（由 SelectPlugin 处理）
            if event.state & 0x4:
                return

            # 【新增】左键按下时清除之前的划词选框
            # 无论之前是否是划词模式，只要重新点击，就清除旧的高亮
            if state.get("highlight_ids"):
                for item_id in state["highlight_ids"]:
                    canvas.delete(item_id)
            state["highlight_ids"] = []

            if state["canvas_id"] is not None:
                canvas.delete(state["canvas_id"])
            state["canvas_id"] = None
            state["selection_rect"] = None
            current_tab._drag_selection_rect = None
            current_tab.selection = None

            # 转换为画布坐标
            cx, cy = canvas.canvasx(event.x), canvas.canvasy(event.y)
            state["start"] = (cx, cy)

            # 判断是否在文字上
            state["is_text_selection"] = DragPlugin._is_on_text(current_tab, cx, cy)

            # 如果不是划词模式且开启了拖拽，记录拖拽起点（用于 scan_dragto）
            if not state["is_text_selection"] and self.drag_enabled:
                canvas.scan_mark(event.x, event.y)

        def on_mouse_drag(event):
            # 【修改】检查是否有 Ctrl 键，有则忽略
            if event.state & 0x4:
                return

            if state["start"] is None:
                return

            cx, cy = canvas.canvasx(event.x), canvas.canvasy(event.y)
            start_x, start_y = state["start"]

            if state["is_text_selection"]:
                # 划词模式：绘制选择区域

                # 清除旧的高亮
                if state.get("highlight_ids"):
                    for item_id in state["highlight_ids"]:
                        canvas.delete(item_id)
                state["highlight_ids"] = []

                # 1. 绘制一个淡淡的虚线框表示选择范围
                rect_id = canvas.create_rectangle(
                    start_x, start_y, cx, cy,
                    outline="green",
                    width=1,
                    dash=(2, 2)
                )
                state["highlight_ids"].append(rect_id)

                # 2. 计算选区矩形
                sel_rect = fitz.Rect(min(start_x, cx), min(start_y, cy), max(start_x, cx), max(start_y, cy))
                state["selection_rect"] = (sel_rect.x0, sel_rect.y0, sel_rect.x1, sel_rect.y1)
                current_tab._drag_selection_rect = state["selection_rect"]

                # 3. 查找并高亮文字
                if hasattr(current_tab, "selectable_page_positions"):
                    for page, page_canvas_rect in current_tab.selectable_page_positions:
                        intersection = sel_rect & page_canvas_rect
                        if not intersection.is_empty:
                            zoom = current_tab.zoom
                            # 转换到页面坐标
                            page_rect = fitz.Rect(
                                (intersection.x0 - page_canvas_rect.x0) / zoom,
                                (intersection.y0 - page_canvas_rect.y0) / zoom,
                                (intersection.x1 - page_canvas_rect.x0) / zoom,
                                (intersection.y1 - page_canvas_rect.y0) / zoom
                            )

                            # 【修复尝试】不使用 clip 参数，而是获取所有 quads 后手动过滤
                            # 这可以避免 clip 边界判定过于严格导致文字被忽略的问题
                            all_quads = page.get_text("quads") # Jerry: 这个参数是非法的。

                            for q in all_quads:
                                # 手动判断相交：构造 quad 的包围盒
                                # 注意：Quad 的点是 ul, ur, ll, lr (左上, 右上, 左下, 右下)
                                q_rect = fitz.Rect(q.ul, q.lr)

                                # 只有当文字块与选区相交时才绘制
                                if q_rect.intersects(page_rect):
                                    # 转换回画布坐标
                                    points = [q.ul, q.ur, q.lr, q.ll]
                                    canvas_points = []
                                    for p in points:
                                        cx_p = p.x * zoom + page_canvas_rect.x0
                                        cy_p = p.y * zoom + page_canvas_rect.y0
                                        canvas_points.extend([cx_p, cy_p])

                                    # 绘制高亮多边形
                                    # 恢复浅绿色填充样式
                                    qid = canvas.create_polygon(
                                        canvas_points,
                                        fill="#90EE90",     # LightGreen 填充
                                        stipple="gray50",   # 半透明纹理
                                        outline="",         # 无轮廓，保持整洁
                                    )
                                    # 确保文字高亮在虚线框之下，但在文字之上（实际上是在图片之上）
                                    # 虚线框(rect_id)是先画的，所以默认在下。
                                    # 我们希望：图片 < 高亮 < 虚线框
                                    # 所以这里不需要 tag_raise 到最顶层，只要比图片高就行。
                                    # 但为了保险，还是 raise 一下，反正虚线框是辅助的。
                                    canvas.tag_raise(qid)
                                    state["highlight_ids"].append(qid)

                # 检查边缘滚动
                _check_edge_scroll(canvas, event.x, event.y, current_tab)
            elif self.drag_enabled:  # 只有在启用拖拽时才执行页面滚动
                # 页面拖动模式：使用 scan_dragto 实现平滑拖动
                # gain=1 表示鼠标移动 1 像素，画布也移动 1 像素（跟随鼠标）
                canvas.scan_dragto(event.x, event.y, gain=1)

        def on_mouse_up(event):
            # 【修改】检查是否有 Ctrl 键，有则忽略
            if event.state & 0x4:
                return

            if state["start"] is None:
                return

            # 如果是划词模式，保存选择
            if state["is_text_selection"] and state["selection_rect"] is not None and hasattr(current_tab, "canvas_to_page_loc"):
                x0, y0, x1, y1 = state["selection_rect"]
                center_x = (x0 + x1) / 2
                center_y = (y0 + y1) / 2

                page, _ = current_tab.canvas_to_page_loc(center_x, center_y)

                if page:
                    _, p1 = current_tab.canvas_to_page_loc(x0, y0)
                    _, p2 = current_tab.canvas_to_page_loc(x1, y1)

                    if p1 and p2:
                        pdf_rect = fitz.Rect(p1, p2)
                        current_tab.selection = {"page": page, "rect": pdf_rect}

                        text = DragPlugin.get_selected_text(access)
                        if text.strip():
                            current_tab._selected_text = text

            state["start"] = None

        # 绑定事件
        canvas.bind("<Button-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)

    def toggle_drag(self) -> None:
        """
        切换拖拽功能的开启/关闭状态
        """
        self.drag_enabled = not self.drag_enabled
        status = "开启" if self.drag_enabled else "关闭"
        messagebox.showinfo("提示", f"页面拖拽功能已{status}")

    @override
    def loaded(self) -> None:
        """
        插件加载时：为 ReaderAccess 扩展 get_selected_text 方法
        """
        self.context.get_selected_text = MethodType(
            self.get_selected_text,
            self.context
        )

        # 在标签页切换时重新绑定事件
        self.context.add_at_notebook_tab_changed_function(
            lambda event=None: self.setup_drag_event(self.context)
        )

        # 为当前 tab 绑定事件
        if self.context.get_current_tab() is not None:
            self.setup_drag_event(self.context)

        # 添加菜单项
        self.context.add_menu_command(
            path=["工具", "拖拽"],
            label="开启/关闭页面拖拽",
            command=self.toggle_drag
        )

    @override
    def run(self) -> None:
        pass

    @override
    def unloaded(self) -> None:
        pass


def _check_edge_scroll(canvas, x, y, tab):
    """检查是否接近窗口边缘，如果是则滚动"""
    width = canvas.winfo_width()
    height = canvas.winfo_height()
    edge_threshold = 30

    # 检查水平滚动
    if x < edge_threshold and tab.canvas_width > width:
        canvas.xview_scroll(-3, "units")
    elif x > width - edge_threshold and tab.canvas_width > width:
        canvas.xview_scroll(3, "units")

    # 检查垂直滚动
    if y < edge_threshold and tab.canvas_height > height:
        canvas.yview_scroll(-3, "units")
    elif y > height - edge_threshold and tab.canvas_height > height:
        canvas.yview_scroll(3, "units")