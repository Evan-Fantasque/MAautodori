import logging

from maa.custom_action import CustomAction

from ..utils.MaaUI import capture, navigate, reached, recognize
from ..utils.SongSelection import exact_title_pattern


logger = logging.getLogger(__name__)


def enter_stage(context, special):
    image = capture(context)
    if not any(recognize(context, node, image) for node in (
        "StartupHomeReady", "SoloModeMenu", "SoloStageCatalog", "SoloConfirmStage",
        "SoloStageReady", "StageAreaItemsPrompt", "StageRosterMismatch", "StageRecommendationDone", "GameErrorDialog",
    )) and not reached(context, "start_app", "StartupHomeReady"):
        raise RuntimeError("未进入舞台挑战或游戏主菜单")

    catalog = "SoloSpecialStageCatalog" if special else "SoloMainStageCatalog"
    switch = "SoloSwitchSpecialStage" if special else "SoloSwitchMainStage"
    choice = [catalog, f"[JumpBack]{switch}"]
    if not navigate(context, "StageChallengeSelect", "SoloStageReady", {
        "StageChallengeSelect": {"next": [
            "GameErrorDialog", "StageCancelAreaItems", "StageCloseRosterMismatch", "StageRecommendationDone",
            "SoloStageReady", "SoloConfirmStage",
            *choice, "SoloEnterStage", "SoloModeMenu", "SoloOpenLive",
        ]},
        "SoloModeMenu": {"next": ["GameErrorDialog", "SoloEnterStage"]},
        "SoloEnterStage": {"next": ["GameErrorDialog", *choice, "SoloEnterStage"]},
    }, reset_hits=(
        "SoloOpenLive", "SoloEnterStage", catalog, switch, "SoloConfirmStage",
        "StageCancelAreaItems", "StageCloseRosterMismatch", "StageRecommendationDone",
    )):
        raise RuntimeError("未进入舞台挑战编队页，请确认舞台已解锁")


def play_stage(context, change_area_items):
    image = capture(context)
    title = recognize(context, "PlayBandSongTitle", image)
    difficulty = recognize(context, "PlayBandDifficulty", image)
    if not (title and difficulty and recognize(context, "PlayAutoOff", image)):
        raise RuntimeError("无法确认曲名、难度或自动演出已关闭")
    logger.info("舞台挑战 %s (%s)", title.text, difficulty.text)
    override = {
        "PlayBandSongTitle": {"expected": exact_title_pattern(title.text)},
        "PlayBandDifficulty": {"expected": f"^{difficulty.text}$"},
        "SingleReadSong": {"next": ["StageStart"]},
        "playsongsingle": {"recognition": "And", "all_of": ["PlayPauseReady"], "pre_delay": 0, "post_delay": 0,
                           "custom_action_param": {"skip_late": True}},
    }
    if change_area_items:
        override["StageStart"] = {"next": ["StageRosterMismatch", "[JumpBack]StageConfirmAreaItems", "playsongsingle"]}
    if not reached(context, "StagePrepareChart", "playsongsingle", override, reset_hits=("StageConfirmAreaItems",)):
        image = capture(context)
        if recognize(context, "StageAreaItemsPrompt", image):
            raise RuntimeError("游戏要求更换区域道具。可启用「舞台区域道具」后重试，或手动处理")
        if recognize(context, "StageRosterMismatch", image):
            raise RuntimeError("当前乐队不符合舞台条件。可启用「舞台推荐编组」后重试，或手动调整编组")
        raise RuntimeError("舞台挑战未打完，请检查乐队编成要求和演出画面")


class StageChallenge(CustomAction):
    def run(self, context, argv):
        try:
            options = (context.get_node_data(argv.node_name) or {}).get("attach") or {}
            enter_stage(context, options.get("special") is True)
            if options.get("recommend") is True and not reached(
                context, "StageRecommendRoster", "SoloStageReady", reset_hits=("StageRecommendationDone",),
            ):
                raise RuntimeError("游戏未能推荐符合要求的编组")
            play_stage(context, options.get("change_area_items") is True)
            if not reached(context, "StageSettle", "DailyLiveStats"):
                raise RuntimeError("未确认舞台挑战结算")
            if not reached(context, "StageReturn", "StageSettlementDone"):
                raise RuntimeError("舞台挑战已结算，但未能回到选关页或主页")
            return self.RunResult(success=True)
        except (RuntimeError, OSError):
            logger.exception("舞台挑战停止")
            return self.RunResult(success=False)
