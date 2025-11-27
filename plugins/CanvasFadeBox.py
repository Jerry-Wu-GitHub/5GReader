import tkinter as tk
from typing import Callable, Tuple, Union, override

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageTk

from glueous_plugin import Plugin


Color = Union[str, Tuple[int, int, int]]

class CanvasFadeBox:
    """带背景框的渐变文本"""

    def __init__(
        self,
        canvas: tk.Canvas, text: str,
        x: int = None, y: int = None,
        size: int = 24, text_color: Color = "black",
        bg_color: Color = "white", padding: int = 20,
        border_color: Color = None, border_width: int = 0, radius: int = 10, # 圆角半径
        anchor: str = "center"
    ):
        self.canvas = canvas
        self.x = (canvas.winfo_width()  // 2) if (x is None) else x
        self.y = (canvas.winfo_height() // 2) if (y is None) else y
        self.text = text
        self.text_color = text_color
        self.bg_color = bg_color
        self.padding = padding
        self.border_color = border_color
        self.border_width = border_width
        self.radius = radius
        self.anchor = anchor

        # 加载字体
        self.font = self._load_font(size)

        self.image_item = None
        self._alpha = 0


    def _load_font(self, size):
        """智能加载字体（Windows/Linux/macOS 兼容）"""
        # Windows 系统
        try:
            return ImageFont.truetype("msyh.ttc", size)  # 微软雅黑
        except:
            pass

        # Windows 备用
        try:
            return ImageFont.truetype("arial.ttf", size)
        except:
            pass

        # Linux 系统
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", size)
        except:
            pass

        # macOS 系统
        try:
            return ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", size)
        except:
            pass

        # 如果都失败，使用默认字体
        return ImageFont.load_default()


    def fade_in(self, duration: int = 200, fps: int = 30):
        """淡入 duration 毫秒"""
        self._animate(0, 255, duration, fps = fps)


    def fade_out(self, duration: int = 500, fps: int = 30):
        """淡出 duration 毫秒"""
        self._animate(255, 0, duration, fps = fps)


    def _animate(self, start_alpha: float | int, end_alpha: float | int, duration: int, *, fps: int = 30):
        """
        核心动画。
        在 duration 毫秒的时间内，从透明度 start_alpha 变到 end_alpha。
        """
        self._alpha = start_alpha
        sleep_time = 1000 // fps
        steps = max(1, duration * fps // 1000)
        alpha_step = (end_alpha - start_alpha) / steps

        def update(step = 0):
            if step <= steps:
                self._alpha = int(start_alpha + alpha_step * step)
                self._update_image()
                self.canvas.after(sleep_time, update, step + 1)

        update()


    def _update_image(self):
        """生成带背景的文本图像"""
        # 计算文本尺寸
        bbox = self.font.getbbox(self.text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 计算画布尺寸（加上内边距）
        box_width = text_width + self.padding * 2
        box_height = text_height + self.padding * 2

        # 创建透明图像
        image = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # 背景色
        if self.bg_color:
            bg_rgb = ImageColor.getrgb(self.bg_color)
            bg_rgba = bg_rgb + (self._alpha,)

            # 绘制圆角矩形背景
            if self.radius > 0:
                self._draw_rounded_rectangle(draw, 0, 0, box_width, box_height,
                                          self.radius, fill=bg_rgba)
            else:
                draw.rectangle([0, 0, box_width, box_height], fill=bg_rgba)

        # 边框
        if self.border_color and self.border_width > 0:
            border_rgb = ImageColor.getrgb(self.border_color)
            border_rgba = border_rgb + (self._alpha,)

            if self.radius > 0:
                self._draw_rounded_rectangle(draw, 0, 0, box_width, box_height,
                                          self.radius, outline=border_rgba, width=self.border_width)
            else:
                draw.rectangle([0, 0, box_width, box_height],
                             outline=border_rgba, width=self.border_width)

        # 文字（居中）
        text_rgb = ImageColor.getrgb(self.text_color)
        text_rgba = text_rgb + (self._alpha,)

        # 计算文字位置（相对于左上角）
        text_x = self.padding - bbox[0]  # 修正字体bbox偏移
        text_y = self.padding - bbox[1]

        draw.text((text_x, text_y), self.text, font=self.font, fill=text_rgba)

        # 转换为tkinter图像
        self.tk_image = ImageTk.PhotoImage(image)

        # 更新Canvas（居中显示）
        if self.image_item:
            self.canvas.itemconfig(self.image_item, image=self.tk_image)
        else:
            self.image_item = self.canvas.create_image(
                self.x, self.y,
                image = self.tk_image,
                anchor = self.anchor
            )

        # 防止垃圾回收
        self.canvas.image_ref = self.tk_image


    def _draw_rounded_rectangle(self, draw, x1, y1, x2, y2, radius, **kwargs):
        """绘制圆角矩形"""
        # points = [
        #     x1 + radius, y1,
        #     x2 - radius, y1,
        #     x2, y1,
        #     x2, y1 + radius,
        #     x2, y2 - radius,
        #     x2, y2,
        #     x2 - radius, y2,
        #     x1 + radius, y2,
        #     x1, y2,
        #     x1, y2 - radius,
        #     x1, y1 + radius,
        #     x1, y1
        # ]
        draw.rounded_rectangle([x1, y1, x2, y2], radius = radius, **kwargs)


    def animate(self, fade_in_time: int = 200, hold_time: int = 2000, fade_out_time: int = 500, *, fps: int = 30):
        self.fade_in(fade_in_time, fps = fps)
        self.canvas.after(hold_time, lambda: self.fade_out(fade_out_time, fps = fps))



class CanvasFadeBoxPlugin(Plugin):
    name = "CanvasFadeBoxPlugin"

    description = """
# CanvasFadeBoxPlugin

- name: CanvasFadeBoxPlugin
- author: Jerry
- hotkeys: None
- menu entrance: None

## Function

Display messages on the canvas with fade-in and fade-out effects.

Provides a `print` API for other plugins to display messages on the canvas.

## Api

- `context.print(text, ...)`: Display a message on the canvas with fade-in and fade-out effects.

## Depend

Python extension library:
- PIL (Pillow)

Other plugins:
- TabPlugin

## Others

The message will be displayed at the bottom center of the canvas by default.
"""

    def print(
        self,
        text: str,
        fade_in_time: int = 100, hold_time: int = 2000, fade_out_time: int = 500,
        with_console: bool = True,
        *,
        x: int = None, y: int = None,
        size: int = None, text_color: Color = "black",
        bg_color: Color = "white", padding: int = None,
        border_color: Color = None, border_width: int = 0, radius: int = None,
        anchor: str = "center",
        fps: int = 30
    ):
        """
        在当前画布上打印一条信息。支持渐入、渐出等效果。
        """
        current_tab = self.context.get_current_tab()
        canvas = current_tab.canvas

        x_view_start, x_view_end = canvas.xview()
        y_view_start, y_view_end = canvas.yview()
        start_x_pos = current_tab.canvas_width  * x_view_start
        end_x_pos   = max(current_tab.canvas_width  * x_view_end, canvas.winfo_width())
        start_y_pos = current_tab.canvas_height * y_view_start
        end_y_pos   = max(current_tab.canvas_height * y_view_end, canvas.winfo_height())
        if x is None:
            x = int(start_x_pos + end_x_pos) // 2
        if y is None:
            y = int(start_y_pos + (end_y_pos - start_y_pos) * 0.9)

        if size is None:
            size = int(min(end_x_pos - start_x_pos, end_y_pos - start_y_pos) / 32)
        if padding is None:
            padding = size // 2
        if radius is None:
            radius = padding // 2

        if with_console:
            print(text)

        CanvasFadeBox(
            canvas = canvas, text = text,
            x = x, y = y,
            size = size, text_color = text_color,
            bg_color = bg_color, padding = padding,
            border_color = border_color, border_width = border_width,
            radius = radius,
            anchor = anchor,
        ).animate(fade_in_time, hold_time, fade_out_time, fps = fps)


    @override
    def loaded(self):
        """
        提供api
        """
        self.context.CanvasFadeBox = CanvasFadeBox
        self.context.print = self.print


    @override
    def run(self):
        pass


    @override
    def unloaded(self):
        pass
