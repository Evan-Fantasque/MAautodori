import logging
import time
import cv2
import numpy as np
import agent.custom.utils.StateCore as StateCore
from agent.custom.utils.util import get_color_eval_in_range, get_runtime_info
from agent.deploy.deploy import get_main_py_path

logging.basicConfig(level=logging.INFO)

OFFSET = {"up": 0, "down": 0, "move": 0, "wait": 0.0, "interval": 0.0}
PHOTOGATE_LATENCY = 30
CMD_SLICE_SIZE = 100
STABLE_THRESHOLD = 3
CONSECUTIVE_FRAMES_NEEDED = 300
FREEZE_SLEEP_TIME = 0.005
CONFIDENCE_THRESHOLD_PLAY = 0.9
CONFIDENCE_THRESHOLD_FAILURE = 0.8

def get_scaled_template(player_inst, template_path):
    template = cv2.imread(str(template_path), 0)
    if template is None:
        return None
    runtime_h, runtime_w, _ = player_inst.ipc_capture_display().shape
    scale_factor = runtime_w / 1920
    if np.isclose(scale_factor, 1.0):
        return template
    original_h, original_w = template.shape[:2]
    new_w = int(original_w * scale_factor)
    new_h = int(original_h * scale_factor)
    if new_w < 1 or new_h < 1:
        return template
    resized_template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized_template


def monitor_failure_thread(state: StateCore.MAautodoriState, stop_event, playback_started_event):
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

        logging.info("Received playback start signal, starting screen monitoring.")

        base_path = get_main_py_path().parent.parent
        fail_template_path = base_path / "assets/resource/image/live/live_failed.png"
        if not fail_template_path.exists():
            logging.error(
                f"Live Failed template image not found: {fail_template_path}, monitor thread cannot work.")
            stop_event.set()
            return

        template = get_scaled_template(state.player, fail_template_path)

        while not stop_event.is_set():
            screen_bgr = state.player.ipc_capture_display()
            if screen_bgr is None:
                time.sleep(1)
                continue

            screen_gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val >= CONFIDENCE_THRESHOLD_FAILURE:
                logging.error(f"Detected 'Live Failed' screen (match: {max_val:.2f})! Sending stop signal!")
                state.playback_interrupted = True
                stop_event.set()
                break

            time.sleep(1)

    except Exception as e:
        logging.error(f"Monitor thread encountered unexpected error: {e}", exc_info=True)
        stop_event.set()
    finally:
        logging.info("Monitor thread terminated.")

def play_song(state: StateCore.MAautodoriState, stop_event, playback_started_event):

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

    base_path = get_main_py_path().parent.parent
    template_path = base_path / "assets/resource/image/live/button/pause.png"
    template = get_scaled_template(state.player, template_path)
    if template is None:
        logging.error("Failed to load pause button template")
        return

    pause_button_found = False
    wait_start_time = time.time()
    playback_started_event.set()

    while not pause_button_found:
        wait_timeout = 30
        wait_current_time = time.time()
        if wait_current_time - wait_start_time > wait_timeout:
            logging.error(f"Waiting for pause button timeout ({wait_current_time - wait_start_time}s), aborting.")
            return
        if check_exit_status(stop_event):
            return

        screen = state.player.ipc_capture_display()
        height, width, _ = screen.shape
        roi_screen = screen[0:int(height * 0.15), width - int(height * 0.15):width]
        gray_roi = cv2.cvtColor(roi_screen, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(gray_roi, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        logging.debug(f"Waiting for pause button, match confidence: {max_val:.2f}")
        if max_val >= CONFIDENCE_THRESHOLD_PLAY:
            logging.info("Pause button detected, waiting for screen frozen.")
            pause_button_found = True
        else:
            time.sleep(0.5)

    if not wait_first_note(state, stop_event):
        return

    while True:
        if check_exit_status(stop_event):
            return

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

    time.sleep(2)
    logging.info("Playback finished.")


def wait_first_note(state: StateCore.MAautodoriState, stop_event):
    last_color = None
    waited_frames = 0
    info = get_runtime_info(state.player.resolution)["wait_first"]
    from_row, to_row = info["from"], info["to"]
    freezed = False
    playback_start_time = time.time()

    while True:
        playback_timeout = 500
        playback_current_time = time.time()
        if playback_current_time - playback_start_time > playback_timeout:
            logging.error(f"Playback timeout ({playback_current_time - playback_start_time}s), aborting.")
            return False
        if check_exit_status(stop_event):
            return False

        try:
            screen = state.player.ipc_capture_display()
            cur_color, _ = get_color_eval_in_range(screen, from_row, to_row)

            if last_color is not None:
                change_score = np.sum(np.abs(cur_color[:3].astype(int) - last_color[:3].astype(int)))

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
