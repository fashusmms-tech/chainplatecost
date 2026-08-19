# -*- coding: utf-8 -*-
"""
金属链板成本计算器 — 手机版 (Kivy / Android)
与电脑版功能一致: 计算、选配件、设置(常数+公式可改)、变量对照
设置保存在 App 私有目录 settings.json
"""
import json
import os
import sys

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

from chainplate_calc import (MATERIAL_KEYS, MATERIAL_NAMES, PITCHES,
                             PITCH_VALUE, SAMPLE_ENV, VAR_NAMES, chain_width_of,
                             compute, default_settings, eval_expr, format_result,
                             formula_vars, load_settings, save_settings)

# 材质显示名 → 内部键名 (Spinner 显示中文名, 计算/设置索引用内部键)
MATERIAL_KEY = {name: key for key, name in MATERIAL_NAMES.items()}

# ---------------- 中文字体 ----------------
# 兼容不同上传方式: fonts/ 子目录 或 项目根目录, 找到哪个用哪个
_DIR = os.path.dirname(os.path.abspath(__file__))
_FONT = next((os.path.join(_DIR, p) for p in ("fonts/simhei.ttf", "simhei.ttf")
              if os.path.exists(os.path.join(_DIR, p))), "")
try:
    # 注意: 不能给类属性赋值 font_name(会覆盖 Kivy 的 Property 对象),
    # 正确做法是注册替换默认字体名 Roboto, 所有控件自动生效
    LabelBase.register(name="CJK", fn_regular=_FONT)
    LabelBase.register(name="Roboto", fn_regular=_FONT)
except Exception:
    pass
Window.softinput_mode = "pan"

C_ACCENT = (0.15, 0.45, 0.85, 1)
C_GRAY = (0.45, 0.45, 0.45, 1)
C_GREEN = (0.0, 0.5, 0.3, 1)


def popup_msg(text, title=""):
    content = BoxLayout(padding=dp(12))
    lbl = Label(text=text, font_size=sp(15), halign="left", valign="top",
                text_size=(dp(300), None), size_hint_y=None)
    lbl.bind(texture_size=lambda *a: setattr(lbl, "height", lbl.texture_size[1]))
    sc = ScrollView()
    sc.add_widget(lbl)
    content.add_widget(sc)
    p = Popup(title=title, content=content, size_hint=(0.92, 0.6))
    p.open()


def section(title):
    return Label(text=title, font_size=sp(17), bold=True, color=C_ACCENT,
                 size_hint_y=None, height=dp(36), halign="left", valign="middle")


def hrow(*widgets, height=dp(46)):
    box = BoxLayout(size_hint_y=None, height=height, spacing=dp(6))
    for w in widgets:
        box.add_widget(w)
    return box


def fld_label(text, wrap=150):
    lbl = Label(text=text, font_size=sp(14), halign="left", valign="middle",
                size_hint_y=None, height=dp(44), size_hint_x=None, width=dp(wrap),
                text_size=(dp(wrap), None))
    return lbl


def num_input(text="", hint=""):
    return TextInput(text=text, hint_text=hint,
                     multiline=False, size_hint_y=None, height=dp(42),
                     font_size=sp(16), input_type="number")


# ============================================================
# 计算主界面
# ============================================================
class MainScreen(Screen):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.build_ui()

    # ---------- 界面 ----------
    def build_ui(self):
        root = ScrollView()
        grid = GridLayout(cols=1, spacing=dp(4), padding=dp(10),
                          size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        root.add_widget(grid)
        self.add_widget(root)
        g = grid

        g.add_widget(Label(text="金属链板成本计算器", font_size=sp(22), bold=True,
                           size_hint_y=None, height=dp(48)))

        # 材质
        g.add_widget(section("材质与节距"))
        self.sp_plate = Spinner(text="201不锈钢", values=list(MATERIAL_NAMES.values()),
                                size_hint_y=None, height=dp(44), font_size=sp(15))
        self.sp_plate.bind(text=lambda *a: self.refresh_info())
        g.add_widget(hrow(fld_label("板材质"), self.sp_plate))

        self.cb_chain_u = CheckBox(active=True)
        self.sp_chain = Spinner(text="201不锈钢", values=list(MATERIAL_NAMES.values()),
                                size_hint_y=None, height=dp(44), font_size=sp(15),
                                disabled=True)
        g.add_widget(hrow(fld_label("链条材质"), self.cb_chain_u,
                          Label(text="与板相同", font_size=sp(13)),
                          self.sp_chain))
        self.cb_chain_u.bind(active=self.on_chain_unified)

        self.cb_pin_u = CheckBox(active=True)
        self.sp_pin = Spinner(text="201不锈钢", values=list(MATERIAL_NAMES.values()),
                              size_hint_y=None, height=dp(44), font_size=sp(15),
                              disabled=True)
        g.add_widget(hrow(fld_label("穿杆材质"), self.cb_pin_u,
                          Label(text="与板相同", font_size=sp(13)),
                          self.sp_pin))
        self.cb_pin_u.bind(active=self.on_pin_unified)

        # 节距
        pitch_box = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        self.pitch_btns = {}
        for i, p in enumerate(PITCHES):
            b = ToggleButton(text=p, group="pitch", font_size=sp(13),
                             state="down" if p == "50.8" else "normal")
            b.bind(on_release=lambda *a: self.refresh_info())
            self.pitch_btns[p] = b
            pitch_box.add_widget(b)
        g.add_widget(hrow(fld_label("节距(mm)"), pitch_box, height=dp(48)))

        self.lbl_chain_w = Label(text="", font_size=sp(13), color=C_GRAY,
                                 size_hint_y=None, height=dp(24), halign="left")
        self.lbl_sheet = Label(text="", font_size=sp(13), color=C_GRAY,
                               size_hint_y=None, height=dp(24), halign="left")
        g.add_widget(self.lbl_chain_w)
        g.add_widget(self.lbl_sheet)

        # 基础尺寸
        g.add_widget(section("基础尺寸 (mm)"))
        self.in_width = num_input("500", "有效宽度")
        self.in_thick = num_input("2.0", "板厚")
        self.in_pin_d = num_input("8", "穿杆直径")
        g.add_widget(hrow(fld_label("有效宽度"), self.in_width))
        g.add_widget(hrow(fld_label("板厚"), self.in_thick))
        g.add_widget(hrow(fld_label("穿杆直径"), self.in_pin_d))

        # 选配件
        g.add_widget(section("选配件 (勾选后输入)"))
        self.acc_rows = {}

        def make_acc(key, title, fields):
            cb = CheckBox(active=False)
            row = hrow(fld_label(title), cb)
            g.add_widget(row)
            fbox = GridLayout(cols=2, spacing=dp(6), size_hint_y=None)
            inputs = {}
            for ftitle, fkey in fields:
                ti = num_input()
                inputs[fkey] = ti
                fbox.add_widget(fld_label(ftitle, wrap=130))
                fbox.add_widget(ti)
            g.add_widget(fbox)
            fbox.opacity = 0
            fbox.disabled = True
            cb.bind(active=lambda chk, v, fb=fbox: self.toggle_acc(fb, v))
            self.acc_rows[key] = (cb, fbox, inputs)

        make_acc("cross", "横挡板", [("长度mm", "length"), ("高度mm", "height"),
                                     ("厚度mm", "thickness"), ("间隔mm", "interval")])
        make_acc("side", "侧挡板", [("高度mm", "height"), ("厚度mm", "thickness")])
        make_acc("ball", "辅助载重滚珠(1元/个)", [("排数", "rows")])
        make_acc("wheel", "辅助载重支轮(3.5元/个)", [("排数", "rows")])
        make_acc("punch", "冲孔", [("价格元/片(自动/手动)", "price")])

        # 按钮
        btn = Button(text="计  算", font_size=sp(20), bold=True,
                     background_color=C_ACCENT, size_hint_y=None, height=dp(54))
        btn.bind(on_release=lambda *a: self.on_compute())
        g.add_widget(btn)

        btn2 = Button(text="设 置 (常数/公式)", font_size=sp(16),
                      size_hint_y=None, height=dp(46))
        btn2.bind(on_release=lambda *a: setattr(self.manager, "current", "settings"))
        g.add_widget(btn2)

        self.result = Label(text="", font_size=sp(14), halign="left", valign="top",
                            size_hint_y=None, text_size=(dp(360), None))
        self.result.bind(texture_size=lambda *a:
                         setattr(self.result, "height", self.result.texture_size[1]))
        g.add_widget(self.result)
        self.refresh_info()

    # ---------- 交互 ----------
    def toggle_acc(self, fbox, visible):
        fbox.opacity = 1 if visible else 0
        fbox.disabled = not visible
        if visible:
            fbox.height = dp(46) * (fbox.children.__len__() // 2)
        else:
            fbox.height = 0

    def on_chain_unified(self, cb, val):
        self.sp_chain.disabled = val
        if val:
            self.sp_chain.text = self.sp_plate.text

    def on_pin_unified(self, cb, val):
        self.sp_pin.disabled = val
        if val:
            self.sp_pin.text = self.sp_plate.text

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
        self.lbl_sheet.text = f"当前板材价格: {s['sheet_price'][mat]:g} 元/kg"
        p = self.pitch()
        self.lbl_chain_w.text = (f"节距 {p} 链条宽度: "
                                 f"{chain_width_of(p, s):g} mm (穿杆/侧挡板公式用)")

    # ---------- 计算 ----------
    def _f(self, name, ti):
        try:
            v = float(ti.text.strip())
        except ValueError:
            raise ValueError(f"{name} 输入无效: {ti.text!r}")
        if v <= 0:
            raise ValueError(f"{name} 必须大于 0")
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
            popup_msg(f"计算错误(公式可能有误, 请到设置→公式检查):\n{e}")
            return
        except Exception as e:
            popup_msg(f"计算出错: {type(e).__name__}: {e}")
            return
        self.result.text = format_result(r)


# ============================================================
# 设置界面
# ============================================================
# 数值字段: (页签名, 显示名, 键路径)
S_FIELDS = [
    ("板材价格", "201 不锈钢板材", ("sheet_price", "201")),
    ("板材价格", "304 不锈钢板材", ("sheet_price", "304")),
    ("板材价格", "碳钢板材", ("sheet_price", "carbon")),
    ("链条价格", "201 · 25.4", ("chain_price", "201", "25.4")),
    ("链条价格", "201 · 31.75", ("chain_price", "201", "31.75")),
    ("链条价格", "201 · 38.1", ("chain_price", "201", "38.1")),
    ("链条价格", "201 · 50.8", ("chain_price", "201", "50.8")),
    ("链条价格", "201 · 假两寸", ("chain_price", "201", "假两寸")),
    ("链条价格", "304 · 25.4", ("chain_price", "304", "25.4")),
    ("链条价格", "304 · 31.75", ("chain_price", "304", "31.75")),
    ("链条价格", "304 · 38.1", ("chain_price", "304", "38.1")),
    ("链条价格", "304 · 50.8", ("chain_price", "304", "50.8")),
    ("链条价格", "304 · 假两寸", ("chain_price", "304", "假两寸")),
    ("链条价格", "碳钢 · 25.4", ("chain_price", "carbon", "25.4")),
    ("链条价格", "碳钢 · 31.75", ("chain_price", "carbon", "31.75")),
    ("链条价格", "碳钢 · 38.1", ("chain_price", "carbon", "38.1")),
    ("链条价格", "碳钢 · 50.8", ("chain_price", "carbon", "50.8")),
    ("链条价格", "碳钢 · 假两寸", ("chain_price", "carbon", "假两寸")),
    ("链条宽度", "节距 25.4", ("chain_width", "25.4")),
    ("链条宽度", "节距 31.75", ("chain_width", "31.75")),
    ("链条宽度", "节距 38.1", ("chain_width", "38.1")),
    ("链条宽度", "节距 50.8", ("chain_width", "50.8")),
    ("链条宽度", "节距 假两寸", ("chain_width", "假两寸")),
    ("公式常数", "密度系数 (density)", ("const", "density")),
    ("公式常数", "穿杆直径系数 (pin_pi)", ("const", "pin_pi")),
    ("公式常数", "穿杆重量系数 (pin_coef)", ("const", "pin_coef")),
    ("公式常数", "穿杆工费 (pin_fee)", ("const", "pin_fee")),
    ("公式常数", "挡板高度加值 (flight_margin)", ("const", "flight_margin")),
    ("公式常数", "人工成本/片 (labor, 0=不计)", ("const", "labor")),
    ("切割冲床焊接", "薄板档最大厚度 (≤)", ("cut", "band1", "max_t")),
    ("切割冲床焊接", "薄板档平费 (flat_fee)", ("cut", "band1", "flat_fee")),
    ("切割冲床焊接", "薄板档平费最大宽度", ("cut", "band1", "flat_w")),
    ("切割冲床焊接", "中板档最小厚度 (≥)", ("cut", "band2", "min_t")),
    ("切割冲床焊接", "中板档最大厚度 (≤)", ("cut", "band2", "max_t")),
    ("切割冲床焊接", "中板档平费 (flat_fee)", ("cut", "band2", "flat_fee")),
    ("切割冲床焊接", "中板档平费最大宽度", ("cut", "band2", "flat_w")),
    ("切割冲床焊接", "中板档公式最小宽度 (formula_w)", ("cut", "band2", "formula_w")),
    ("切割冲床焊接", "中板档公式加价 (formula_extra)", ("cut", "band2", "formula_extra")),
    ("切割冲床焊接", "厚板档最小厚度 (≥)", ("cut", "band3", "min_t")),
    ("切割冲床焊接", "厚板档平费 (flat_fee)", ("cut", "band3", "flat_fee")),
    ("切割冲床焊接", "厚板档平费最大宽度", ("cut", "band3", "flat_w")),
    ("切割冲床焊接", "厚板档公式加价 (formula_extra)", ("cut", "band3", "formula_extra")),
    ("切割冲床焊接", "冲床手动值 (等号关闭时)", ("punch", "manual_fee")),
    ("切割冲床焊接", "焊接平费最大直径 (max_d)", ("weld", "max_d")),
    ("切割冲床焊接", "焊接小直径费 (fee_small)", ("weld", "fee_small")),
    ("切割冲床焊接", "焊接大直径费 (fee_large)", ("weld", "fee_large")),
    ("冲孔", "自动计算最大板厚 (auto_max_t)", ("punch_hole", "auto_max_t")),
    ("冲孔", "自动平费最大宽度 (auto_flat_w)", ("punch_hole", "auto_flat_w")),
    ("冲孔", "自动平费 (auto_flat_fee)", ("punch_hole", "auto_flat_fee")),
    ("冲孔", "手动输入最小板厚 (manual_min_t)", ("punch_hole", "manual_min_t")),
    ("选配件", "横挡板工费 (cross_fee)", ("accessory", "cross_fee")),
    ("选配件", "侧挡板工费 (side_fee)", ("accessory", "side_fee")),
    ("选配件", "滚珠单价 (ball)", ("accessory", "ball")),
    ("选配件", "支轮单价 (wheel)", ("accessory", "wheel")),
]

S_BOOL = [("切割冲床焊接", "冲床费用=切割费用", ("punch", "equals_cut"))]

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
        self.build_ui()

    def build_ui(self):
        outer = BoxLayout(orientation="vertical", padding=dp(6))
        self.add_widget(outer)

        tp = TabbedPanel(do_default_tab=False, size_hint_y=1.0)
        outer.add_widget(tp)

        self.entries = {}
        self.bools = {}
        self.formula_entries = {}
        self.formula_maps = {}

        # 数值页签
        tabs = {}
        for tab, label, path in S_FIELDS:
            if tab not in tabs:
                tabs[tab] = self._make_tab(tp, tab)
            ti = num_input(str(get_nested(self.app.settings, path)))
            self.entries[path] = ti
            row = hrow(fld_label(label, wrap=190), ti)
            tabs[tab].add_widget(row)

        for tab, label, path in S_BOOL:
            if tab not in tabs:
                tabs[tab] = self._make_tab(tp, tab)
            cb = CheckBox(active=bool(get_nested(self.app.settings, path)))
            self.bools[path] = cb
            tabs[tab].add_widget(hrow(fld_label(label, wrap=190), cb))

        # 公式页签
        ftab = self._make_tab(tp, "公式")
        for label, path, hint in S_FORMULAS:
            box = GridLayout(cols=1, spacing=dp(2), size_hint_y=None)
            box.height = dp(120)
            ti = TextInput(text=str(get_nested(self.app.settings, path)),
                           multiline=False, size_hint_y=None, height=dp(42),
                           font_size=sp(14), font_name="CJK")
            self.formula_entries[path] = ti
            map_lbl = Label(text="", font_size=sp(11), color=C_GREEN,
                            halign="left", valign="top", size_hint_y=None,
                            text_size=(dp(330), None))
            map_lbl.bind(texture_size=lambda *a:
                         setattr(map_lbl, "height", map_lbl.texture_size[1]))
            self.formula_maps[path] = map_lbl
            ti.bind(text=lambda *a, p=path: self.update_formula_map(p))
            box.add_widget(fld_label(f"{label}  ({hint})", wrap=330))
            box.add_widget(ti)
            box.add_widget(map_lbl)
            ftab.add_widget(box)

        btns = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
        b_save = Button(text="保存设置", font_size=sp(16), bold=True,
                        background_color=C_ACCENT)
        b_save.bind(on_release=lambda *a: self.on_save())
        b_reset = Button(text="恢复默认", font_size=sp(15))
        b_reset.bind(on_release=lambda *a: self.on_defaults())
        b_back = Button(text="返回", font_size=sp(15))
        b_back.bind(on_release=lambda *a: setattr(self.manager, "current", "main"))
        btns.add_widget(b_save)
        btns.add_widget(b_reset)
        btns.add_widget(b_back)
        outer.add_widget(btns)
        self.refresh_maps()

    @staticmethod
    def _make_tab(tp, title):
        item = TabbedPanelItem(text=title)
        sc = ScrollView()
        grid = GridLayout(cols=1, spacing=dp(2), padding=dp(8), size_hint_y=None)
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

    def update_formula_map(self, path):
        slot = path[-1]
        expr = self.formula_entries[path].text
        vs = formula_vars(expr)
        env = self.slot_env(slot)
        parts = []
        for v in vs:
            name, src = VAR_NAMES.get(v, (v, "自定义"))
            val = env.get(v)
            val_s = f"{val:g}" if isinstance(val, (int, float)) else str(val)
            parts.append(f"{v}={name}[{src}]={val_s}")
        self.formula_maps[path].text = ("变量对照: " + "  ".join(parts)
                                        if parts else "变量对照: (无变量)")

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
                errs.append(f"{'→'.join(map(str, path))} = {raw!r} 不是有效数字")
        for path, cb in self.bools.items():
            set_nested(s, path, bool(cb.active))
        for path, ti in self.formula_entries.items():
            raw = ti.text.strip()
            set_nested(s, path, raw)
            try:
                eval_expr(raw, SAMPLE_ENV)
            except ValueError as e:
                errs.append(f"公式[{path[-1]}]: {e}")
        if errs:
            popup_msg("\n".join(errs))
            return
        self.app.settings = s
        try:
            os.makedirs(os.path.dirname(self.app.settings_path), exist_ok=True)
            save_settings(s, self.app.settings_path)
        except OSError as e:
            popup_msg(f"保存失败: {e}")
            return
        self.app.main_screen.refresh_info()
        self.refresh_maps()
        popup_msg("设置已保存并生效")

    def on_defaults(self):
        d = default_settings()
        for path, ti in self.entries.items():
            ti.text = str(get_nested(d, path))
        for path, cb in self.bools.items():
            cb.active = bool(get_nested(d, path))
        for path, ti in self.formula_entries.items():
            ti.text = str(get_nested(d, path))


# ============================================================
class ChainPlateApp(App):
    title = "金属链板成本计算器"

    def build(self):
        # 数据目录: 默认 App 私有目录; 可被 CHAINPLATE_DATA_DIR 覆盖(本地测试用)
        data_dir = os.environ.get("CHAINPLATE_DATA_DIR") or self.user_data_dir
        self.settings_path = os.path.join(data_dir, "settings.json")
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
        self.settings_screen = SettingsScreen(self, name="settings")
        sm.add_widget(self.main_screen)
        sm.add_widget(self.settings_screen)
        return sm


if __name__ == "__main__":
    if os.environ.get("KIVY_SMOKE"):
        # 本地冒烟测试: 2 秒后自动退出 (Kivy 会占用 sys.argv, 故用环境变量触发)
        app = ChainPlateApp()
        Clock.schedule_once(lambda *a: app.stop(), 2.0)
        app.run()
        print("SMOKE OK")
    else:
        ChainPlateApp().run()
