# -*- coding: utf-8 -*-
"""把三张预览图拼成一张对比板(深色底 + 标题 + 说明)。"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(os.path.dirname(ROOT), "preview")
FONT = os.path.join(ROOT, "fonts", "simhei.ttf")
FULL = r"C:\Windows\Fonts\msyh.ttc"   # 拼板上的说明文字用系统字, 不受子集字体限制

S = 1.0
BW, BH = 1500, 1080


def _f(size):
    try:
        return ImageFont.truetype(FULL, int(size))
    except Exception:
        return ImageFont.truetype(FONT, int(size))


def main():
    shots = [("01-main.png", "① 参数录入", "分区卡片 · 分段胶囊 · 开关 · 吸底计算"),
             ("02-main-expanded.png", "② 勾选后展开", "只有勾上的配件才展开参数区"),
             ("03-result.png", "③ 报价结果", "总价放大 + 成本结构环形图 + 明细")]
    board = Image.new("RGB", (BW, BH), (8, 10, 14))
    d = ImageDraw.Draw(board)

    # 标题
    d.text((BW // 2, 56), "金属链板成本计算器 · UI 重做", font=_f(34), fill=(236, 240, 246), anchor="mm")
    d.text((BW // 2, 96), "Kivy 实现 / 深色工业风 / 计算口径与公式完全没动（118 组黄金用例 + 21 项界面回归全过）",
           font=_f(15), fill=(126, 138, 152), anchor="mm")

    pw = 393 * 1.0
    gap = 46
    total = pw * 3 + gap * 2
    x0 = (BW - total) / 2
    top = 150
    for i, (fn, title, sub) in enumerate(shots):
        p = os.path.join(OUT, fn)
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        im = im.resize((int(pw), int(pw * im.size[1] / im.size[0])), Image.LANCZOS)
        x = int(x0 + i * (pw + gap))
        board.paste(im, (x, top))
        d.rectangle([x - 1, top - 1, x + pw, top + im.size[1]], outline=(30, 38, 48))
        d.text((x + 4, top + im.size[1] + 22), title, font=_f(17), fill=(226, 232, 240))
        d.text((x + 4, top + im.size[1] + 48), sub, font=_f(13), fill=(120, 132, 146))

    d.text((BW // 2, BH - 34), "预览由 Kivy 替身渲染 · 真机效果以 APK 为准", font=_f(12),
           fill=(88, 98, 110), anchor="mm")
    out = os.path.join(os.path.dirname(ROOT), "preview", "ui-redesign-board.png")
    board.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
