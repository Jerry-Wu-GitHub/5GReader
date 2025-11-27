from __future__ import annotations

from pathlib import Path
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, Menu
from typing import Any, Callable, Dict, List
from types import ModuleType

from .ReaderAccess  import ReaderAccess
from .PluginManager import PluginManager



def construct_menu(menu: tk.Menu, menu_structure: List[Dict[str, Any]]) -> None:
    """
    从菜单的字典结构 `menu_structure` 为菜单组件 `menu` 添加内容。

    Params:

    - `menu_structure`: 菜单的字典结构，like:

        ```python
        [
            {
                "type" : "menu",
                "label" : "文件",
                "children": [
                    {
                        "type" : "command",
                        "label" : "新建",
                        "command" : create_new,
                        "accelerator": "Ctrl+N",
                    },
                    {
                        "type" : "separator",
                    },
                    {
                        "type" : "menu",
                        "label" : "打开",
                        "children": [
                            {
                                "type" : "command",
                                "label" : "PDF 文件",
                                "command" : open_pdf,
                                "accelerator": "Ctrl+O",
                            },
                        ],
                    }
                ],
            }
        ]
        ```
    
    Return:

    - tkinter.Menu
    """

    for sublabel in menu_structure:
        if sublabel["type"] == "separator":
            menu.add_separator()
        elif sublabel["type"] == "command":
            menu.add_command(**{k: v for (k, v) in sublabel.items() if (k != "type")})
        elif sublabel["type"] == "menu":
            submenu = tk.Menu(menu, **{k: v for (k, v) in sublabel.items() if (k not in ("type", "children", "label"))})
            construct_menu(submenu, sublabel["children"]) # 递归构造子菜单项
            menu.add_cascade(label = sublabel["label"], menu=submenu)



class Reader:
    """
    主程序类，管理多标签页和全局状态。
    """

    def __init__(self, settings: Dict[str, Any]):
        self.settings: Dict[str, Any] = settings

        # 创建窗口
        self.root = tk.Tk()
        self.root.title(self.settings["window_title"])
        self.root.geometry(f"{self.settings['window_width']}x{self.settings['window_height']}")

        # 创建菜单栏
        self.menubar = tk.Menu(self.root)
        self.menu_structure: List[Dict[str, Any]] = []
        """
        Like:
            [
                {
                    "type"    : "menu",
                    "label"   : "example",
                    "children": [
                        {
                            "type"    : "command"
                            "label"   : "run",
                            "command" : Function,
                        }
                    ],
                }
            ]
        """
        self.update_menubar()
        self.root.config(menu = self.menubar)

        # 创建工具栏
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(side = tk.TOP, fill = tk.X, padx = 5, pady = 5)

        # 创建标签页容器
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 加载数据文件 data.json
        # 插件可以使用 `data` 中的信息恢复上次打开的文件和状态
        self.data: Dict[str, Any] = {}
        try:
            with open(self.settings["data_path"], mode = "r", encoding = self.settings["encoding"]) as file:
                self.data = json.load(file)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"读取数据文件时出错: {e}")

        # 在整个 mainloop 中要周期性执行的函数
        # 每一条的格式： [函数, [参数1, 参数2, ...]]
        self.periodically_executed_functions: List[[Callable, List[Any]]] = [
            [self.dump_data, []],
        ]

        # 在每次标签页切换时要执行的函数
        self.at_notebook_tab_changed_functions: List[[Callable, List[Any]]] = []

        self.access = ReaderAccess(self)
        self.plugin_manager = PluginManager(self.access)
        self.plugin_manager.load_plugins_from_directory(Path(self.settings["plugin_directory_path"]))
        self.plugin_manager.bind_hotkeys()
        self.root.after(0, self.plugin_manager.loaded)


    def update_menubar(self) -> None:
        """
        根据 self.menu_structure 更新 self.menubar
        """
        self.menubar.delete(0, tk.END)
        construct_menu(self.menubar, self.menu_structure)


    def dump_data(self) -> None:
        """
        导出数据文件 data.json。
        """

        # 写入数据文件
        try:
            with open(self.settings["data_path"], mode = "w", encoding = self.settings["encoding"]) as file:
                json.dump(self.data, file, indent = 4, ensure_ascii = False)
        except Exception as e:
            print(f"写入数据文件时出错: {e}")


    def periodically_execute(self) -> None:
        """
        执行在整个 mainloop 中要周期性执行的函数。
        """
        for (function, args) in self.periodically_executed_functions:
            # try:
            function(*args)
            # except Exception as error:
            #     print(f"in reader.periodically_execute: {function.__name__}: {error.__class__.__name__}: {error}")

        # 每隔一定时间再次执行
        self.root.after(self.settings["frequency"], self.periodically_execute)


    def at_notebook_tab_changed(self, event) -> None:
        for (function, args) in self.at_notebook_tab_changed_functions:
            try:
                function(event, *args)
            except Exception as error:
                print(f"in reader.at_notebook_tab_changed: {function.__name__}: {error.__class__.__name__}: {error}")


    def mainloop(self) -> None:
        """
        进入主循环。
        """
        self.periodically_execute()
        self.notebook.bind("<<NotebookTabChanged>>", self.at_notebook_tab_changed)
        self.root.mainloop()
