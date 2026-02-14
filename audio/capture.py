import queue
import logging

import pyaudiowpatch as pyaudio

logger = logging.getLogger(__name__)


class AudioCapture:
    """Captures system audio via WASAPI loopback."""

    def __init__(self, chunk_queue: queue.Queue, chunk_duration_ms: int = 100):
        self.chunk_queue = chunk_queue
        self.chunk_duration_ms = chunk_duration_ms
        self._pa = pyaudio.PyAudio()
        self._stream = None
        self._running = False
        self._device_info = None
        self._drop_count = 0
        self.channels = 0
        self.sample_rate = 0

    def _find_loopback_device(self) -> dict:
        """Find the WASAPI loopback device for default speakers."""
        wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = self._pa.get_device_info_by_index(
            wasapi_info["defaultOutputDevice"]
        )
        for loopback in self._pa.get_loopback_device_info_generator():
            if default_speakers["name"] in loopback["name"]:
                logger.info(
                    "Found loopback device: %s (rate=%s, channels=%s)",
                    loopback["name"],
                    loopback["defaultSampleRate"],
                    loopback["maxInputChannels"],
                )
                return loopback
        raise RuntimeError(
            "No WASAPI loopback device found. "
            "Ensure audio is playing through your default speakers."
        )

    def start(self):
        """Open audio stream with callback that enqueues chunks."""
        self._device_info = self._find_loopback_device()
        self._running = True

        self.channels = int(self._device_info["maxInputChannels"])
        self.sample_rate = int(self._device_info["defaultSampleRate"])
        chunk_frames = int(self.sample_rate * self.chunk_duration_ms / 1000)

        def callback(in_data, frame_count, time_info, status):
            if self._running:
                try:
                    self.chunk_queue.put_nowait(in_data)
                except queue.Full:
                    self._drop_count += 1
                    if self._drop_count % 50 == 1:
                        logger.warning(
                            "Audio capture queue full — dropped %d chunks",
                            self._drop_count,
                        )
            return (None, pyaudio.paContinue)

        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            frames_per_buffer=chunk_frames,
            input=True,
            input_device_index=self._device_info["index"],
            stream_callback=callback,
        )
        logger.info(
            "Audio capture started: %d Hz, %d channels, %d ms chunks",
            self.sample_rate, self.channels, self.chunk_duration_ms,
        )

    def stop(self):
        """Stop audio capture and release resources."""
        self._running = False
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception as e:
                logger.warning("Error stopping audio stream: %s", e)
        self._pa.terminate()
        logger.info("Audio capture stopped")
