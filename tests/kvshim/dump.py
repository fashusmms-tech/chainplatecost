# -*- coding: utf-8 -*-
"""打印控件树 + 画布指令, 排查版面问题。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("CHAINPLATE_DATA_DIR", os.path.join(HERE, "..", "..", "preview", "data"))

from kivy import _core as C   # noqa: E402
import main as app_mod        # noqa: E402

app = app_mod.ChainPlateApp()
root = app.build()
C.layout_root(root, 393.0, 852.0)


def dump(w, d=0, limit=None):
    if d > 6:
        return
    cls = type(w).__name__
    txt = getattr(w, "text", "") or ""
    print("%s%s pos=(%.1f,%.1f) size=(%.1f,%.1f) sh=(%s,%s) %s" % (
        "  " * d, cls, w.pos[0], w.pos[1], w.size[0], w.size[1],
        w.size_hint_x, w.size_hint_y, txt[:14]))
    if d <= 4:
        for name in ("before", "after"):
            grp = getattr(w.canvas, name)
            kinds = [type(i).__name__ for i in grp.children]
            if kinds:
                print("%s  .%s: %s" % ("  " * d, name, kinds))
        for c in reversed(w.children):
            dump(c, d + 1)


cur = root.current_screen()
print("SCREEN", cur.name, cur.size)
for c in reversed(cur.children):
    dump(c, 1)
