"""The Ultimate Generative Austrian Soundscape - Kaprun Comfort Edition.

Key idea in this version: each (mood, season, time_of_day[, variation])
combination maps to a STABLE seed. That seed controls both which tracks
get picked AND the exact effect parameters used. Result:
  - Run the same combination twice -> you get the exact same song back.
  - Run a different combination -> you reliably get a different song.
  - --all generates one file per combination in a single pass, reusing
    the track library that's loaded once into memory.
"""

from __future__ import annotations

import hashlib
import time
from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from random import Random

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

MOODS = ["happy", "sad", "stressed", "neutral"]
VALID_SEASONS = ["Summer", "Winter", "Spring", "Autumn"]
VALID_TIMES = ["Day", "Evening", "Night"]


# --------------------------------------------------------------------------
# Deterministic seeding
# --------------------------------------------------------------------------

def deterministic_seed(*parts: str | int) -> int:
    """Turn any combination of labels into a stable integer seed.

    Python's built-in hash() is randomized per-process (PYTHONHASHSEED),
    so it CANNOT be used for reproducibility across runs. hashlib is
    stable, which is what we need: the same combo always yields the
    same seed, forever, on any machine.
    """
    key = "|".join(str(p) for p in parts).encode("utf-8")
    digest = hashlib.sha256(key).hexdigest()
    return int(digest[:16], 16)  # plenty of entropy, fits in a 64-bit int


# --------------------------------------------------------------------------
# Mood detection (unchanged behaviour)
# --------------------------------------------------------------------------

def detect_emotion(image_file: Path) -> str:
    import cv2
    from deepface import DeepFace

    image = cv2.imread(str(image_file))
    if image is None:
        raise FileNotFoundError(f"Face image was not found or could not be read: {image_file}")

    result = DeepFace.analyze(image, actions=["emotion"], enforce_detection=False)
    analysis = result[0] if isinstance(result, list) else result
    return str(analysis.get("dominant_emotion", "neutral")).lower()


def detect_emotion_from_webcam(camera_index: int = 0) -> str:
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
            if key == 32:
                frame = preview
                break
            if key == 27:
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
    audio: np.ndarray  # shape (2, n_samples), resampled to library rate
    original_sr: float


class TrackLibrary:
    """Loads every track once, resamples to a common rate, keeps it in RAM."""

    def __init__(self, tracks_dir: Path, target_sr: float | None = None):
        self.tracks_dir = tracks_dir
        paths = sorted(list(tracks_dir.glob("*.mp3")) + list(tracks_dir.glob("*.wav")))
        if not paths:
            raise FileNotFoundError(f"No .mp3/.wav files found in {tracks_dir}")

        raw: list[tuple[Path, np.ndarray, float]] = []
        for p in paths:
            try:
                audio, sr = self._read_stereo(p)
            except Exception as exc:
                print(f"⚠️  Skipping {p.name}: {exc}")
                continue
            raw.append((p, audio, sr))

        if not raw:
            raise RuntimeError(f"None of the files in {tracks_dir} could be read.")

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

    def pick_layers(self, num_layers: int, rng: Random) -> list[LoadedTrack]:
        return rng.sample(self.tracks, min(num_layers, len(self.tracks)))


def crossfade_loop(audio: np.ndarray, target_length: int, crossfade_seconds: float = 0.75, sr: float = 44100.0) -> np.ndarray:
    """Loop `audio` up to `target_length` samples, crossfading each seam."""
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
            break

    return output[:, :target_length]


def render_mix(library: TrackLibrary, layers: list[LoadedTrack]) -> np.ndarray:
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
        mixed = mixed / peak * 0.98

    return mixed


def apply_psychoacoustics(audio: np.ndarray, sr: float, mood: str, season: str, time_of_day: str, rng: Random) -> np.ndarray:
    """Applies tailored acoustic spaces. All 'randomness' here comes from
    the seeded `rng`, so the same combo always yields the same effect
    settings, and different combos land on different (but still
    deterministic) settings.
    """
    effects = [Compressor(threshold_db=-15, ratio=2.5, attack_ms=10.0, release_ms=150.0)]

    if mood in {"sad", "stressed", "fear", "angry"}:
        # Deterministic per-combo variation within a comforting range
        cutoff = rng.uniform(1500, 2500)
        depth = rng.uniform(0.15, 0.3)
        effects.append(LowpassFilter(cutoff_frequency_hz=cutoff))
        effects.append(Chorus(rate_hz=0.5, depth=depth))
    else:
        cutoff = rng.uniform(4000, 6000)
        effects.append(LowpassFilter(cutoff_frequency_hz=cutoff))

    random_damping = rng.uniform(0.4, 0.7)

    if season == "Autumn":
        phaser_rate = rng.uniform(0.2, 0.4)
        effects.append(Phaser(rate_hz=phaser_rate, depth=0.4, mix=0.2))

    if time_of_day == "Night":
        delay_time = rng.uniform(0.35, 0.65)
        room_size = rng.uniform(0.8, 0.95)
        effects.extend([
            Delay(delay_seconds=delay_time, feedback=0.2, mix=0.2),
            Reverb(room_size=room_size, damping=random_damping, wet_level=0.5),
            Gain(gain_db=-1.5),
        ])
    else:
        room_size = rng.uniform(0.5, 0.7)
        effects.extend([
            Reverb(room_size=room_size, damping=random_damping, wet_level=0.3),
            Gain(gain_db=1.0),
        ])

    board = Pedalboard(effects)
    return board(audio, sr, reset=False)


def generate_one(
    library: TrackLibrary,
    mood: str,
    season: str,
    time_of_day: str,
    num_layers: int,
    variation: int = 0,
) -> Path:
    """Generate exactly one deterministic soundscape for this combination.

    Calling this again with the SAME arguments will always produce the
    same track selection and the same effect settings -> the same song.
    Bump `variation` if you want a different, still-reproducible, take
    on the same combination.
    """
    seed = deterministic_seed(mood, season, time_of_day, variation)
    rng = Random(seed)

    layers = library.pick_layers(num_layers, rng=rng)
    mixed_audio = render_mix(library, layers)

    print("🎛️ Applying psychoacoustic comfort effects...")
    final_audio = apply_psychoacoustics(mixed_audio, library.samplerate, mood, season, time_of_day, rng=rng)

    DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
    suffix = f"_v{variation}" if variation else ""
    output_filename = DEFAULT_OUTPUT / f"kaprun_{mood}_{season}_{time_of_day}{suffix}.wav"

    with AudioFile(str(output_filename), "w", library.samplerate, final_audio.shape[0]) as dest:
        dest.write(final_audio)

    return output_filename


def resolve_mood(args) -> str:
    if args.image is not None:
        return detect_emotion(args.image)
    if args.mood is not None:
        return args.mood

    print("\nHow should I get your mood?")
    print("  1. Detect via webcam")
    print("  2. Choose manually")
    choice = input("Choose 1-2 [default: 1]: ").strip()

    if choice == "2":
        return select_from_menu("Mood", MOODS, default=MOODS[0])

    return detect_emotion_from_webcam()


def select_from_menu(label: str, options: list[str], default: str, default_is_live: bool = False) -> str:
    """Show a numbered menu and let the user pick by number, or press
    Enter to accept the default. More reliable than free-text input,
    since there's no typo/capitalization to get wrong.
    """
    tag = "live default" if default_is_live else "default"
    print(f"\n{label} [{tag}: {default}]")
    for i, opt in enumerate(options, start=1):
        marker = " (default)" if opt == default else ""
        print(f"  {i}. {opt}{marker}")

    choice = input(f"Choose 1-{len(options)}, or press Enter for the default: ").strip()
    if not choice:
        return default
    if choice.isdigit() and 1 <= int(choice) <= len(options):
        return options[int(choice) - 1]

    print(f"⚠️  Didn't recognize '{choice}', falling back to the default ({default}).")
    return default


def resolve_env(args) -> tuple[str, str]:
    live_season, live_time = get_live_kaprun_context()

    if args.season:
        season = args.season.title()
    else:
        season = select_from_menu("Season", VALID_SEASONS, live_season, default_is_live=True)

    if args.time_of_day:
        time_of_day = args.time_of_day.title()
    else:
        time_of_day = select_from_menu("Time of day", VALID_TIMES, live_time, default_is_live=True)

    return season, time_of_day


def main() -> None:
    parser = ArgumentParser(description="Kaprun Generative Alpine Soundscape")
    parser.add_argument("--layers", type=int, default=4, help="Number of tracks to blend per mix (default 4)")
    parser.add_argument("--mood", choices=MOODS)
    parser.add_argument("--image", type=Path, help="Face image used to detect the mood automatically")
    parser.add_argument("--season", choices=VALID_SEASONS)
    parser.add_argument("--time", dest="time_of_day", choices=VALID_TIMES)
    parser.add_argument("--variation", type=int, default=0,
                         help="Bump this to get a different but still-reproducible take on the same combo")
    parser.add_argument("--all", action="store_true",
                         help="Generate one deterministic file for EVERY mood x season x time combination")
    args = parser.parse_args()

    if not TRACKS_DIR.exists():
        TRACKS_DIR.mkdir(parents=True)
        print(f"Created directory at {TRACKS_DIR}. Please place your tracks here.")
        return

    try:
        library = TrackLibrary(TRACKS_DIR)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"❌ {exc}")
        return

    if args.all:
        total = len(MOODS) * len(VALID_SEASONS) * len(VALID_TIMES)
        print(f"\n🌍 Generating all {total} combinations (deterministic, reruns will overwrite with identical results)...")
        done = 0
        for mood in MOODS:
            for season in VALID_SEASONS:
                for time_of_day in VALID_TIMES:
                    start = time.perf_counter()
                    out = generate_one(library, mood, season, time_of_day, args.layers, args.variation)
                    done += 1
                    elapsed = time.perf_counter() - start
                    print(f"✅ [{done}/{total}] {out.name} ({elapsed:.1f}s)")
        print(f"\n🏁 Done. {total} soundscapes written to {DEFAULT_OUTPUT}")
        return

    # Single combination mode
    mood = resolve_mood(args)
    print(f"\n👤 Detected/Selected Mood: {mood.title()}")

    season, time_of_day = resolve_env(args)
    print(f"🌲 Acoustic Environment: {season}, {time_of_day}")

    start = time.perf_counter()
    out = generate_one(library, mood, season, time_of_day, args.layers, args.variation)
    elapsed = time.perf_counter() - start
    print(f"✅ Success! Your personalized soundscape is ready: {out} ({elapsed:.1f}s)")


if __name__ == "__main__":
    main()