# -*- coding: utf-8 -*-
"""直接下载 Kivy 的 Windows 轮子并解压到指定目录(绕开 pip 的临时目录)。

    python tests/kvshim/getkivy.py E:\\deepseek\\kivyenv
装完后用 PYTHONPATH 指过去即可 import kivy。
"""
import io
import json
import os
import ssl
import sys
import time
import urllib.request
import zipfile

API = "https://pypi.org/pypi/%s/json"
UA = {"User-Agent": "curl/8"}

PKGS = ["kivy", "kivy_deps.sdl2", "kivy_deps.glew",
        "docutils", "pygments", "filetype", "requests",
        "urllib3", "certifi", "idna", "charset-normalizer", "Kivy-Garden",
        "pillow"]


def _get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(2 + i * 2)
    raise last


def pick(files, want_tags):
    """want_tags 现在是平台尾标签: win_amd64 / any"""
    cands = []
    for f in files:
        name = f["filename"]
        if not name.endswith(".whl"):
            continue
        parts = name[:-4].split("-")
        plat = parts[-1]
        for i, want in enumerate(want_tags):
            if plat == want:
                # 纯 Python 包优先, 其次 cp312
                is_cp312 = "cp312" in parts
                cands.append((i, 0 if (want == "any" or is_cp312) else 1, f))
                break
    if not cands:
        return None
    cands.sort(key=lambda x: (x[0], x[1]))
    return cands[0][2]


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "kivyenv")
    whl_dir = os.path.join(dest, "_whl")
    os.makedirs(whl_dir, exist_ok=True)
    want = ["win_amd64", "any"]

    todo = list(PKGS)
    done = set()
    while todo:
        pkg = todo.pop(0)
        if pkg in done:
            continue
        done.add(pkg)
        try:
            meta = json.loads(_get(API % pkg).decode("utf-8"))
        except Exception as e:
            print("SKIP", pkg, e)
            continue
        info = meta["info"]
        ver = info["version"]
        f = pick(meta["urls"], want)
        if f is None:
            print("NO WHEEL", pkg, ver)
            continue
        path = os.path.join(whl_dir, f["filename"])
        if not os.path.exists(path):
            print("GET  %-22s %-10s %s" % (pkg, ver, f["filename"]))
            data = _get(f["url"])
            with open(path, "wb") as fh:
                fh.write(data)
            print("     %.1f MB" % (len(data) / 1e6))
        else:
            print("HAVE", pkg, ver)
        for req in info.get("requires_dist") or []:
            if "extra ==" in req:
                continue
            name = req.split(";")[0].split("(")[0].split("[")[0]
            name = name.split(" ")[0].strip().rstrip("<>=")
            if name and name.lower() not in done:
                todo.append(name)
        done.add(pkg)

    for name in sorted(os.listdir(whl_dir)):
        if not name.endswith(".whl"):
            continue
        with zipfile.ZipFile(os.path.join(whl_dir, name)) as z:
            z.extractall(dest)
        print("UNPACK", name)
    print("DONE ->", dest)


if __name__ == "__main__":
    main()
