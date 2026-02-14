import os
import io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging

from PIL import Image, ImageTk

logger = logging.getLogger(__name__)

_C = {
    "header":      "#1B2A4A",
    "header_text": "#FFFFFF",
    "bg":          "#F0F2F5",
    "panel":       "#FFFFFF",
    "text":        "#1A1A2E",
    "muted":       "#6B7280",
    "border":      "#E5E7EB",
    "section":     "#374151",
    "slide_bg":    "#1F2937",
    "accent":      "#2563EB",
    "success":     "#059669",
    "interim_bg":  "#F3F4F6",
}


class NoteTakingGUI:
    """McKinsey-style GUI for lecture notetaking.

    Layout (4 panels):
      ┌─ Header (dark navy): title + buttons ──────────────────────┐
      ├─ Status bar ───────────────────────────────────────────────┤
      ├─ Top: Slide preview (left) │ Live Dictation (right, gray) ─┤
      ├─ Bottom: Transcript (left) │ Refined transcript (right) ───┤
      └────────────────────────────────────────────────────────────┘
    """

    def __init__(self, controller):
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("Lecture Notetaker")
        self.root.geometry("1300x900")
        self.root.minsize(1000, 700)
        self.root.configure(bg=_C["bg"])

        self._slide_photo = None
        self._has_interim = False
        self._listening_shown = False
        self._transcript_visible = False

        self._build_ui()
        self._check_env()

    def _check_env(self):
        missing = []
        stt_provider = os.getenv("STT_PROVIDER", "deepgram")
        if stt_provider == "deepgram":
            if not os.getenv("DEEPGRAM_API_KEY"):
                missing.append("DEEPGRAM_API_KEY=your-deepgram-api-key")
        else:
            if not os.getenv("GCP_PROJECT_ID"):
                missing.append("GCP_PROJECT_ID=your-project-id")
            if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                missing.append("GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json")
        if not os.getenv("OPENAI_API_KEY"):
            missing.append("OPENAI_API_KEY=your-openai-api-key")

        if missing:
            messagebox.showwarning(
                "Setup Required",
                "Missing API keys. Please add to your .env file:\n\n"
                + "\n".join(missing)
                + "\n\nSee .env.example for reference.",
            )

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Header.TButton", font=("Segoe UI", 9), padding=(12, 4),
        )

        header = tk.Frame(self.root, bg=_C["header"], height=52)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header, text="LECTURE NOTETAKER",
            font=("Segoe UI", 13, "bold"),
            bg=_C["header"], fg=_C["header_text"],
        ).pack(side="left", padx=16)

        btn_frame = tk.Frame(header, bg=_C["header"])
        btn_frame.pack(side="right", padx=12)

        self.export_btn = ttk.Button(
            btn_frame, text="Export PDF", command=self._export_pdf,
            style="Header.TButton", state="disabled",
        )
        self.export_btn.pack(side="right", padx=3)

        _sep = tk.Frame(btn_frame, width=1, bg="#3D5A80")
        _sep.pack(side="right", fill="y", padx=8, pady=10)

        self.stop_btn = ttk.Button(
            btn_frame, text="\u25A0  Stop", command=self._stop,
            style="Header.TButton", state="disabled",
        )
        self.stop_btn.pack(side="right", padx=3)

        self.start_btn = ttk.Button(
            btn_frame, text="\u25B6  Start", command=self._start,
            style="Header.TButton", state="disabled",
        )
        self.start_btn.pack(side="right", padx=3)

        self.region_btn = ttk.Button(
            btn_frame, text="Select Region", command=self._select_region,
            style="Header.TButton",
        )
        self.region_btn.pack(side="right", padx=3)

        self.force_capture_btn = ttk.Button(
            btn_frame, text="Force Capture",
            command=self._force_capture,
            style="Header.TButton", state="disabled",
        )
        self.force_capture_btn.pack(side="right", padx=3)

        _sep2 = tk.Frame(btn_frame, width=1, bg="#3D5A80")
        _sep2.pack(side="right", fill="y", padx=8, pady=10)

        self.transcript_toggle_btn = ttk.Button(
            btn_frame, text="Show Transcript",
            command=self._toggle_transcript,
            style="Header.TButton",
        )
        self.transcript_toggle_btn.pack(side="right", padx=3)

        self.load_slides_btn = ttk.Button(
            btn_frame, text="Load Slides (PDF)", command=self._load_slides,
            style="Header.TButton",
        )
        self.load_slides_btn.pack(side="right", padx=3)

        status_bar = tk.Frame(self.root, bg="#E8EDF2", height=26)
        status_bar.pack(fill="x")
        status_bar.pack_propagate(False)

        self.status_var = tk.StringVar(
            value="Ready \u2014 Load a slide PDF or select a screen region to begin"
        )
        tk.Label(
            status_bar, textvariable=self.status_var,
            font=("Segoe UI", 9), bg="#E8EDF2", fg=_C["muted"],
            anchor="w",
        ).pack(side="left", padx=16, fill="x", expand=True)

        self.region_var = tk.StringVar(value="")
        tk.Label(
            status_bar, textvariable=self.region_var,
            font=("Segoe UI", 9), bg="#E8EDF2", fg=_C["muted"],
        ).pack(side="right", padx=16)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            status_bar, variable=self.progress_var,
            maximum=100, mode="determinate", length=200,
        )
        self.slides_info_var = tk.StringVar(value="")
        self.slides_info_label = tk.Label(
            status_bar, textvariable=self.slides_info_var,
            font=("Segoe UI", 8), bg="#E8EDF2", fg=_C["success"],
        )

        main_pane = tk.PanedWindow(
            self.root, orient="vertical", sashwidth=5,
            bg=_C["border"], sashrelief="flat",
        )
        main_pane.pack(fill="both", expand=True, padx=0, pady=0)
        self._main_pane = main_pane

        top_pane = tk.PanedWindow(
            main_pane, orient="horizontal", sashwidth=5,
            bg=_C["border"], sashrelief="flat",
        )
        self._top_pane = top_pane

        slide_panel = tk.Frame(top_pane, bg=_C["panel"])
        self._section_label(slide_panel, "CAPTURED SLIDE")

        canvas_frame = tk.Frame(slide_panel, bg=_C["slide_bg"])
        canvas_frame.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self.slide_canvas = tk.Canvas(
            canvas_frame, bg=_C["slide_bg"], highlightthickness=0,
        )
        self.slide_canvas.pack(fill="both", expand=True)

        counter_frame = tk.Frame(slide_panel, bg=_C["panel"])
        counter_frame.pack(fill="x", padx=12, pady=(0, 8))
        self.slide_var = tk.StringVar(value="No slides captured")
        tk.Label(
            counter_frame, textvariable=self.slide_var,
            font=("Segoe UI", 10, "bold"), bg=_C["panel"], fg=_C["text"],
        ).pack(side="left")

        top_pane.add(slide_panel, minsize=280)

        live_panel = tk.Frame(top_pane, bg=_C["panel"])
        self._section_label(live_panel, "LIVE DICTATION")

        l_container = tk.Frame(live_panel, bg="#FAFBFC")
        l_container.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        l_container.grid_rowconfigure(0, weight=1)
        l_container.grid_columnconfigure(0, weight=1)

        self.live_text = tk.Text(
            l_container, wrap="word", state="disabled",
            font=("Consolas", 10), bg="#FAFBFC", fg=_C["text"],
            padx=8, pady=8, relief="flat", borderwidth=0,
        )
        l_scroll = ttk.Scrollbar(l_container, command=self.live_text.yview)
        self.live_text.config(yscrollcommand=l_scroll.set)
        self.live_text.grid(row=0, column=0, sticky="nsew")
        l_scroll.grid(row=0, column=1, sticky="ns")

        self.live_text.tag_configure(
            "slide_sep", font=("Segoe UI", 9, "bold"),
            foreground=_C["accent"], spacing1=10, spacing3=4,
        )
        self.live_text.tag_configure(
            "final", font=("Consolas", 10), foreground=_C["text"],
        )
        self.live_text.tag_configure(
            "interim", font=("Consolas", 10, "italic"), foreground=_C["muted"],
        )
        self.live_text.tag_configure(
            "frozen", font=("Consolas", 10), foreground=_C["muted"],
        )

        top_pane.add(live_panel, minsize=300)
        main_pane.add(top_pane, minsize=220)

        bottom_pane = tk.PanedWindow(
            main_pane, orient="horizontal", sashwidth=5,
            bg=_C["border"], sashrelief="flat",
        )
        self._bottom_pane = bottom_pane

        transcript_panel = tk.Frame(bottom_pane, bg=_C["panel"])
        self._transcript_panel = transcript_panel
        self._section_label(transcript_panel, "TRANSCRIPT")

        t_container = tk.Frame(transcript_panel, bg=_C["panel"])
        t_container.pack(fill="both", expand=True, padx=0, pady=0)
        t_container.grid_rowconfigure(0, weight=1)
        t_container.grid_columnconfigure(0, weight=1)

        self.transcript_text = tk.Text(
            t_container, wrap="word", state="disabled",
            font=("Segoe UI", 10), bg=_C["panel"], fg=_C["text"],
            padx=12, pady=8, relief="flat", borderwidth=0,
        )
        t_scroll = ttk.Scrollbar(t_container, command=self.transcript_text.yview)
        self.transcript_text.config(yscrollcommand=t_scroll.set)
        self.transcript_text.grid(row=0, column=0, sticky="nsew")
        t_scroll.grid(row=0, column=1, sticky="ns")

        self.transcript_text.tag_configure(
            "slide_sep", font=("Segoe UI", 9, "bold"),
            foreground=_C["accent"], spacing1=10, spacing3=4,
        )
        self.transcript_text.tag_configure(
            "final", font=("Segoe UI", 10), foreground=_C["text"],
        )

        refined_panel = tk.Frame(bottom_pane, bg=_C["panel"])
        self._refined_panel = refined_panel
        self._section_label(refined_panel, "REFINED TRANSCRIPT")

        r_container = tk.Frame(refined_panel, bg=_C["panel"])
        r_container.pack(fill="both", expand=True, padx=0, pady=0)
        r_container.grid_rowconfigure(0, weight=1)
        r_container.grid_columnconfigure(0, weight=1)

        self.refined_text = tk.Text(
            r_container, wrap="word", state="disabled",
            font=("Segoe UI", 10), bg=_C["panel"], fg=_C["text"],
            padx=12, pady=8, relief="flat", borderwidth=0,
        )
        r_scroll = ttk.Scrollbar(r_container, command=self.refined_text.yview)
        self.refined_text.config(yscrollcommand=r_scroll.set)
        self.refined_text.grid(row=0, column=0, sticky="nsew")
        r_scroll.grid(row=0, column=1, sticky="ns")

        self.refined_text.tag_configure(
            "slide_sep", font=("Segoe UI", 9, "bold"),
            foreground=_C["accent"], spacing1=10, spacing3=4,
        )
        self.refined_text.tag_configure(
            "final", font=("Segoe UI", 10), foreground=_C["text"],
        )
        self.refined_text.tag_configure(
            "refining", font=("Segoe UI", 9, "italic"),
            foreground=_C["muted"],
        )

        bottom_pane.add(refined_panel, minsize=250)
        main_pane.add(bottom_pane, minsize=140)

        def _set_sashes(event=None):
            self.root.update_idletasks()
            h = main_pane.winfo_height()
            w = top_pane.winfo_width()
            if h > 100 and w > 100:
                main_pane.sash_place(0, 0, int(h * 0.45))
                top_pane.sash_place(0, int(w * 0.42), 0)
                self.root.unbind("<Map>")

        self.root.bind("<Map>", _set_sashes)

    def _section_label(self, parent, text):
        """Create a McKinsey-style section header with subtle underline."""
        frame = tk.Frame(parent, bg=_C["panel"])
        frame.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(
            frame, text=text, font=("Segoe UI", 9, "bold"),
            bg=_C["panel"], fg=_C["muted"],
        ).pack(anchor="w")
        tk.Frame(frame, height=1, bg=_C["border"]).pack(fill="x", pady=(3, 0))

    def _load_slides(self):
        path = filedialog.askopenfilename(
            title="Select Slide PDF",
            filetypes=[("PDF files", "*.pdf")],
        )
        if path:
            self.load_slides_btn.config(state="disabled")
            self.controller.load_slides_pdf(path)

    def _select_region(self):
        self.controller.select_region()

    def _start(self):
        self.start_btn.config(state="disabled")
        self.region_btn.config(state="disabled")
        self.load_slides_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.force_capture_btn.config(state="normal")
        self.controller.start_capture()

    def _stop(self):
        self.stop_btn.config(state="disabled")
        self.force_capture_btn.config(state="disabled")
        self.start_btn.config(state="normal")
        self.region_btn.config(state="normal")
        self.load_slides_btn.config(state="normal")
        self.export_btn.config(state="normal")
        self.controller.stop_capture()

    def _export_pdf(self):
        path = filedialog.asksaveasfilename(
            title="Export PDF", defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile="lecture_notes.pdf",
        )
        if path:
            self.controller.export_pdf(path)

    def _force_capture(self):
        self.controller.force_capture()

    def _toggle_transcript(self):
        """Show/hide the transcript panel."""
        if self._transcript_visible:
            self._bottom_pane.forget(self._transcript_panel)
            self._transcript_visible = False
            self.transcript_toggle_btn.config(text="Show Transcript")
        else:
            self._bottom_pane.forget(self._refined_panel)
            self._bottom_pane.add(self._transcript_panel, minsize=250)
            self._bottom_pane.add(self._refined_panel, minsize=250)
            self._transcript_visible = True
            self.transcript_toggle_btn.config(text="Hide Transcript")
            self.root.update_idletasks()
            w = self._bottom_pane.winfo_width()
            if w > 100:
                self._bottom_pane.sash_place(0, int(w * 0.4), 0)

    def set_region_info(self, region: tuple[int, int, int, int]):
        left, top, w, h = region
        self.root.after(0, lambda: (
            self.region_var.set(f"Region: ({left},{top}) {w}\u00d7{h}"),
            self.start_btn.config(state="normal"),
        ))

    def display_slide_image(self, image):
        """Display a captured screen image on the canvas."""
        def _update():
            try:
                if isinstance(image, bytes):
                    img = Image.open(io.BytesIO(image))
                else:
                    img = image.copy()
                canvas_w = self.slide_canvas.winfo_width()
                canvas_h = self.slide_canvas.winfo_height()
                if canvas_w < 10 or canvas_h < 10:
                    canvas_w, canvas_h = 450, 350
                img_w, img_h = img.size
                scale = min(canvas_w / img_w, canvas_h / img_h)
                new_w = int(img_w * scale)
                new_h = int(img_h * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                self._slide_photo = ImageTk.PhotoImage(img)
                self.slide_canvas.delete("all")
                self.slide_canvas.create_image(
                    canvas_w // 2, canvas_h // 2,
                    image=self._slide_photo, anchor="center",
                )
            except Exception as e:
                logger.warning("Failed to display slide: %s", e)
        self.root.after(0, _update)

    def update_slide(self, slide_num: int, total: int):
        self.root.after(
            0, lambda: self.slide_var.set(f"Slide {slide_num + 1} / {total}")
        )

    def live_add_separator(self, slide_idx: int):
        """Add slide separator to the live dictation panel."""
        def _update():
            self.live_text.config(state="normal")
            self._remove_interim()
            if slide_idx > 0:
                self.live_text.insert("end", "\n")
            self.live_text.insert(
                "end",
                f"\u2500\u2500\u2500  Slide {slide_idx + 1}  \u2500\u2500\u2500\n",
                "slide_sep",
            )
            self.live_text.see("end")
            self.live_text.config(state="disabled")
        self.root.after(0, _update)

    def live_update_interim(self, text: str):
        """Show/update the current interim text (gray) at end of live panel.

        Uses tag-based removal so only interim-tagged text is deleted — never
        separators or finals that may have been inserted after the interim.
        """
        def _update():
            self.live_text.config(state="normal")
            self._remove_interim()
            if text.strip():
                self.live_text.insert("end", text, "interim")
                self._has_interim = True
            self.live_text.see("end")
            self.live_text.config(state="disabled")
        self.root.after(0, _update)

    def live_commit_final(self, text: str, slide_idx: int = -1):
        """Remove interim preview, insert the confirmed final text.

        If slide_idx is given, ensures text goes under that slide's separator
        (not after a newer separator added during a slide transition).
        """
        def _update():
            self.live_text.config(state="normal")
            self._remove_interim()
            insert_pos = "end"

            if slide_idx >= 0:
                next_sep = f"\u2500\u2500\u2500  Slide {slide_idx + 2}  \u2500\u2500\u2500"
                found = self.live_text.search(next_sep, "1.0", "end")
                if found:
                    line_num = int(found.split('.')[0])
                    insert_pos = f"{line_num}.0"

            self.live_text.insert(insert_pos, text + "\n", "final")
            self.live_text.see("end")
            self.live_text.config(state="disabled")
        self.root.after(0, _update)

    def _remove_interim(self):
        """Remove ONLY interim-tagged text. Safe: never touches finals or separators."""
        if self._has_interim:
            ranges = self.live_text.tag_ranges("interim")
            pairs = [(str(ranges[i]), str(ranges[i + 1]))
                     for i in range(0, len(ranges), 2)]
            for start, end in reversed(pairs):
                self.live_text.delete(start, end)
            self._has_interim = False

    def clear_live(self):
        """Clear the live dictation panel for a new session."""
        def _update():
            self.live_text.config(state="normal")
            self.live_text.delete("1.0", "end")
            self._has_interim = False
            self.live_text.config(state="disabled")
        self.root.after(0, _update)

    def transcript_add_separator(self, slide_idx: int):
        """Add slide separator to the transcript panel."""
        def _update():
            self.transcript_text.config(state="normal")
            if slide_idx > 0:
                self.transcript_text.insert("end", "\n")
            self.transcript_text.insert(
                "end",
                f"\u2500\u2500\u2500  Slide {slide_idx + 1}  \u2500\u2500\u2500\n",
                "slide_sep",
            )
            self.transcript_text.see("end")
            self.transcript_text.config(state="disabled")
        self.root.after(0, _update)

    def transcript_append(self, text: str, slide_idx: int = -1):
        """Append postprocessed Korean text under the correct slide section."""
        def _update():
            self.transcript_text.config(state="normal")
            insert_pos = "end"

            if slide_idx >= 0:
                next_sep = f"\u2500\u2500\u2500  Slide {slide_idx + 2}  \u2500\u2500\u2500"
                found = self.transcript_text.search(next_sep, "1.0", "end")
                if found:
                    line_num = int(found.split('.')[0])
                    insert_pos = f"{line_num}.0"

            self.transcript_text.insert(insert_pos, text + "\n", "final")
            self.transcript_text.see("end")
            self.transcript_text.config(state="disabled")
        self.root.after(0, _update)

    def clear_transcript(self):
        """Clear the transcript panel for a new session."""
        def _update():
            self.transcript_text.config(state="normal")
            self.transcript_text.delete("1.0", "end")
            self.transcript_text.config(state="disabled")
        self.root.after(0, _update)

    def refined_add_separator(self, slide_idx: int):
        """Add slide separator to the refined panel."""
        def _update():
            self._clear_listening()
            self.refined_text.config(state="normal")
            if slide_idx > 0:
                self.refined_text.insert("end", "\n")
            self.refined_text.insert(
                "end",
                f"\u2500\u2500\u2500  Slide {slide_idx + 1}  \u2500\u2500\u2500\n",
                "slide_sep",
            )
            self.refined_text.see("end")
            self.refined_text.config(state="disabled")
        self.root.after(0, _update)

    def refined_append(self, text: str, slide_idx: int = -1):
        """Append refined text under the correct slide section.

        If slide_idx is given, ensures text goes under that slide's separator
        (not after a newer separator added while LLM was processing).
        """
        def _update():
            self._clear_listening()
            self.refined_text.config(state="normal")
            insert_pos = "end"

            if slide_idx >= 0:
                next_sep = f"\u2500\u2500\u2500  Slide {slide_idx + 2}  \u2500\u2500\u2500"
                found = self.refined_text.search(next_sep, "1.0", "end")
                if found:
                    line_num = int(found.split('.')[0])
                    insert_pos = f"{line_num}.0"

            self.refined_text.insert(insert_pos, text + "\n", "final")
            self.refined_text.see("end")
            self.refined_text.config(state="disabled")
        self.root.after(0, _update)

    def refined_show_pending(self, text: str = "Refining..."):
        """Show a temporary 'refining' indicator."""
        def _update():
            self.refined_text.config(state="normal")
            self.refined_text.insert("end", f"  {text}\n", "refining")
            self.refined_text.see("end")
            self.refined_text.config(state="disabled")
        self.root.after(0, _update)

    def refined_replace_all(self, slide_texts: dict[int, str]):
        """Replace all refined text with finalized versions."""
        def _update():
            self.refined_text.config(state="normal")
            self.refined_text.delete("1.0", "end")
            for slide_idx in sorted(slide_texts.keys()):
                if slide_idx > 0:
                    self.refined_text.insert("end", "\n")
                self.refined_text.insert(
                    "end",
                    f"\u2500\u2500\u2500  Slide {slide_idx + 1}  \u2500\u2500\u2500\n",
                    "slide_sep",
                )
                self.refined_text.insert("end", slide_texts[slide_idx] + "\n", "final")
            self.refined_text.see("end")
            self.refined_text.config(state="disabled")
        self.root.after(0, _update)

    def clear_refined(self):
        """Clear the refined panel for a new session."""
        def _update():
            self.refined_text.config(state="normal")
            self.refined_text.delete("1.0", "end")
            self.refined_text.config(state="disabled")
        self.root.after(0, _update)

    def show_listening_indicator(self):
        """Show a 'Listening...' indicator in the refined panel."""
        def _update():
            self._listening_shown = True
            self.refined_text.config(state="normal")
            self.refined_text.delete("1.0", "end")
            self.refined_text.insert(
                "1.0",
                "\nListening for speech...\n"
                "Refined transcript will appear here as you speak.\n",
                "refining",
            )
            self.refined_text.config(state="disabled")
        self.root.after(0, _update)

    def _clear_listening(self):
        """Remove the listening indicator if still shown. Call from main thread."""
        if self._listening_shown:
            self._listening_shown = False
            self.refined_text.config(state="normal")
            self.refined_text.delete("1.0", "end")
            self.refined_text.config(state="disabled")

    def update_status(self, status: str):
        self.root.after(0, lambda: self.status_var.set(status))

    def show_progress(self, current: int, total: int):
        def _update():
            if total <= 0:
                self.progress_bar.pack(side="right", padx=8)
                self.progress_var.set(0)
                return
            pct = (current / total) * 100
            self.progress_var.set(pct)
            if current <= 1:
                self.progress_bar.pack(side="right", padx=8)
            if current >= total:
                self.progress_bar.pack_forget()
        self.root.after(0, _update)

    def set_slides_loaded_info(self, text: str):
        def _update():
            self.slides_info_var.set(text)
            if text:
                self.slides_info_label.pack(side="left", padx=(16, 0))
            else:
                self.slides_info_label.pack_forget()
        self.root.after(0, _update)

    def enable_load_slides_btn(self):
        self.root.after(0, lambda: self.load_slides_btn.config(state="normal"))

    def show_error(self, title: str, message: str):
        self.root.after(0, lambda: messagebox.showerror(title, message))

    def run(self):
        self.root.mainloop()
