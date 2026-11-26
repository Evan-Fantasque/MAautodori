import logging
import re

from maa.custom_action import CustomAction

from ..utils.MaaUI import navigate


logger = logging.getLogger(__name__)
GAME_PACKAGE = "com.bilibili.star.bili"
FOREGROUND_PACKAGE = re.compile(r"\b([A-Za-z0-9_.]+)/[^\s}]+")


def foreground_package(context):
    commands = (
        "dumpsys window | grep -m 1 mCurrentFocus=",
        "dumpsys activity activities | grep -m 1 -E 'topResumedActivity[=:]|mResumedActivity[=:]|ResumedActivity:'",
    )
    for command in commands:
        if context.tasker.stopping:
            return None
        try:
            job = context.tasker.controller.post_shell(command, timeout=4000).wait()
            output = job.get() if job.succeeded else None
        except (OSError, RuntimeError):
            logger.debug("读取 Android 前台应用失败。", exc_info=True)
            continue
        if output and (match := FOREGROUND_PACKAGE.search(output)):
            return match[1]
    return None


class EnsureGameForeground(CustomAction):
    def run(self, context, argv):
        foreground = foreground_package(context)
        if foreground == GAME_PACKAGE:
            logger.info("游戏已在前台，跳过启动。")
            return self.RunResult(success=True)
        if not foreground or context.tasker.stopping:
            logger.warning("无法确认前台应用，启动任务已停止。")
            return self.RunResult(success=False)
        logger.info("游戏不在前台，启动简中服。")
        result = context.run_action("StartupLaunch")
        return self.RunResult(success=bool(result and result.success))


class PrepareSolo(CustomAction):
    def run(self, context, argv):
        try:
            check_presentation = {
                "next": ["GameErrorDialog", "PlayPresentationOff", "[JumpBack]PlayPresentationEnabled"],
                "timeout": 5500,
            }
            success = navigate(context, "SoloPrepareRoute", ("SoloChallengeReady", "PlayPresentationOff"), {
                "SoloFreeReady": check_presentation,
                "SoloStageReady": check_presentation,
            }, reset_hits=("SoloSwitchMainStage", "SoloSwitchSpecialStage", "PlayPresentationEnabled"))
            return self.RunResult(success=success)
        except (RuntimeError, OSError):
            logger.exception("未能完成单人演出准备")
            return self.RunResult(success=False)
