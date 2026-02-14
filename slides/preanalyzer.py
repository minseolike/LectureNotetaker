"""Pre-analyze slide PDF before lecture: extract pages, analyze with Vision API,
build korean_to_english mappings and term lists upfront.

Caches analysis results to disk so subsequent loads of the same PDF skip Vision API.
"""

import hashlib
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone

import pymupdf
import imagehash
from PIL import Image

from screen.analyzer import ScreenAnalyzer, ScreenAnalysis

logger = logging.getLogger(__name__)


@dataclass
class PreAnalyzedSlide:
    """Data for a single pre-analyzed slide."""
    page_num: int
    image: Image.Image
    phash: imagehash.ImageHash
    analysis: ScreenAnalysis | None = None


class SlidePreAnalyzer:
    """Loads a PDF, extracts pages as images, analyzes all slides upfront.

    Analysis results are cached to ``{pdf_stem}.cache.json`` next to the PDF.
    On subsequent loads of the same PDF (matched by SHA-256 hash), the cache
    is used and Vision API calls are skipped entirely.
    """

    def __init__(self, config):
        self.analyzer = ScreenAnalyzer(config)
        self.slides: list[PreAnalyzedSlide] = []
        self.korean_to_english: dict[str, str] = {}
        self.all_terms: list[str] = []
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded and len(self.slides) > 0

    @property
    def slide_count(self) -> int:
        return len(self.slides)

    @staticmethod
    def _compute_pdf_hash(pdf_path: str) -> str:
        """Compute SHA-256 hash of a PDF file."""
        h = hashlib.sha256()
        with open(pdf_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _cache_path(pdf_path: str) -> str:
        """Return cache file path for a given PDF."""
        stem, _ = os.path.splitext(pdf_path)
        return stem + ".cache.json"

    def _save_cache(self, pdf_path: str):
        """Save current analysis results to a JSON cache file."""
        cache_data = {
            "pdf_hash": self._compute_pdf_hash(pdf_path),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "slides": [],
        }
        for slide in self.slides:
            entry = {
                "page_num": slide.page_num,
                "phash": str(slide.phash),
                "analysis": slide.analysis.model_dump() if slide.analysis else None,
            }
            cache_data["slides"].append(entry)

        cache_file = self._cache_path(pdf_path)
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=1)
            logger.info("Saved analysis cache to %s", cache_file)
        except Exception as e:
            logger.warning("Failed to save cache: %s", e)

    def _load_cache(self, pdf_path: str, images: list[Image.Image]) -> bool:
        """Try to load analysis from cache. Returns True if cache is valid.

        On success, populates self.slides with cached phash/analysis + fresh images.
        """
        cache_file = self._cache_path(pdf_path)
        if not os.path.exists(cache_file):
            return False

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
        except Exception as e:
            logger.warning("Failed to read cache file: %s", e)
            return False

        current_hash = self._compute_pdf_hash(pdf_path)
        if cache_data.get("pdf_hash") != current_hash:
            logger.info("PDF changed since cache was created, re-analyzing")
            return False

        cached_slides = cache_data.get("slides", [])
        if len(cached_slides) != len(images):
            logger.info("Page count mismatch (cache=%d, PDF=%d), re-analyzing",
                        len(cached_slides), len(images))
            return False

        for entry, img in zip(cached_slides, images):
            page_num = entry["page_num"]
            phash = imagehash.hex_to_hash(entry["phash"])
            analysis = None
            if entry.get("analysis"):
                analysis = ScreenAnalysis.model_validate(entry["analysis"])

            slide = PreAnalyzedSlide(
                page_num=page_num,
                image=img,
                phash=phash,
                analysis=analysis,
            )
            self.slides.append(slide)

            if analysis and analysis.korean_to_english:
                self.korean_to_english.update(analysis.korean_to_english)
            if analysis:
                self.all_terms.extend(analysis.key_terms)
                self.all_terms.extend(analysis.medical_concepts)

        self.all_terms = list(dict.fromkeys(self.all_terms))

        logger.info("Loaded analysis cache: %d slides from %s",
                     len(self.slides), cache_file)
        return True

    def extract_pages(self, pdf_path: str, dpi: int = 150) -> list[Image.Image]:
        """Extract all pages from a PDF as PIL Images."""
        doc = pymupdf.open(pdf_path)
        images = []
        zoom = dpi / 72.0
        mat = pymupdf.Matrix(zoom, zoom)

        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append(img)

        doc.close()
        logger.info("Extracted %d pages from PDF: %s", len(images), pdf_path)
        return images

    def load_and_analyze(self, pdf_path: str, on_progress: callable = None):
        """Extract PDF pages and analyze each with Vision API.

        If a valid cache exists for this PDF, skips Vision API calls entirely.

        Args:
            pdf_path: Path to the slide PDF
            on_progress: callback(current, total, status_text) for progress updates
        """
        self.slides.clear()
        self.korean_to_english.clear()
        self.all_terms.clear()
        self._loaded = False

        if on_progress:
            on_progress(0, 0, "Extracting PDF pages...")
        images = self.extract_pages(pdf_path)

        if not images:
            logger.warning("No pages found in PDF: %s", pdf_path)
            return

        total = len(images)

        if on_progress:
            on_progress(0, total, "Checking for cached analysis...")
        if self._load_cache(pdf_path, images):
            self._loaded = True
            if on_progress:
                on_progress(total, total,
                            f"Loaded from cache! {total} slides, "
                            f"{len(self.korean_to_english)} Korean-English mappings.")
            return

        results: list[PreAnalyzedSlide] = [None] * total
        completed = 0

        rate_lock = threading.Lock()
        last_api_time = [0.0]

        def analyze_one(idx: int, img: Image.Image) -> tuple[int, PreAnalyzedSlide]:
            with rate_lock:
                now = time.monotonic()
                min_next = last_api_time[0] + 5.0
                wait = min_next - now
                last_api_time[0] = max(now, min_next)
            if wait > 0:
                time.sleep(wait)

            phash = imagehash.phash(img)
            try:
                analysis = self.analyzer.analyze_with_fallback(img)
            except Exception as e:
                logger.error("Failed to analyze slide %d: %s", idx + 1, e)
                analysis = None
            return idx, PreAnalyzedSlide(
                page_num=idx, image=img, phash=phash, analysis=analysis,
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(analyze_one, i, img): i
                for i, img in enumerate(images)
            }
            for future in as_completed(futures):
                idx, slide = future.result()
                results[idx] = slide
                completed += 1
                if on_progress:
                    on_progress(completed, total,
                                f"Analyzed slide {idx + 1} ({completed}/{total})...")

        for slide in results:
            self.slides.append(slide)

            if slide.analysis and slide.analysis.korean_to_english:
                self.korean_to_english.update(slide.analysis.korean_to_english)

            if slide.analysis:
                self.all_terms.extend(slide.analysis.key_terms)
                self.all_terms.extend(slide.analysis.medical_concepts)

        self.all_terms = list(dict.fromkeys(self.all_terms))

        self._loaded = True

        self._save_cache(pdf_path)

        if on_progress:
            on_progress(total, total, f"Done! {total} slides analyzed, "
                        f"{len(self.korean_to_english)} Korean-English mappings found.")

        logger.info(
            "Pre-analysis complete: %d slides, %d Korean-English mappings, %d terms",
            len(self.slides), len(self.korean_to_english), len(self.all_terms),
        )

    def match_screen(self, captured_image: Image.Image,
                     threshold: int = 12) -> PreAnalyzedSlide | None:
        """Match a captured screen image against pre-analyzed slides using imagehash.

        Args:
            captured_image: PIL Image from screen capture
            threshold: Max hamming distance for a match

        Returns:
            Best matching PreAnalyzedSlide, or None if no match found.
        """
        if not self.slides:
            return None

        captured_hash = imagehash.phash(captured_image)
        best_match = None
        best_distance = threshold + 1

        for slide in self.slides:
            distance = captured_hash - slide.phash
            if distance < best_distance:
                best_distance = distance
                best_match = slide

        if best_match and best_distance <= threshold:
            logger.info(
                "Matched captured screen to slide %d (distance=%d)",
                best_match.page_num + 1, best_distance,
            )
            return best_match

        logger.info("No slide match found (best distance=%d > threshold=%d)",
                     best_distance, threshold)
        return None

    def get_slide_analysis(self, page_num: int) -> ScreenAnalysis | None:
        """Get analysis for a specific slide by page number."""
        for slide in self.slides:
            if slide.page_num == page_num:
                return slide.analysis
        return None
