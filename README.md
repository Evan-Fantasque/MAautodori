<!-- markdownlint-disable MD033 MD041 -->
<p align="center">
  <img alt="LOGO" src="https://cdn.jsdelivr.net/gh/MaaAssistantArknights/design@main/logo/maa-logo_512x512.png" width="256" height="256" />
</p>

<div align="center">

# MaaPracticeBoilerplate

</div>

本仓库为 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 所提供的项目模板，开发者可基于此模板直接创建自己的 MaaXXX 项目。

> **MaaFramework** 是基于图像识别技术、运用 [MAA](https://github.com/MaaAssistantArknights/MaaAssistantArknights) 开发经验去芜存菁、完全重写的新一代自动化黑盒测试框架。
> 低代码的同时仍拥有高扩展性，旨在打造一款丰富、领先、且实用的开源库，助力开发者轻松编写出更好的黑盒测试程序，并推广普及。

## MAautodori Windows 开发包

Windows x64 打包使用 MaaFramework `v6.0.0-beta.3`（Python 包 `MaaFw==6.0.0b3`）和 MXU `v2.11.2`。Agent 与 Pipeline 检查工具使用同一 MaaFramework 版本。升级时同步更新 `requirements.txt`、`maatools.config.mts`、打包工作流及 `deps/tools/` 的 Schema。

从仓库根目录运行 `git submodule update --init --recursive`，再运行 `python tools/configure.py` 配置 OCR。打包流程见 [.github/workflows/install.yml](.github/workflows/install.yml)，产物位于 `install/`。

Windows 上运行包内 `mxu.exe` 需要 Microsoft Edge WebView2。Agent 使用包内的 `.venv`，以便 MXU 提权重启后仍加载配套的 MaaFw。首次运行发布包时，从解压目录创建 Python 环境、安装依赖并启动界面。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\mxu.exe
```

发布包将 `mxu.exe`、`maafw/`、`interface.json`、`resource/` 和 `agent/` 放在同一目录。MXU 从 `maafw/MaaAgentBinary/` 加载 MaaTouch 和 Minitouch。

上游源码见 [MXU v2.11.2](https://github.com/MaaXYZ/MXU/tree/v2.11.2) 和 [MaaFramework v6.0.0-beta.3](https://github.com/MaaXYZ/MaaFramework/tree/v6.0.0-beta.3)。随包提供的许可证位于 `licenses/`。

## 从 MuMu 启动到单人演出准备

1. 打开 `install/mxu.exe`，选择「模拟器」和「简中服」。第一次保存配置时，先打开 MuMu，选中要使用的 ADB 设备。
2. 在 MXU 的「前置程序」添加 MuMu 安装目录下的 `nx_main\MuMuManager.exe`，参数填 `control -v 0 launch`。启用「等待退出」，将 `0` 换成实际实例编号。MXU 会运行该命令并等已保存的 ADB 设备可用。[MXU 2.11.2 前置程序实现](https://github.com/MaaXYZ/MXU/blob/v2.11.2/src/components/Toolbar.tsx#L547)
3. 按顺序添加「启动游戏到主菜单」和「单人演出准备（停在开打前）」，再在第二个任务选择模式。使用当前曲目和难度。若只需进首页，保留第一个任务即可。

启动流程使用 MaaFramework 的应用启动、OCR 和区域校验，处理已识别的常规签到、活动签到、新曲提示、促销翻页和通知窗口。识别到需要登录的提示时关闭游戏并停止，遇到未知界面时等待至超时。若游戏已停留在其他页面，先返回标题页或主菜单。

| 模式 | 自动流程停点 |
| --- | --- |
| 自由演出 | 编队页「演出开始」前 |
| 挑战演出 | 活动开放时，到挑战点数选择窗口，等待玩家确认 |
| 舞台挑战（主舞台、特别舞台） | 对应舞台的编队页「演出开始」前 |

单人准备任务仅列出上述入口。旧打歌模块和本地调试方法见 [Agent 开发指南](agent/ARCHITECTURE_GUIDE.md)。

`自由演出（单曲）` 从普通自由演出的「选择乐队」页面开始。它按页面标出的难度加载谱面，通过 MaaFramework 发送触控。运行前，请关闭游戏内的「自动演出」并确认火焰消耗设定。

`每日清火＋免费三抽` 固定走普通单人自由演出。默认搜 `SAVIOR OF SONG` 的 `EXPERT`，可以在任务选项填完整曲名、更改难度及常规用火档（1～3），也可以关闭优先 10 火。选曲使用当前游戏筛选条件，找不到时尝试切到「所有」，仍被筛选排除时暂停。每场开打前核对扣火数字，确认结算后重读余额。清到 0 火后领取当天剩余的每日免费演出招募次数。

## 即刻开始

- [📄 快速开始](https://maafw.com/docs/1.1-QuickStarted)
- ~~[🎞️ 视频教程](https://www.bilibili.com/video/BV1yr421E7MW)~~ 视频中使用的MaaFramework版本较老，建议以文档为准。

## 如何开发

0. 使用右上角 `Use this template` - `Create a new repository` 来基于本模板创建您自己的项目。

1. 克隆本项目（地址请修改为您基于本模板创建的新项目地址）。

    ```bash
    git clone https://github.com/MaaXYZ/MaaPracticeBoilerplate.git
    ```

2. 下载 OCR（文字识别）资源文件 [ppocr_v5.zip](https://download.maafw.xyz/MaaCommonAssets/OCR/ppocr_v5/ppocr_v5-zh_cn.zip) 解压到 `assets/resource/model/ocr/` 目录下，确保路径如下：

    ```tree
    assets/resource/model/ocr/
    ├── det.onnx
    ├── keys.txt
    └── rec.onnx
    ```

    _请注意，您不需要将 OCR 资源文件上传到您的代码仓库中。`.gitignore` 已经忽略了 `assets/resource/model/ocr/` 目录，且 GitHub workflow 在发布版本时会自动配置这些资源文件。_

3. 进行开发工作。请参考 [MaaFramework 相关文档](https://maafw.com/docs/1.1-QuickStarted)，并按您的业务需求修改 `assets` 目录下的 `resource` 资源文件以及 `interface.json` 文件，然后使用 [开发工具](https://maafw.com/docs/1.1-QuickStarted#%E8%B0%83%E8%AF%95)进行调试。

4. 完成开发后，上传您的代码并发布版本。

    ```bash
    # 配置 git 信息（仅第一次需要，后续不用再配置）
    git config user.name "您的 GitHub 昵称"
    git config user.email "您的 GitHub 邮箱"
    
    # 提交修改
    git add .
    git commit -m "XX 新功能"
    git push origin HEAD -u
    ```

5. 发布您的版本

    需要**先**修改仓库设置 `Settings` - `Actions` - `General` - `Read and write permissions` - `Save`

    ```bash
    # CI 检测到 tag 会自动进行发版
    git tag v1.0.0
    git push origin v1.0.0
    ```

6. 更多操作，请参考 [个性化配置](./docs/zh_cn/个性化配置.md)（可选）

## 生态共建

MAA 正计划建设为一类项目，而非舟的单一软件。

若您的项目依赖于 MaaFramework，我们欢迎您将它命名为 MaaXXX, MXA, MAX 等等。当然，这是许可而不是限制，您也可以自由选择其他与 MAA 无关的名字，完全取决于您自己的想法！

同时，我们也非常欢迎您提出 PR，在 [社区项目列表](https://github.com/MaaXYZ/MaaFramework#%E7%A4%BE%E5%8C%BA%E9%A1%B9%E7%9B%AE) 中添加上您的项目！

## FAQ

### 0. 我是第一次使用 git，这是什么？视频演示中那个黑框框命令行哪来的？

黑框框是 git bash，几乎任何现代软件的开发都离不开 git，建议先参考 [菜鸟教程](https://www.runoob.com/git/git-install-setup.html) 或搜索一些视频，学习完 git 后再来进行后续开发工作。

### 1. 我是第一次使用 Python，在命令行输入 `python ./configure.py` 或 `python -m pip install MaaFW` 之后没有反应？没有报错，也没有提示成功，什么都没有

Win10 或者 Win11 系统自带了一份 "Python"，但它其实只是一个安装器，是没法用的。  
你需要做的是关闭它或者删除它的环境变量，然后自己去 Python 官网下载并安装一份 Python。  
[参考方法](https://www.bilibili.com/read/cv24692025/)

### 2. 使用 MaaDebugger 或 MaaPicli 时弹窗报错，应用程序错误：应用程序无法正常启动

![缺少运行库](https://github.com/user-attachments/assets/942df84b-f47d-4bb5-98b5-ab5d44bc7c2a)

一般是电脑缺少某些运行库，请安装一下 [vc_redist](https://aka.ms/vs/17/release/vc_redist.x64.exe) 。

### 3. 我应该如何打包我的项目？

你需要按照项目推荐的[开发流程](#如何开发)发布一个版本，[CI](/.github/workflows/install.yml) 会自动完成打包工作。具体的工作方式请参考 [GitHub Actions 文档](https://docs.github.com/zh/actions)。

### 4. 我在这个仓库里提了 Issue 很久没人回复

这里是《项目模板》仓库，它仅仅是一个模板，一般很少会修改，开发者也较少关注。  
在此仓库请仅提问模板相关问题，其他问题最好前往对应的仓库提出，如果有 log，最好也带上它（`debug/maa.log` 文件）

- MaaFW 本身及 MaaPiCli 的问题：[MaaFramework/issues](https://github.com/MaaXYZ/MaaFramework/issues)
- MaaDebugger 的问题：[MaaDebugger/issues](https://github.com/MaaXYZ/MaaDebugger/issues)
- 不知道算是哪里的、其他疑问等：[讨论区](https://github.com/MaaXYZ/MaaFramework/discussions)

### 5. OCR 文字识别一直没有识别结果，报错 "Failed to load det or rec", "ocrer_ is null"

**请仔细阅读文档**，你无视了前面步骤的报错。我不想解释了，请再把本文档仔细阅读一遍！

### 6. 在开发过程中遇到了其他问题

闭门造车大概率无法解决任何问题，你可以加入 [MaaFramework 开发交流群](http://qm.qq.com/cgi-bin/qm/qr?_wv=1027&k=9sleK6URhEG0v3QeTmpFueCjF26wibEH&authKey=LBZc5FxWa3M%2BiWj3rpBfRmqg9PD9jJNaxpp3xTqTcGxsp1Am3kd1uzxQXiP4w8w4&noverify=0&group_code=595990173) 以寻求帮助。

> [!WARNING]
> 在提问前，请完整阅读 [MaaFramework 开发文档](https://maafw.com/docs/1.1-QuickStarted)以及[如何开发](#如何开发)，通常情况下他们能解决大多数问题。
> 在提问时，请 **具体指出文档中困惑的章节** / **分享你的项目文件中的具体内容** / **提供完整的报错信息** ，不然你能得的大概率只有类似 _“请先读文档”_ 这样的回答。

## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动！

感谢以下开发者对本项目作出的贡献（下面链接改成你自己的项目地址）:

[![Contributors](https://contrib.rocks/image?repo=MaaXYZ/MaaFramework&max=1000)](https://github.com/MaaXYZ/MaaFramework/graphs/contributors)
