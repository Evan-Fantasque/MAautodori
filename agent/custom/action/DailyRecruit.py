import logging
import time

from ..utils.MaaUI import capture, click, reached, recognize

logger = logging.getLogger(__name__)


def _open_banner(context):
    return reached(context, "DailyRecruitOpen", "DailyRecruitBanner")


def _remaining(context, image):
    result = recognize(context, "DailyRecruitRemaining", image)
    return int(result.text[2]) if result else None


def _finish_pull(context):
    return (
        reached(context, "DailyRecruitReveal", "DailyRecruitResult")
        and reached(context, "DailyRecruitBack", "DailyRecruitBanner")
    )


def recruit(context):
    if not _open_banner(context):
        raise RuntimeError("没有找到每日演出免费招募")
    initial = None
    for _ in range(4):
        image = capture(context)
        if not recognize(context, "DailyRecruitBanner", image):
            raise RuntimeError("每日免费招募页面已变化")
        remaining = _remaining(context, image)
        if initial is None:
            initial = remaining
        if remaining == 0 or recognize(context, "DailyRecruitExhausted", image):
            if remaining not in (None, 0):
                raise RuntimeError("免费招募的次数和状态不一致")
            logger.info("每日免费招募已完成，本次抽取 %d 次", initial or 0)
            return "done"
        if recognize(context, "DailyRecruitLockedBadge", image):
            return "locked"
        button = recognize(context, "DailyRecruitSingle", image)
        free = recognize(context, "DailyRecruitFree", image)
        if not button or not free or remaining not in (1, 2, 3):
            raise RuntimeError("未确认单次免费招募按钮及剩余次数")
        if not click(context, button.box):
            raise RuntimeError("无法打开免费招募确认框")
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            image = capture(context)
            confirm = recognize(context, "DailyRecruitConfirm", image)
            if confirm:
                break
            if recognize(context, "DailyRecruitLocked", image):
                if not reached(context, "DailyRecruitDismissLocked", "DailyRecruitBanner"):
                    raise RuntimeError("无法关闭演出条件提示")
                return "locked"
            time.sleep(0.25)
        else:
            raise RuntimeError("没有看到每日免费招募确认框，已停止")
        if not click(context, (768, 477)) or not _finish_pull(context):
            raise RuntimeError("已确认招募，但无法确认结果，请检查游戏")
        image = capture(context)
        after = _remaining(context, image)
        if after != remaining - 1 and not (
            remaining == 1 and after is None and recognize(context, "DailyRecruitExhausted", image)
        ):
            raise RuntimeError("免费招募次数未按预期减少，已停止")
        logger.info("已确认一次每日免费招募，剩余 %d 次", remaining - 1)
    raise RuntimeError("免费招募超出预期次数")
