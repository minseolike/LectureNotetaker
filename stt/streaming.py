import threading
import queue
import time
import logging

from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.client_options import ClientOptions

from medical.terms import get_all_medical_terms, MIXED_LECTURE_TERMS

logger = logging.getLogger(__name__)


class StreamingSTT:
    """Manages streaming recognition sessions with Chirp 3 and medical term boosting."""

    def __init__(self, config, audio_queue: queue.Queue, on_transcript: callable,
                 on_error: callable = None, sample_rate: int = 48000):
        self.config = config
        self.audio_queue = audio_queue
        self.on_transcript = on_transcript
        self.on_error = on_error
        self.sample_rate = sample_rate
        self._running = False
        self._force_restart = False
        self._thread = None
        self._client = SpeechClient(
            client_options=ClientOptions(
                api_endpoint=f"{config.gcp_region}-speech.googleapis.com"
            )
        )

    def _build_phrase_set(self) -> cloud_speech.SpeechAdaptation:
        """Build phrase set from medical terminology (static + dynamic) for recognition boosting."""
        all_terms = get_all_medical_terms() + MIXED_LECTURE_TERMS
        phrases = [
            cloud_speech.PhraseSet.Phrase(value=term, boost=boost / 10.0)
            for term, boost in all_terms
        ]

        phrase_sets = []
        for i in range(0, len(phrases), 500):
            chunk = phrases[i:i + 500]
            phrase_sets.append(
                cloud_speech.SpeechAdaptation.AdaptationPhraseSet(
                    inline_phrase_set=cloud_speech.PhraseSet(phrases=chunk)
                )
            )

        logger.info("Built phrase set with %d terms (%d chunks)", len(phrases), len(phrase_sets))
        return cloud_speech.SpeechAdaptation(phrase_sets=phrase_sets)

    def _make_config_request(self) -> cloud_speech.StreamingRecognizeRequest:
        recognition_config = cloud_speech.RecognitionConfig(
            explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
                encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=self.sample_rate,
                audio_channel_count=1,
            ),
            language_codes=self.config.stt_language_codes,
            model=self.config.stt_model,
            adaptation=self._build_phrase_set(),
        )
        streaming_config = cloud_speech.StreamingRecognitionConfig(
            config=recognition_config,
            streaming_features=cloud_speech.StreamingRecognitionFeatures(
                interim_results=True,
            ),
        )
        return cloud_speech.StreamingRecognizeRequest(
            recognizer=(
                f"projects/{self.config.gcp_project_id}"
                f"/locations/{self.config.gcp_region}/recognizers/_"
            ),
            streaming_config=streaming_config,
        )

    def _audio_generator(self):
        """Yield audio chunks from the queue, respecting 25KB limit."""
        MAX_CHUNK_BYTES = 25000
        while self._running and not self._force_restart:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                for i in range(0, len(chunk), MAX_CHUNK_BYTES):
                    yield cloud_speech.StreamingRecognizeRequest(
                        audio=chunk[i:i + MAX_CHUNK_BYTES]
                    )
            except queue.Empty:
                continue

    def _request_generator(self):
        """Yield config request first, then audio requests."""
        yield self._make_config_request()
        yield from self._audio_generator()

    def _run_stream(self):
        """Run streaming sessions with auto-restart.

        Audio is preserved across restarts because the queue persists — chunks
        that arrive during the brief reconnect gap are picked up by the next
        session.  We keep the timeout close to Google's 5-min limit to
        minimise the number of restarts (and therefore gaps).
        """
        consecutive_errors = 0
        while self._running:
            self._force_restart = False
            stream_start = time.monotonic()
            try:
                logger.info("Starting new STT streaming session")
                responses = self._client.streaming_recognize(
                    requests=self._request_generator()
                )
                for response in responses:
                    if not self._running:
                        return
                    if self._force_restart:
                        break
                    elapsed = time.monotonic() - stream_start
                    if elapsed > self.config.stt_stream_timeout_sec:
                        logger.info(
                            "Stream timeout reached (%.0fs), restarting...",
                            elapsed,
                        )
                        break
                    for result in response.results:
                        if result.alternatives:
                            transcript = result.alternatives[0].transcript
                            is_final = result.is_final
                            self.on_transcript(
                                transcript, is_final,
                                words=None, confidence=1.0,
                            )
                consecutive_errors = 0
            except Exception as e:
                if self._running:
                    consecutive_errors += 1
                    err_msg = str(e)
                    delay = min(0.5 * consecutive_errors, 3.0)
                    logger.warning(
                        "STT stream error (#%d): %s. Restarting in %.1fs...",
                        consecutive_errors, err_msg, delay,
                    )
                    if self.on_error:
                        self.on_error(f"STT error: {err_msg[:100]}")
                    time.sleep(delay)

    def force_restart(self):
        """Force the stream to restart (e.g., to pick up new dynamic terms)."""
        self._force_restart = True
        logger.info("STT stream force restart requested")

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run_stream, daemon=True)
        self._thread.start()
        logger.info("STT streaming started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("STT streaming stopped")
