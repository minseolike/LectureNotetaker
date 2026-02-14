import re
import logging

logger = logging.getLogger(__name__)

_KOREAN_CORRECTIONS = {
    "골프지자": "골표지자",
    "골프의자": "골표지자",
    "골프이자": "골표지자",
    "골프골프이자": "골표지자",
    "골프 지자": "골표지자",
    "골프표지자": "골표지자",
    "골재 형성": "골재형성",
    "골 강도": "골강도",
    "골밀 도": "골밀도",
    "골 질": "골질",
}


class TranscriptPostProcessor:
    """Lightweight Korean STT correction.

    Only fixes Korean→Korean misrecognitions (e.g. 골프지자→골표지자).
    All English term conversion is handled by the LLM refiner with slide context.
    """

    def __init__(self):
        self._ko_corrections: list[tuple[re.Pattern, str]] = []
        for wrong, correct in sorted(_KOREAN_CORRECTIONS.items(),
                                      key=lambda x: len(x[0]), reverse=True):
            self._ko_corrections.append(
                (re.compile(re.escape(wrong)), correct)
            )

    def process(self, text: str) -> str:
        """Apply Korean→Korean STT corrections only.

        Korean→English conversion is handled by the LLM refiner.
        """
        for pattern, correct in self._ko_corrections:
            text = pattern.sub(correct, text)
        return text
