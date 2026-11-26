# -*- coding: utf-8 -*-
"""检查 main.py 里**会显示出来**的中文是否都在打包字体里。

APK 里的 fonts/simhei.ttf 是子集字体(122KB), 只有原版用到的字;
新文案如果用了子集外的字, 手机上会显示成方框。
用"渲染结果是不是 .notdef"判断, 不需要 fontTools。
(用 AST 取字符串常量, 所以注释和文档字符串不算。)
"""
import ast
import hashlib
import io
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FONT = os.path.join(ROOT, "fonts", "simhei.ttf")

_f = ImageFont.truetype(FONT, 48)
_cache = {}


def _h(ch):
    if ch in _cache:
        return _cache[ch]
    im = Image.new("L", (72, 72), 0)
    ImageDraw.Draw(im).text((8, 8), ch, font=_f, fill=255)
    _cache[ch] = hashlib.md5(im.tobytes()).hexdigest()
    return _cache[ch]


NOTDEF = _h("\uffff")


def has(ch):
    return _h(ch) != NOTDEF


def visible_strings(path):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docs:
                out.append(node.value)
    return out


def main():
    strs = visible_strings(os.path.join(ROOT, "main.py"))
    bad = {}
    for s in strs:
        for ch in s:
            if ord(ch) > 0x7F and not has(ch):
                bad.setdefault(ch, set()).add(s)
    print("可见字符串:", len(strs))
    if not bad:
        print("OK: 全部字符都在子集字体里")
        return 0
    print("缺字 %d 个:" % len(bad))
    for ch, ctx in sorted(bad.items(), key=lambda kv: ord(kv[0])):
        print("  U+%04X %s   <- %s" % (ord(ch), ch, " / ".join(sorted(ctx))[:80]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
