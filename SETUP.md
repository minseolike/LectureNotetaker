# Lecture Notetaker - Setup Guide

## Option A: Run the Pre-built Executable (Recommended)

### 1. Copy the folder
Copy the entire `LectureNotetaker` folder to the target computer.

### 2. Set up API keys
Copy `.env.example` to `.env` **in the same folder as `LectureNotetaker.exe`** and fill in your API keys:

```
STT_PROVIDER=deepgram
DEEPGRAM_API_KEY=your-key-here
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 3. Set up Google Cloud (optional, only if using Google STT)
If using Google Chirp 3 as STT provider:
1. Place your GCP service account JSON file in the app folder
2. Set `GOOGLE_APPLICATION_CREDENTIALS=./service-account.json` in `.env`
3. Set `STT_PROVIDER=google` in `.env`

### 4. Run
Double-click `LectureNotetaker.exe`.

---

## Option B: Run from Source Code

### Requirements
- Windows 10 or later
- Python 3.11+

### 1. Clone or copy the project
```bash
git clone <repo-url>
cd Notetaking
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up API keys
```bash
copy .env.example .env
```
Edit `.env` with your API keys (see Option A step 2).

### 4. Run
```bash
python main.py
```

---

## Building the Executable Yourself

```bash
pip install pyinstaller
python build.py
```

The output will be in `dist/LectureNotetaker/`. Copy this entire folder to any Windows PC.

---

## API Keys You Need

| Service | Required? | Purpose | Get it at |
|---------|-----------|---------|-----------|
| Deepgram | Yes (default STT) | Real-time speech-to-text | https://console.deepgram.com/ |
| OpenAI | Yes | Screen analysis + note refinement | https://platform.openai.com/api-keys |
| Anthropic | Optional | PDF polish step | https://console.anthropic.com/ |
| Google Cloud | Optional | Fallback STT (Chirp 3) | https://console.cloud.google.com/ |

## Important
- **`.env` must be in the same folder as `LectureNotetaker.exe`** — the app looks for it right next to the executable, not anywhere else
- **No path changes needed** — all paths are relative, works from any folder on any PC
- Windows only (uses WASAPI for system audio capture)
