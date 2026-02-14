"""PyInstaller build script for Lecture Notetaker."""

import PyInstaller.__main__
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def build():
    icon_path = os.path.join(BASE_DIR, "app_icon.ico")

    args = [
        os.path.join(BASE_DIR, "main.py"),
        "--name", "LectureNotetaker",
        "--onedir",
        "--windowed",
        *(["--icon", icon_path] if os.path.exists(icon_path) else []),
        "--add-data", f"{os.path.join(BASE_DIR, 'medical', 'terms.py')};medical",
        "--add-data", f"{os.path.join(BASE_DIR, '.env.example')};.",
        *(["--add-data", f"{icon_path};."] if os.path.exists(icon_path) else []),
        "--hidden-import", "google.cloud.speech_v2",
        "--hidden-import", "google.auth",
        "--hidden-import", "google.auth.transport.grpc",
        "--hidden-import", "google.auth.transport.requests",
        "--hidden-import", "grpc",
        "--hidden-import", "openai",
        "--hidden-import", "pydantic",
        "--hidden-import", "mss",
        "--hidden-import", "imagehash",
        "--hidden-import", "rapidfuzz",
        "--hidden-import", "websocket",
        "--hidden-import", "anthropic",
        "--hidden-import", "PIL",
        "--hidden-import", "numpy",
        "--collect-all", "google.cloud.speech_v2",
        "--collect-all", "openai",
        "--collect-all", "anthropic",
        "--collect-all", "pymupdf",
        "--collect-all", "mss",
        "--collect-all", "websocket",
        "--clean",
        "--noconfirm",
    ]

    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    build()
