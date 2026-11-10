# VYKE — Local Offline Voice Control Layer

VYKE is an offline, privacy-first voice layer for Windows that turns speech into safe, local actions. Designed as a standalone assistant foundation and an embeddable plugin for other agent and automation systems.

## Core Architecture
- **Speech-to-Text (ASR):** Whistle (16.9 MB, CPU, Apache-2.0, offline)
- **NLU & Intent Routing:** Needle 3 (Cactus Compute, grammar-constrained tool calls + confidence)
- **Safety & Policy Gate:** Multi-tier authorization gate (T0 read-only, T1 bounded, T2 privileged/blocked in P0)
- **Plugin Surface:** Embedded Python API (Level 1) & Local WebSocket sidecar (Level 2)

## Project Structure
- `voicecore/`: Core Python library and runtime
  - `config/`: Configuration files (`voicecore.toml`, `apps.allowlist.json`)
  - `docs/`: Technical specifications, architecture, and milestones
  - `scripts/`: Environment setup and verification scripts
  - `src/voicecore/`: Package source code (audio capture, ASR, NLU, policy, tools, runtime, plugin)
  - `tests/`: Unit tests and model evaluation datasets

## Documentation & Progress
- [PRD](voicecore/docs/01_PRD.md)
- [Architecture](voicecore/docs/02_ARCHITECTURE.md)
- [Tech Stack & Ledger](voicecore/docs/03_TECH_STACK.md)
- [Tool Specification](voicecore/docs/04_TOOL_SPEC.md)
- [Security Guardrails](voicecore/docs/06_SECURITY_GUARDRAILS.md)
- [Progress Log](voicecore/docs/PROGRESS.md)
