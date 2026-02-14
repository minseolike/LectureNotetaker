import json
import logging
import queue
import threading
import time

import websocket

logger = logging.getLogger(__name__)


class DeepgramStreamingSTT:
    """Low-latency streaming STT using Deepgram Nova-2 via WebSocket.

    Significantly faster than Google Chirp 3 for real-time transcription.
    Requires a Deepgram API key (free tier available at deepgram.com).
    """

    def __init__(self, config, audio_queue, on_transcript,
                 on_error=None, on_auth_failure=None, sample_rate=48000):
        self.config = config
        self.audio_queue = audio_queue
        self.on_transcript = on_transcript
        self.on_error = on_error
        self.on_auth_failure = on_auth_failure
        self.sample_rate = sample_rate
        self._running = False
        self._ws = None
        self._ws_ready = threading.Event()
        self._auth_failed = False
        self._consecutive_errors = 0
        self._max_retries = 5
        self._stream_start_mono = 0.0
        self._restart_requested = False

    def _build_url(self):
        params = (
            f"model=nova-2"
            f"&language=ko"
            f"&encoding=linear16"
            f"&sample_rate={self.sample_rate}"
            f"&channels=1"
            f"&interim_results=true"
            f"&smart_format=true"
            f"&punctuate=true"
            f"&endpointing=300"
            f"&utterance_end_ms=1200"
            f"&filler_words=false"
            f"&words=true"
        )
        return f"wss://api.deepgram.com/v1/listen?{params}"

    def _on_open(self, ws):
        self._stream_start_mono = time.monotonic()
        logger.info("Deepgram WebSocket connected (stream_start=%.2f)", self._stream_start_mono)
        self._ws_ready.set()
        self._consecutive_errors = 0

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)

            msg_type = data.get("type", "")
            if msg_type in ("UtteranceEnd", "Metadata"):
                return

            ch = data.get("channel", {})
            if not isinstance(ch, dict):
                return

            alts = ch.get("alternatives", [])
            if alts:
                alt = alts[0]
                transcript = alt.get("transcript", "")
                if transcript.strip():
                    is_final = data.get("is_final", False)
                    confidence = alt.get("confidence", 1.0)

                    words_data = None
                    raw_words = alt.get("words", [])
                    if raw_words and self._stream_start_mono > 0:
                        words_data = [
                            (w.get("word", ""),
                             self._stream_start_mono + w.get("start", 0),
                             self._stream_start_mono + w.get("end", 0))
                            for w in raw_words
                        ]

                    self.on_transcript(
                        transcript, is_final,
                        words=words_data, confidence=confidence,
                    )
        except Exception as e:
            logger.warning("Deepgram parse error: %s", e)

    def _on_error(self, ws, error):
        err_str = str(error)
        if "401" in err_str or "INVALID_AUTH" in err_str:
            self._auth_failed = True
            logger.error("Deepgram auth failed (invalid API key). Stopping retries.")
            if self.on_error:
                self.on_error("Deepgram API key invalid. Falling back to Google STT...")
            if self.on_auth_failure:
                self.on_auth_failure()
            return
        logger.error("Deepgram WebSocket error: %s", error)
        if self.on_error:
            self.on_error(f"Deepgram: {err_str[:100]}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info("Deepgram WebSocket closed: %s %s", close_status_code, close_msg)
        self._ws_ready.clear()

        if self._auth_failed or not self._running:
            return

        if self._restart_requested:
            self._restart_requested = False
            logger.info("Deepgram reconnecting...")
            if self._running:
                self._connect()
            return

        self._consecutive_errors += 1
        if self._consecutive_errors >= self._max_retries:
            logger.error("Deepgram: %d consecutive failures, giving up.", self._consecutive_errors)
            if self.on_error:
                self.on_error("Deepgram connection failed repeatedly. Falling back to Google STT...")
            if self.on_auth_failure:
                self.on_auth_failure()
            return

        delay = min(2 ** self._consecutive_errors, 16)
        logger.info("Deepgram reconnecting in %ds (attempt %d/%d)...",
                     delay, self._consecutive_errors, self._max_retries)
        time.sleep(delay)
        if self._running and not self._auth_failed:
            self._connect()

    def _send_audio(self):
        """Thread that reads audio from queue and sends to Deepgram."""
        while self._running:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
                if self._ws_ready.is_set() and self._ws:
                    try:
                        self._ws.send(audio_data, opcode=websocket.ABNF.OPCODE_BINARY)
                    except Exception as e:
                        if self._running:
                            logger.warning("Deepgram send error: %s", e)
            except queue.Empty:
                continue

    def _connect(self):
        """Create and start WebSocket connection."""
        url = self._build_url()
        self._ws = websocket.WebSocketApp(
            url,
            header=[f"Authorization: Token {self.config.deepgram_api_key}"],
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        threading.Thread(
            target=self._ws.run_forever, daemon=True,
            kwargs={"ping_interval": 20, "ping_timeout": 10},
        ).start()

    def start(self):
        self._running = True
        self._auth_failed = False
        self._consecutive_errors = 0
        self._connect()
        threading.Thread(target=self._send_audio, daemon=True).start()
        logger.info("Deepgram STT started (nova-2, ko, sample_rate=%d)", self.sample_rate)

    def stop(self):
        self._running = False
        if self._ws:
            try:
                self._ws.send(json.dumps({"type": "CloseStream"}))
                self._ws.close()
            except Exception:
                pass
        self._ws_ready.clear()
        logger.info("Deepgram STT stopped")

    def force_restart(self):
        """Reconnect to apply new settings (keywords, etc.)."""
        if self._ws and self._running:
            self._restart_requested = True
            try:
                self._ws.close()
            except Exception:
                self._restart_requested = False
