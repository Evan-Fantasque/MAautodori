"""
火焰不足处理动作
当 LiveBoostRecognition 识别到火焰 < min_liveboost 时，自动关闭游戏并停止任务。
"""
import logging
from maa.custom_action import CustomAction
from maa.context import Context
from ..utils.StateCore import global_state


class HandleLiveBoost(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        logger = logging.getLogger("HandleLiveBoost")

        try:
            liveboost = int(argv.reco_detail.best_result.detail)
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"无法解析火焰数量: {e}")
            return CustomAction.RunResult(success=False)

        min_liveboost = global_state.min_liveboost

        if liveboost < min_liveboost:
            logger.info(f"火焰不足 ({liveboost} < {min_liveboost})，准备退出")
            context.run_action("close_app")
            context.run_action("stop")
        else:
            logger.debug(f"火焰充足 ({liveboost} >= {min_liveboost})，继续任务")

        return CustomAction.RunResult(success=True)
