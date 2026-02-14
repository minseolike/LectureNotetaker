"""File-based audio test: feeds a pre-recorded audio file through the STT pipeline.

Bypasses WASAPI loopback so we can test with YouTube lecture audio.
Requires: DEEPGRAM_API_KEY in .env, ffmpeg (via imageio-ffmpeg).

Usage:
    python -m tests.test_file_audio test_audio/lecture_sample.m4a
    python -m tests.test_file_audio test_audio/lecture_sample.m4a --duration 60
    python -m tests.test_file_audio test_audio/lecture_sample.m4a --refine
"""

import argparse
import json
import logging
import os
import queue
import struct
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from config import Config
from stt.postprocess import TranscriptPostProcessor
from stt.refiner import TranscriptRefiner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def get_ffmpeg_path() -> str:
    """Get ffmpeg binary path."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    import shutil
    path = shutil.which("ffmpeg")
    if path:
        return path
    raise RuntimeError(
        "ffmpeg not found. Install via: pip install imageio-ffmpeg"
    )


def decode_audio_to_pcm(input_path: str, sample_rate: int = 48000,
                         duration: float = 0) -> bytes:
    """Decode any audio file to raw PCM (mono, 16-bit, given sample rate).

    Args:
        input_path: Path to audio file (m4a, mp3, wav, etc.)
        sample_rate: Target sample rate in Hz
        duration: Max seconds to decode (0 = full file)

    Returns:
        Raw PCM bytes (mono, int16, little-endian)
    """
    ffmpeg = get_ffmpeg_path()
    cmd = [
        ffmpeg, "-i", input_path,
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-loglevel", "error",
    ]
    if duration > 0:
        cmd.extend(["-t", str(duration)])
    cmd.append("-")

    logger.info("Decoding audio: %s (rate=%d, duration=%s)",
                input_path, sample_rate, duration or "full")

    result = subprocess.run(cmd, capture_output=True, check=True)
    pcm_data = result.stdout
    seconds = len(pcm_data) / (sample_rate * 2)
    logger.info("Decoded %.1f seconds of audio (%d bytes)", seconds, len(pcm_data))
    return pcm_data


def feed_audio_to_deepgram(pcm_data: bytes, config: Config,
                            sample_rate: int = 48000,
                            chunk_ms: int = 100) -> list[dict]:
    """Send PCM audio to Deepgram and collect transcripts.

    Args:
        pcm_data: Raw PCM bytes (mono, int16)
        config: Config with Deepgram API key
        sample_rate: Sample rate of PCM data
        chunk_ms: Chunk size in milliseconds

    Returns:
        List of transcript dicts: {text, is_final, words, confidence, time}
    """
    from stt.deepgram_streaming import DeepgramStreamingSTT

    audio_queue = queue.Queue(maxsize=5000)
    results = []
    results_lock = threading.Lock()
    done_event = threading.Event()

    def on_transcript(text, is_final, words=None, confidence=1.0):
        with results_lock:
            results.append({
                "text": text,
                "is_final": is_final,
                "words": words,
                "confidence": confidence,
                "time": time.monotonic(),
            })
            if is_final:
                conf_str = f"[{confidence:.2f}]" if confidence < 1.0 else ""
                print(f"  {'FINAL' if is_final else 'interim'}: {text} {conf_str}")

    stt = DeepgramStreamingSTT(
        config, audio_queue, on_transcript,
        on_error=lambda msg: logger.warning("STT error: %s", msg),
        sample_rate=sample_rate,
    )

    from medical.terms import format_for_deepgram
    keywords = format_for_deepgram()
    if keywords:
        stt._keywords = keywords[:200]
        logger.info("Loaded %d keywords for Deepgram boosting", len(stt._keywords))

    stt.start()

    logger.info("Waiting for Deepgram connection...")
    stt._ws_ready.wait(timeout=10)
    if not stt._ws_ready.is_set():
        raise RuntimeError("Deepgram connection timeout")
    logger.info("Deepgram connected. Feeding audio...")

    chunk_bytes = int(sample_rate * 2 * chunk_ms / 1000)
    total_chunks = len(pcm_data) // chunk_bytes
    chunk_interval = chunk_ms / 1000.0

    start_time = time.monotonic()
    for i in range(0, len(pcm_data), chunk_bytes):
        chunk = pcm_data[i:i + chunk_bytes]
        if not chunk:
            break
        try:
            audio_queue.put(chunk, timeout=1.0)
        except queue.Full:
            logger.warning("Audio queue full, dropping chunk")

        elapsed = time.monotonic() - start_time
        expected = (i // chunk_bytes) * chunk_interval / 1.5
        if elapsed < expected:
            time.sleep(expected - elapsed)

    logger.info("Audio feed complete. Waiting for final transcripts...")
    time.sleep(3.0)

    stt.stop()
    time.sleep(0.5)

    return results


def run_postprocess(results: list[dict], config: Config) -> list[dict]:
    """Run post-processing on transcript results."""
    postprocessor = TranscriptPostProcessor()

    processed = []
    for r in results:
        if r["is_final"]:
            original = r["text"]
            fixed = postprocessor.process(original)
            processed.append({
                **r,
                "original": original,
                "text": fixed,
                "changed": original != fixed,
            })

    return processed


def run_refinement(processed: list[dict], config: Config) -> list[dict]:
    """Run LLM refinement on processed transcripts."""
    refiner = TranscriptRefiner(config)

    refined = []
    for i, p in enumerate(processed):
        original = p["text"]
        try:
            result = refiner.refine(original)
            refined.append({
                **p,
                "pre_refine": original,
                "text": result,
                "refined_changed": original != result,
            })
            if original != result:
                print(f"  Refined [{i}]: {original}")
                print(f"       →  : {result}")
        except Exception as e:
            logger.warning("Refinement failed for segment %d: %s", i, e)
            refined.append({**p, "pre_refine": original, "refined_changed": False})

    return refined


def print_summary(results: list[dict], processed: list[dict],
                  refined: list[dict] | None = None):
    """Print a summary of the test results."""
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    finals = [r for r in results if r["is_final"]]
    interims = [r for r in results if not r["is_final"]]

    print(f"\nTotal messages: {len(results)}")
    print(f"  Final: {len(finals)}")
    print(f"  Interim: {len(interims)}")

    if finals:
        confidences = [r["confidence"] for r in finals]
        print(f"\nConfidence stats (finals):")
        print(f"  Min: {min(confidences):.3f}")
        print(f"  Max: {max(confidences):.3f}")
        print(f"  Avg: {sum(confidences)/len(confidences):.3f}")

        low_conf = [r for r in finals if r["confidence"] < 0.4]
        very_low = [r for r in finals if r["confidence"] < 0.15]
        print(f"  Low confidence (<0.4): {len(low_conf)}")
        print(f"  Very low (<0.15, would be skipped): {len(very_low)}")

    if processed:
        changed = [p for p in processed if p.get("changed")]
        print(f"\nPost-processing:")
        print(f"  Total segments: {len(processed)}")
        print(f"  Changed by postprocessor: {len(changed)}")
        if changed:
            print(f"  Examples of changes:")
            for p in changed[:5]:
                print(f"    '{p['original']}' → '{p['text']}'")

    if refined:
        ref_changed = [r for r in refined if r.get("refined_changed")]
        print(f"\nRefinement:")
        print(f"  Changed by refiner: {len(ref_changed)}/{len(refined)}")

    print(f"\n{'=' * 70}")
    print("FULL TRANSCRIPT (post-processed)")
    print("=" * 70)
    for p in processed:
        marker = " *" if p.get("changed") else ""
        print(f"  {p['text']}{marker}")

    if refined:
        print(f"\n{'=' * 70}")
        print("FULL TRANSCRIPT (refined)")
        print("=" * 70)
        for r in refined:
            marker = " *" if r.get("refined_changed") else ""
            print(f"  {r['text']}{marker}")


def main():
    parser = argparse.ArgumentParser(description="Test STT pipeline with audio file")
    parser.add_argument("audio_file", help="Path to audio file (m4a, mp3, wav)")
    parser.add_argument("--duration", type=float, default=120,
                        help="Max seconds to process (default: 120)")
    parser.add_argument("--sample-rate", type=int, default=48000,
                        help="Sample rate for STT (default: 48000)")
    parser.add_argument("--refine", action="store_true",
                        help="Also run LLM refinement (uses OpenAI API)")
    parser.add_argument("--output", type=str, default="",
                        help="Save results to JSON file")
    args = parser.parse_args()

    config = Config()

    if not config.deepgram_api_key:
        print("ERROR: DEEPGRAM_API_KEY not set in .env")
        sys.exit(1)

    print(f"\n[1/3] Decoding audio: {args.audio_file}")
    pcm_data = decode_audio_to_pcm(
        args.audio_file,
        sample_rate=args.sample_rate,
        duration=args.duration,
    )

    print(f"\n[2/3] Streaming to Deepgram STT...")
    results = feed_audio_to_deepgram(pcm_data, config, args.sample_rate)

    print(f"\n[3/3] Post-processing transcripts...")
    processed = run_postprocess(results, config)

    refined = None
    if args.refine:
        print(f"\n[Bonus] Running LLM refinement...")
        refined = run_refinement(processed, config)

    print_summary(results, processed, refined)

    if args.output:
        output_data = {
            "audio_file": args.audio_file,
            "duration": args.duration,
            "sample_rate": args.sample_rate,
            "results_count": len(results),
            "processed": [
                {"text": p["text"], "original": p.get("original", ""),
                 "confidence": p["confidence"], "changed": p.get("changed", False)}
                for p in processed
            ],
        }
        if refined:
            output_data["refined"] = [
                {"text": r["text"], "pre_refine": r.get("pre_refine", ""),
                 "refined_changed": r.get("refined_changed", False)}
                for r in refined
            ]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
