"""
演出结算数据识别
OCR 读取结算画面中的 9 项关键数据：score, maxcombo, perfect, great, good, bad, miss, fast, slow。
返回 JSON 字符串供 SavePlayResult 保存。
"""
import json
import logging
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from typing import Union, Optional
from maa.define import RectType


class PlayResultRecognition(CustomRecognition):
    # 结算画面中各数据项的 ROI 区域（基于 1280x720 基准分辨率）
    TYPE_ROI_MAP = {
        "score":    [1028, 192, 144, 35],
        "maxcombo": [1009, 391,  91, 28],
        "perfect":  [ 829, 282,  90, 28],
        "great":    [ 828, 322,  91, 27],
        "good":     [ 829, 363,  91, 27],
        "bad":      [ 829, 401,  90, 27],
        "miss":     [ 830, 438,  91, 28],
        "fast":     [1088, 283,  90, 27],
        "slow":     [1088, 323,  91, 28],
    }

    def analyze(
        self, context: Context, argv: CustomRecognition.AnalyzeArg
    ) -> Union[CustomRecognition.AnalyzeResult, Optional[RectType]]:
        logger = logging.getLogger("PlayResultRecognition")

        result: dict = {}

        pipeline = {
            f"_PlayResultRecognition_ocr_{type_}": {
                "recognition": "OCR",
                "only_rec": True,
                "roi": roi,
            }
            for type_, roi in self.TYPE_ROI_MAP.items()
        }

        for type_ in self.TYPE_ROI_MAP:
            pipeline_key = f"_PlayResultRecognition_ocr_{type_}"
            try:
                ocr_text = context.run_recognition(
                    pipeline_key,
                    argv.image,
                    pipeline,
                ).best_result.text
                type_result = int(ocr_text.replace(",", "").replace(" ", ""))
            except (ValueError, AttributeError):
                type_result = -1
            result[type_] = type_result

        logger.debug(f"Play result: {result}")
        return CustomRecognition.AnalyzeResult([0, 0, 0, 0], json.dumps(result))
