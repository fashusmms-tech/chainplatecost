# -*- coding: utf-8 -*-
"""界面层回归测试: 驱动真实控件, 校验"界面取值 → 计算结果"与引擎一致。

https:// 覆盖 v1.1 改动的关键点:
  - 数字框改用 text+float 过滤后, 取值仍然正确
  - 选配件未勾选时不占高度, 勾选后参数区展开
  - on_compute 组装的参数与手写参数完全一致(总价逐项相同)
  - 冲孔自动/手动两条分支
  - 上次输入的记忆(collect_state / restore_state)可往返
  - 复制用的文本就是 format_result 的输出

运行: python tests/ui_smoke.py      (需要图形环境, 本地跑; CI 只负责打包)
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_TMP = os.path.join(tempfile.gettempdir(), "chainplate_ui_test")
os.environ["KIVY_NO_ARGS"] = "1"
os.environ["KIVY_HOME"] = os.path.join(_TMP, "kivy")
os.environ["CHAINPLATE_DATA_DIR"] = os.path.join(_TMP, "data")
os.environ.setdefault("KIVY_WINDOW", "sdl2")
os.makedirs(os.environ["KIVY_HOME"], exist_ok=True)
os.makedirs(os.environ["CHAINPLATE_DATA_DIR"], exist_ok=True)

from kivy.config import Config  # noqa: E402

Config.set("graphics", "width", "360")
Config.set("graphics", "height", "740")
Config.set("graphics", "resizable", "0")
Config.set("kivy", "log_level", "error")

from kivy.clock import Clock  # noqa: E402

import main as app_mod  # noqa: E402
from chainplate_calc import compute, format_result  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print("  PASS  %s" % name)
    else:
        print("  FAIL  %s  %s" % (name, detail))
        FAILS.append(name)


class T(app_mod.ChainPlateApp):
    def build(self):
        r = super().build()
        Clock.schedule_once(self.run_tests, 0.8)
        return r

    # ---------- helpers ----------
    def reset(self):
        m = self.main_screen
        for k, (cb, _fb, inputs) in m.acc_rows.items():
            cb.active = False
            for ti in inputs.values():
                ti.text = ""
        m.sp_plate.text = "201不锈钢"
        m.cb_chain_u.active = True
        m.cb_pin_u.active = True
        for p, b in m.pitch_btns.items():
            b.state = "down" if p == "50.8" else "normal"
        m.in_width.text = "500"
        m.in_thick.text = "2.0"
        m.in_pin_d.text = "8"

    def params_for(self, width=500.0, thickness=2.0, pin_d=8.0,
                   pitch="50.8", cross=None, side=None, ball=None, wheel=None,
                   punch=None, punch_manual=None):
        p = {"pitch": pitch, "plate_mat": "201", "chain_mat": "201",
             "pin_mat": "201", "width": width, "thickness": thickness,
             "pin_d": pin_d}
        if cross:
            p["cross"] = cross
        if side:
            p["side"] = side
        if ball:
            p["ball_rows"] = ball
        if wheel:
            p["wheel_rows"] = wheel
        if punch:
            p["punch"] = True
            p["punch_manual"] = punch_manual
        return p

    # ---------- cases ----------
    def run_tests(self, *a):
        try:
            self.t_basic()
            self.t_acc()
            self.t_punch()
            self.t_state()
            self.t_copy()
            self.t_heights()
        except Exception:
            import traceback
            traceback.print_exc()
            FAILS.append("exception")
        finally:
            print("\n%s  (%d failures)" % ("ALL PASS" if not FAILS else "FAILED", len(FAILS)))
            self.stop()

    def t_basic(self):
        print("[基础计算]")
        self.reset()
        self.main_screen.on_compute()
        got = self.main_screen._last
        want = compute(self.params_for(), self.settings)
        check("总价与引擎一致", got and abs(got["total_per_meter"] - want["total_per_meter"]) < 1e-9,
              "%r vs %r" % (got and got["total_per_meter"], want["total_per_meter"]))

    def t_acc(self):
        print("[选配件]")
        self.reset()
        m = self.main_screen
        for k in ("cross", "side", "ball", "wheel"):
            m.acc_rows[k][0].active = True
        m.acc_rows["cross"][2]["length"].text = "120"
        m.acc_rows["cross"][2]["height"].text = "60"
        m.acc_rows["cross"][2]["thickness"].text = "2.0"
        m.acc_rows["cross"][2]["interval"].text = "200"
        m.acc_rows["side"][2]["height"].text = "60"
        m.acc_rows["side"][2]["thickness"].text = "2.0"
        m.acc_rows["ball"][2]["rows"].text = "1"
        m.acc_rows["wheel"][2]["rows"].text = "1"
        m.in_width.text = "800"
        m.on_compute()
        got = m._last
        want = compute(self.params_for(
            width=800.0,
            cross={"length": 120.0, "height": 60.0, "thickness": 2.0, "interval": 200.0},
            side={"height": 60.0, "thickness": 2.0}, ball=1, wheel=1), self.settings)
        check("全选配件总价一致",
              got and abs(got["total_per_meter"] - want["total_per_meter"]) < 1e-9,
              "%r vs %r" % (got and got["total_per_meter"], want["total_per_meter"]))
        check("横挡板件数=4", got and got["cross"]["count"] == 4,
              got and got["cross"]["count"])

    def t_punch(self):
        print("[冲孔 自动/手动]")
        self.reset()
        m = self.main_screen
        m.acc_rows["punch"][0].active = True
        m.in_thick.text = "1.0"
        self._hint = m.lbl_punch_hint.text
        check("薄板提示为自动", "自动" in self._hint, self._hint)
        m.on_compute()
        got = m._last
        check("自动冲孔=0.5", got and abs(got["punch"]["price"] - 0.5) < 1e-9,
              got and got["punch"]["price"])

        m.in_thick.text = "2.0"
        m.acc_rows["punch"][2]["price"].text = "1.5"
        check("厚板提示为手动", "手动" in m.lbl_punch_hint.text, m.lbl_punch_hint.text)
        m.on_compute()
        got = m._last
        want = compute(self.params_for(punch=True, punch_manual=1.5), self.settings)
        check("手动冲孔总价一致",
              got and abs(got["total_per_meter"] - want["total_per_meter"]) < 1e-9,
              "%r vs %r" % (got and got["total_per_meter"], want["total_per_meter"]))

    def t_state(self):
        print("[记忆上次输入]")
        self.reset()
        m = self.main_screen
        m.sp_plate.text = "304不锈钢"
        m.cb_chain_u.active = False
        m.sp_chain.text = "201不锈钢"
        m.pitch_btns["38.1"].state = "down"
        m.pitch_btns["50.8"].state = "normal"
        m.in_width.text = "650"
        m.acc_rows["side"][0].active = True
        m.acc_rows["side"][2]["height"].text = "55"
        st = m.collect_state()
        check("state 记录材质", st["plate"] == "304不锈钢", st["plate"])
        check("state 记录节距", st["pitch"] == "38.1", st["pitch"])
        check("state 记录链条非联动", st["chain_u"] is False, st["chain_u"])

        self.reset()
        m.restore_state(st)
        check("恢复板材质", m.sp_plate.text == "304不锈钢", m.sp_plate.text)
        check("恢复节距", m.pitch() == "38.1", m.pitch())
        check("恢复宽度", m.in_width.text == "650", m.in_width.text)
        check("恢复侧挡板勾选", m.acc_rows["side"][0].active is True)
        check("恢复侧挡板高度", m.acc_rows["side"][2]["height"].text == "55")
        st2 = m.collect_state()
        check("往返一致", st2 == st, "%r != %r" % (st2, st))

    def t_copy(self):
        print("[复制文本]")
        self.reset()
        self.main_screen.on_compute()
        txt = format_result(self.main_screen._last)
        check("复制文本含每米总价", "每米总价" in txt)
        check("复制文本含材质行", "201不锈钢" in txt)

    def t_heights(self):
        print("[布局: 选配件占位]")
        self.reset()
        m = self.main_screen
        heights = [fb.height for _, fb, _ in m.acc_rows.values()]
        check("未勾选时高度全为 0", all(h == 0 for h in heights), heights)
        m.acc_rows["cross"][0].active = True
        check("勾选后高度>0", m.acc_rows["cross"][1].height > 0,
              m.acc_rows["cross"][1].height)
        check("勾选后 opacity=1", m.acc_rows["cross"][1].opacity == 1)
        m.acc_rows["cross"][0].active = False
        check("取消勾选归零", m.acc_rows["cross"][1].height == 0)


T().run()
sys.exit(1 if FAILS else 0)
