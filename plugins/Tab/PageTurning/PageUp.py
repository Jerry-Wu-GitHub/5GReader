"""
上一页。
"""

from tkinter import ttk
from typing import override

from glueous_plugin import Plugin


class PageUpPlugin(Plugin):
    """
    上一页插件：允许用户通过快捷键或菜单项切换到上一页。
    """

    # 插件信息
    name = "PageUpPlugin"
    description = """
# PageUpPlugin

- name: PageUpPlugin
- author: Jerry
- hotkeys: `PageUp`
- menu entrance: `前往 → 上一页`

## Function

Switch to the previous page.

When the first page is reached, a prompt message "已经是第一页" will be displayed in the console.

## Api

- `context.get_prev_button()`: Get the 'Previous Page' button component.

## Depend

Python extension library: None

Other plugins:
- TabPlugin
- PageNoPlugin

## Others

Page number calculation: 'Tab.page_no' is a 0-based index.
"""

    # 快捷键设置
    hotkeys = ["<Prior>"]  # 对应 PageUp 键


    @override
    def loaded(self) -> None:
        """
        注册菜单项、快捷键、“上一页”按钮。
        """
        # 注册菜单项、快捷键
        self.context.add_menu_command(
            path = ["前往"],
            label = "上一页",
            command = self.run,
            accelerator = self.hotkey
        )

        # “上一页”按钮
        prev_btn = self.context.add_tool(
            ttk.Button,
            kwargs = {
                "text": "←",
                "command": self.run,
                "width": 3,
            }
        )

        # 将这个按钮组件添加到 context 中，以便其他插件访问
        self.context.get_prev_button = lambda: prev_btn


    @override
    def run(self) -> None:
        """
        执行上一页操作。
        【修复】重写逻辑以支持双页/书籍模式。
        """
        current_tab = self.context.get_current_tab()
        if current_tab is None:
            return

        try:
            # 获取所有页面的矩形
            all_page_rects = current_tab.selectable_page_positions
            if not all_page_rects:
                return

            # 获取当前视口的垂直位置
            # canvas.yview() 返回 (起始比例, 结束比例)
            scroll_start_y = current_tab.canvas.yview()[0] * current_tab.canvas_height
            
            # 找到当前视口顶部边缘或之上的第一个页面
            # 我们从当前页码开始向前搜索，这样更高效
            first_visible_page_index = -1
            for i in range(current_tab.page_no, -1, -1):
                _, rect = all_page_rects[i]
                # 如果页面的底部在视口顶部之上或附近，它就是可见的第一个
                if rect.y1 >= scroll_start_y:
                    first_visible_page_index = i
                else:
                    # 一旦找到完全在视口上方的页面，就停止搜索
                    break
            
            if first_visible_page_index == -1:
                first_visible_page_index = 0

            # 目标是找到一个完全在 first_visible_page_index 上方的页面
            target_page_index = -1
            # 获取当前可见行的顶部y坐标
            first_visible_rect_y0 = all_page_rects[first_visible_page_index][1].y0

            # 从当前可见页的前一页开始，反向搜索
            for i in range(first_visible_page_index - 1, -1, -1):
                _, rect = all_page_rects[i]
                # 如果找到一个页面的顶部y坐标明显小于当前行的顶部，
                # 那么它就是上一行的页面，是我们的目标
                if rect.y0 < first_visible_rect_y0 - 1: # -1 是为了容错
                    target_page_index = i
                    break
            
            # 如果没找到（说明已经是第一行了），则直接到第0页
            if target_page_index == -1:
                target_page_index = 0

            # 如果计算出的目标页和当前页相同，并且不是第0页，说明可能卡住了，再往前找一页
            if target_page_index == current_tab.page_no and target_page_index > 0:
                 target_page_index -=1

            # 如果已经是第一页，则不执行任何操作
            if current_tab.page_no == 0 and target_page_index == 0:
                 print("已经是第一页")
                 return

            # 滚动到目标页面
            _, target_page_rect = all_page_rects[target_page_index]
            current_tab.scroll_pos = (target_page_rect.x0, target_page_rect.y0)

            # 手动更新内部页码状态和UI
            # update_view_attributes 会自动更新 page_no，但我们手动设置以确保同步
            current_tab.state["page_no"] = target_page_index
            self.context.update_page_number()
            self.context.update_page_turning_button()

        except (AttributeError, IndexError):
            # 如果发生异常（例如 ViewPlugin 未加载），则回退到原始逻辑
            if current_tab.page_no > 0:
                current_tab.page_no -= 1
            else:
                print("已经是第一页")


    @override
    def unloaded(self) -> None:
        pass
