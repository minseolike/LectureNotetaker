# Lecture Notetaker

Real-time lecture transcription system that understands your slides and medical terminology — outputting study-ready annotated PDFs.

## The Problem

Medical students watch hours of recorded lectures and need accurate, structured notes. Existing tools fall short:

- **Generic transcription fails on medical terms** — tools like Otter.ai have no domain knowledge, dropping accuracy on specialized vocabulary
- **Korean-English code-switching is unsupported** — professors say English terms phonetically in Korean (e.g., "오스테오포로시스" for "osteoporosis"), and no generic STT can handle this
- **No slide awareness** — existing tools produce flat transcripts with no connection to the slides being discussed
- **Hours of manual cleanup** — students spend as much time correcting and organizing transcripts as they spent watching the lecture

Lecture Notetaker solves all of these by combining domain-specific STT, slide-aware AI refinement, and direct PDF annotation into a single pipeline.

## How It Works

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Pre-analyze │───▶│ Capture Audio│───▶│  Transcribe  │───▶│   Refine     │
│  Lecture PDF │    │ (WASAPI)     │    │ (Deepgram)   │    │  (4-stage)   │
└─────────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘
      │                                                          │
      │  Vision AI reads each slide,                             ▼
      │  extracts terms + phonetic mappings              ┌──────────────┐
      └─────────────────────────────────────────────────▶│ Export PDF    │
                                                         │ (annotated)  │
                                                         └──────────────┘
```

1. **Pre-analyze** your lecture PDF — Vision AI reads every slide once, extracting terms, concepts, and Korean-to-English phonetic mappings
2. **Capture** system audio during the lecture (WASAPI loopback — no microphone needed)
3. **Transcribe** in real-time with Deepgram Nova-2, boosted with 570+ medical terms
4. **Track slides** — press Page Down when the lecturer advances; each transcript segment is tagged to its slide
5. **Refine** through a 4-stage LLM pipeline:
   - Convert Korean phonetic transliterations to English medical terms (using slide context)
   - Smooth and proofread across slide boundaries
   - Medical polish — formal academic style, structured formatting
   - Generate concise bullet-point summaries per slide
6. **Export** — annotated PDF with slide images, polished notes, and summaries in the margins

## What Makes This Different

| | Lecture Notetaker | Otter.ai / Generic STT |
|---|---|---|
| **Medical terms** | 570+ terms boosted in STT engine | No domain optimization |
| **Slide awareness** | Each note tied to its slide with Vision AI context | Flat transcript, no slide context |
| **Korean + English** | Phonetic mapping (오스테오포로시스 → osteoporosis) | Cannot handle code-switching |
| **Refinement** | 4-stage LLM pipeline with medical knowledge | Single-pass or none |
| **Output** | Annotated PDF with slide images + notes | Plain text transcript |
| **Open source** | MIT License, fully customizable | Proprietary, closed |

## Features

- **System audio capture** (WASAPI loopback) — no microphone needed
- **Real-time Korean + English transcription** via Deepgram Nova-2 (primary) or Google Chirp 3 (fallback)
- **Medical terminology boosting** — 570+ medical terms across pathology, physiology, pharmacology, immunology, biochemistry, clinical medicine
- **AI-powered slide analysis** — OpenAI Vision reads and understands each slide
- **Smart note refinement** — LLM-based transcript cleanup with slide context
- **PDF polish** — Anthropic Claude produces medical-grade lecture notes
- **Direct PDF annotation** — notes appear in slide margins with Korean font support

## Tips for Best Results

- **Pre-analyze first** — always run "Analyze Slides" before starting capture. This builds the term dictionary that powers accurate transcription
- **Advance slides in sync** — press Page Down when the lecturer changes slides so notes are correctly grouped
- **Use F5 for long slides** — if a lecturer stays on one slide for a long time, press F5 to flush accumulated notes mid-slide
- **Add course-specific terms** — edit `medical/terms.py` with terms specific to your current course for better recognition
- **Quiet audio environment** — since it captures system audio, close other audio sources (music, notifications) during lectures

## Quick Start

### Prerequisites
- Deepgram API key (primary STT)
- OpenAI API key (screen analysis + note refinement)
- Anthropic API key (optional, for PDF polish)
- Google Cloud account (optional, fallback STT)

### Setup

1. Copy `.env.example` to `.env` and fill in your API keys:
   ```
   STT_PROVIDER=deepgram
   DEEPGRAM_API_KEY=your-deepgram-key
   OPENAI_API_KEY=sk-your-openai-key
   ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run:
   ```
   python main.py
   ```

### Usage

1. Click **Browse** to select your lecture PDF
2. Click **Analyze Slides** — Vision API processes each slide (one-time)
3. Start playing your lecture video
4. Click **Start Capture** to begin transcription
5. Press **Page Down** when the lecturer advances slides
6. Press **F5** to manually flush notes for the current slide
7. Click **Stop & Save** when done — annotated PDF saved as `*_noted.pdf`

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Page Down | Next slide (flushes current slide notes) |
| Page Up | Previous slide |
| F5 | Flush notes for current slide now |

## Building Portable Executable

```
python build.py
```

Output: `dist/LectureNotetaker/` folder with standalone `.exe`.

To use on another computer:
1. Copy the `LectureNotetaker/` folder
2. Create `.env` with API keys
3. Place service account JSON in the folder (if using Google STT)
4. Run `LectureNotetaker.exe`

## Adding Custom Medical Terms

Edit `medical/terms.py` to add terms specific to your courses:
```python
CUSTOM_TERMS = [
    ("your term", 15),  # (term, boost_value 10-20)
]
```

## Architecture

```
System Audio → WASAPI Loopback → Deepgram Nova-2 STT → Transcript Buffer
                                                            ↓
                                          OpenAI Refiner ← OpenAI Vision (slide context)
                                                            ↓
                                                  Claude Polish → PyMuPDF → Annotated PDF
```

## Built With

**Language:** Python

**Key Libraries:** Tkinter (GUI), PyMuPDF (PDF annotation), pyaudiowpatch (WASAPI audio capture)

**APIs:** Deepgram (STT), OpenAI (Vision + refinement), Google Cloud Speech (fallback STT), Anthropic (PDF polish)

**AI Assistance:** Claude — Assisted with architectural design, debugging, and code optimization.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
