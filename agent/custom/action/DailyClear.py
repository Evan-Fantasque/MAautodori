import json
import logging

from maa.custom_action import CustomAction

from .DailyRecruit import recruit
from ..utils.MaaUI import capture, click, reached, recognize
from ..utils.SongSelection import DIFFICULTIES, exact_title_pattern, select_song, verify_band


logger = logging.getLogger(__name__)


def choose_boost(balance, regular, max_available):
    if balance >= 10 and max_available:
        return 10
    return regular if balance else 0


def _select_page(context):
    return reached(context, "DailyEnterSelection", "FreeSongList", {
        "SoloModeMenu": {"next": ["SoloEnterFree"]},
        "SoloEnterFree": {"next": ["FreeSongList"]},
    })


def _number(context, name, image, override=None):
    result = recognize(context, name, image, override)
    if not result:
        raise RuntimeError(f"无法读取火焰数字（{name}）")
    return int(result.text.split("/")[0])


def _balance(context):
    return _number(context, "DailyBoostBalance", capture(context))


def _band(context, title, difficulty):
    image = capture(context)
    if recognize(context, "SoloFreeReady", image) and verify_band(context, image, title, difficulty):
        return
    if not _select_page(context):
        raise RuntimeError("未能进入普通自由演出的选曲页")
    if not select_song(context, title, difficulty):
        raise RuntimeError(f"当前乐曲筛选下找不到或无法选择 {title} {difficulty}")
    if not reached(context, "DailyConfirmSong", "SoloFreeReady"):
        raise RuntimeError("无法进入普通自由演出的编队页")
    if not verify_band(context, capture(context), title, difficulty):
        raise RuntimeError("编队页的曲名或难度与设置不一致")


def _boost_preview(before, after, exact=False):
    nodes = {"DailyBoostBefore": {}, "DailyBoostAfter": {}}
    if before - after == 10:
        nodes["DailyBoostBefore"]["roi"] = [1138, 544, 36, 25]
        nodes["DailyBoostAfter"]["roi"] = [1190, 544, 34, 25]
    else:
        short_balance = before < 10
        nodes["DailyBoostBefore"]["roi"] = [1046, 544, 24 if short_balance else 35, 25]
        nodes["DailyBoostAfter"]["roi"] = [1085 if short_balance else 1099, 544, 34, 25]
    if exact:
        nodes["DailyBoostBefore"]["expected"] = f"^{before}$"
        nodes["DailyBoostAfter"]["expected"] = f"^{after}$"
    return nodes


def _radio(y):
    return {"DailyBoostSelected": {"roi": [981, y - 19, 42, 38]}}


def _set_boost(context, balance, regular, prioritize_max=True):
    if not reached(context, "DailyBoostOpen", "DailyBoostDialog"):
        raise RuntimeError("未能打开火焰设置")
    image = capture(context)
    max_available = prioritize_max and balance >= 10 and bool(recognize(context, "DailyBoostMax", image))
    tier = choose_boost(balance, regular, max_available)
    y = 517 if tier == 10 else 133 + tier * 77
    row = {"DailyBoostTier": {"roi": [298, y - 20, 56, 40], "expected": f"^{tier}$"}}
    if not recognize(context, "DailyBoostTier", image, row):
        raise RuntimeError(f"找不到 {tier} 火档")
    if tier != 10 and recognize(context, "DailyBoostSelected", image, _radio(517)):
        if not click(context, (1002, 517)):
            raise RuntimeError("无法关闭最大消费档")
    if not recognize(context, "DailyBoostSelected", image, _radio(y)) and not click(context, (1002, y)):
        raise RuntimeError(f"无法选择 {tier} 火")
    if not reached(context, "DailyBoostApply", "SoloFreeReady", _radio(y)):
        raise RuntimeError("火焰档位未确认")
    image = capture(context)
    expected = (balance, balance - min(tier, balance))
    layout = _boost_preview(*expected)
    preview = (
        _number(context, "DailyBoostBefore", image, layout),
        _number(context, "DailyBoostAfter", image, layout),
    )
    if preview != expected or _number(context, "DailyBoostBalance", image) != balance:
        raise RuntimeError(f"火焰预览 {preview[0]} → {preview[1]}，预期 {expected[0]} → {expected[1]}")
    logger.info("火焰设置 %d 档，开打前确认 %d → %d", tier, *preview)
    return preview


def _play(context, title, difficulty, preview):
    image = capture(context)
    observed = recognize(context, "PlayBandSongTitle", image)
    if not observed or not verify_band(context, image, title, difficulty):
        raise RuntimeError("开打前未能重新确认曲名和难度")
    before, after = preview
    override = {
        "PlayBandSongTitle": {"expected": exact_title_pattern(observed.text)},
        "PlayBandDifficulty": {"expected": f"^{difficulty}$"},
        "playsongsingle": {"custom_action_param": {"skip_late": True}},
        **_boost_preview(before, after, exact=True),
        "startlivesingle": {
            "all_of": [
                "SingleFreeBand",
                {"recognition": "OCR", "roi": [1020, 621, 220, 62], "expected": "^演出开始$"},
                "PlayBandSongTitle", "DailyBoostBefore", "DailyBoostAfter",
            ],
        },
    }
    if not reached(context, "ui_simplified_entry", "playsongsingle", override):
        raise RuntimeError("单曲任务中止，请检查演出画面")
    if not reached(context, "DailySettle", "DailyLiveStats"):
        raise RuntimeError("未确认演出正常结算")


def _return_after_live(context):
    if not reached(context, "DailySettleBack", "DailyLobby"):
        raise RuntimeError("已结算，但未能返回自由演出入口")


def _ready(context, *, keep_recruit=False):
    image = capture(context)
    if recognize(context, "DailyLobby", image):
        return
    if recognize(context, "DailyResumeSettlement", image):
        _return_after_live(context)
        return
    if recognize(context, "DailyRecruitList", image):
        if keep_recruit or reached(context, "DailyBackToHome", "StartupHomeReady"):
            return
        raise RuntimeError("无法从招募页返回主菜单")
    if not reached(context, "start_app", "StartupHomeReady"):
        raise RuntimeError("未进入主菜单，请检查是否需要登录")


def _go_to_recruit(context):
    if not recognize(context, "DailyRecruitList", capture(context)):
        if not reached(context, "DailyBackToHome", "StartupHomeReady"):
            raise RuntimeError("未能返回主菜单，无法进入招募")
    return recruit(context)


def _burn_boost(context, title, difficulty, regular, prioritize_max):
    _ready(context)
    completed = 0
    previous = None
    stalls = 0
    while True:
        if recognize(context, "FreeSongList", capture(context)):
            _band(context, title, difficulty)
        balance = _balance(context)
        if not balance:
            return completed
        if previous is not None and balance >= previous:
            stalls += 1
            if stalls >= 2:
                raise RuntimeError("连续两局后火焰未减少")
        else:
            stalls = 0
        _band(context, title, difficulty)
        balance = _balance(context)
        if not balance:
            return completed
        preview = _set_boost(context, balance, regular, prioritize_max)
        _play(context, title, difficulty, preview)
        previous = balance
        completed += 1
        logger.info("已确认第 %d 场结算", completed)
        _return_after_live(context)


class DailyClear(CustomAction):
    def run(self, context, argv):
        try:
            raw = argv.custom_action_param
            config = raw if isinstance(raw, dict) else json.loads(raw or "{}")
            # Separate MXU options merge in attach without replacing custom action parameters.
            node = context.get_node_data(argv.node_name) or {}
            options = node.get("attach") or {}
            title = config.get("title", "SAVIOR OF SONG").strip()
            difficulty = options.get("difficulty", config.get("difficulty", "EXPERT")).strip().upper()
            regular = int(options.get("regular", config.get("regular", 3)))
            max_option = config.get("max", "开")
            if not title or difficulty not in DIFFICULTIES or regular not in (1, 2, 3) or max_option not in ("开", "关"):
                raise RuntimeError("请填写完整曲名、有效难度和 1～3 的常规档")
            prioritize_max = options.get("prioritize_max", max_option == "开")
            completed = _burn_boost(context, title, difficulty, regular, prioritize_max is True)
            if not config.get("recruit_after", True):
                logger.info("清火完成，本次完成 %d 场", completed)
                return self.RunResult(success=True)
            status = _go_to_recruit(context)
            if status == "locked" and not completed:
                _ready(context)
                _band(context, title, difficulty)
                if _balance(context) != 0:
                    raise RuntimeError("火焰已恢复，请重新开始任务")
                _play(context, title, difficulty, _set_boost(context, 0, regular))
                completed += 1
                _return_after_live(context)
                status = _go_to_recruit(context)
            if status != "done":
                raise RuntimeError("游戏仍提示需要完成演出")
            logger.info("清火和招募完成，本次完成 %d 场", completed)
            return self.RunResult(success=True)
        except Exception:
            logger.exception("每日清火流程停止")
            return self.RunResult(success=False)


class DailyFreeRecruit(CustomAction):
    def run(self, context, argv):
        try:
            _ready(context, keep_recruit=True)
            status = _go_to_recruit(context)
            if status == "locked":
                raise RuntimeError("今日免费招募需要先完成一次演出")
            return self.RunResult(success=status == "done")
        except Exception:
            logger.exception("每日免费招募停止")
            return self.RunResult(success=False)
