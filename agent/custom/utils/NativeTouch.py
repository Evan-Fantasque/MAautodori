import logging
import time
from collections import deque


FAILURE_CHECK_INTERVAL = 3.0
MIN_FAILURE_CHECK_GAP = 0.120
STOP_CHECK_INTERVAL = 0.25
MIN_STOP_CHECK_GAP = 0.012


def play_native_actions(
    controller, actions, stop_event, rpc_lock, *, skip_late=False,
    is_stopping=None, check_failure=None,
):
    """Send chart touches at their original relative times through MaaFramework."""
    touches = [action for action in actions if action["type"] != "wait"]
    if not touches or any(action["finger"] is None for action in touches):
        return False

    logger = logging.getLogger("Play")
    pending = deque()
    held = set()
    submitted = set()
    first_time = touches[0]["time"]
    start = time.perf_counter()
    failed = False
    peak_lateness = 0.0
    skipped = 0
    next_failure_check = start + FAILURE_CHECK_INTERVAL
    next_stop_check = start
    peak_failure_check = 0.0
    failure_checks = 0

    def complete_touch():
        job, kind, contact = pending.popleft()
        # Keep a failed down in the cleanup set in case it reached Android.
        if kind == "down":
            held.add(contact)
        success = job.wait().succeeded
        if kind == "up" and success:
            held.discard(contact)
        return success

    def drain_pending():
        nonlocal failed
        while pending and (len(pending) >= 8 or pending[0][0].done):
            if not complete_touch():
                failed = True

    def wait_for_touch(deadline):
        nonlocal next_stop_check, next_failure_check, failure_checks, peak_failure_check
        while not stop_event.is_set() and not failed:
            now = time.perf_counter()
            remaining = deadline - now
            if remaining <= 0:
                return
            if is_stopping is not None and now >= next_stop_check and remaining >= MIN_STOP_CHECK_GAP:
                next_stop_check = now + STOP_CHECK_INTERVAL
                if is_stopping():
                    stop_event.set()
                    return
            failure_budget = max(MIN_FAILURE_CHECK_GAP, 2 * peak_failure_check + 0.020)
            if check_failure is not None and now >= next_failure_check and remaining >= failure_budget:
                with rpc_lock:
                    drain_pending()
                    check_start = time.perf_counter()
                    # A queued touch takes precedence even inside an otherwise long gap.
                    if not failed and not pending and not stop_event.is_set() and deadline - check_start >= failure_budget:
                        confirmed = check_failure()
                        check_end = time.perf_counter()
                        failure_checks += 1
                        peak_failure_check = max(peak_failure_check, check_end - check_start)
                        next_failure_check = check_end + FAILURE_CHECK_INTERVAL
                        if confirmed:
                            stop_event.set()
                            return
            remaining = deadline - time.perf_counter()
            if remaining > 0.001:
                time.sleep(min(remaining - 0.001, 0.02))

    try:
        for action in touches:
            with rpc_lock:
                drain_pending()
            if failed or stop_event.is_set():
                break

            deadline = start + (action["time"] - first_time) / 1000
            wait_for_touch(deadline)
            if failed or stop_event.is_set():
                break
            kind = action["type"]
            contact = action["finger"]
            with rpc_lock:
                if stop_event.is_set():
                    break
                lateness = time.perf_counter() - deadline
                peak_lateness = max(peak_lateness, lateness)
                if lateness > 0.075 and (not skip_late or lateness > 0.25):
                    logger.warning("MaaFW 触控调度落后 %.1f ms，停止本曲。", lateness * 1000)
                    failed = True
                    break
                if skip_late:
                    # A missed down has no corresponding on-device contact. Always
                    # release contacts we did send, even if the up deadline passed.
                    if kind != "down" and contact not in submitted:
                        continue
                    if lateness > 0.075 and kind != "up":
                        skipped += 1
                        continue
                if kind == "up":
                    job = controller.post_touch_up(contact)
                    submitted.discard(contact)
                elif kind == "down":
                    x, y = map(round, action["pos"])
                    job = controller.post_touch_down(x, y, contact=contact)
                    submitted.add(contact)
                else:
                    x, y = map(round, action["to"])
                    job = controller.post_touch_move(x, y, contact=contact)
                pending.append((job, kind, contact))
    finally:
        with rpc_lock:
            while pending:
                failed = not complete_touch() or failed
            for contact in held:
                if not controller.post_touch_up(contact).wait().succeeded:
                    logger.warning("触点 %s 未能抬起。", contact)
                    failed = True

    logger.info("MaaFW 触控最大提交延迟 %.1f ms。", peak_lateness * 1000)
    if check_failure is not None:
        logger.info("MaaFW 曲中失败检查 %d 次，单次最长 %.1f ms。", failure_checks, peak_failure_check * 1000)
    if skipped:
        logger.warning("跳过了 %d 个已错过时机的触控动作。", skipped)
    return not failed and not stop_event.is_set()
