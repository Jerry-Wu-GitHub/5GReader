# 5GReader

<img src="./static/icon/GR.png" alt="icon" style="height:256px;" />

---

## 简介

5GReader 是一款可高度个性化的电子书阅读器。

- **G**eek ：本项目支持便捷的修改和自定义。
- **G**lueous ：可以像胶水（glue）一样将各种插件粘合在一起。
- **G**raceful ：用户能高雅地解决问题。<img src="https://inews.gtimg.com/om_bt/OocRNGFIBPxalHupyX96S01pqgXewuvFoOWhZJhi5CzkIAA/0" alt="高雅人士" style="height:48px;" />
- **G**emini ：请输入文本。
- **G**itHub ：本项目在 GitHub 上协作完成。

主要使用 Python 语言进行开发。

底层调用了 Python 的扩展库 PyMuPDF 来实现电子书文件的读取和渲染。PyMuPDF 支持以下文件格式：

- **PDF** - Adobe Portable Document Format
- **XPS** - Open XML Paper Specification
- **EPUB** - Electronic Publication
- **CBZ** - Comic Book Archive
- **FB2** - Fiction - FictionBook 2.0
- **MOBI** - Mobipocket eBook

前端（UI界面）使用 Python 的标准库 Tkinter 进行开发。目前窗口分为三部分：

1. 顶层的菜单栏。
2. 中间的工具栏。
3. 下面的标签页。

---

## 项目层次图

```mermaid
graph
	classDef Plugin stroke:#6090b8,stroke-width:4px;
	
	subgraph "glueous: <code>module</code>"
		reader[reader: <code>Reader</code>]
		access[access: <code>ReaderAccess</code>]
		plugin_manager[plugin_manager: <code>PluginManager</code>]
	end
	
	subgraph "glueous_plugin: <code>module</code>"
		Plugin(<code>Plugin</code>)
	end
	
	subgraph plugins
		plugin1(plugin1: <code>Plugin1</code>)
		plugin2(plugin2: <code>Plugin2</code>)
	end
	class plugins Plugin
	
	plugin1 -.->|inherit| Plugin
	plugin2 -.->|inherit| Plugin
	
	reader -->|comb| plugin_manager
	plugin_manager -->|control| plugin1
	plugin_manager -->|control| plugin2
	
	reader <-->|comb| access

	access <-->|self.context| plugin1
	access <-->|self.context| plugin2
```

---

## 插件

### 编写语言

Python 是最推荐的用于编写插件的语言。如果你不会 Python ，但还是想开发一些高级自定义功能，依然可以使用你熟悉的语言进行开发（不推荐）。例如：

**C/C++**

- 简单函数：用 `ctypes` 加载 `.so`/`.dll`
- **C++ 类/复杂库**：**强烈推荐** `pybind11`（直接用 `ctypes` 会因 name mangling 和内存管理导致极高成本）

**Java**

- 使用 `JPype` 或 `Py4J`

你可以用你熟悉的语言将主要函数写好，然后用 Python 仅实现 Glueous Reader 的插件接口及对你的函数的调用。

实在不会的话，你可以运行 [`/整合项目03.py`](/整合项目03.py) ，这会在当前工作目录下生成一份文件 `project.md` ，其中包含了整个项目的所有代码，然后喂给 AI 。

### 开发

插件代码文件一律放在 [`/plugins`](/plugins) 文件夹（及其子目录）下，你可以在那里查看学习已有的插件。

插件类需要继承 [`glueous_plugin`](/glueous_plugin) 库中的 [`Plugin`](/glueous_plugin/Plugin.py) 抽象类（你需要先阅读 `Plugin` 类的代码！），需要实现以下方法：

- `loaded` ：在程序启动时被调用一次。
- `run` ：每当插件快捷键被触发时被调用。
- `unloaded` ：在程序退出时被调用一次。

例如，见 [`example.py`](/plugins/example.py) ：

```python
"""
显示当前页码信息插件
"""

from tkinter import messagebox
from glueous_plugin import Plugin


# 继承 Plugin
class ShowPageInfoPlugin(Plugin):
    """
    显示当前页码和总页数的简单插件
    """

    # 插件唯一标识
    name = "ShowPageInfoPlugin"

    # 插件描述
    description = """
# ShowPageInfoPlugin

- name: ShowPageInfoPlugin
- author: Glueous Reader
- hotkeys: `Ctrl+I`
- menu entrance: `工具 → 显示页码信息`

## Function

Display the current page number and total number of pages for the current tab.

If no files are opened, a warning prompt will pop up.

## Api

None

## Depend

Python extension library: None

Other plugins:
- TabPlugin

## Others

Page number calculation: 'Tab.page_no' is a 0-based index, displayed with+1.
"""

    # 快捷键绑定（格式同 Tkinter）
    hotkeys = ["<Control-i>"]

    def loaded(self) -> None:
        """
        插件加载时执行：注册菜单项
        """
        self.context.add_menu_command(
            path = ["工具"],           # 菜单路径
            label = "显示页码信息",     # 菜单项名称
            command = self.run,        # 点击时执行的函数
            accelerator = "Ctrl+I"     # 显示快捷键提示
        )


    def run(self) -> None:
        """
        插件主逻辑：获取并显示当前页码信息
        """
        # 通过 context 获取当前标签页
        current_tab = self.context.get_current_tab()

        if current_tab is None:
            # 没有打开的文件
            messagebox.showwarning("提示", "请先打开一个PDF文件")
            return

        # 获取页码信息（注意：Tab 类中页码是 0-based 的）
        current_page = current_tab.page_no + 1
        total_pages = current_tab.total_pages

        # 显示信息
        messagebox.showinfo(
            "页码信息",
            f"当前页码: {current_page}\n总页数: {total_pages}"
        )


    def unloaded(self) -> None:
        """
        插件卸载时执行（清理资源）
        """
        # 这个简单插件无需清理
        pass
```

在实例化你的插件类时，会向构造函数传入一个 [`ReaderAccess`](/glueous_plugin/ReaderAccess.py) 对象，它将作为你的插件访问整个阅读器程序的接口。主要功能如下：

- 向菜单栏添加选项。
- 向工具栏添加组件。
- 绑定快捷键。
- 数据持久化。

具体 api 可以见 [`/glueous/ReaderAccess.py`](/glueous/ReaderAccess.py) 。

你的插件可以为这个 `ReaderAccess` 对象添加新的属性/方法，这样别的插件就可以访问你定义的变量/函数了。

为了让其他开发者不用阅读源码就能了解这个插件的功能及其提供的额外接口，你需要按照以下格式编写插件的帮助文档，并赋值给该插件类的 `description` 属性：

```markdown
# PluginName

- name: PluginName
- author: Your Name
- hotkeys: None
- menu entrance: None

## Function

Write a description of the plugin's functionality here.

## Api

The additional properties and methods provided by your plugin for the ReaderAccess object.

## Depend

Python extension library:
- additional Python extension libraries that your plugin depends on

Other plugins:
- other plugins that your plugin depends on

## Others

other things you would like other developers to know...
```

如果你的插件发生了异常，程序不会崩溃，你的插件运行会结束，在标准输出会显示报错信息。

插件开发完成后，请在 [`/plugins/__init__.py`](/plugins/__init__.py) 中更新插件加载顺序。

### 注意

- 快捷键冲突：如果你的插件跟已有插件的快捷键一样，会触发后加载的插件。
- 插件加载顺序：如果在你的插件的 `loaded` 方法中需要访问 `ReaderAccess` 对象的 `member` 成员，而定义该成员的插件在你的插件之后才被加载，那么你的插件的 `loaded` 方法将会报错并中断执行。为避免此类情况的发生，请在 [`/plugins/__init__.py`](/plugins/__init__.py) 中更新插件加载顺序。
- 不要直接修改已有插件的代码文件（注释除外）。如需给已有类添加功能，请使用 `types.MethodType` 或 `property` 来动态添加。
- [编程规范](编程规范.md) 

---

## 快速开始

1. 安装 Python ≥3.8。

2. 安装 [`/requirements.txt`](/requirements.txt) 中的扩展库：

    ```console
    pip install -r path/to/your/project/requirements.txt
    ```

3. 运行 [`/main.py`](/main.py) 。

---

## 注意

> [!WARNING]
>
> **项目早期声明**：由于本项目才刚刚建立，还有很多不完善的地方，比如，接口可能会改，无法向后兼容等等。感谢各位的理解！