"""Reproduce thread benchmarks: Fresh Process vs In-Process.

Measures:
  - Fresh process per thread setting (1, 2, 4, 8) with set_threads called BEFORE load.
  - 10 warm runs each of `voicecore --text "open notepad"`.
  - In-process thread mutation on already-loaded model.
  - Precise stage timing: NLU ms, Gate ms, Total ms.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def percentile(data: List[float], p: int) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    idx = max(0, int(len(s) * (p / 100.0)) - 1)
    return s[idx]


def run_worker_fresh(threads: int, runs: int = 10) -> Dict[str, float]:
    """Worker code executed in a separate fresh Python process."""
    import cactus
    from voicecore.config import VoiceCoreConfig
    from voicecore.nlu.needle_router import NeedleRouter
    from voicecore.policy.gate import PolicyGate
    from voicecore.runtime.assistant import Assistant
    from voicecore.tools.builtin.open_app import open_app, open_app_precheck
    from voicecore.tools.builtin.search_files import search_files, search_files_precheck
    from voicecore.tools.builtin.set_reminder import set_reminder, set_reminder_precheck
    from voicecore.tools.registry import ToolRegistry
    from voicecore.events import EventBus, RouteEvent

    # 1. SET THREADS BEFORE LOAD
    cactus.set_threads(threads)

    # 2. Build pipeline
    registry = ToolRegistry()
    registry.register(open_app, tier="T1", name="open_app", precheck=open_app_precheck, triggers=["open", "launch"])
    registry.register(search_files, tier="T0", name="search_files", precheck=search_files_precheck, triggers=["search", "find"])
    registry.register(set_reminder, tier="T1", name="set_reminder", precheck=set_reminder_precheck, triggers=["remind", "reminder"])

    config = VoiceCoreConfig()
    gate = PolicyGate(config=config.policy, registry=registry)
    router = NeedleRouter(registry=registry, stateless=True)
    bus = EventBus()
    assistant = Assistant(router=router, registry=registry, policy_gate=gate, config=config, event_bus=bus)

    # 3. Warmup call (cold)
    assistant.run_text("open notepad")

    # 4. 10 Warm runs
    nlu_times: List[float] = []
    tot_times: List[float] = []

    for _ in range(runs):
        events = []
        bus.subscribe(RouteEvent, lambda e: events.append(e.nlu_ms))
        t0 = time.perf_counter()
        assistant.run_text("open notepad")
        tot = (time.perf_counter() - t0) * 1000.0
        nlu = events[-1] if events else 0.0
        nlu_times.append(nlu)
        tot_times.append(tot)

    return {
        "threads": threads,
        "nlu_p50": percentile(nlu_times, 50),
        "nlu_p95": percentile(nlu_times, 95),
        "nlu_mean": sum(nlu_times) / len(nlu_times),
        "tot_p50": percentile(tot_times, 50),
        "tot_p95": percentile(tot_times, 95),
        "tot_mean": sum(tot_times) / len(tot_times),
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        t = int(sys.argv[2])
        res = run_worker_fresh(t, runs=10)
        print(f"RESULT_JSON:{json.dumps(res)}")
        sys.exit(0)

    # Controller process: spawn fresh subprocess per thread setting
    print("=" * 80)
    print(" VoiceCore: Thread Benchmark (Fresh Process per Thread Setting, Set Before Load)")
    print("=" * 80)

    python_exe = sys.executable
    script_path = str(Path(__file__).resolve())
    thread_settings = [1, 2, 4, 8]

    fresh_results = {}
    for t in thread_settings:
        print(f"Spawning fresh process for threads = {t}...")
        cmd = [python_exe, script_path, "--worker", str(t)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        out = proc.stdout
        for line in out.splitlines():
            if line.startswith("RESULT_JSON:"):
                data = json.loads(line.replace("RESULT_JSON:", ""))
                fresh_results[t] = data
                print(f"  Threads={t:2d} -> NLU p50: {data['nlu_p50']:6.1f} ms | NLU p95: {data['nlu_p95']:6.1f} ms | Total p50: {data['tot_p50']:6.1f} ms")

    # In-process comparison
    print("\n" + "=" * 80)
    print(" VoiceCore: Thread Benchmark (In-Process Dynamic Mutation, Loaded Once)")
    print("=" * 80)
    import cactus
    from voicecore.config import VoiceCoreConfig
    from voicecore.nlu.needle_router import NeedleRouter
    from voicecore.policy.gate import PolicyGate
    from voicecore.runtime.assistant import Assistant
    from voicecore.tools.builtin.open_app import open_app, open_app_precheck
    from voicecore.tools.builtin.search_files import search_files, search_files_precheck
    from voicecore.tools.builtin.set_reminder import set_reminder, set_reminder_precheck
    from voicecore.tools.registry import ToolRegistry
    from voicecore.events import EventBus, RouteEvent

    # Load with initial threads=2
    cactus.set_threads(2)
    registry = ToolRegistry()
    registry.register(open_app, tier="T1", name="open_app", precheck=open_app_precheck, triggers=["open", "launch"])
    registry.register(search_files, tier="T0", name="search_files", precheck=search_files_precheck, triggers=["search", "find"])
    registry.register(set_reminder, tier="T1", name="set_reminder", precheck=set_reminder_precheck, triggers=["remind", "reminder"])

    config = VoiceCoreConfig()
    gate = PolicyGate(config=config.policy, registry=registry)
    router = NeedleRouter(registry=registry, stateless=True)
    bus = EventBus()
    assistant = Assistant(router=router, registry=registry, policy_gate=gate, config=config, event_bus=bus)

    # Initial warmup
    assistant.run_text("open notepad")

    in_process_results = {}
    for t in thread_settings:
        cactus.set_threads(t)
        nlu_times = []
        tot_times = []
        for _ in range(10):
            events = []
            bus.subscribe(RouteEvent, lambda e: events.append(e.nlu_ms))
            t0 = time.perf_counter()
            assistant.run_text("open notepad")
            tot = (time.perf_counter() - t0) * 1000.0
            nlu = events[-1] if events else 0.0
            nlu_times.append(nlu)
            tot_times.append(tot)

        in_process_results[t] = {
            "threads": t,
            "nlu_p50": percentile(nlu_times, 50),
            "nlu_p95": percentile(nlu_times, 95),
            "tot_p50": percentile(tot_times, 50),
        }
        print(f"  Threads={t:2d} (In-Process) -> NLU p50: {in_process_results[t]['nlu_p50']:6.1f} ms | NLU p95: {in_process_results[t]['nlu_p95']:6.1f} ms | Total p50: {in_process_results[t]['tot_p50']:6.1f} ms")

    print("\n" + "=" * 90)
    print(f" {'Threads':<8} | {'Fresh NLU p50':<15} | {'Fresh Total p50':<16} | {'In-Process NLU p50':<19} | {'In-Process Total p50':<20}")
    print(" " + "-" * 88)
    for t in thread_settings:
        fr = fresh_results[t]
        ip = in_process_results[t]
        print(f" {t:<8d} | {fr['nlu_p50']:8.1f} ms     | {fr['tot_p50']:8.1f} ms      | {ip['nlu_p50']:8.1f} ms         | {ip['tot_p50']:8.1f} ms")
    print("=" * 90)

