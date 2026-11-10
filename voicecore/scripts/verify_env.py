"""Environment contract check for VoiceCore.  Run: python scripts/verify_env.py [--skip-models]

Each step prints PASS/FAIL with raw evidence. Exit code 1 if any step fails.
Nothing here is assumed: it prints what the installed package actually returns.
"""
import os
import sys
import tempfile
import time
import wave

# Privacy: must be set BEFORE the engine loads.
os.environ.setdefault("CACTUS_TELEMETRY", "0")
os.environ.setdefault("NEEDLE_TELEMETRY", "0")
os.environ.setdefault("DO_NOT_TRACK", "1")

results = []


def step(name):
    def deco(fn):
        def run(*a, **k):
            t0 = time.perf_counter()
            try:
                evidence = fn(*a, **k)
                results.append((name, True))
                print(f"[PASS] {name} ({time.perf_counter() - t0:.2f}s) {evidence or ''}")
            except Exception as e:  # noqa: BLE001 - we want every failure reported
                results.append((name, False))
                print(f"[FAIL] {name}: {type(e).__name__}: {e}")
        return run
    return deco


@step("python >= 3.11")
def check_python():
    assert sys.version_info >= (3, 11), sys.version
    return sys.version.split()[0]


@step("import engine (cactus / needle)")
def check_import():
    try:
        import cactus as engine
        name = "cactus"
    except ImportError:
        import needle as engine
        name = "needle"
    return f"package={name} version={getattr(engine, '__version__', '?')} file={engine.__file__}"


@step("telemetry env vars set")
def check_env():
    assert os.environ.get("CACTUS_TELEMETRY") == "0" or os.environ.get("NEEDLE_TELEMETRY") == "0"
    assert os.environ.get("DO_NOT_TRACK") == "1"


@step("mic extra importable + input device present")
def check_mic():
    import numpy  # noqa: F401
    import soxr  # noqa: F401
    import sounddevice as sd
    inputs = [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]
    assert inputs, "no input devices found"
    return f"{len(inputs)} input device(s), first: {inputs[0]}"


def _silence_wav(path, seconds=1.0, rate=16000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))


@step("Whistle: silence -> empty transcript (engine + weights load)")
def check_whistle():
    try:
        import cactus as engine
    except ImportError:
        import needle as engine
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "silence.wav")
        _silence_wav(p)
        out = engine.transcribe(p)
    assert isinstance(out, dict) and "text" in out, f"unexpected return: {out!r}"
    assert out["text"].strip() == "", f"expected empty transcript, got {out['text']!r}"
    return f"keys={sorted(out)}"


@step("Needle: dummy tool call (prints raw return shape - needed for spike S2)")
def check_needle():
    import json
    try:
        import cactus as engine
    except ImportError:
        import needle as engine

    calls_made = []

    @engine.tool
    def get_weather(city: str):
        "Get the current weather for a city."
        calls_made.append(city)
        return {"city": city, "temp_c": 27, "sky": "clear"}

    with engine.Needle(tools=[get_weather]) as agent:
        run_out = agent.run("what's the weather in Lagos?")
        print("   run() ->", json.dumps(run_out, default=str)[:600])
        agent.reset()
        comp_out = agent.complete("what's the weather in Lagos?")
        print("   complete() ->", json.dumps(comp_out, default=str)[:600])
    print("   tool executed by run()/complete() (count):", len(calls_made))
    assert isinstance(run_out, dict)
    assert isinstance(comp_out, dict)
    assert len(calls_made) == 1, f"expected complete() not to execute tool, count={len(calls_made)}"
    return f"run keys={sorted(run_out)}; complete keys={sorted(comp_out)}"


if __name__ == "__main__":
    check_python()
    check_import()
    check_env()
    check_mic()
    if "--skip-models" not in sys.argv:
        check_whistle()
        check_needle()
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} steps passed")
    sys.exit(1 if failed else 0)
