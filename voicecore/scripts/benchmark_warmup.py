"""Benchmark script: model load time + cold vs warm inference latency.

Runs 10 inferences each for ASR and NLU after a single warm-up call,
then reports p50/p95 and cold vs warm deltas. Output goes to stdout.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List

import numpy as np

# Add src to path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cactus

SILENCE_1S = np.zeros(16000, dtype=np.float32)
N_RUNS = 10


def pct(times: List[float], p: int) -> float:
    s = sorted(times)
    idx = max(0, int(len(s) * p / 100) - 1)
    return s[idx]


def main() -> None:
    print("=" * 60)
    print("VoiceCore Warmup & Latency Benchmark")
    print("=" * 60)

    # --- Model load time (Whistle) ---
    t0 = time.perf_counter()
    whistle = cactus.Whistle()
    whistle_load_ms = (time.perf_counter() - t0) * 1000.0
    print(f"\n[LOAD] Whistle model load:  {whistle_load_ms:7.1f} ms")

    # --- Model load time (Needle) ---
    t0 = time.perf_counter()
    agent = cactus.Cactus(tools=[], stateless=True)
    needle_load_ms = (time.perf_counter() - t0) * 1000.0
    print(f"[LOAD] Needle model load:   {needle_load_ms:7.1f} ms")
    print(f"[LOAD] Total model load:    {whistle_load_ms + needle_load_ms:7.1f} ms")

    # --- ASR cold run (first real inference after model load) ---
    t0 = time.perf_counter()
    whistle.transcribe(SILENCE_1S, language="en")
    asr_cold_ms = (time.perf_counter() - t0) * 1000.0
    print(f"\n[COLD] ASR first inference: {asr_cold_ms:7.1f} ms")

    t0 = time.perf_counter()
    agent.complete("open notepad")
    nlu_cold_ms = (time.perf_counter() - t0) * 1000.0
    print(f"[COLD] NLU first inference: {nlu_cold_ms:7.1f} ms")
    print(f"[COLD] Total cold pipeline: {asr_cold_ms + nlu_cold_ms:7.1f} ms")

    # --- ASR warm runs ---
    asr_times: List[float] = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        whistle.transcribe(SILENCE_1S, language="en")
        asr_times.append((time.perf_counter() - t0) * 1000.0)

    # --- NLU warm runs ---
    nlu_times: List[float] = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        agent.complete("open notepad")
        nlu_times.append((time.perf_counter() - t0) * 1000.0)

    total_times = [a + n for a, n in zip(asr_times, nlu_times)]

    print(f"\n[WARM] {N_RUNS}-run statistics (ms):")
    print(f"{'':8s} {'p50':>8s}  {'p95':>8s}  {'min':>8s}  {'max':>8s}")
    print(f"{'ASR':8s} {pct(asr_times,50):8.1f}  {pct(asr_times,95):8.1f}  {min(asr_times):8.1f}  {max(asr_times):8.1f}")
    print(f"{'NLU':8s} {pct(nlu_times,50):8.1f}  {pct(nlu_times,95):8.1f}  {min(nlu_times):8.1f}  {max(nlu_times):8.1f}")
    print(f"{'Total':8s} {pct(total_times,50):8.1f}  {pct(total_times,95):8.1f}  {min(total_times):8.1f}  {max(total_times):8.1f}")

    print(f"\n[DELTA] Cold vs warm ASR:   {asr_cold_ms - pct(asr_times,50):+.1f} ms vs p50")
    print(f"[DELTA] Cold vs warm NLU:   {nlu_cold_ms - pct(nlu_times,50):+.1f} ms vs p50")
    print(f"[DELTA] Cold vs warm total: {(asr_cold_ms+nlu_cold_ms) - pct(total_times,50):+.1f} ms vs p50")
    print("=" * 60)

    agent.close()


if __name__ == "__main__":
    main()

