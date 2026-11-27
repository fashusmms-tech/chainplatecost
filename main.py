# -*- coding: utf-8 -*-
"""金属链板成本计算器 — 手机版 (Kivy / Android)  v1.2

v1.2 只重做界面层：深色工业风、分区卡片、分段胶囊、开关、吸底计算条、
结果页独立 + 成本结构环形图。

计算口径与公式一行未动（tests/golden.py 锁死 118 组用例）。
界面控件对外暴露的名字（acc_rows / pitch_btns / sp_plate / in_width …）保持不变，
所以 tests/ui_smoke.py 与设置页的变量对照都能照常工作。
"""
import json
import os
import time
import weakref

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
try:
    from kivy.utils import platform
except Exception:  # kvshim 等替身环境里没有 kivy.utils
    platform = ""

from chainplate_calc import (MATERIAL_NAMES, PITCHES, SAMPLE_ENV, VAR_NAMES,
                             chain_width_of, compute, default_settings,
                             eval_expr, format_result, formula_vars,
                             load_settings, save_settings)

APP_VERSION = "1.3.1"

MATERIAL_KEY = {name: key for key, name in MATERIAL_NAMES.items()}
MATERIAL_LIST = list(MATERIAL_NAMES.values())

# ---------------- 中文字体 ----------------
_DIR = os.path.dirname(os.path.abspath(__file__))
_FONT = next((os.path.join(_DIR, p) for p in ("fonts/simhei.ttf", "simhei.ttf")
              if os.path.exists(os.path.join(_DIR, p))), "")
try:
    LabelBase.register(name="CJK", fn_regular=_FONT)
    LabelBase.register(name="Roboto", fn_regular=_FONT)
except Exception:
    pass
# below_target: 键盘弹出时把焦点控件顶到键盘上方(手机上比 pan 稳)
Window.softinput_mode = "below_target"


# ---------------- 软键盘 / 焦点 ----------------
# Android 的 IME 是异步弹出的。Kivy 2.3 在 request_keyboard 之后, 每 0.2s 用
# SDL 的"键盘是否已显示"复查一次, 没显示就 release —— 而 release 会顺带清掉焦点。
# IME 弹出动画还没走完时就会被误判, 表现就是"点输入框完全没反应"。
# 这里给每次键盘请求留一个宽限期, 宽限期内不做这个复查。
def _patch_ime_grace(seconds=2.0):
    if platform != "android":
        return
    try:
        orig_check = Window._check_keyboard_shown
        orig_request = Window.request_keyboard
    except AttributeError:
        return
    state = {"until": 0.0}

    def _check(dt):
        if time.time() < state["until"]:
            return True
        return orig_check(dt)

    def _request(*a, **kw):
        state["until"] = time.time() + seconds
        return orig_request(*a, **kw)

    Window._check_keyboard_shown = _check
    Window.request_keyboard = _request


_patch_ime_grace()

# 同一时刻只允许一个输入框持有焦点: 否则会同时亮多个橙色描边, 键盘也不知道给谁。
_INPUTS = []


def _register_input(w):
    _INPUTS.append(weakref.ref(w))


def _defocus_others(keep):
    for ref in list(_INPUTS):
        w = ref()
        if w is None:
            try:
                _INPUTS.remove(ref)
            except ValueError:
                pass
        elif w is not keep and w.focus:
            w.focus = False

# ============================================================
# 主题 (深色工业风: 炭黑底 + 琥珀强调)
# ============================================================
BG      = (0.039, 0.051, 0.067, 1)      # #0A0D11
CARD    = (0.078, 0.102, 0.129, 1)      # #141A21
SUNKEN  = (0.055, 0.071, 0.094, 1)      # 卡片里挖下去的一块
INPUT   = (0.106, 0.137, 0.173, 1)      # #1B232C
LINE    = (1, 1, 1, 0.08)
LINE2   = (1, 1, 1, 0.16)
TXT     = (0.914, 0.933, 0.957, 1)
DIM     = (0.545, 0.592, 0.651, 1)
DIM2    = (0.369, 0.416, 0.471, 1)
AMBER   = (1.0, 0.651, 0.169, 1)
AMBER2  = (1.0, 0.478, 0.094, 1)
OKC     = (0.24, 0.86, 0.59, 1)
WARN    = (1.0, 0.62, 0.24, 1)
DARKTX  = (0.145, 0.086, 0.012, 1)      # 琥珀按钮上的字


def _a(c, k=1.0):
    return (c[0], c[1], c[2], c[3] * k)


# ============================================================
# 通用小工具
# ============================================================
def panel(w, fill=CARD, border=LINE, radius=20, bw=0.9):
    """给任意控件加一层圆角底。"""
    with w.canvas.before:
        w._p_c = Color(*fill)
        w._p_bg = RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(radius)])
        w._p_bc = Color(*border)
        w._p_bd = Line(rounded_rectangle=(w.x, w.y, w.width, w.height, dp(radius)),
                       width=dp(bw))

    def _sync(*_a):
        w._p_bg.pos = w.pos
        w._p_bg.size = w.size
        w._p_bg.radius = [dp(radius)]
        w._p_bd.rounded_rectangle = (w.x, w.y, w.width, w.height, dp(radius))

    w.bind(pos=_sync, size=_sync)
    return w


def repanel(w, fill=None, border=None):
    if fill is not None:
        w._p_c.rgba = fill
    if border is not None:
        w._p_bc.rgba = border


def L(text="", fs=13, color=TXT, bold=False, align="left", valign="middle"):
    """常用标签。bold 用描边模拟(黑体没有粗体字重)。"""
    lb = Label(text=text, font_size=sp(fs), color=color, bold=False,
               halign=align, valign=valign, size_hint_y=None, height=sp(fs) * 1.6)
    if bold:
        lb.outline_width = sp(0.42)
        lb.outline_color = color
    lb.bind(size=lambda i, v: setattr(i, "text_size", (v[0], None)))
    return lb


def tw(text, fs, extra=0.0):
    """粗略估宽(中文按全角、西文按 0.56 全角), 用来给固定宽度的小标签定宽。

    这样不依赖 texture_size 的分布时机, 布局一帧就稳。
    """
    w = 0.0
    for c in (text or ""):
        w += fs if ord(c) > 0x2E80 else fs * 0.56
    return w + dp(extra)


def fit(lbl, extra=0.0):
    """按文字宽度固定标签宽度(左/右对齐都靠它)。"""
    lbl.size_hint_x = None
    lbl.width = tw(lbl.text, lbl.font_size, extra)
    return lbl


def center_in(child, parent):
    """把 child 摆到 parent 正中(Button 这类非 Layout 控件不会自己摆子控件)。"""
    def _sync(*_a):
        child.pos = [parent.center_x - child.width / 2.0,
                     parent.center_y - child.height / 2.0]
    parent.bind(pos=_sync, size=_sync)
    _sync()
    return child


def vpad(w, row_h, pad_x=0.0):
    """把控件在 row_h 高的行里垂直居中。

    Kivy 的 BoxLayout 对 size_hint_y=None 的子控件是贴底的, 靠上下等量 padding
    把它顶到中间 —— 这样真机和预览一致。
    """
    gap = max(0.0, (float(row_h) - w.height) / 2.0)
    box = BoxLayout(size_hint=(None, 1), width=w.width + dp(2 * pad_x),
                    padding=[dp(pad_x), dp(gap), dp(pad_x), dp(gap)])
    box.add_widget(w)
    return box


def hairline(w, color=LINE, pos="top"):
    with w.canvas.after:
        c = Color(*color)
        ln = Line(points=(0, 0, 0, 0), width=dp(0.8))

    def _sync(*_a):
        y = w.y + w.height if pos == "top" else w.y
        ln.points = (w.x, y, w.x + w.width, y)

    w.bind(pos=_sync, size=_sync)
    return w


class Glyph(Widget):
    """小图标: 全部用 Line/Ellipse 画, 不依赖图片和特殊字符。"""

    def __init__(self, kind="", size=16, color=DIM, lw=1.7, **kw):
        kw.setdefault("size_hint", (None, None))
        super().__init__(**kw)
        self.kind = kind
        self.gsize = size
        self.gcolor = color
        self.glw = lw
        self.size = (dp(size), dp(size))
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *a):
        self.canvas.after.clear()
        cx, cy = self.center_x, self.center_y
        s = self.gsize / 2.0 * 0.92
        col = self.gcolor
        wd = dp(self.glw)
        with self.canvas.after:
            Color(*col)
            k = self.kind
            if k == "back":
                Line(points=[cx + s * .45, cy - s, cx - s * .5, cy, cx + s * .45, cy + s],
                     width=wd, joint="round", cap="round")
            elif k == "next":
                Line(points=[cx - s * .45, cy - s, cx + s * .5, cy, cx - s * .45, cy + s],
                     width=wd, joint="round", cap="round")
            elif k == "chev":
                Line(points=[cx - s * .5, cy + s * .28, cx, cy - s * .3, cx + s * .5, cy + s * .28],
                     width=wd, joint="round", cap="round")
            elif k == "gear":
                Line(circle=(cx, cy, s * .62, 0, 360), width=wd)
                Line(circle=(cx, cy, s * .22, 0, 360), width=wd)
                import math
                for i in range(8):
                    t = math.pi / 4 * i + math.pi / 8
                    Line(points=[cx + math.cos(t) * s * .66, cy + math.sin(t) * s * .66,
                                 cx + math.cos(t) * s * 1.0, cy + math.sin(t) * s * 1.0],
                         width=wd, cap="round")
            elif k == "share":
                Line(points=[cx, cy - s * .55, cx, cy + s * .85], width=wd, cap="round")
                Line(points=[cx - s * .45, cy + s * .35, cx, cy + s * .85,
                             cx + s * .45, cy + s * .35], width=wd, joint="round", cap="round")
                Line(points=[cx - s * .75, cy - s * .12, cx - s * .75, cy - s * .8,
                             cx + s * .75, cy - s * .8, cx + s * .75, cy - s * .12],
                     width=wd, joint="round", cap="round")
            elif k == "copy":
                Line(rectangle=(cx - s * .85, cy - s * .15, s * 1.4, s * 1.15), width=wd)
                Line(points=[cx - s * .1, cy + s * .3, cx - s * .1, cy + s * .85,
                             cx + s * .85, cy + s * .85, cx + s * .85, cy + s * .15],
                     width=wd, joint="round", cap="round")
            elif k == "check":
                Line(points=[cx - s * .85, cy + s * .02, cx - s * .2, cy - s * .62,
                             cx + s * .85, cy + s * .55], width=wd, joint="round", cap="round")
            elif k == "sun":
                Line(circle=(cx, cy, s * .34, 0, 360), width=wd)
                import math
                for i in range(8):
                    t = math.pi / 4 * i
                    Line(points=[cx + math.cos(t) * s * .52, cy + math.sin(t) * s * .52,
                                 cx + math.cos(t) * s * .95, cy + math.sin(t) * s * .95],
                         width=wd, cap="round")
            elif k == "ball":
                Line(circle=(cx, cy, s * .72, 0, 360), width=wd)
                Color(*col)
                Ellipse(pos=(cx - s * .22, cy - s * .22), size=(s * .44, s * .44))
            elif k == "baffle":
                Line(points=[cx - s * .8, cy - s * .45, cx + s * .8, cy - s * .45],
                     width=wd, cap="round")
                Line(points=[cx - s * .55, cy - s * .45, cx - s * .55, cy + s * .62],
                     width=wd, cap="round")
                Line(points=[cx + s * .55, cy - s * .45, cx + s * .55, cy + s * .62],
                     width=wd, cap="round")
            elif k == "side":
                Line(points=[cx - s * .7, cy - s * .7, cx - s * .7, cy + s * .55],
                     width=wd, cap="round")
                Line(points=[cx + s * .7, cy - s * .7, cx + s * .7, cy + s * .55],
                     width=wd, cap="round")
                Line(points=[cx - s * .7, cy + s * .55, cx + s * .7, cy + s * .55],
                     width=wd, cap="round")
            elif k == "arrow":
                Line(points=[cx - s * .8, cy, cx + s * .8, cy], width=wd, cap="round")
                Line(points=[cx + s * .05, cy + s * .55, cx + s * .8, cy,
                             cx + s * .05, cy - s * .55], width=wd, joint="round", cap="round")
            elif k == "plus":
                Line(points=[cx - s * .7, cy, cx + s * .7, cy], width=wd, cap="round")
                Line(points=[cx, cy - s * .7, cx, cy + s * .7], width=wd, cap="round")


class IconBtn(Button):
    def __init__(self, kind="back", size=36, gsize=16, color=DIM, accent=False, **kw):
        kw.setdefault("size_hint", (None, None))
        kw.setdefault("background_normal", "")
        kw.setdefault("background_down", "")
        kw.setdefault("background_color", (0, 0, 0, 0))
        super().__init__(**kw)
        self.size = (dp(size), dp(size))
        self.color = color
        panel(self, fill=_a(AMBER, 0.14) if accent else (1, 1, 1, 0.055),
              border=_a(AMBER, 0.32) if accent else LINE, radius=11)
        g = Glyph(kind, size=gsize, color=AMBER if accent else (0.72, 0.76, 0.81, 1))
        self.add_widget(g)
        center_in(g, self)


class MiniSwitch(Widget):
    """圆角开关 (代替原来那个灰色小方块勾选框)。

    注意: 名字不能叫 Switch —— Kivy 内置 kivy.uix.switch.Switch 在 data/style.kv 里
    用 <Switch> 注册了样式规则，而 Kivy 是按**类名**匹配 kv 规则的。叫 Switch 会让
    那条规则套到本控件上，规则里的 self.active_norm_pos 在本类上是 None，
    求值 None * float 抛 TypeError，App 启动即崩（手机上表现为打开闪退）。
    回归检查: python tests/check_class_names.py
    """
    active = BooleanProperty(False)

    def __init__(self, active=False, w=38, h=22, **kw):
        kw.setdefault("size_hint", (None, None))
        super().__init__(**kw)
        self.size = (dp(w), dp(h))
        with self.canvas.before:
            self._tc = Color(1, 1, 1, 0.10)
            self._tr = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(h / 2.0)])
            self._ac = Color(*AMBER)
            self._ar = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(h / 2.0)])
            self._kc = Color(0.49, 0.53, 0.58, 1)
            self._kn = Ellipse(pos=self.pos, size=(dp(15), dp(15)))
        self.bind(pos=self._sync, size=self._sync, active=self._sync)
        self.active = bool(active)
        self._sync()

    def _sync(self, *a):
        w, h = self.size
        r = h / 2.0
        kd = h - dp(6)
        self._tr.pos = self.pos
        self._tr.size = self.size
        self._tr.radius = [r]
        self._ar.pos = self.pos
        self._ar.size = self.size
        self._ar.radius = [r]
        if self.active:
            self._ac.rgba = AMBER
            self._kc.rgba = DARKTX
            kx = self.x + w - kd - dp(3)
        else:
            self._ac.rgba = (0, 0, 0, 0)
            self._kc.rgba = (0.49, 0.53, 0.58, 1)
            kx = self.x + dp(3)
        self._kn.pos = (kx, self.y + dp(3))
        self._kn.size = (kd, kd)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.active = not self.active
            return True
        return super().on_touch_down(touch)


class Input(TextInput):
    """深色圆角输入框; 聚焦时描边变琥珀色。"""

    def __init__(self, text="", hint="", fs=15, align="right", **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(40))
        kw.setdefault("multiline", False)
        kw.setdefault("input_filter", "float")
        kw.setdefault("input_type", "text")
        super().__init__(text=text, hint_text=hint, font_size=sp(fs),
                         foreground_color=TXT, cursor_color=AMBER,
                         background_color=(0, 0, 0, 0),
                         background_normal="", background_active="",
                         halign=align, padding=[dp(10), dp(11), dp(10), dp(8)],
                         write_tab=False, **kw)
        with self.canvas.before:
            self._bc = Color(*INPUT)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(9)])
            self._lc = Color(*LINE2)
            self._ln = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(9)),
                            width=dp(0.9))
        self.bind(pos=self._sync, size=self._sync, focus=self._on_focus_changed)
        self._sync()
        _register_input(self)

    def _sync(self, *a):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bg.radius = [dp(9)]
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(9))
        if self.focus:
            self._lc.rgba = _a(AMBER, 0.75)
        else:
            self._lc.rgba = LINE2

    def _on_focus_changed(self, *a):
        """注意: 方法名不能叫 _on_focus!

        Kivy 的 FocusBehavior.__init__ 里是 fbind('focus', self._on_focus),
        而 self._on_focus 会解析到子类(本类)的同名方法。一旦在这里覆盖 _on_focus,
        Kivy 自己的 _on_focus -> _bind_keyboard -> Window.request_keyboard ->
        SDL_StartTextInput 整条链就再也不会执行 —— 表现为手机点输入框
        "输入法完全不弹", 且 IME 服务端 mServedInputConnection 一直是 null。
        """
        if self.focus:
            # 拿到焦点时把别的输入框的焦点(和橙色描边)清掉, 键盘只跟着这一个
            _defocus_others(self)
        self._sync()


class DarkOption(SpinnerOption):
    """下拉层的选项样式(深色)。Kivy 的 Spinner.option_cls 要的是"类名字符串",
    所以下面注册进 Factory, 再用名字引用。"""

    def __init__(self, **kw):
        kw.setdefault("background_normal", "")
        kw.setdefault("background_down", "")
        kw.setdefault("background_color", (0.10, 0.13, 0.17, 1))
        kw.setdefault("color", TXT)
        kw.setdefault("font_size", sp(14))
        super().__init__(**kw)


try:
    from kivy.factory import Factory
    Factory.register("DarkOption", cls=DarkOption)
    _OPTION_CLS = "DarkOption"
except Exception:
    _OPTION_CLS = "SpinnerOption"


class Select(Spinner):
    """下拉选择: 圆角 + 右侧小箭头, 置灰时文字变暗。"""
    muted = BooleanProperty(False)

    def __init__(self, text="", values=(), muted=False, w=112, h=34, **kw):
        kw.setdefault("size_hint", (None, None))
        super().__init__(text=text, values=list(values), font_size=sp(13),
                         color=TXT, halign="left", valign="middle",
                         background_normal="", background_down="",
                         background_color=(0, 0, 0, 0),
                         disabled=bool(muted), **kw)
        self.size = (dp(w), dp(h))
        self.option_cls = _OPTION_CLS
        with self.canvas.before:
            self._bc = Color(*INPUT)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
            self._lc = Color(*LINE2)
            self._ln = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(10)),
                            width=dp(0.9))
        with self.canvas.after:
            self._cc = Color(*DIM)
            self._ch = Line(points=(0, 0, 0, 0), width=dp(2), joint="round",
                            cap="round")
        self.bind(pos=self._sync, size=self._sync, text=self._sync, disabled=self._sync)
        self.muted = bool(muted)
        self._sync()

    def _sync(self, *a):
        w, h = self.size
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bg.radius = [dp(10)]
        self._ln.rounded_rectangle = (self.x, self.y, w, h, dp(10))
        cx, cy = self.right - dp(13), self.center_y
        s = dp(4.2)
        self._ch.points = [cx - s, cy + s * .45, cx, cy - s * .45, cx + s, cy + s * .45]
        grey = self.muted or self.disabled
        self._bc.rgba = (1, 1, 1, 0.035) if grey else INPUT
        self._lc.rgba = (1, 1, 1, 0.10) if grey else LINE2
        self._cc.rgba = (1, 1, 1, 0.28) if grey else (1, 1, 1, 0.55)
        self.color = (0.50, 0.54, 0.59, 1) if grey else TXT
        # 文字内缩, 给右侧箭头留位置
        self.text_size = (w - dp(26), None)


class PitchChip(ToggleButton):
    """节距分段胶囊。"""

    def __init__(self, text="", **kw):
        super().__init__(text=text, font_size=sp(12.5), color=DIM,
                         background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), **kw)
        with self.canvas.before:
            self._fc = Color(1, 1, 1, 0.045)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(11)])
            self._gc = Color(*AMBER)
            self._gl = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(11)])
            self._lc = Color(1, 1, 1, 0.10)
            self._ln = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, dp(11)),
                            width=dp(0.9))
        self.bind(pos=self._sync, size=self._sync, state=self._sync)
        self._sync()

    def _sync(self, *a):
        on = self.state == "down"
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._bg.radius = [dp(11)]
        self._bg.pos = self.pos
        self._gl.pos = self.pos
        self._gl.size = self.size
        self._gl.radius = [dp(11)]
        self._gc.rgba = AMBER if on else (0, 0, 0, 0)
        self._lc.rgba = (1, 1, 1, 0.30) if on else (1, 1, 1, 0.10)
        self._ln.rounded_rectangle = (self.x, self.y, self.width, self.height, dp(11))
        self.color = DARKTX if on else (0.61, 0.66, 0.71, 1)
        self.text_size = (self.width, None)


class Card(BoxLayout):
    def __init__(self, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("padding", [dp(15), dp(16), dp(15), dp(14)])
        kw.setdefault("spacing", dp(0))
        kw.setdefault("size_hint_y", None)
        super().__init__(**kw)
        panel(self, fill=CARD, border=LINE, radius=20)
        self.bind(minimum_height=self.setter("height"))


class SectionHead(BoxLayout):
    def __init__(self, title="", right="", **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(20))
        kw.setdefault("spacing", dp(8))
        super().__init__(orientation="horizontal", **kw)
        with self.canvas.before:
            Color(*AMBER)
            self._bar = RoundedRectangle(pos=(self.x, self.y + dp(4)),
                                         size=(dp(3), dp(12)), radius=[dp(1.5)])
        self.bind(pos=lambda *a: self._sync(), size=lambda *a: self._sync())
        self._t = L(title, 12.5, (0.74, 0.78, 0.82, 1), bold=True)
        fit(self._t, 2)
        self._pad = Widget(size_hint=(None, None), size=(dp(7), dp(1)))
        self.add_widget(self._pad)
        self.add_widget(self._t)
        self._r = L(right, 10.5, DIM2, align="right")
        self._r.size_hint_x = 1
        self.add_widget(self._r)

    def _sync(self):
        self._bar.pos = (self.x, self.center_y - dp(6))
        self._bar.size = (dp(3), dp(12))
        self._pad.size = (dp(7), dp(1))


class Row(BoxLayout):
    def __init__(self, h=46, divider=True, **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(h))
        kw.setdefault("spacing", dp(8))
        super().__init__(orientation="horizontal", **kw)
        if divider:
            hairline(self, LINE, "top")


class BottomBar(BoxLayout):
    def __init__(self, **kw):
        kw.setdefault("orientation", "horizontal")
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(84))
        # 上下各 16: 内容区正好 52 = 按钮高度, 按钮自然垂直居中
        kw.setdefault("padding", [dp(16), dp(16), dp(16), dp(16)])
        kw.setdefault("spacing", dp(12))
        super().__init__(**kw)
        panel(self, fill=(0.043, 0.055, 0.071, 0.98), border=LINE, radius=0)
        with self.canvas.after:
            Color(1, 1, 1, 0.06)
            self._ln = Line(points=(0, 0, 0, 0), width=dp(0.9))

        def _sync(*a):
            y = self.top - dp(0.5)
            self._ln.points = (self.x, y, self.right, y)

        self.bind(pos=_sync, size=_sync)


class CTA(Button):
    """琥珀实心主按钮。"""

    def __init__(self, text="", icon="", **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(52))
        kw.setdefault("background_normal", "")
        kw.setdefault("background_down", "")
        kw.setdefault("background_color", (0, 0, 0, 0))
        super().__init__(text=text, font_size=sp(16), color=DARKTX,
                         halign="center", valign="middle", **kw)
        panel(self, fill=AMBER, border=(1, 0.84, 0.56, 0.55), radius=16, bw=1.0)
        with self.canvas.after:
            Color(1, 1, 1, 0.22)
            self._hl = Line(points=(0, 0, 0, 0), width=dp(1))
            self._c = Color(0.15, 0.09, 0.01, 1)
            self._g = Line(points=(0, 0, 0, 0), width=dp(2), joint="round", cap="round")
            self._gh = Line(points=(0, 0, 0, 0), width=dp(2), joint="round", cap="round")
        self._icon = icon
        if icon:
            self.padding = [0, 0, dp(20), 0]
        self.bind(pos=self._sync, size=self._sync, state=self._sync)
        self._sync()
        # 布局当帧里 size/pos 的派发顺序不可靠, 下一帧再同步一次, 箭头才不会停在左边
        Clock.schedule_once(lambda *a: self._sync(), 0)

    # Kivy 会自动调用这两个, 比显式 bind 更保险
    def on_size(self, *a):
        Clock.schedule_once(lambda *x: self._sync(), -1)

    def on_pos(self, *a):
        Clock.schedule_once(lambda *x: self._sync(), -1)

    def _sync(self, *a):
        # Kivy 在 __init__ 里就会触发 on_pos/on_size, 那时画布指令还没建好
        if getattr(self, "_hl", None) is None:
            return
        r = dp(16)
        self._hl.points = (self.x + r, self.y + self.height - dp(1.2),
                           self.right - r, self.y + self.height - dp(1.2))
        if self._icon == "arrow":
            cx = self.right - dp(26)
            cy = self.center_y
            s = dp(7)
            self._g.points = [cx - s * .9, cy, cx + s * .55, cy]
            self._gh.points = [cx - s * .1, cy + s * .68,
                               cx + s * .55, cy,
                               cx - s * .1, cy - s * .68]
        if self.text_size[0] != self.width:
            self.text_size = (self.width, None)


class Ghost(Button):
    """描边次按钮。"""

    def __init__(self, text="", **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(52))
        kw.setdefault("background_normal", "")
        kw.setdefault("background_down", "")
        kw.setdefault("background_color", (0, 0, 0, 0))
        super().__init__(text=text, font_size=sp(13.5), color=(0.80, 0.84, 0.88, 1),
                         halign="center", valign="middle", **kw)
        panel(self, fill=(1, 1, 1, 0.05), border=LINE2, radius=16, bw=1.0)
        self.bind(pos=lambda *a: setattr(self, "text_size", (self.width, None)),
                  size=lambda *a: setattr(self, "text_size", (self.width, None)))


class AppBar(BoxLayout):
    def __init__(self, title="", sub="", right="gear", on_back=None, **kw):
        kw.setdefault("orientation", "horizontal")
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(58))
        kw.setdefault("padding", [dp(14), dp(8), dp(14), dp(6)])
        kw.setdefault("spacing", dp(10))
        super().__init__(**kw)
        panel(self, fill=BG, border=(0, 0, 0, 0), radius=0)
        self.back = IconBtn("back", 36, 15)
        if on_back:
            self.back.bind(on_release=lambda *a: on_back())
        else:
            self.back.disabled = True
            self.back.opacity = 0.35
        self.add_widget(self.back)
        box = BoxLayout(orientation="vertical", spacing=dp(1))
        self.title_lbl = L(title, 16.5, TXT, bold=True)
        self.sub_lbl = L(sub, 10.5, DIM2)
        box.add_widget(self.title_lbl)
        box.add_widget(self.sub_lbl)
        self.add_widget(box)
        if right:
            self.btn_right = IconBtn("gear" if right == "gear" else "share", 36, 16,
                                     accent=(right != "gear"))
            self.add_widget(self.btn_right)
        else:
            self.btn_right = None


# ============================================================
# 计算主界面
# ============================================================
class MainScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self._last = None
        with self.canvas.before:
            Color(*BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self._bg, "pos", self.pos),
                  size=lambda *a: setattr(self._bg, "size", self.size))
        self.build_ui()

    # ---------- 界面 ----------
    def build_ui(self):
        root = BoxLayout(orientation="vertical")
        self.add_widget(root)

        bar = AppBar("链板报价", "链板 · 链条 · 穿杆 一件到底", "gear")
        bar.btn_right.bind(on_release=lambda *a: self._go_settings())
        self.appbar = bar
        root.add_widget(bar)

        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(2))
        grid = GridLayout(cols=1, spacing=dp(12), size_hint_y=None,
                          padding=[dp(16), dp(6), dp(16), dp(20)])
        grid.bind(minimum_height=grid.setter("height"))
        self.scroll.add_widget(grid)
        root.add_widget(self.scroll)
        g = grid

        # ---------------- 材质与节距 ----------------
        c1 = Card()
        g.add_widget(c1)
        self.h_mat = SectionHead("材质与节距", "3 项已定")
        c1.add_widget(self.h_mat)
        c1.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # 板材质
        r1 = Row(46)
        r1.add_widget(L("板材质", 13.5, (0.79, 0.83, 0.87, 1)))
        self.sp_plate = Select(MATERIAL_LIST[0], MATERIAL_LIST, w=112)
        self.sp_plate.bind(text=lambda *a: self.refresh_info())
        r1.add_widget(vpad(self.sp_plate, 46))
        c1.add_widget(r1)

        # 链条材质
        r2 = Row(46)
        r2.add_widget(L("链条材质", 13.5, (0.79, 0.83, 0.87, 1)))
        self.cb_chain_u = MiniSwitch(True)
        self.cb_chain_u.bind(active=self.on_chain_unified)
        r2.add_widget(vpad(self.cb_chain_u, 46))
        r2.add_widget(vpad(L("同板", 11, DIM), 46))
        self.sp_chain = Select(MATERIAL_LIST[0], MATERIAL_LIST, w=112, muted=True)
        r2.add_widget(vpad(self.sp_chain, 46))
        c1.add_widget(r2)

        # 穿杆材质
        r3 = Row(46)
        r3.add_widget(L("穿杆材质", 13.5, (0.79, 0.83, 0.87, 1)))
        self.cb_pin_u = MiniSwitch(True)
        self.cb_pin_u.bind(active=self.on_pin_unified)
        r3.add_widget(vpad(self.cb_pin_u, 46))
        r3.add_widget(vpad(L("同板", 11, DIM), 46))
        self.sp_pin = Select(MATERIAL_LIST[0], MATERIAL_LIST, w=112, muted=True)
        r3.add_widget(vpad(self.sp_pin, 46))
        c1.add_widget(r3)

        # 节距
        ph = Row(28, divider=False)
        ph.add_widget(L("节距", 13.5, (0.79, 0.83, 0.87, 1)))
        self.lbl_pitch = L("", 11, DIM2, align="right")
        self.lbl_pitch.size_hint_x = 1
        ph.add_widget(self.lbl_pitch)
        c1.add_widget(ph)

        chips = BoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(36), spacing=dp(7))
        self.pitch_btns = {}
        for p in PITCHES:
            # group: 单选; allow_no_selection=False: 再点已选中的不会变成"全不选"
            b = PitchChip(p, group="pitch", allow_no_selection=False)
            b.state = "down" if p == "50.8" else "normal"
            b.bind(on_release=lambda *a: self.refresh_info())
            self.pitch_btns[p] = b
            chips.add_widget(b)
        c1.add_widget(chips)
        c1.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # 元信息条
        meta = Row(30, divider=False)
        with meta.canvas.before:
            Color(1, 1, 1, 0.10)
            meta._dash = Line(points=(0, 0, 0, 0), width=dp(0.8))

        def _meta_sync(*_a):
            y = meta.top - dp(1)
            meta._dash.points = (meta.x, y, meta.right, y)

        meta.bind(pos=_meta_sync, size=_meta_sync)
        self.lbl_chain_w = L("", 10.5, (0.47, 0.52, 0.57, 1))
        self.lbl_chain_w.size_hint_x = 1
        meta.add_widget(self.lbl_chain_w)
        self.lbl_sheet = L("", 10.5, (0.47, 0.52, 0.57, 1), align="right")
        self.lbl_sheet.size_hint_x = 1
        meta.add_widget(self.lbl_sheet)
        c1.add_widget(meta)

        # ---------------- 基础尺寸 ----------------
        c2 = Card()
        g.add_widget(c2)
        self.h_size = SectionHead("基础尺寸", "单位 mm")
        c2.add_widget(self.h_size)
        c2.add_widget(Widget(size_hint_y=None, height=dp(12)))

        stats = GridLayout(cols=3, size_hint_y=None, height=dp(66), spacing=dp(1))
        panel(stats, fill=SUNKEN, border=LINE, radius=14)
        with stats.canvas.after:
            Color(1, 1, 1, 0.07)
            stats._v1 = Line(points=(0, 0, 0, 0), width=dp(1))
            stats._v2 = Line(points=(0, 0, 0, 0), width=dp(1))
            Color(*AMBER)
            stats._top = Line(points=(0, 0, 0, 0), width=dp(2))

        def _stats_sync(*_a):
            w = stats.width / 3.0
            stats._v1.points = (stats.x + w, stats.y + dp(8), stats.x + w, stats.top - dp(8))
            stats._v2.points = (stats.x + 2 * w, stats.y + dp(8),
                                stats.x + 2 * w, stats.top - dp(8))
            stats._top.points = (stats.x + dp(12), stats.top - dp(1),
                                 stats.x + w - dp(10), stats.top - dp(1))

        stats.bind(pos=_stats_sync, size=_stats_sync)

        self.in_width = Input("445", "有效宽度", 15, "right")
        self.in_thick = Input("1", "板厚", 15, "right")
        self.in_pin_d = Input("8", "穿杆直径", 15, "right")

        stats.add_widget(self._stat_cell("有效宽度", self.in_width))
        stats.add_widget(self._stat_cell("板厚", self.in_thick))
        stats.add_widget(self._stat_cell("穿杆直径", self.in_pin_d))
        c2.add_widget(stats)
        self.in_thick.bind(text=lambda *a: self._update_punch_hint())
        # 三个尺寸框一改, 底部预估价立刻跟着变
        for _ti in (self.in_width, self.in_thick, self.in_pin_d):
            _ti.bind(text=lambda *a: self._refresh_estimate())

        # ---------------- 选配件 ----------------
        c3 = Card()
        g.add_widget(c3)
        self.h_acc = SectionHead("选配件", "已选 0 / 5")
        c3.add_widget(self.h_acc)
        c3.add_widget(Widget(size_hint_y=None, height=dp(8)))

        self.acc_rows = {}
        self.acc_titles = {}
        self.acc_switches = {}

        def make_acc(key, title, sub, icon, fields, tag=""):
            row = Row(46, divider=True)
            tile = Widget(size_hint=(None, None), size=(dp(30), dp(30)))
            panel(tile, fill=(1, 1, 1, 0.04), border=LINE, radius=9)
            gl = Glyph(icon, 15, (0.50, 0.54, 0.59, 1))
            tile.add_widget(gl)
            center_in(gl, tile)
            row.add_widget(vpad(tile, 46))

            nm = BoxLayout(orientation="vertical", spacing=dp(1))
            title_lbl = L(title, 13.5, (0.86, 0.90, 0.94, 1))
            sub_lbl = L(sub, 10.5, (0.39, 0.44, 0.49, 1))
            nm.add_widget(title_lbl)
            nm.add_widget(sub_lbl)
            row.add_widget(nm)

            if tag:
                tg = fit(L(tag, 10, (0.60, 0.64, 0.70, 1)), 14)
                row.add_widget(vpad(tg, 46))

            sw = MiniSwitch(False)
            row.add_widget(vpad(sw, 46))
            c3.add_widget(row)

            fbox = GridLayout(cols=2, spacing=dp(6), size_hint_y=None,
                              padding=[dp(10), dp(9), dp(10), dp(9)])
            panel(fbox, fill=(1, 1, 1, 0.035), border=(1, 0.65, 0.17, 0.28), radius=12)
            inputs = {}
            for ftitle, fkey in fields:
                lb = L(ftitle, 11, (0.52, 0.56, 0.61, 1))
                fbox.add_widget(lb)
                ti = Input("", "", 13, "right")
                ti.size_hint_y = None
                ti.height = dp(30)
                inputs[fkey] = ti
                fbox.add_widget(ti)
            fbox.height = 0
            fbox.opacity = 0
            fbox.disabled = True
            c3.add_widget(fbox)

            sw.bind(active=lambda chk, v, fb=fbox, k=key: self._toggle_row(k, v))

            self.acc_rows[key] = (sw, fbox, inputs)
            self.acc_titles[key] = sub_lbl
            self.acc_switches[key] = (sw, tile, gl)

        make_acc("cross", "横挡板", "长 / 高 / 厚 / 间隔 4 项", "baffle",
                 [("长度mm", "length"), ("高度mm", "height"),
                  ("厚度mm", "thickness"), ("间隔mm", "interval")], "按 kg")
        make_acc("side", "侧挡板", "高度 / 厚度 2 项", "side",
                 [("高度mm", "height"), ("厚度mm", "thickness")])
        make_acc("ball", "辅助载重滚珠", "1 元 / 个 · 按排数计", "ball",
                 [("排数", "rows")])
        make_acc("wheel", "辅助载重支轮", "3.5 元 / 个 · 按排数计", "ball",
                 [("排数", "rows")])
        make_acc("punch", "冲孔", "板厚 2.0 → 单孔 0.80 元", "sun",
                 [("价格元/片", "price")])

        self.lbl_punch_hint = L("", 10.5, OKC)
        self.lbl_punch_hint.size_hint_y = None
        self.lbl_punch_hint.height = dp(0)
        self.lbl_punch_hint.opacity = 0
        c3.add_widget(self.lbl_punch_hint)

        # ---------------- 吸底 ----------------
        bb = BottomBar()
        self.lbl_est_t = L("每米价格", 10, (0.41, 0.45, 0.51, 1))
        self.lbl_est_v = L("￥783.8", 20, TXT, bold=True)
        est = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(122),
                        spacing=dp(0))
        est.add_widget(self.lbl_est_t)
        est.add_widget(self.lbl_est_v)
        bb.add_widget(est)
        self.btn_calc = CTA("计 算", "arrow")
        self.btn_calc.bind(on_release=lambda *a: self.on_compute())
        bb.add_widget(self.btn_calc)
        root.add_widget(bb)
        self.bottombar = bb

        self.refresh_acc_titles()
        self.refresh_info()
        self._update_punch_hint()

    def _stat_cell(self, title, inp):
        b = BoxLayout(orientation="vertical", spacing=dp(2),
                      padding=[dp(12), dp(9), dp(10), dp(9)])
        b.add_widget(L(title, 10.5, DIM2))
        inp.halign = "left"
        b.add_widget(inp)
        return b

    def _toggle_row(self, key, on):
        sw, fbox, inputs = self.acc_rows[key]
        self.toggle_acc(fbox, on)
        _sw, tile, gl = self.acc_switches[key]
        repanel(tile, fill=_a(AMBER, 0.16) if on else (1, 1, 1, 0.04),
                border=_a(AMBER, 0.30) if on else LINE)
        gl.gcolor = AMBER if on else (0.50, 0.54, 0.59, 1)
        gl._redraw()
        n = sum(1 for k in self.acc_rows if self.acc_rows[k][0].active)
        self.h_acc._r.text = "已选 %d / 5" % n
        if key == "punch":
            self._update_punch_hint()
        self._refresh_estimate()

    def _refresh_estimate(self):
        """吸底条的实时预估价。

        口径与 on_compute 一致: 勾上且填全的选配件一起计入, 填不全就先跳过
        —— 这样"勾一个配件, 价格马上跟着变", 而不是等点了计算才知道。
        """
        s = self.app.settings
        try:
            params = {"pitch": self.pitch(),
                      "plate_mat": MATERIAL_KEY.get(self.sp_plate.text, self.sp_plate.text),
                      "chain_mat": MATERIAL_KEY.get(self.sp_chain.text, self.sp_chain.text),
                      "pin_mat": MATERIAL_KEY.get(self.sp_pin.text, self.sp_pin.text),
                      "width": float(self.in_width.text or 0),
                      "thickness": float(self.in_thick.text or 0),
                      "pin_d": float(self.in_pin_d.text or 0)}
        except Exception:
            return
        if params["width"] <= 0 or params["thickness"] <= 0 or params["pin_d"] <= 0:
            return

        def _val(ti):
            v = float(ti.text.strip())
            if v <= 0:
                raise ValueError
            return v

        if self.acc_rows["cross"][0].active:
            inp = self.acc_rows["cross"][2]
            try:
                params["cross"] = {"length": _val(inp["length"]),
                                   "height": _val(inp["height"]),
                                   "thickness": _val(inp["thickness"]),
                                   "interval": _val(inp["interval"])}
            except Exception:
                pass
        if self.acc_rows["side"][0].active:
            inp = self.acc_rows["side"][2]
            try:
                params["side"] = {"height": _val(inp["height"]),
                                  "thickness": _val(inp["thickness"])}
            except Exception:
                pass
        if self.acc_rows["ball"][0].active:
            try:
                params["ball_rows"] = int(_val(self.acc_rows["ball"][2]["rows"]))
            except Exception:
                pass
        if self.acc_rows["wheel"][0].active:
            try:
                params["wheel_rows"] = int(_val(self.acc_rows["wheel"][2]["rows"]))
            except Exception:
                pass
        if self.acc_rows["punch"][0].active:
            params["punch"] = True
            try:
                auto = params["thickness"] < s["punch_hole"]["auto_max_t"]
                params["punch_manual"] = (None if auto
                                          else _val(self.acc_rows["punch"][2]["price"]))
            except Exception:
                return
        try:
            r = compute(params, s)
            self.lbl_est_v.text = "￥%.1f" % r["total_per_meter"]
            self._est_ok = True
        except Exception:
            pass

    # ---------- 交互 ----------
    def toggle_acc(self, fbox, visible):
        fbox.opacity = 1 if visible else 0
        fbox.disabled = not visible
        if visible:
            rows = len(fbox.children) // 2
            fbox.height = dp(46) * rows - dp(6)
        else:
            fbox.height = 0
        if fbox is self.acc_rows["punch"][1]:
            self._update_punch_hint()

    def on_chain_unified(self, cb, val):
        self.sp_chain.disabled = val
        self.sp_chain.muted = val
        self.sp_chain._sync()
        if val:
            self.sp_chain.text = self.sp_plate.text

    def on_pin_unified(self, cb, val):
        self.sp_pin.disabled = val
        self.sp_pin.muted = val
        self.sp_pin._sync()
        if val:
            self.sp_pin.text = self.sp_plate.text

    def _go_settings(self):
        self.manager.current = "settings"

    def pitch(self):
        for p, b in self.pitch_btns.items():
            if b.state == "down":
                return p
        return "50.8"

    def refresh_info(self):
        s = self.app.settings
        if self.cb_chain_u.active:
            self.sp_chain.text = self.sp_plate.text
        if self.cb_pin_u.active:
            self.sp_pin.text = self.sp_plate.text
        mat = MATERIAL_KEY.get(self.sp_plate.text, self.sp_plate.text)
        p = self.pitch()
        cw = chain_width_of(p, s)
        self.lbl_chain_w.text = "节距 %s · 链宽 %g mm" % (p, cw)
        self.lbl_sheet.text = "板价 %g 元/kg" % s["sheet_price"][mat]
        self.lbl_pitch.text = ("%s mm · 假两寸" % p) if p == "假两寸" else ("%s mm" % p)
        self._update_acc_subs()
        self._refresh_estimate()

    def refresh_acc_titles(self):
        acc = self.app.settings["accessory"]
        self.acc_titles["ball"].text = "%g 元 / 个 · 按排数计" % acc["ball"]
        self.acc_titles["wheel"].text = "%g 元 / 个 · 按排数计" % acc["wheel"]
        self.acc_titles["cross"].text = "长 / 高 / 厚 / 间隔 4 项 · 工费 %g" % acc["cross_fee"]
        self.acc_titles["side"].text = "高度 / 厚度 2 项 · 工费 %g" % acc["side_fee"]

    def _update_acc_subs(self):
        """冲孔副标题跟着板厚走, 不用点开就知道按哪个价算。"""
        s = self.app.settings["punch_hole"]
        try:
            t = float(self.in_thick.text)
        except ValueError:
            self.acc_titles["punch"].text = "板厚未填"
            return
        if t < s["auto_max_t"]:
            self.acc_titles["punch"].text = "板厚 %g → 自动计价" % t
        else:
            self.acc_titles["punch"].text = "板厚 %g → 需手动填价" % t

    def _update_punch_hint(self):
        try:
            active = self.acc_rows["punch"][0].active
        except KeyError:
            return
        if not active:
            self.lbl_punch_hint.text = ""
            self.lbl_punch_hint.height = dp(0)
            self.lbl_punch_hint.opacity = 0
            self._update_acc_subs()
            return
        s = self.app.settings["punch_hole"]
        try:
            t = float(self.in_thick.text)
        except ValueError:
            self.lbl_punch_hint.text = "请先填写板厚"
            self.lbl_punch_hint.height = dp(24)
            self.lbl_punch_hint.opacity = 1
            return
        if t < s["auto_max_t"]:
            self.lbl_punch_hint.text = (
                "板厚 %g < %g：自动计算 (宽<%g → %g 元/片, 否则 宽÷1000)"
                % (t, s["auto_max_t"], s["auto_flat_w"], s["auto_flat_fee"]))
        else:
            self.lbl_punch_hint.text = (
                "板厚 %g ≥ %g：需手动填价格 (元/片)" % (t, s["auto_max_t"]))
        self.lbl_punch_hint.height = dp(30)
        self.lbl_punch_hint.opacity = 1
        self._update_acc_subs()

    # ---------- 计算 ----------
    def _f(self, name, ti):
        try:
            v = float(ti.text.strip())
        except ValueError:
            raise ValueError("%s 输入无效: %r" % (name, ti.text))
        if v <= 0:
            raise ValueError("%s 必须大于 0" % name)
        return v

    def on_compute(self):
        s = self.app.settings
        params = {"pitch": self.pitch(),
                  "plate_mat": MATERIAL_KEY.get(self.sp_plate.text, self.sp_plate.text),
                  "chain_mat": MATERIAL_KEY.get(self.sp_chain.text, self.sp_chain.text),
                  "pin_mat": MATERIAL_KEY.get(self.sp_pin.text, self.sp_pin.text)}
        errs = []
        try:
            params["width"] = self._f("有效宽度", self.in_width)
            params["thickness"] = self._f("板厚", self.in_thick)
            params["pin_d"] = self._f("穿杆直径", self.in_pin_d)
        except ValueError as e:
            errs.append(str(e))
        if self.acc_rows["cross"][0].active:
            inp = self.acc_rows["cross"][2]
            try:
                params["cross"] = {
                    "length": self._f("横挡板长度", inp["length"]),
                    "height": self._f("横挡板高度", inp["height"]),
                    "thickness": self._f("横挡板厚度", inp["thickness"]),
                    "interval": self._f("横挡板间隔", inp["interval"]),
                }
            except ValueError as e:
                errs.append(str(e))
        if self.acc_rows["side"][0].active:
            inp = self.acc_rows["side"][2]
            try:
                params["side"] = {
                    "height": self._f("侧挡板高度", inp["height"]),
                    "thickness": self._f("侧挡板厚度", inp["thickness"]),
                }
            except ValueError as e:
                errs.append(str(e))
        if self.acc_rows["ball"][0].active:
            try:
                params["ball_rows"] = int(self._f("滚珠排数",
                                                  self.acc_rows["ball"][2]["rows"]))
            except ValueError as e:
                errs.append(str(e))
        if self.acc_rows["wheel"][0].active:
            try:
                params["wheel_rows"] = int(self._f("支轮排数",
                                                   self.acc_rows["wheel"][2]["rows"]))
            except ValueError as e:
                errs.append(str(e))
        if self.acc_rows["punch"][0].active:
            inp = self.acc_rows["punch"][2]
            params["punch"] = True
            try:
                t = float(self.in_thick.text)
                auto = t < s["punch_hole"]["auto_max_t"]
                params["punch_manual"] = None if auto else self._f("冲孔价格", inp["price"])
            except ValueError as e:
                errs.append(str(e))
        if errs:
            popup_msg("\n".join(errs))
            return
        try:
            r = compute(params, s)
        except ValueError as e:
            popup_msg("计算错误(公式可能有误, 请到设置→公式检查):\n%s" % e)
            return
        except Exception as e:
            popup_msg("计算出错: %s: %s" % (type(e).__name__, e))
            return
        self._last = r
        self.show_result(r)
        self.app.save_state()

    # ---------- 结果 ----------
    def show_result(self, r):
        self._last = r
        self.app.result_screen.show(r)
        self.manager.current = "result"
        self._refresh_estimate()

    def on_copy(self):
        if not self._last:
            return
        try:
            Clipboard.copy(format_result(self._last))
            popup_msg("明细已复制到剪贴板, 可直接粘贴到微信/短信")
        except Exception as e:
            popup_msg("复制失败: %s: %s" % (type(e).__name__, e))

    # ---------- 上次输入的记忆 ----------
    def collect_state(self):
        st = {"pitch": self.pitch(),
              "plate": self.sp_plate.text,
              "chain": self.sp_chain.text,
              "pin": self.sp_pin.text,
              "chain_u": bool(self.cb_chain_u.active),
              "pin_u": bool(self.cb_pin_u.active),
              "width": self.in_width.text,
              "thick": self.in_thick.text,
              "pin_d": self.in_pin_d.text,
              "acc": {}}
        for k, (cb, _fbox, inputs) in self.acc_rows.items():
            st["acc"][k] = {"on": bool(cb.active),
                            "v": {fk: ti.text for fk, ti in inputs.items()}}
        return st

    def restore_state(self, st):
        if not isinstance(st, dict) or not st:
            return
        try:
            if st.get("plate") in MATERIAL_LIST:
                self.sp_plate.text = st["plate"]
            cu = bool(st.get("chain_u", True))
            pu = bool(st.get("pin_u", True))
            self.cb_chain_u.active = cu
            self.cb_pin_u.active = pu
            if not cu and st.get("chain") in MATERIAL_LIST:
                self.sp_chain.text = st["chain"]
            if not pu and st.get("pin") in MATERIAL_LIST:
                self.sp_pin.text = st["pin"]
            p = st.get("pitch")
            if p in self.pitch_btns:
                for k, b in self.pitch_btns.items():
                    b.state = "down" if k == p else "normal"
            for key, ti in (("width", self.in_width), ("thick", self.in_thick),
                            ("pin_d", self.in_pin_d)):
                v = st.get(key)
                if isinstance(v, str) and v.strip():
                    ti.text = v
            for k, data in (st.get("acc") or {}).items():
                if k not in self.acc_rows:
                    continue
                cb, _fbox, inputs = self.acc_rows[k]
                cb.active = bool(data.get("on"))
                for fk, v in (data.get("v") or {}).items():
                    if fk in inputs and isinstance(v, str):
                        inputs[fk].text = v
            self.refresh_info()
            self._update_punch_hint()
        except Exception:
            pass


# ============================================================
# 结果页
# ============================================================
class CostBar(Widget):
    """成本结构条: 一条按比例分段的横条, 手机上比环形图更容易看清。

    指令一次性建好(最多 10 段), 之后只改 pos/size/颜色, 不重建 canvas —— 
    比 clear()+add() 稳, 也不会在重绘时留下残影。
    """

    MAXSEG = 10

    def __init__(self, **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(10))
        super().__init__(**kw)
        self._segs = []
        with self.canvas.before:
            Color(1, 1, 1, 0.07)
            self._track = RoundedRectangle(pos=self.pos, size=self.size,
                                           radius=[self.height / 2.0])
            self._cols, self._bars = [], []
            for _ in range(self.MAXSEG):
                c = Color(1, 1, 1, 0)
                b = RoundedRectangle(pos=self.pos, size=(0, 0), radius=[self.height / 2.0])
                self._cols.append(c)
                self._bars.append(b)
        self.bind(pos=self._redraw, size=self._redraw)

    def set_segments(self, segs):
        self._segs = list(segs)
        self._redraw()

    def _redraw(self, *a):
        x, y = self.x, self.y
        w, h = self.width, self.height
        r = h / 2.0
        self._track.pos = (x, y)
        self._track.size = (w, h)
        self._track.radius = [r]
        cur = 0.0
        total = 100.0
        for i in range(self.MAXSEG):
            if i >= len(self._segs):
                self._bars[i].size = (0, 0)
                continue
            a0, a1, col = self._segs[i]
            seg = max(0.0, a1 - a0)
            sx = x + w * (cur / total)
            sw = max(dp(2), w * (seg / total) - dp(1.2))
            cur += seg
            self._cols[i].rgba = tuple(col)
            self._bars[i].pos = (sx, y)
            self._bars[i].size = (sw, h)
            self._bars[i].radius = [r]


class ResultScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        with self.canvas.before:
            Color(*BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self._bg, "pos", self.pos),
                  size=lambda *a: setattr(self._bg, "size", self.size))
        self.build_ui()

    def build_ui(self):
        root = BoxLayout(orientation="vertical")
        self.add_widget(root)
        self.appbar = AppBar("报价结果", "—", "share", on_back=self._back)
        self.appbar.btn_right.bind(
            on_release=lambda *a: self.app.main_screen.on_copy())
        root.add_widget(self.appbar)

        self.scroll = ScrollView(do_scroll_x=False, bar_width=dp(2))
        grid = GridLayout(cols=1, spacing=dp(12), size_hint_y=None,
                          padding=[dp(16), dp(6), dp(16), dp(20)])
        grid.bind(minimum_height=grid.setter("height"))
        self.scroll.add_widget(grid)
        root.add_widget(self.scroll)
        g = grid

        # -------- 总价 --------
        hero = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(0),
                         padding=[dp(16), dp(15), dp(16), dp(14)])
        hero.bind(minimum_height=hero.setter("height"))
        panel(hero, fill=(0.082, 0.106, 0.133, 1), border=(1, 1, 1, 0.09), radius=22)
        g.add_widget(hero)

        top = BoxLayout(size_hint_y=None, height=dp(16))
        self.lbl_hero_t = fit(L("每米成本", 11, DIM), 2)
        top.add_widget(self.lbl_hero_t)
        top.add_widget(Widget())
        self.lbl_per = fit(L("", 10, DIM2, align="right"), 2)
        top.add_widget(self.lbl_per)
        hero.add_widget(top)

        numrow = BoxLayout(size_hint_y=None, height=dp(58), spacing=dp(3))
        cur = fit(L("￥", 17, AMBER, bold=True), 1)
        numrow.add_widget(cur)
        self.lbl_total = fit(L("—", 40, TXT, bold=True), 4)
        self.lbl_total.height = dp(54)
        numrow.add_widget(self.lbl_total)
        unit = fit(L("/ 米", 11.5, DIM), 8)
        numrow.add_widget(unit)
        numrow.add_widget(Widget())
        hero.add_widget(numrow)

        pills = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(6))
        self.pill_box = pills
        hero.add_widget(pills)
        hero.add_widget(Widget(size_hint_y=None, height=dp(12)))

        line = Widget(size_hint_y=None, height=dp(1))
        panel(line, fill=(1, 1, 1, 0.09), border=(0, 0, 0, 0), radius=0)
        hero.add_widget(line)
        hero.add_widget(Widget(size_hint_y=None, height=dp(12)))

        # 成本结构: 一条比例条 + 图例(比环形图更容易在手机上看清, 也更省性能)
        self.costbar = CostBar()
        hero.add_widget(self.costbar)
        hero.add_widget(Widget(size_hint_y=None, height=dp(10)))
        self.legend = GridLayout(cols=2, size_hint_y=None, height=dp(66),
                                 spacing=dp(2))
        hero.add_widget(self.legend)

        # -------- 明细 --------
        lst = Card()
        g.add_widget(lst)
        self.rows_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(0))
        self.rows_box.bind(minimum_height=self.rows_box.setter("height"))
        lst.add_widget(self.rows_box)

        self.res_note = L("", 10.5, DIM2, align="left")
        self.res_note.size_hint_y = None
        self.res_note.height = dp(0)
        self.res_note.opacity = 0
        g.add_widget(self.res_note)

        self._note_holder = Widget(size_hint_y=None, height=dp(10))
        g.add_widget(self._note_holder)

        # -------- 吸底 --------
        bb = BottomBar()
        self.btn_back = Ghost("返回修改")
        self.btn_back.bind(on_release=lambda *a: self._back())
        bb.add_widget(self.btn_back)
        self.btn_copy = CTA("复制明细", "copy")
        self.btn_copy.bind(on_release=lambda *a: self.app.main_screen.on_copy())
        bb.add_widget(self.btn_copy)
        root.add_widget(bb)
        self.bottombar = bb

    def _back(self):
        self.manager.current = "main"

    # ---------- 填充 ----------
    def show(self, r):
        self.r = r
        pm = r["per_meter"]
        tot = r["total_per_meter"]
        m = self.app.main_screen

        def _num(t):
            try:
                return float(t)
            except Exception:
                return 0.0

        self.appbar.sub_lbl.text = "%.0f 宽 · 板厚 %.1f · 节距 %s" % (
            _num(m.in_width.text), _num(m.in_thick.text), m.pitch())
        self.lbl_per.text = "%.1f 片 / 米" % pm
        fit(self.lbl_per, 2)
        self.lbl_total.text = "%.2f" % tot
        fit(self.lbl_total, 4)

        # 小药丸
        self.pill_box.clear_widgets()
        self.pill_box.add_widget(self._pill("单件 ￥%.2f" % (tot / pm if pm else 0)))
        # 所有分项统一折算成"每米", 才能算占比
        plate_m = r["plate"]["total"] * pm
        pin_m = r["pin"]["total"] * pm
        chain_m = r["chain"]["total"]
        side_m = (r["side"] or {}).get("total", 0)
        cross_m = (r["cross"] or {}).get("total", 0)
        punch_m = (r["punch"] or {}).get("price", 0) * pm
        ball_m = (r["ball"] or {}).get("total", 0)
        wheel_m = (r["wheel"] or {}).get("total", 0)
        labor_m = (r["labor"] or 0) * pm
        pct = ((plate_m + pin_m + chain_m + side_m + cross_m + punch_m + ball_m + wheel_m)
               / tot * 100.0) if tot else 0
        self.pill_box.add_widget(self._pill("材料 %.0f%%" % pct))
        self.pill_box.add_widget(self._pill(self.app.main_screen.sp_plate.text))
        self.pill_box.add_widget(Widget())

        # 环形图 + 图例
        parts = [("链板", plate_m, (1.0, 0.70, 0.22, 1)),
                 ("穿杆", pin_m, (0.94, 0.52, 0.16, 1)),
                 ("链条", chain_m, (0.66, 0.72, 0.78, 1)),
                 ("侧挡板", side_m, (0.42, 0.49, 0.56, 1)),
                 ("横挡板", cross_m, (0.30, 0.36, 0.42, 1)),
                 ("冲孔", punch_m, (0.22, 0.27, 0.33, 1)),
                 ("滚珠", ball_m, (0.55, 0.60, 0.66, 1)),
                 ("支轮", wheel_m, (0.48, 0.53, 0.59, 1)),
                 ("人工", labor_m, (0.78, 0.82, 0.86, 1))]
        parts = [p for p in parts if p[1] > 0]
        segs, acc = [], 0.0
        for _, v, col in parts:
            a0 = acc / tot * 100.0 if tot else 0
            acc += v
            a1 = acc / tot * 100.0 if tot else 0
            segs.append((a0, a1, col))
        self.costbar.set_segments(segs)

        self.legend.clear_widgets()
        for name, v, col in parts[:6]:
            self.legend.add_widget(self._legend(name, v / tot * 100.0 if tot else 0, col))

        # 明细
        self.rows_box.clear_widgets()
        rows = [("链板", "%.2f 元/片 × %.1f" % (r["plate"]["total"], pm),
                 "%.2f" % (r["plate"]["total"] * pm))]
        rows.append(("穿杆", "%.2f 元/根 × %.1f" % (r["pin"]["total"], pm),
                     "%.2f" % (r["pin"]["total"] * pm)))
        rows.append(("链条", "%.2f 元/米 × 2" % r["chain"]["unit"],
                     "%.2f" % r["chain"]["total"]))
        if r["side"]:
            rows.append(("侧挡板", "%.2f 元/件 × 2" % r["side"]["price"],
                         "%.2f" % r["side"]["total"]))
        if r["cross"]:
            rows.append(("横挡板", "%.2f 元/件 × %d" % (r["cross"]["price"],
                                                      r["cross"]["count"]),
                         "%.2f" % r["cross"]["total"]))
        if r["punch"]:
            rows.append(("冲孔", "%.2f 元/片 (%s)" % (r["punch"]["price"],
                                                   "自动" if r["punch"]["auto"] else "手动"),
                         "%.2f" % (r["punch"]["price"] * pm)))
        if r["ball"]:
            rows.append(("滚珠", "%.2f × %d 排" % (r["ball"]["unit"], r["ball"]["rows"]),
                         "%.2f" % r["ball"]["total"]))
        if r["wheel"]:
            rows.append(("支轮", "%.2f × %d 排" % (r["wheel"]["unit"], r["wheel"]["rows"]),
                         "%.2f" % r["wheel"]["total"]))
        if r["labor"]:
            rows.append(("人工", "%.2f 元/片 × %.1f" % (r["labor"], pm),
                         "%.2f" % (r["labor"] * pm)))
        for name, sub, val in rows:
            self.rows_box.add_widget(self._line(name, sub, val))
        self.rows_box.add_widget(self._total_line(tot))

        notes = []
        if r["cross"] and r["cross"]["count"] <= 0:
            notes.append("横挡板数量为 0 (间隔小于半个节距), 请检查“间隔”")
        if r["punch"] and not r["punch"]["auto"]:
            notes.append("冲孔按手动填写的价格计算")
        if notes:
            self.res_note.text = "\n".join(notes)
            self.res_note.color = WARN
            self.res_note.height = dp(18) * len(notes)
            self.res_note.opacity = 1
        else:
            self.res_note.text = ""
            self.res_note.height = dp(0)
            self.res_note.opacity = 0
        self.btn_copy.disabled = False
        Clock.schedule_once(lambda *a: setattr(self.scroll, "scroll_y", 1), 0.05)

    def _pill(self, txt):
        p = BoxLayout(size_hint=(None, None), size=(dp(10), dp(20)))
        lab = Label(text=txt, font_size=sp(10), color=(0.67, 0.71, 0.76, 1),
                    size_hint=(None, None), size=(dp(10), dp(20)),
                    halign="center", valign="middle")
        p.add_widget(lab)
        panel(p, fill=(1, 1, 1, 0.07), border=(0, 0, 0, 0), radius=6)
        # 宽度按文字长度估: 中文按 10px, 其它按 6px
        w = sum(10.0 if ord(c) > 0x2E80 else 6.2 for c in txt)
        p.width = dp(w + 16)
        lab.size = (p.width, p.height)
        lab.text_size = (p.width, p.height)
        return p

    def _legend(self, name, pct, col):
        b = BoxLayout(orientation="horizontal", spacing=dp(5), size_hint_y=None,
                      height=dp(18))
        dot = Widget(size_hint=(None, None), size=(dp(6), dp(6)))
        panel(dot, fill=col, border=(0, 0, 0, 0), radius=2)
        b.add_widget(Widget(size_hint=(None, None), size=(dp(0), dp(1))))
        b.add_widget(dot)
        b.add_widget(L(name, 10, (0.68, 0.73, 0.78, 1)))
        v = L("%.1f" % pct, 10, (0.90, 0.93, 0.96, 1), align="right")
        v.size_hint_x = 1
        b.add_widget(v)

        def _cy(*_a):
            dot.center_y = b.center_y

        b.bind(pos=_cy, size=_cy)
        return b

    def _line(self, name, sub, val):
        row = Row(42, divider=True)
        box = BoxLayout(orientation="vertical", spacing=dp(0))
        box.add_widget(L(name, 13, (0.87, 0.90, 0.94, 1)))
        box.add_widget(L(sub, 10, (0.39, 0.44, 0.49, 1)))
        row.add_widget(box)
        v = fit(L(val, 13.5, TXT, bold=True, align="right"), 2)
        row.add_widget(v)
        return row

    def _total_line(self, total):
        row = Row(46, divider=False)
        with row.canvas.before:
            Color(1, 1, 1, 0.16)
            row._dash = Line(points=(0, 0, 0, 0), width=dp(0.9))

        def _sync(*_a):
            y = row.top - dp(1)
            row._dash.points = (row.x, y, row.right, y)

        row.bind(pos=_sync, size=_sync)
        row.add_widget(L("合计 / 每米", 12, DIM))
        v = fit(L("￥%.2f" % total, 16, AMBER, bold=True, align="right"), 2)
        row.add_widget(v)
        return row


# ============================================================
# 设置界面
# ============================================================
S_FIELDS = [
    ("板材", "201 不锈钢板材", ("sheet_price", "201")),
    ("板材", "304 不锈钢板材", ("sheet_price", "304")),
    ("板材", "碳钢板材", ("sheet_price", "carbon")),
    ("链条", "201 · 25.4", ("chain_price", "201", "25.4")),
    ("链条", "201 · 31.75", ("chain_price", "201", "31.75")),
    ("链条", "201 · 38.1", ("chain_price", "201", "38.1")),
    ("链条", "201 · 50.8", ("chain_price", "201", "50.8")),
    ("链条", "201 · 假两寸", ("chain_price", "201", "假两寸")),
    ("链条", "304 · 25.4", ("chain_price", "304", "25.4")),
    ("链条", "304 · 31.75", ("chain_price", "304", "31.75")),
    ("链条", "304 · 38.1", ("chain_price", "304", "38.1")),
    ("链条", "304 · 50.8", ("chain_price", "304", "50.8")),
    ("链条", "304 · 假两寸", ("chain_price", "304", "假两寸")),
    ("链条", "碳钢 · 25.4", ("chain_price", "carbon", "25.4")),
    ("链条", "碳钢 · 31.75", ("chain_price", "carbon", "31.75")),
    ("链条", "碳钢 · 38.1", ("chain_price", "carbon", "38.1")),
    ("链条", "碳钢 · 50.8", ("chain_price", "carbon", "50.8")),
    ("链条", "碳钢 · 假两寸", ("chain_price", "carbon", "假两寸")),
    ("链宽", "节距 25.4", ("chain_width", "25.4")),
    ("链宽", "节距 31.75", ("chain_width", "31.75")),
    ("链宽", "节距 38.1", ("chain_width", "38.1")),
    ("链宽", "节距 50.8", ("chain_width", "50.8")),
    ("链宽", "节距 假两寸", ("chain_width", "假两寸")),
    ("常数", "密度系数 (density)", ("const", "density")),
    ("常数", "穿杆直径系数 (pin_pi)", ("const", "pin_pi")),
    ("常数", "穿杆重量系数 (pin_coef)", ("const", "pin_coef")),
    ("常数", "穿杆工费 (pin_fee)", ("const", "pin_fee")),
    ("常数", "挡板高度加值 (flight_margin)", ("const", "flight_margin")),
    ("常数", "人工成本/片 (labor, 0=不计)", ("const", "labor")),
    ("加工", "薄板档最大厚度 (≤)", ("cut", "band1", "max_t")),
    ("加工", "薄板档平费 (flat_fee)", ("cut", "band1", "flat_fee")),
    ("加工", "薄板档平费最大宽度", ("cut", "band1", "flat_w")),
    ("加工", "中板档最大厚度 (≤)", ("cut", "band2", "max_t")),
    ("加工", "中板档平费 (flat_fee)", ("cut", "band2", "flat_fee")),
    ("加工", "中板档平费最大宽度", ("cut", "band2", "flat_w")),
    ("加工", "中板档公式最小宽度 (formula_w)", ("cut", "band2", "formula_w")),
    ("加工", "中板档公式加价 (formula_extra)", ("cut", "band2", "formula_extra")),
    ("加工", "厚板档平费 (flat_fee)", ("cut", "band3", "flat_fee")),
    ("加工", "厚板档平费最大宽度", ("cut", "band3", "flat_w")),
    ("加工", "厚板档公式加价 (formula_extra)", ("cut", "band3", "formula_extra")),
    ("加工", "冲床手动值 (等号关闭时)", ("punch", "manual_fee")),
    ("加工", "焊接平费最大直径 (max_d)", ("weld", "max_d")),
    ("加工", "焊接小直径费 (fee_small)", ("weld", "fee_small")),
    ("加工", "焊接大直径费 (fee_large)", ("weld", "fee_large")),
    ("冲孔", "自动计算最大板厚 (auto_max_t)", ("punch_hole", "auto_max_t")),
    ("冲孔", "自动平费最大宽度 (auto_flat_w)", ("punch_hole", "auto_flat_w")),
    ("冲孔", "自动平费 (auto_flat_fee)", ("punch_hole", "auto_flat_fee")),
    ("配件", "横挡板工费 (cross_fee)", ("accessory", "cross_fee")),
    ("配件", "侧挡板工费 (side_fee)", ("accessory", "side_fee")),
    ("配件", "滚珠单价 (ball)", ("accessory", "ball")),
    ("配件", "支轮单价 (wheel)", ("accessory", "wheel")),
]

S_BOOL = [("加工", "冲床费用=切割费用", ("punch", "equals_cut"))]

S_FORMULAS = [
    ("板价格", ("formulas", "plate"),
     "变量: pin_d pitch thickness width sheet_price density pin_pi cut_fee punch_fee weld_fee"),
    ("穿杆价格", ("formulas", "pin"),
     "变量: pin_d width chain_width sheet_price pin_coef pin_fee"),
    ("横挡板价格", ("formulas", "cross"),
     "变量: length height thickness sheet_price density flight_margin cross_fee"),
    ("侧挡板价格", ("formulas", "side"),
     "变量: pitch chain_width height thickness sheet_price density flight_margin side_fee"),
    ("切割·薄板档平费", ("formulas", "cut_b1_flat"), "变量: flat_fee"),
    ("切割·薄板档超宽", ("formulas", "cut_b1_wide"), "变量: width"),
    ("切割·中板档平费", ("formulas", "cut_b2_flat"), "变量: flat_fee"),
    ("切割·中板档超宽", ("formulas", "cut_b2_wide"), "变量: width formula_extra"),
    ("切割·厚板档平费", ("formulas", "cut_b3_flat"), "变量: flat_fee"),
    ("切割·厚板档超宽", ("formulas", "cut_b3_wide"), "变量: width formula_extra"),
    ("焊接·小直径", ("formulas", "weld_small"), "变量: fee_small"),
    ("焊接·大直径", ("formulas", "weld_large"), "变量: fee_large"),
    ("冲孔·自动平费", ("formulas", "punch_auto_flat"), "变量: auto_flat_fee"),
    ("冲孔·自动超宽", ("formulas", "punch_auto_wide"), "变量: width"),
    ("每米总价", ("formulas", "total"),
     "变量: per_meter plate pin chain_total side_total cross_total punch ball_total wheel_total labor"),
]


def get_nested(d, path):
    for k in path:
        d = d[k]
    return d


def set_nested(d, path, value):
    for k in path[:-1]:
        d = d.setdefault(k, {})
    d[path[-1]] = value


class SettingsScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        with self.canvas.before:
            Color(*BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self._bg, "pos", self.pos),
                  size=lambda *a: setattr(self._bg, "size", self.size))
        self.build_ui()

    def build_ui(self):
        outer = BoxLayout(orientation="vertical")
        self.add_widget(outer)
        self.appbar = AppBar("设置", "常数与公式 · 改完点保存", "",
                             on_back=lambda: setattr(self.manager, "current", "main"))
        outer.add_widget(self.appbar)

        from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
        tp = TabbedPanel(do_default_tab=False, size_hint_y=1.0, tab_width=dp(46))
        outer.add_widget(tp)
        self.tp = tp

        self.entries = {}
        self.bools = {}
        self.formula_entries = {}
        self.formula_maps = {}

        tabs = {}
        for tab, label, path in S_FIELDS:
            if tab not in tabs:
                tabs[tab] = self._make_tab(tp, tab)
            ti = Input(str(get_nested(self.app.settings, path)), "", 14, "right")
            ti.height = dp(34)
            ti.size_hint_x = None
            ti.width = dp(104)
            self.entries[path] = ti
            row = Row(40, divider=True)
            row.add_widget(L(label, 12.5, (0.72, 0.76, 0.80, 1)))
            row.add_widget(ti)
            tabs[tab].add_widget(row)

        for tab, label, path in S_BOOL:
            if tab not in tabs:
                tabs[tab] = self._make_tab(tp, tab)
            sw = MiniSwitch(bool(get_nested(self.app.settings, path)))
            self.bools[path] = sw
            row = Row(44, divider=True)
            row.add_widget(L(label, 12.5, (0.72, 0.76, 0.80, 1)))
            row.add_widget(sw)
            tabs[tab].add_widget(row)

        ftab = self._make_tab(tp, "公式")
        for label, path, hint in S_FORMULAS:
            box = BoxLayout(orientation="vertical", spacing=dp(3),
                            size_hint_y=None, padding=[0, dp(8), 0, dp(8)])
            box.bind(minimum_height=box.setter("height"))
            ti = TextInput(text=str(get_nested(self.app.settings, path)),
                           multiline=True, size_hint_y=None, height=dp(58),
                           font_size=sp(12), font_name="CJK",
                           foreground_color=TXT, background_color=(0, 0, 0, 0),
                           cursor_color=AMBER, padding=[dp(9), dp(8)])
            self.formula_entries[path] = ti
            _register_input(ti)
            map_lbl = L("", 10, OKC)
            map_lbl.size_hint_y = None
            map_lbl.height = dp(0)
            self.formula_maps[path] = map_lbl
            ti.bind(text=lambda *a, p=path: self.update_formula_map(p))
            ti.bind(text=self._no_newline)
            box.add_widget(L(label, 12.5, TXT, bold=True))
            box.add_widget(L(hint, 9.5, DIM2))
            box.add_widget(ti)
            box.add_widget(map_lbl)
            ftab.add_widget(box)

        btns = BottomBar()
        btns.height = dp(72)
        b_back = Ghost("返回")
        b_back.bind(on_release=lambda *a: setattr(self.manager, "current", "main"))
        btns.add_widget(b_back)
        b_reset = Ghost("恢复默认")
        b_reset.bind(on_release=lambda *a: self.on_defaults())
        btns.add_widget(b_reset)
        b_save = CTA("保存设置", "")
        b_save.bind(on_release=lambda *a: self.on_save())
        btns.add_widget(b_save)
        outer.add_widget(btns)
        self.refresh_maps()

    def _make_tab(self, tp, title):
        from kivy.uix.tabbedpanel import TabbedPanelItem
        item = TabbedPanelItem(text=title, font_size=sp(12))
        sc = ScrollView()
        grid = GridLayout(cols=1, spacing=dp(0), padding=[dp(14), dp(6), dp(14), dp(16)],
                          size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        sc.add_widget(grid)
        item.add_widget(sc)
        tp.add_widget(item)
        return grid

    # ---------- 变量对照 ----------
    def _base_env(self):
        from chainplate_calc import cut_fee, punch_fee, weld_fee
        s = self.app.settings
        m = self.app.main_screen
        try:
            w = float(m.in_width.text); t = float(m.in_thick.text)
            d = float(m.in_pin_d.text)
        except ValueError:
            w, t, d = 500.0, 2.0, 8.0
        from chainplate_calc import PITCH_VALUE
        pitch = PITCH_VALUE[m.pitch()]
        mat = MATERIAL_KEY.get(m.sp_plate.text, m.sp_plate.text)
        return {
            "width": w, "thickness": t, "pin_d": d, "pitch": pitch,
            "chain_width": chain_width_of(m.pitch(), s),
            "sheet_price": s["sheet_price"][mat],
            "density": s["const"]["density"], "pin_pi": s["const"]["pin_pi"],
            "pin_coef": s["const"]["pin_coef"], "pin_fee": s["const"]["pin_fee"],
            "flight_margin": s["const"]["flight_margin"], "labor": s["const"]["labor"],
            "cut_fee": cut_fee(t, w, s), "punch_fee": punch_fee(t, w, s),
            "weld_fee": weld_fee(d, s),
            "cross_fee": s["accessory"]["cross_fee"], "side_fee": s["accessory"]["side_fee"],
            "per_meter": 1000.0 / pitch,
        }

    def slot_env(self, slot):
        env = self._base_env()
        s = self.app.settings
        if slot in ("cut_b1_flat", "cut_b1_wide"):
            env["flat_fee"] = s["cut"]["band1"]["flat_fee"]
        elif slot in ("cut_b2_flat", "cut_b2_wide"):
            env["flat_fee"] = s["cut"]["band2"]["flat_fee"]
            env["formula_extra"] = s["cut"]["band2"]["formula_extra"]
        elif slot in ("cut_b3_flat", "cut_b3_wide"):
            env["flat_fee"] = s["cut"]["band3"]["flat_fee"]
            env["formula_extra"] = s["cut"]["band3"]["formula_extra"]
        elif slot in ("weld_small", "weld_large"):
            env["fee_small"] = s["weld"]["fee_small"]
            env["fee_large"] = s["weld"]["fee_large"]
            env["max_d"] = s["weld"]["max_d"]
        elif slot in ("punch_auto_flat", "punch_auto_wide"):
            env["auto_flat_fee"] = s["punch_hole"]["auto_flat_fee"]
        elif slot == "total":
            m = self.app.main_screen
            try:
                params = {"pitch": m.pitch(),
                          "plate_mat": MATERIAL_KEY.get(m.sp_plate.text, m.sp_plate.text),
                          "chain_mat": MATERIAL_KEY.get(m.sp_chain.text, m.sp_chain.text),
                          "pin_mat": MATERIAL_KEY.get(m.sp_pin.text, m.sp_pin.text),
                          "width": float(m.in_width.text),
                          "thickness": float(m.in_thick.text),
                          "pin_d": float(m.in_pin_d.text),
                          "cross": None, "side": None, "punch": None,
                          "ball_rows": None, "wheel_rows": None}
                r = compute(params, s)
                env.update({"per_meter": r["per_meter"], "plate": r["plate"]["total"],
                            "pin": r["pin"]["total"], "chain_total": r["chain"]["total"],
                            "side_total": 0.0, "cross_total": 0.0, "punch": 0.0,
                            "ball_total": 0.0, "wheel_total": 0.0})
            except Exception:
                pass
        return env

    def _no_newline(self, ti, text):
        if "\n" in text or "\r" in text:
            ti.text = text.replace("\r", " ").replace("\n", " ")

    def update_formula_map(self, path):
        slot = path[-1]
        expr = self.formula_entries[path].text
        vs = formula_vars(expr)
        env = self.slot_env(slot)
        lines = []
        for v in vs:
            name, src = VAR_NAMES.get(v, (v, "自定义"))
            val = env.get(v)
            val_s = ("%g" % val) if isinstance(val, (int, float)) else str(val)
            lines.append("%s = %s [%s] = %s" % (v, name, src, val_s))
        lbl = self.formula_maps[path]
        lbl.text = ("变量对照:\n" + "\n".join(lines)) if lines else "变量对照: (无变量)"
        lbl.height = dp(14) * (len(lines) + 1) if lines else dp(14)

    def refresh_maps(self):
        for path in self.formula_maps:
            self.update_formula_map(path)

    # ---------- 保存 ----------
    def on_save(self):
        s = default_settings()
        errs = []
        for path, ti in self.entries.items():
            raw = ti.text.strip()
            try:
                set_nested(s, path, float(raw))
            except ValueError:
                errs.append("%s = %r 不是有效数字" % ("→".join(map(str, path)), raw))
        for path, sw in self.bools.items():
            set_nested(s, path, bool(sw.active))
        for path, ti in self.formula_entries.items():
            raw = ti.text.strip()
            set_nested(s, path, raw)
            try:
                eval_expr(raw, SAMPLE_ENV)
            except ValueError as e:
                errs.append("公式[%s]: %s" % (path[-1], e))
        if errs:
            popup_msg("\n".join(errs))
            return
        self.app.settings = s
        try:
            os.makedirs(os.path.dirname(self.app.settings_path), exist_ok=True)
            save_settings(s, self.app.settings_path)
        except OSError as e:
            popup_msg("保存失败: %s" % e)
            return
        self.app.main_screen.refresh_info()
        self.app.main_screen.refresh_acc_titles()
        self.app.main_screen._update_punch_hint()
        self.refresh_maps()
        popup_msg("设置已保存并生效")

    def on_defaults(self):
        d = default_settings()
        for path, ti in self.entries.items():
            ti.text = str(get_nested(d, path))
        for path, sw in self.bools.items():
            sw.active = bool(get_nested(d, path))
        for path, ti in self.formula_entries.items():
            ti.text = str(get_nested(d, path))


def popup_msg(text, title=""):
    content = BoxLayout(padding=dp(14), orientation="vertical")
    lbl = L(text, 14, TXT, align="left", valign="top")
    lbl.size_hint_y = None
    lbl.bind(texture_size=lambda i, v: setattr(i, "height", v[1]))
    sc = ScrollView()
    sc.add_widget(lbl)
    content.add_widget(sc)
    content.add_widget(Widget(size_hint_y=None, height=dp(10)))
    btn = CTA("确定", "")
    btn.height = dp(44)
    content.add_widget(btn)
    p = Popup(title=title, content=content, size_hint=(0.9, 0.5))
    btn.bind(on_release=lambda *a: p.dismiss())
    p.open()


# ============================================================
class ChainPlateApp(App):
    title = "链板成本计算器"

    def build(self):
        data_dir = os.environ.get("CHAINPLATE_DATA_DIR") or self.user_data_dir
        self.settings_path = os.path.join(data_dir, "settings.json")
        self.state_path = os.path.join(data_dir, "ui_state.json")
        try:
            os.makedirs(data_dir, exist_ok=True)
        except OSError:
            pass
        if not os.path.exists(self.settings_path):
            try:
                save_settings(default_settings(), self.settings_path)
            except OSError:
                pass
        self.settings = load_settings(self.settings_path)
        sm = ScreenManager()
        self.main_screen = MainScreen(self, name="main")
        self.result_screen = ResultScreen(self, name="result")
        self.settings_screen = SettingsScreen(self, name="settings")
        sm.add_widget(self.main_screen)
        sm.add_widget(self.result_screen)
        sm.add_widget(self.settings_screen)
        sm.current = "main"
        self.main_screen.restore_state(self._load_state())
        Window.bind(on_key_down=self._on_key_down)
        return sm

    def _load_state(self):
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_state(self):
        try:
            st = self.main_screen.collect_state()
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(st, f, ensure_ascii=False)
        except Exception:
            pass

    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        if key == 27 and self.root is not None:
            if self.root.current == "settings":
                self.root.current = "main"
                return True
            if self.root.current == "result":
                self.root.current = "main"
                return True
        return False

    def on_pause(self):
        self.save_state()
        return True

    def on_resume(self):
        pass

    def on_stop(self):
        self.save_state()


if __name__ == "__main__":
    if os.environ.get("KIVY_SMOKE"):
        app = ChainPlateApp()
        Clock.schedule_once(lambda *a: app.stop(), 2.0)
        app.run()
        print("SMOKE OK")
    else:
        ChainPlateApp().run()
