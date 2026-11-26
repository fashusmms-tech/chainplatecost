# 用 GitHub 打包 APK（v1.2 界面版）

整个流程不需要在本机装 Android SDK，全部在 GitHub 的免费机器上跑，**大约 25–40 分钟**出包（第一次）
后续有缓存，大约 10–20 分钟。

---

## 0. 一次性准备

仓库已经就绪：

- 仓库：`https://github.com/fashusmms-tech/chainplatecost`
- 分支：`main`
- 工作流：`.github/workflows/build-apk.yml`

需要确认的只有一件事：**仓库是 Public，或 Actions 额度够用**。
（Private 仓库免费额度 2000 分钟/月，单次约 30 分钟，够用十几次。）

---

## 1. 把新界面推上去

在 `chainplatecost` 目录里：

```bash
git status                 # 确认改了 main.py / buildozer.spec / 工作流
git add -A
git commit -m "v1.2: 重做界面（深色工业风 / 分区卡片 / 结果页 / 成本结构条）"
git push origin main
```

推上去后，**Actions 会自动触发**一次构建（因为我们改了 `main.py`）。
只想手动触发的话，可以给 commit 加 `[skip ci]`，然后按下一步手动点。

---

## 2. 手动触发（推荐先用这个）

1. 打开 `https://github.com/fashusmms-tech/chainplatecost/actions`
2. 左边选 **Build APK**
3. 右上 **Run workflow** → 分支选 `main` → 点绿色 **Run workflow**

工作流固定打 **debug** 包（自带调试签名，装到手机就能用）。
要能上架/长期升级的 release 包，见第 5 节。

---

## 3. 下载 APK

构建完成后：

1. 点开这次运行记录
2. 页面底部 **Artifacts** → 下载 **chainplatecost-apk**
3. 解压得到 `chainplatecost-1.2.0-arm64-v8a-debug.apk`
4. 传到手机安装（第一次装需要在系统里允许「安装未知来源应用」）

> `debug` 包自带调试签名，可以直接装；缺点是包体略大、不能上应用商店。

如果构建失败：

- 下载 **buildozer-log** 这个 artifact，里面有完整日志
- 常见原因见第 6 节

---

## 4. 装到手机上要看什么

装好后重点确认这几处（都是这次改动最大的地方）：

| 位置 | 看什么 |
|---|---|
| 主界面顶部 | 标题「链板报价」、副标题、右侧齿轮能否进设置 |
| 材质卡片 | 三个下拉能弹、开关能切换、关掉开关后下拉可点 |
| 节距 | 5 个胶囊能选中，选完右侧数字跟着变 |
| 基础尺寸 | 三个大数字能点开输入、能弹数字键盘 |
| 选配件 | 勾上后参数区展开、取消后收起（不占高度） |
| 底部条 | 「每米价格」随输入实时变、点「计算」进结果页 |
| 结果页 | 总价、成本结构条、明细、合计；「复制明细」能粘到微信 |
| 设置页 | 5 个页签能切、公式页能滚动、保存后主界面价格会变 |

有任何一处不对，**截图发我**，我按真机效果改。

---

## 5. 关于 release 包（可选）

`debug` 够自己用。要发正式包（可上架/可长期升级）需要自己生成签名：

```bash
keytool -genkey -v -keystore chainplate.keystore -alias chainplate \
        -keyalg RSA -keysize 2048 -validity 10000
```

然后把 keystore 转成 base64 放进 GitHub Secrets，并在工作流里加一段签名步骤。
需要的话告诉我，我把这段补进 workflow（**不要**把 keystore 提交进仓库）。

---

## 6. 已知会踩的坑

| 现象 | 原因 | 处理 |
|---|---|---|
| `Unable to locate package libtinfo5` | ubuntu-latest 升到 24.04 后没这个包 | 工作流已锁 `ubuntu-22.04`，并加了 `\|\| echo` 兜底 |
| `buildozer: command not found` | `pip --user` 装的路径不在 PATH | 工作流已 `echo $HOME/.local/bin >> $GITHUB_PATH` |
| 构建步骤莫名失败、日志末尾是 `yes: standard output: Broken pipe` | `yes` 收到 SIGPIPE 被 pipefail 判成失败 | 工作流已改成抓 `PIPESTATUS[1]`，不看 `yes` 的退出码 |
| `kivy` 编译失败 / cython 报错 | cython 版本太新 | 已钉 `cython==0.29.37`、`buildozer==1.5.0`、`p4a.branch=v2024.01.21` |
| 中文显示成方框 | 打包字体是子集字体，缺字 | 已加 `tests/kvshim/fontcheck.py`，改文案前后各跑一次 |
| 首次构建 40 分钟没动静 | 在下载 SDK/NDK（约 1.5GB） | 正常，第二次有缓存会快很多 |

---

## 7. 改完界面后怎么自查（不装 Android）

在项目根目录：

```bash
# 1) 公式没被动过（118 组用例）
python tests/golden.py

# 2) 类名不能和 Kivy 内置控件重名（重名会导致手机上打开即闪退）
python tests/check_class_names.py

# 3) 界面逻辑没坏（21 项，需要 Kivy；没有 Kivy 时用替身跑）
PYTHONPATH=tests/kvshim python tests/ui_smoke.py

# 4) 文案没有用到子集字体外的字（否则手机上变方框）
PYTHONPATH=tests/kvshim python tests/kvshim/fontcheck.py

# 5) 出预览图（不需要 Kivy）
PYTHONPATH=tests/kvshim python tests/kvshim/shots.py
```

`tests/kvshim/` 是本机用的「Kivy 替身 + 渲染器」，**不会打进 APK**
（`buildozer.spec` 里 `source.exclude_dirs` 已经排除 `tests`）。

> ⚠️ 替身没有 Kivy 的 kv 规则，所以「类名撞车」这类问题它测不出来 —— 这就是
> 第 2 项单独存在的理由。曾经把开关类命名为 `Switch`，被 Kivy 的 `<Switch>`
> 规则套上，构造时引用不存在的 `active_norm_pos`，启动就崩。
>
> 想在本机用**真 Kivy** 跑一遍（最能提前发现这类问题）：
>
> ```bash
> python -m venv .venv-kivy
> .venv-kivy\Scripts\python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple kivy==2.3.0
> set CHAINPLATE_DATA_DIR=%CD%\.appdata_test
> .venv-kivy\Scripts\python -c "import main; main.ChainPlateApp().run()"
> ```
