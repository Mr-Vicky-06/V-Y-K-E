import numpy as np
import pytest

from voicecore.asr.whistle import WhistleASR
from voicecore.config import ASRConfig, DebugConfig


@pytest.mark.real_model
def test_whistle_asr_silence_numpy():
    asr = WhistleASR()
    silence = np.zeros(16000, dtype=np.float32)  # 1 second of silence
    transcript = asr.transcribe(silence)
    assert transcript.text == ""
    assert transcript.asr_ms >= 0.0


def test_whistle_asr_clean_error_handling():
    asr = WhistleASR()
    # Non-existent file path
    transcript = asr.transcribe("non_existent_audio_file.wav")
    assert transcript.text == ""
    assert transcript.asr_ms >= 0.0


def test_whistle_asr_config():
    cfg = ASRConfig(language="en", keywords=["Antigravity", "Chennai"])
    asr = WhistleASR(config=cfg)
    assert asr.config.language == "en"
    assert "Antigravity" in asr.config.keywords
