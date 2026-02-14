import threading
import time
import logging
import io

import mss
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class ScreenCapture:
    """Periodically captures a screen region and detects slide changes."""

    def __init__(self, region: tuple[int, int, int, int], config,
                 on_slide_changed: callable):
        left, top, width, height = region
        self._monitor = {"left": left, "top": top, "width": width, "height": height}
        self._interval = config.screen_poll_interval_sec
        self._threshold_pct = config.screen_change_threshold_pct
        self._on_slide_changed = on_slide_changed
        self._running = False
        self._thread = None
        self._last_array: np.ndarray | None = None
        self._last_image = None

    def capture(self) -> Image.Image:
        """Capture the screen region and return as PIL Image."""
        with mss.mss() as sct:
            shot = sct.grab(self._monitor)
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    def has_changed(self, current: Image.Image) -> bool:
        """Check if >threshold_pct of pixels changed (per-channel diff > 20)."""
        w, h = current.size
        scale = 320 / max(w, 1)
        small = current.resize((int(w * scale), int(h * scale)), Image.NEAREST)
        arr = np.asarray(small, dtype=np.int16)

        if self._last_array is None:
            self._last_array = arr
            return True

        if arr.shape != self._last_array.shape:
            self._last_array = arr
            return True

        diff = np.abs(arr - self._last_array)
        changed_pixels = np.any(diff > 20, axis=2)
        pct_changed = changed_pixels.mean() * 100

        if pct_changed > self._threshold_pct:
            logger.info("Slide change: %.1f%% pixels changed (threshold=%d%%)",
                        pct_changed, self._threshold_pct)
            self._last_array = arr
            return True

        if pct_changed > 3.0:
            logger.debug("Below threshold: %.1f%% pixels changed", pct_changed)

        return False

    def get_image_bytes(self, image: Image.Image) -> bytes:
        """Convert PIL Image to PNG bytes."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()

    def _poll_loop(self):
        """Main polling loop - runs in background thread."""
        while self._running:
            try:
                image = self.capture()
                if self.has_changed(image):
                    self._last_image = image
                    logger.info("Slide change detected")
                    self._on_slide_changed(image)
            except Exception as e:
                logger.warning("Screen capture error: %s", e)
            time.sleep(self._interval)

    def force_capture(self) -> Image.Image | None:
        """Force an immediate capture and trigger slide change."""
        try:
            image = self.capture()
            w, h = image.size
            scale = 320 / max(w, 1)
            small = image.resize((int(w * scale), int(h * scale)), Image.NEAREST)
            self._last_array = np.asarray(small, dtype=np.int16)
            self._last_image = image
            self._on_slide_changed(image)
            return image
        except Exception as e:
            logger.warning("Force capture failed: %s", e)
            return None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Screen capture started (interval=%.1fs, threshold=%d%%)",
                     self._interval, self._threshold_pct)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("Screen capture stopped")
