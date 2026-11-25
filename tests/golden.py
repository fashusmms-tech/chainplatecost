# -*- coding: utf-8 -*-
"""生成/校验"黄金用例"：锁死计算引擎的输出，防止优化过程改到价格。

用法:
    python tests/golden.py gen     # 生成 tests/golden.json（仅在确认公式未变时执行）
    python tests/golden.py check   # 校验当前引擎输出与 golden.json 完全一致

只调用 chainplate_calc.compute()，不涉及界面。
"""
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import chainplate_calc as cc  # noqa: E402

GOLDEN = os.path.join(HERE, "golden.json")

PITCHES = cc.PITCHES
MATS = cc.MATERIAL_KEYS
DIMS = [(300.0, 1.0, 5.0), (500.0, 2.0, 8.0), (800.0, 3.0, 10.0), (650.0, 1.5, 6.0)]
ACC = [
    {},
    {"side": {"height": 50.0, "thickness": 2.0}},
    {"cross": {"length": 100.0, "height": 50.0, "thickness": 2.0, "interval": 200.0}},
    {"ball_rows": 2},
    {"wheel_rows": 1},
    {"punch": True, "punch_manual": 1.2},
    {"side": {"height": 60.0, "thickness": 2.0},
     "cross": {"length": 120.0, "height": 60.0, "thickness": 2.0, "interval": 200.0},
     "ball_rows": 1, "wheel_rows": 1, "punch": True, "punch_manual": 1.5},
]


def cases():
    out = []
    # 1) 节距 × 材质 × 尺寸
    for pitch, mat, (w, t, d) in itertools.product(PITCHES, MATS, DIMS):
        out.append(("pitch=%s,mat=%s,w=%s,t=%s,d=%s" % (pitch, mat, w, t, d),
                    dict(pitch=pitch, plate_mat=mat, chain_mat=mat, pin_mat=mat,
                         width=w, thickness=t, pin_d=d)))
    # 2) 选配件组合（默认 50.8 / 201）
    for i, acc in enumerate(ACC):
        p = dict(pitch="50.8", plate_mat="201", chain_mat="201", pin_mat="201",
                 width=500.0, thickness=2.0, pin_d=8.0)
        p.update(acc)
        out.append(("acc#%d" % i, p))
    # 3) 混合材质（板 304 / 链条 201 / 穿杆 碳钢）
    for pitch in PITCHES:
        out.append(("mixed=%s" % pitch,
                    dict(pitch=pitch, plate_mat="304", chain_mat="201", pin_mat="carbon",
                         width=600.0, thickness=2.0, pin_d=8.0)))
    # 4) 分档边界厚度/宽度
    for t in (1.0, 1.2, 1.3, 1.5, 2.0, 2.5, 3.0):
        for w in (400.0, 600.0, 601.0, 700.0, 701.0, 1000.0):
            out.append(("band t=%s,w=%s" % (t, w),
                        dict(pitch="50.8", plate_mat="201", chain_mat="201", pin_mat="201",
                             width=w, thickness=t, pin_d=8.0)))
    # 5) 穿杆直径边界（焊接分档 8）
    for d in (6.0, 8.0, 8.1, 10.0):
        out.append(("pin d=%s" % d,
                    dict(pitch="50.8", plate_mat="201", chain_mat="201", pin_mat="201",
                         width=500.0, thickness=2.0, pin_d=d)))
    return out


def snapshot(settings=None):
    s = settings or cc.default_settings()
    data = {}
    for name, params in cases():
        r = cc.compute(dict(params), s)
        data[name] = {
            "total_per_meter": round(r["total_per_meter"], 6),
            "per_meter": round(r["per_meter"], 6),
            "plate_total": round(r["plate"]["total"], 6),
            "plate_material": round(r["plate"]["material"], 6),
            "plate_cut": round(r["plate"]["cut"], 6),
            "plate_punch": round(r["plate"]["punch"], 6),
            "plate_weld": round(r["plate"]["weld"], 6),
            "pin_total": round(r["pin"]["total"], 6),
            "chain_unit": round(r["chain"]["unit"], 6),
            "side": round(r["side"]["total"], 6) if r["side"] else None,
            "cross": round(r["cross"]["total"], 6) if r["cross"] else None,
            "cross_count": r["cross"]["count"] if r["cross"] else None,
            "punch": round(r["punch"]["price"], 6) if r["punch"] else None,
            "ball": round(r["ball"]["total"], 6) if r["ball"] else None,
            "wheel": round(r["wheel"]["total"], 6) if r["wheel"] else None,
            "text_sha": _sha(cc.format_result(r)),
        }
    return data


def _sha(text):
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode == "gen":
        data = snapshot()
        with open(GOLDEN, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        print("golden written: %d cases -> %s" % (len(data), GOLDEN))
        return 0
    if mode != "check":
        print("unknown mode:", mode)
        return 2
    if not os.path.exists(GOLDEN):
        print("missing", GOLDEN)
        return 2
    with open(GOLDEN, encoding="utf-8") as f:
        want = json.load(f)
    got = snapshot()
    bad = []
    for k in sorted(set(want) | set(got)):
        if want.get(k) != got.get(k):
            bad.append((k, want.get(k), got.get(k)))
    if bad:
        print("FAIL: %d/%d cases differ" % (len(bad), len(want)))
        for k, a, b in bad[:10]:
            print(" ", k)
            if a and b:
                for f2 in a:
                    if a[f2] != b.get(f2):
                        print("    %s: %r -> %r" % (f2, a[f2], b.get(f2)))
        return 1
    print("PASS: %d cases identical (数值与格式文本完全一致)" % len(want))
    return 0


if __name__ == "__main__":
    sys.exit(main())
