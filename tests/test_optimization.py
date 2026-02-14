"""Tests for the optimization changes:
- Timestamp-based slide assignment
- RefinerBuffer batch processing
- Thread-safe dynamic terms
- Confidence filtering
- Deepgram keyword URL building
"""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch


class TestTimestampSlideAssignment(unittest.TestCase):
    """Test _compute_slide_for_utterance() with various timestamp patterns."""

    def _make_notetaker(self):
        """Create a minimal LectureNotetaker-like object for testing."""
        obj = MagicMock()
        obj.current_slide = 0
        obj._slide_timeline = []
        obj._slide_grace_sec = 5.0

        from main import LectureNotetaker
        obj._compute_slide_for_utterance = (
            LectureNotetaker._compute_slide_for_utterance.__get__(obj)
        )
        return obj

    def test_no_timeline_returns_current(self):
        """With no slide changes, always return current slide."""
        obj = self._make_notetaker()
        obj.current_slide = 2
        obj._slide_timeline = []
        result = obj._compute_slide_for_utterance(None)
        self.assertEqual(result, 2)

    def test_no_words_uses_grace_period(self):
        """Without word timestamps, fall back to grace period."""
        obj = self._make_notetaker()
        obj.current_slide = 1
        obj._slide_timeline = [
            (100.0, 0),
            (time.monotonic() - 2.0, 1),
        ]
        result = obj._compute_slide_for_utterance(None)
        self.assertEqual(result, 0)

    def test_no_words_past_grace_period(self):
        """Without word timestamps, past grace period -> current slide."""
        obj = self._make_notetaker()
        obj.current_slide = 1
        obj._slide_timeline = [
            (100.0, 0),
            (time.monotonic() - 10.0, 1),
        ]
        result = obj._compute_slide_for_utterance(None)
        self.assertEqual(result, 1)

    def test_words_before_slide_change(self):
        """Words spoken before slide change -> assigned to previous slide."""
        obj = self._make_notetaker()
        obj.current_slide = 1
        obj._slide_timeline = [(100.0, 0), (200.0, 1)]

        words = [
            ("hello", 140.0, 141.0),
            ("world", 150.0, 151.0),
            ("test", 160.0, 161.0),
        ]
        result = obj._compute_slide_for_utterance(words)
        self.assertEqual(result, 0)

    def test_words_after_slide_change(self):
        """Words spoken after slide change -> assigned to current slide."""
        obj = self._make_notetaker()
        obj.current_slide = 1
        obj._slide_timeline = [(100.0, 0), (200.0, 1)]

        words = [
            ("hello", 240.0, 241.0),
            ("world", 250.0, 251.0),
            ("test", 260.0, 261.0),
        ]
        result = obj._compute_slide_for_utterance(words)
        self.assertEqual(result, 1)

    def test_words_spanning_slide_change(self):
        """Words that span a slide change: median determines assignment."""
        obj = self._make_notetaker()
        obj.current_slide = 1
        obj._slide_timeline = [(100.0, 0), (200.0, 1)]

        words = [
            ("a", 170.0, 171.0),
            ("b", 180.0, 181.0),
            ("c", 190.0, 191.0),
            ("d", 210.0, 211.0),
            ("e", 220.0, 221.0),
        ]
        result = obj._compute_slide_for_utterance(words)
        self.assertEqual(result, 0)

    def test_empty_words_list(self):
        """Empty words list should fall back to grace period."""
        obj = self._make_notetaker()
        obj.current_slide = 1
        obj._slide_timeline = [(100.0, 0), (time.monotonic() - 10.0, 1)]
        result = obj._compute_slide_for_utterance([])
        self.assertEqual(result, 1)

    def test_single_word(self):
        """Single word utterance."""
        obj = self._make_notetaker()
        obj.current_slide = 1
        obj._slide_timeline = [(100.0, 0), (200.0, 1)]

        words = [("hello", 150.0, 151.0)]
        result = obj._compute_slide_for_utterance(words)
        self.assertEqual(result, 0)

    def test_first_slide_no_previous(self):
        """On first slide, always assign to slide 0."""
        obj = self._make_notetaker()
        obj.current_slide = 0
        obj._slide_timeline = [(100.0, 0)]

        words = [("hello", 90.0, 91.0)]
        result = obj._compute_slide_for_utterance(words)
        self.assertEqual(result, 0)

    def test_multiple_rapid_slide_changes(self):
        """Multiple rapid slide changes -- correct assignment."""
        obj = self._make_notetaker()
        obj.current_slide = 3
        obj._slide_timeline = [
            (100.0, 0),
            (102.0, 1),
            (104.0, 2),
            (106.0, 3),
        ]

        words = [("test", 103.0, 103.5)]
        result = obj._compute_slide_for_utterance(words)
        self.assertEqual(result, 1)


class TestRefinerBuffer(unittest.TestCase):
    """Test RefinerBuffer batch processing logic."""

    def _make_buffer(self, max_segments=3, flush_timeout=8.0):
        refiner = MagicMock()
        refiner.refine.return_value = "refined text"
        results = []

        def on_refined(text, slide_idx):
            results.append((text, slide_idx))

        def get_context(slide_idx, transcript=""):
            return f"context for slide {slide_idx}"

        from stt.refiner import RefinerBuffer
        buf = RefinerBuffer(
            refiner, on_refined, get_context,
            max_segments=max_segments, flush_timeout_sec=flush_timeout,
        )
        return buf, refiner, results

    def test_flush_on_max_segments(self):
        """Buffer flushes when max_segments reached."""
        buf, refiner, results = self._make_buffer(max_segments=3)

        buf.add("segment 1", 0)
        buf.add("segment 2", 0)
        self.assertEqual(len(results), 0)

        buf.add("segment 3", 0)
        time.sleep(0.3)
        self.assertEqual(len(results), 1)
        refiner.refine.assert_called_once()
        call_args = refiner.refine.call_args[0]
        self.assertIn("segment 1", call_args[0])
        self.assertIn("segment 3", call_args[0])

    def test_flush_on_slide_change(self):
        """Buffer flushes when slide changes."""
        buf, refiner, results = self._make_buffer(max_segments=5)

        buf.add("text for slide 0", 0)
        buf.add("more text", 0)
        buf.add("text for slide 1", 1)
        time.sleep(0.3)

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0][1], 0)

    def test_flush_on_timeout(self):
        """Buffer flushes after timeout."""
        buf, refiner, results = self._make_buffer(
            max_segments=10, flush_timeout=0.5,
        )

        buf.add("segment 1", 0)
        self.assertEqual(len(results), 0)

        time.sleep(1.0)
        self.assertEqual(len(results), 1)

    def test_manual_flush(self):
        """Manual flush() clears buffer."""
        buf, refiner, results = self._make_buffer(max_segments=10)

        buf.add("segment 1", 0)
        buf.add("segment 2", 0)
        buf.flush()
        time.sleep(0.3)

        self.assertEqual(len(results), 1)

    def test_empty_flush_noop(self):
        """Flushing empty buffer does nothing."""
        buf, refiner, results = self._make_buffer()
        buf.flush()
        time.sleep(0.1)
        self.assertEqual(len(results), 0)
        refiner.refine.assert_not_called()


class TestThreadSafety(unittest.TestCase):
    """Test thread-safe access to dynamic terms."""

    def test_concurrent_add(self):
        """Multiple threads adding terms concurrently."""
        from medical.terms import _dynamic_terms, _lock

        with _lock:
            _dynamic_terms.clear()

        from medical.terms import add_dynamic_terms

        errors = []

        def add_batch(batch_id):
            try:
                terms = [f"term_{batch_id}_{i}" for i in range(50)]
                add_dynamic_terms(terms)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_batch, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors: {errors}")

        from medical.terms import get_dynamic_terms
        dynamic = get_dynamic_terms()
        self.assertEqual(len(dynamic), 500)

        with _lock:
            _dynamic_terms.clear()

    def test_concurrent_read_write(self):
        """One thread writing, multiple threads reading."""
        from medical.terms import _dynamic_terms, _lock

        with _lock:
            _dynamic_terms.clear()

        from medical.terms import add_dynamic_terms, get_all_medical_terms

        errors = []
        stop = threading.Event()

        def writer():
            for i in range(100):
                add_dynamic_terms([f"rw_term_{i}"])
                time.sleep(0.001)
            stop.set()

        def reader():
            try:
                while not stop.is_set():
                    get_all_medical_terms()
            except Exception as e:
                errors.append(e)

        w = threading.Thread(target=writer)
        readers = [threading.Thread(target=reader) for _ in range(5)]

        w.start()
        for r in readers:
            r.start()

        w.join()
        for r in readers:
            r.join(timeout=5.0)

        self.assertEqual(len(errors), 0, f"Errors: {errors}")

        with _lock:
            _dynamic_terms.clear()


class TestConfidenceFilter(unittest.TestCase):
    """Test confidence-based transcript filtering."""

    def _make_notetaker(self):
        obj = MagicMock()
        obj.current_slide = 0
        obj._slide_timeline = [(100.0, 0)]
        obj._slide_grace_sec = 5.0

        from main import LectureNotetaker
        obj._compute_slide_for_utterance = (
            LectureNotetaker._compute_slide_for_utterance.__get__(obj)
        )
        obj._on_transcript = (
            LectureNotetaker._on_transcript.__get__(obj)
        )
        obj.gui = MagicMock()
        obj.postprocessor = MagicMock()
        obj.postprocessor.process.return_value = "processed"
        obj.transcript_buffer = MagicMock()
        obj.refined_texts = {}
        obj.refiner_buffer = MagicMock()
        return obj

    def test_very_low_confidence_skipped(self):
        """Confidence < 0.15 -> skipped entirely."""
        obj = self._make_notetaker()
        obj._on_transcript("noise text", True, words=None, confidence=0.10)
        obj.gui.live_commit_final.assert_not_called()

    def test_low_confidence_no_refinement(self):
        """Confidence < 0.4 -> shown but not refined."""
        obj = self._make_notetaker()
        obj._on_transcript("low conf", True, words=None, confidence=0.3)
        obj.gui.live_commit_final.assert_called_once()
        obj.gui.transcript_append.assert_called_once()
        obj.refiner_buffer.add.assert_not_called()
        obj.gui.refined_append.assert_called_once()

    def test_normal_confidence_refined(self):
        """Confidence >= 0.4 -> refined normally (calls _refine_async)."""
        obj = self._make_notetaker()
        obj._on_transcript("good text", True, words=None, confidence=0.8)
        obj.gui.live_commit_final.assert_called_once()
        obj.gui.transcript_append.assert_called_once()
        obj._refine_async.assert_called_once()

    def test_interim_ignores_confidence(self):
        """Interim text shown regardless of confidence."""
        obj = self._make_notetaker()
        obj._on_transcript("interim", False, words=None, confidence=0.05)
        obj.gui.live_update_interim.assert_called_once_with("interim")


class TestDeepgramURL(unittest.TestCase):
    """Test Deepgram URL building (no keyword boosting)."""

    def _make_stt(self):
        config = MagicMock()
        config.deepgram_api_key = "test_key"
        from stt.deepgram_streaming import DeepgramStreamingSTT
        return DeepgramStreamingSTT(
            config, MagicMock(), lambda *a, **kw: None,
            sample_rate=48000,
        )

    def test_url_contains_words_true(self):
        stt = self._make_stt()
        url = stt._build_url()
        self.assertIn("words=true", url)

    def test_url_no_keywords(self):
        stt = self._make_stt()
        url = stt._build_url()
        self.assertNotIn("keywords=", url)


class TestDeepgramMessageParsing(unittest.TestCase):
    """Test Deepgram WebSocket message parsing with word timestamps."""

    def _make_stt(self):
        config = MagicMock()
        config.deepgram_api_key = "test_key"
        self.received = []

        def on_transcript(text, is_final, words=None, confidence=1.0):
            self.received.append({
                "text": text, "is_final": is_final,
                "words": words, "confidence": confidence,
            })

        from stt.deepgram_streaming import DeepgramStreamingSTT
        stt = DeepgramStreamingSTT(
            config, MagicMock(), on_transcript, sample_rate=48000,
        )
        stt._stream_start_mono = 1000.0
        return stt

    def test_final_with_words(self):
        """Parse a Deepgram final message with word timestamps."""
        import json
        stt = self._make_stt()

        msg = json.dumps({
            "is_final": True,
            "channel": {
                "alternatives": [{
                    "transcript": "hello world",
                    "confidence": 0.95,
                    "words": [
                        {"word": "hello", "start": 1.0, "end": 1.5},
                        {"word": "world", "start": 1.5, "end": 2.0},
                    ],
                }],
            },
        })

        stt._on_message(None, msg)
        self.assertEqual(len(self.received), 1)
        r = self.received[0]
        self.assertEqual(r["text"], "hello world")
        self.assertTrue(r["is_final"])
        self.assertAlmostEqual(r["confidence"], 0.95)
        self.assertEqual(len(r["words"]), 2)
        self.assertAlmostEqual(r["words"][0][1], 1001.0)
        self.assertAlmostEqual(r["words"][1][1], 1001.5)

    def test_interim_without_words(self):
        """Parse an interim message (typically no words)."""
        import json
        stt = self._make_stt()

        msg = json.dumps({
            "is_final": False,
            "channel": {
                "alternatives": [{
                    "transcript": "hello",
                    "confidence": 0.8,
                }],
            },
        })

        stt._on_message(None, msg)
        self.assertEqual(len(self.received), 1)
        r = self.received[0]
        self.assertFalse(r["is_final"])
        self.assertIsNone(r["words"])

    def test_empty_transcript_ignored(self):
        """Empty transcript in message should be ignored."""
        import json
        stt = self._make_stt()

        msg = json.dumps({
            "is_final": True,
            "channel": {
                "alternatives": [{
                    "transcript": "   ",
                    "confidence": 0.9,
                }],
            },
        })

        stt._on_message(None, msg)
        self.assertEqual(len(self.received), 0)

    def test_before_connection_no_words(self):
        """If stream_start_mono is 0, words should be None."""
        import json
        stt = self._make_stt()
        stt._stream_start_mono = 0

        msg = json.dumps({
            "is_final": True,
            "channel": {
                "alternatives": [{
                    "transcript": "test",
                    "confidence": 0.9,
                    "words": [{"word": "test", "start": 1.0, "end": 1.5}],
                }],
            },
        })

        stt._on_message(None, msg)
        self.assertEqual(len(self.received), 1)
        self.assertIsNone(self.received[0]["words"])


class TestRefinerBufferEdgeCases(unittest.TestCase):
    """Edge case tests for RefinerBuffer."""

    def _make_buffer(self, **kwargs):
        refiner = MagicMock()
        refiner.refine.return_value = "refined"
        results = []

        def on_refined(text, slide_idx):
            results.append((text, slide_idx))

        from stt.refiner import RefinerBuffer
        buf = RefinerBuffer(
            refiner, on_refined, lambda idx: "",
            **kwargs,
        )
        return buf, refiner, results

    def test_rapid_slide_changes(self):
        """Buffer handles rapid slide changes (flush between each)."""
        buf, refiner, results = self._make_buffer(max_segments=10)

        buf.add("text0", 0)
        buf.add("text1", 1)
        buf.add("text2", 2)
        time.sleep(0.5)

        self.assertGreaterEqual(len(results), 2)

    def test_refiner_failure_returns_original(self):
        """When refiner fails, original text is returned."""
        buf, refiner, results = self._make_buffer(max_segments=1)
        refiner.refine.side_effect = Exception("API error")

        buf.add("original text", 0)
        time.sleep(0.3)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "original text")

    def test_concurrent_adds(self):
        """Multiple threads adding to buffer simultaneously."""
        buf, refiner, results = self._make_buffer(max_segments=5)
        errors = []

        def add_items(batch):
            try:
                for i in range(10):
                    buf.add(f"text_{batch}_{i}", 0)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_items, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        buf.flush()
        time.sleep(0.5)

        self.assertEqual(len(errors), 0)
        self.assertGreater(len(results), 0)


class TestSlideAssignmentIntegration(unittest.TestCase):
    """Integration tests simulating real slide change + speech patterns."""

    def _make_notetaker(self):
        obj = MagicMock()
        obj.current_slide = -1
        obj._slide_timeline = []
        obj._slide_grace_sec = 5.0

        from main import LectureNotetaker
        obj._compute_slide_for_utterance = (
            LectureNotetaker._compute_slide_for_utterance.__get__(obj)
        )
        return obj

    def test_lecture_sequence(self):
        """Simulate a typical lecture: 3 slides with speech between changes."""
        obj = self._make_notetaker()

        obj.current_slide = 0
        obj._slide_timeline.append((100.0, 0))

        words = [("intro", 105.0, 106.0), ("topic", 107.0, 108.0)]
        self.assertEqual(obj._compute_slide_for_utterance(words), 0)

        obj.current_slide = 1
        obj._slide_timeline.append((120.0, 1))

        words = [("still", 118.0, 118.5), ("about", 119.0, 119.5)]
        self.assertEqual(obj._compute_slide_for_utterance(words), 0)

        words = [("new", 125.0, 125.5), ("slide", 126.0, 126.5)]
        self.assertEqual(obj._compute_slide_for_utterance(words), 1)

        obj.current_slide = 2
        obj._slide_timeline.append((150.0, 2))

        words = [("final", 155.0, 155.5)]
        self.assertEqual(obj._compute_slide_for_utterance(words), 2)

    def test_no_slide_captured_yet(self):
        """Before any slide is captured, current_slide=-1 -> returns 0."""
        obj = self._make_notetaker()
        obj.current_slide = -1
        result = obj._compute_slide_for_utterance(None)
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
