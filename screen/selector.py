import tkinter as tk
import logging

logger = logging.getLogger(__name__)


class RegionSelector:
    """Full-screen overlay for rubber-band region selection."""

    def __init__(self, master: tk.Tk = None):
        self._region = None
        self._master = master

    def select(self) -> tuple[int, int, int, int] | None:
        """Open overlay and let user draw a rectangle.
        Returns (left, top, width, height) or None if cancelled."""
        self._region = None
        self._done = False

        overlay = tk.Toplevel(self._master)
        overlay.attributes("-fullscreen", True)
        overlay.attributes("-alpha", 0.3)
        overlay.attributes("-topmost", True)
        overlay.configure(bg="black")
        overlay.title("Select Screen Region")
        overlay.grab_set()  # Make modal

        canvas = tk.Canvas(overlay, cursor="cross", bg="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        start_x = start_y = 0
        rect_id = None

        def on_press(event):
            nonlocal start_x, start_y, rect_id
            start_x, start_y = event.x, event.y
            if rect_id:
                canvas.delete(rect_id)
            rect_id = canvas.create_rectangle(
                start_x, start_y, start_x, start_y,
                outline="red", width=3,
            )

        def on_drag(event):
            if rect_id:
                canvas.coords(rect_id, start_x, start_y, event.x, event.y)

        def on_release(event):
            x0 = min(start_x, event.x)
            y0 = min(start_y, event.y)
            x1 = max(start_x, event.x)
            y1 = max(start_y, event.y)
            w = x1 - x0
            h = y1 - y0
            if w > 20 and h > 20:
                self._region = (x0, y0, w, h)
            self._done = True
            overlay.destroy()

        def on_escape(event):
            self._done = True
            overlay.destroy()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        overlay.bind("<Escape>", on_escape)

        # Show instruction label
        label = tk.Label(
            overlay, text="Draw a rectangle around the video area. Press Escape to cancel.",
            font=("Segoe UI", 16), fg="white", bg="black",
        )
        label.place(relx=0.5, rely=0.05, anchor="center")

        # Wait for the overlay to close (without blocking the main event loop)
        overlay.wait_window()

        if self._region:
            logger.info("Region selected: %s", self._region)
        return self._region
