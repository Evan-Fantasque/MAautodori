import logging
import re
import subprocess
from maa.custom_action import CustomAction
from maa.context import Context
from ..utils.StateCore import global_state, init_player_and_mnt
from ..utils.chart import Chart

class SaveSong(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        logger = logging.getLogger("SaveSong")
        
        # 1. 确保设备已初始化
        if not global_state.player or not global_state.mnt:
            try:
                global_state.player, global_state.mnt = init_player_and_mnt(context)
            except Exception as e:
                logger.error(f"初始化设备失败: {e}", exc_info=True)
                return CustomAction.RunResult(success=False)

        # 2. 从上一步（SongRecognition）的识别结果中获取歌曲名
        if not argv.reco_detail or not argv.reco_detail.best_result:
            logger.error("未获取到识别结果")
            return CustomAction.RunResult(success=False)
            
        name = argv.reco_detail.best_result.detail
        if not name:
            logger.error("识别结果中未包含歌曲名")
            return CustomAction.RunResult(success=False)

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

        # 4. 更新全局状态
        global_state.current_song_name = current_song_name
        global_state.current_song_id = current_song_id
        
        # 5. 生成图谱与触控命令
        try:
            current_chart = Chart((current_song_id, difficulty), current_song_name)
            current_chart.notes_to_actions(
                global_state.player.resolution, 
                default_move_slice_size, 
                humanize=humanize
            )
            
            # 获取屏幕方向
            orientation = self._get_orientation(context)
            global_state.orientation = orientation
            
            current_chart.actions_to_MNTcmd(
                (global_state.mnt.max_x, global_state.mnt.max_y), 
                orientation, 
                offset, 
                cmd_slice_size
            )
            
            global_state.current_chart = current_chart
            logger.info(f"Saved song chart for: {current_song_name}")
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
