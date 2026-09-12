"""The Ultimate Generative Austrian Soundscape - Kaprun Comfort Edition.

Changes in this version:
  - TrackLibrary: loads every source track ONCE and caches it in memory
    (resampled to a common rate), so generating multiple mixes in one
    run doesn't re-hit the disk every time.
  - --count N: generate N mixes in a single invocation, reusing the
    cached tracks and the mood/season/time you picked once.
  - Crossfaded looping instead of a hard tile+cut, so short tracks
    looped under longer ones don't click at the seam.
  - Sample-rate mismatches across your 23 files are detected and
    resampled instead of silently mixed at the wrong speed.
  - Peak-normalize instead of a blind clip, so loud mixes don't
    just get flattened.
"""

from __future__ import annotations

import random
import time
from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from pedalboard import (
    Chorus,
    Compressor,
    Delay,
    Gain,
    LowpassFilter,
    Pedalboard,
    Phaser,
    Resample,
    Reverb,
)
from pedalboard.io import AudioFile

ROOT = Path(__file__).resolve().parent
TRACKS_DIR = ROOT / "collections" / "Tracks"
DEFAULT_OUTPUT = ROOT / "static"

VALID_SEASONS = ["Summer", "Winter", "Spring", "Autumn"]
VALID_TIMES = ["Day", "Evening", "Night"]


# --------------------------------------------------------------------------
# Mood detection (unchanged behaviour, just kept separate from mixing logic)
# --------------------------------------------------------------------------

def detect_emotion(image_file: Path) -> str:
    """Detect the dominant facial emotion from an image file."""
    import cv2
    from deepface import DeepFace

    image = cv2.imread(str(image_file))
    if image is None:
        raise FileNotFoundError(f"Face image was not found or could not be read: {image_file}")

    result = DeepFace.analyze(image, actions=["emotion"], enforce_detection=False)
    analysis = result[0] if isinstance(result, list) else result
    return str(analysis.get("dominant_emotion", "neutral")).lower()


def detect_emotion_from_webcam(camera_index: int = 0) -> str:
    """Capture one webcam frame and detect its dominant emotion."""
    import cv2
    from deepface import DeepFace

    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        raise RuntimeError("Could not open the webcam. Use --image or --mood instead.")

    print("🏔️ Look at the camera. Press SPACE to capture your mood for the mix, or ESC to cancel.")
    frame = None
    try:
        while True:
            ok, preview = camera.read()
            if not ok:
                break
            cv2.imshow("Kaprun Alpine Sounds - Emotion Detection", preview)
            key = cv2.waitKey(1) & 0xFF
            if key == 32:  # Spacebar
                frame = preview
                break
            if key == 27:  # ESC
                raise RuntimeError("Emotion detection cancelled.")
    finally:
        camera.release()
        cv2.destroyAllWindows()

    if frame is None:
        return "neutral"

    result = DeepFace.analyze(frame, actions=["emotion"], enforce_detection=False)
    analysis = result[0] if isinstance(result, list) else result
    return str(analysis.get("dominant_emotion", "neutral")).lower()


def get_live_kaprun_context() -> tuple[str, str]:
    """Automatically detects the Season and Time of Day based on real-world time."""
    now = datetime.now()
    month = now.month
    hour = now.hour

    if month in (12, 1, 2):
        season = "Winter"
    elif month in (3, 4, 5):
        season = "Spring"
    elif month in (6, 7, 8):
        season = "Summer"
    else:
        season = "Autumn"

    if 6 <= hour < 17:
        time_of_day = "Day"
    elif 17 <= hour < 21:
        time_of_day = "Evening"
    else:
        time_of_day = "Night"

    return season, time_of_day


# --------------------------------------------------------------------------
# Track loading & caching
# --------------------------------------------------------------------------

@dataclass
class LoadedTrack:
    path: Path
    audio: np.ndarray  # shape (2, n_samples), already resampled to library rate
    original_sr: float


class TrackLibrary:
    """Loads every track once, resamples to a common rate, and keeps it in RAM.

    Build this once per run (or once per process, if you turn this into a
    long-lived service) and reuse it across as many generated mixes as you
    like via `pick_layers()` / `render_mix()`.
    """

    def __init__(self, tracks_dir: Path, target_sr: float | None = None):
        self.tracks_dir = tracks_dir
        paths = sorted(list(tracks_dir.glob("*.mp3")) + list(tracks_dir.glob("*.wav")))
        if not paths:
            raise FileNotFoundError(f"No .mp3/.wav files found in {tracks_dir}")

        raw: list[tuple[Path, np.ndarray, float]] = []
        for p in paths:
            try:
                audio, sr = self._read_stereo(p)
            except Exception as exc:  # skip unreadable files instead of aborting the whole run
                print(f"⚠️  Skipping {p.name}: {exc}")
                continue
            raw.append((p, audio, sr))

        if not raw:
            raise RuntimeError(f"None of the files in {tracks_dir} could be read.")

        # Pick a common sample rate: the one requested, else the most common
        # rate among the source files (so we resample the minority, not the
        # majority).
        if target_sr is None:
            rates = [sr for _, _, sr in raw]
            target_sr = max(set(rates), key=rates.count)
        self.samplerate = target_sr

        self.tracks: list[LoadedTrack] = []
        for p, audio, sr in raw:
            if sr != target_sr:
                print(f"↺ Resampling {p.name}: {sr:.0f} Hz → {target_sr:.0f} Hz")
                audio = Resample(target_sample_rate=target_sr)(audio, sr, reset=False)
            self.tracks.append(LoadedTrack(path=p, audio=audio, original_sr=sr))

        print(f"📚 Loaded {len(self.tracks)} tracks at {self.samplerate:.0f} Hz.")

    @staticmethod
    def _read_stereo(file_path: Path) -> tuple[np.ndarray, float]:
        with AudioFile(str(file_path)) as f:
            samplerate = f.samplerate
            audio = f.read(f.frames)
            if audio.shape[0] == 1:
                audio = np.vstack((audio, audio))
            elif audio.shape[0] > 2:
                audio = audio[:2, :]
            return audio, samplerate

    def pick_layers(self, num_layers: int, rng: random.Random | None = None) -> list[LoadedTrack]:
        rng = rng or random
        return rng.sample(self.tracks, min(num_layers, len(self.tracks)))


def crossfade_loop(audio: np.ndarray, target_length: int, crossfade_seconds: float = 0.75, sr: float = 44100.0) -> np.ndarray:
    """Loop `audio` up to `target_length` samples, crossfading each seam
    instead of hard-cutting, so short tracks don't click when they repeat
    under a longer one.
    """
    channels, length = audio.shape
    if length >= target_length:
        return audio[:, :target_length]

    crossfade_samples = min(int(crossfade_seconds * sr), length // 2) if length > 1 else 0
    output = np.zeros((channels, target_length))
    output[:, :length] = audio
    pos = length

    fade_out = np.linspace(1.0, 0.0, crossfade_samples) if crossfade_samples else np.array([])
    fade_in = np.linspace(0.0, 1.0, crossfade_samples) if crossfade_samples else np.array([])

    while pos < target_length:
        remaining = target_length - pos
        take = min(length, remaining)

        if crossfade_samples and pos >= crossfade_samples:
            # Blend the tail of what's already written with the head of the next repeat
            output[:, pos - crossfade_samples:pos] *= fade_out
            head = audio[:, :crossfade_samples] * fade_in
            output[:, pos - crossfade_samples:pos] += head
            body_len = take - crossfade_samples
            if body_len > 0:
                output[:, pos:pos + body_len] = audio[:, crossfade_samples:crossfade_samples + body_len]
            pos += max(take - crossfade_samples, 0) if take > crossfade_samples else take
        else:
            output[:, pos:pos + take] = audio[:, :take]
            pos += take

        if take <= 0:
            break  # safety valve, shouldn't normally trigger

    return output[:, :target_length]


def render_mix(library: TrackLibrary, layers: list[LoadedTrack]) -> np.ndarray:
    """Mix a set of already-loaded tracks into one stereo bed."""
    print(f"\n🎚️  Mixing {len(layers)} layers:")
    for layer in layers:
        print(f"   - {layer.path.name}")

    max_length = max(layer.audio.shape[1] for layer in layers)
    mixed = np.zeros((2, max_length))

    for layer in layers:
        looped = crossfade_loop(layer.audio, max_length, sr=library.samplerate)
        mixed += looped * (1.0 / len(layers))

    peak = np.max(np.abs(mixed))
    if peak > 1.0:
        mixed = mixed / peak * 0.98  # gentle peak-normalize instead of hard clipping

    return mixed


def apply_psychoacoustics(audio: np.ndarray, sr: float, mood: str, season: str, time_of_day: str) -> np.ndarray:
    """Applies tailored acoustic spaces based on your mood and the environment."""
    effects = [Compressor(threshold_db=-15, ratio=2.5, attack_ms=10.0, release_ms=150.0)]

    if mood in {"sad", "stressed", "fear", "angry"}:
        effects.append(LowpassFilter(cutoff_frequency_hz=2000))
        effects.append(Chorus(rate_hz=0.5, depth=0.2))
    else:
        effects.append(LowpassFilter(cutoff_frequency_hz=5000))

    random_damping = random.uniform(0.4, 0.7)

    if season == "Autumn":
        effects.append(Phaser(rate_hz=0.3, depth=0.4, mix=0.2))

    if time_of_day == "Night":
        effects.extend([
            Delay(delay_seconds=0.5, feedback=0.2, mix=0.2),
            Reverb(room_size=0.9, damping=random_damping, wet_level=0.5),
            Gain(gain_db=-1.5),
        ])
    else:
        effects.extend([
            Reverb(room_size=0.6, damping=random_damping, wet_level=0.3),
            Gain(gain_db=1.0),
        ])

    board = Pedalboard(effects)
    return board(audio, sr, reset=False)


def resolve_mood(args) -> str:
    if args.image is not None:
        return detect_emotion(args.image)
    if args.mood is not None:
        return args.mood
    return detect_emotion_from_webcam()


def resolve_env(args) -> tuple[str, str]:
    live_season, live_time = get_live_kaprun_context()

    if args.season:
        season = args.season.title()
    else:
        season_input = input(f"Season [Press Enter to use live: {live_season}]: ").strip().title()
        season = season_input if season_input in VALID_SEASONS else live_season

    if args.time_of_day:
        time_of_day = args.time_of_day.title()
    else:
        time_input = input(f"Time of day [Press Enter to use live: {live_time}]: ").strip().title()
        time_of_day = time_input if time_input in VALID_TIMES else live_time

    return season, time_of_day


def main() -> None:
    parser = ArgumentParser(description="Kaprun Generative Alpine Soundscape")
    parser.add_argument("--layers", type=int, default=4, help="Number of tracks to blend per mix (default 4)")
    parser.add_argument("--count", type=int, default=1, help="How many mixes to generate in this run (default 1)")
    parser.add_argument("--mood", choices=["happy", "sad", "stressed", "neutral"])
    parser.add_argument("--image", type=Path, help="Face image used to detect the mood automatically")
    parser.add_argument("--season", choices=VALID_SEASONS)
    parser.add_argument("--time", dest="time_of_day", choices=VALID_TIMES)
    parser.add_argument("--seed", type=int, help="Random seed, for reproducible track selection")
    parser.add_argument("--vary-per-mix", action="store_true",
                         help="With --count > 1, pick a fresh random track selection for each mix "
                              "instead of just repeating a new random draw with the same mood/season/time.")
    args = parser.parse_args()

    if not TRACKS_DIR.exists():
        TRACKS_DIR.mkdir(parents=True)
        print(f"Created directory at {TRACKS_DIR}. Please place your tracks here.")
        return

    rng = random.Random(args.seed) if args.seed is not None else random

    try:
        library = TrackLibrary(TRACKS_DIR)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"❌ {exc}")
        return

    mood = resolve_mood(args)
    print(f"\n👤 Detected/Selected Mood: {mood.title()}")

    season, time_of_day = resolve_env(args)
    print(f"🌲 Acoustic Environment: {season}, {time_of_day}")

    DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)

    for i in range(args.count):
        start = time.perf_counter()
        layers = library.pick_layers(args.layers, rng=rng)
        mixed_audio = render_mix(library, layers)

        print("🎛️ Applying psychoacoustic comfort effects...")
        final_audio = apply_psychoacoustics(mixed_audio, library.samplerate, mood, season, time_of_day)

        unique_id = rng.randint(1000, 9999)
        suffix = f"_{i + 1}" if args.count > 1 else ""
        output_filename = DEFAULT_OUTPUT / f"kaprun_{mood}_{season}_{time_of_day}_{unique_id}{suffix}.wav"

        with AudioFile(str(output_filename), "w", library.samplerate, final_audio.shape[0]) as dest:
            dest.write(final_audio)

        elapsed = time.perf_counter() - start
        print(f"✅ [{i + 1}/{args.count}] Saved {output_filename.name} in {elapsed:.1f}s")

    print(f"\n🏁 Done. {args.count} soundscape(s) written to {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()