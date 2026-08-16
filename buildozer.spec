[app]
# 应用显示名称(手机桌面图标下的名字)
title = 链板成本计算器

# 包名: 建议改成你自己的域名倒序, 如 com.你的名字.chainplatecost
package.name = chainplatecost
package.domain = com.Mengfanhua

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,txt
source.include_patterns = fonts/*

version = 1.0.0

# python3 + kivy 即可; 计算引擎是纯 Python, 无其他依赖
requirements = python3,kivy==2.3.0

orientation = portrait
fullscreen = 0

# 安卓版本: 33 (Android 13), 最低 21 (Android 5.0)
android.api = 33
android.minapi = 21
android.archs = arm64-v8a

# 接受 SDK 许可(云端构建需要)
android.accept_sdk_license = True

# 应用数据目录 user_data_dir 即可写, 设置保存在那里

[buildozer]
log_level = 2
warn_on_root = 1
