import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")
    gcp_region: str = os.getenv("GCP_REGION", "us")
    stt_model: str = "chirp_3"
    stt_language_codes: list[str] = field(
        default_factory=lambda: ["ko-KR", "en-US"]
    )
    stt_stream_timeout_sec: int = 290

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model_vision: str = "gpt-4o-mini"
    openai_model_writer: str = "gpt-4o-mini"

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    audio_chunk_duration_ms: int = 100

    screen_poll_interval_sec: float = 3.0
    screen_change_threshold_pct: int = 15

    stt_provider: str = os.getenv("STT_PROVIDER", "deepgram")
    deepgram_api_key: str = os.getenv("DEEPGRAM_API_KEY", "")

    note_font_size: int = 9
    note_font_color: tuple = (0.15, 0.15, 0.15)

    pdf_output_path: str = ""
