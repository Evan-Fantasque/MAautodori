"""
LiveBoost 火焰数量识别
OCR 识别画面右上角的火焰数量（格式如 "3/10"），供 HandleLiveBoost 判断是否需要停止任务。
"""
import re
import logging
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from typing import Union, Optional
from maa.define import RectType


class LiveBoostRecognition(CustomRecognition):
    def analyze(
        self, context: Context, argv: CustomRecognition.AnalyzeArg
    ) -> Union[CustomRecognition.AnalyzeResult, Optional[RectType]]:
        logger = logging.getLogger("LiveBoostRecognition")

        roi = [979, 30, 61, 20]

        pipeline = {
            "live_boost_enough_ocr": {
                "recognition": "OCR",
                "only_rec": True,
                "roi": roi,
            },
        }
        try:
            ocr_text = context.run_recognition(
                "live_boost_enough_ocr",
                argv.image,
                pipeline,
            ).best_result.text

            logger.debug(f"Live boost OCR result: '{ocr_text}'")

            # 正则提取 "N/" 格式中的数字
            pattern = r"^\s*(\d+)\s*/"
            match = re.match(pattern, ocr_text.replace(" ", ""))

            if match:
                live_boost = int(match.group(1))
            else:
                live_boost = -1

            logger.debug(f"Live boost: {live_boost}")
            return CustomRecognition.AnalyzeResult(roi, str(live_boost))

        except Exception as e:
            logger.error(f"LiveBoostRecognition failed: {e}")
            return CustomRecognition.AnalyzeResult(roi, "-1")
