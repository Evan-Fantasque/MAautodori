from maa.custom_action import CustomAction
from maa.context import Context
import threading
import logging
from ..utils.StateCore import global_state, init_player_and_mnt
from ..utils.PlaySong import play_song, monitor_failure_thread

class Play(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        logger = logging.getLogger("Play")
        
        # 1. 初始化外部控制器 (Minitouch/Player)
        if not global_state.player or not global_state.mnt:
            try:
                global_state.player, global_state.mnt = init_player_and_mnt(context)
            except Exception as e:
                logger.error(f"初始化设备失败: {e}", exc_info=True)
                return CustomAction.RunResult(success=False)

        stop_event = global_state.stop_event
        playback_started_event = global_state.playback_started_event
        
        stop_event.clear()
        playback_started_event.clear()
        
        monitor = threading.Thread(
            target=monitor_failure_thread,
            args=(global_state, stop_event, playback_started_event),
            daemon=True
        )
        try:
            monitor.start()
            play_song(global_state, stop_event, playback_started_event)
            stop_event.set()
            return CustomAction.RunResult(success=True)
        except Exception as e:
            stop_event.set()
            logger.error(f"Error during song playback: {e}", exc_info=True)
            return CustomAction.RunResult(success=False)
        finally:
            monitor.join(timeout=5)
