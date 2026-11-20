import json
import logging

from fuzzywuzzy import process
from maa.context import Context
from maa.custom_recognition import CustomRecognition

from ..utils.StateCore import global_state


logger = logging.getLogger("SongRecognition")


class SongRecognition(CustomRecognition):
    def analyze(self, context: Context, argv: CustomRecognition.AnalyzeArg):
        params = json.loads(argv.custom_recognition_param or "{}") or {}
        ocr_node = params.get("ocr_node", "PlaySongTitle")
        height, width = argv.image.shape[:2]
        roi = list(argv.roi) if argv.roi else None
        has_region = roi and roi[2] > 0 and roi[3] > 0 and roi != [0, 0, width, height]

        override = {}
        if has_region:
            override = {ocr_node: {"roi": roi}}
        elif ocr_node == "PlaySongTitle":
            if not global_state.roi:
                logger.warning("曲名识别缺少 ROI，请配置识别区域或指定 OCR 节点。")
                return None
            override = {ocr_node: {"roi": global_state.roi}}

        recognition = context.run_recognition(ocr_node, argv.image, override)
        if not recognition or not recognition.best_result:
            return None
        text = recognition.best_result.text
        mode = global_state.live_mode
        if mode not in ("medley_single", "free_single") and "full" in text.lower():
            return None

        try:
            song_ids = global_state.all_song_name_indexes
            match = process.extractOne(text, song_ids.keys())
        except Exception:
            logger.exception("无法匹配曲库")
            return None
        if not match:
            return None

        name, score = match
        adjusted_score = score * min(len(text), len(name)) / max(len(text), len(name))
        if adjusted_score <= 50:
            return None

        song_id = song_ids[name]
        if mode == "free_single":
            if global_state.is_full_song:
                name = "[FULL] " + name
            elif global_state.is_high_difficulty:
                name = "[超高難易度 SPECIAL] " + name

        if name.startswith("[FULL]") and not global_state.is_full_song:
            return None
        if mode == "full_auto":
            if global_state.song_attempt_count_dict.get(song_id, 0) >= global_state.max_attempt_count:
                logger.warning("歌曲 %r 已达尝试上限", name)
                return None
            if global_state.not_fc_count_dict.get(song_id, 0) >= global_state.max_continuous_not_fc_count:
                logger.warning("歌曲 %r 已达未 Full Combo 上限", name)
                global_state.not_fc_count_dict[song_id] = 0
                return None

        global_state.current_song_name = name
        global_state.current_song_id = song_id
        logger.info("曲名识别为 %r（%.2f%%）", name, adjusted_score)
        return self.AnalyzeResult(recognition.best_result.box, name)
