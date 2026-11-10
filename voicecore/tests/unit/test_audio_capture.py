from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from voicecore.audio.capture import AudioCapture, resolve_input_device
from voicecore.config import AudioConfig


def test_resolve_input_device_excludes_sound_mapper():
    mock_devices = [
        {"name": "Microsoft Sound Mapper - Input", "max_input_channels": 2, "default_samplerate": 44100.0},
        {"name": "Realtek Microphone Array", "max_input_channels": 2, "default_samplerate": 48000.0},
    ]
    with patch("sounddevice.query_devices", return_value=mock_devices):
        with patch("sounddevice.default.device", [0, 0]):
            idx, name, rate = resolve_input_device()
            # Must NOT pick Microsoft Sound Mapper (idx 0)
            assert idx == 1
            assert name == "Realtek Microphone Array"
            assert rate == 48000.0


def test_resolve_input_device_by_substring():
    mock_devices = [
        {"name": "Microsoft Sound Mapper - Input", "max_input_channels": 2, "default_samplerate": 44100.0},
        {"name": "Headset OnePlus", "max_input_channels": 1, "default_samplerate": 44100.0},
        {"name": "Realtek Microphone Array", "max_input_channels": 2, "default_samplerate": 48000.0},
    ]
    with patch("sounddevice.query_devices", return_value=mock_devices):
        idx, name, rate = resolve_input_device("oneplus")
        assert idx == 1
        assert "OnePlus" in name


def test_audio_capture_resampling_to_16k():
    mock_devices = [
        {"name": "Realtek Microphone Array", "max_input_channels": 2, "default_samplerate": 48000.0},
    ]
    with patch("sounddevice.query_devices", return_value=mock_devices):
        with patch("sounddevice.default.device", [0, 0]):
            cap = AudioCapture()
            assert cap.native_rate == 48000
            assert cap.target_rate == 16000

            # Simulate 1 second of recorded frames at 48000 Hz
            dummy_frames = [np.zeros(4800, dtype=np.float32) for _ in range(10)]
            cap._frames = dummy_frames

            output = cap.stop_capture()
            assert len(output) == 16000
            assert output.dtype == np.float32


def test_audio_capture_empty_stop():
    mock_devices = [
        {"name": "Realtek Mic", "max_input_channels": 1, "default_samplerate": 16000.0},
    ]
    with patch("sounddevice.query_devices", return_value=mock_devices):
        with patch("sounddevice.default.device", [0, 0]):
            cap = AudioCapture()
            output = cap.stop_capture()
            assert len(output) == 0
