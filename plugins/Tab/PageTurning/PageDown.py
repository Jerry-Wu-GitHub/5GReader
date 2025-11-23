"""
下一页。
"""

from tkinter import ttk
from typing import override
from types import MethodType

from glueous import ReaderAccess
from glueous_plugin import Plugin


class PageDownPlugin(Plugin):
    """
    下一页插件：允许用户通过快捷键或菜单项切换到下一页。
    """

    # 插件信息
    name = "PageDownPlugin"
    description = """
# PageDownPlugin

- name: PageDownPlugin
- author: Jerry
- hotkeys: `PageDown`
- menu entrance: `前往 → 下一页`

## Function

Switch to the next page.

When the last page is reached, a prompt message "已经是最后一页" will be displayed in the console.

## Api

- `context.get_next_button()`: Get the 'Next Page' button component.
- `context.update_page_turning_button()`: Update page switch button status.

## Depend

Python extension library: None

Other plugins:
- TabPlugin
- PageNoPlugin

## Others

Page number calculation: 'Tab.page_no' is a 0-based index.
"""

    # 快捷键设置
    hotkeys = ["<Next>"]  # 对应 PageDown 键


    @staticmethod
    def update_page_turning_button(access: ReaderAccess, event = None) -> None:
        """
        更新 prev_button 和 next_button 的启用/禁用状态。
        """
        # 获取“上一页”和“下一页”按钮
        prev_button = access.get_prev_button()
        next_button = access.get_next_button()

        current_tab = access.get_current_tab()
        if current_tab is None:
            prev_button.config(state = "disabled")
            next_button.config(state = "disabled")
            return

        # 检查当前页码并更新按钮状态
        if current_tab.page_no <= 0:
            prev_button.config(state = "disabled")
        else:
            prev_button.config(state = "normal")

        if current_tab.page_no >= current_tab.total_pages - 1:
            next_button.config(state = "disabled")
        else:
            next_button.config(state = "normal")


    @override
    def loaded(self) -> None:
        """
        注册菜单项、快捷键、“下一页”按钮。
        """
        # 注册菜单项、快捷键
        self.context.add_menu_command(
            path = ["前往"],
            label = "下一页",
            command = self.run,
            accelerator = self.hotkey
        )

        # “下一页”按钮
        next_btn = self.context.add_tool(
            ttk.Button,
            kwargs = {
                "text": "→",
                "command": self.run,
                "width": 3,
            }
        )

        # 将这个按钮组件添加到 context 中，以便其他插件访问
        self.context.get_next_button = lambda: next_btn
        self.context.update_page_turning_button = MethodType(self.update_page_turning_button, self.context)

        # 绑定标签页切换事件，以更新按钮显示
        self.context.add_at_notebook_tab_changed_function(self.context.update_page_turning_button)


    @override
    def run(self) -> bool:
        """
        执行下一页操作。
        """
        current_tab = self.context.get_current_tab()
        if current_tab is None:
            return False

        # 检查是否已经是最后一页
        if current_tab.page_no >= current_tab.total_pages - 1:
            print("已经是最后一页")
            return False

        # 计算下一页在画布上的位置
        try:
            # selectable_page_positions 是由 ViewPlugin 注入的
            # 它返回一个列表：[(page, page_rect_on_canvas), ...]
            all_page_rects = current_tab.selectable_page_positions
            
            # 获取下一页的矩形
            next_page_index = current_tab.page_no + 1
            if 0 <= next_page_index < len(all_page_rects):
                _, next_page_rect = all_page_rects[next_page_index]
                
                # 【关键】将滚动位置设置为下一页的左上角
                # 这会自动触发 update_view_region 和 render
                current_tab.scroll_pos = (next_page_rect.x0, next_page_rect.y0)
                
                # 手动更新内部页码状态和UI
                current_tab.state["page_no"] = next_page_index
                self.context.update_page_number()
                self.context.update_page_turning_button()
                return True
            else:
                # 如果找不到下一页的矩形，则回退到旧逻辑
                current_tab.page_no += 1
                return True

        except AttributeError:
            # 如果 selectable_page_positions 不存在（例如 ViewPlugin 未加载）
            # 则执行原始的翻页逻辑
            current_tab.page_no += 1
            return True


    def page_down_single(self, tab) -> bool:
        """
        对单页视图的文档进行向下翻页。

        返回是否成功翻页。
        """
        if tab.page_no >= tab.total_pages - 1:
            print("已经是最后一页")
            return False

        tab.scroll_pos = (tab.scroll_pos[0], 0)
        tab.page_no += 1
        self.context.update_page_number()
        self.context.update_page_turning_button()
        return True


    def page_down_continuous(self, tab) -> bool:
        """
        对单页视图的文档进行向下翻页。

        返回是否成功翻页。
        """
        pass


    @override
    def unloaded(self) -> None:
        pass
