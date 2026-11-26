# -*- coding: utf-8 -*-
"""对 _core 做 Kivy 语义修正(不重复贴整个文件)。

改动点:
  * size_hint=(x, y) 这种写法要拆成 size_hint_x / size_hint_y;
  * children 顺序: Kivy 里"后加的在前", add_widget 插入到 0;
  * 布局按 reversed(children); 自然高度/宽度要区分横竖(横排取最高, 竖排求和);
  * 普通 Widget 不摆子控件(只有 Layout 才摆);
  * ScreenManager 记住 manager;
  * EventDispatcher.setter(name);
  * TextInput.focus; center / center_x / center_y 可写。
"""
import math

from . import _core as C
from ._core import _pad4, _place

# ---------------------------------------------------------------- size_hint
_orig_widget_init = C.Widget.__init__


def _widget_init(self, **kw):
    sh = kw.pop("size_hint", None)
    self._fixed_h = "height" in kw
    self._fixed_w = "width" in kw
    _orig_widget_init(self, **kw)
    if sh is not None:
        self.size_hint_x, self.size_hint_y = sh


C.Widget.__init__ = _widget_init


def add_widget(self, w, index=0):
    if w.parent is not None:
        w.parent.remove_widget(w)
    w.parent = self
    self.children.insert(0 if index is None else index, w)
    self._children_changed()


def _kids(w):
    return list(reversed(w.children))


def _min_h(w, avail_w):
    """w 在 avail_w 宽度下至少要多高。"""
    if isinstance(w, C.GridLayout):
        p = _pad4(w.padding)
        ch = _kids(w)
        cols = w.cols or 1
        rows = int(math.ceil(len(ch) / float(cols))) if ch else 0
        if not rows:
            return p[1] + p[3]
        inner_w = max(1.0, avail_w - p[0] - p[2])
        col_w = max(1.0, (inner_w - w.spacing * (cols - 1)) / float(cols))
        total = p[1] + p[3] + w.spacing * (rows - 1)
        for r in range(rows):
            row = ch[r * cols:(r + 1) * cols]
            total += max([_height_of(c, col_w) for c in row] or [0])
        return total
    if isinstance(w, C.BoxLayout):
        p = _pad4(w.padding)
        ch = _kids(w)
        if not ch:
            return p[1] + p[3]
        if w.orientation == "vertical":
            total = p[1] + p[3] + w.spacing * (len(ch) - 1)
            for c in ch:
                total += _height_of(c, max(1.0, avail_w - p[0] - p[2]))
            return total
        return p[1] + p[3] + max([_height_of(c, avail_w) for c in ch] or [0])
    if isinstance(w, (C.Screen, C.ScrollView, C.ScreenManager)):
        return w.size[1]
    return w.size[1]


def _min_w(w, avail_w):
    if isinstance(w, C.GridLayout):
        return w.size[0]
    if isinstance(w, C.BoxLayout):
        p = _pad4(w.padding)
        ch = _kids(w)
        if not ch:
            return p[0] + p[2]
        if w.orientation == "horizontal":
            total = p[0] + p[2] + w.spacing * (len(ch) - 1)
            for c in ch:
                total += _width_of(c, avail_w)
            return total
        return p[0] + p[2] + max([_width_of(c, avail_w) for c in ch] or [0])
    return w.size[0]


def _height_of(w, avail_w):
    if getattr(w, "size_hint_y", 1) is None:
        # 绑过 minimum_height 的容器(卡片/结果列表)按内容撑高;
        # 没绑的(比如收起来的配件参数区 height=0)就用显式高度。
        if w._bindings.get("minimum_height"):
            return max(w.size[1], _min_h(w, avail_w))
        return w.size[1]
    return _min_h(w, avail_w)


def _width_of(w, avail_w):
    if getattr(w, "size_hint_x", 1) is None:
        return w.size[0]
    return avail_w * float(getattr(w, "size_hint_x", 1) or 0)


def _layout_box(w):
    p = _pad4(w.padding)
    ch = _kids(w)
    if not ch:
        return
    inner_w = max(1.0, w.width - p[0] - p[2])
    inner_h = max(1.0, w.height - p[1] - p[3])
    if w.orientation == "vertical":
        fixed, flex = 0.0, []
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
        fixed, flex = 0.0, []
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
    ch = _kids(w)
    if not ch:
        return
    cols = w.cols or 1
    rows = int(math.ceil(len(ch) / float(cols)))
    inner_w = max(1.0, w.width - p[0] - p[2])
    inner_h = max(1.0, w.height - p[1] - p[3])
    col_w = (inner_w - w.spacing * (cols - 1)) / float(cols)
    # 每行取该行最高子控件; 全是 flex 的行再平分剩下的高度
    heights, flex_rows = [], []
    for r in range(rows):
        row = ch[r * cols:(r + 1) * cols]
        fixed = [_height_of(c, col_w) for c in row if getattr(c, "size_hint_y", 1) is None]
        if fixed:
            heights.append(max(fixed))
        else:
            heights.append(None)
            flex_rows.append(r)
    used = sum(h for h in heights if h) + w.spacing * (rows - 1)
    left = max(0.0, inner_h - used)
    for r in flex_rows:
        heights[r] = left / max(1, len(flex_rows))
    y = w.top - p[3]
    for r in range(rows):
        rh = heights[r] or 0.0
        y -= rh
        x = w.x + p[0]
        for c in ch[r * cols:(r + 1) * cols]:
            h = _height_of(c, col_w) if getattr(c, "size_hint_y", 1) is None else rh
            _place(c, x, y, col_w, h)
            x += col_w + w.spacing
        y -= w.spacing


def layout_children(w):
    if isinstance(w, C.BoxLayout):
        _layout_box(w)
    elif isinstance(w, C.GridLayout):
        _layout_grid(w)
    elif isinstance(w, C.ScrollView):
        for c in w.children:
            _place(c, w.x, w.y, w.width, _height_of(c, w.width))
    elif isinstance(w, C.ScreenManager):
        for c in w.children:
            _place(c, w.x, w.y, w.width, w.height)
    elif isinstance(w, C.Screen):
        for c in w.children:
            _place(c, w.x, w.y, w.width, w.height)
    # 普通 Widget 不摆子控件(Kivy 行为)


def sm_add_widget(self, w, index=0):
    add_widget(self, w, index)
    w.manager = self
    n = getattr(w, "name", "")
    if n and not self.current:
        self.current = n


def setter(self, name):
    return lambda inst, value: setattr(self, name, value)


C.Widget.add_widget = add_widget
C.ScreenManager.add_widget = sm_add_widget
C.EventDispatcher.setter = setter
C.layout_children = layout_children
C._layout_box = _layout_box
C._layout_grid = _layout_grid
C.TextInput.focus = C.BooleanProperty(False)


# ---- Label: 显式给了 height 就不要被 texture 高度覆盖 ----
def _label_on_text(self, *a):
    if not getattr(self, "_fixed_h", False) and self.size_hint_y is None:
        self.size = [self.size[0], self._tex_h()[1]]
    self.dispatch("texture_size", self._tex_h())


C.Label._on_text = _label_on_text


# ---- center 可写 ----
def _cx_get(self):
    return self.pos[0] + self.size[0] / 2.0


def _cx_set(self, v):
    self.pos = [v - self.size[0] / 2.0, self.pos[1]]


def _cy_get(self):
    return self.pos[1] + self.size[1] / 2.0


def _cy_set(self, v):
    self.pos = [self.pos[0], v - self.size[1] / 2.0]


def _c_get(self):
    return (_cx_get(self), _cy_get(self))


def _c_set(self, v):
    self.pos = [v[0] - self.size[0] / 2.0, v[1] - self.size[1] / 2.0]


C.Widget.center_x = property(_cx_get, _cx_set)
C.Widget.center_y = property(_cy_get, _cy_set)
C.Widget.center = property(_c_get, _c_set)
