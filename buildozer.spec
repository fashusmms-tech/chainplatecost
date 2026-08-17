[app]
title = 链板成本计算器

package.name = chainplatecost
package.domain = com.Mengfanhua

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,txt
source.include_patterns = fonts/*

version = 1.0.0

# 钉死 p4a 到 2024.06.16(默认 Python 3.11), 与 kivy 2.3.0 兼容
# (2026 新版 p4a 默认 Python 3.14 会导致 kivy 编译失败)
requirements = python3,kivy==2.3.0
p4a.branch = v2024.06.16

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 21
android.archs = arm64-v8a

# NDK 25b 是与 kivy 2.3.0 最稳的组合
android.ndk = 25b

android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
