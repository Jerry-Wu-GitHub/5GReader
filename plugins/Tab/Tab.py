from __future__ import annotations

from math import ceil
import tkinter as tk
from tkinter import messagebox, ttk
import os
from typing import Any, List, Tuple, override
from types import MethodType

from PIL import Image, ImageTk
import fitz  # PyMuPDF

from plugins.Tab.FileState import FileState, FileHasher

from glueous import ReaderAccess
from glueous_plugin import Plugin



class Tab:
    """
    Tab 类，单个文件的标签页容器，管理单电子书文件的显示和状态。
    """

    #### Class Data Descriptors ####

    CANVAS_CONTEXT_NAME: str = "tab canvas"

    #### Magic Methods ####

    def __init__(self, context: ReaderAccess, file_path: str = None):
        self.context = context

        # 与父容器建立关联
        self.notebook = self.context.get_notebook() # 父标签页容器
        self.frame = ttk.Frame(self.notebook)  # 标签页内容框架
        self.notebook.add(self.frame)          # 将frame添加到Notebook

        self.state = FileState(file_path).to_json()
        self.doc = None  # PyMuPDF文档对象

        self.tk_images = []
        # 创建标签页内的UI组件
        self.create_widgets()

        # 打开文件
        self.open()


    def __del__(self):
        """释放资源"""
        if hasattr(self, 'doc'):
            self.doc.close()


    #### Data Descriptors associated with FileState ####

    @property
    def file_path(self) -> str:
        """
        当前打开的文件的绝对路径。
        """
        return self.state["file_path"]

    @file_path.setter
    def file_path(self, path: str) -> None:
        raise AttributeError("`file_path 'is a read-only attribute. If you want to open another file, please call the `.open()` method.")


    @property
    def open_count(self) -> int:
        """
        文件被打开的次数。
        """
        return self.state["open_count"]

    @open_count.setter
    def open_count(self, count: int) -> None:
        if count < 0:
            raise ValueError(f"Open count cannot be negative, got {count}")
        self.state["open_count"] = count


    @property
    def display_mode(self) -> str:
        """
        显示模式。
        【修复】始终返回字符串值，以供外部逻辑（如 .split()）使用。
        """
        return self.state["display_mode"]

    @display_mode.setter
    def display_mode(self, mode: str | object) -> None:
        """
        【修复】接受字符串或枚举，但始终在 state 中存储字符串值。
        """
        from plugins.Tab.FileState import DisplayMode

        valid_modes_values = [m.value for m in DisplayMode]
        
        value_to_set = ""
        if isinstance(mode, str) and mode in valid_modes_values:
            value_to_set = mode
        elif isinstance(mode, DisplayMode) and mode.value in valid_modes_values:
            value_to_set = mode.value
        else:
            raise ValueError(f"Invalid display mode: {mode}. Must be one of {valid_modes_values}")

        if self.state["display_mode"] != value_to_set:
            self.state["display_mode"] = value_to_set
            self.update_view_region()
            self.render()


    @property
    def scroll_pos(self) -> Tuple[float, float]:
        """
        滚动偏移量（单位：逻辑像素，Page 坐标）。
        """
        return self.state["scroll_pos"]

    @scroll_pos.setter
    def scroll_pos(self, pos: Tuple[float, float]) -> None:
        self.state["scroll_pos"] = pos
        # 更新画布滚动位置
        self.update_view_region()
        self.render()


    @property
    def page_no(self) -> int:
        """
        当前页码（0-based）。
        """
        return self.state["page_no"]

    @page_no.setter
    def page_no(self, page_no: int) -> None:
        if not 0 <= page_no < self.total_pages:
            raise ValueError(f"Page number out of range: {page_no} (total pages: {self.total_pages})")
        self.state["page_no"] = page_no
        self.update_view_region()
        self.render()


    @property
    def zoom(self) -> float:
        """
        缩放比例。
        """
        return self.state["zoom"]

    @zoom.setter
    def zoom(self, zoom_level: float) -> None:
        if zoom_level <= 0:
            raise ValueError(f"Zoom level must be positive, got {zoom_level}")
        self.state["zoom"] = zoom_level

        # 更新滚动区域
        self.update_view_region()
        self.render()


    @property
    def rotation(self) -> int:
        """
        页面旋转角度。
        """
        return self.state["rotation"]

    @rotation.setter
    def rotation(self, angle: int) -> None:
        if angle not in FileState.ROTATIONS:
            raise ValueError(f"Invalid rotation angle: {angle}. Must in {FileState.ROTATIONS}.")
        self.state["rotation"] = angle
        self.update_view_region()
        self.render()


    #### Other Data Descriptors ####

    @property
    def dpi(self) -> int:
        """
        分辨率。
        """
        return self.context.get_setting("dpi", 72)


    @property
    def total_pages(self) -> int:
        """
        这本书的总页数。
        """
        if self.doc:
            return len(self.doc)
        return 0


    @property
    def page(self) -> fitz.Page | None:
        """
        获取当前页的 Page 对象。
        """
        if self.doc is None:
            return None
        if not 0 <= self.page_no < self.total_pages:
            raise ValueError(f"Invalid page number: {self.page_no}")
        return self.doc[self.page_no]


    @property
    def canvas_width(self) -> float:
        """
        画下要显示的页面所需的画布宽度。
        """
        return self.page.rect.width * self.zoom

    @property
    def canvas_height(self) -> float:
        """
        画下要显示的页面所需的画布高度。
        """
        return self.page.rect.height * self.zoom

    @property
    def canvas_rect(self) -> fitz.Rect:
        """
        返回；经过缩放后，页面的形状矩形。
        """
        return self.page.rect * self.zoom


    @property
    def visible_page_positions(self) -> List[Tuple[fitz.Page, fitz.Rect, fitz.Rect]]:
        """
        返回：
        - List[(能见页面, 该页面上的能见区域, 该区域显示在整块 canvas 上的位置矩形)]

        用于 render 方法。

        注意：可能会有多个页面。
        """
        x_view_start, x_view_end = self.canvas.xview()
        y_view_start, y_view_end = self.canvas.yview()

        # 可见页面区域坐标
        page_x1 = x_view_start * self.page.rect.width
        page_y1 = y_view_start * self.page.rect.height
        page_x2 = x_view_end   * self.page.rect.width
        page_y2 = y_view_end   * self.page.rect.height
        visible_page_region = fitz.Rect(page_x1, page_y1, page_x2, page_y2)

        # 该区域显示在整块 canvas 上的位置
        visible_canvas_region = visible_page_region * self.zoom

        return [(self.page, visible_page_region, visible_canvas_region)]


    @property
    def selectable_page_positions(self) -> List[Tuple[fitz.Page, fitz.Rect]]:
        """
        返回：
        - List[(可被选择的页面, 该页面的在整块 canvas 上的位置矩形)]

        注意：可能会有多个页面。
        """
        return [(self.page, fitz.Rect(0, 0, self.page.rect.width, self.page.rect.height) * self.zoom)]


    def coord2real(self, pos: Tuple[float, float]) -> Tuple[float, float]:
        """
        将窗口上的画布上的坐标转换为在整个画布上的坐标。
        """
        x_view_start, _ = self.canvas.xview()
        y_view_start, _ = self.canvas.yview()

        return (
            self.canvas_width  * x_view_start + pos[0],
            self.canvas_height * y_view_start + pos[1],
        )


    #### Methods ####

    def update_view_attributes(self) -> None:
        """
        当用户通过拖动滑动条、鼠标滚轮滚动、拖动、按方向键等方式移动视图位置时，应调用此函数，实时更新属性。

        此方法不会主动刷新画布。
        """
        x_view_start, _ = self.canvas.xview()
        y_view_start, _ = self.canvas.yview()
        self.state["scroll_pos"] = (self.page.rect.width * x_view_start, self.page.rect.height * y_view_start)

    def auto_update_view_attributes(self, func):
        """
        装饰器：在函数执行后自动调用 update_view_attributes() 方法。
        """
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            self.update_view_attributes()
            return result
        return wrapper


    def update_view_region(self):
        """
        当程序直接为 zoom、rotation、scroll_pos 属性进行赋值操作时，应调用此方法，实时同步显示。
        """
        # 计算视图起始比例（基于滚动位置和页面尺寸）
        x_view_start = max(self.scroll_pos[0] / self.page.rect.width, 0.0)
        y_view_start = max(self.scroll_pos[1] / self.page.rect.height, 0.0)

        # 计算缩放后的页面尺寸，更新滚动区域
        self.canvas.configure(scrollregion=(0, 0, self.canvas_width, self.canvas_height))

        # 计算视图显示长度（基于画布尺寸和页面尺寸）
        self.canvas.update_idletasks()
        x_view_length = self.canvas.winfo_width() / self.canvas_width
        y_view_length = self.canvas.winfo_height() / self.canvas_height

        # 限制视图范围在 [0, 1] 内
        x_view_end = min(x_view_start + x_view_length, 1.0)
        y_view_end = min(y_view_start + y_view_length, 1.0)

        # 更新滚动条位置
        self.h_scroll.set(x_view_start, x_view_end)
        self.v_scroll.set(y_view_start, y_view_end)

        # 更新画布视图范围
        self.canvas.xview_moveto(x_view_start)
        self.canvas.yview_moveto(y_view_start)

    def auto_update_view_region(self, func):
        """
        装饰器：在函数执行后自动调用 update_view_attributes() 方法。
        """
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            self.update_view_region()
            return result
        return wrapper


    def convert_color(self, img: Image.Image) -> Image.Image:
        """
        转换图像颜色，会在 render 方法中调用。
        """
        return img


    # def rotate_image(self, img: Image.Image, angle: int) -> Image.Image:
    #     """
    #     旋转图像，自动选择性能最优的方案，支持 0 度。

    #     Params:

    #     - `img`: 要旋转的图像。
    #     - `angle`: 旋转的度数。

    #     Returns:

    #     - 若 angle = 0，则返回原图像，否则返回原图像旋转后的副本。
    #     """
    #     if angle == 0:
    #         return img  # 直接返回，不创建新对象

    #     rotate_map = {
    #         90: Image.ROTATE_90,
    #         180: Image.ROTATE_180,
    #         270: Image.ROTATE_270
    #     }
    #     if angle in rotate_map:
    #         return img.transpose(rotate_map[angle])

    #     return img.rotate(angle, expand=True)


    def render(self):
        """
        渲染页面。

        为加速渲染，仅渲染会显示到画布上的部分。
        """
        if not self.doc or not (0 <= self.page_no < self.total_pages):
            return

        # 清空画布和缓存
        self.canvas.delete("all")
        self.tk_images.clear()

        for (page, page_rect, canvas_rect) in self.visible_page_positions:
            # 渲染页面图像
            pix = page.get_pixmap(
                clip = page_rect,
                dpi = int(self.dpi * self.zoom),
                colorspace = "rgb"
            )

            # 图像转换
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            img = self.convert_color(img).resize((ceil(canvas_rect.width), ceil(canvas_rect.height)))
            self.tk_images.append(ImageTk.PhotoImage(image = img))

            # 在画布上绘制
            self.canvas.create_image(
                canvas_rect.x0,
                canvas_rect.y0,
                anchor = tk.NW,
                image  = self.tk_images[-1]
            )

            # print(self.page.rect)
            # print((self.canvas.winfo_width(), self.canvas.winfo_width()))


    def auto_render(self, func):
        """
        装饰器：在函数执行后自动调用 render() 方法。
        """
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            self.render()
            return result
        return wrapper


    def create_widgets(self):
        """
        创建标签页内的显示组件（画布、滚动条等）。
        【注意】恢复到原始版本，滚动逻辑将由 ViewPlugin 注入。
        """
        # 显示区域（带滚动条）
        self.display_frame = ttk.Frame(self.frame)

        # 滚动条
        self.v_scroll = ttk.Scrollbar(self.display_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.h_scroll = ttk.Scrollbar(self.display_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # 画布 (使用原始的、轻量级的回调绑定)
        self.canvas = tk.Canvas(
            self.display_frame,
            xscrollcommand=self.auto_render(self.auto_update_view_attributes(self.h_scroll.set)),
            yscrollcommand=self.auto_render(self.auto_update_view_attributes(self.v_scroll.set)),
            bg="white",
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)


    def _read_state(self) -> None:
        """
        从应用数据中搜索这本书的数据
        """
        file_path = self.file_path
        
        file_states = self.context.data.setdefault("file_states", {})
        if not isinstance(file_states, dict):
            file_states = {}
            self.context.data["file_states"] = file_states

        file_hash = FileHasher().hash_file(file_path)
        if file_hash in file_states:
            self.state = file_states[file_hash]
            self.state["file_path"] = file_path
        else:
            self.state = FileState(self.file_path).to_json()
            file_states[file_hash] = self.state



    def open(self) -> bool:
        """
        打开文件并初始化。

        返回是否打开成功。
        """
        try:
            # 关闭已打开的文档
            if self.doc:
                self.doc.close()

            self._read_state()

            # 用 pymupdf 读取文档
            self.doc = fitz.open(self.file_path)

            # 更新标签页标题（显示文件名）
            tab_title = os.path.basename(self.file_path)
            self.notebook.tab(self.frame, text = tab_title)

            # 刷新显示
            self.update_view_region()
            self.render()

            # 计数打开次数
            self.state["open_count"] += 1
            return True
        except Exception as e:
            messagebox.showerror("错误", f"打开失败: {str(e)}")
            self.reset()
            return False


    def reset(self):
        """重置标签页状态"""
        if self.doc:
            self.doc.close()
        self.state = None
        self.doc = None
        self.canvas.delete("all")
        # 仅在frame被管理时修改标签标题
        try:
            self.notebook.tab(self.frame, text="空标签页")
        except tk.TclError:
            # 若frame已被移除，忽略错误
            pass



class TabPlugin(Plugin):
    """
    标签页插件：提供对标签页的管理接口。
    """

    # 插件信息
    name = "TabPlugin"
    description = """
# TabPlugin

- name: TabPlugin
- author: Jerry
- hotkeys: None
- menu entrance: None

## Function

Manage tab operations including creating, getting current tab, and closing tabs. 

Provide core tab functionality for the PDF reader.

## Api

- `context.create_tab(file_path)`: Create a new tab with the specified file path.
- `context.get_current_tab()`: Get the currently active tab.
- `context.close_tab(tab)`: Close the specified tab.
- `context.tabs`: List of all open tabs.
- `context.Tab`: The Tab class itself.
- `context.FileHasher`: FileHasher is used to calculate the hash value of files and supports multiple algorithms.

## Depend

Python extension library:
- fitz (PyMuPDF)
- PIL (Pillow)

Other plugins:
- ContextMenuPlugin

## Others

This plugin must be loaded before any other plugins that manipulate tabs.
"""

    @staticmethod
    def create_tab(access: ReaderAccess, file_path: str | None = None) -> Tab:
        """
        创建新标签页
        """
        new_tab = Tab(access, file_path)

        # 激活新标签页
        access._reader.notebook.select(new_tab.frame)

        # 添加到标签页列表
        access.tabs.append(new_tab)


    @staticmethod
    def get_current_tab(access: ReaderAccess) -> Tab | None:
        """
        获取当前激活的标签页实例。
        """
        reader = access._reader

        if not access.tabs:
            return None

        # 获取当前选中标签页的路径字符串
        current_frame_path = reader.notebook.select()
        if not current_frame_path:
            return None

        # 将路径字符串转换为窗口对象
        try:
            current_frame = reader.root.nametowidget(current_frame_path)
        except KeyError:
            return None

        # 从标签页列表中找到匹配的 Tab
        for tab in access.tabs:
            if tab.frame == current_frame:
                return tab
        return None


    @staticmethod
    def close_tab(access: ReaderAccess, tab: Tab) -> None:
        """
        关闭一个标签页，返回是否成功关闭。
        """
        if tab in access.tabs:
            access.tabs.remove(tab)

        tab.reset()
        access._reader.notebook.forget(tab.frame)


    def rebind_context_menu(self, event = None) -> None:
        """
        重新绑定标签页的右键菜单。
        """
        current_tab = self.context.get_current_tab()
        self.context.context_menu_manager.set_context(Tab.CANVAS_CONTEXT_NAME, current_tab and current_tab.canvas)


    @override
    def loaded(self) -> None:
        """
        在插件被加载时运行。
        """

        # 添加操作标签的接口，方便其他插件调用
        self.context.create_tab      = MethodType(self.create_tab     , self.context)
        self.context.get_current_tab = MethodType(self.get_current_tab, self.context)
        self.context.close_tab       = MethodType(self.close_tab      , self.context)
        self.context.tabs: List[Tab] = []
        self.context.Tab : type      = Tab
        self.context.FileHasher      = FileHasher

        # 右键菜单
        self.context.add_at_notebook_tab_changed_function(self.rebind_context_menu)
        self.rebind_context_menu()


    @override
    def run(self) -> None:
        pass


    @override
    def unloaded(self) -> None:
        pass
