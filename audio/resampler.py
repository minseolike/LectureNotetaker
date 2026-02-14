import warnings

import numpy as np


class AudioResampler:
    """Converts WASAPI loopback audio (stereo) to mono LINEAR16 for STT."""

    def __init__(self, source_channels: int, source_rate: int):
        self.source_channels = source_channels
        self.source_rate = source_rate
        self.sample_width = 2

        self._use_audioop = False
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                import audioop  # noqa: F401
                self._use_audioop = True
        except ImportError:
            pass

    def to_mono(self, data: bytes) -> bytes:
        """Convert stereo to mono by averaging channels."""
        if self.source_channels <= 1:
            return data

        if self._use_audioop:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                import audioop
                return audioop.tomono(data, self.sample_width, 0.5, 0.5)

        return self._to_mono_numpy(data)

    def _to_mono_numpy(self, data: bytes) -> bytes:
        """Convert multi-channel 16-bit PCM to mono using numpy vectorized ops."""
        n_channels = self.source_channels
        samples = np.frombuffer(data, dtype=np.int16)
        n_frames = len(samples) // n_channels
        samples = samples[:n_frames * n_channels].reshape(n_frames, n_channels)
        mono = samples.mean(axis=1).astype(np.int16)
        return mono.tobytes()

    def process(self, data: bytes) -> bytes:
        """Full pipeline: stereo->mono."""
        return self.to_mono(data)
