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


def reached(context, entry, final, override=None):
    result = context.run_task(entry, override)
    return bool(result and result.nodes and result.nodes[-1].name == final and result.nodes[-1].completed)
