import json
import logging
import re
import subprocess
from maa.custom_action import CustomAction
from maa.context import Context
from ..utils.MaaUI import reached
from ..utils.StateCore import global_state, init_player_and_mnt
from ..utils.chart import Chart

class SaveSong(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        logger = logging.getLogger("SaveSong")
        global_state.current_chart = None

        # 从 SongRecognition 的识别结果中获取歌曲名
        if not argv.reco_detail or not argv.reco_detail.best_result:
            logger.error("未获取到识别结果")
            return CustomAction.RunResult(success=False)
            
        name = argv.reco_detail.best_result.detail
        if not name:
            logger.error("识别结果中未包含歌曲名")
            return CustomAction.RunResult(success=False)

        params = argv.custom_action_param
        if isinstance(params, str):
            params = json.loads(params)
        backend = params.get("touch_backend") if isinstance(params, dict) else None
        if backend not in (None, "maafw", "legacy"):
            logger.error("无法识别打歌触控链路 %r", backend)
            return self.RunResult(success=False)
        native = backend == "maafw"
        difficulty = global_state.difficulty
        humanize = global_state.human_delay_enabled
        default_move_slice_size = global_state.default_move_slice_size
        cmd_slice_size = global_state.cmd_slice_size
        offset = global_state.offset

        current_song_name = str(name).strip('"')
        
        # 3. 获取歌曲 ID
        current_song_id = global_state.all_song_name_indexes.get(current_song_name)
        if not current_song_id:
            logger.error(f"无法找到歌曲 '{current_song_name}' 对应的 ID")
            return CustomAction.RunResult(success=False)

        if not native and (not global_state.player or not global_state.mnt):
            try:
                global_state.player, global_state.mnt = init_player_and_mnt(context)
            except Exception as e:
                logger.error(f"初始化设备失败: {e}", exc_info=True)
                return CustomAction.RunResult(success=False)

        # 更新全局状态
        global_state.current_song_name = current_song_name
        global_state.current_song_id = current_song_id
        
        # 生成图谱与触控命令
        try:
            # Both selectable backends take difficulty from the same band screen.
            # Older tasks without a backend parameter still use their configured difficulty.
            if backend is not None:
                if not reached(context, "PlayPreparePresentation", "PlayPresentationOff", reset_hits=("PlayPresentationEnabled",)):
                    logger.error("未能确认演奏模式为 OFF，本次演出未开始")
                    return self.RunResult(success=False)
                screen = context.tasker.controller.post_screencap().wait().get()
                if screen is None or not screen.size:
                    logger.error("无法读取编队页面")
                    return self.RunResult(success=False)
                detected = context.run_recognition("PlayBandDifficulty", screen)
                if not detected or not detected.hit or not detected.best_result:
                    logger.error("未确认当前难度")
                    return self.RunResult(success=False)
                difficulty = detected.best_result.text.lower()
            if native:
                resolution = (screen.shape[1], screen.shape[0])
            else:
                resolution = global_state.player.resolution

            current_chart = Chart((current_song_id, difficulty), current_song_name)
            current_chart.notes_to_actions(
                resolution,
                default_move_slice_size,
                humanize=humanize,
            )
            if not current_chart.actions:
                logger.error("没有可播放的谱面动作")
                return self.RunResult(success=False)
            if not native:
                orientation = self._get_orientation(context)
                global_state.orientation = orientation
                current_chart.actions_to_MNTcmd(
                    (global_state.mnt.max_x, global_state.mnt.max_y), orientation, offset, cmd_slice_size,
                )

            global_state.current_chart = current_chart
            global_state.current_touch_backend = "maafw" if native else "legacy"
            global_state.current_difficulty = difficulty
            logger.info("Prepared %s (%s) with %s", current_song_name, difficulty, global_state.current_touch_backend)
            return CustomAction.RunResult(success=True)
            
        except Exception as e:
            logger.error(f"生成图谱失败: {e}", exc_info=True)
            return CustomAction.RunResult(success=False)

    def _get_orientation(self, context: Context) -> int:
        """获取设备屏幕方向 (0, 1, 2, 3)"""
        logger = logging.getLogger("SaveSong")
        ctrl_info = context.tasker.controller.info
        adb_path = str(ctrl_info.get("adb_path"))
        adb_serial = ctrl_info.get("adb_serial")
        
        try:
            command_list = [
                adb_path,
                "-s",
                adb_serial,
                "shell",
                "dumpsys input|grep SurfaceOrientation",
            ]
            output = subprocess.check_output(command_list, text=True)
            match = re.search(r"SurfaceOrientation:\s*(\d+)", output)
            if match:
                orientation = int(match.group(1))
                logger.debug(f"SurfaceOrientation: {orientation}")
                return orientation
        except Exception as e:
            logger.error(f"Failed to get SurfaceOrientation: {e}")
        return 0
