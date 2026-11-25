import logging
import math
import re
from fractions import Fraction
from hashlib import sha256
from pathlib import Path


_CHART_DIRECTORY = Path(__file__).resolve().parents[3] / "charts"
_LANES = {code: lane for lane, code in enumerate("6123458")}
_ROW = re.compile(r"#([0-9]{3})([0-9A-Z]{2}):\s*(\S+)", re.IGNORECASE)
_SLIDE = re.compile(r"slide_(?:(end)(?:_(flick))?_)?([ab])(?:_skill)?\.wav")
_TAPS = {"bd.wav", "skill.wav", "fever_note.wav"}
_FLICKS = {"flick.wav", "fever_note_flick.wav"}
_TAP_AND_FLICK_SOUNDS = _TAPS | _FLICKS
_BUTAI_EXPERT_HASH = "f922098f5c98ab08ebb2ec44dd69a05589fecb6bf77a8df3b836ed4551d26d37"
_LOGGER = logging.getLogger(__name__)


def load_local_bms(song_id, difficulty):
    difficulty = difficulty.lower()
    if not re.fullmatch(r"[0-9]+", str(song_id)) or not re.fullmatch(r"[a-z]+", difficulty):
        return None
    for extension in (".bms", ".txt"):
        path = _CHART_DIRECTORY / f"{song_id}-{difficulty}{extension}"
        try:
            source = path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            continue
        except (OSError, UnicodeError) as error:
            raise ValueError(f"无法读取本地谱面 {path}: {error}") from error
        try:
            known_chart = str(song_id) == "792" and difficulty == "expert"
            chart = parse_bms(source, known_butai=known_chart)
        except ValueError as error:
            raise ValueError(f"本地谱面 {path}: {error}") from error
        _LOGGER.info("已读取本地 BMS 谱面 %s", path)
        return chart
    return None


def _parse_rows(source):
    sounds, extended_bpm, measure_lengths = {}, {}, {}
    rows = []
    initial_bpm = None
    for line in source.splitlines():
        line = line.strip()
        row = _ROW.fullmatch(line)
        if row:
            measure, channel, content = row.groups()
            measure = int(measure)
            if channel.upper() == "02":
                try:
                    ratio = Fraction(content)
                except (ValueError, ZeroDivisionError) as error:
                    raise ValueError(f"第 {measure} 小节长度无效") from error
                if ratio <= 0:
                    raise ValueError(f"第 {measure} 小节长度必须为正数")
                measure_lengths[measure] = ratio * 4
            else:
                rows.append((measure, channel.upper(), content.upper()))
            continue
        key, _, value = line.replace("\t", " ").partition(" ")
        key, value = key.upper(), value.strip()
        if key == "#BPM":
            initial_bpm = float(value)
        elif re.fullmatch(r"#BPM[0-9A-Z]{2}", key):
            extended_bpm[key[-2:]] = float(value)
        elif re.fullmatch(r"#WAV[0-9A-Z]{2}", key):
            sounds[key[-2:]] = value.casefold()
        elif key in {"#RANDOM", "#SETRANDOM", "#IF", "#SWITCH", "#SETSWITCH"}:
            raise ValueError(f"暂不支持 {key}")
        elif key == "#LNOBJ" or (key == "#LNTYPE" and value != "1"):
            raise ValueError(f"暂不支持此长按格式 {key} {value}")
        elif re.match(r"#[0-9]{3}[0-9A-Z]{2}", key):
            raise ValueError(f"无效的小节事件 {line}")
    if initial_bpm is None:
        raise ValueError("缺少初始 BPM")

    tempo = {Fraction(0): initial_bpm}
    starts = [Fraction(0)]
    for measure in range(max((row[0] for row in rows), default=0)):
        starts.append(starts[-1] + measure_lengths.get(measure, 4))
    events = []
    for measure, channel, content in rows:
        if channel == "01":  # Background audio and fever cues.
            continue
        if len(content) % 2 or not re.fullmatch(r"[0-9A-Z]+", content):
            raise ValueError(f"第 {measure} 小节的 {channel} 轨数据无效")
        length = measure_lengths.get(measure, 4)
        for index in range(0, len(content), 2):
            token = content[index:index + 2]
            if token == "00":
                continue
            beat = starts[measure] + length * Fraction(index, len(content))
            if channel == "03":
                tempo[beat] = int(token, 16)
            elif channel == "08" and token in extended_bpm:
                tempo[beat] = extended_bpm[token]
            elif channel[0] in "15" and channel[1] in _LANES and token in sounds:
                events.append((beat, channel, sounds[token]))
            else:
                raise ValueError(f"第 {float(beat):g} 拍包含不支持的轨道或标记 {channel}:{token}")
    if not all(math.isfinite(bpm) and bpm > 0 for bpm in tempo.values()):
        raise ValueError("BPM 必须为正数")
    return tempo, sorted(events)


def parse_bms(source, *, known_butai=False):
    tempo, events = _parse_rows(source)
    notes, holds, slides, previous_slides = [], {}, {}, {}
    # This raw chart contains two consecutive end markers on slide B.
    join_butai = known_butai and sha256(source.encode("utf-8")).hexdigest() == _BUTAI_EXPERT_HASH
    for beat, channel, sound in events:
        lane = _LANES[channel[1]]
        node = {"beat": float(beat), "lane": lane}
        if channel[0] == "5":
            if sound not in _TAP_AND_FLICK_SOUNDS:
                raise ValueError(f"第 {float(beat):g} 拍的长按标记不受支持: {sound}")
            if lane in holds:
                node["flick"] = sound in _FLICKS
                notes.append({"type": "Long", "connections": [holds.pop(lane), node]})
            elif sound in _TAPS:
                holds[lane] = node
            else:
                raise ValueError(f"第 {float(beat):g} 拍的长按结束没有起点")
        elif sound in _TAP_AND_FLICK_SOUNDS:
            notes.append({"type": "Single", **node, "flick": sound in _FLICKS})
        else:
            match = _SLIDE.fullmatch(sound)
            if match is None:
                raise ValueError(f"第 {float(beat):g} 拍的音符不受支持: {sound}")
            end, flick, stream = match.groups()
            if not end:
                slides.setdefault(stream, []).append(node)
                continue
            node["flick"] = bool(flick)
            if stream in slides:
                nodes = slides.pop(stream) + [node]
                notes.append({"type": "Slide", "connections": nodes})
                previous_slides[stream] = nodes
            elif join_butai and (stream, beat, lane) == ("b", 124, 3):
                previous_slides[stream].append(node)
                _LOGGER.info("按连续滑键处理《舞台に立って》EXPERT 的第 123.5–124 拍")
            else:
                raise ValueError(f"第 {float(beat):g} 拍的滑键结束没有起点: {sound}")
    if holds or slides:
        raise ValueError("谱面结束时仍有长按或滑键没有收尾")
    if not notes:
        raise ValueError("谱面没有可演奏的音符")

    # Chart needs the full tempo map before calculating any slide node's time.
    bpms = [{"type": "BPM", "beat": float(beat), "bpm": bpm} for beat, bpm in sorted(tempo.items())]
    notes.sort(key=lambda note: note["connections"][0]["beat"] if "connections" in note else note["beat"])
    return bpms + notes
