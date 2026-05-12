"""
演奏结果保存动作
从 PlayResultRecognition 的识别结果中读取结算数据，执行：
- FC/AP 检测
- 失败计数与连续失败上限检测
- not_fc 歌曲追踪
- 单曲尝试次数追踪
- 通过 PlayRecord 持久化记录
"""
import json
import logging
import time
from maa.custom_action import CustomAction
from maa.context import Context
from ..utils.StateCore import global_state
from ..utils.chart import PlayRecord


class SavePlayResult(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        logger = logging.getLogger("SavePlayResult")

        try:
            # 1. 解析是否成功
            param = argv.custom_action_param
            if isinstance(param, str):
                param = json.loads(param)
            succeed = param.get("succeed", False) if isinstance(param, dict) else False

            playresult = {}

            if succeed and argv.reco_detail and argv.reco_detail.best_result:
                try:
                    detail = argv.reco_detail.best_result.detail
                    if isinstance(detail, str):
                        playresult = json.loads(detail)
                except json.JSONDecodeError:
                    logger.error("无法解析结算数据 JSON")
                    playresult = {}

                # 2. FC 检测
                if playresult:
                    self._check_fc_status(playresult, logger)

            # 3. 失败计数
            if succeed:
                if global_state.play_failed_times > 0:
                    logger.info(
                        f"任务成功，连续失败计数从 {global_state.play_failed_times} 重置为零"
                    )
                global_state.play_failed_times = 0
            else:
                global_state.play_failed_times += 1
                logger.info(
                    f"任务失败，当前连续失败计数: {global_state.play_failed_times}"
                )

            # 4. 保存演奏记录
            PlayRecord.create(
                play_time=int(time.time()),
                play_offset=global_state.offset,
                result=playresult,
                succeed=succeed,
                chart_id=global_state.current_song_id,
                difficulty=global_state.difficulty,
            )

            # 5. 歌曲尝试次数追踪
            if global_state.current_song_id:
                current_count = global_state.song_attempt_count_dict.get(
                    global_state.current_song_id, 0
                )
                global_state.song_attempt_count_dict[global_state.current_song_id] = (
                    current_count + 1
                )
                logger.info(
                    f"歌曲 '{global_state.current_song_name}' "
                    f"已尝试 {global_state.song_attempt_count_dict[global_state.current_song_id]} 次"
                )

            global_state.last_played_song_id = global_state.current_song_id

            # 6. 连续失败上限检测
            if global_state.play_failed_times >= global_state.max_continuous_failed_times:
                logger.error(
                    f"连续失败已达上限 ({global_state.max_continuous_failed_times})，自动停止"
                )
                context.run_action("close_app")
                context.run_action("stop")

            return CustomAction.RunResult(success=True)

        except Exception as e:
            logger.error(f"保存演奏结果失败: {e}", exc_info=True)
            return CustomAction.RunResult(success=False)

    def _check_fc_status(self, playresult: dict, logger: logging.Logger):
        """检查是否 Full Combo / All Perfect，并更新 not_fc 计数"""
        perfect = playresult.get("perfect", -1)
        great = playresult.get("great", -1)
        good = playresult.get("good", -1)
        bad = playresult.get("bad", -1)
        miss = playresult.get("miss", -1)
        maxcombo = playresult.get("maxcombo", -1)

        is_not_fc = False
        reasons = []

        # AP 判定：perfect + great == maxcombo
        is_ap_by_sum = (
            perfect != -1
            and great != -1
            and maxcombo != -1
            and (perfect + great) == maxcombo
        )

        if is_ap_by_sum:
            is_not_fc = False
        else:
            if -1 in [perfect, great, good, bad, miss, maxcombo]:
                is_not_fc = True
                reasons.append("OCR Failed")
            else:
                if bad > 0:
                    reasons.append(f"Bad: {bad}")
                if miss > 0:
                    reasons.append(f"Miss: {miss}")
                if good > 0:
                    reasons.append(f"Good: {good}")

                sum_of_judgements = perfect + great
                if maxcombo != sum_of_judgements:
                    reasons.append(f"P+G={sum_of_judgements}, MaxCombo={maxcombo}")

                if reasons:
                    is_not_fc = True

        if is_not_fc and global_state.current_song_id:
            current_count = global_state.not_fc_count_dict.get(
                global_state.current_song_id, 0
            )
            global_state.not_fc_count_dict[global_state.current_song_id] = current_count + 1
            logger.warning(
                f"歌曲 '{global_state.current_song_name}' 未 Full Combo，"
                f"累计: {global_state.not_fc_count_dict[global_state.current_song_id]} 次，"
                f"原因: {', '.join(reasons)}"
            )
