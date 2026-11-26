# -*- coding: utf-8 -*-
"""一个极简的 Kivy 运行时替身 (只为本机预览/回归用, 不进 APK)。

目的: 在没有 Kivy / 没有网络的机器上
  1) 真正执行 main.py 的 build_ui(), 抓出 API 用法错误;
  2) 用同一套布局规则算出每个控件的矩形, 再用 Pillow 画成图片, 肉眼校版面;
  3) 让 tests/ui_smoke.py 这种"驱动真实控件"的测试原样跑起来。

只实现 main.py 用到的那一小部分 API。
"""
import math
import os

__version__ = "2.3.1+shim"

# ============================================================
# properties
# ============================================================
class Property:
    def __init__(self, default=None, **kw):
        self.default = default
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.name, self.default)

    def __set__(self, obj, value):
        old = obj.__dict__.get(self.name, self.default)
        obj.__dict__[self.name] = value
        try:
            same = old == value
        except Exception:
            same = False
        if not same:
            obj.dispatch(self.name, value)


class NumericProperty(Property):
    def __init__(self, default=0, **kw):
        super().__init__(float(default))

    def __set__(self, obj, value):
        super().__set__(obj, float(value))


class StringProperty(Property):
    def __init__(self, default="", **kw):
        super().__init__(default)


class BooleanProperty(Property):
    def __init__(self, default=False, **kw):
        super().__init__(bool(default))

    def __set__(self, obj, value):
        super().__set__(obj, bool(value))


class ListProperty(Property):
    def __init__(self, default=None, **kw):
        super().__init__(list(default or []))

    def __set__(self, obj, value):
        super().__set__(obj, list(value))


class DictProperty(Property):
    def __init__(self, default=None, **kw):
        super().__init__(dict(default or {}))


class ObjectProperty(Property):
    pass


class OptionProperty(StringProperty):
    def __init__(self, default=None, options=None, **kw):
        super().__init__(default if default is not None else (options or [""])[0])
        self.options = list(options or [])

    def __set__(self, obj, value):
        if self.options and value not in self.options:
            return
        super().__set__(obj, value)


class AliasProperty(Property):
    def __init__(self, getter=None, setter=None, **kw):
        super().__init__(None)
        self.getter = getter
        self.setter = setter

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return self.getter(obj)

    def __set__(self, obj, value):
        if self.setter is None:
            return
        self.setter(obj, value)
        obj.dispatch(self.name, value)


def bind_alias(name, getter, setter=None):
    return AliasProperty(getter, setter)


# ============================================================
# event
# ============================================================
class EventDispatcher:
    def __init__(self, **kwargs):
        object.__setattr__(self, "_bindings", {})
        for k, v in kwargs.items():
            try:
                setattr(self, k, v)
            except Exception:
                pass

    def bind(self, **kw):
        for k, cb in kw.items():
            self._bindings.setdefault(k, []).append(cb)
        return self

    def unbind(self, **kw):
        for k in kw:
            self._bindings.pop(k, None)
        return self

    def fbind(self, **kw):
        return self.bind(**kw)

    def dispatch(self, name, value=None):
        for cb in list(self._bindings.get(name, [])):
            try:
                cb(self, value)
            except TypeError:
                cb(self, value)

    def register_event_type(self, name):
        pass

    def get(self, key):
        return getattr(self, key, None)


# ============================================================
# graphics
# ============================================================
_CURRENT = []


class Instruction:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        if _CURRENT:
            _CURRENT[-1].children.append(self)

    def __repr__(self):
        return "<%s %r>" % (type(self).__name__, self.__dict__)


class Color(Instruction):
    def __init__(self, r=1.0, g=1.0, b=1.0, a=1.0):
        super().__init__(rgba=(r, g, b, a))
        self.rgba = (r, g, b, a)


class Rectangle(Instruction):
    def __init__(self, pos=(0, 0), size=(0, 0), **kw):
        super().__init__(pos=list(pos), size=list(size), **kw)


class Ellipse(Instruction):
    def __init__(self, pos=(0, 0), size=(0, 0), **kw):
        super().__init__(pos=list(pos), size=list(size), angle_start=0, angle_end=360, **kw)


class RoundedRectangle(Instruction):
    def __init__(self, pos=(0, 0), size=(0, 0), radius=(0,), **kw):
        super().__init__(pos=list(pos), size=list(size), radius=list(radius), **kw)


class Line(Instruction):
    def __init__(self, points=None, width=1.0, circle=None, rounded_rectangle=None,
                 ellipse=None, **kw):
        super().__init__(points=list(points or []), width=width, circle=circle,
                         rounded_rectangle=rounded_rectangle, ellipse=ellipse, **kw)


class InstructionGroup:
    def __init__(self, *children):
        self.children = list(children)

    def add(self, *instr):
        self.children.extend(instr)

    def insert(self, index, instr):
        self.children.insert(index, instr)

    def remove(self, instr):
        if instr in self.children:
            self.children.remove(instr)

    def clear(self):
        self.children = []

    def __enter__(self):
        _CURRENT.append(self)
        return self

    def __exit__(self, *exc):
        _CURRENT.pop()
        return False


class Canvas(InstructionGroup):
    def __init__(self):
        super().__init__()
        self.before = InstructionGroup()
        self.after = InstructionGroup()

    def __enter__(self):
        _CURRENT.append(self)
        return self

    def __exit__(self, *exc):
        _CURRENT.pop()
        return False


class PushMatrix(Instruction):
    pass


class PopMatrix(Instruction):
    pass


# ============================================================
# metrics / config / clock / clipboard / fonts
# ============================================================
DENSITY = 1.0


def dp(x):
    return float(x) * DENSITY


def sp(x):
    return float(x) * DENSITY


class Config:
    _d = {}

    @classmethod
    def set(cls, section, key, value):
        cls._d[(section, key)] = value

    @classmethod
    def get(cls, section, key, default=None):
        return cls._d.get((section, key), default)


class Clock:
    _events = []
    _t = 0.0

    @classmethod
    def schedule_once(cls, cb, delay=0.0):
        cls._events.append((cls._t + float(delay or 0.0), cb))
        return True

    @classmethod
    def schedule_interval(cls, cb, interval=0.0):
        return True

    @classmethod
    def unschedule(cls, cb):
        cls._events = [e for e in cls._events if e[1] is not cb]

    @classmethod
    def tick(cls, dt=0.1):
        cls._t += dt
        due = [e for e in cls._events if e[0] <= cls._t]
        cls._events = [e for e in cls._events if e[0] > cls._t]
        for _t, cb in due:
            cb(dt)


class Clipboard:
    text = ""

    @classmethod
    def copy(cls, text=""):
        cls.text = text

    @classmethod
    def paste(cls, *a):
        return cls.text


class LabelBase:
    fonts = {}

    @classmethod
    def register(cls, name="Roboto", fn_regular=None, fn_bold=None, **kw):
        cls.fonts[name] = (fn_regular, fn_bold)

    @classmethod
    def get(cls, name):
        return cls.fonts.get(name)


class Window(EventDispatcher):
    size = (360.0, 740.0)
    softinput_mode = ""
    width = 360.0
    height = 740.0

    def __init__(self):
        super().__init__()

    @classmethod
    def bind(cls, **kw):
        return cls

    @classmethod
    def screenshot(cls, *a, **kw):
        return None


window = Window()


def Logger_(*a, **kw):
    pass


# ============================================================
# widgets
# ============================================================
class Widget(EventDispatcher):
    size = ListProperty([100, 100])
    pos = ListProperty([0, 0])
    opacity = NumericProperty(1.0)
    disabled = BooleanProperty(False)

    def __init__(self, **kw):
        self.children = []
        self.parent = None
        self.canvas = Canvas()
        self.ids = {}
        self.size_hint_x = 1.0
        self.size_hint_y = 1.0
        self.padding = [0, 0, 0, 0]
        self.spacing = 0
        self.name = ""
        self.manager = None
        self.text = ""
        self._visible = True
        super().__init__()
        self.size = [100, 100]
        self.pos = [0, 0]
        for k, v in kw.items():
            setattr(self, k, v)

    # -- 几何 --
    @property
    def width(self):
        return self.size[0]

    @width.setter
    def width(self, v):
        self.size = [float(v), self.size[1]]

    @property
    def height(self):
        return self.size[1]

    @height.setter
    def height(self, v):
        self.size = [self.size[0], float(v)]

    @property
    def x(self):
        return self.pos[0]

    @x.setter
    def x(self, v):
        self.pos = [float(v), self.pos[1]]

    @property
    def y(self):
        return self.pos[1]

    @y.setter
    def y(self, v):
        self.pos = [self.pos[0], float(v)]

    @property
    def right(self):
        return self.pos[0] + self.size[0]

    @property
    def top(self):
        return self.pos[1] + self.size[1]

    @property
    def center_x(self):
        return self.pos[0] + self.size[0] / 2.0

    @property
    def center_y(self):
        return self.pos[1] + self.size[1] / 2.0

    def collide_point(self, x, y):
        return (self.pos[0] <= x <= self.right) and (self.pos[1] <= y <= self.top)

    # -- 树 --
    def add_widget(self, w, index=0):
        if w.parent is not None:
            w.parent.remove_widget(w)
        w.parent = self
        if index is None or index >= len(self.children):
            self.children.append(w)
        else:
            self.children.insert(index, w)
        self._children_changed()

    def remove_widget(self, w):
        if w in self.children:
            self.children.remove(w)
            w.parent = None
            self._children_changed()

    def clear_widgets(self, *a):
        for c in list(self.children):
            c.parent = None
        self.children = []
        self._children_changed()

    def _children_changed(self):
        self.dispatch("children", self.children)

    def walk(self):
        yield self
        for c in list(self.children):
            for x in c.walk():
                yield x

    # -- 事件 --
    def on_touch_down(self, touch):
        if self.disabled:
            return False
        for c in reversed(self.children):
            if c.on_touch_down(touch):
                return True
        return False

    def do_layout(self, *a):
        pass


def _pad4(p):
    if isinstance(p, (int, float)):
        return [float(p)] * 4
    if len(p) == 2:
        return [float(p[0]), float(p[1]), float(p[0]), float(p[1])]
    return [float(x) for x in p]


class BoxLayout(Widget):
    orientation = "horizontal"

    def __init__(self, **kw):
        super().__init__(**kw)
        if "orientation" in kw:
            self.orientation = kw["orientation"]

    def _intrinsic(self, avail_w):
        p = _pad4(self.padding)
        ch = [c for c in self.children]
        n = len(ch)
        if not n:
            return max(p[1] + p[3], 0)
        if self.orientation == "vertical":
            total = p[1] + p[3] + self.spacing * (n - 1)
            for c in ch:
                total += _height_of(c, avail_w - p[0] - p[2])
            return total
        total = p[0] + p[2] + self.spacing * (n - 1)
        for c in ch:
            total += _width_of(c, avail_w)
        return max(total, 0)

    @property
    def minimum_height(self):
        return self._intrinsic(self.size[0])

    @property
    def minimum_width(self):
        p = _pad4(self.padding)
        if self.orientation != "horizontal":
            return p[0] + p[2] + max([_width_of(c, self.size[0]) for c in self.children] or [0])
        total = p[0] + p[2] + self.spacing * max(0, len(self.children) - 1)
        for c in self.children:
            total += _width_of(c, self.size[0])
        return total


class GridLayout(Widget):
    cols = 1
    rows = 0

    def __init__(self, **kw):
        super().__init__(**kw)
        if "cols" in kw:
            self.cols = int(kw["cols"])

    def _rows(self):
        return int(math.ceil(len(self.children) / float(self.cols or 1)))

    def _intrinsic(self, avail_w):
        p = _pad4(self.padding)
        ch = self.children
        n = len(ch)
        cols = self.cols or 1
        rows = int(math.ceil(n / float(cols)))
        if not rows:
            return max(p[1] + p[3], 0)
        inner_w = (avail_w - p[0] - p[2] - self.spacing * (cols - 1)) / float(cols)
        total = p[1] + p[3] + self.spacing * (rows - 1)
        for r in range(rows):
            row = ch[r * cols:(r + 1) * cols]
            total += max([_height_of(c, max(inner_w, 1)) for c in row] or [0])
        return total

    @property
    def minimum_height(self):
        return self._intrinsic(self.size[0])

    @property
    def minimum_width(self):
        return self.size[0]


class Label(Widget):
    text = StringProperty("")
    font_size = NumericProperty(14)
    color = ListProperty([1, 1, 1, 1])
    bold = BooleanProperty(False)
    halign = "left"
    valign = "middle"
    markup = BooleanProperty(False)
    outline_width = NumericProperty(0)
    outline_color = ListProperty([1, 1, 1, 1])
    font_name = StringProperty("Roboto")
    shorten = BooleanProperty(False)
    _text_size = None

    def __init__(self, **kw):
        self._text_size = None
        super().__init__(**kw)
        if "text" in kw:
            self.text = kw["text"]
        if "text_size" in kw:
            self.text_size = kw["text_size"]
        if "font_size" in kw:
            self.font_size = kw["font_size"]
        if "color" in kw:
            self.color = list(kw["color"])
        if "halign" in kw:
            self.halign = kw["halign"]
        if "valign" in kw:
            self.valign = kw["valign"]
        if "bold" in kw:
            self.bold = kw["bold"]
        if "size_hint_y" in kw and kw["size_hint_y"] is None:
            self.size = [self.size[0], self._tex_h()[1]]
        self.bind(text=self._on_text)

    @property
    def text_size(self):
        return self._text_size if self._text_size else (self.size[0], None)

    @text_size.setter
    def text_size(self, v):
        self._text_size = v

    def _wrap_w(self):
        ts = self._text_size
        if ts and ts[0]:
            return float(ts[0])
        if self.size_hint_x is not None and self.size_hint_x != 0:
            if self.parent is not None and self.parent.size[0]:
                return max(10.0, self.parent.size[0] * self.size_hint_x)
        return max(10.0, self.size[0])

    def _tex_h(self):
        w = self._wrap_w()
        fs = max(self.font_size, 1.0)
        lines = 1
        cur = 0.0
        for ch in (self.text or " "):
            if ch == "\n":
                lines += 1
                cur = 0.0
                continue
            cw = fs if ord(ch) > 0x2E80 else fs * 0.55
            if cur + cw > w:
                lines += 1
                cur = cw
            else:
                cur += cw
        return (w, lines * fs * 1.42)

    @property
    def texture_size(self):
        return self._tex_h()

    def _on_text(self, *a):
        if self.size_hint_y is None:
            self.size = [self.size[0], self._tex_h()[1]]
        self.dispatch("texture_size", self._tex_h())


class ButtonBehavior:
    state = StringProperty("normal")
    _down = False

    def on_touch_down(self, touch):
        if self.disabled:
            return False
        if self.collide_point(*touch.pos):
            self._down = True
            self._do_press()
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self._down:
            self._down = False
            self._do_release()
            self.dispatch("on_release", None)
            return True
        return super().on_touch_up(touch)

    def _do_press(self):
        pass

    def _do_release(self):
        pass


class Button(ButtonBehavior, Widget):
    text = StringProperty("")
    font_size = NumericProperty(14)
    color = ListProperty([1, 1, 1, 1])
    background_normal = StringProperty("")
    background_down = StringProperty("")
    background_color = ListProperty([1, 1, 1, 1])
    halign = "center"
    valign = "middle"
    bold = BooleanProperty(False)
    size_hint_x = 1.0
    size_hint_y = 1.0
    _text_size = None

    def __init__(self, **kw):
        self.background_color = [1, 1, 1, 1]
        super().__init__(**kw)
        for k in ("text", "font_size", "color", "background_normal",
                  "background_down", "background_color", "halign", "bold"):
            if k in kw:
                v = kw[k]
                if k == "color" or k == "background_color":
                    v = list(v)
                setattr(self, k, v)

    @property
    def text_size(self):
        return (self.size[0], None)

    @text_size.setter
    def text_size(self, v):
        pass

    @property
    def texture_size(self):
        return (self.size[0], self.font_size * 1.4)

    def on_touch_down(self, touch):
        if self.disabled:
            return False
        return ButtonBehavior.on_touch_down(self, touch)


class ToggleButton(Button):
    group = StringProperty("")
    _groups = {}

    def __init__(self, **kw):
        if "state" in kw and kw["state"] == "down":
            kw = dict(kw)
            self.__dict__["_pre_down"] = True
        super().__init__(**kw)
        g = self.group
        if g and self.state == "down":
            ToggleButton._groups[g] = self

    def _do_press(self):
        if self.group:
            other = ToggleButton._groups.get(self.group)
            if other is not None and other is not self:
                other.state = "normal"
            ToggleButton._groups[self.group] = self
        self.state = "down"

    def _do_release(self):
        if self.group:
            return
        self.state = "normal"

    def on_touch_up(self, touch):
        if self.group:
            if self._down:
                self._down = False
                self._do_release_group_press()
            return ButtonBehavior.on_touch_up(self, touch)
        return ButtonBehavior.on_touch_up(self, touch)

    def _do_release_group_press(self):
        # 同组按钮: 点已按下的不再弹起(Kivy 行为)
        self.state = self.state


class CheckBox(Widget):
    active = BooleanProperty(False)

    def __init__(self, **kw):
        super().__init__(**kw)
        if "active" in kw:
            self.active = bool(kw["active"])
        self.size = [dp(24), dp(24)]

    def on_touch_down(self, touch):
        if self.disabled:
            return False
        if self.collide_point(*touch.pos):
            self.active = not self.active
            return True
        return super().on_touch_down(touch)


class TextInput(Widget):
    text = StringProperty("")
    hint_text = StringProperty("")
    multiline = BooleanProperty(False)
    font_size = NumericProperty(14)
    input_filter = ObjectProperty(None)
    input_type = StringProperty("text")
    foreground_color = ListProperty([1, 1, 1, 1])
    background_color = ListProperty([0, 0, 0, 1])
    cursor_color = ListProperty([1, 1, 1, 1])
    font_name = StringProperty("Roboto")
    halign = StringProperty("left")
    padding = ListProperty([0, 0, 0, 0])
    readonly = BooleanProperty(False)
    _focused = False

    def __init__(self, **kw):
        super().__init__(**kw)
        for k in ("text", "hint_text", "multiline", "font_size", "input_filter",
                  "input_type", "background_color", "cursor_color", "font_name", "halign"):
            if k in kw:
                setattr(self, k, kw[k])

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._focused = True
            self.dispatch("focus", True)
            return True
        return super().on_touch_down(touch)


class Spinner(Button):
    values = ListProperty([])
    sync_height = BooleanProperty(False)
    option_cls = None

    def __init__(self, **kw):
        super().__init__(**kw)
        if "values" in kw:
            self.values = list(kw["values"])


class SpinnerOption(Button):
    pass


class ScrollView(Widget):
    scroll_y = NumericProperty(1.0)
    bar_width = NumericProperty(2)
    do_scroll_x = BooleanProperty(False)
    do_scroll_y = BooleanProperty(True)

    def add_widget(self, w, index=0):
        super().add_widget(w, index)

    def scroll_to(self, *a, **kw):
        pass


class Screen(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)

    def on_enter(self):
        pass

    def on_leave(self):
        pass


class ScreenManager(Widget):
    current = StringProperty("")

    def __init__(self, **kw):
        super().__init__(**kw)
        if "current" in kw:
            self.current = kw["current"]

    def add_widget(self, w, index=0):
        super().add_widget(w, index)
        n = getattr(w, "name", "")
        if n and not self.current:
            self.current = n

    def _screens(self):
        return [c for c in self.children if isinstance(c, Screen)]

    def current_screen(self):
        for s in self._screens():
            if s.name == self.current:
                return s
        return self._screens()[0] if self._screens() else None

    def __getattr__(self, item):
        # .current 赋值时切屏: 这里只做属性访问兜底
        raise AttributeError(item)

    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)
        if key == "current":
            for s in self._screens():
                if s.name == value:
                    s.on_enter()
                    break


class Popup(Widget):
    def __init__(self, **kw):
        self.title = kw.pop("title", "")
        self.content = kw.pop("content", None)
        self.size_hint = kw.pop("size_hint", (1, 1))
        super().__init__(**kw)
        self.opened = False

    def open(self):
        self.opened = True

    def dismiss(self, *a):
        self.opened = False


class TabbedPanel(Widget):
    do_default_tab = BooleanProperty(True)
    tab_width = NumericProperty(100)
    default_tab = ObjectProperty(None)

    def __init__(self, **kw):
        super().__init__(**kw)

    def add_widget(self, w, index=0):
        super().add_widget(w, index)
        if self.default_tab is None:
            self.default_tab = w


class TabbedPanelItem(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)


# ============================================================
# 布局: 自底向上算高度, 自顶向下定位
# ============================================================
def _height_of(w, avail_w):
    """给一个控件在 avail_w 宽度下的自然高度。"""
    if getattr(w, "size_hint_y", 1) is None:
        h = w.size[1]
        if isinstance(w, (BoxLayout, GridLayout)):
            h = max(h, w._intrinsic(avail_w))
        return h
    if isinstance(w, (BoxLayout, GridLayout)):
        return w._intrinsic(avail_w)
    return w.size[1]


def _width_of(w, avail_w):
    if getattr(w, "size_hint_x", 1) is None:
        return w.size[0]
    return avail_w * float(getattr(w, "size_hint_x", 1) or 0)


def _place(w, x, y, width, height):
    w.size = [width, height]
    w.pos = [x, y]
    layout_children(w)


def layout_children(w):
    if isinstance(w, BoxLayout):
        _layout_box(w)
    elif isinstance(w, GridLayout):
        _layout_grid(w)
    elif isinstance(w, ScrollView):
        for c in w.children:
            _place(c, w.x, w.y, w.width, _height_of(c, w.width))
    elif isinstance(w, ScreenManager):
        for c in w.children:
            _place(c, w.x, w.y, w.width, w.height)
    elif isinstance(w, Screen):
        for c in w.children:
            _place(c, w.x, w.y, w.width, w.height)
    elif isinstance(w, Widget):
        for c in w.children:
            if getattr(c, "size_hint_y", 1) is not None or True:
                _place(c, w.x, w.y, _width_of(c, w.width), _height_of(c, w.width))


def _layout_box(w):
    p = _pad4(w.padding)
    ch = list(w.children)
    if not ch:
        return
    inner_w = max(1.0, w.width - p[0] - p[2])
    inner_h = max(1.0, w.height - p[1] - p[3])
    if w.orientation == "vertical":
        fixed = 0.0
        flex = []
        for c in ch:
            if getattr(c, "size_hint_y", 1) is None:
                fixed += _height_of(c, inner_w)
            else:
                flex.append(c)
        gaps = w.spacing * (len(ch) - 1)
        rest = max(0.0, inner_h - fixed - gaps)
        hs = {}
        if flex:
            weights = [float(getattr(c, "size_hint_y", 1) or 0) for c in flex]
            tw = sum(weights) or 1.0
            for c, wt in zip(flex, weights):
                hs[c] = rest * wt / tw
        y = w.top - p[3]
        for c in ch:
            h = _height_of(c, inner_w) if getattr(c, "size_hint_y", 1) is None else hs.get(c, 0.0)
            y -= h
            _place(c, w.x + p[0], y, inner_w, h)
            y -= w.spacing
    else:
        fixed = 0.0
        flex = []
        for c in ch:
            if getattr(c, "size_hint_x", 1) is None:
                fixed += _width_of(c, inner_w)
            else:
                flex.append(c)
        gaps = w.spacing * (len(ch) - 1)
        rest = max(0.0, inner_w - fixed - gaps)
        ws = {}
        if flex:
            weights = [float(getattr(c, "size_hint_x", 1) or 0) for c in flex]
            tw = sum(weights) or 1.0
            for c, wt in zip(flex, weights):
                ws[c] = rest * wt / tw
        x = w.x + p[0]
        for c in ch:
            wd = _width_of(c, inner_w) if getattr(c, "size_hint_x", 1) is None else ws.get(c, 0.0)
            _place(c, x, w.y + p[1], wd, max(1.0, w.height - p[1] - p[3]))
            x += wd + w.spacing


def _layout_grid(w):
    p = _pad4(w.padding)
    ch = list(w.children)
    if not ch:
        return
    cols = w.cols or 1
    rows = int(math.ceil(len(ch) / float(cols)))
    inner_w = max(1.0, w.width - p[0] - p[2])
    inner_h = max(1.0, w.height - p[1] - p[3])
    col_w = (inner_w - w.spacing * (cols - 1)) / float(cols)
    row_h = (inner_h - w.spacing * (rows - 1)) / float(rows)
    y = w.top - p[3]
    for r in range(rows):
        y -= row_h
        x = w.x + p[0]
        for c in ch[r * cols:(r + 1) * cols]:
            h = _height_of(c, col_w) if getattr(c, "size_hint_y", 1) is None else row_h
            _place(c, x, y, col_w, h)
            x += col_w + w.spacing
        y -= w.spacing


def layout_root(root, width, height):
    root.size = [width, height]
    root.pos = [0, 0]
    layout_children(root)


def collide(w, x, y):
    return w.pos[0] <= x <= w.right and w.pos[1] <= y <= w.top


# ============================================================
# App
# ============================================================
class App:
    title = ""
    root = None

    def build(self):
        return Widget()

    def run(self):
        if self.root is None:
            self.root = self.build()
        for _ in range(4):
            if not Clock._events:
                break
            Clock.tick(0.25)
        return self.root

    def stop(self, *a):
        pass
