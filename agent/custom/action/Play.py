from maa.custom_action import CustomAction
from maa.context import Context
import json
import threading
import logging
from ..utils.StateCore import global_state, init_player_and_mnt
from ..utils.PlaySong import play_song, monitor_failure_thread

class Play(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        logger = logging.getLogger("Play")

        if global_state.current_chart is None:
            logger.error("未准备好谱面")
            return CustomAction.RunResult(success=False)
        
        # 1. 初始化外部控制器 (Minitouch/Player)
        if global_state.current_touch_backend == "legacy" and (not global_state.player or not global_state.mnt):
            try:
                global_state.player, global_state.mnt = init_player_and_mnt(context)
            except Exception as e:
                logger.error(f"初始化设备失败: {e}", exc_info=True)
                return CustomAction.RunResult(success=False)

        stop_event = global_state.stop_event
        playback_started_event = global_state.playback_started_event
        # Agent screenshot transfers share the same request/reply channel as controls.
        rpc_lock = threading.Lock()
        
        stop_event.clear()
        playback_started_event.clear()
        
        monitor = None
        try:
            controller = context.tasker.controller
            if global_state.current_touch_backend == "legacy":
                monitor = threading.Thread(
                    target=monitor_failure_thread,
                    args=(context.clone(), controller, global_state, stop_event, playback_started_event, rpc_lock),
                    daemon=True,
                )
                monitor.start()
            params = argv.custom_action_param or {}
            if isinstance(params, str):
                params = json.loads(params)
            completed = play_song(
                context, controller, global_state, stop_event, playback_started_event, rpc_lock,
                skip_late=isinstance(params, dict) and params.get("skip_late") is True,
            )

            if global_state.playback_interrupted:
                logger.warning("检测到 Live Failed 信号，演奏未正常完成")
                return CustomAction.RunResult(success=False)

            return CustomAction.RunResult(success=completed)
        except Exception as e:
            logger.error(f"Error during song playback: {e}", exc_info=True)
            return CustomAction.RunResult(success=False)
        finally:
            stop_event.set()
            playback_started_event.set()
            if monitor is not None and monitor.ident is not None:
                monitor.join(timeout=5)
