# Technical Spikes Ledger (M0)

Raw outputs, observed values, and verification evidence for spikes S1 through S4.

---

## Spike S1: Package & API Confirmation (`needle` vs `cactus`)

### Research & Investigation
1. **Installed baseline `cactus-needle==3.2.10`:**
   - Package metadata imports `needle`.
   - Engine fetch routine in `needle/agent/fetch.py` hardcodes:
     - `ENGINE_REPOS[3] = "Cactus-Compute/needle3"`
     - `ENGINE_VERSIONS[3] = "3.3.3"`
     - URL: `https://huggingface.co/Cactus-Compute/needle3/resolve/main/python/cactus_needle-3.3.3-py3-none-win_amd64.whl`
   - **Observed Error on Contract Check:**
     ```
     [FAIL] Whistle: silence -> empty transcript (engine + weights load): RemoteEntryNotFoundError: 404 Client Error
     Entry Not Found for url: https://huggingface.co/Cactus-Compute/needle3/resolve/main/python/cactus_needle-3.3.3-py3-none-win_amd64.whl
     ```
2. **Upstream Repository Audit on Hugging Face:**
   - Listing `Cactus-Compute/needle3` via `HfApi`:
     `['.gitattributes', 'LICENSE', 'README.md', 'checkpoints/needle3.safetensors', 'config.json', 'needle3.cact', 'tokenizer/tokenizer.model', 'tokenizer/tokenizer.vocab']`
     *(Confirmed: No wheel files exist in the `needle3` repository)*.
   - Needle 3 official model card states:
     ```sh
     pip install -U cactus-compute
     # Runtime binaries and supported platforms live in the Cactus repository.
     ```
   - Hugging Face repository `Cactus-Compute/cactus` contains:
     `releases/4.1.0/python/cactus_runtime-4.1.0-py3-none-win_amd64.whl` (contains `libcactus.dll`).
3. **Cactus Compute 4.1.0 Verification:**
   - PyPI package: `cactus-compute==4.1.0`.
   - Core API exports:
     ```python
     from .agent.text import Cactus, extract
     from .agent.whistle import Whistle, transcribe, stream
     from .agent.tools import Field, tool
     Needle = Cactus  # Exact alias
     ```
   - Model weights used:
     - `needle3.cact` from `Cactus-Compute/needle3`
     - `whistle.cact` from `Cactus-Compute/whistle`

### Conclusion & Resolution
- **Installed Version:** `cactus-compute==4.1.0` with `cactus-runtime==4.1.0`.
- **API:** Use `cactus` (or `import cactus as needle` / `Needle = cactus.Needle`).
- **Telemetry Environment Variables:**
  Must set both before importing:
  - `CACTUS_TELEMETRY=0`
  - `NEEDLE_TELEMETRY=0`
  - `DO_NOT_TRACK=1`
- **Recorded in:** `docs/DECISIONS.md` under `DECISION-001`.

---

## Spike S2: Real Return Shapes of `Needle.run()` and `Needle.complete()`

Executed script: `scripts/test_spike_s2.py` against live weights `needle3.cact`.

### Raw Output: `agent.run("what's the weather in Lagos?")`
```json
{
  "type": "respond",
  "success": true,
  "error": null,
  "error_code": null,
  "reason": null,
  "function_calls": [],
  "suppressed_calls": [],
  "reasoning": "User asked a question, respond with the weather value.",
  "confidence": 0.7067,
  "prefill_tps": 118.1,
  "decode_tps": 59.2,
  "peak_ram_mb": 131.0,
  "results": [
    {
      "city": "Lagos",
      "temp_c": 27,
      "sky": "clear"
    }
  ]
}
```
- **Tool execution count after `run()`:** 1 (tool **was executed** by `run()`).
- **`function_calls`:** empty (resolved into `"results"`).

### Raw Output: `agent.complete("what's the weather in Lagos?")`
```json
{
  "type": "call",
  "success": true,
  "error": null,
  "error_code": null,
  "reason": null,
  "function_calls": [
    {
      "name": "get_weather",
      "arguments": {
        "city": "Lagos"
      }
    }
  ],
  "suppressed_calls": [],
  "reasoning": "Query asks for weather in Lagos. get_weather tool with city 'Lagos'.",
  "confidence": 0.957,
  "prefill_tps": 135.3,
  "decode_tps": 74.4,
  "peak_ram_mb": 131.0,
  "validation": {
    "ungrounded": [],
    "negation": false
  }
}
```
- **Tool execution count after `complete()`:** 1 (tool **WAS NOT EXECUTED** by `complete()`).
- **Does `complete()` return `function_calls` without executing?**
  **YES.** It parses and validates arguments against the schema and returns the proposed calls in `comp_out["function_calls"]` without running the Python function. This enables our `PolicyGate` to intervene.
- **Where is `confidence`?**
  Top-level float in `comp_out["confidence"]` (e.g. `0.957`).
- **Behavior of `stateless=True` vs `reset()`:**
  - Tested in `scripts/test_spike_s2_state.py`.
  - Stateful mode (`stateless=False` default): Conversation history builds across turns. Calling `agent.reset()` clears conversation memory.
  - Stateless mode (`stateless=True`): Each turn is evaluated independently with zero context accumulation.

---

## Spike S3: `transcribe` Input Formats & Behavior on Silence

Executed script: `scripts/test_spike_s3.py` against live weights `whistle.cact`.

### Supported Input Formats
1. **`str` file path** to a `.wav` file: Supported.
2. **`pathlib.Path`** to a `.wav` file: Supported.
3. **Numpy `float32` array:** 16 kHz mono float samples in `[-1.0, 1.0]`: Supported.
4. **Numpy `int16` array:** Supported.

### Signature & Docstring
```python
transcribe(audio, language=None, keywords=None, word_timestamps=False, weights=None) -> dict
```
- `audio`: WAV file path or 16 kHz mono float samples in `[-1, 1]` of any length.
- `language`: Target language string (e.g. `"en"`) or `None` for auto-detection.
- `keywords`: List of strings for vocabulary/name biasing.
- `word_timestamps`: Boolean flag to emit token-level timestamp intervals.

### Result Dictionary Structure & Silence Behavior
Output on 1.0 second silence WAV (`b"\x00\x00" * 16000`):
```json
{
  "text": "",
  "language": "",
  "ttft_ms": 0.0,
  "decode_tps": 0.0
}
```
- **Behavior on silence:** Returns valid dictionary with `text: ""` and `language: ""`. No exceptions raised.

---

## Spike S4: Hotkey Listener (`pynput`) on Windows

Executed script: `scripts/test_spike_s4.py`.

### Findings
- **Library:** `pynput` (v1.8.2) works on Windows 11 without requiring elevated administrative privileges.
- **Combination Parsing:**
  `keyboard.HotKey.parse("<ctrl>+<alt>+<space>")` cleanly resolves to:
  `[<Key.ctrl: <17>>, <Key.alt: <18>>, <32>]`.
- **Security & Keylogging Prevention:**
  - By wrapping `keyboard.HotKey`, key events outside the configured combination are completely disregarded.
  - Simulated test in `scripts/test_spike_s4.py` confirmed:
    - Pressing standard alphanumeric keys (`'a'`, `'b'`) results in **zero activations** and no stored text.
    - Full combination press activates callback once.
    - Releasing any key in the combination immediately deactivates.
