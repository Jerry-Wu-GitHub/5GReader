from glueous_plugin import Plugin
import math
from typing import List, Tuple, Optional
import fitz  # PyMuPDF

class ViewPlugin(Plugin):
    """
    视图插件（简化版）。
    移除了所有“分隔”模式的逻辑，所有视图模式现在都默认为“连续”滚动。
    """
    name = "ViewPlugin"

    description = """
# ViewPlugin

- name: ViewPlugin
- author: Little Liu
- hotkeys: None
- menu entrance: `视图 → 单页`, `视图 → 双页`, `视图 → 书籍`

## Function

负责 PDF 页面的布局计算、渲染和视图管理。
提供核心的坐标转换服务，支持缩放、滚动和多种阅读模式（单页、双页、书籍）。

- 动态计算页面在画布上的位置
- 处理页面渲染（PDF -> Image -> Canvas）
- 管理滚动条和视图区域
- 提供画布坐标到 PDF 页面坐标的转换接口

## Api

向 Tab 类注入了以下关键属性和方法：
- `Tab.canvas_width/height` - 画布总尺寸
- `Tab.visible_page_positions` - 当前可见页面的位置信息
- `Tab.canvas_to_page_loc(x, y)` - 画布坐标转页面坐标
- `Tab.render()` - 渲染当前视图

## Depend

Python extension library:
- fitz (PyMuPDF)
- PIL (Pillow)

Other plugins:
- TabPlugin
"""

    hotkeys = []

    def __init__(self, context):
        super().__init__(context)
        self.context = context

    def _set_layout_mode_for_current_tab(self, layout_part: str):
        """
        设置新的布局模式（如 "facing", "book" 或 ""）。
        连续性始终为 "continuous"。
        """
        tab = self.context.get_current_tab()
        if tab is None:
            return

        # 模式始终以 "continuous" 开头
        new_mode_parts = ["continuous"]
        if layout_part:
            new_mode_parts.append(layout_part)

        new_mode = " ".join(new_mode_parts)

        # 只有当模式实际改变时才更新
        if new_mode != tab.display_mode:
            tab.display_mode = new_mode


    def loaded(self) -> None:
        Tab = self.context.Tab

        # ===== 辅助函数 (保持不变) =====
        def _page_size(page: fitz.Page, zoom: float):
            r = page.rect
            return (r.width * zoom, r.height * zoom)

        def _get_view_rect(tab) -> fitz.Rect:
            try:
                c = getattr(tab, "canvas", None)
                if c is not None and hasattr(c, "canvasx"):
                    sx = c.canvasx(0)
                    sy = c.canvasy(0)
                    vw = c.winfo_width()
                    vh = c.winfo_height()
                    return fitz.Rect(sx, sy, sx + vw, sy + vh)
            except Exception:
                pass
            try:
                cw = getattr(tab, "canvas_width")
                ch = getattr(tab, "canvas_height")
                return fitz.Rect(0, 0, float(cw), float(ch))
            except Exception:
                return fitz.Rect(0, 0, 1e9, 1e9)

        # ===== 页面布局计算 (保持不变) =====
        def _compute_page_canvas_rects(tab):
            zoom = getattr(tab, "zoom", 1.0)
            margin = 20 * zoom
            vgap = 20 * zoom
            hgap = 20 * zoom
            docs = list(tab.doc)
            if not docs: return []
            sizes = [_page_size(p, zoom) for p in docs]
            mode = tab.display_mode
            is_facing = "facing" in mode
            is_book = "book" in mode

            # --- 计算内部内容宽度 (inner_width)，逻辑不变 ---
            if is_facing or is_book:
                pair_widths = []
                n = len(sizes)
                start = 1 if is_book and n >= 1 else 0
                if is_book and n >= 1: pair_widths.append(sizes[0][0])
                i = start
                while i < n:
                    left_w = sizes[i][0]
                    right_w = sizes[i + 1][0] if i + 1 < n else 0
                    pair_widths.append(left_w + hgap + right_w if right_w else left_w)
                    i += 2
                inner_width = max(pair_widths) if pair_widths else (max((w for w, _ in sizes)) if sizes else 0)
            else:
                inner_width = max((w for w, _ in sizes), default=0)

            # --- 计算页面矩形，逻辑不变 ---
            rects: List[fitz.Rect] = []
            y = margin
            if is_facing or is_book:
                n = len(sizes)
                i = 0
                if is_book and n >= 1:
                    w, h = sizes[0]
                    x = margin + (inner_width - w)
                    rects.append(fitz.Rect(x, y, x + w, y + h))
                    y += h + vgap
                    i = 1
                while i < n:
                    left_w, left_h = sizes[i]
                    right_w, right_h = (sizes[i + 1] if i + 1 < n else (0, 0))
                    pair_w = left_w + (hgap + right_w if right_w else 0)
                    pair_x0 = margin + (inner_width - pair_w) / 2
                    row_h = max(left_h, right_h)
                    left_y = y + (row_h - left_h) / 2
                    right_y = y + (row_h - right_h) / 2
                    left_x = pair_x0
                    right_x = pair_x0 + left_w + (hgap if right_w else 0)
                    rects.append(fitz.Rect(left_x, left_y, left_x + left_w, left_y + left_h))
                    if right_w: rects.append(fitz.Rect(right_x, right_y, right_x + right_w, right_y + right_h))
                    y += row_h + vgap
                    i += 2
            else:
                for w, h in sizes:
                    x = margin + (inner_width - w) / 2
                    rects.append(fitz.Rect(x, y, x + w, y + h))
                    y += h + vgap

            # 【关键修复】计算并应用屏幕居中偏移量
            try:
                # 获取屏幕（视口）的宽度
                viewport_width = tab.canvas.winfo_width()
                # 计算内容的实际总宽度
                content_width = inner_width + 2 * margin

                # 如果屏幕比内容宽，则计算需要向右推的距离
                if viewport_width > content_width:
                    offset = (viewport_width - content_width) / 2
                    # 将所有计算好的矩形向右平移
                    for r in rects:
                        r.x0 += offset
                        r.x1 += offset
            except Exception:
                # 如果获取窗口宽度失败（例如窗口还未完全创建），则不进行偏移
                pass

            return rects

        def _nearest_page_index_by_point(rects: List[fitz.Rect], point: Tuple[float, float]) -> int:
            if not rects: return 0
            px, py = point
            for i, r in enumerate(rects):
                if r.x0 <= px <= r.x1 and r.y0 <= py <= r.y1: return i
            best_i, best_d = 0, float("inf")
            for i, r in enumerate(rects):
                cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
                d = (cx - px) ** 2 + (cy - py) ** 2
                if d < best_d: best_d, best_i = d, i
            return best_i

        # ===== 注入新的属性和方法 =====
        Tab.canvas_width = property(lambda self: math.ceil(max((r.x1 for r in _compute_page_canvas_rects(self)), default=0) + 20 * self.zoom))
        Tab.canvas_height = property(lambda self: math.ceil(max((r.y1 for r in _compute_page_canvas_rects(self)), default=0) + 20 * self.zoom))
        Tab.canvas_rect = property(lambda self: fitz.Rect(0, 0, float(self.canvas_width), float(self.canvas_height)))
        Tab.selectable_page_positions = property(lambda self: list(zip(list(self.doc), _compute_page_canvas_rects(self))))
        Tab.coord2real = lambda self, pos: (self.canvas.canvasx(pos[0]), self.canvas.canvasy(pos[1]))

        def canvas_to_page_loc(self, canvas_x: float, canvas_y: float) -> Tuple[Optional[fitz.Page], Optional[fitz.Point]]:
            """
            将画布坐标转换为页面对象和页面内坐标。

            Args:
                canvas_x: 画布 X 坐标（已考虑滚动条，即 canvasx）
                canvas_y: 画布 Y 坐标（已考虑滚动条，即 canvasy）

            Returns:
                (page, point):
                    page: 对应的 fitz.Page 对象，如果坐标不在任何页面上则为 None
                    point: 页面内的坐标 (fitz.Point)，基于 PDF 原始尺寸（未缩放）
            """
            # 获取所有页面的布局矩形
            page_rects = _compute_page_canvas_rects(self)

            for i, rect in enumerate(page_rects):
                # 检查点是否在矩形内
                if rect.x0 <= canvas_x <= rect.x1 and rect.y0 <= canvas_y <= rect.y1:
                    page = self.doc[i]

                    # 计算相对于页面左上角的偏移
                    offset_x = canvas_x - rect.x0
                    offset_y = canvas_y - rect.y0

                    # 还原缩放，得到 PDF 原始坐标
                    pdf_x = offset_x / self.zoom
                    pdf_y = offset_y / self.zoom

                    return page, fitz.Point(pdf_x, pdf_y)

            return None, None

        Tab.canvas_to_page_loc = canvas_to_page_loc

        def visible_page_positions(self) -> List[Tuple[fitz.Page, fitz.Rect, fitz.Rect]]:
            page_rects = _compute_page_canvas_rects(self)
            view = _get_view_rect(self)
            out = []
            for page, p_rect in zip(self.doc, page_rects):
                inter = p_rect & view
                if inter.is_empty: continue
                pr = fitz.Rect((inter.x0 - p_rect.x0) / self.zoom, (inter.y0 - p_rect.y0) / self.zoom, (inter.x1 - p_rect.x0) / self.zoom, (inter.y1 - p_rect.y0) / self.zoom)
                pr = pr & page.rect
                if pr.is_empty or pr.width <= 0 or pr.height <= 0: continue
                out.append((page, pr, p_rect))
            return out
        Tab.visible_page_positions = property(visible_page_positions)

        def update_view_attributes(self) -> None:
            try:
                x_view_start, _ = self.canvas.xview()
                y_view_start, _ = self.canvas.yview()
                cw, ch = max(1.0, float(self.canvas_width)), max(1.0, float(self.canvas_height))
                sx, sy = x_view_start * cw, y_view_start * ch
                self.state["scroll_pos"] = (sx, sy)
                vw, vh = self.canvas.winfo_width(), self.canvas.winfo_height()
                cx, cy = sx + vw / 2, sy + vh / 2
                page_rects = _compute_page_canvas_rects(self)
                nearest = _nearest_page_index_by_point(page_rects, (cx, cy))
                if self.page_no != nearest:
                    self.state["page_no"] = nearest
                    if hasattr(self.context, "update_page_number"): self.context.update_page_number()
                    if hasattr(self.context, "update_page_turning_button"): self.context.update_page_turning_button()
            except Exception: pass
        Tab.update_view_attributes = update_view_attributes

        def update_view_region(self):
            try:
                cw, ch = float(self.canvas_width), float(self.canvas_height)
                self.canvas.configure(scrollregion=(0, 0, cw, ch))
                vw, vh = self.canvas.winfo_width(), self.canvas.winfo_height()
                sx, sy = self.state.get("scroll_pos", (0.0, 0.0))
                sx, sy = max(0.0, min(sx, cw - vw)), max(0.0, min(sy, ch - vh))
                x_start, y_start = sx / cw if cw > 0 else 0.0, sy / ch if ch > 0 else 0.0
                self.canvas.xview_moveto(x_start)
                self.canvas.yview_moveto(y_start)
                self.h_scroll.set(x_start, (sx + vw) / cw if cw > 0 else 1.0)
                self.v_scroll.set(y_start, (sy + vh) / ch if ch > 0 else 1.0)
            except Exception: pass
        Tab.update_view_region = update_view_region

        def new_render(tab_self):
            if not tab_self.doc: return
            tab_self.canvas.delete("page")
            if not hasattr(tab_self, 'tk_images'): tab_self.tk_images = []
            tab_self.tk_images.clear()
            try:
                from PIL import Image, ImageTk
                for (page, clip_rect, canvas_rect) in tab_self.visible_page_positions:
                    pix = page.get_pixmap(matrix=fitz.Matrix(tab_self.zoom, tab_self.zoom), clip=clip_rect, alpha=False)
                    if pix.width == 0 or pix.height == 0: continue
                    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    if hasattr(tab_self, 'convert_color'): img = tab_self.convert_color(img)
                    tk_img = ImageTk.PhotoImage(image=img)
                    tab_self.tk_images.append(tk_img)
                    canvas_x = canvas_rect.x0 + (clip_rect.x0 * tab_self.zoom)
                    canvas_y = canvas_rect.y0 + (clip_rect.y0 * tab_self.zoom)
                    tab_self.canvas.create_image(canvas_x, canvas_y, anchor="nw", image=tk_img, tags="page")
            except Exception: pass
        Tab.render = new_render

        # 【简化】只创建布局菜单，不再有“连续性”菜单
        try:
            layout_modes = {
                "单页": "",
                "双页": "facing",
                "书籍": "book"
            }
            for label, layout_part in layout_modes.items():
                self.context.add_menu_command(
                    path=["视图"],
                    label=label,
                    command=(lambda part=layout_part: self._set_layout_mode_for_current_tab(part)),
                )
        except Exception as e:
            print(f"创建视图菜单失败: {e}")

    def run(self, *args, **kwargs) -> None: pass
    def unloaded(self) -> None: pass