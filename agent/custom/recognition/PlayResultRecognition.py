import logging

from maa.context import Context
from maa.custom_recognition import CustomRecognition


logger = logging.getLogger("PlayResultRecognition")


class PlayResultRecognition(CustomRecognition):
    FIELDS = ("score", "maxcombo", "perfect", "great", "good", "bad", "miss", "fast", "slow")

    def analyze(self, context: Context, argv: CustomRecognition.AnalyzeArg):
        result = {}
        for field in self.FIELDS:
            recognition = context.run_recognition(f"PlayResult{field.capitalize()}", argv.image)
            match = recognition.best_result if recognition else None
            result[field] = int(match.text) if match else -1

        logger.debug("Play result: %s", result)
        return self.AnalyzeResult([0, 0, 0, 0], result)
