import json
import os
import pathlib
import tempfile
import wave
import numpy as np

os.environ["CACTUS_TELEMETRY"] = "0"
os.environ["NEEDLE_TELEMETRY"] = "0"
os.environ["DO_NOT_TRACK"] = "1"

import cactus

# 1. Silence file path (str and Path)
with tempfile.TemporaryDirectory() as td:
    wav_path = os.path.join(td, "silence_1s.wav")
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)
    
    print("=== Test 1: str file path (silence 1s) ===")
    out_str = cactus.transcribe(wav_path)
    print("Return type:", type(out_str))
    print("Result dict:", json.dumps(out_str, indent=2))

    print("\n=== Test 2: pathlib.Path ===")
    out_path = cactus.transcribe(pathlib.Path(wav_path))
    print("Result dict:", json.dumps(out_path, indent=2))

# 3. Numpy array inputs
print("\n=== Test 3: numpy array float32 (16000 samples = 1s silence) ===")
silence_f32 = np.zeros(16000, dtype=np.float32)
try:
    out_f32 = cactus.transcribe(silence_f32)
    print("Result dict:", json.dumps(out_f32, indent=2))
except Exception as e:
    print(f"Failed with {type(e).__name__}: {e}")

print("\n=== Test 4: numpy array int16 ===")
silence_i16 = np.zeros(16000, dtype=np.int16)
try:
    out_i16 = cactus.transcribe(silence_i16)
    print("Result dict:", json.dumps(out_i16, indent=2))
except Exception as e:
    print(f"Failed with {type(e).__name__}: {e}")

print("\n=== Test 5: inspect transcribe signature and docstring ===")
import inspect
print("Signature:", inspect.signature(cactus.transcribe))
print("Docstring:\n", inspect.getdoc(cactus.transcribe))

