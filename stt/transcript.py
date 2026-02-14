import threading
from collections import defaultdict


class TranscriptBuffer:
    """Accumulates transcript segments tagged by slide index."""

    def __init__(self):
        self._lock = threading.Lock()
        self._segments: dict[int, list[str]] = defaultdict(list)
        self._archive: dict[int, list[str]] = defaultdict(list)
        self._interim: str = ""

    def add_segment(self, text: str, slide_index: int, is_final: bool):
        with self._lock:
            if is_final:
                segments = self._segments[slide_index]
                if segments and text.startswith(segments[-1]):
                    segments[-1] = text
                    if self._archive[slide_index]:
                        self._archive[slide_index][-1] = text
                elif segments and segments[-1].startswith(text):
                    pass
                else:
                    segments.append(text)
                    self._archive[slide_index].append(text)
                self._interim = ""
            else:
                self._interim = text

    def get_slide_text(self, slide_index: int) -> str:
        """Get all accumulated final text for a slide."""
        with self._lock:
            return " ".join(self._segments.get(slide_index, []))

    def get_current_interim(self) -> str:
        with self._lock:
            return self._interim

    def get_archived_text(self, slide_index: int) -> str:
        """Get all final text ever recorded for a slide (survives flush)."""
        with self._lock:
            return " ".join(self._archive.get(slide_index, []))

    def flush_slide(self, slide_index: int) -> str:
        """Return and clear all text for a slide."""
        with self._lock:
            text = " ".join(self._segments.pop(slide_index, []))
            return text

    def has_enough_text(self, slide_index: int, min_chars: int) -> bool:
        with self._lock:
            text = " ".join(self._segments.get(slide_index, []))
            return len(text) >= min_chars

    def get_all_slide_indices(self) -> list[int]:
        """Return all slide indices that have archived text."""
        with self._lock:
            return sorted(self._archive.keys())
