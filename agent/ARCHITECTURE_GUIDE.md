# MAautodori Agent 开发指南

## 先用现有管线

MaaFramework v6.0.0-beta.3 和 MXU 2.11.2 是当前基准。任务入口写在 `assets/interface.json`，游戏内流程写在 `assets/resource/pipeline/`。`start.json` 负责启动国服并进入主菜单，`solo_prepare.json` 只走已确认的单人入口，到准备页即停。模拟器启动使用 MXU 的「前置程序」，配置见[项目说明](../README.md#从-mumu-启动到单人演出准备)。

有现成 OCR、模板识别或点击节点时直接复用。首次为新页面加点击时，先在 MuMu 上截图，确认目标和能识别该页面的特征。保持每个单人分支的明确停点。

## 复用旧打歌模块

- 曲名和结算使用 `play_recognition.json` 中的 MaaFramework OCR 节点。曲名识别用 `ocr_node` 指定页面，另可用 ROI 覆盖。Python 负责 Bestdori 曲名和 ID 匹配、结算字段汇总及保存。巡回演出的曲名区域需用对应页面确认后配置。
- `SaveSong` 按当前难度准备谱面，`chart.py` 将谱面转换成带时间的触控动作。「自由演出（单曲）」由 `NativeTouch.py` 通过 MaaFramework 提交动作。首音符检测等判定线稳定后在目标轨道上取样。任务间共享的歌曲和谱面放在 `StateCore.py` 的 `global_state`。
- 本地 BMS 放在程序根目录的 `charts/`。例如便携包中使用 `charts/792-expert.bms`，也接受同名 `.txt`。同一首歌优先读取本地文件，缺少文件时沿用 Bestdori。文件存在但含错误或尚未支持的音符时，任务停止并在日志中写明原因。曲名索引仍来自 Bestdori。
- 增加识别或动作时，在 `custom/recognition/` 或 `custom/action/` 修改并在 `CustomFile.py` 注册。Pipeline 中的 `custom_recognition`、`custom_action` 名称与装饰器一致。返回 `AnalyzeResult(box=…, detail=…)` 或 `RunResult(success=…)`。
- 暂停按钮和演出失败使用 MaaFramework 的 720p 模板。旧「自由演出（挖矿）」可单独启用「检查火焰」。挖矿和巡回演出仍使用 EvATive7 后端。CI 从固定的修复提交构建各 Android ABI。手动开发时，将产物的 ABI 子目录和 `LICENSE` 放入 `deps/minitouch_EvATive7/`，安装脚本会复制到 `install/share/MinitouchEvATive7/`。Agent 按包内二进制内容生成模拟器文件名，升级时会自动部署新组件。 [旧打歌实现](https://github.com/EvATive7/autodori) · [Minitouch 修复提交](https://github.com/Evan-Fantasque/minitouch/commit/a56848b27cb8b7b23ff845a377aa5bda19a2ed1a)

修改后运行 `npx @nekosu/maa-tools check` 检查管线。改到打歌模块时可先用离线谱面验证命令生成，再单独验证改动涉及的实机步骤。多人入口不接入自动化。
