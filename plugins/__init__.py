"""
A folder used to store plugins.
"""
from typing import List

# 插件加载顺序
plugin_loading_order: List[str] = [
    # 基础插件
    "ContextMenuPlugin",
    "TabPlugin",
    "CanvasFadeBoxPlugin",

    # 文件
    "OpenPlugin",
    "ClosePlugin",

    # 翻页
    "PageUpPlugin",
    "PageNoPlugin",
    "PageDownPlugin",

    # 缩放
    "ZoomPlugin",
    "ZoomOutPlugin",
    "ZoomInPlugin",

    # 滚动
    "ScrollPlugin",
    "HorizontalScrollPlugin",
    "VerticalScrollUpPlugin",
    "HorizontalScrollLeftPlugin",
    "HorizontalScrollRightPlugin",

    # 选择
    "SelectPlugin",
    "DragPlugin",
    "CopyPlugin",
    "TranslatePlugin",
    "SearchPlugin",
    "HighLightPlugin",

    # AI
    "OCRPlugin",
    "OCRDebugPlugin",
    "AIConfigurePlugin",
    "SummaryPlugin",
    "MindMapPlugin",
]
