import io
import logging

import pymupdf
from PIL import Image

logger = logging.getLogger(__name__)


class SlideData:
    """Data for one captured slide."""
    def __init__(self, slide_num: int, image: Image.Image,
                 notes: list[str] | None = None,
                 transcript: str = ""):
        self.slide_num = slide_num
        self.image = image
        self.notes = notes or []
        self.transcript = transcript


class PDFExporter:
    """Compiles captured slides + notes + highlighted transcript into a PDF."""

    FONT_FAMILY = "'Malgun Gothic', '맑은 고딕', sans-serif"

    def __init__(self, config):
        self.font_size = config.note_font_size
        r, g, b = config.note_font_color
        self.font_color_hex = "#{:02x}{:02x}{:02x}".format(
            int(r * 255), int(g * 255), int(b * 255)
        )

    @staticmethod
    def _escape_html(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _notes_to_html(self, notes: list[str]) -> str:
        """Convert bullet-point notes to HTML."""
        items = "".join(
            f"<li>{self._escape_html(note)}</li>" for note in notes
        )
        return (
            f'<div style="font-family:{self.FONT_FAMILY};font-size:{self.font_size}pt;'
            f"color:{self.font_color_hex};"
            f'line-height:1.4;">'
            f'<b>Summary:</b>'
            f'<ul style="margin:2pt 0; padding-left:14pt;">'
            f"{items}</ul></div>"
        )

    def export(self, output_path: str, slides: list[SlideData],
               on_progress: callable = None):
        """Export all slides to a single PDF with high-resolution images.

        Args:
            output_path: Path for the output PDF
            slides: List of SlideData objects
            on_progress: Optional callback(current, total) for progress updates
        """
        if not slides:
            logger.warning("No slides to export")
            return

        doc = pymupdf.open()

        for i, slide in enumerate(slides):
            if on_progress:
                on_progress(i + 1, len(slides))

            buf = io.BytesIO()
            slide.image.save(buf, format="JPEG", quality=85)
            img_bytes = buf.getvalue()

            img_w, img_h = slide.image.size
            page_w = 792
            img_scale = page_w / img_w
            img_display_h = img_h * img_scale

            notes_space = 350
            page_h = img_display_h + notes_space
            page_h = max(page_h, 842)

            page = doc.new_page(width=page_w, height=page_h)

            header_rect = pymupdf.Rect(10, 5, page_w - 10, 20)
            page.insert_htmlbox(
                header_rect,
                f'<div style="font-family:{self.FONT_FAMILY};font-size:8pt;color:#666666;">'
                f'Slide {slide.slide_num + 1} / {len(slides)}</div>',
            )

            img_rect = pymupdf.Rect(0, 20, page_w, 20 + img_display_h)
            page.insert_image(img_rect, stream=img_bytes)

            content_top = 20 + img_display_h + 8
            content_rect = pymupdf.Rect(20, content_top, page_w - 20, page_h - 15)

            html_parts = []

            if slide.notes:
                html_parts.append(self._notes_to_html(slide.notes))

            if slide.transcript:
                html_parts.append(
                    f'<div style="font-family:{self.FONT_FAMILY};font-size:{self.font_size}pt;'
                    f'line-height:1.5;margin-top:4pt;">'
                    f'<b style="color:{self.font_color_hex};">Refined Notes:</b><br/>'
                    f'{self._escape_html(slide.transcript)}</div>'
                )

            if html_parts:
                combined_html = "".join(html_parts)
                page.insert_htmlbox(content_rect, combined_html, scale_low=0.4)

            logger.info("Exported slide %d/%d", i + 1, len(slides))

        doc.subset_fonts()
        doc.save(output_path, garbage=3, deflate=True)
        doc.close()
        logger.info("PDF exported to %s (%d slides)", output_path, len(slides))
