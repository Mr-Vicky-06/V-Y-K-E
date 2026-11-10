"""Generate synthetic test audio clips for M2 negative tests: silence, keyboard noise, and music."""
import os
import wave
import numpy as np


def save_wav(path: str, samples: np.ndarray, rate: int = 16000) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    int16_samples = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(int16_samples.tobytes())
    print(f"Generated: {path} ({len(samples)/rate:.1f}s)")


def generate_clips():
    rate = 16000
    out_dir = os.path.join(os.path.dirname(__file__), "..", "tests", "test_data", "audio")

    # 1. Silence (3 seconds)
    silence = np.zeros(rate * 3, dtype=np.float32)
    save_wav(os.path.join(out_dir, "silence.wav"), silence, rate)

    # 2. Keyboard noise (3 seconds of sporadic clicking and room rumble)
    np.random.seed(42)
    noise = np.random.normal(0, 0.005, rate * 3).astype(np.float32)  # Ambient rumble
    # Add 8 sharp keyclick transients
    click_times = [0.2, 0.5, 0.9, 1.3, 1.6, 2.0, 2.3, 2.7]
    for ct in click_times:
        idx = int(ct * rate)
        click_len = int(0.02 * rate)  # 20ms click
        t = np.linspace(0, 1, click_len)
        click = np.sin(2 * np.pi * 1200 * t) * np.exp(-t * 15) * 0.35
        noise[idx : idx + click_len] += click.astype(np.float32)
    save_wav(os.path.join(out_dir, "keyboard_noise.wav"), noise, rate)

    # 3. Music clip (10 seconds of polyphonic musical chords)
    t10 = np.linspace(0, 10, rate * 10, endpoint=False)
    # A major chord arpeggio / melody: A4 (440Hz), C#5 (554.37Hz), E5 (659.25Hz), G#4 (415.3Hz)
    chord = (
        0.25 * np.sin(2 * np.pi * 440.0 * t10)
        + 0.20 * np.sin(2 * np.pi * 554.37 * t10)
        + 0.20 * np.sin(2 * np.pi * 659.25 * t10)
        + 0.15 * np.sin(2 * np.pi * 220.0 * t10)
    )
    # Add tremolo modulation
    tremolo = 0.5 + 0.5 * np.sin(2 * np.pi * 2.0 * t10)
    music = (chord * tremolo).astype(np.float32)
    save_wav(os.path.join(out_dir, "music_clip_10s.wav"), music, rate)


if __name__ == "__main__":
    generate_clips()

