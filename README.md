# 链板成本计算器 — 手机版 (Android APK)

电脑版(Windows exe)的手机版。计算逻辑与电脑版完全一致，界面用 Kivy 重写，
适合手机触屏操作。**APK 由 GitHub Actions 云端自动编译**，无需在本机安装
任何安卓工具链。

## 文件说明

| 文件 | 说明 |
|---|---|
| `main.py` | Kivy 手机界面（计算 + 选配件 + 设置 + 公式编辑 + 变量对照） |
| `chainplate_calc.py` | 计算引擎（纯 Python，与电脑版同一份） |
| `fonts/simhei.ttf` | 内置中文字体（安卓默认字体不支持中文） |
| `buildozer.spec` | 打包配置（应用名、包名、版本、安卓版本等） |
| `.github/workflows/build-apk.yml` | GitHub 云端自动构建脚本 |

## 第一次构建步骤（约 10 分钟操作）

1. **注册/登录 GitHub**（https://github.com），没有账号先注册（免费）。

2. **新建仓库**：右上角 + → New repository
   - Repository name: `chainplatecost`
   - 公开或私有都行（私有推荐）
   - 不要勾选任何初始化选项（README 等都不要）
   - 点 Create repository

3. **上传代码**（任选一种）：
   - 方式 A（网页上传，简单）：
     打开仓库页面 → Add file → Upload files → 把本文件夹里的
     `main.py`、`chainplate_calc.py`、`buildozer.spec`、`fonts` 文件夹、
     `.github` 文件夹全部拖进去 → Commit changes
     （注意 .github 是隐藏文件夹，网页上传时直接拖整个文件夹即可）
   - 方式 B（git 命令）：
     ```
     cd E:\deepseek\chainplate_android
     git init
     git add .
     git commit -m "链板成本计算器 手机版"
     git branch -M main
     git remote add origin https://github.com/你的用户名/chainplatecost.git
     git push -u origin main
     ```
     （推送时会要求输入 GitHub 用户名和 Token；Token 在 GitHub →
      Settings → Developer settings → Personal access tokens 生成，
      repo 权限即可）

4. **等待云端构建**：
   仓库页面 → Actions 页签 → 会自动开始 "Build APK" 工作流，
   首次构建约 **20~40 分钟**（要下载安卓 SDK），之后每次改代码
   重新 push 会自动构建（约 5~15 分钟）。

5. **下载 APK**：构建完成后（绿色 ✓）→ 点击该次运行 → 底部
   Artifacts → 下载 `chainplatecost-apk` → 解压得到
   `chainplatecost-1.0.0-arm64-v8a-debug.apk`。

6. **安装到手机**：
   - 把 apk 传到手机（微信文件传输助手 / QQ / 数据线都行）
   - 手机点开 apk → 允许"安装未知应用"（首次会提示）
   - 安装完成即可使用；图标名为"链板成本计算器"

## 使用说明（手机版）

- **计算**：选材质/节距 → 输入尺寸 → 勾选选配件后参数框自动出现 →
  点【计算】→ 下方显示逐项明细和每米总价
- **设置**：主界面点【设置】→ 8 个页签（板材价格/链条价格/链条宽度/
  公式常数/切割冲床焊接/冲孔/选配件/公式）→ 改完点【保存设置】
- **公式**：公式页签可直接修改计算公式，每条公式下方有变量对照
  （变量=中文名=当前值）；改完可点保存，写错会提示
- 设置保存在手机 App 私有目录（卸载 App 会清空，重装后恢复默认）

## 常见问题

- **构建失败**：点开失败的运行看日志；最常见原因是网络超时，
  重新运行一次（Actions → 该次运行 → 右上角 Re-run）通常就好。
- **想改应用图标/名称**：改 `buildozer.spec` 里的 title；
  图标需要加 `icon.png`（512×512）到项目根目录并在 spec 中配置。
- **包名冲突**：`package.domain` 改自己的域名倒序更稳妥。
- **旧手机（Android 5 以下）**：把 `buildozer.spec` 里
  `android.minapi` 调低（如 19）后重新构建。

## 本地修改代码后

改完 `main.py` 或 `chainplate_calc.py` → `git add . && git commit -m x && git push`
→ 等 Actions 构建 → 下载新 APK 安装（可直接覆盖安装，设置会保留）。
