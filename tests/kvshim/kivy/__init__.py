# -*- coding: utf-8 -*-
"""kivy 替身入口。

只做两件事:
  1) 导出 _core 里那套最小实现;
  2) 把 kivy.uix.* / kivy.core.* / kivy.graphics 这些子模块直接注册进
     sys.modules —— 因为本机沙箱不允许往这个目录写文件, 一个 __init__.py
     就能把整套导入路径伪造出来。
"""
import sys
import types

from . import _core                                    # noqa: F401
from . import _patch                                   # noqa: F401  (Kivy 语义修正, 必须在导出前)
from ._core import (AliasProperty, App, BooleanProperty, BoxLayout, Button,
                    ButtonBehavior, Canvas, CheckBox, Clipboard, Clock, Color,
                    Config, DictProperty, Ellipse, EventDispatcher,
                    GridLayout, Instruction, InstructionGroup, Label,
                    LabelBase, Line, ListProperty, NumericProperty,
                    ObjectProperty, OptionProperty, Popup, Property,
                    Rectangle, RoundedRectangle, Screen, ScreenManager,
                    ScrollView, Spinner, SpinnerOption, StringProperty,
                    TabbedPanel, TabbedPanelItem, TextInput, ToggleButton,
                    Widget, Window, dp, sp, window, __version__)
from ._core import Logger_ as _Logger

__all__ = ["__version__"]


def _mk_pkg(name):
    m = types.ModuleType(name)
    m.__path__ = []
    m.__package__ = name
    sys.modules[name] = m
    parent, _, leaf = name.rpartition(".")
    if parent and parent in sys.modules:
        setattr(sys.modules[parent], leaf, m)
    return m


def _mk(name, **attrs):
    m = types.ModuleType(name)
    m.__package__ = name.rpartition(".")[0]
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    parent, _, leaf = name.rpartition(".")
    if parent in sys.modules:
        setattr(sys.modules[parent], leaf, m)
    return m


for _p in ("kivy.uix", "kivy.core", "kivy.graphics"):
    _mk_pkg(_p)

_mk("kivy.properties",
    AliasProperty=AliasProperty, BooleanProperty=BooleanProperty,
    DictProperty=DictProperty, ListProperty=ListProperty,
    NumericProperty=NumericProperty, ObjectProperty=ObjectProperty,
    OptionProperty=OptionProperty, Property=Property,
    StringProperty=StringProperty)
_mk("kivy.event", EventDispatcher=EventDispatcher)
_mk("kivy.metrics", dp=dp, sp=sp)
_mk("kivy.config", Config=Config)
_mk("kivy.clock", Clock=Clock)
_mk("kivy.app", App=App)
_mk("kivy.logger", Logger=type("Logger", (), {
    "info": staticmethod(lambda *a, **k: None),
    "warning": staticmethod(lambda *a, **k: None),
    "error": staticmethod(lambda *a, **k: None),
    "debug": staticmethod(lambda *a, **k: None)}))
_mk("kivy.graphics", Canvas=Canvas, Color=Color, Ellipse=Ellipse,
    Instruction=Instruction, InstructionGroup=InstructionGroup, Line=Line,
    Rectangle=Rectangle, RoundedRectangle=RoundedRectangle)
_mk("kivy.core.window", Window=Window, window=window)
_mk("kivy.core.clipboard", Clipboard=Clipboard)
_mk("kivy.core.text", LabelBase=LabelBase)

_mk("kivy.uix.widget", Widget=Widget)
_mk("kivy.uix.boxlayout", BoxLayout=BoxLayout)
_mk("kivy.uix.gridlayout", GridLayout=GridLayout)
_mk("kivy.uix.label", Label=Label)
_mk("kivy.uix.button", Button=Button, ButtonBehavior=ButtonBehavior)
_mk("kivy.uix.togglebutton", ToggleButton=ToggleButton)
_mk("kivy.uix.checkbox", CheckBox=CheckBox)
_mk("kivy.uix.textinput", TextInput=TextInput)
_mk("kivy.uix.spinner", Spinner=Spinner, SpinnerOption=SpinnerOption)
_mk("kivy.uix.screenmanager", Screen=Screen, ScreenManager=ScreenManager)
_mk("kivy.uix.scrollview", ScrollView=ScrollView)
_mk("kivy.uix.popup", Popup=Popup)
_mk("kivy.uix.tabbedpanel", TabbedPanel=TabbedPanel, TabbedPanelItem=TabbedPanelItem)
