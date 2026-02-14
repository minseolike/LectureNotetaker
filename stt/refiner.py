"""Transcript refiner: uses OpenAI to clean up STT output.

Takes raw transcript + slide screen context and produces refined text where:
- Korean phonetic transliterations → actual English words/names
- Filler words and repetitions cleaned up
- Medical/academic terminology corrected using screen context
"""

import logging
import threading
import time

from anthropic import Anthropic
from openai import OpenAI

logger = logging.getLogger(__name__)

REFINE_PROMPT = """You are a transcript refiner for a Korean medical lecture.

Your job is to clean up the transcript so it reads like polished lecture notes:
convert transliterations to English, normalize numbers and units, and use slide
context to ensure technical terms are accurate.

═══ 1. TRANSLITERATION → ENGLISH ═══

Convert ONLY when the speaker is PRONOUNCING AN ENGLISH WORD in Korean phonetics.

CONVERT (English words spoken in Korean phonetics):
  "오스테오포로시스" → "osteoporosis", "페소피지올로지" → "pathophysiology"
  "메타 아날리시스" → "meta-analysis", "씨티엑스" → "CTX"
  "엠아라이" → "MRI", "피밸류" → "p-value", "아웃컴" → "outcome"
  "디엑사" → "DEXA", "비스포스포네이트" → "bisphosphonate"

KEEP as Korean (native Korean words, NOT transliterations):
  골밀도, 골표지자, 골다공증, 파골세포, 조골세포, 골재형성, 골강도, 골절,
  혈중 칼슘, 칼슘 대사
  Common loanwords: 데이터, 그룹, 리스크, 케이스, 레벨

The test: Is the speaker TRYING TO SAY an English word using Korean sounds?
  YES → convert.  NO (standard Korean word) → keep as Korean.

═══ 2. NUMBERS & UNITS ═══

Convert spoken Korean numbers and units to digits and standard notation.
  "영 점 오" → "0.5", "이십 오" → "25", "삼십 퍼센트" → "30%"
  "백 이십" → "120", "천 오백" → "1500", "일만" → "10000"
  "밀리미터" → "mm", "센티미터" → "cm", "나노그램" → "ng"
  "밀리리터" → "mL", "마이크로그램" → "μg", "킬로그램" → "kg"
  "나노몰" → "nmol", "피코몰" → "pmol"
  Combine: "오 밀리그램" → "5mg", "이십 나노그램 퍼 밀리리터" → "20ng/mL"

═══ 3. SLIDE-CONTEXT TERM MATCHING ═══

When the slide context contains specific English terms (from key_terms,
medical_concepts, or korean_to_english mappings), and the speaker is clearly
referring to the same concept, use the slide's exact spelling.
  - Speaker says "티 스코어" and slide shows "T-score" → use "T-score"
  - Speaker says "랭크 리간드" and slide shows "RANKL" → use "RANKL"
  - Speaker says "디노수맙" and slide shows "denosumab" → use "denosumab"
Only apply this when confident the speaker is referring to the slide term.

═══ 4. FIX GARBLED/MISSPELLED ENGLISH ═══

The STT sometimes outputs badly garbled or misspelled English instead of
proper terms. Use slide context and medical knowledge to correct these:
  "igemedaity" → "IgE mediated", "andretix1" → "dendritic"
  "thelper2셀" → "T-helper 2 세포", "thelper" → "T-helper"
  "glumerollon appritis" → "glomerulonephritis"
  "immediatedimmediatedhypersensitivity" → "immediate/mediated hypersensitivity"
  "phasema valiss" → phase (or match to slide context)

If English text appears concatenated without spaces, add proper spacing:
  "Firstexposure" → "First exposure"
  "B셀이IGE를프로덕션합니다" → "B 세포가 IgE를 production합니다"

═══ 5. CLEANUP ═══

- Fix obviously misheard terms using slide context as spelling reference
- Remove stutters or repeated words

═══ NEVER DO ═══
- NEVER add definitions, explanations, or descriptions from the slide
- NEVER expand abbreviations unless the speaker actually said the full form
- NEVER add sentences, numbers, or facts from the slide that were not spoken
- NEVER make the output significantly longer than the input
- NEVER include slide text content that wasn't spoken
- NEVER convert native Korean medical terms to English

The slide context is ONLY for spelling reference — use it to identify what word
the speaker was trying to say, NOT to add information they didn't say.

═══ OUTPUT RULES ═══
- Output the refined transcript ONLY. No explanations, no labels.
- The output must be approximately the same length as the input.
- If the input is already clean, return it EXACTLY as-is."""


FINALIZE_PROMPT = """You are a final proofreader for Korean medical lecture notes.

The text below was transcribed and refined in small batches. Do a LIGHT final
pass to fix punctuation, flow, and contextually nonsensical parts.

═══ FIX THESE ═══
1. STRAY PERIODS: Remove periods (.) that appear mid-sentence or at unnatural
   locations (e.g. "골밀도가. 감소하면" → "골밀도가 감소하면")
2. BATCH JOINS: Where two batches were joined, smooth if it reads unnaturally
   (e.g. missing space, broken sentence, dangling punctuation)
3. BAD PUNCTUATION: Double periods, comma before period, random punctuation
4. CONTEXTUAL ERRORS: If a word or phrase is clearly wrong given the slide
   context and surrounding medical content, correct it
   (e.g. wrong term from STT mishearing that slipped through refinement)

═══ DO NOT ═══
- Do NOT add new information or content that wasn't spoken
- Do NOT significantly rephrase or restructure sentences
- Do NOT make the output much longer than the input
- If a section reads fine, leave it as-is

Output the corrected text ONLY. No explanations."""


POLISH_PROMPT = """너는 의대 교수이자 의학 강의 노트 편집자야.

아래 텍스트는 의학 강의의 실시간 STT 음성 인식 결과물이야. 이걸 의대생이 공부하기
좋은 깔끔한 강의 노트로 다듬어줘.

═══ 1. 의학 지식을 활용한 교정 ═══

STT 오류를 의학 맥락으로 교정:
- 잘못된 용어 → 올바른 의학 용어 (예: "FCR 리셉터" → "FcεRI 수용체")
- 불완전한 설명 → 의학적으로 정확하게 보완
- 잘못 인식된 영어 → 올바른 의학 용어로 수정
- 의학적으로 말이 안 되는 부분이 있으면 ⚠️로 표시하고 올바른 해석 제시

═══ 2. 문단 구조화 ═══

벽처럼 이어진 텍스트를 논리적 문단으로 분리:
- 주제가 바뀔 때 (예: Type 1 → Type 2) 새 문단 시작
- 각 문단은 하나의 coherent한 개념을 다룸
- 문단 사이에 빈 줄(\\n\\n)로 구분

═══ 3. 구어체 → 문어체 변환 ═══

- 구어체 표현 제거: "크게 보면", "이거는 뭐냐면", "그래서 결국"
- 모든 문장 끝을 간결체로: ~음, ~슴, ~임, ~됨, ~함
  "감소합니다" → "감소함", "해야 합니다" → "필요함"
- 불필요한 반복이나 말더듬만 제거하고, 강의 설명·예시·부연은 모두 유지
- 강의에서 말한 내용을 요약하거나 축약하지 말 것 — 문체만 바꿀 것

═══ 4. 가독성 향상 ═══

- 긴 문장은 자연스러운 지점에서 분리
- 일관된 의학 용어 사용
- 영어 의학 용어는 그대로 유지 (DEXA, T-score, IgE 등)
- 필요하면 길어져도 됨 — 내용 보존이 간결함보다 중요

═══ 하지 말 것 ═══
- 강의에서 언급하지 않은 완전히 새로운 주제를 추가하지 말 것
- 강의 내용을 삭제하거나 요약하지 말 것 — 설명, 예시, 부연 모두 유지
- 여러 문장을 하나로 압축하지 말 것

═══ 출력 ═══
교정된 노트만 출력. 설명이나 라벨 없이."""


SUMMARY_PROMPT = """You are a note summarizer for Korean medical lectures.

Given the transcript of what the lecturer said during one slide, produce
concise bullet-point summary notes in Korean 간결체 (~슴, ~음, ~임, ~됨 endings).

═══ RULES ═══
- Each bullet point: one key fact or concept from the transcript
- Use 간결체: "골밀도가 감소함", "T-score -2.5 이하에서 진단됨"
- Keep English terms that appear in the transcript as-is (e.g. DEXA, T-score)
- 3-7 bullet points per slide (fewer if short transcript)
- Omit filler, repetition, tangents — only key information
- Each bullet should be self-contained and concise (one line)
- If the transcript is too short or empty, return nothing

Output bullet points ONLY, one per line. No numbering, no bullet markers,
no headers, no explanations."""


class TranscriptRefiner:
    """Refines transcript segments using OpenAI, with slide context.

    Uses Anthropic Claude for the polish step (PDF export) if configured.
    """

    def __init__(self, config):
        self.client = OpenAI(api_key=config.openai_api_key)
        self.model = config.openai_model_writer
        self._lock = threading.Lock()

        if config.anthropic_api_key:
            self.anthropic = Anthropic(api_key=config.anthropic_api_key)
            self.anthropic_model = config.anthropic_model
        else:
            self.anthropic = None
            self.anthropic_model = None

    def refine(self, transcript: str, screen_context: str = "") -> str:
        """Refine a transcript segment using LLM."""
        if not transcript.strip():
            return transcript

        user_msg = f"Transcript:\n{transcript}"
        if screen_context:
            user_msg = f"Slide context:\n{screen_context}\n\n{user_msg}"

        try:
            input_len = len(transcript)
            max_tok = min(1000, max(200, int(input_len * 1.5)))

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": REFINE_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.1,
                max_tokens=max_tok,
            )
            result = response.choices[0].message.content.strip()
            if not result:
                return transcript

            if len(result) > len(transcript) * 2:
                logger.warning(
                    "Refiner hallucination detected: input=%d chars, output=%d chars. Using original.",
                    len(transcript), len(result),
                )
                return transcript

            return result
        except Exception as e:
            logger.warning("Transcript refinement failed: %s", e)
            return transcript

    def finalize(self, transcript: str, screen_context: str = "") -> str:
        """Final light proofreading pass over a full slide's refined text."""
        if not transcript.strip():
            return transcript

        user_msg = f"Text:\n{transcript}"
        if screen_context:
            user_msg = f"Slide context:\n{screen_context}\n\n{user_msg}"

        try:
            input_len = len(transcript)
            max_tok = min(2000, max(200, int(input_len * 1.3)))

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": FINALIZE_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.15,
                max_tokens=max_tok,
            )
            result = response.choices[0].message.content.strip()
            if not result:
                return transcript

            if len(result) > len(transcript) * 1.5:
                logger.warning(
                    "Finalize output too long: input=%d, output=%d. Using original.",
                    len(transcript), len(result),
                )
                return transcript

            return result
        except Exception as e:
            logger.warning("Finalize failed: %s", e)
            return transcript

    def polish(self, transcript: str, screen_context: str = "") -> str:
        """Polish refined transcript using Claude for medical-grade notes."""
        if not transcript.strip():
            return transcript

        user_msg = transcript
        if screen_context:
            user_msg = f"[슬라이드 context]\n{screen_context}\n\n[강의 transcript]\n{user_msg}"

        try:
            input_len = len(transcript)
            max_tok = min(8192, max(500, int(input_len * 2)))

            if self.anthropic:
                response = self.anthropic.messages.create(
                    model=self.anthropic_model,
                    system=POLISH_PROMPT,
                    messages=[{"role": "user", "content": user_msg}],
                    temperature=0.3,
                    max_tokens=max_tok,
                )
                result = response.content[0].text.strip()
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": POLISH_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.3,
                    max_tokens=max_tok,
                )
                result = response.choices[0].message.content.strip()

            if not result:
                return transcript

            if len(result) > len(transcript) * 2.5:
                logger.warning(
                    "Polish output too long: input=%d, output=%d. Using original.",
                    len(transcript), len(result),
                )
                return transcript

            return result
        except Exception as e:
            logger.warning("Polish failed: %s", e)
            return transcript

    def summarize(self, transcript: str, screen_context: str = "") -> list[str]:
        """Generate bullet-point summary from refined transcript."""
        if not transcript.strip():
            return []

        user_msg = f"Transcript:\n{transcript}"
        if screen_context:
            user_msg = f"Slide context:\n{screen_context}\n\n{user_msg}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SUMMARY_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
                max_tokens=500,
            )
            result = response.choices[0].message.content.strip()
            if not result:
                return []

            bullets = [line.strip().lstrip("•-·* ") for line in result.split("\n")]
            bullets = [b for b in bullets if b]
            return bullets
        except Exception as e:
            logger.warning("Summarize failed: %s", e)
            return []


class RefinerBuffer:
    """Buffers transcript segments and flushes them to the refiner in batches."""

    def __init__(self, refiner: TranscriptRefiner, on_refined: callable,
                 get_context: callable, max_segments: int = 2,
                 flush_timeout_sec: float = 4.0):
        self.refiner = refiner
        self.on_refined = on_refined
        self.get_context = get_context
        self.max_segments = max_segments
        self.flush_timeout_sec = flush_timeout_sec

        self._buffer: list[tuple[str, int]] = []
        self._lock = threading.Lock()
        self._first_buffered_at = 0.0
        self._timer: threading.Timer | None = None
        self._pending_count = 0
        self._pending_lock = threading.Lock()
        self._all_done = threading.Event()
        self._all_done.set()

    def add(self, text: str, slide_idx: int):
        """Add a transcript segment to the buffer."""
        with self._lock:
            if self._buffer and self._buffer[-1][1] != slide_idx:
                self._flush_locked()

            self._buffer.append((text, slide_idx))
            if len(self._buffer) == 1:
                self._first_buffered_at = time.monotonic()
                self._timer = threading.Timer(
                    self.flush_timeout_sec, self._flush_on_timeout,
                )
                self._timer.daemon = True
                self._timer.start()

            if len(self._buffer) >= self.max_segments:
                self._flush_locked()

    def _flush_on_timeout(self):
        """Called by timer thread when flush timeout expires."""
        with self._lock:
            if self._buffer:
                self._flush_locked()

    def _flush_locked(self):
        """Flush buffer while lock is held."""
        if not self._buffer:
            return

        segments = list(self._buffer)
        self._buffer.clear()
        self._first_buffered_at = 0.0
        if self._timer:
            self._timer.cancel()
            self._timer = None

        with self._pending_lock:
            self._pending_count += 1
            self._all_done.clear()

        threading.Thread(
            target=self._do_flush, args=(segments,), daemon=True,
        ).start()

    def _do_flush(self, segments: list[tuple[str, int]]):
        """Refine a batch of segments and deliver result."""
        slide_idx = segments[-1][1]
        combined = " ".join(text for text, _ in segments)

        try:
            context = self.get_context(slide_idx, combined)
            refined = self.refiner.refine(combined, context)
            self.on_refined(refined, slide_idx)
        except Exception as e:
            logger.warning("Batch refine failed: %s", e)
            self.on_refined(combined, slide_idx)
        finally:
            with self._pending_lock:
                self._pending_count -= 1
                if self._pending_count == 0:
                    self._all_done.set()

    def flush(self):
        """Force flush any remaining buffer (e.g., on stop)."""
        with self._lock:
            if self._buffer:
                self._flush_locked()

    def wait_pending(self, timeout: float = 15.0) -> bool:
        """Wait for all in-flight refine operations to complete."""
        return self._all_done.wait(timeout=timeout)
