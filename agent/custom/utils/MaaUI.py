import logging


logger = logging.getLogger(__name__)


def capture(context):
    if context.tasker.stopping:
        raise RuntimeError("任务已停止")
    image = context.tasker.controller.post_screencap().wait().get()
    if image is None or not image.size:
        raise RuntimeError("无法读取游戏画面")
    return image


def recognize(context, node, image, override=None):
    result = context.run_recognition(node, image, override)
    return result.best_result if result and result.hit else None


def click(context, target):
    if context.tasker.stopping:
        return False
    if len(target) == 4:
        x, y, width, height = target
        target = (x + width // 2, y + height // 2)
    return context.tasker.controller.post_click(*target).wait().succeeded


def reached(context, entry, final, override=None, *, reset_hits=()):
    for node in reset_hits:
        context.clear_hit_count(node)
    result = context.run_task(entry, override)
    targets = (final,) if isinstance(final, str) else final
    return bool(result and result.nodes and result.nodes[-1].name in targets and result.nodes[-1].completed)


def navigate(context, entry, final, override=None, *, reset_hits=()):
    # Only use this for routes that can restart from home before a request is submitted.
    image = capture(context)
    if not recognize(context, "GameErrorDialog", image):
        if reached(context, entry, final, override, reset_hits=reset_hits):
            return True
        image = capture(context)
    if not recognize(context, "GameRecoverableError", image):
        return False
    logger.info("导航遇到已识别的游戏错误，尝试返回主页并重走一次：%s", entry)
    if not reached(context, "start_app", "StartupHomeReady", reset_hits=(
        "StartupDownloadFailed", "StartupDismissInterrupted", "GameRetryConnection", "StartupTapTitle",
    )):
        return False
    return reached(context, entry, final, override, reset_hits=reset_hits)
