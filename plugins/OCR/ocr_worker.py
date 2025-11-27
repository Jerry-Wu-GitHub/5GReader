# ./plugins/OCR/ocr_worker.py
import easyocr
import numpy as np
from typing import List, Tuple


# 每个进程独立的全局 Reader 实例
_process_reader = None


def init_worker():
    """初始化函数，每个进程只执行一次"""
    import os
    pid = os.getpid()
    global _process_reader

    try:
        _process_reader = easyocr.Reader(['ch_sim', 'en'], gpu=True)
        print(f"[PID {pid}] ✅ GPU 模式初始化成功")
    except Exception as e:
        print(f"[PID {pid}] ⚠️ GPU 失败: {e}，切换到 CPU")
        _process_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        print(f"[PID {pid}] ✅ CPU 模式初始化成功")


def readtext(
    img_array: np.ndarray,
    detail=1,
    paragraph=False,
    min_size=10
) -> List[Tuple]:
    """OCR 提取函数，直接使用子进程的全局 reader"""
    global _process_reader
    return _process_reader.readtext(
        img_array,
        detail=detail,
        paragraph=paragraph,
        min_size=min_size
    )
