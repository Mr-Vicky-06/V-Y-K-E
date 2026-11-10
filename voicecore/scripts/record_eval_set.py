"""Interactive Audio Evaluation Set Recorder and Word Error Rate (WER) Benchmark.

Workflow:
  1. python scripts/record_eval_set.py
     Prompts user through 40 representative voice commands.
     Records at device native rate, resamples to 16 kHz mono WAV via soxr,
     and saves to tests/eval/audio/user_recordings/ with labels.json.

  2. python scripts/record_eval_set.py --eval
     Re-runs evaluation across all user recordings:
     - Transcribes each WAV with WhistleASR
     - Computes Word Error Rate (WER) against expected text
     - Routes through NeedleRouter & evaluates PolicyGate
     - Prints WER summary and routing accuracy table
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from voicecore.asr.whistle import WhistleASR
from voicecore.audio.capture import AudioCapture
from voicecore.config import AudioConfig, VoiceCoreConfig
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.policy.gate import Decision, PolicyGate
from voicecore.tools.builtin.open_app import open_app, open_app_precheck
from voicecore.tools.builtin.search_files import search_files, search_files_precheck
from voicecore.tools.builtin.set_reminder import set_reminder, set_reminder_precheck
from voicecore.tools.registry import ToolRegistry


RECORDING_SET: List[Dict[str, Any]] = [
    # 1. open_app (10)
    {"id": 1, "phrase": "open notepad", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "notepad"}}], "category": "open_app"},
    {"id": 2, "phrase": "launch calculator", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "calculator"}}], "category": "open_app"},
    {"id": 3, "phrase": "open calc", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "calc"}}], "category": "open_app"},
    {"id": 4, "phrase": "start paint", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "paint"}}], "category": "open_app"},
    {"id": 5, "phrase": "open file explorer", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "file explorer"}}], "category": "open_app"},
    {"id": 6, "phrase": "please open the notepad application", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "notepad"}}], "category": "open_app"},
    {"id": 7, "phrase": "bring up calculator", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "calculator"}}], "category": "open_app"},
    {"id": 8, "phrase": "open mspaint", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "mspaint"}}], "category": "open_app"},
    {"id": 9, "phrase": "open node pad", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "node pad"}}], "category": "open_app"},
    {"id": 10, "phrase": "open notepad and open calculator", "expected_calls": [{"name": "open_app", "arguments": {"app_name": "notepad"}}, {"name": "open_app", "arguments": {"app_name": "calculator"}}], "category": "multi_action"},

    # 2. search_files (10)
    {"id": 11, "phrase": "search files for quarterly report", "expected_calls": [{"name": "search_files", "arguments": {"query": "quarterly report"}}], "category": "search_files"},
    {"id": 12, "phrase": "find files named budget", "expected_calls": [{"name": "search_files", "arguments": {"query": "budget"}}], "category": "search_files"},
    {"id": 13, "phrase": "search local files for project proposal", "expected_calls": [{"name": "search_files", "arguments": {"query": "project proposal"}}], "category": "search_files"},
    {"id": 14, "phrase": "find my resume file", "expected_calls": [{"name": "search_files", "arguments": {"query": "resume"}}], "category": "search_files"},
    {"id": 15, "phrase": "search files for invoice", "expected_calls": [{"name": "search_files", "arguments": {"query": "invoice"}}], "category": "search_files"},
    {"id": 16, "phrase": "find files called report", "expected_calls": [{"name": "search_files", "arguments": {"query": "report"}}], "category": "search_files"},
    {"id": 17, "phrase": "search for meeting notes file", "expected_calls": [{"name": "search_files", "arguments": {"query": "meeting notes"}}], "category": "search_files"},
    {"id": 18, "phrase": "look for files named presentation", "expected_calls": [{"name": "search_files", "arguments": {"query": "presentation"}}], "category": "search_files"},
    {"id": 19, "phrase": "search files containing proposal", "expected_calls": [{"name": "search_files", "arguments": {"query": "proposal"}}], "category": "search_files"},
    {"id": 20, "phrase": "find spreadsheet named taxes", "expected_calls": [{"name": "search_files", "arguments": {"query": "taxes"}}], "category": "search_files"},

    # 3. set_reminder (10)
    {"id": 21, "phrase": "set a reminder to call mom tomorrow at 10:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "call mom", "when": "tomorrow at 10:00"}}], "category": "set_reminder"},
    {"id": 22, "phrase": "remind me to buy milk tomorrow at 18:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "buy milk", "when": "tomorrow at 18:00"}}], "category": "set_reminder"},
    {"id": 23, "phrase": "set a reminder for team meeting tomorrow at 09:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "team meeting", "when": "tomorrow at 09:00"}}], "category": "set_reminder"},
    {"id": 24, "phrase": "remind me to take medication in 20 minutes", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "take medication", "when": "in 20 minutes"}}], "category": "set_reminder"},
    {"id": 25, "phrase": "set a reminder for dentist appointment tomorrow at 14:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "dentist appointment", "when": "tomorrow at 14:00"}}], "category": "set_reminder"},
    {"id": 26, "phrase": "remind me to submit timesheet tomorrow at 17:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "submit timesheet", "when": "tomorrow at 17:00"}}], "category": "set_reminder"},
    {"id": 27, "phrase": "set a reminder to check oven in 30 minutes", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "check oven", "when": "in 30 minutes"}}], "category": "set_reminder"},
    {"id": 28, "phrase": "remind me to call John at 15:00", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "call John", "when": "at 15:00"}}], "category": "set_reminder"},
    {"id": 29, "phrase": "set a reminder to stretch in 1 hour", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "stretch", "when": "in 1 hour"}}], "category": "set_reminder"},
    {"id": 30, "phrase": "remind me to drink water in 15 minutes", "expected_calls": [{"name": "set_reminder", "arguments": {"message": "drink water", "when": "in 15 minutes"}}], "category": "set_reminder"},

    # 4. Near-miss collisions (5)
    {"id": 31, "phrase": "open the quarterly report", "expected_calls": [], "category": "near_miss"},
    {"id": 32, "phrase": "open budget", "expected_calls": [], "category": "near_miss"},
    {"id": 33, "phrase": "find notepad", "expected_calls": [], "category": "near_miss"},
    {"id": 34, "phrase": "search for calculator", "expected_calls": [], "category": "near_miss"},
    {"id": 35, "phrase": "remind me about notepad", "expected_calls": [], "category": "near_miss"},

    # 5. Negation & Off-topic (5)
    {"id": 36, "phrase": "don't open notepad", "expected_calls": [], "category": "negation"},
    {"id": 37, "phrase": "do not set a reminder for 5pm", "expected_calls": [], "category": "negation"},
    {"id": 38, "phrase": "what is the capital of France?", "expected_calls": [], "category": "off_topic"},
    {"id": 39, "phrase": "open that app we used yesterday", "expected_calls": [], "category": "vague"},
    {"id": 40, "phrase": "open", "expected_calls": [], "category": "missing_arg"},
]


AMBIENT_SET: List[Dict[str, Any]] = [
    # 3 repeats of typing (10 seconds each)
    {"id": "typing_1", "category": "typing", "prompt": "10s of steady keyboard typing (press keys naturally)", "duration_s": 10.0},
    {"id": "typing_2", "category": "typing", "prompt": "10s of fast typing with spacebar & backspace clicks", "duration_s": 10.0},
    {"id": "typing_3", "category": "typing", "prompt": "10s of intermittent typing and mouse clicks", "duration_s": 10.0},

    # 3 repeats of music with vocals (10 seconds each)
    {"id": "music_1", "category": "music_with_vocals", "prompt": "10s of music track with vocal singing (verse)", "duration_s": 10.0},
    {"id": "music_2", "category": "music_with_vocals", "prompt": "10s of music track with vocal singing (chorus)", "duration_s": 10.0},
    {"id": "music_3", "category": "music_with_vocals", "prompt": "10s of music track with mixed vocal harmonies", "duration_s": 10.0},

    # 3 repeats of nearby talking (10 seconds each)
    {"id": "talking_1", "category": "nearby_talking", "prompt": "10s of nearby room conversation / chatter", "duration_s": 10.0},
    {"id": "talking_2", "category": "nearby_talking", "prompt": "10s of background podcast / video speech", "duration_s": 10.0},
    {"id": "talking_3", "category": "nearby_talking", "prompt": "10s of ambient conversational dialogue", "duration_s": 10.0},
]


def normalize_words(text: str) -> List[str]:
    """Clean punctuation and lowercase for WER computation."""
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return [w for w in cleaned.split() if w]


def calculate_wer(reference: str, hypothesis: str) -> Tuple[float, int, int]:
    """Compute Word Error Rate (WER) using Levenshtein distance on words.

    Returns:
        (wer_float, edit_distance, ref_word_count)
    """
    ref_words = normalize_words(reference)
    hyp_words = normalize_words(hypothesis)

    if not ref_words:
        return (0.0 if not hyp_words else 1.0, len(hyp_words), len(ref_words))

    # Levenshtein distance matrix
    r_len, h_len = len(ref_words), len(hyp_words)
    dp = [[0] * (h_len + 1) for _ in range(r_len + 1)]

    for i in range(r_len + 1):
        dp[i][0] = i
    for j in range(h_len + 1):
        dp[0][j] = j

    for i in range(1, r_len + 1):
        for j in range(1, h_len + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = min(
                    dp[i - 1][j] + 1,      # deletion
                    dp[i][j - 1] + 1,      # insertion
                    dp[i - 1][j - 1] + 1,  # substitution
                )

    edits = dp[r_len][h_len]
    wer = edits / float(len(ref_words))
    return wer, edits, len(ref_words)


def record_dataset(output_dir: Path) -> None:
    """Prompt user interactively to record the 40-phrase dataset."""
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = AudioCapture()

    print("=" * 80)
    print(" VoiceCore: Interactive Evaluation Audio Recorder")
    print(f" Input Device: [{capture.device_index}] {capture.device_name} ({capture.native_rate} Hz -> 16 kHz soxr)")
    print(f" Target Folder: {output_dir}")
    print(" Total Phrases: 40")
    print("=" * 80)
    print(" Instructions:")
    print("   1. Read the phrase shown on screen.")
    print("   2. Press ENTER to start recording.")
    print("   3. Speak clearly at normal pace.")
    print("   4. Press ENTER to stop recording and proceed to the next phrase.")
    print("   Type 'skip' to skip, or 'quit' to save and exit.")
    print("=" * 80)

    labels = []
    labels_file = output_dir / "labels.json"

    # Load existing labels if resuming
    if labels_file.is_file():
        try:
            with labels_file.open("r", encoding="utf-8") as f:
                labels = json.load(f)
            print(f"Resuming: Loaded {len(labels)} existing recordings from labels.json")
        except Exception:
            labels = []

    already_done_ids = {item["id"] for item in labels}

    for item in RECORDING_SET:
        p_id = item["id"]
        phrase = item["phrase"]
        if p_id in already_done_ids:
            continue

        wav_filename = f"utt_{p_id:03d}.wav"
        wav_path = output_dir / wav_filename

        print(f"\n[{p_id:02d}/40] Category: {item['category']}")
        print(f"  >>> PHRASE TO SPEAK: \"{phrase}\" <<<")
        user_input = input("  Press ENTER to START recording (or 'skip'/'quit'): ").strip().lower()

        if user_input == "quit":
            break
        if user_input == "skip":
            continue

        # Start recording
        print("  [RECORDING...] Speak now. Press ENTER when finished.")
        capture.start_capture()
        t_start = time.perf_counter()

        input()  # Wait for user to finish speaking
        duration = time.perf_counter() - t_start
        samples = capture.stop_capture()

        # Save to 16 kHz WAV
        import numpy as np
        int16_samples = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(int16_samples.tobytes())

        print(f"  [SAVED] {wav_filename} ({duration:.1f}s, {len(samples)} samples)")

        record_entry = {
            "id": p_id,
            "filename": wav_filename,
            "expected_transcript": phrase,
            "expected_calls": item["expected_calls"],
            "category": item["category"],
            "duration_s": round(duration, 2),
        }
        labels.append(record_entry)

        # Save labels incrementally
        with labels_file.open("w", encoding="utf-8") as f:
            json.dump(labels, f, indent=2)

    capture.close()
    print("\n" + "=" * 80)
    print(f"Recording session finished. Total recordings saved: {len(labels)}")
    print(f"Labels saved to: {labels_file}")
    print("Run `python scripts/record_eval_set.py --eval` to evaluate the recordings.")
    print("=" * 80)


def evaluate_dataset(recordings_dir: Path) -> int:
    """Run transcription, WER computation, and PolicyGate evaluation on user recordings."""
    labels_file = recordings_dir / "labels.json"
    if not labels_file.is_file():
        print(f"[ERROR] labels.json not found in {recordings_dir}. Run recording first.")
        return 1

    with labels_file.open("r", encoding="utf-8") as f:
        labels = json.load(f)

    if not labels:
        print("[ERROR] labels.json is empty.")
        return 1

    config = VoiceCoreConfig()
    config.asr.keywords = ["notepad", "calculator"]

    registry = ToolRegistry()
    registry.register(open_app, tier="T1", name="open_app", precheck=open_app_precheck)
    registry.register(search_files, tier="T0", name="search_files", precheck=search_files_precheck)
    registry.register(set_reminder, tier="T1", name="set_reminder", precheck=set_reminder_precheck)

    gate = PolicyGate(config=config.policy, registry=registry)
    router = NeedleRouter(registry=registry, stateless=True)
    asr = WhistleASR(config=config.asr, debug_config=config.debug)

    print("=" * 95)
    print(f" VoiceCore: Evaluating {len(labels)} User Audio Recordings with Word Error Rate (WER)")
    print("=" * 95)

    headers = f"{'ID':3s} | {'Expected Text':32s} | {'ASR Transcript':32s} | {'WER':6s} | {'Calls':18s} | {'Conf':6s} | {'Gate'}"
    print(headers)
    print("-" * 115)

    total_edits = 0
    total_ref_words = 0
    correct_routing_count = 0
    results = []

    for item in labels:
        p_id = item["id"]
        expected_text = item["expected_transcript"]
        wav_file = recordings_dir / item["filename"]

        if not wav_file.is_file():
            print(f"[{p_id:02d}] Missing file: {wav_file}")
            continue

        # 1. Transcribe with Whistle
        transcript_obj = asr.transcribe(str(wav_file))
        actual_text = transcript_obj.text

        # 2. Compute WER
        wer, edits, ref_words = calculate_wer(expected_text, actual_text)
        total_edits += edits
        total_ref_words += ref_words

        # 3. Route with Needle
        route_res = router.route(actual_text)

        calls_repr = ", ".join(f"{c.name}" for c in route_res.calls) if route_res.calls else "[]"

        # 4. Policy Gate decision
        decisions = []
        for c in route_res.calls:
            dec = gate.decide(
                call=c,
                confidence=route_res.confidence,
                negation=route_res.negation,
                ungrounded=route_res.ungrounded,
            )
            decisions.append(str(dec.decision))
        gate_str = decisions[0] if decisions else "NO_CALLS"

        # Check routing correctness
        exp_names = [c["name"] for c in item.get("expected_calls", [])]
        act_names = [c.name for c in route_res.calls]
        is_correct = (exp_names == act_names)
        if is_correct:
            correct_routing_count += 1

        exp_disp = expected_text if len(expected_text) <= 32 else expected_text[:29] + "..."
        act_disp = actual_text if len(actual_text) <= 32 else actual_text[:29] + "..."

        print(f"{p_id:02d} | {exp_disp:32s} | {act_disp:32s} | {wer:5.2f} | {calls_repr:18s} | {route_res.confidence:0.4f} | {gate_str}")

        results.append({
            "id": p_id,
            "expected_text": expected_text,
            "actual_text": actual_text,
            "wer": round(wer, 4),
            "asr_ms": transcript_obj.asr_ms,
            "route_calls": [{"name": c.name, "arguments": c.arguments} for c in route_res.calls],
            "confidence": route_res.confidence,
            "gate_decision": gate_str,
            "is_correct": is_correct,
        })

    overall_wer = total_edits / float(max(1, total_ref_words))
    routing_acc = correct_routing_count / float(max(1, len(labels)))

    print("-" * 115)
    print("\n[EVALUATION SUMMARY]")
    print(f"  Total Recordings Evaluated: {len(labels)}")
    print(f"  Total Reference Words:      {total_ref_words}")
    print(f"  Total Word Edits (Sub/Del): {total_edits}")
    print(f"  Overall Word Error Rate:    {overall_wer*100.0:.2f}% (WER = {overall_wer:.4f})")
    print(f"  Routing Accuracy:           {routing_acc*100.0:.1f}% ({correct_routing_count}/{len(labels)})")
    print("=" * 115)

    router.close()
    return 0


def generate_ambient_samples(ambient_dir: Path) -> int:
    """Generate 10s synthetic ambient WAV samples for offline testing."""
    import numpy as np
    ambient_dir.mkdir(parents=True, exist_ok=True)
    sr = 16000
    dur = 10.0
    n_samples = int(sr * dur)
    t = np.linspace(0, dur, n_samples, endpoint=False)

    labels = []
    for item in AMBIENT_SET:
        clip_id = item["id"]
        cat = item["category"]
        wav_path = ambient_dir / f"{clip_id}.wav"

        if cat == "typing":
            # 10s of realistic acoustic mechanical keyboard keystrokes
            sig = np.zeros(n_samples, dtype=np.float32)
            np.random.seed(abs(hash(clip_id)) % (2**32))
            pos = 4000
            while pos < n_samples - 2000:
                click_len = np.random.randint(80, 240)
                click_env = np.exp(-np.linspace(0, 10, click_len))
                noise = np.random.randn(click_len) * click_env
                freq = np.random.choice([1200, 1800, 2400, 3200])
                click = noise + 0.3 * np.sin(2 * np.pi * freq * np.linspace(0, click_len/sr, click_len)) * click_env
                sig[pos:pos+click_len] += click.astype(np.float32) * 0.4
                pos += np.random.randint(int(sr * 0.12), int(sr * 0.45))
        elif cat == "music_with_vocals":
            # 10s of music containing chords + vocal-like formant sweep
            np.random.seed(abs(hash(clip_id)) % (2**32))
            chord = (
                0.25 * np.sin(2 * np.pi * 220.0 * t) +
                0.20 * np.sin(2 * np.pi * 277.18 * t) +
                0.20 * np.sin(2 * np.pi * 329.63 * t)
            )
            vocal_pitch = 180.0 + 10.0 * np.sin(2 * np.pi * 4.5 * t)
            vocal_formant = 0.35 * np.sin(2 * np.pi * vocal_pitch * t) * (1.0 + 0.5 * np.sin(2 * np.pi * 0.5 * t))
            sig = (chord + vocal_formant).astype(np.float32) * 0.5
        else:  # nearby_talking
            # 10s of conversational speech formant bursts
            np.random.seed(abs(hash(clip_id)) % (2**32))
            sig = np.zeros(n_samples, dtype=np.float32)
            pos = 2000
            while pos < n_samples - 2000:
                burst_len = np.random.randint(int(sr * 0.4), int(sr * 1.2))
                burst_len = min(burst_len, n_samples - pos)
                tb = np.linspace(0, burst_len/sr, burst_len)
                pitch = float(np.random.choice([120.0, 160.0, 210.0]))
                f1 = 500.0 + 150.0 * np.sin(2 * np.pi * 3.0 * tb)
                vocal = np.sin(2 * np.pi * pitch * tb) * (0.5 * np.sin(2 * np.pi * f1 * tb))
                env = np.sin(np.pi * np.linspace(0, 1, burst_len))
                sig[pos:pos+burst_len] += (vocal * env).astype(np.float32) * 0.45
                pos += burst_len + np.random.randint(int(sr * 0.2), int(sr * 0.8))

        # Peak normalize to prevent clipping
        max_val = np.max(np.abs(sig))
        if max_val > 0:
            sig = (sig / max_val) * 0.8
        int16_pcm = (sig * 32767).astype(np.int16)

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(int16_pcm.tobytes())

        labels.append({
            "id": clip_id,
            "filename": f"{clip_id}.wav",
            "category": cat,
            "duration_s": dur,
            "prompt": item["prompt"],
        })
        print(f"  [GENERATED] {clip_id}.wav ({dur}s, category={cat})")

    labels_file = ambient_dir / "ambient_labels.json"
    with labels_file.open("w", encoding="utf-8") as f:
        json.dump(labels, f, indent=2)
    print(f"\nSaved {len(labels)} ambient sample audio clips to {ambient_dir}")
    return 0


def record_ambient_dataset(ambient_dir: Path) -> int:
    """Interactively record 10s ambient negative clips (typing, music, nearby talking)."""
    ambient_dir.mkdir(parents=True, exist_ok=True)
    labels_file = ambient_dir / "ambient_labels.json"

    print("=" * 80)
    print(f" VoiceCore: Ambient Negative Evaluation Recorder ({len(AMBIENT_SET)} clips of 10s)")
    print(" Target: 3 repeats of typing, 3 repeats of music with vocals, 3 repeats of talking")
    print(f" Output Directory: {ambient_dir}")
    print("=" * 80)

    cfg = AudioConfig(max_seconds=15)
    capture = AudioCapture(config=cfg)

    labels = []
    for item in AMBIENT_SET:
        clip_id = item["id"]
        cat = item["category"]
        prompt = item["prompt"]
        duration = item["duration_s"]
        wav_filename = f"{clip_id}.wav"
        wav_path = ambient_dir / wav_filename

        print(f"\n[{clip_id.upper()}] Category: {cat}")
        print(f"  Instruction: {prompt}")
        print(f"  Clip Duration: {duration:.1f} seconds")
        input("  Press ENTER when ready to start 10s recording...")

        print(f"  Recording for {duration:.1f} seconds... (Perform the action now!)")
        capture.start()
        t0 = time.time()
        while time.time() - t0 < duration:
            time.sleep(0.1)

        samples = capture.stop()
        if samples is None or len(samples) == 0:
            print(f"  [WARN] No audio recorded for {clip_id}. Skipping.")
            continue

        int16_samples = (samples * 32767).astype("int16")
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(int16_samples.tobytes())

        print(f"  [SAVED] {wav_filename} ({len(samples)/16000:.1f}s)")
        labels.append({
            "id": clip_id,
            "filename": wav_filename,
            "category": cat,
            "duration_s": round(len(samples)/16000, 2),
            "prompt": prompt,
        })
        with labels_file.open("w", encoding="utf-8") as f:
            json.dump(labels, f, indent=2)

    capture.close()
    print("\n" + "=" * 80)
    print(f"Ambient recording session finished. Total clips: {len(labels)}")
    print(f"Run `python scripts/record_eval_set.py --ambient --eval` to evaluate.")
    print("=" * 80)
    return 0


def evaluate_ambient_dataset(ambient_dir: Path) -> int:
    """Evaluate 10s ambient negative clips through WhistleASR, NeedleRouter, and PolicyGate."""
    labels_file = ambient_dir / "ambient_labels.json"
    if not labels_file.is_file():
        wavs = list(ambient_dir.glob("*.wav"))
        if not wavs:
            print(f"[NOTICE] No ambient recordings found in {ambient_dir}. Generating synthetic samples...")
            generate_ambient_samples(ambient_dir)
            if not labels_file.is_file():
                return 1

    with labels_file.open("r", encoding="utf-8") as f:
        labels = json.load(f)

    config = VoiceCoreConfig()
    registry = ToolRegistry()
    registry.register(open_app, tier="T1", name="open_app", precheck=open_app_precheck, triggers=["open", "launch"])
    registry.register(search_files, tier="T0", name="search_files", precheck=search_files_precheck, triggers=["search", "find"])
    registry.register(set_reminder, tier="T1", name="set_reminder", precheck=set_reminder_precheck, triggers=["remind", "reminder"])

    gate = PolicyGate(config=config.policy, registry=registry)
    router = NeedleRouter(registry=registry, stateless=True)
    asr = WhistleASR(config=config.asr, debug_config=config.debug)

    print("=" * 105)
    print(f" VoiceCore: Evaluating {len(labels)} Ambient 10s Clips (Typing, Music with Vocals, Nearby Talking)")
    print(" Verifying Safety Guarantee: Exactly ZERO actions must fire (ACT = 0%)")
    print("=" * 105)

    headers = f"{'Clip ID':12s} | {'Category':18s} | {'Whistle Transcript':32s} | {'Confidence':10s} | {'Gate Outcome':12s} | Status"
    print(headers)
    print("-" * 105)

    actions_fired = 0
    results = []

    for item in labels:
        clip_id = item["id"]
        cat = item["category"]
        wav_file = ambient_dir / item.get("filename", f"{clip_id}.wav")
        if not wav_file.is_file():
            print(f"[MISSING] {wav_file}")
            continue

        transcript_obj = asr.transcribe(wav_file)
        raw_text = transcript_obj.text.strip()
        display_transcript = f'"{raw_text}"' if raw_text else "(Silence / No Speech)"
        if len(display_transcript) > 32:
            display_transcript = display_transcript[:29] + '..."'

        if not raw_text:
            calls_str = "None"
            conf_str = "0.0000"
            gate_decision = "NO_SPEECH"
            status = "SAFE (Zero action)"
        else:
            route_res = router.route(raw_text)
            conf_str = f"{route_res.confidence:.4f}"
            if not route_res.calls:
                gate_decision = "NO_CALLS"
                status = "SAFE (Zero action)"
            else:
                call = route_res.calls[0]
                dec = gate.decide(
                    call=call,
                    confidence=route_res.confidence,
                    negation=route_res.negation,
                    ungrounded=route_res.ungrounded,
                )
                gate_decision = dec.decision
                if dec.decision == Decision.ACT:
                    actions_fired += 1
                    status = "VIOLATION (Action Fired!)"
                else:
                    status = f"SAFE ({dec.decision})"

        print(f"{clip_id:12s} | {cat:18s} | {display_transcript:32s} | {conf_str:10s} | {gate_decision:12s} | {status}")
        results.append({
            "clip_id": clip_id,
            "category": cat,
            "transcript": raw_text,
            "gate_decision": gate_decision,
            "status": status,
        })

    print("-" * 105)
    print("\n[AMBIENT EVALUATION SUMMARY]")
    print(f"  Total 10s Ambient Clips Evaluated: {len(results)}")
    print(f"  Total Actions Fired (ACT):         {actions_fired}")
    print(f"  False-Action Rate:                 {actions_fired / max(1, len(results)) * 100.0:.1f}%")
    print(f"  Negative Safety Verification:      {'PASS (100% Zero Actions Fired)' if actions_fired == 0 else 'FAIL'}")
    print("=" * 105)
    router.close()
    return 0 if actions_fired == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="VoiceCore: Evaluation Audio Recording & WER Benchmark")
    parser.add_argument("--eval", action="store_true", help="Run WER and routing evaluation on saved recordings")
    parser.add_argument("--ambient", action="store_true", help="Record or evaluate 10s ambient negative clips (typing, music, talking)")
    parser.add_argument("--generate-samples", action="store_true", help="Generate synthetic ambient audio clips for testing")
    parser.add_argument("--dir", type=str, default="", help="Recordings directory (default: user_recordings or ambient_eval)")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent

    if args.ambient:
        ambient_dir = Path(args.dir) if args.dir else base_dir / "tests" / "test_data" / "audio" / "ambient_eval"
        if not ambient_dir.is_absolute():
            ambient_dir = base_dir / args.dir

        if args.generate_samples:
            return generate_ambient_samples(ambient_dir)
        elif args.eval:
            return evaluate_ambient_dataset(ambient_dir)
        else:
            return record_ambient_dataset(ambient_dir)

    recordings_dir = Path(args.dir) if args.dir else base_dir / "tests" / "eval" / "audio" / "user_recordings"
    if not recordings_dir.is_absolute():
        recordings_dir = base_dir / args.dir

    if args.eval:
        return evaluate_dataset(recordings_dir)
    else:
        record_dataset(recordings_dir)
        return 0



if __name__ == "__main__":
    sys.exit(main())

