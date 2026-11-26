# -*- coding: utf-8 -*-
"""检查 main.py 里定义的类名，有没有和 Kivy 自带 kv 规则重名。

为什么需要这个检查：
    Kivy 在应用类样式规则时是**按类名匹配**的。如果自己的类改名成了
    Kivy 内置控件的名字（例如把开关命名为 Switch），那么 Kivy 在
    data/style.kv 里写的 <Switch> 规则会被套到自己的控件上。那条规则会引用
    自己控件上并不存在的属性（例如 active_norm_pos），求值得到 None，
    于是在 __init__ 里抛 TypeError，整个 App 起不来 —— 表现就是手机上
    “安装后打开闪退”。

    这个错误在 tests/kvshim（Kivy 替身）里永远不会暴露，因为替身没有 kv 规则。
    所以单独用这个脚本兜底：不 import kivy，只比对类名清单。

用法:
    python tests/check_class_names.py
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAIN = os.path.join(ROOT, "main.py")
NAMES = os.path.join(HERE, "kivy_kv_rule_names.txt")


def load_rule_names():
    names = {}
    with open(NAMES, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            names[parts[0]] = parts[1] if len(parts) > 1 else "?"
    return names


def main():
    if not os.path.exists(MAIN):
        print("找不到 main.py: %s" % MAIN)
        return 2
    if not os.path.exists(NAMES):
        print("找不到类名清单: %s" % NAMES)
        print("可以用 _tmp_gennames 类的脚本从 kivy 包里重新生成")
        return 2

    tree = ast.parse(open(MAIN, encoding="utf-8").read())
    mine = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    rules = load_rule_names()
    bad = [(c, rules[c]) for c in mine if c in rules]

    print("main.py 定义 %d 个类, Kivy 自带规则 %d 个" % (len(mine), len(rules)))
    if not bad:
        print("PASS: 没有类名与 Kivy kv 规则冲突")
        return 0
    print("FAIL: 以下类名会被套上 Kivy 的样式规则, 会导致启动崩溃")
    for name, where in bad:
        print("   %-16s 与 Kivy 规则 <%s> 冲突 (定义在 kivy/%s)" % (name, name, where))
    print("\n处理办法: 改一个不重名的类名(如 Switch -> MiniSwitch), 所有使用处一起改。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
