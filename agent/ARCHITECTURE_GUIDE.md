# MAautodori 架构与开发指南 (MaaFramework)

本文档旨在为人类和 AI 开发者提供本项目的架构摘要，概述如何在基于 `maafw` (MaaFramework) 的模块化规范下，开发和迁移自定义动作 (Custom Action) 与自定义识别 (Custom Recognition)。

## 1. 核心设计原则

本项目的架构从原本高度耦合的单文件脚本（`github.com/EvATive7/autodori`）重构为符合 `maafw` 规范的模块化代理（Agent）。核心原则包括：
- **逻辑解耦**：每个具体的识别和动作必须是单一职责的独立类。
- **状态集中管理**：严禁在业务代码中滥用 `global` 关键字。所有的生命周期状态、任务配置以及外部控制器（Player, Minitouch 等）均由 `StateCore.py` 中的单例对象 `global_state` 统一管理。
- **声明式注册**：业务代码无需关心如何被 MaaFramework 引擎调用，统一在 `CustomFile.py` 中通过装饰器进行集中注册。

## 2. 全局状态管理 (StateCore)

在打歌脚本的特定需求下，不同动作和识别器之间需要共享大量的配置（如打歌难度、延迟、偏移量）和状态（如当前识别到的歌曲 ID、图谱、设备连接状态）。
我们在 `agent/custom/utils/StateCore.py` 提供了一个 `MAautodoriState` 单例 (`global_state`)。

**最佳实践：**
- **获取配置**：不再通过解析 `argv.custom_action_param` 在 JSON 管线中反复传递复杂参数，而是直接从 `global_state` 中读取。例如读取 `global_state.difficulty`。
- **状态跨模块传递**：前一个模块（如 `SongRecognition`）将识别出的关键信息写入 `global_state`（如 `current_song_id`），后续被触发的模块（如 `SaveSong`, `Play`）直接从 `global_state` 中提取。
- **设备初始化保障**：动作层在需要使用外部设备控制前，应主动检查 `global_state.player` 和 `global_state.mnt`，若未初始化则调用同一文件内的 `init_player_and_mnt(context)` 进行挂载。

## 3. 编写自定义识别 (Custom Recognition)

自定义识别负责图像分析与特征提取（如 OCR 歌名），并返回识别框和相关详情。

**步骤：**
1. 在 `agent/custom/recognition/` 下新建 Python 文件。
2. 继承 `maa.custom_recognition.CustomRecognition`。
3. 实现 `analyze` 方法。
4. 从 `global_state` 获取识别所需的特定配置（如 `roi`, `live_mode`）。若传入了 `argv.roi`（注意它是底层 `Rect` 对象），需转换成 `[x,y,w,h]` 列表以满足引擎中转 JSON 时的序列化要求。
5. (如有必要) 将识别出的关键上下文数据（如歌曲 ID、歌曲名）缓存至 `global_state`，供随后的 Action 动作衔接使用。
6. 返回 `CustomRecognition.AnalyzeResult`，其中包含检测区域 (`box`) 和字符串详情 (`detail`)。

**结构示例：**
```python
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from ..utils.StateCore import global_state

class MyRecognition(CustomRecognition):
    def analyze(self, context: Context, argv: CustomRecognition.AnalyzeArg):
        # 1. 从 global_state 获取运行时配置
        mode = global_state.live_mode
        
        # 2. 执行核心识别逻辑 (如 OCR, 模板匹配)
        # ...

        # 3. 更新全局上下文供后续 Action 使用
        global_state.current_song_name = "example_song"

        # 4. 返回结果给引擎
        return self.AnalyzeResult(box=[0, 0, 100, 100], detail="example_song")
```

## 4. 编写自定义动作 (Custom Action)

自定义动作负责具体的设备交互与任务执行逻辑。

**步骤：**
1. 在 `agent/custom/action/` 下新建 Python 文件。
2. 继承 `maa.custom_action.CustomAction`。
3. 实现 `run` 方法。
4. 检查并确保设备控制器已初始化 (`init_player_and_mnt(context)`)。
5. 从 `global_state` 中提取图谱实例、配置参数等执行上下文。
6. 执行具体的业务控制逻辑（如打歌、点击等）。
7. 返回 `CustomAction.RunResult(success=True/False)`。

**结构示例：**
```python
from maa.custom_action import CustomAction
from maa.context import Context
from ..utils.StateCore import global_state, init_player_and_mnt

class MyAction(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        # 1. 确保外部设备控制接口就绪
        if not global_state.player or not global_state.mnt:
            try:
                global_state.player, global_state.mnt = init_player_and_mnt(context)
            except Exception as e:
                return CustomAction.RunResult(success=False)

        # 2. 从 global_state 读取由 Recognition 传递或初始化设定的参数
        song_id = global_state.current_song_id
        difficulty = global_state.difficulty

        # 3. 执行核心动作
        # ...

        return CustomAction.RunResult(success=True)
```

## 5. 注册模块 (CustomFile.py)

无论是 Action 还是 Recognition，编写完成后**必须**在统一的入口 `agent/CustomFile.py` 中使用 `AgentServer` 装饰器进行注册。这样 MaaFramework 引擎在解析 JSON 管线任务时，才能正确映射并调用相应的 Python 类。

```python
from maa.agent.agent_server import AgentServer

from agent.custom.action.MyAction import MyAction
from agent.custom.recognition.MyRecognition import MyRecognition

@AgentServer.custom_action("MyAction")
class MyActionClass(MyAction):
    def __init__(self):
        super().__init__()

@AgentServer.custom_recognition("MyRecognition")
class MyRecognitionClass(MyRecognition):
    def __init__(self):
        super().__init__()
```

遵循以上规范，即可在保持模块高度解耦的前提下，高效地向本自动打歌代理中迁移旧代码或开发新的任务逻辑。