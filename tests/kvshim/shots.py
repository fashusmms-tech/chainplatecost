# -*- coding: utf-8 -*-
"""在没有 Kivy 的机器上跑 main.py 的界面: 布局 + 出图。

用法:
    python tests/kvshim/shots.py            # 出三张图到 tests/kvshim/out/
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)        # 让 import kivy 命中替身
sys.path.insert(0, ROOT)

os.environ["KIVY_NO_ARGS"] = "1"
os.environ.setdefault("CHAINPLATE_DATA_DIR",
                      os.path.join(tempfile.gettempdir(), "chainplate_preview"))
_data = os.environ["CHAINPLATE_DATA_DIR"]
os.makedirs(_data, exist_ok=True)
# 每次出图都从"干净状态"开始(否则会读到上次存下来的勾选)
for _f in ("ui_state.json", "settings.json"):
    try:
        os.remove(os.path.join(_data, _f))
    except OSError:
        pass

import kivy                     # noqa: E402
from kivy import _core as C     # noqa: E402

import render                   # noqa: E402
import main as app_mod          # noqa: E402

OUT = os.environ.get("SHOT_DIR") or os.path.join(os.path.dirname(ROOT), "preview")
os.makedirs(OUT, exist_ok=True)

W, H = 393.0, 852.0


def build():
    app = app_mod.ChainPlateApp()
    root = app.build()
    return app, root


def shot(root, name):
    C.layout_root(root, W, H)
    p = os.path.join(OUT, name)
    render.paint(root, (W, H), out=p)
    print("saved", p)


def main():
    app, root = build()
    shot(root, "01-main.png")

    # 打开两个配件, 看展开态
    m = app.main_screen
    m.acc_rows["punch"][0].active = True
    m.acc_rows["cross"][0].active = True
    m.acc_rows["cross"][2]["length"].text = "120"
    m.acc_rows["cross"][2]["height"].text = "60"
    m.acc_rows["cross"][2]["thickness"].text = "2.0"
    m.acc_rows["cross"][2]["interval"].text = "200"
    m.acc_rows["punch"][2]["price"].text = "1.5"
    shot(root, "02-main-expanded.png")

    m.on_compute()
    C.layout_root(root, W, H)
    shot(root, "03-result.png")

    root.current = "settings"
    C.layout_root(root, W, H)
    shot(root, "04-settings.png")
    print("current screen:", root.current)


if __name__ == "__main__":
    main()
