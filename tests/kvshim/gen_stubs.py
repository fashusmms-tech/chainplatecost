# -*- coding: utf-8 -*-
"""生成 kivy 替身的模块骨架(只跑一次, 产物提交在 tests/kvshim/kivy 下)。"""
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kivy")

files = {
    "__init__.py": "from ._core import __version__\n",
    "properties.py": (
        "from ._core import (AliasProperty, BooleanProperty, DictProperty, ListProperty,\n"
        "                    NumericProperty, ObjectProperty, OptionProperty, Property,\n"
        "                    StringProperty)\n"),
    "event.py": "from ._core import EventDispatcher\n",
    "metrics.py": "from ._core import dp, sp\n",
    "config.py": "from ._core import Config\n",
    "clock.py": "from ._core import Clock\n",
    "app.py": "from ._core import App\n",
    "logger.py": (
        "\nclass Logger:\n"
        "    @staticmethod\n"
        "    def info(*a, **kw): pass\n"
        "    @staticmethod\n"
        "    def warning(*a, **kw): pass\n"
        "    @staticmethod\n"
        "    def error(*a, **kw): pass\n"
        "    @staticmethod\n"
        "    def debug(*a, **kw): pass\n"),
    "graphics/__init__.py": (
        "from .._core import (Canvas, Color, Ellipse, Instruction, InstructionGroup, Line,\n"
        "                     PopMatrix, PushMatrix, Rectangle, RoundedRectangle)\n"),
    "core/__init__.py": "",
    "core/window/__init__.py": "from ..._core import Window, window\n",
    "core/clipboard/__init__.py": "from ..._core import Clipboard\n",
    "core/text/__init__.py": "from ..._core import LabelBase\n",
    "uix/__init__.py": "",
    "uix/widget.py": "from .._core import Widget\n",
    "uix/boxlayout.py": "from .._core import BoxLayout\n",
    "uix/gridlayout.py": "from .._core import GridLayout\n",
    "uix/label.py": "from .._core import Label\n",
    "uix/button.py": "from .._core import Button, ButtonBehavior\n",
    "uix/togglebutton.py": "from .._core import ToggleButton\n",
    "uix/checkbox.py": "from .._core import CheckBox\n",
    "uix/textinput.py": "from .._core import TextInput\n",
    "uix/spinner.py": "from .._core import Spinner, SpinnerOption\n",
    "uix/screenmanager.py": "from .._core import Screen, ScreenManager\n",
    "uix/scrollview.py": "from .._core import ScrollView\n",
    "uix/popup.py": "from .._core import Popup\n",
    "uix/tabbedpanel.py": "from .._core import TabbedPanel, TabbedPanelItem\n",
}

for path, body in files.items():
    full = os.path.join(BASE, path)
    d = os.path.dirname(full)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(body)
print("wrote", len(files), "modules")
