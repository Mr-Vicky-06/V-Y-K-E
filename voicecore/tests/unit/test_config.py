from pathlib import Path
import pytest
from voicecore.config import VoiceCoreConfig, PolicyConfig


def test_default_config():
    cfg = VoiceCoreConfig()
    assert cfg.audio.hotkey == "ctrl+alt+space"
    assert cfg.audio.max_seconds == 30
    assert cfg.asr.language == "en"
    assert cfg.policy.act_threshold == 0.80
    assert cfg.policy.confirm_threshold == 0.50
    assert cfg.search.max_results == 10


def test_load_config_from_toml(tmp_path: Path):
    toml_content = """
[audio]
hotkey = "ctrl+space"
max_seconds = 15

[policy]
act_threshold = 0.85
confirm_threshold = 0.60
"""
    cfg_file = tmp_path / "voicecore.toml"
    cfg_file.write_text(toml_content, encoding="utf-8")

    cfg = VoiceCoreConfig.from_toml(cfg_file)
    assert cfg.audio.hotkey == "ctrl+space"
    assert cfg.audio.max_seconds == 15
    assert cfg.policy.act_threshold == 0.85
    assert cfg.policy.confirm_threshold == 0.60


def test_invalid_thresholds(tmp_path: Path):
    toml_content = """
[policy]
act_threshold = 0.40
confirm_threshold = 0.70
"""
    cfg_file = tmp_path / "voicecore.toml"
    cfg_file.write_text(toml_content, encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid policy thresholds"):
        VoiceCoreConfig.from_toml(cfg_file)

