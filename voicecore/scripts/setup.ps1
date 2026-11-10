# VoiceCore dev setup — Windows PowerShell. Run from project root or voicecore folder: .\scripts\setup.ps1
$ErrorActionPreference = "Stop"

if (Test-Path .\voicecore) { Set-Location .\voicecore }

# 1. Python 3.11+ check
$ver = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$ver -lt [version]"3.11") { throw "Python 3.11+ required, found $ver" }

# 2. Virtual environment
if (-not (Test-Path .venv)) { python -m venv .venv }
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

# 3. Dependencies (mic extra = numpy, soxr, sounddevice)
pip install "cactus-compute[mic]" pytest pynput
pip install -e .

# 4. Privacy: disable telemetry for this session AND for future sessions
$env:CACTUS_TELEMETRY = "0"
$env:NEEDLE_TELEMETRY = "0"
$env:DO_NOT_TRACK = "1"
[Environment]::SetEnvironmentVariable("CACTUS_TELEMETRY", "0", "User")
[Environment]::SetEnvironmentVariable("NEEDLE_TELEMETRY", "0", "User")
[Environment]::SetEnvironmentVariable("DO_NOT_TRACK", "1", "User")

# 5. First-run model download needs internet ONCE; verify_env.py triggers and checks it
python scripts\verify_env.py
if ($LASTEXITCODE -ne 0) { throw "verify_env.py failed - read its output before continuing" }
Write-Host "Setup OK. Next: disable network and run scripts\verify_env.py again to prove offline operation."
