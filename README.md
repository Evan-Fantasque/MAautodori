# MAautodori

MAautodori 是一个面向《BanG Dream! 少女乐团派对！》简中服的 MuMu 单人自动化工具。可以启动游戏并处理常见的登录后弹窗、自动打歌清火，以及领取每日免费演出招募。本项目的自动演出范围限于单人模式，协力等多人入口未接入。

> **使用声明**
>
> 本项目为第三方工具。使用本工具产生的后果由使用者自行承担。

## Windows 便携包

[在 GitHub Releases 下载 Windows x64 便携包](https://github.com/Evan-Fantasque/MAautodori/releases/latest)

使用 Windows x64。将便携 ZIP 完整解压到一个目录，双击 `mxu.exe`。便携包内含 Python、Agent 依赖、OCR 和触控组件。MuMu 和游戏需自行安装，并先在游戏中完成登录。打歌默认从 Bestdori 获取谱面，也可读取本地 BMS。

如果系统缺少运行库，请分别安装 [Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/#download-section) 和 [Visual C++ x64 运行库](https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist)。

## 从 MuMu 启动到单人演出准备

1. 在 MXU 的空配置中使用「启动模拟器到一键每日」预设。它会依次添加「启动游戏到主菜单」和「每日清火＋免费三抽」。
2. 第一次先手动打开 MuMu。在这份 MXU 配置中选择「模拟器」和「简中服」，选中并保存实际要使用的 MuMu 设备。
3. 在同一配置里添加「前置程序」，选择 MuMu 安装目录下的 `nx_main\MuMuManager.exe`。填入 `control -v 0 launch`，把 `0` 改成实际实例编号，启用「等待退出」。下次点「开始任务」，MXU 会先启动 MuMu，再连接设备并运行任务。

如果只想导航到开打前，可在任务列表中依次添加「启动游戏到主菜单」和「单人演出准备（停在开打前）」，再选择单人模式。

## 任务列表

| 任务 | 用途 |
| --- | --- |
| 启动游戏到主菜单 | 启动简中服，处理已识别的签到、公告、新曲提示和宣传页。遇到需要登录的提示时关闭游戏并停止。 |
| 单人演出准备（停在开打前） | 从主菜单进入自由演出、挑战演出或舞台挑战。自由演出和舞台挑战停在开打前的准备页，挑战演出停在挑战点数确认处。 |
| 自由演出（单曲） | 从普通自由演出的「选择乐队」页开始，按当前曲目和难度打完一场。开始前请关闭游戏内「自动演出」，并检查用火设定。 |
| 挑战演出 | 活动开放时自动打单人挑战演出。每场核对挑战点数消费，结算后按实际余额决定是否继续。 |
| 每日清火＋免费三抽 | 先清到 0 火，再领取当天剩余的免费演出招募。若已是 0 火、当天尚未完成演出且招募要求先完成演出，会补打一场 0 火自由演出。 |
| 每日清火 | 循环打一首指定歌曲。每场开打前核对用火预览，确认结算后重读火焰余额，读到 0 火结束。 |
| 每日免费招募 | 领取当天剩余的免费次数。游戏要求先完成演出时停下并提示。 |
| 自由演出（挖矿）（可靠性未验证） | 从自由演出选曲页开始，循环选歌、打歌和结算。可开启演出前火焰检查。 |
| 巡回演出（可靠性未验证） | 活动开放时，从巡回演出页面选曲、开始各曲并处理结算。曲名识别区域需按活动页面核对。 |

「每日清火」和「每日清火＋免费三抽」默认选 `SAVIOR OF SONG`（`EXPERT`）。在任务里输入完整曲名，从下拉框选择难度和常规用火（1、2、3 火，默认 3 火）。「优先10火」默认开启，可用 10 火且余额足够时优先用 10 火。如果结算后重读的余额比 10 火预览高出超过 1 火，本次任务改用常规档。选曲会尝试切到「所有」以解除筛选，仍找不到指定曲目时停止。

可以分别添加清火和免费招募来组合日常任务。一键每日包含招募解锁所需的补演出判断。旧配置自定义过难度、用火档或关闭过「优先10火」时，升级后请在新控件里重新选择。

「挑战演出」默认使用当前选中的曲目、`EXPERT` 和 200 点档。可填写完整曲名，选择难度和 200／400／800／1600 点档。「点数不足时」默认停止，也可选择降档下限。开启降档后，余额不够首选档时使用仍付得起的最高档，低于下限即结束。

在 MXU 的「设置 → 任务设置 → 打歌」中可以切换「打歌触控链路」。默认使用 MaaFramework 控制器，也可以选「EvATive7 Minitouch（延迟补偿）」。设置对所有配置生效，用于自由演出（单曲）、挑战演出、每日清火和每日清火＋免费三抽。使用 EvATive7 时，请选择 MXU 自动识别的 MuMu 实例，以便读取模拟器画面。

## 本地谱面

在 `mxu.exe` 同级目录创建 `charts/`，将自行取得的 BanG Dream! 原始 BMS 按 `曲目ID-难度.bms` 命名。例如《舞台に立って》EXPERT 使用 `charts/792-expert.bms`，也接受同名 `.txt`。两种触控链路都优先读取本地谱面，找不到时使用 Bestdori 的解析结果。遇到不兼容的本地谱面时，任务停止并在日志中提示原因。曲名索引仍由 Bestdori 提供。

《舞台に立って》EXPERT 的连续滑键修正会在读取匹配的原始 BMS 时自动生效。请自行将谱面放入 `charts/`。 [《舞台に立って》EXPERT 简中服原始 BMS](https://bestdori.com/assets/cn/musicscore/musicscore800_rip/792_butai_expert.txt)

## 本地开发和打包

当前 Windows x64 基准为 MaaFramework `v6.0.0-beta.3`（`MaaFw==6.0.0b3`）和 MXU `v2.11.2`。下载对应版本的 Windows x64 压缩包，将 MaaFramework 解压到 `deps/`，将 MXU 解压到 `deps/mxu/`。安装脚本会读取 `deps/bin/`、`deps/share/MaaAgentBinary/`、`deps/LICENSE.md`、`deps/mxu/mxu.exe` 和 `deps/mxu/LICENSE`。[MaaFramework 下载](https://github.com/MaaXYZ/MaaFramework/releases/tag/v6.0.0-beta.3) · [MXU 下载](https://github.com/MaaXYZ/MXU/releases/tag/v2.11.2)

在仓库根目录执行以下命令。子模块提供简中 OCR 模型，打包脚本会配置模型并生成 `install/`。

```powershell
git submodule update --init --recursive
python -m pip install -r tools/requirements.txt
python tools/install.py v0.0.1-local win x86_64
python -m venv install/.venv
.\install\.venv\Scripts\python.exe -m pip install -r install/requirements.txt
.\install\mxu.exe
```

GitHub Actions 会构建并验证包含 Python 的 Windows x64 便携包。可在 Actions 的 `portable-win-x64` 产物中下载测试包；用于开发的 `MAautodori-win-x86_64` 产物需要在包根目录创建 `.venv` 并安装 `requirements.txt`。[打包工作流](.github/workflows/install.yml)

发布时，按改动幅度选择 `v主版本.次版本.修订号`，更新 `assets/interface.json` 的 `version`。确认 Actions 检查和打包通过后，推送与该版本一致的 Git 标签。Actions 会检查版本一致性并自动发布便携 ZIP。窗口标题显示项目名称和版本号。

在 Windows x64 上用 Python 3.14.4 执行 `python tools/package_portable.py`，可将生成的 `install/` 打包成 `build/portable/MAautodori-win-x64-<版本>.zip`。

- 任务入口与选项在 [assets/interface.json](assets/interface.json)，游戏流程在 [assets/resource/pipeline/](assets/resource/pipeline/)，Python Agent 在 [agent/](agent/)。
- 修改 Pipeline 或任务配置后，在仓库根目录执行 `npm ci` 和 `npx @nekosu/maa-tools check`。涉及识别或触控时，再在 MuMu 验证实际受影响的步骤。
- 两个标为「可靠性未验证」的旧任务使用旧触控后端。需要开发或测试它们时，从 [Agent 开发指南](agent/ARCHITECTURE_GUIDE.md) 查看 Minitouch 文件布局和识别配置。

## 来源和许可证

项目使用 MaaFramework 和 MXU，打歌实现参考 [autodori](https://github.com/EvATive7/autodori)。[Bestdori](https://bestdori.com/) 提供曲目信息和谱面。

本仓库使用 [MIT 许可证](LICENSE)。打包的上游组件许可见包内 `licenses/` 和组件目录。
