from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import numpy as np
import os
import threading
from tkinter import messagebox
from typing import Any, Dict, List, Tuple, override
import warnings

import fitz

from glueous_plugin import Plugin



OCRResult = Tuple[Tuple[Tuple[int, int], Tuple[int, int]], str, float, str]



def select_fontname(text: str, fontnames: List[str]) -> str:
    for fontname in fontnames:
        if all(fitz.Font(fontname).has_glyph(ord(char)) for char in text):
            return fontname
    return fontnames[-1]



# def calculate_fontsize(
#     rect: Tuple[Tuple[int, int], Tuple[int, int]],
#     text: str,
#     fontname: str,
#     relative_error: float
# ) -> float:
#     """
#     计算可以塞进 rect 矩形的最大字号。
#     """
#     if not text:
#         return 0

#     font = fitz.Font(fontname)

#     # 计算宽度上限
#     width_limit = rect[1][0] - rect[0][0]

#     # 二分查找搜索最佳字号
#     left = 1
#     right = rect[1][1] - rect[0][1]
#     while (right - left) / left >= relative_error:
#         mid = (left + right) / 2
#         text_width = font.text_length(text, mid)
#         if text_width < width_limit:
#             # 可以放下
#             left = mid
#         else:
#             # 放不下
#             right = mid

#     return left



class OCRPlugin(Plugin):
    """
    OCR 插件：自动识别文档中图像的文字并整合到 Page 中。
    """

    # 插件信息
    name = "OCRPlugin"

    description = """
# OCRPlugin

- name: OCRPlugin
- author: Glueous Reader
- hotkeys: `Ctrl+Shift+O`
- menu entrance: `工具 → OCR → 开启自动OCR`, `工具 → OCR → 重新识别当前页`

## Function

使用 EasyOCR 库对文档中的图像进行光学字符识别（OCR），提取图像中的文本及其位置信息。

- 支持自动 OCR：优先识别当前可见页面，然后是可选择页面
- 支持手动重新识别当前页面
- 识别结果缓存到 `data.json`，避免重复识别
- 通过 `Page.insert_text()` 方法，将 OCR 结果整合到原始文本中

## Api

None.

## Depend

Python extension library:
- easyocr
- torch (EasyOCR 依赖)

Other plugins:
- TabPlugin

## Others

首次运行会下载 OCR 模型，可能需要较长时间。
"""

    hotkeys = ["<Control-Shift-O>"]

    def __init__(self, context):
        super().__init__(context)

        # OCR 引擎（延迟初始化）
        self._ocr_reader = None

        # 进程池（没用到）
        self._executor = None  # 不立即创建

        # OCR 工作线程
        self.ocr_thread = None

        # 保存原始的 Tab.open 方法
        self.original_tab_open = None


    @property
    def ocr_reader(self) -> "easyocr.Reader":
        if self._ocr_reader is None:
            import easyocr

            try:
                self._ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu = True)
                print(f"✅ GPU 模式初始化成功")
            except Exception as e:
                print(f"⚠️ GPU 失败: {e}，切换到 CPU")
                self._ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu = False)
                print(f"✅ CPU 模式初始化成功")

        return self._ocr_reader


    # @property
    # def executor(self):
    #     """延迟创建进程池"""
    #     if self._executor is None:
    #         import sys

    #         # 确保子进程能找到模块
    #         if sys.platform == 'win32':
    #             sys.path.insert(0, os.path.dirname(__file__))

    #         self._executor = ProcessPoolExecutor(
    #             max_workers = self.concurrency,
    #             initializer = ocr_worker.init_worker
    #         )
    #     return self._executor


    @property
    def ocr_settings(self) -> Dict[str, Any]:
        ocr_settings = self.context.data.setdefault("ocr_settings", {})
        if not isinstance(ocr_settings, dict):
            ocr_settings = {}
            self.context.data["ocr_settings"] = ocr_settings
        return ocr_settings


    @property
    def auto_ocr_enabled(self) -> bool:
        """
        返回是否开启自动 OCR。
        """
        return self.ocr_settings.setdefault("auto_ocr_enabled", False)


    @property
    def cache(self) -> Dict[str, Dict[int, List[Tuple[List, str, float]]]]:
        """
        返回所有文件的 OCR 缓存。
        """
        return self.ocr_settings.setdefault("cache", {})


    @property
    def concurrency(self) -> int:
        """
        返回多进程加速时的最大并发数。
        """
        return self.ocr_settings.setdefault("concurrency", os.cpu_count())

    # @concurrency.setter
    # def concurrency(self, value: int):
    #     """
    #     设置多进程加速时的最大并发数。
    #     """
    #     new_concurrency = max(value, 1) # 不能为 0 或负数
    #     if new_concurrency != self.concurrency:
    #         self.ocr_settings["concurrency"] = new_concurrency
    #         self.executor = ProcessPoolExecutor(max_workers = new_concurrency)


    @property
    def max_tasks(self) -> int:
        """
        一次性识别的最大页面数。
        """
        return self.ocr_settings.setdefault("max_tasks", 1)#(self.concurrency + 1) // 2)

    @max_tasks.setter
    def max_tasks(self, value: int):
        """
        设置一次性识别的最大页面数。
        """
        self.ocr_settings["max_tasks"] = max(value, 1) # 不能为 0 或负数


    @property
    def fontnames(self) -> str:
        """
        返回插入文字的字体。
        """
        return self.ocr_settings.setdefault("fontnames", ["hevi", "china-s", "china-ss"])


    @property
    def fontsize_relative_error(self) -> float:
        """
        返回计算插入文字的字号的相对误差。
        """
        return self.ocr_settings.setdefault("fontsize_relative_error", 0.01)

    @fontsize_relative_error.setter
    def fontsize_relative_error(self, value):
        """
        设置计算插入文字的字号的相对误差。
        """
        if value <= 0:
            raise ValueError("`fontsize_relative_error` should be a positive number")
        self.ocr_settings["fontsize_relative_error"] = value


    def enabled_auto_ocr(self):
        """
        启用自动 OCR 。
        """
        self.ocr_settings["auto_ocr_enabled"] = True


    def disenabled_auto_ocr(self):
        """
        禁用自动 OCR 。
        """
        self.ocr_settings["auto_ocr_enabled"] = False


    def shift_auto_ocr(self) -> bool:
        """
        切换自动 OCR 开关。

        返回切换后的状态。
        """
        if self.auto_ocr_enabled:
            self.disenabled_auto_ocr()
        else:
            self.enabled_auto_ocr()
        return self.auto_ocr_enabled


    def get_ocr_cache(self, file_path) -> Dict[int, List[Tuple[List, str, float]]]:
        """
        返回文件的 OCR 缓存。
        """
        file_hash = self.context.FileHasher().hash_file(file_path)
        file_ocr_cache = self.cache.setdefault(file_hash, {})

        return file_ocr_cache


    @staticmethod
    def get_image_infos(page: fitz.Page) -> List[Tuple[fitz.Rect, np.ndarray]]:
        """
        提取 page 上的所有图像。

        Returns:

        返回列表的每个元素是一个三元组，代表一个图像的信息：(该图像在page上的矩形, 能被easyocr处理的格式（含原图尺寸信息）)
        """
        results = []
        for image_info in page.get_images(full = True):
            # 该图像在page上的矩形
            bbox = page.get_image_bbox(image_info)

            # 获取图像的 pixmap
            pixmap = fitz.Pixmap(page.parent, image_info[0])

            # 将 pixmap 转换为 numpy array，适配 easyocr
            img_array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)

            results.append((bbox, img_array))
        return results


    @staticmethod
    def img2page_coord(img_coord: Tuple[int, int], img_start_coord: Tuple[int, int], scale: Tuple[float, float]) -> Tuple[int, int]:
        """
        将图像坐标转换为页面坐标。
        
        Args:
            img_coord: 图像上的坐标 (x, y)
            img_start_coord: 图像在页面上的起始坐标 (x, y)
            scale: 缩放比例 (scale_x, scale_y)
            
        Returns:
            页面上的坐标 (x, y)
        """
        x, y = img_coord
        start_x, start_y = img_start_coord
        scale_x, scale_y = scale

        return (start_x + x * scale_x, start_y + y * scale_y)



    def perform_ocr(self, page: fitz.Page) -> List[OCRResult]:
        """
        对 page 对象上的所有图片进行 OCR 。

        使用多线程加速。

        Return like:

            [
                ([(x0, y0), (x1, y1)], "text", fontsize, "fontname"),
                ...
            ]

        其中 (x0, y0), (x1, y1) 依次是这段文字在 page 上的左上角、右下角坐标。
        """

        ocr_results = []
        image_infos = self.get_image_infos(page)
        if not image_infos:
            return []

        image_rects, image_arrays = zip(*image_infos)

        # 对每个图像进行 OCR 识别，后期可使用进程池并发加速
        # ocr_raw_resultses = list(self.executor.map(ocr_worker.readtext, image_arrays))
        ocr_raw_resultses = [
            self.ocr_reader.readtext(img_array, detail=1, paragraph=False, min_size=10)
            for img_array in image_arrays
        ]

        for (img_rect, img_array, ocr_raw_results) in zip(image_rects, image_arrays, ocr_raw_resultses):
            # 将图像坐标转换为页面坐标
            img_width,  img_height  = img_array.shape[1], img_array.shape[0]
            page_width, page_height = page.rect.width,    page.rect.height

            # 计算缩放比例
            scale = (page_width  / img_width, page_height / img_height)

            # 转换坐标
            img_start_coord = (img_rect.x0, img_rect.y0)
            for (points, text, _) in ocr_raw_results:
                if not text:
                    continue

                rect = (
                    self.img2page_coord(points[0], img_start_coord, scale),
                    self.img2page_coord(points[2], img_start_coord, scale),
                )

                # 选择字体
                fontname = select_fontname(text, self.fontnames)

                # 计算字号
                width_limit = rect[1][0] - rect[0][0]
                fontsize = width_limit / fitz.Font(fontname).text_length(text, 1)

                ocr_results.append((
                    rect,
                    text,
                    fontsize,
                    fontname
                ))

        return ocr_results


    def insert_into_page(self, ocr_results: List[OCRResult], page: fitz.Page) -> None:
        """
        将 OCR 结果插入到页面中。
        """
        for (((x0, y0), (x1, y1)), text, fontsize, fontname) in ocr_results:
            if not text:
                continue

            # rect = fitz.Rect(x0, y0, x1, y1)

            # page.insert_textbox(
            #     rect,
            #     text,
            #     fontsize = fontsize,
            #     fontname = fontname,
            #     # render_mode = 3 # 设为3表示不渲染文本（隐藏）
            # )

            page.insert_text(
                (x0, y1 - fontsize * 0.3),
                text,
                fontsize = fontsize,
                fontname = fontname,
                # render_mode = 3 # 设为3表示不渲染文本（隐藏）
            )


    def ocr_update_page(self, page: fitz.Page, cache: Dict[int, List[Tuple[List, str]]]) -> None:
        """
        对 page 进行 OCR ，并将 OCR 得到的文字插入到 page 的正确位置。

        将 OCR 结果存入缓存中。
        """

        print(f"正在对第 {page} 页进行 OCR...")

        # 获取当前页的 OCR 结果
        ocr_results = self.perform_ocr(page)

        # 将 OCR 结果插入到页面中
        self.insert_into_page(ocr_results, page)

        # 将 OCR 结果存入缓存中
        cache[str(page.number)] = ocr_results



    def get_tasks(self, max_tasks: int = 1) -> List[fitz.Page]:
        """
        按优先级获取待处理的OCR任务列表。

        如果在 file_ocr_cache 中已经有该页面的 OCR 缓存，则不会加入该页面。

        Args:
            max_tasks: 最大任务数

        Returns:
            fitz.Page 列表
        """
        # 获取当前标签页
        current_tab = self.context.get_current_tab()
        if not current_tab or not current_tab.doc:
            return []

        # 获取缓存
        file_ocr_cache = self.get_ocr_cache(current_tab.file_path)

        tasks = []

        # 优先级0：当前页面
        current_page_no = current_tab.page_no
        if str(current_page_no) not in file_ocr_cache:
            tasks.append(current_tab.page)

        # 优先级1：可见页面
        for (page, _, _) in current_tab.visible_page_positions:
            if len(tasks) >= max_tasks:
                break
            if (str(page.number) not in file_ocr_cache) and (page not in tasks):
                tasks.append(page)

        # 优先级2：可选择页面
        for (page, _) in current_tab.selectable_page_positions:
            if len(tasks) >= max_tasks:
                break
            if (str(page.number) not in file_ocr_cache) and (page not in tasks):
                tasks.append(page)

        # 限制任务数量
        return tasks[:max_tasks]


    @override
    def loaded(self):
        """
        插件加载时执行：注册菜单项并启动后台任务。
        """
        # 注册菜单项
        self.context.add_menu_command(
            path = ["工具", "OCR"],
            label = "开启/关闭自动OCR",
            command = self.toggle_auto_ocr,
            accelerator = "Ctrl+Shift+O"
        )

        self.context.add_menu_command(
            path = ["工具", "OCR"],
            label = "重新识别当前页",
            command = self.reocr_current_page
        )

        # 启动后台OCR任务
        self.context.add_periodically_execute_function(self.start_ocr_thread)

        Tab = self.context.Tab
        self.original_tab_open = Tab.open

        def open_with_ocr(tab: Tab) -> None:
            self.original_tab_open(tab)

            if self.auto_ocr_enabled:
                file_ocr_cache = self.get_ocr_cache(tab.file_path)
                for (page_no, ocr_results) in file_ocr_cache.items():
                    self.insert_into_page(ocr_results, tab.doc[int(page_no)])

        Tab.open = open_with_ocr


    def toggle_auto_ocr(self) -> None:
        """
        切换自动OCR开关。
        """
        enabled = self.shift_auto_ocr()
        if enabled:
            self.context.print("自动OCR：开启")
        else:
            self.context.print("自动OCR：关闭")


    def reocr_current_page(self) -> None:
        """
        重新识别当前页面。
        """
        current_tab = self.context.get_current_tab()
        if (not current_tab) or (not current_tab.doc) or (not current_tab.file_path):
            messagebox.showwarning("提示", "请先打开一个文档")
            return

        file_path = current_tab.file_path
        page_no = current_tab.page_no

        # 清除缓存
        file_ocr_cache = self.get_ocr_cache(file_path)
        if page_no in file_ocr_cache:
            file_ocr_cache.pop(page_no)

        current_tab.reset()
        current_tab.open()

        # 重新OCR
        if not self.auto_ocr_enabled:
            self.ocr_update_page(current_tab.page, file_ocr_cache)


    def start_ocr_thread(self) -> None:
        """
        启动 OCR 工作线程。
        """
        if self.auto_ocr_enabled and ((self.ocr_thread is None) or (not self.ocr_thread.is_alive())):
            self.ocr_thread = threading.Thread(target = self.run, daemon=True)
            self.ocr_thread.start()


    @override
    def run(self) -> None:
        """
        执行OCR任务。
        """
        # 获取待处理的任务
        tasks = self.get_tasks(max_tasks = self.max_tasks)

        for page in tasks:
            file_path = page.parent.name
            page_no = page.number

            # 获取缓存
            file_ocr_cache = self.get_ocr_cache(file_path)

            # 如果已经有缓存，跳过
            if str(page_no) in file_ocr_cache:
                continue

            # 执行OCR
            self.ocr_update_page(page, file_ocr_cache)


    def stop_ocr_worker(self) -> None:
        """
        停止 OCR 工作线程。
        """
        if self.ocr_thread:
            self.ocr_thread.join(timeout=2)


    @override
    def unloaded(self):
        """
        插件卸载时执行：恢复原始方法并停止工作线程。
        """
        self.stop_ocr_worker()

        # 恢复原始 Tab.open 方法
        if self.original_tab_open is not None:
            self.context.Tab.open = self.original_tab_open
