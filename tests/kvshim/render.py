# -*- coding: utf-8 -*-
"""把控件树画成 PNG(Kivy 替身专用, 只为在没装 Kivy 的机器上校版面)。

注意: Kivy 的 y 轴朝上, PIL 朝下, 所以所有纵坐标都要翻一次。
"""
import os

from PIL import Image, ImageDraw, ImageFont

from kivy import _core as C

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FONT = os.path.join(ROOT, "fonts", "simhei.ttf")
S = 2          # 2x 出图
_H = 0.0       # 画布高度(css px)


def _font(size):
    try:
        return ImageFont.truetype(FONT, max(1, int(round(size * S))))
    except Exception:
        return ImageFont.load_default()


def _px(v):
    return v * S


def _col(c, k=1.0):
    if c is None:
        return (255, 255, 255, 0)
    a = int(255 * min(1.0, max(0.0, (c[3] if len(c) > 3 else 1.0) * k)))
    return (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255), a)


def _box(w):
    """Kivy 矩形 → PIL 矩形 (l, t, r, b)。"""
    x, y = w.pos
    ww, hh = w.size
    return (_px(x), _px(_H - (y + hh)), _px(x + ww), _px(_H - y))


class Canvas:
    """PIL 的 ImageDraw 不会做 alpha 混合, 所以每个图元先画到小图层再 alpha_composite。"""

    def __init__(self, size, bg=(0, 0, 0, 255)):
        self.img = Image.new("RGBA", size, bg)

    def _paint(self, box, fn, pad=2):
        x0, y0, x1, y1 = [int(round(v)) for v in box]
        w = max(1, x1 - x0) + pad * 2
        h = max(1, y1 - y0) + pad * 2
        lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        fn(ImageDraw.Draw(lay), pad - x0, pad - y0, w, h)
        self.img.alpha_composite(lay, (x0 - pad, y0 - pad))

    def fill(self, box, color, radius=0.0):
        if color[3] == 0:
            return
        x0, y0, x1, y1 = box

        def fn(d, ox, oy, w, h):
            if radius > 0.5:
                d.rounded_rectangle([ox + x0, oy + y0, ox + x1, oy + y1],
                                    radius=radius, fill=color)
            else:
                d.rectangle([ox + x0, oy + y0, ox + x1, oy + y1], fill=color)

        self._paint(box, fn)

    def outline(self, box, color, width=1.0, radius=0.0):
        if color[3] == 0:
            return
        x0, y0, x1, y1 = box
        w = max(1, int(round(width * S)))

        def fn(d, ox, oy, ww, hh):
            d.rectangle([ox + x0, oy + y0, ox + x1, oy + y1], outline=color, width=0)
            if radius > 0.5:
                d.rounded_rectangle([ox + x0, oy + y0, ox + x1, oy + y1],
                                    radius=radius, outline=color, width=w)
            else:
                d.rectangle([ox + x0, oy + y0, ox + x1, oy + y1], outline=color, width=w)

        self._paint(box, fn, pad=w + 2)

    def line(self, pts, color, width=1.0):
        """pts: [(x, y), ...] 已经是像素坐标"""
        if color[3] == 0 or len(pts) < 2:
            return
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        box = (min(xs), min(ys), max(xs), max(ys))
        w = max(1, int(round(width * S)))

        def fn(d, ox, oy, ww, hh):
            d.line([(x + ox, y + oy) for x, y in pts], fill=color, width=w, joint="curve")

        self._paint(box, fn, pad=w + 2)

    def arc(self, center, r, a0, a1, color, width=1.0):
        if color[3] == 0:
            return
        cx, cy = self._flip_center(center, r)
        box = (cx - r * S, cy - r * S, cx + r * S, cy + r * S)
        w = max(1, int(round(width * S)))

        def fn(d, ox, oy, ww, hh):
            d.arc([ox + cx - r * S, oy + cy - r * S, ox + cx + r * S, oy + cy + r * S],
                  start=-a1, end=-a0, fill=color, width=w)

        self._paint(box, fn, pad=w + 2)

    def circle(self, center, r, color, width=1.0):
        if color[3] == 0:
            return
        cx, cy = self._flip_center(center, r)
        w = max(1, int(round(width * S)))
        box = (cx - r * S, cy - r * S, cx + r * S, cy + r * S)

        def fn(d, ox, oy, ww, hh):
            d.ellipse([ox + cx - r * S, oy + cy - r * S, ox + cx + r * S, oy + cy + r * S],
                      outline=color, width=w)

        self._paint(box, fn, pad=w + 2)

    def disc(self, center, r, color):
        cx, cy = self._flip_center(center, r)
        box = (cx - r * S, cy - r * S, cx + r * S, cy + r * S)

        def fn(d, ox, oy, ww, hh):
            d.ellipse([ox + cx - r * S, oy + cy - r * S, ox + cx + r * S, oy + cy + r * S],
                      fill=color)

        self._paint(box, fn)

    @staticmethod
    def _flip_center(center, r):
        return (_px(center[0]), _px(_H - center[1]))

    def ellipse(self, box, color):
        if color[3] == 0:
            return
        x0, y0, x1, y1 = box

        def fn(d, ox, oy, w, h):
            d.ellipse([ox + x0, oy + y0, ox + x1, oy + y1], fill=color)

        self._paint(box, fn)

    def text(self, xy, s, font, fill, stroke=0):
        if fill[3] == 0 or not s:
            return
        pad = 4 + stroke
        w = int(font.getlength(s)) + pad * 2 + 2
        h = int(font.size * 1.6) + pad * 2
        lay = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
        ImageDraw.Draw(lay).text((pad, pad), s, font=font, fill=fill,
                                 stroke_width=stroke, stroke_fill=fill)
        self.img.alpha_composite(lay, (int(xy[0]) - pad, int(xy[1]) - pad))


def _draw_instr(cv, ins, current, op):
    t = type(ins).__name__
    if t == "Color":
        current[0] = ins.rgba
        return
    col = _col(current[0], op)
    if col[3] == 0:
        return
    if t == "Rectangle":
        x, y = ins.pos
        w, h = ins.size
        cv.fill((_px(x), _px(_H - (y + h)), _px(x + w), _px(_H - y)), col)
    elif t == "RoundedRectangle":
        x, y = ins.pos
        w, h = ins.size
        r = ins.radius[0] if ins.radius else 0
        cv.fill((_px(x), _px(_H - (y + h)), _px(x + w), _px(_H - y)), col, radius=_px(r))
    elif t == "Ellipse":
        x, y = ins.pos
        w, h = ins.size
        cv.ellipse((_px(x), _px(_H - (y + h)), _px(x + w), _px(_H - y)), col)
    elif t == "Line":
        if ins.rounded_rectangle:
            x, y, w, h, r = ins.rounded_rectangle
            cv.outline((_px(x), _px(_H - (y + h)), _px(x + w), _px(_H - y)), col,
                       width=ins.width, radius=_px(r))
        elif ins.circle:
            cx, cy, r, a0, a1 = ins.circle
            full = abs((a1 - a0) % 360) < 0.6 and abs(a1 - a0) >= 359
            if full:
                cv.circle((cx, cy), r, col, ins.width)
            else:
                cv.arc((cx, cy), r, a0, a1, col, ins.width)
        elif ins.points:
            p = ins.points
            pts = [(_px(p[i]), _px(_H - p[i + 1])) for i in range(0, len(p) - 1, 2)]
            cv.line(pts, col, ins.width)


def _wrap(text, font, maxw):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if font.getlength(cur + ch) > maxw and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    lines.append(cur)
    return lines


def _draw_label(cv, w, op):
    text = getattr(w, "text", "")
    if not text:
        return
    fs = float(getattr(w, "font_size", 14))
    font = _font(fs)
    color = _col(getattr(w, "color", (1, 1, 1, 1)), op)
    if color[3] == 0:
        return
    x0, y0, x1, y1 = _box(w)
    maxw = max(4, x1 - x0 - _px(2))
    lines = _wrap(text, font, maxw)
    lh = fs * 1.42 * S
    total_h = lh * len(lines)
    valign = getattr(w, "valign", "middle")
    if valign == "top":
        ty = y0
    elif valign == "bottom":
        ty = y1 - total_h
    else:
        ty = y0 + (y1 - y0 - total_h) / 2.0
    halign = getattr(w, "halign", "left")
    stroke = 0
    if float(getattr(w, "outline_width", 0) or 0) > 0:
        stroke = max(1, int(round(float(w.outline_width) * S * 0.85)))
    for i, line in enumerate(lines):
        lw = font.getlength(line)
        if halign == "center":
            tx = x0 + (x1 - x0 - lw) / 2.0
        elif halign == "right":
            tx = x1 - lw - _px(1)
        else:
            tx = x0 + _px(1)
        cv.text((tx, ty + i * lh), line, font, color, stroke)


def _draw_input(cv, w, op):
    x0, y0, x1, y1 = _box(w)
    text = w.text or w.hint_text or ""
    if not text:
        return
    fs = float(getattr(w, "font_size", 14))
    font = _font(fs)
    hint = not w.text
    color = _col((0.55, 0.58, 0.62, 1) if hint else getattr(w, "foreground_color", (1, 1, 1, 1)), op)
    ty = (y0 + y1) / 2.0 - fs * S * 0.69
    halign = getattr(w, "halign", "left")
    lw = font.getlength(text)
    pad = _px(10)
    if halign == "right":
        tx = x1 - lw - pad
    elif halign == "center":
        tx = x0 + (x1 - x0 - lw) / 2.0
    else:
        tx = x0 + pad
    cv.text((tx, ty), text, font, color, 0)


def _shift(w, dy):
    w.pos = [w.pos[0], w.pos[1] + dy]
    for c in w.children:
        _shift(c, dy)


def paint(root, size=None, bg=(0.039, 0.051, 0.067, 1), out="shot.png"):
    global _H
    W, H = size or (root.size[0], root.size[1])
    _H = H
    cv = Canvas((int(_px(W)), int(_px(H))), _col(bg))
    root_cv = cv

    def walk(w, opacity, cv=None):
        cv = cv or root_cv
        op = opacity * (getattr(w, "opacity", 1) or 0)
        if op <= 0.001:
            return
        if isinstance(w, C.ScreenManager):
            cur = w.current_screen()
            if cur is not None:
                walk(cur, op, cv)
            return
        if isinstance(w, C.ScrollView):
            for c in w.children:
                _shift(c, w.top - (c.pos[1] + c.size[1]))
        cur_col = [None]

        def paint_group(group):
            for ins in group.children:
                _draw_instr(cv, ins, cur_col, op)

        paint_group(w.canvas.before)
        if isinstance(w, C.TextInput):
            _draw_input(cv, w, op)
        elif isinstance(w, (C.Label, C.Button)):
            _draw_label(cv, w, op)
        paint_group(w.canvas.after)
        if isinstance(w, C.ScrollView):
            # 滚动区要裁剪: 先画到一层透明图, 再按可视区域贴回去
            sub = Canvas(cv.img.size, (0, 0, 0, 0))
            for c in reversed(w.children):
                walk(c, op, sub)
            x0, y0, x1, y1 = _box(w)
            box = (max(0, int(x0)), max(0, int(y0)),
                   min(cv.img.size[0], int(x1)), min(cv.img.size[1], int(y1)))
            if box[2] > box[0] and box[3] > box[1]:
                cv.img.alpha_composite(sub.img.crop(box), (box[0], box[1]))
            return
        for c in reversed(w.children):
            walk(c, op, cv)

    walk(root, 1.0)
    cv.img.convert("RGB").save(out)
    return out
