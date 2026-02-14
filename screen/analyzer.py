import io
import base64
import logging
import time

from openai import OpenAI, RateLimitError
from pydantic import BaseModel
from PIL import Image

logger = logging.getLogger(__name__)


class ScreenAnalysis(BaseModel):
    """Structured output from Vision API for a captured screen."""
    slide_title: str
    key_topics: list[str]
    key_terms: list[str]
    medical_concepts: list[str]
    text_content: str
    language: str
    summary: str
    has_diagram: bool
    diagram_description: str | None = None
    korean_to_english: dict[str, str] = {}


SCREEN_ANALYSIS_PROMPT = """You are a medical education expert analyzing a captured lecture screen.
Extract the following information and return as JSON:

1. "slide_title": The title or header visible on screen
2. "key_topics": Main topics covered (2-5 items)
3. "key_terms": Important technical/medical terms visible on screen.
   CRITICAL: If a term is written in English on the screen, return it in English.
   If written in Korean, return it in Korean. Preserve the original language exactly.
4. "medical_concepts": Specific medical concepts including:
   - Disease names, Drug names, Anatomical structures, Pathological mechanisms,
     Lab values, diagnostic criteria, Clinical findings
5. "text_content": ALL readable text on the screen, transcribed exactly as shown.
   Include bullet points, labels, captions — every piece of text visible.
   CRITICAL: Preserve original language — English text as English, Korean as Korean.
6. "language": Primary language - "ko", "en", or "mixed"
7. "summary": 2-3 sentence summary of the screen content
8. "has_diagram": Whether there's a diagram, figure, or image (true/false)
9. "diagram_description": Brief description if diagram exists, null otherwise
10. "korean_to_english": A dictionary mapping Korean phonetic transliterations to their
    original English terms. For EVERY English term on the screen, provide how a Korean
    speaker would phonetically say it in Korean (한글 음차) as the key, and the actual
    English term as the value. Include ALL variations.
    Examples:
    - "아웃컴" → "outcome", "메타 아날리시스" → "meta-analysis"
    - "프리텀" → "preterm", "딜리버리" → "delivery"
    - "트리플렛" → "triplet", "코호트" → "cohort"
    - "싱글톤" → "singleton", "미스캐리지" → "miscarriage"
    - "리덕션" → "reduction", "케이스" → "case"
    Be thorough — include common medical/academic English terms visible on screen.
    Also include abbreviations: "씨티" → "CT", "엠알아이" → "MRI", etc.

Respond in the same language as the screen content.
Preserve all medical terminology exactly as written on screen."""


class ScreenAnalyzer:
    """Uses OpenAI Vision API to analyze captured screen images."""

    def __init__(self, config):
        self.client = OpenAI(
            api_key=config.openai_api_key,
            max_retries=2,
        )
        self.model = config.openai_model_vision

    def analyze(self, image: Image.Image) -> ScreenAnalysis:
        """Analyze a screen capture with OpenAI Vision."""
        img = image
        if img.width > 1024:
            ratio = 1024 / img.width
            img = img.resize((1024, int(img.height * ratio)), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        base64_image = base64.b64encode(buf.getvalue()).decode("utf-8")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": SCREEN_ANALYSIS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "auto",
                            },
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=2000,
        )

        result_text = response.choices[0].message.content
        return ScreenAnalysis.model_validate_json(result_text)

    def analyze_with_fallback(self, image: Image.Image) -> ScreenAnalysis:
        """Analyze with retry on rate limit and graceful fallback on failure."""
        for attempt in range(5):
            try:
                return self.analyze(image)
            except RateLimitError as e:
                if attempt < 4:
                    delay = 10 * (2 ** attempt)
                    logger.warning(
                        "Rate limited (attempt %d/5), waiting %ds...",
                        attempt + 1, delay,
                    )
                    time.sleep(delay)
                    continue
                logger.warning("Rate limit persists after 5 attempts: %s", e)
            except Exception as e:
                logger.warning("Screen analysis failed: %s. Using empty fallback.", e)
                break

        return ScreenAnalysis(
            slide_title="(Analysis failed)",
            key_topics=[],
            key_terms=[],
            medical_concepts=[],
            text_content="",
            language="mixed",
            summary="",
            has_diagram=False,
        )
