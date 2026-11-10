from pathlib import Path
import socket
import pytest

from voicecore.asr.whistle import WhistleASR
from voicecore.config import VoiceCoreConfig
from voicecore.nlu.needle_router import NeedleRouter
from voicecore.policy.gate import PolicyGate
from voicecore.runtime.assistant import Assistant
from voicecore.tools.builtin.open_app import open_app
from voicecore.tools.registry import ToolRegistry


@pytest.mark.real_model
def test_pipeline_runs_100_percent_offline():
    """Verify that after initial setup, no network calls are made during audio pipeline runs."""
    pkg_root = Path(__file__).resolve().parents[2]
    config_path = pkg_root / "config" / "voicecore.toml"
    audio_path = pkg_root / "tests" / "test_data" / "audio" / "open_notepad_16k.wav"

    orig_connect = socket.socket.connect

    def blocked_connect(*args, **kwargs):
        raise OSError("Network unreachable (Strict Offline Enforcement)")

    socket.socket.connect = blocked_connect
    try:
        config = VoiceCoreConfig.from_toml(config_path)
        registry = ToolRegistry()

        def open_app_dry(app_name: str) -> dict:
            return open_app(app_name, dry_run=True)

        open_app_dry.__name__ = "open_app"
        registry.register(open_app_dry, tier="T1", name="open_app")

        gate = PolicyGate(config=config.policy, registry=registry)
        router = NeedleRouter(registry=registry, stateless=True)
        asr = WhistleASR(config=config.asr, debug_config=config.debug)

        assistant = Assistant(
            router=router,
            registry=registry,
            policy_gate=gate,
            asr=asr,
            config=config,
        )

        res = assistant.run_audio(audio_path)
        assert len(res) == 1
        assert res[0]["status"] == "executed"
        assert res[0]["call"]["name"] == "open_app"
    finally:
        socket.socket.connect = orig_connect

