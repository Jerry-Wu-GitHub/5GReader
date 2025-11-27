"""
OCR 插件：对文档中的图像进行光学字符识别
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Tuple, override
import fitz

from glueous_plugin import Plugin


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
        self.ocr_reader = None
        self.ocr_lock = threading.Lock()

        # 自动 OCR 开关
        self.auto_ocr_enabled = False

        # OCR 任务队列和工作线程
        self.ocr_queue: List[Tuple[int, str, int]] = []  # [(priority, file_path, page_no), ...]
        self.ocr_thread = None
        self.stop_ocr_thread = False

        # 保存原始的 get_text 方法
        self.original_get_text = None

        # 记录上次检查的页面，用于检测翻页
        self.last_checked_page = None


    def initialize_ocr_reader(self) -> None:
        """
        初始化 OCR 引擎（延迟加载）。
        """
        if self.ocr_reader is not None:
            return

        try:
            import easyocr
            import warnings
            print("正在初始化 OCR 引擎...")
            # 过滤 PyTorch 的警告信息
            warnings.filterwarnings("ignore", category=UserWarning, module="torch")
            # 支持中文和英文，使用 CPU 模式
            self.ocr_reader = easyocr.Reader(
                ["ch_sim", "en"],
                gpu=False,
                verbose=False  # 减少输出信息
            )
            print("OCR 引擎初始化完成")
        except ImportError:
            print("错误：未安装 easyocr 库，请运行：pip install easyocr")
            self.disable()
        except Exception as e:
            print(f"OCR 引擎初始化失败: {e}")
            self.disable()


    def get_ocr_cache_key(self, file_path: str, page_no: int) -> str:
        """
        生成 OCR 缓存的键名。
        """
        return f"{file_path}#page{page_no}"


    def get_cached_ocr_result(self, file_path: str, page_no: int) -> List[Dict[str, Any]] | None:
        """
        从缓存中获取 OCR 结果。

        Returns:
            List of OCR results or None if not cached
        """
        ocr_cache = self.context.data.setdefault("ocr_cache", {})
        cache_key = self.get_ocr_cache_key(file_path, page_no)
        return ocr_cache.get(cache_key)


    def save_ocr_result(self, file_path: str, page_no: int, result: List[Dict[str, Any]]) -> None:
        """
        保存 OCR 结果到缓存。
        """
        ocr_cache = self.context.data.setdefault("ocr_cache", {})
        cache_key = self.get_ocr_cache_key(file_path, page_no)
        ocr_cache[cache_key] = result


    def perform_ocr_on_page(self, file_path: str, page_no: int) -> List[Dict[str, Any]]:
        """
        对指定页面执行 OCR 识别。

        Returns:
            List of OCR results: [{"text": str, "bbox": [x0, y0, x1, y1], "confidence": float}, ...]
        """
        # 检查缓存
        cached_result = self.get_cached_ocr_result(file_path, page_no)
        if cached_result is not None:
            return cached_result

        # 初始化 OCR 引擎
        if self.ocr_reader is None:
            self.initialize_ocr_reader()
            if self.ocr_reader is None:
                return []

        doc = None
        try:
            # 打开文档
            doc = fitz.open(file_path)
            if page_no >= len(doc):
                print(f"页码 {page_no} 超出范围")
                return []

            page = doc[page_no]

            # 获取页面上的所有图像
            image_list = page.get_images()

            if not image_list:
                # 没有图像，保存空结果到缓存
                self.save_ocr_result(file_path, page_no, [])
                return []

            ocr_results = []

            for img_index, img_info in enumerate(image_list):
                try:
                    # 获取图像的 xref
                    xref = img_info[0]

                    # 提取图像数据
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]

                    # 获取图像在页面上的位置
                    image_rects = page.get_image_rects(xref)
                    if not image_rects:
                        continue

                    # 使用第一个矩形（通常图像只出现一次）
                    image_bbox = image_rects[0]

                    # 检查图像大小，过小的图像跳过
                    if image_bbox.width < 10 or image_bbox.height < 10:
                        continue

                    # 从字节读取图像
                    import io
                    import numpy as np
                    from PIL import Image

                    image = Image.open(io.BytesIO(image_bytes))

                    # 转换为 RGB（如果需要）
                    if image.mode != "RGB":
                        image = image.convert("RGB")

                    # 保存原始尺寸（用于坐标转换）
                    original_width = image.width
                    original_height = image.height

                    # 如果图像过大，缩小以提高性能
                    max_dimension = 2000
                    if max(image.width, image.height) > max_dimension:
                        scale = max_dimension / max(image.width, image.height)
                        new_size = (int(image.width * scale), int(image.height * scale))
                        image = image.resize(new_size, Image.Resampling.LANCZOS)

                    # 转换为 numpy 数组（EasyOCR 需要）
                    image_array = np.array(image)

                    # 执行 OCR
                    with self.ocr_lock:
                        ocr_output = self.ocr_reader.readtext(
                            image_array,
                            detail=1,
                            paragraph=False,
                            min_size=10,  # 最小文本框大小
                        )

                    # 处理 OCR 结果
                    for detection in ocr_output:
                        bbox_in_image, text, confidence = detection

                        # 过滤低置信度结果
                        if confidence < 0.2:
                            continue

                        # 将图像内坐标转换为页面坐标
                        # bbox_in_image: [[x0, y0], [x1, y1], [x2, y2], [x3, y3]]
                        # 如果图像被缩放过，需要按比例还原坐标
                        img_width = image.width  # 当前（可能缩放后的）尺寸
                        img_height = image.height

                        # 计算文本框在图像中的相对位置
                        x0_rel = min(point[0] for point in bbox_in_image) / img_width
                        y0_rel = min(point[1] for point in bbox_in_image) / img_height
                        x1_rel = max(point[0] for point in bbox_in_image) / img_width
                        y1_rel = max(point[1] for point in bbox_in_image) / img_height

                        # 转换为页面坐标
                        page_x0 = image_bbox.x0 + x0_rel * image_bbox.width
                        page_y0 = image_bbox.y0 + y0_rel * image_bbox.height
                        page_x1 = image_bbox.x0 + x1_rel * image_bbox.width
                        page_y1 = image_bbox.y0 + y1_rel * image_bbox.height

                        ocr_results.append({
                            "text": text.strip(),
                            "bbox": [page_x0, page_y0, page_x1, page_y1],
                            "confidence": float(confidence)
                        })

                except Exception as e:
                    print(f"处理图像 {img_index} 时出错: {e}")
                    continue

            # 保存到缓存
            self.save_ocr_result(file_path, page_no, ocr_results)

            return ocr_results

        except Exception as e:
            print(f"OCR 识别页面 {page_no + 1} 时出错: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            if doc:
                doc.close()


    def modified_get_text(self, original_method, page_instance, *args, **kwargs):
        """
        重载后的 get_text 方法，整合 OCR 结果。
        """
        # 调用原始方法获取文本（需要传递 page_instance 作为 self）
        original_text = original_method(page_instance, *args, **kwargs)

        # 如果插件未启用，直接返回原始文本
        if not self._able:
            return original_text

        try:
            # 获取页面信息
            doc = page_instance.parent
            page_no = page_instance.number

            # 尝试获取文件路径
            file_path = getattr(doc, "name", None)
            if not file_path:
                return original_text

            # 获取 OCR 结果
            ocr_results = self.get_cached_ocr_result(file_path, page_no)

            # 如果没有缓存且自动 OCR 开启，添加到队列
            if ocr_results is None and self.auto_ocr_enabled:
                self.add_to_ocr_queue(file_path, page_no, priority=1)
                return original_text

            # 如果没有 OCR 结果，返回原始文本
            if not ocr_results:
                return original_text

            # 获取格式参数
            text_format = args[0] if args else "text"
            clip = kwargs.get("clip", None)

            # 根据格式整合 OCR 结果
            if text_format in ("text", "TEXT"):
                # 纯文本格式
                ocr_text_parts = []
                for result in ocr_results:
                    # 如果指定了裁剪区域，检查文本是否在区域内
                    if clip:
                        bbox = fitz.Rect(result["bbox"])
                        if not bbox.intersects(clip):
                            continue
                    ocr_text_parts.append(result["text"])

                if ocr_text_parts:
                    ocr_text = "\n".join(ocr_text_parts)
                    # 在原始文本后添加 OCR 文本
                    if original_text and not original_text.endswith("\n"):
                        original_text += "\n"
                    return original_text + ocr_text

            elif text_format in ("dict", "json", "rawdict", "rawjson"):
                # 字典/JSON 格式 - 添加 OCR 块到 blocks 列表
                import json
                if isinstance(original_text, dict):
                    result_dict = original_text
                else:
                    try:
                        result_dict = json.loads(original_text)
                    except:
                        result_dict = {"blocks": []}

                # 为每个 OCR 结果创建一个 block
                blocks = result_dict.get("blocks", [])
                for ocr_item in ocr_results:
                    # 如果指定了裁剪区域，检查是否在区域内
                    if clip:
                        bbox = fitz.Rect(ocr_item["bbox"])
                        if not bbox.intersects(clip):
                            continue

                    # 构造符合 PyMuPDF 格式的 block
                    block = {
                        "type": 0,  # 文本块
                        "bbox": ocr_item["bbox"],
                        "lines": [{
                            "spans": [{
                                "text": ocr_item["text"],
                                "bbox": ocr_item["bbox"],
                                "origin": (ocr_item["bbox"][0], ocr_item["bbox"][3]),
                                "flags": 0,
                                "font": "OCR",
                                "size": 10,
                            }],
                            "bbox": ocr_item["bbox"],
                            "wmode": 0,
                            "dir": (1, 0),
                        }],
                    }
                    blocks.append(block)

                result_dict["blocks"] = blocks

                if text_format in ("json", "rawjson"):
                    return json.dumps(result_dict, ensure_ascii=False)
                else:
                    return result_dict

            return original_text

        except Exception as e:
            print(f"整合 OCR 结果时出错: {e}")
            return original_text


    def add_to_ocr_queue(self, file_path: str, page_no: int, priority: int = 2) -> None:
        """
        添加页面到 OCR 队列。

        Args:
            file_path: 文件路径
            page_no: 页码
            priority: 优先级 (0=最高[当前页], 1=高[可见页], 2=普通[可选择页])
        """
        task = (priority, file_path, page_no)

        # 检查是否已存在（忽略优先级）
        for i, (p, f, pn) in enumerate(self.ocr_queue):
            if f == file_path and pn == page_no:
                # 如果新优先级更高，更新优先级并移动位置
                if priority < p:
                    self.ocr_queue.pop(i)
                    break
                else:
                    return

        # 按优先级插入（优先级数字越小越优先）
        inserted = False
        for i, (p, _, _) in enumerate(self.ocr_queue):
            if priority < p:
                self.ocr_queue.insert(i, task)
                inserted = True
                break

        if not inserted:
            self.ocr_queue.append(task)


    def ocr_worker(self) -> None:
        """
        OCR 工作线程，处理队列中的识别任务。
        """
        import time
        while not self.stop_ocr_thread:
            if self.ocr_queue:
                priority, file_path, page_no = self.ocr_queue.pop(0)
                print(f"正在识别 (优先级 {priority}): {file_path} 第 {page_no + 1} 页")
                self.perform_ocr_on_page(file_path, page_no)
            else:
                # 队列为空，休眠一会
                time.sleep(0.5)


    def start_ocr_thread(self) -> None:
        """
        启动 OCR 工作线程。
        """
        if self.ocr_thread is None or not self.ocr_thread.is_alive():
            self.stop_ocr_thread = False
            self.ocr_thread = threading.Thread(target=self.ocr_worker, daemon=True)
            self.ocr_thread.start()


    def stop_ocr_worker(self) -> None:
        """
        停止 OCR 工作线程。
        """
        self.stop_ocr_thread = True
        if self.ocr_thread:
            self.ocr_thread.join(timeout=2)


    def toggle_auto_ocr(self) -> None:
        """
        切换自动 OCR 开关。
        """
        self.auto_ocr_enabled = not self.auto_ocr_enabled

        if self.auto_ocr_enabled:
            print("已开启自动 OCR")
            self.start_ocr_thread()
            # 触发当前可见页面的识别
            self.trigger_visible_pages_ocr()
        else:
            print("已关闭自动 OCR")
            self.stop_ocr_worker()


    def trigger_visible_pages_ocr(self) -> None:
        """
        触发当前可见页面和可选择页面的 OCR 识别。
        优先级：当前页面(0) > 可见页面(1) > 可选择页面(2)
        """
        current_tab = self.context.get_current_tab()
        if not current_tab or not current_tab.doc:
            return

        file_path = current_tab.file_path

        # 最高优先级：当前页面
        current_page = current_tab.page_no
        self.add_to_ocr_queue(file_path, current_page, priority=0)

        # 高优先级：可见页面
        for page, _, _ in current_tab.visible_page_positions:
            if page.number != current_page:
                self.add_to_ocr_queue(file_path, page.number, priority=1)

        # 普通优先级：可选择页面
        for page, _ in current_tab.selectable_page_positions:
            if page.number != current_page:
                self.add_to_ocr_queue(file_path, page.number, priority=2)


    def reocr_current_page(self) -> None:
        """
        重新识别当前页面。
        """
        current_tab = self.context.get_current_tab()
        if not current_tab or not current_tab.doc:
            from tkinter import messagebox
            messagebox.showwarning("提示", "请先打开一个文档")
            return

        file_path = current_tab.file_path
        page_no = current_tab.page_no

        # 清除缓存
        ocr_cache = self.context.data.setdefault("ocr_cache", {})
        cache_key = self.get_ocr_cache_key(file_path, page_no)
        if cache_key in ocr_cache:
            del ocr_cache[cache_key]

        # 重新识别
        print(f"重新识别第 {page_no + 1} 页...")
        result = self.perform_ocr_on_page(file_path, page_no)

        from tkinter import messagebox
        messagebox.showinfo("完成", f"识别完成，找到 {len(result)} 个文本块")


    def periodic_check(self) -> None:
        """
        周期性检查函数，检测页面变化并触发 OCR。
        """
        if not self.auto_ocr_enabled:
            return

        try:
            current_tab = self.context.get_current_tab()
            if not current_tab or not current_tab.doc:
                self.last_checked_page = None
                return

            current_page_key = (current_tab.file_path, current_tab.page_no)

            # 检测页面是否变化
            if self.last_checked_page != current_page_key:
                self.last_checked_page = current_page_key
                self.trigger_visible_pages_ocr()
        except Exception as e:
            print(f"OCR 周期性检查出错: {e}")


    def on_page_change(self, event=None) -> None:
        """
        页面切换时的回调函数，触发可见页面的 OCR。
        """
        if self.auto_ocr_enabled:
            self.trigger_visible_pages_ocr()


    @override
    def loaded(self) -> None:
        """
        插件加载时执行：注册菜单项并重载 get_text 方法。
        """
        # 添加菜单项
        self.context.add_menu_command(
            path=["工具", "OCR"],
            label="开启/关闭自动OCR",
            command=self.toggle_auto_ocr,
            accelerator="Ctrl+Shift+O"
        )

        self.context.add_menu_command(
            path=["工具", "OCR"],
            label="重新识别当前页",
            command=self.reocr_current_page
        )

        # 重载 Page.get_text 方法
        if self.original_get_text is None:
            self.original_get_text = fitz.Page.get_text

            # 创建闭包保存 self 引用
            plugin_self = self

            def new_get_text(page_instance, *args, **kwargs):
                return plugin_self.modified_get_text(
                    plugin_self.original_get_text,
                    page_instance,
                    *args,
                    **kwargs
                )

            fitz.Page.get_text = new_get_text


    @override
    def run(self) -> None:
        """
        快捷键触发时执行：切换自动 OCR。
        """
        self.toggle_auto_ocr()


    @override
    def unloaded(self) -> None:
        """
        插件卸载时执行：恢复原始 get_text 方法并停止工作线程。
        """
        # 停止 OCR 线程
        self.stop_ocr_worker()

        # 恢复原始方法
        if self.original_get_text is not None:
            fitz.Page.get_text = self.original_get_text
