# -*- coding: utf-8 -*-
"""真 Kivy 下的界面行为探针（需要本机装了真 Kivy，不是 tests/kvshim 替身）。

它能查出替身测不出来的那类问题：
  - 节距胶囊是不是真的单选（走用户按下逻辑 _do_press，而不是直接改 state）
  - 点第二个输入框时，第一个有没有失焦（否则会同时亮多个橙色描边）
  - 主界面默认值
  - 软键盘模式

用法（项目根目录）:
    .venv-kivy\\Scripts\\python tests\\probe_ui.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.argv = ["main.py"]

from kivy.core.window import Window  # noqa: E402

Window.size = (400, 860)

import main  # noqa: E402
from kivy.clock import Clock  # noqa: E402


def _states(ms):
    return {k: v.state for k, v in ms.pitch_btns.items()}


def _downs(s):
    return [k for k, v in s.items() if v == "down"]


def probe(dt):
    ms = app.main_screen
    names = list(ms.pitch_btns)
    print("\n=== 节距: 模拟真实点击 ===")
    print("  初始 down:", _downs(_states(ms)), "pitch()=%s" % ms.pitch())
    ms.pitch_btns[names[0]]._do_press()
    print("  点 %-6s -> down=%s pitch()=%s" % (names[0], _downs(_states(ms)), ms.pitch()))
    ms.pitch_btns[names[3]]._do_press()
    print("  点 %-6s -> down=%s pitch()=%s" % (names[3], _downs(_states(ms)), ms.pitch()))
    ms.pitch_btns[names[3]]._do_press()
    print("  再点同一枚 -> down=%s pitch()=%s" % (_downs(_states(ms)), ms.pitch()))
    ok_single = len(_downs(_states(ms))) == 1

    print("\n=== 输入框焦点互斥 ===")
    a, b = ms.in_width, ms.in_thick
    a.focus = True
    b.focus = True
    print("  先 A 后 B: A=%s B=%s" % (a.focus, b.focus))
    ok_focus = not (a.focus and b.focus)

    print("\n=== 默认值 ===")
    print("  有效宽度=%r 板厚=%r 穿杆直径=%r" % (a.text, b.text, ms.in_pin_d.text))

    print("\n=== 软键盘 ===")
    print("  softinput_mode:", Window.softinput_mode)
    print("  已注册输入框:", len([r for r in main._INPUTS if r() is not None]))

    print("\n结论: 单选=%s 焦点互斥=%s" % ("OK" if ok_single else "FAIL",
                                          "OK" if ok_focus else "FAIL"))
    app.stop()


app = main.ChainPlateApp()
Clock.schedule_once(probe, 1.5)
app.run()
