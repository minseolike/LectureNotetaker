import ctypes
import queue
import threading
import logging
import sys
import time

from PIL import Image

# Enable DPI awareness on Windows BEFORE any Tkinter window is created.
# Without this, Tkinter coordinates are in logical pixels but mss captures
# in physical pixels, causing the selected region to be too small.
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from config import Config
from audio.capture import AudioCapture
from audio.resampler import AudioResampler
from stt.streaming import StreamingSTT
from stt.transcript import TranscriptBuffer
from stt.postprocess import TranscriptPostProcessor
from stt.refiner import TranscriptRefiner, RefinerBuffer
from screen.selector import RegionSelector
from screen.capture import ScreenCapture
from screen.analyzer import ScreenAnalyzer
from slides.preanalyzer import SlidePreAnalyzer
from export.pdf import PDFExporter, SlideData
from gui.app import NoteTakingGUI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class LectureNotetaker:
    """Main orchestrator: screen capture + audio → notes + highlighted transcript → PDF."""

    def __init__(self):
        self.config = Config()
        self.audio_queue = queue.Queue(maxsize=1000)
        self.resampled_queue = queue.Queue(maxsize=1000)
        self.transcript_buffer = TranscriptBuffer()
        self.postprocessor = TranscriptPostProcessor()
        self.current_slide = -1
        self.total_slides = 0
        self._running = False
        self._write_lock = threading.Lock()
        self._slide_timeline: list[tuple[float, int]] = []
        self._slide_grace_sec = 5.0

        self.slide_images: dict[int, Image.Image] = {}
        self.slide_pdf_images: dict[int, Image.Image] = {}
        self.slide_analyses = {}
        self.refined_texts: dict[int, list[str]] = {}

        self.region = None
        self.audio_capture = None
        self.resampler = None
        self.stt = None
        self.screen_capture = None
        self.screen_analyzer = ScreenAnalyzer(self.config)
        self.pre_analyzer = SlidePreAnalyzer(self.config)
        self.pdf_exporter = PDFExporter(self.config)
        self.refiner = TranscriptRefiner(self.config)
        self.refiner_buffer = RefinerBuffer(
            self.refiner,
            on_refined=self._on_refined,
            get_context=self._get_screen_context,
        )
        self.gui = NoteTakingGUI(controller=self)

    def select_region(self):
        """Open overlay for user to draw a rectangle around the video area."""
        selector = RegionSelector(master=self.gui.root)
        region = selector.select()
        if region:
            self.region = region
            self.gui.set_region_info(region)
            self.gui.update_status(
                f"Region selected: {region[2]}x{region[3]}. Click 'Start Capture' to begin."
            )
            logger.info("Region selected: %s", region)
        else:
            self.gui.update_status("Region selection cancelled.")

    def load_slides_pdf(self, pdf_path: str):
        """Load and pre-analyze a slide PDF in background thread."""
        def _load():
            try:
                def _on_progress(current, total, status):
                    self.gui.update_status(status)
                    if total > 0:
                        self.gui.show_progress(current, total)

                self.pre_analyzer.load_and_analyze(pdf_path, on_progress=_on_progress)

                if self.pre_analyzer.is_loaded:
                    if self.pre_analyzer.korean_to_english:
                        logger.info(
                            "Pre-loaded %d Korean→English mappings from PDF",
                            len(self.pre_analyzer.korean_to_english),
                        )

                    info = (
                        f"Slides loaded: {self.pre_analyzer.slide_count} slides, "
                        f"{len(self.pre_analyzer.korean_to_english)} term mappings"
                    )
                    self.gui.set_slides_loaded_info(info)
                    self.gui.update_status(
                        f"PDF pre-analysis complete! {self.pre_analyzer.slide_count} slides ready. "
                        f"Select a region and start capture."
                    )
                else:
                    self.gui.update_status("PDF loading failed. Check your OpenAI API key/billing.")
            except Exception as e:
                logger.error("PDF pre-analysis failed: %s", e)
                self.gui.update_status(f"PDF load error: {e}")
            finally:
                self.gui.enable_load_slides_btn()

        threading.Thread(target=_load, daemon=True).start()

    def start_capture(self):
        """Start audio capture, STT streaming, and screen polling."""
        if not self.region:
            self.gui.show_error("Error", "No screen region selected.")
            return

        self._running = True
        self.current_slide = -1
        self.total_slides = 0
        self._slide_timeline.clear()

        self.gui.clear_live()
        self.gui.clear_transcript()
        self.gui.clear_refined()
        self.gui.show_listening_indicator()

        try:
            self.audio_capture = AudioCapture(
                self.audio_queue, self.config.audio_chunk_duration_ms
            )
            self.audio_capture.start()
        except RuntimeError as e:
            self.gui.show_error("Audio Error", str(e))
            self.gui.update_status("Audio capture failed. Check speakers.")
            self._running = False
            return

        self.resampler = AudioResampler(
            self.audio_capture.channels,
            self.audio_capture.sample_rate,
        )

        def _resample_worker():
            drop_count = 0
            while self._running:
                try:
                    raw = self.audio_queue.get(timeout=0.1)
                    mono = self.resampler.process(raw)
                    try:
                        self.resampled_queue.put_nowait(mono)
                    except queue.Full:
                        drop_count += 1
                        if drop_count % 50 == 1:
                            logger.warning(
                                "Resampled queue full — dropped %d chunks so far",
                                drop_count,
                            )
                except queue.Empty:
                    continue

        threading.Thread(target=_resample_worker, daemon=True).start()

        if self.config.stt_provider == "deepgram" and self.config.deepgram_api_key:
            from stt.deepgram_streaming import DeepgramStreamingSTT
            self.stt = DeepgramStreamingSTT(
                self.config, self.resampled_queue, self._on_transcript,
                on_error=lambda msg: self.gui.update_status(msg),
                on_auth_failure=self._fallback_to_google_stt,
                sample_rate=self.audio_capture.sample_rate,
            )
            logger.info("Using Deepgram Nova-2 STT (fast)")
        else:
            self._start_google_stt()
        self.stt.start()

        self.screen_capture = ScreenCapture(
            self.region, self.config, self._on_slide_changed,
        )
        self.screen_capture.start()

        self.gui.update_status("Capturing audio + screen... Slide changes are detected automatically.")
        logger.info("Capture started")

    def _on_slide_changed(self, image: Image.Image):
        """Called when screen capture detects a slide change."""
        change_time = time.monotonic()
        self.current_slide += 1
        self.total_slides = self.current_slide + 1
        slide_idx = self.current_slide
        self._slide_timeline.append((change_time, slide_idx))

        self.slide_images[slide_idx] = image
        self.gui.display_slide_image(image)
        self.gui.update_slide(slide_idx, self.total_slides)
        self.gui.live_add_separator(slide_idx)
        self.gui.transcript_add_separator(slide_idx)
        self.gui.refined_add_separator(slide_idx)

        if self.pre_analyzer.is_loaded:
            matched = self.pre_analyzer.match_screen(image)
            if matched and matched.analysis:
                analysis = matched.analysis
                self.slide_analyses[slide_idx] = analysis
                self.slide_pdf_images[slide_idx] = matched.image
                self.gui.update_status(
                    f"Slide {slide_idx + 1} matched to PDF page {matched.page_num + 1}: "
                    f"{analysis.slide_title}"
                )

                logger.info("Slide %d matched to pre-analyzed page %d",
                           slide_idx + 1, matched.page_num + 1)
                return

        self.gui.update_status(f"Slide {slide_idx + 1} detected. Analyzing...")

        def _analyze():
            try:
                analysis = self.screen_analyzer.analyze_with_fallback(image)
                self.slide_analyses[slide_idx] = analysis

                self.gui.update_status(
                    f"Slide {slide_idx + 1} analyzed: {analysis.slide_title}"
                )
            except Exception as e:
                logger.error("Screen analysis failed for slide %d: %s", slide_idx + 1, e)
                self.gui.update_status(f"Analysis error: {e}")

        threading.Thread(target=_analyze, daemon=True).start()

    def _compute_slide_for_utterance(self, words: list[tuple[str, float, float]] | None) -> int:
        """Determine which slide an utterance belongs to using word timestamps.

        Uses the median word timestamp to find which slide was active when
        most of the speech occurred. Falls back to grace period heuristic
        if word timestamps aren't available (Google STT).
        """
        idx = max(0, self.current_slide)
        if not self._slide_timeline:
            return idx

        if not words or len(words) == 0:
            last_change_time, last_slide_idx = self._slide_timeline[-1]
            if idx > 0 and (time.monotonic() - last_change_time) < self._slide_grace_sec:
                return idx - 1
            return idx

        mid_idx = len(words) // 2
        median_time = words[mid_idx][1]

        assigned_slide = 0
        for change_time, slide_idx_at_change in self._slide_timeline:
            if median_time >= change_time:
                assigned_slide = slide_idx_at_change
            else:
                break

        assigned_slide = min(assigned_slide, idx)
        if assigned_slide != idx:
            logger.info(
                "Timestamp assignment: utterance at %.2f → slide %d (current=%d)",
                median_time, assigned_slide + 1, idx + 1,
            )
        return assigned_slide

    def _on_transcript(self, text: str, is_final: bool,
                       words: list[tuple[str, float, float]] | None = None,
                       confidence: float = 1.0):
        """Transcript callback with word timestamps and confidence.

        Top-right (LIVE DICTATION): Real-time stream of speech.
          - Interim: gray italic, replaced inline on each update
          - Final: committed with slide-aware positioning

        Bottom-left (TRANSCRIPT): PostProcessed Korean text.
        Bottom-right (REFINED): LLM-refined with English terms.
        """
        if is_final:
            if confidence < 0.15:
                logger.debug("Skipping noise: confidence=%.2f text='%s'", confidence, text[:50])
                return

            slide_idx = self._compute_slide_for_utterance(words)

            corrected = self.postprocessor.process(text)

            self.gui.live_commit_final(text, slide_idx)

            self.gui.transcript_append(corrected, slide_idx)

            self.transcript_buffer.add_segment(corrected, slide_idx, True)

            if confidence < 0.4:
                logger.info("Low confidence (%.2f), skipping refinement: '%s'", confidence, text[:50])
                self.gui.refined_append(corrected, slide_idx)
                self.refined_texts.setdefault(slide_idx, []).append(corrected)
            else:
                self._refine_async(corrected, slide_idx)
        else:
            self.gui.live_update_interim(text)

    def _get_screen_context(self, slide_idx: int, transcript: str = "") -> str:
        """Build screen context string for the refiner from current slide analysis.

        Includes title, key terms, medical concepts, Korean→English mappings,
        and English words extracted from slide text (for garbled English matching).
        """
        analysis = self.slide_analyses.get(slide_idx)
        parts = []

        if analysis:
            if analysis.slide_title:
                parts.append(f"Title: {analysis.slide_title}")
            if analysis.key_terms:
                parts.append(f"Terms on slide: {', '.join(analysis.key_terms)}")
            if analysis.medical_concepts:
                parts.append(f"Medical terms on slide: {', '.join(analysis.medical_concepts)}")
            if analysis.korean_to_english:
                mapping_lines = [f"  {k} → {v}" for k, v in analysis.korean_to_english.items()]
                parts.append("Korean phonetic → English mappings:\n" + "\n".join(mapping_lines))
            if analysis.text_content:
                import re
                eng_words = re.findall(r'[A-Za-z][A-Za-z0-9\-]{2,}', analysis.text_content)
                if eng_words:
                    unique_eng = list(dict.fromkeys(eng_words))
                    parts.append(f"English words on slide: {', '.join(unique_eng)}")

        return "\n".join(parts)

    def _on_refined(self, refined_text: str, slide_idx: int):
        """Callback from RefinerBuffer when a batch is refined."""
        self.gui.refined_append(refined_text, slide_idx)
        self.refined_texts.setdefault(slide_idx, []).append(refined_text)

    def _refine_async(self, text: str, slide_idx: int):
        """Add transcript to the refinement buffer (batched for better context)."""
        self.refiner_buffer.add(text, slide_idx)

    def _start_google_stt(self):
        """Initialize Google Chirp 3 STT as the active provider."""
        self.stt = StreamingSTT(
            self.config, self.resampled_queue, self._on_transcript,
            on_error=lambda msg: self.gui.update_status(msg),
            sample_rate=self.audio_capture.sample_rate,
        )
        logger.info("Using Google Chirp 3 STT")

    def _fallback_to_google_stt(self):
        """Called when Deepgram auth fails — switch to Google STT automatically."""
        logger.warning("Deepgram failed, falling back to Google Chirp 3 STT")
        if self.stt:
            self.stt.stop()
        self._start_google_stt()
        self.stt.start()
        self.gui.update_status("Deepgram auth failed — switched to Google Chirp 3 STT.")

    def force_capture(self):
        """Manual slide change trigger."""
        if self.screen_capture:
            self.screen_capture.force_capture()

    def stop_capture(self):
        """Stop audio and screen capture, then finalize refined text."""
        self._running = False

        self.refiner_buffer.flush()

        if self.screen_capture:
            self.screen_capture.stop()
        if self.stt:
            self.stt.stop()
        if self.audio_capture:
            self.audio_capture.stop()

        self.gui.update_status("Capture stopped. Finalizing refined text...")
        logger.info("Capture stopped. %d slides captured.", self.total_slides)

        threading.Thread(target=self._finalize_refined, daemon=True).start()

    def _finalize_refined(self):
        """Run a final LLM pass over each slide's refined text to fix punctuation/flow."""
        if not self.refiner_buffer.wait_pending(timeout=15.0):
            logger.warning("Timed out waiting for pending refines")

        if not self.refined_texts:
            self.gui.update_status(
                f"Capture stopped. {self.total_slides} slides captured. "
                f"Click 'Export PDF' to save."
            )
            return

        total = len(self.refined_texts)
        finalized = {}

        for i, (slide_idx, segments) in enumerate(sorted(self.refined_texts.items())):
            self.gui.update_status(f"Finalizing slide {i + 1}/{total}...")

            joined = "\n".join(segments)
            if not joined.strip():
                finalized[slide_idx] = joined
                continue

            context = self._get_screen_context(slide_idx, joined)
            result = self.refiner.finalize(joined, context)
            finalized[slide_idx] = result

        for slide_idx, text in finalized.items():
            self.refined_texts[slide_idx] = [text]

        self.gui.refined_replace_all(finalized)

        self.gui.update_status(
            f"Capture stopped. {self.total_slides} slides captured, "
            f"refined text finalized. Click 'Export PDF' to save."
        )
        logger.info("Finalization complete for %d slides", total)

    def export_pdf(self, output_path: str):
        """Export all captured slides + transcript to PDF."""
        def _export():
            try:
                slides_data = []
                for slide_idx in range(self.total_slides):
                    image = self.slide_pdf_images.get(slide_idx) or self.slide_images.get(slide_idx)
                    if not image:
                        continue

                    refined_segs = self.refined_texts.get(slide_idx, [])
                    if refined_segs:
                        transcript_text = "\n".join(refined_segs)
                    else:
                        transcript_text = self.transcript_buffer.get_archived_text(slide_idx)

                    context = self._get_screen_context(slide_idx, transcript_text)

                    self.gui.update_status(
                        f"Polishing slide {slide_idx + 1}/{self.total_slides}..."
                    )
                    polished_text = self.refiner.polish(transcript_text, context)

                    self.gui.update_status(
                        f"Summarizing slide {slide_idx + 1}/{self.total_slides}..."
                    )
                    summary_bullets = self.refiner.summarize(polished_text, context)

                    slides_data.append(SlideData(
                        slide_num=slide_idx,
                        image=image,
                        notes=summary_bullets,
                        transcript=polished_text,
                    ))

                self.pdf_exporter.export(
                    output_path, slides_data,
                    on_progress=lambda cur, tot: self.gui.update_status(
                        f"Exporting slide {cur}/{tot}..."
                    ),
                )

                self.gui.update_status(f"PDF exported to {output_path}")
                logger.info("PDF exported: %s (%d slides)", output_path, len(slides_data))
            except Exception as e:
                logger.error("PDF export failed: %s", e)
                self.gui.update_status(f"Export error: {e}")

        threading.Thread(target=_export, daemon=True).start()

    def run(self):
        self.gui.run()


def main():
    app = LectureNotetaker()
    app.run()


if __name__ == "__main__":
    main()
