from maa.custom_recognition import CustomRecognition
from maa.context import Context
from maa.define import RectType
from typing import Union, Optional
import logging
import json
from fuzzywuzzy import process as fzwzprocess

from ..utils.StateCore import global_state

class SongRecognition(CustomRecognition):
    def analyze(
        self, context: Context, argv: CustomRecognition.AnalyzeArg
    ) -> Union[CustomRecognition.AnalyzeResult, Optional[RectType]]:
        logger = logging.getLogger("SongRecognition")
        
        # ROI 优先级：管线 argv.roi > global_state 后备
        if argv.roi:
            # 必须转换为 list 以保证 json 序列化成功
            roi = [argv.roi.x, argv.roi.y, argv.roi.w, argv.roi.h]
        elif global_state.roi:
            roi = global_state.roi
        else:
            logger.error("未配置 ROI，请在 pipeline JSON 中为 SongRecognition 节点添加 roi 字段")
            return self.AnalyzeResult(None, "")

        live_mode = global_state.live_mode
        is_full_song = global_state.is_full_song
        is_high_difficulty = global_state.is_high_difficulty
        difficulty = global_state.difficulty

        models_to_try = ["ppocr_v5/zh_cn-server", ""]

        def fuzzy_match_song(name):
            return fzwzprocess.extractOne(name, list(global_state.all_song_name_indexes.keys()))

        def check_song_available(name, id_, diff, mode, is_full):
            if name.startswith("[FULL]") and not is_full:
                return False
            if mode == "full_auto":
                if id_:
                    attempt_count = global_state.song_attempt_count_dict.get(id_, 0)
                    max_attempt_count = global_state.max_attempt_count
                    if attempt_count >= max_attempt_count:
                        logger.warning(f"Song '{name}' has reached max attempt count ({attempt_count}).")
                        return False

                    not_fc_count = global_state.not_fc_count_dict.get(id_, 0)
                    max_not_fc = global_state.max_continuous_not_fc_count
                    if not_fc_count >= max_not_fc:
                        logger.warning(f"Song '{name}' has reached the non-FC limit ({not_fc_count}).")
                        global_state.not_fc_count_dict[id_] = 0
                        return False
            return True

        def match(model=None):
            pipeline = {
                "_ocr_song": {
                    "recognition": "OCR",
                    "only_rec": True,
                    "roi": roi,
                },
            }
            if model:
                pipeline["_ocr_song"]["model"] = model
            try:
                logger.info(f"Pipeline: {pipeline}")
                logger.info(f"Type of roi: {type(roi)}")
                
                ocr_result = context.run_recognition("_ocr_song", argv.image, pipeline)
                if not ocr_result or not ocr_result.best_result:
                    return None
                    
                ocr_text = ocr_result.best_result.text
                logger.info(f"OCR ({model or 'default'}) raw text: '{ocr_text}'")

                if live_mode not in ["medley_single", "free_single"] and "full" in ocr_text.lower():
                    return 100

                match_result = fuzzy_match_song(ocr_text)
                if not match_result:
                    return None

                matched_name, raw_score = match_result[0], match_result[1]

                len_ocr = len(ocr_text)
                len_matched = len(matched_name)
                length_ratio = min(len_ocr, len_matched) / max(len_ocr, len_matched) if len_ocr and len_matched else 0
                adjusted_score = raw_score * length_ratio

                logger.info(
                    f"Adjusted score for '{matched_name}' with length penalty ({model or 'default'}): "
                    f"{adjusted_score:.2f} (raw: {raw_score}, len_ratio: {length_ratio:.2f})"
                )
                return (matched_name, adjusted_score)

            except Exception as e:
                logger.error(f"OCR ({model or 'default'}) execution failed: {e}")
                return None

        results = [m for m in [match(model) for model in models_to_try] if m]

        if not results or 100 in results:
            return self.AnalyzeResult(None, "")

        best_match = max(results, key=lambda x: x[1])

        if best_match and best_match[1] > 50:
            matched_song_name = best_match[0]
            adjusted_confidence = best_match[1]

            if live_mode == "free_single":
                if is_full_song:
                    matched_song_name = "[FULL] " + matched_song_name
                elif is_high_difficulty:
                    matched_song_name = "[超高難易度 SPECIAL] " + matched_song_name

            song_id = global_state.all_song_name_indexes.get(best_match[0])

            if not check_song_available(matched_song_name, song_id, difficulty, live_mode, is_full_song):
                return self.AnalyzeResult(None, "")

            logger.info(f"Song recognised: '{matched_song_name}' (Adjusted Confidence: {adjusted_confidence:.2f}%)")
            
            # 保存当前识别出的歌曲信息到全局状态中，供后续 Action 使用
            global_state.current_song_name = matched_song_name
            global_state.current_song_id = song_id
            
            return self.AnalyzeResult(roi, matched_song_name)

        return self.AnalyzeResult(None, "")
