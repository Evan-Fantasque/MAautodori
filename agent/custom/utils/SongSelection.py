import re
import time
import unicodedata

import cv2
import numpy as np

from .MaaUI import capture, click, recognize


DIFFICULTIES = dict(zip(("EASY", "NORMAL", "HARD", "EXPERT", "SPECIAL"), (713, 825, 938, 1050, 1181)))

def title_key(value):
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


def _label(context, node, image):
    result = recognize(context, node, image)
    return result.text if result else ""


def verify_band(context, image, title, difficulty):
    return (
        title_key(_label(context, "PlayBandSongTitle", image)) == title_key(title)
        and _label(context, "PlayBandDifficulty", image) == difficulty
    )


def select_difficulty(context, difficulty, *, list_node="FreeSongList"):
    image = capture(context)
    if not recognize(context, list_node, image):
        return False
    x = DIFFICULTIES[difficulty]
    label = recognize(context, "SongPickerDifficulty", image, {
        "SongPickerDifficulty": {"roi": [x - 55, 558, 110, 30], "expected": f"^{difficulty}$"}
    })
    if not label:
        return False
    region = image[517:555, x - 19:x + 19]
    if np.count_nonzero(np.ptp(region, axis=2) > 45) < 100:
        if not click(context, (x, 539)):
            return False
        time.sleep(0.5)
        image = capture(context)
        region = image[517:555, x - 19:x + 19]
    return np.count_nonzero(np.ptp(region, axis=2) > 45) >= 100


def _find_visible(context, image, title):
    # OCR keeps original spacing; normalize only for exact title comparison.
    result = context.run_recognition("SongPickerVisibleTitles", image)
    if not result:
        return None
    matches = [item for item in result.all_results if title_key(item.text) == title_key(title)]
    if len(matches) == 1:
        return matches[0].box
    return None


def _search_list(context, title, list_node):
    deadline = time.monotonic() + 150
    controller = context.tasker.controller
    expected = title_key(title)
    for direction in (-1, 1):
        previous = None
        stalls = 0
        while time.monotonic() < deadline:
            image = capture(context)
            if not recognize(context, list_node, image):
                return False
            if title_key(_label(context, "PlaySelectSongTitle", image)) == expected:
                return True
            found = _find_visible(context, image, title)
            if found:
                if not click(context, found):
                    return False
                time.sleep(0.55)
                confirmed = capture(context)
                return title_key(_label(context, "PlaySelectSongTitle", confirmed)) == expected
            if recognize(context, "SongPickerNoEntries", image):
                return False
            content = image[140:577, 216:550]
            if previous is not None and cv2.absdiff(content, previous).mean() < 0.4:
                stalls += 1
                if stalls >= 2:
                    break
            else:
                stalls = 0
            previous = content.copy()
            start, end = 350 + direction * 150, 350 - direction * 150
            if not controller.post_swipe(390, start, 390, end, 360).wait().succeeded:
                return False
            time.sleep(0.4)
    return False


def select_song(context, title, difficulty, *, list_node="FreeSongList"):
    """Find a song in a compatible list and verify the requested difficulty on that song."""
    # A difficulty filter can change which songs are visible.
    select_difficulty(context, difficulty, list_node=list_node)
    if _search_list(context, title, list_node):
        return select_difficulty(context, difficulty, list_node=list_node)
    image = capture(context)
    if not recognize(context, list_node, image):
        return False
    all_songs = recognize(context, "SongPickerAllSongs", image)
    if not all_songs or not click(context, all_songs.box):
        return False
    time.sleep(0.6)
    return _search_list(context, title, list_node) and select_difficulty(context, difficulty, list_node=list_node)


def exact_title_pattern(title):
    return r"^\s*" + r"\s*".join(re.escape(part) for part in title.split()) + r"\s*$"
