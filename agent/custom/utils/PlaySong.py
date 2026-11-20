import logging
import time
import numpy as np
from maa.context import Context
import agent.custom.utils.StateCore as StateCore
from agent.custom.utils.NativeTouch import play_native_actions
from agent.custom.utils.util import get_runtime_info

logging.basicConfig(level=logging.INFO)

OFFSET = {"up": 0, "down": 0, "move": 0, "wait": 0.0, "interval": 0.0}
PHOTOGATE_LATENCY = 30
CMD_SLICE_SIZE = 100
STABLE_THRESHOLD = 3
CONSECUTIVE_FRAMES_NEEDED = 300
FREEZE_SLEEP_TIME = 0.005


def match_play_screen(context: Context, controller, node: str) -> bool:
    image = controller.post_screencap().wait().get()
    if image is None or image.size == 0:
        return False
    result = context.run_recognition(node, image)
    return result is not None and result.hit


def confirm_native_failure(context, controller, state):
    try:
        failed = match_play_screen(context, controller, "PlayFailureVisible")
    except Exception:
        logging.warning("失败画面检查异常，继续演奏。", exc_info=True)
        return False
    if failed:
        state.playback_interrupted = True
        logging.warning("Detected 'Live Failed' screen.")
    return failed


def monitor_failure_thread(context, controller, state, stop_event, playback_started_event, rpc_lock):
    """
    A background monitoring thread.
    It waits for the playback start signal, then continuously monitors for the "Live Failed" screen through image matching.
    """
    try:
        logging.info("Monitor thread started, waiting for playback start signal.")

        playback_started_event.wait(timeout=30)

        if not playback_started_event.is_set():
            logging.warning("Timeout waiting for playback start signal, monitor thread exiting.")
            stop_event.set()
            return
        if stop_event.is_set():
            return

        logging.info("Received playback start signal, starting screen monitoring.")

        while not stop_event.is_set():
            with rpc_lock:
                if context.tasker.stopping:
                    stop_event.set()
                    break
                failed = match_play_screen(context, controller, "PlayFailureVisible")
            if failed:
                logging.warning("Detected 'Live Failed' screen.")
                state.playback_interrupted = True
                stop_event.set()
                break

            stop_event.wait(1)

    except Exception as e:
        logging.error(f"Monitor thread encountered unexpected error: {e}", exc_info=True)
        stop_event.set()
    finally:
        logging.info("Monitor thread terminated.")

def play_song(context: Context, controller, state, stop_event, playback_started_event, rpc_lock, *, skip_late=False) -> bool:

    logging.info("Start play")
    state.clear_cmd_log()
    state.reset_for_new_task()

    def _get_wait_time():
        wait_for = 0.0
        if state.current_chart is not None:
            index = state.current_chart.actions_to_cmd_index
            for action in state.current_chart.actions[index - CMD_SLICE_SIZE : index]:
                if action["type"] == "wait":
                    wait_for += action["length"]
            return wait_for
        return wait_for

    def _adjust_offset():
        total_cost = 0.0
        for type_ in ["up", "down", "move", "wait", "interval"]:
            type_data = state.callback_data[type_]
            total = type_data["total"]
            if total != 0:
                total_cost += type_data["total_offset"] - OFFSET[type_] * total
                OFFSET[type_] = type_data["total_offset"] / total

        if state.current_chart is not None:
            state.current_chart._a2c_offset += total_cost
        logging.debug("Adjust offset: {}".format(OFFSET))
        logging.debug("Adjust _actions_to_cmd_offset: {}".format(total_cost))

    logging.info("Waiting for game to load, detecting pause button.")

    native = state.current_touch_backend == "maafw"

    def is_stopping():
        return context.tasker.stopping

    wait_deadline = time.monotonic() + 30
    playback_started_event.set()

    while True:
        if check_exit_status(stop_event) or (native and is_stopping()):
            return False
        with rpc_lock:
            pause_visible = match_play_screen(context, controller, "PlayPauseReady")
        if pause_visible:
            logging.info("Pause button detected, waiting for screen frozen.")
            break
        if time.monotonic() >= wait_deadline:
            logging.error("Waiting for pause button timed out.")
            return False
        stop_event.wait(0.5)

    if native:
        if not wait_native_first_note(
            controller, state.current_chart, stop_event, rpc_lock, is_stopping=is_stopping
        ):
            return False

        def check_failure():
            return confirm_native_failure(context, controller, state)

        complete = play_native_actions(
            controller, state.current_chart.actions, stop_event, rpc_lock, skip_late=skip_late,
            is_stopping=is_stopping, check_failure=check_failure,
        )
        return (
            complete and not stop_event.wait(2) and not is_stopping() and not check_failure()
        )
    if not wait_first_note(state, stop_event):
        return False

    while True:
        if check_exit_status(stop_event):
            return False

        state.current_chart.command_builder.publish(state.mnt, block=False)
        wait_time = _get_wait_time()
        time.sleep(max(0, wait_time - 3) / 1000)

        index = state.current_chart.actions_to_cmd_index
        if state.current_chart.actions[index : index + CMD_SLICE_SIZE]:
            with state.callback_data_lock:
                _adjust_offset()
                state.callback_data = state._generate_default_callback_data()
            state.current_chart.actions_to_MNTcmd(
                (state.mnt.max_x, state.mnt.max_y), state.orientation, OFFSET, CMD_SLICE_SIZE
            )
        else:
            break

    if stop_event.wait(2):
        return False
    logging.info("Playback finished.")
    return True


def wait_native_first_note(controller, chart, stop_event, rpc_lock, *, is_stopping=None):
    first = next((action for action in chart.actions if action["type"] == "down"), None)
    if first is None:
        return False

    width, height = chart.screen_resolution
    positions = [action["pos"] for action in chart.actions
                 if action["type"] == "down" and action["time"] == first["time"]]
    judge_y = round(first["pos"][1])
    upper_y, lower_y = judge_y - round(40 * height / 720), judge_y - round(14 * height / 720)
    radius = round(60 * width / 1280)
    deadline = time.monotonic() + 20
    line_since = None
    baseline = None
    crossed_upper = {}
    armed = {}
    next_stop_poll = 0.0

    while not stop_event.is_set() and time.monotonic() < deadline:
        now = time.monotonic()
        if is_stopping is not None and now >= next_stop_poll:
            if is_stopping():
                return False
            next_stop_poll = now + 0.25
        with rpc_lock:
            screen = controller.post_screencap().wait().get()
        now = time.monotonic()
        if screen is None or screen.shape[:2] != (height, width):
            stop_event.wait(FREEZE_SLEEP_TIME)
            continue

        # The opening fade changes the entire lane before the judgement line is fully drawn.
        line = screen[judge_y - 2 : judge_y + 3, width // 10 : -width // 10].astype(np.int16)
        blue, green, red = (line[:, :, channel] for channel in range(3))
        cyan = (blue > 133) & (green > 133) & (np.minimum(blue, green) - red > 25)
        if np.count_nonzero(cyan) < 0.7 * width:
            line_since = baseline = None
            crossed_upper.clear()
            armed.clear()
        elif line_since is None:
            line_since = now
        elif now - line_since >= 0.25:
            strips = []
            for x, _ in positions:
                left, right = max(0, round(x) - radius), min(width, round(x) + radius)
                strips.append(tuple(screen[y - 2 : y + 3, left:right].astype(np.int16)
                                    for y in (upper_y, lower_y)))
            if baseline is None:
                baseline = strips
            else:
                for i, (top, bottom) in enumerate(strips):
                    ref_top, ref_bottom = baseline[i]
                    upper = np.count_nonzero(np.max(np.abs(top - ref_top), axis=2) > 65) > 25
                    lower = np.count_nonzero(np.max(np.abs(bottom - ref_bottom), axis=2) > 65) > 25
                    if not upper and not lower:
                        armed[i] = True
                        crossed_upper.pop(i, None)
                    if upper and not lower and armed.get(i) and i not in crossed_upper:
                        crossed_upper[i] = now
                    if lower and i in crossed_upper:
                        crossing = now - crossed_upper.pop(i)
                        armed[i] = False
                        if 0 < crossing <= 0.18:
                            # The lower strip is just above the line and detects the leading edge.
                            delay = min(0.035, max(0.012, crossing * 0.7 + 0.005))
                            logging.info("First note crossed both lane strips; starting native timing.")
                            return not stop_event.wait(delay)

        time.sleep(FREEZE_SLEEP_TIME)

    logging.warning("未确认首音符经过判定线，停止本曲。")
    return False


def wait_first_note(state: StateCore.MAautodoriState, stop_event):
    last_color = None
    waited_frames = 0
    info = get_runtime_info(state.player.resolution)["wait_first"]
    from_row, to_row = info["from"], info["to"]
    freezed = False
    playback_start_time = time.monotonic()

    while True:
        playback_timeout = 500
        playback_current_time = time.monotonic()
        if playback_current_time - playback_start_time > playback_timeout:
            logging.error(f"Playback timeout ({playback_current_time - playback_start_time}s), aborting.")
            return False
        if check_exit_status(stop_event):
            return False

        try:
            screen = state.player.ipc_capture_display()
            if screen is None or not screen.size:
                stop_event.wait(FREEZE_SLEEP_TIME)
                continue
            cur_color = screen[from_row : to_row + 1].mean(axis=(0, 1))

            if last_color is not None:
                change_score = abs(cur_color[:3].astype(int) - last_color[:3].astype(int)).sum()

                if change_score > STABLE_THRESHOLD:
                    if freezed:
                        logging.info("First note detected, starting playback.")
                        time.sleep(PHOTOGATE_LATENCY / 1000)
                        return True
                else:
                    if not freezed:
                        waited_frames += 1

                if not freezed and waited_frames >= CONSECUTIVE_FRAMES_NEEDED:
                    freezed = True
                    logging.info("Screen has frozen. Photogate is ready.")

            last_color = cur_color
            time.sleep(FREEZE_SLEEP_TIME)

        except Exception as e:
            logging.error(f"Error during photogate detection: {e}")
            return False


def check_exit_status(stop_event):
    if stop_event.is_set():
        logging.warning("Playback failed, exiting.")
        return True
    return False
