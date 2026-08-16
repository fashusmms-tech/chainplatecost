# -*- coding: utf-8 -*-
"""
金属链板成本计算引擎 (纯逻辑, 无界面依赖)
所有公式常数集中在 DEFAULT_SETTINGS, 可被 settings.json 覆盖(设置界面修改)
"""

import copy
import json
import os

# ---------------- 固定数据 ----------------
PITCHES = ["25.4", "31.75", "38.1", "50.8", "假两寸"]
PITCH_VALUE = {"25.4": 25.4, "31.75": 31.75, "38.1": 38.1, "50.8": 50.8, "假两寸": 50.8}
# 假两寸: 节距按 50.8, 其余链条参数(宽度等)与 38.1 相同
CHAIN_PARAM = {"25.4": "25.4", "31.75": "31.75", "38.1": "38.1", "50.8": "50.8", "假两寸": "38.1"}
MATERIAL_KEYS = ["201", "304", "carbon"]
MATERIAL_NAMES = {"201": "201不锈钢", "304": "304不锈钢", "carbon": "碳钢"}

# ---------------- 默认常数(设置界面可改) ----------------
DEFAULT_SETTINGS = {
    "sheet_price": {"201": 7.8, "304": 14.5, "carbon": 5.0},          # 板材价格 元/kg
    "chain_price": {                                                    # 链条价格 元/米
        "201":    {"25.4": 20.0, "31.75": 19.0, "38.1": 26.0, "50.8": 37.0, "假两寸": 23.0},
        "304":    {"25.4": 20.0, "31.75": 25.5, "38.1": 38.0, "50.8": 54.5, "假两寸": 33.0},
        "carbon": {"25.4": 10.0, "31.75": 11.0, "38.1": 14.0, "50.8": 20.0, "假两寸": 12.0},
    },                                                                  # 注: 碳钢假两寸原表未给出, 默认12元/米(可按实际修改)
    "chain_width": {"25.4": 38.0, "31.75": 41.0, "38.1": 55.0, "50.8": 62.0, "假两寸": 55.0},
    "const": {
        "density": 0.00793,     # 板重量密度系数
        "pin_pi": 3.14,         # 板公式中 穿杆直径×3.14
        "pin_coef": 0.00623,    # 穿杆重量系数
        "pin_fee": 0.1,         # 穿杆工费(元)
        "flight_margin": 15.0,  # 挡板公式中 高+15
        "labor": 0.0,           # 人工成本(元/片, 默认0不计入)
    },
    "cut": {                    # 切割费用(分档)
        "band1": {"max_t": 1.2, "flat_w": 600.0, "flat_fee": 0.5},          # 厚≤1.2: w≤600→0.5, w>600→w/1000
        "band2": {"min_t": 1.5, "max_t": 2.0, "flat_w": 600.0,              # 1.5~2: w≤600→0.7,
                  "formula_w": 700.0, "flat_fee": 0.7, "formula_extra": 0.3},  # w>700→w/1000+0.3
        "band3": {"min_t": 3.0, "flat_w": 600.0, "flat_fee": 1.0,           # ≥3: w≤600→1, w>600→w/1000+0.6
                  "formula_extra": 0.6},
    },
    "punch": {"equals_cut": True, "manual_fee": 0.0},   # 冲床费用=切割费用(默认); 关闭后用手动值
    "weld": {"max_d": 8.0, "fee_small": 0.8, "fee_large": 1.0},            # 焊接: 穿杆直径≤8→0.8, 否则1.0
    "punch_hole": {                                     # 冲孔(选配件)
        "auto_max_t": 1.2,       # 板厚<1.2 自动计算
        "auto_flat_w": 500.0,    # 有效宽度<500→0.5, ≥500→宽/1000
        "auto_flat_fee": 0.5,
        "manual_min_t": 1.5,     # 板厚>1.5 需手动输入 (1.2~1.5 区间同样手动)
    },
    "accessory": {
        "cross_fee": 1.5,   # 横挡板工费(元)
        "side_fee": 0.4,    # 侧挡板工费(元)
        "ball": 1.0,        # 辅助载重滚珠 元/个
        "wheel": 3.5,       # 辅助载重支轮 元/个
    },
}

# ---------------- 公式(可在设置界面修改) ----------------
# 默认公式与报价单一致; 变量含义见设置界面的提示
DEFAULT_FORMULAS = {
    "plate": "(pin_d * pin_pi + pitch + thickness) * width * thickness * density * sheet_price / 1000 + cut_fee + punch_fee + weld_fee",
    "pin": "pin_d * pin_d * (width + chain_width) * pin_coef * sheet_price / 1000 + pin_fee",
    "cross": "length * (height + flight_margin) * thickness * density * sheet_price / 1000 + cross_fee",
    "side": "(pitch + chain_width / 2) * (height + flight_margin) * thickness * density * sheet_price / 1000 + side_fee",
    "cut_b1_flat": "flat_fee",
    "cut_b1_wide": "width / 1000",
    "cut_b2_flat": "flat_fee",
    "cut_b2_wide": "width / 1000 + formula_extra",
    "cut_b3_flat": "flat_fee",
    "cut_b3_wide": "width / 1000 + formula_extra",
    "weld_small": "fee_small",
    "weld_large": "fee_large",
    "punch_auto_flat": "auto_flat_fee",
    "punch_auto_wide": "width / 1000",
    "total": "per_meter * plate + per_meter * pin + chain_total + side_total + cross_total + per_meter * punch + ball_total + wheel_total + per_meter * labor",
}

# 公式校验用的示例变量(设置界面"测试公式"用)
SAMPLE_ENV = {
    "pin_d": 8.0, "pitch": 50.8, "thickness": 2.0, "width": 500.0,
    "sheet_price": 7.8, "chain_width": 62.0, "length": 100.0, "height": 50.0,
    "density": 0.00793, "pin_pi": 3.14, "pin_coef": 0.00623, "pin_fee": 0.1,
    "flight_margin": 15.0, "cross_fee": 1.5, "side_fee": 0.4,
    "cut_fee": 0.7, "punch_fee": 0.7, "weld_fee": 0.8,
    "flat_fee": 0.7, "formula_extra": 0.3,
    "fee_small": 0.8, "fee_large": 1.0, "max_d": 8.0, "auto_flat_fee": 0.5,
    "per_meter": 19.685, "plate": 7.0, "pin": 1.8, "chain_total": 74.0,
    "side_total": 33.0, "cross_total": 23.0, "punch": 1.0,
    "ball_total": 0.0, "wheel_total": 0.0, "labor": 0.0,
}

# 把公式挂进设置(设置界面可修改, 保存到 settings.json)
DEFAULT_SETTINGS["formulas"] = dict(DEFAULT_FORMULAS)

# ---------------- 安全表达式求值 ----------------
import ast
import operator as _op

_ALLOWED_BINOPS = {
    ast.Add: _op.add, ast.Sub: _op.sub, ast.Mult: _op.mul,
    ast.Div: _op.truediv, ast.Mod: _op.mod, ast.Pow: _op.pow,
}
_ALLOWED_UNOPS = {ast.USub: _op.neg, ast.UAdd: _op.pos}


def eval_expr(expr, env):
    """安全求值算术表达式: 数字/变量/+-*\/%**/括号/一元负号/round()
    不执行任意代码(基于 ast 白名单), 变量不在 env 中或语法非法会抛 ValueError"""
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"公式语法错误: {e}")

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise ValueError(f"公式里有未知变量: {node.id}")
            return env[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            return _ALLOWED_BINOPS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNOPS:
            return _ALLOWED_UNOPS[type(node.op)](walk(node.operand))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "round" and 1 <= len(node.args) <= 2
                and not node.keywords):
            v = walk(node.args[0])
            nd = walk(node.args[1]) if len(node.args) == 2 else 0
            return round(v, int(nd))
        raise ValueError(f"公式含不支持的写法: {type(node).__name__}")
    try:
        return walk(tree)
    except ZeroDivisionError:
        raise ValueError("公式出现除零")


def eval_formula(slot, s, env):
    """按槽位取公式并求值; 缺省回退默认公式"""
    formula = (s.get("formulas") or {}).get(slot) or DEFAULT_FORMULAS[slot]
    try:
        return eval_expr(formula, env)
    except ValueError as e:
        raise ValueError(f"[{slot}] {e}")


# ---------------- 变量对照表 (设置界面显示用) ----------------
# 变量名 -> (中文名, 来源)
VAR_NAMES = {
    "pin_d": ("穿杆直径", "主界面·基础尺寸"),
    "pitch": ("节距", "主界面·节距选择"),
    "thickness": ("板厚", "主界面·基础尺寸"),
    "width": ("有效宽度", "主界面·基础尺寸"),
    "sheet_price": ("板材价格(当前材质)", "设置·板材价格"),
    "chain_width": ("链条宽度(当前节距)", "设置·链条宽度"),
    "length": ("横挡板长度", "主界面·横挡板"),
    "height": ("挡板高度", "主界面·横挡板/侧挡板"),
    "density": ("密度系数", "设置·公式常数"),
    "pin_pi": ("穿杆直径系数3.14", "设置·公式常数"),
    "pin_coef": ("穿杆重量系数0.00623", "设置·公式常数"),
    "pin_fee": ("穿杆工费", "设置·公式常数"),
    "flight_margin": ("挡板高度加值15", "设置·公式常数"),
    "labor": ("人工成本/片", "设置·公式常数"),
    "cut_fee": ("切割费", "自动·按板厚/宽度分档"),
    "punch_fee": ("冲床费", "自动·=切割费"),
    "weld_fee": ("焊接费", "自动·按穿杆直径分档"),
    "flat_fee": ("该档平费", "设置·切割费用"),
    "formula_extra": ("超宽加价", "设置·切割费用"),
    "fee_small": ("小直径焊接费", "设置·焊接"),
    "fee_large": ("大直径焊接费", "设置·焊接"),
    "max_d": ("焊接分档直径", "设置·焊接"),
    "auto_flat_fee": ("冲孔平费", "设置·冲孔"),
    "cross_fee": ("横挡板工费", "设置·选配件"),
    "side_fee": ("侧挡板工费", "设置·选配件"),
    "per_meter": ("每米片数(1000÷节距)", "自动"),
    "plate": ("板价格", "计算结果"),
    "pin": ("穿杆价格", "计算结果"),
    "chain_total": ("链条总价×2", "计算结果"),
    "side_total": ("侧挡板总价", "计算结果"),
    "cross_total": ("横挡板总价", "计算结果"),
    "punch": ("冲孔价格", "计算结果"),
    "ball_total": ("滚珠总价", "计算结果"),
    "wheel_total": ("支轮总价", "计算结果"),
}


def formula_vars(expr):
    """提取公式中用到的变量名(按出现顺序去重); 语法错误返回空"""
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in out:
            out.append(node.id)
    return out
# ---------------- 设置读写 ----------------
def deep_merge(base, extra):
    """递归合并, base 为模板(缺失键用默认值)"""
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out

def default_settings():
    return copy.deepcopy(DEFAULT_SETTINGS)

def load_settings(path=None):
    s = default_settings()
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                s = deep_merge(s, json.load(f))
        except Exception:
            pass
    return s

def save_settings(s, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

# ---------------- 公式实现 (各价格公式可在设置中修改) ----------------
def cut_fee(thickness, width, s):
    """切割费用(元/片): 分档逻辑不变, 档内金额表达式可在设置中修改"""
    cut = s["cut"]
    b1, b2, b3 = cut["band1"], cut["band2"], cut["band3"]
    if thickness <= b1["max_t"]:
        if width <= b1["flat_w"]:
            return eval_formula("cut_b1_flat", s, {"flat_fee": b1["flat_fee"], "width": width})
        return eval_formula("cut_b1_wide", s, {"width": width, "flat_fee": b1["flat_fee"]})
    if thickness <= b2["max_t"]:   # 含 1.2~1.5 未定义区间, 归入中板档
        if width <= b2["flat_w"]:
            return eval_formula("cut_b2_flat", s, {"flat_fee": b2["flat_fee"], "width": width})
        if width <= b2["formula_w"]:   # 600~700 未定义区间, 按平费
            return eval_formula("cut_b2_flat", s, {"flat_fee": b2["flat_fee"], "width": width})
        return eval_formula("cut_b2_wide", s, {"width": width, "formula_extra": b2["formula_extra"],
                                               "flat_fee": b2["flat_fee"]})
    # 厚板档 (含 2~3 未定义区间)
    if width <= b3["flat_w"]:
        return eval_formula("cut_b3_flat", s, {"flat_fee": b3["flat_fee"], "width": width})
    return eval_formula("cut_b3_wide", s, {"width": width, "formula_extra": b3["formula_extra"],
                                           "flat_fee": b3["flat_fee"]})

def punch_fee(thickness, width, s):
    """冲床费用 = 切割费用(默认); 可关闭后用手动值"""
    p = s["punch"]
    if p["equals_cut"]:
        return cut_fee(thickness, width, s)
    return p.get("manual_fee", 0.0)

def weld_fee(pin_d, s):
    """焊接费用(元/根): 分档逻辑固定, 档内金额表达式可在设置中修改"""
    w = s["weld"]
    env = {"pin_d": pin_d, "max_d": w["max_d"],
           "fee_small": w["fee_small"], "fee_large": w["fee_large"]}
    if pin_d <= w["max_d"]:
        return eval_formula("weld_small", s, env)
    return eval_formula("weld_large", s, env)

def plate_price_full(thickness, width, pin_d, pitch_val, sheet_price, s):
    """板价格(元/片) — 公式可在设置中修改"""
    c = s["const"]
    env = {"pin_d": pin_d, "pitch": pitch_val, "thickness": thickness,
           "width": width, "sheet_price": sheet_price,
           "density": c["density"], "pin_pi": c["pin_pi"],
           "cut_fee": cut_fee(thickness, width, s),
           "punch_fee": punch_fee(thickness, width, s),
           "weld_fee": weld_fee(pin_d, s)}
    return eval_formula("plate", s, env)

def pin_price(pin_d, width, chain_width, sheet_price, s):
    """穿杆价格(元/根) — 公式可在设置中修改"""
    c = s["const"]
    env = {"pin_d": pin_d, "width": width, "chain_width": chain_width,
           "sheet_price": sheet_price, "pin_coef": c["pin_coef"],
           "pin_fee": c["pin_fee"]}
    return eval_formula("pin", s, env)

def chain_price(material, pitch_key, s):
    """链条价格(元/米), 固定表"""
    tbl = s["chain_price"].get(material, {})
    if pitch_key in tbl:
        return tbl[pitch_key]
    return tbl.get("50.8", 0.0)   # 缺项时回退到 50.8 档

def chain_width_of(pitch_key, s):
    return s["chain_width"].get(pitch_key, 38.0)

def cross_flight_price(length, height, thickness, sheet_price, s):
    """横挡板价格(元/件) — 公式可在设置中修改"""
    c = s["const"]
    env = {"length": length, "height": height, "thickness": thickness,
           "sheet_price": sheet_price, "density": c["density"],
           "flight_margin": c["flight_margin"],
           "cross_fee": s["accessory"]["cross_fee"]}
    return eval_formula("cross", s, env)

def side_flight_price(pitch_val, chain_width, height, thickness, sheet_price, s):
    """侧挡板价格(元/件) — 公式可在设置中修改"""
    c = s["const"]
    env = {"pitch": pitch_val, "chain_width": chain_width, "height": height,
           "thickness": thickness, "sheet_price": sheet_price,
           "density": c["density"], "flight_margin": c["flight_margin"],
           "side_fee": s["accessory"]["side_fee"]}
    return eval_formula("side", s, env)

def cross_flight_count(interval, pitch_val):
    """横挡板数量 = 间隔÷节距, 四舍五入取整"""
    return int(interval / pitch_val + 0.5)

def punch_hole_price(thickness, width, s, manual=None):
    """冲孔价格(元/片): 板厚<1.2 自动(金额表达式可改); 否则手动输入"""
    ph = s["punch_hole"]
    if thickness < ph["auto_max_t"]:
        if width < ph["auto_flat_w"]:
            return eval_formula("punch_auto_flat", s,
                                {"auto_flat_fee": ph["auto_flat_fee"], "width": width})
        return eval_formula("punch_auto_wide", s,
                            {"width": width, "auto_flat_fee": ph["auto_flat_fee"]})
    return manual if manual is not None else 0.0

# ---------------- 总计算 ----------------
def compute(params, s=None):
    """params: 见下方; 返回明细 dict
    params = {
      pitch, plate_mat, chain_mat, pin_mat,
      width, thickness, pin_d,
      cross: {length,height,thickness,interval} | None,
      side: {height,thickness} | None,
      ball_rows: int|None, wheel_rows: int|None,
      punch: float|None (手动冲孔价, 未给且需手动时记0),
    }
    """
    s = s or default_settings()
    pitch_key = params["pitch"]
    pitch_val = PITCH_VALUE[pitch_key]
    cw = chain_width_of(pitch_key, s)
    per_meter = 1000.0 / pitch_val

    sheet_p = s["sheet_price"]
    plate_sp = sheet_p[params["plate_mat"]]
    pin_sp = sheet_p[params["pin_mat"]]

    width = params["width"]
    thickness = params["thickness"]
    pin_d = params["pin_d"]

    # 1) 板
    pl = plate_price_full(thickness, width, pin_d, pitch_val, plate_sp, s)
    # 2) 穿杆
    pin = pin_price(pin_d, width, cw, pin_sp, s)
    # 3) 链条
    ch = chain_price(params["chain_mat"], pitch_key, s)
    # 4) 横挡板
    cross = None
    if params.get("cross"):
        cp = cross_flight_price(params["cross"]["length"], params["cross"]["height"],
                                params["cross"]["thickness"], plate_sp, s)
        cnt = cross_flight_count(params["cross"]["interval"], pitch_val)
        cross = {"price": cp, "count": cnt, "total": cp * cnt}
    # 5) 侧挡板
    side = None
    if params.get("side"):
        sp = side_flight_price(pitch_val, cw, params["side"]["height"],
                               params["side"]["thickness"], plate_sp, s)
        side = {"price": sp, "total": sp * 2.0 * per_meter}
    # 6) 冲孔
    punch = None
    if params.get("punch") is not None:
        pv = punch_hole_price(thickness, width, s, params.get("punch_manual"))
        punch = {"price": pv, "auto": thickness < s["punch_hole"]["auto_max_t"]}
    # 7) 滚珠/支轮
    ball = None
    if params.get("ball_rows"):
        ball = {"unit": s["accessory"]["ball"], "rows": params["ball_rows"],
                "total": s["accessory"]["ball"] * params["ball_rows"] * per_meter}
    wheel = None
    if params.get("wheel_rows"):
        wheel = {"unit": s["accessory"]["wheel"], "rows": params["wheel_rows"],
                 "total": s["accessory"]["wheel"] * params["wheel_rows"] * per_meter}

    labor = s["const"].get("labor", 0.0)

    cut = cut_fee(thickness, width, s)
    punch_f = punch_fee(thickness, width, s)
    weld = weld_fee(pin_d, s)
    pl_material = pl - cut - punch_f - weld

    env = {"per_meter": per_meter, "plate": pl, "pin": pin,
           "chain_total": ch * 2.0,
           "side_total": side["total"] if side else 0.0,
           "cross_total": cross["total"] if cross else 0.0,
           "punch": punch["price"] if punch else 0.0,
           "ball_total": ball["total"] if ball else 0.0,
           "wheel_total": wheel["total"] if wheel else 0.0,
           "labor": labor}
    total = eval_formula("total", s, env)

    return {
        "pitch_key": pitch_key, "pitch_val": pitch_val, "per_meter": per_meter,
        "chain_width": cw, "plate_mat": params["plate_mat"],
        "chain_mat": params["chain_mat"], "pin_mat": params["pin_mat"],
        "sheet_price": plate_sp,
        "plate": {"material": pl_material, "cut": cut,
                  "punch": punch_f, "weld": weld, "total": pl},
        "pin": {"total": pin},
        "chain": {"unit": ch, "total": ch * 2.0},
        "cross": cross, "side": side, "punch": punch,
        "ball": ball, "wheel": wheel, "labor": labor,
        "total_per_meter": total,
    }

def format_result(r):
    """把明细 dict 格式化成多行文本"""
    L = []
    L.append("=" * 46)
    L.append(f"金属链板成本明细  节距 {r['pitch_key']} mm")
    L.append("=" * 46)
    L.append(f"材质: 板 {MATERIAL_NAMES[r['plate_mat']]} | 链条 {MATERIAL_NAMES[r['chain_mat']]}"
             f" | 穿杆 {MATERIAL_NAMES[r['pin_mat']]}")
    L.append(f"板材价格 {r['sheet_price']:.2f} 元/kg | 链条宽度 {r['chain_width']:.0f} mm")
    L.append("")
    L.append("【每片/每件价格】")
    L.append(f"  板价格     {r['plate']['total']:8.2f} 元/片"
             f" (材料 {r['plate']['material']:.2f} + 切割 {r['plate']['cut']:.2f}"
             f" + 冲床 {r['plate']['punch']:.2f} + 焊接 {r['plate']['weld']:.2f})")
    L.append(f"  穿杆价格   {r['pin']['total']:8.2f} 元/根")
    L.append(f"  链条价格   {r['chain']['unit']:8.2f} 元/米")
    if r["side"]:
        L.append(f"  侧挡板价格 {r['side']['price']:8.2f} 元/件")
    if r["cross"]:
        L.append(f"  横挡板价格 {r['cross']['price']:8.2f} 元/件 × 数量 {r['cross']['count']}"
                 f" (间隔÷节距 四舍五入)")
    if r["punch"]:
        mode = "自动" if r["punch"]["auto"] else "手动"
        L.append(f"  冲孔价格   {r['punch']['price']:8.2f} 元/片 ({mode})")
    if r["ball"]:
        L.append(f"  辅助载重滚珠 {r['ball']['unit']:.2f} 元/个 × {r['ball']['rows']} 排")
    if r["wheel"]:
        L.append(f"  辅助载重支轮 {r['wheel']['unit']:.2f} 元/个 × {r['wheel']['rows']} 排")
    L.append("")
    L.append("【每米总价 (1000÷节距×各项)】")
    L.append(f"  板     {r['plate']['total'] * r['per_meter']:9.2f} 元")
    L.append(f"  穿杆   {r['pin']['total'] * r['per_meter']:9.2f} 元")
    L.append(f"  链条   {r['chain']['total']:9.2f} 元 ({r['chain']['unit']:.2f} × 2 根)")
    if r["side"]:
        L.append(f"  侧挡板 {r['side']['total']:9.2f} 元")
    if r["cross"]:
        L.append(f"  横挡板 {r['cross']['total']:9.2f} 元")
    if r["punch"]:
        L.append(f"  冲孔   {r['punch']['price'] * r['per_meter']:9.2f} 元")
    if r["ball"]:
        L.append(f"  滚珠   {r['ball']['total']:9.2f} 元")
    if r["wheel"]:
        L.append(f"  支轮   {r['wheel']['total']:9.2f} 元")
    if r["labor"]:
        L.append(f"  人工   {r['labor'] * r['per_meter']:9.2f} 元")
    L.append("-" * 46)
    L.append(f"  每米总价: {r['total_per_meter']:.2f} 元/米")
    return "\n".join(L)
