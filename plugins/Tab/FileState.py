r"""
FileState 类。
"""

from __future__ import annotations

from enum import Enum
import hashlib
from typing import Any, Dict, List


class Favorite:
    """
    一条收藏记录。
    """

    def __init__(self, page_no: int, name: str = ""):
        self.page_no: int = page_no # 页码
        self.name   : str = name    # 名称


    @classmethod
    def from_json(cls, json_obj: Dict[str, Any]) -> Favorite:
        """
        从 JSON 数据构造对象。

        Params:

        - `json_obj`: JSON 对象，如：
            
            ```json
            {
                "name": "哈密顿图",
                "page_no": 104
            }
            ```

        Return:

        - 一个 Favorite 对象。
        """
        if "page_no" not in json_obj:
            raise ValueError(f"missing field `page_no` in JSON object `{json_obj}`.")
        return cls(page_no = json_obj["page_no"], name = json_obj.get("name", ""))


    def to_json(self) -> Dict[str, Any]:
        """
        将对象序列化为 JSON 对象。

        Return:

        - 一个字典，如：

            ```json
            {
                "name": "哈密顿图",
                "page_no": 104
            }
            ```
        """
        return {
            "name": self.name,
            "page_no": self.page_no
        }


class DisplayMode(Enum):
    SINGLE            = "single"
    CONTINUOUS        = "continuous"
    SINGLE_FACING     = "single facing"
    CONTINUOUS_FACING = "continuous facing"
    SINGLE_BOOK       = "single book"
    CONTINUOUS_BOOK   = "continuous book"



class FileState:
    """
    FileState 类，记录 Tab 类的状态，可以序列化为 JSON 对象来存储，用于在下次重新打开程序时能恢复到上次打开时的状态。
    """

    DISPLAY_MODES = (
        DisplayMode.SINGLE,
        DisplayMode.CONTINUOUS,
        DisplayMode.SINGLE_FACING,
        DisplayMode.CONTINUOUS_FACING,
        DisplayMode.SINGLE_BOOK,
        DisplayMode.CONTINUOUS_BOOK,
    )

    ROTATIONS = (0, 90, 180, 270)

    def __init__(self, file_path: str = ""):
        """
        默认构造方法，只要提供 `file_path` 参数。
        """
        # 绝对路径
        self.file_path: str = file_path

        # 这本书里收藏的条目
        self.favorites: List[Favorite] = []

        # “固定标签页”开关：`true` 时，关闭所有文档也不会把这本书关掉
        self.is_pinned = False

        # 文件被删或移动
        self.is_missing = False

        # 这本书累计被打开过的次数
        self.open_count = 0

        # 如果 `true`，下次打开它时会忽略下面所有个性化状态（相当于“恢复默认视图”）
        self.use_default_state = False

        # 页面布局：
        # - `single` / `continuous` / `facing` / `book`，其中 ("single", "continuous") 可与 ("", "facing", "book") 两两组合
        self.display_mode: DisplayMode = DisplayMode.SINGLE

        # 客户区左上角的滚动偏移量（单位：逻辑像素，Page 坐标）
        self.scroll_pos = (0.0, 0.0)

        # 当前“活跃页”编号（0-based）
        self.page_no = 0

        # 缩放比
        self.zoom = 1.0

        # 页面旋转角度，0/90/180/270 四选一，顺时针
        self.rotation = 0

        # 主窗体状态码：
        # - 0 = 普通/还原
        # - 1 = 最大化
        # - 2 = 最小化
        self.window_state = 0

        # 窗体几何：x y width height（单位：屏幕像素，含边框）。
        self.window_pos = (0, 0, 0, 0)

        # 左侧“目录/书签”面板是否展开。`false` 表示收起。
        self.show_toc = False

        # 如果目录或注释面板被打开，它的宽度是多少像素。
        self.sidebar_dx = 572

        # 是否按“从右到左”顺序显示对页（对阿拉伯/希伯来文 PDF 有用）。普通文档保持 `false`。
        self.display_r2l = False

        # 标记 PDF 重新解析/重载的计数
        self.reparse_idx = 0


    @classmethod
    def from_json(cls, json_obj: Dict[str, Any]) -> FileState:
        """
        从 JSON 数据构造对象。

        Params:

        - `json_obj`: JSON 对象，如：
            
            ```json
            {
                "file_path": "C:\\\\Users\\\\Administrator\\\\Documents\\\\example.pdf",
                "favorites": [
                    {
                        "name": "哈密顿图",
                        "page_no": 104
                    }
                ],
                "is_pinned": false,
                "is_missing": false,
                "open_count": 12,
                "use_default_state": false,
                "display_mode": "continuous",
                "scroll_pos": [0.0, 0.0],
                "page_no": 1,
                "zoom": 1.0,
                "rotation": 0,
                "window_state": 0,
                "window_pos": [0, 0, 0, 0],
                "show_toc": false,
                "sidebar_dx": 572,
                "display_r2l": false,
                "reparse_idx": 0
            }
            ```

        Return:

        - 一个 FileState 对象。
        """
        if "file_path" not in json_obj:
            raise ValueError(f"missing field `file_path` in JSON object `{json_obj}`.")

        instance = cls(file_path = json_obj["file_path"])

        # 基本类型字段
        instance.is_pinned          = json_obj.get("is_pinned", False)
        instance.is_missing         = json_obj.get("is_missing", False)
        instance.open_count         = json_obj.get("open_count", 0)
        instance.use_default_state  = json_obj.get("use_default_state", False)
        instance.display_mode       = DisplayMode(json_obj.get("display_mode", "single"))
        instance.page_no            = json_obj.get("page_no", 1)
        instance.zoom               = json_obj.get("zoom", 1.0)
        instance.rotation           = json_obj.get("rotation", 0)
        instance.window_state       = json_obj.get("window_state", 0)
        instance.show_toc           = json_obj.get("show_toc", False)
        instance.sidebar_dx         = json_obj.get("sidebar_dx", 572)
        instance.display_r2l        = json_obj.get("display_r2l", False)
        instance.reparse_idx        = json_obj.get("reparse_idx", 0)

        # 元组类型字段
        scroll_pos = json_obj.get("scroll_pos", [0.0, 0.0])
        instance.scroll_pos = (float(scroll_pos[0]), float(scroll_pos[1]))

        window_pos = json_obj.get("window_pos", [0, 0, 0, 0])
        instance.window_pos = (int(window_pos[0]), int(window_pos[1]), int(window_pos[2]), int(window_pos[3]))

        # 列表类型字段
        instance.favorites = [Favorite.from_json(fav) for fav in json_obj.get("favorites", [])]

        return instance


    def to_json(self) -> Dict[str, Any]:
        """
        将对象序列化为 JSON 对象。

        Return:

        - 一个字典，如：

            ```json
            {
                "file_path": "C:\\\\Users\\\\Administrator\\\\Documents\\\\example.pdf",
                "favorites": [
                    {
                        "name": "哈密顿图",
                        "page_no": 104
                    }
                ],
                "is_pinned": false,
                "is_missing": false,
                "open_count": 12,
                "use_default_state": false,
                "display_mode": "continuous",
                "scroll_pos": [0.0, 0.0],
                "page_no": 1,
                "zoom": 1.0,
                "rotation": 0,
                "window_state": 0,
                "window_pos": [0, 0, 0, 0],
                "show_toc": false,
                "sidebar_dx": 572,
                "display_r2l": false,
                "reparse_idx": 0
            }
            ```
        """
        return {
            "file_path"         : self.file_path,
            "favorites"         : [fav.to_json() for fav in self.favorites],
            "is_pinned"         : self.is_pinned,
            "is_missing"        : self.is_missing,
            "open_count"        : self.open_count,
            "use_default_state" : self.use_default_state,
            "display_mode"      : self.display_mode.value,
            "scroll_pos"        : list(self.scroll_pos),
            "page_no"           : self.page_no,
            "zoom"              : self.zoom,
            "rotation"          : self.rotation,
            "window_state"      : self.window_state,
            "window_pos"        : list(self.window_pos),
            "show_toc"          : self.show_toc,
            "sidebar_dx"        : self.sidebar_dx,
            "display_r2l"       : self.display_r2l,
            "reparse_idx"       : self.reparse_idx
        }



class FileHasher:
    """
    FileHasher 用于计算文件的哈希值，支持多种算法。
    """

    ALGORITHMS_GUARANTEED = hashlib.algorithms_guaranteed
    ALGORITHMS_AVAILABLE  = hashlib.algorithms_available
    DEFAULT_ALGORITHM = "sha256"

    def __init__(self, algorithm: str = None):
        if algorithm is None:
            algorithm = self.DEFAULT_ALGORITHM
        self._check_algorithm(algorithm)
        self._algorithm = algorithm


    @classmethod
    def _check_algorithm(cls, algorithm: str):
        if algorithm not in cls.ALGORITHMS_AVAILABLE:
            raise ValueError(f"unsupported algorithms: {algorithm}")


    @property
    def algorithm(self):
        return self._algorithm

    @algorithm.setter
    def algorithm(self, value):
        self._check_algorithm(value)
        self._algorithm = value


    def hash_file(self, filepath, chunk_size: int = 8192) -> int:
        """
        计算文件哈希值（支持多种算法）

        :param filepath: 文件路径
        :param chunk_size: 每次读取的字节数
        :return: 十六进制哈希值字符串
        """
        hash_obj = hashlib.new(self.algorithm)

        with open(filepath, 'rb') as f:
            # 分块读取并更新哈希
            while chunk := f.read(chunk_size):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()
