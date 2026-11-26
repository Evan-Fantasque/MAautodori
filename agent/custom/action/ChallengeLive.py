import json
import logging

from maa.custom_action import CustomAction

from ..utils.MaaUI import capture, click, navigate, reached, recognize
from ..utils.SongSelection import DIFFICULTIES, exact_title_pattern, select_song, verify_band


logger = logging.getLogger(__name__)
TIERS = (200, 400, 800, 1600)
SONG_LIST = "ChallengeSongList"
ACHIEVEMENT_NODES = ("ChallengeRewardOK", "ChallengeRewardListClose")
REWARD_NODES = (*ACHIEVEMENT_NODES, "DailyLiveLargeRewardOK", "DailyLiveRewardOK", "DailyLiveRewardNext")
ENTER_CHALLENGE = {
    "SoloModeMenu": {"next": ["GameErrorDialog", "SoloEnterChallenge"]},
    "SoloEnterChallenge": {"next": ["GameErrorDialog", SONG_LIST]},
}


def choose_tier(balance, preferred, floor):
    if balance >= preferred:
        return preferred
    if floor:
        return next((tier for tier in reversed(TIERS) if floor <= tier <= balance), None)
    return None


def _enter_selection(context):
    image = capture(context)
    if not any(recognize(context, node, image) for node in (
        "ChallengeCPDialog", "ChallengeBandReady", SONG_LIST, "SoloModeMenu", "StartupHomeReady", "GameErrorDialog",
    )) and not reached(context, "start_app", "StartupHomeReady"):
        raise RuntimeError("未进入主菜单，请检查游戏是否需要登录")
    if not navigate(context, "ChallengeEnterSelection", SONG_LIST, ENTER_CHALLENGE,
                    reset_hits=("ChallengeCPCancel", "ChallengeBandBack")):
        raise RuntimeError("未找到挑战演出选曲页，请确认当前活动开放挑战演出")


def _balance(context, node, image):
    result = recognize(context, node, image)
    if not result:
        raise RuntimeError("无法读取所持挑战点数")
    return int(result.text)


def _select_cost(context, tier, balance):
    if not reached(context, "ChallengeOpenCP", "ChallengeCPDialog", {
        "SoloConfirmChallengeSong": {"next": ["ChallengeCPDialog"]},
    }):
        raise RuntimeError("未进入挑战点数选择窗口")
    image = capture(context)
    if _balance(context, "ChallengeDialogBalance", image) != balance:
        raise RuntimeError("点数窗口余额和选曲页不一致，请重新启动挑战任务")

    y = 213 + TIERS.index(tier) * 73
    fields = {
        "ChallengeDialogBalance": {"expected": f"^{balance}$"},
        "ChallengeTierLabel": {"roi": [477, y - 23, 91, 46], "expected": f"^{tier}$"},
        "ChallengeTierSelected": {"roi": [857, y - 20, 39, 40]},
    }
    if not recognize(context, "ChallengeTierLabel", image, fields):
        raise RuntimeError(f"找不到 {tier} 点档")
    if not recognize(context, "ChallengeTierSelected", image, fields) and not click(context, (876, y)):
        raise RuntimeError(f"无法选择 {tier} 点档")
    if not reached(context, "ChallengeApplyCost", "ChallengeBandReady", fields):
        raise RuntimeError(f"未确认 {tier} 点档，请检查点数窗口")


def _play(context, title, difficulty, tier):
    image = capture(context)
    observed = recognize(context, "PlayBandSongTitle", image)
    if not observed or not verify_band(context, image, title, difficulty):
        raise RuntimeError("最终确认页的曲名或难度和任务设置不一致")
    if not reached(context, "ChallengePrepareChart", "playsongsingle", {
        "PlayBandSongTitle": {"expected": exact_title_pattern(observed.text)},
        "PlayBandDifficulty": {"expected": f"^{difficulty}$"},
        "ChallengeBandCost": {"expected": fr"^{tier}\s*消[费耗]$"},
        "SingleReadSong": {"next": ["ChallengeStart"]},
        "playsongsingle": {"custom_action_param": {"skip_late": True}},
    }):
        raise RuntimeError(f"未能按 {tier} 点档完成演出，已停止")
    if not reached(context, "ChallengeSettle", "DailyLiveStats", reset_hits=REWARD_NODES):
        raise RuntimeError("未确认挑战演出正常结算，已停止")
    if not reached(context, "ChallengeReturn", SONG_LIST, ENTER_CHALLENGE, reset_hits=(
        *REWARD_NODES, "DailyLiveStatsNext", "DailyLiveExpNext", "DailyLiveRankUp", "DailyLivePointsOK",
        "StoryOpenMenu", "StorySelectSkip", "StoryConfirmSkip", "GameRetryConnection",
    )):
        raise RuntimeError("已结算，但未能返回挑战演出选曲页")


class ChallengeLive(CustomAction):
    def run(self, context, argv):
        try:
            raw = argv.custom_action_param
            config = raw if isinstance(raw, dict) else json.loads(raw or "{}") or {}
            options = (context.get_node_data(argv.node_name) or {}).get("attach") or {}
            difficulty = options.get("difficulty", "EXPERT")
            preferred = options.get("cp_tier", 200)
            floor = options.get("cp_floor", 0)
            if preferred not in TIERS or difficulty not in DIFFICULTIES:
                raise RuntimeError("请选择有效的挑战点数档和曲目难度")
            if floor not in (0, *TIERS) or floor > preferred:
                raise RuntimeError("降档下限不能高于首选挑战点数档")

            _enter_selection(context)
            title = config.get("title", "").strip()
            image = capture(context)
            balance = _balance(context, "ChallengeBalance", image)
            completed = 0
            while (tier := choose_tier(balance, preferred, floor)) is not None:
                if not title:
                    song = recognize(context, "PlaySelectSongTitle", image)
                    if not song:
                        raise RuntimeError("无法读取当前挑战曲名，请在任务里填写完整曲名")
                    title = song.text
                if not select_song(context, title, difficulty, list_node=SONG_LIST):
                    raise RuntimeError(f"挑战曲目不可用或无法选择难度（{title} {difficulty}）")
                logger.info("挑战演出 %s %s，余额 %d，本场 %d 点", title, difficulty, balance, tier)
                _select_cost(context, tier, balance)
                _play(context, title, difficulty, tier)
                completed += 1
                image = capture(context)
                remaining = _balance(context, "ChallengeBalance", image)
                if remaining != balance - tier:
                    raise RuntimeError(f"结算后余额为 {remaining}，预期为 {balance - tier}，已停止")
                balance = remaining
            logger.info("挑战演出结束，完成 %d 场，剩余 %d 点，不足 %d 点档", completed, balance,
                        floor or preferred)
            return self.RunResult(success=True)
        except Exception:
            logger.exception("挑战演出流程停止")
            return self.RunResult(success=False)
