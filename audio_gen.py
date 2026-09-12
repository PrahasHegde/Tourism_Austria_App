"""Create a personalized Austrian soundscape."""

from argparse import ArgumentParser
from pathlib import Path

from pedalboard import Chorus, Gain, HighpassFilter, Pedalboard, Reverb
from pedalboard.io import AudioFile


ROOT = Path(__file__).resolve().parent
COLLECTIONS = ROOT / "collections"
DEFAULT_OUTPUT = ROOT / "static"


def detect_emotion(image_file: Path) -> str:
	"""Detect the dominant facial emotion from an image file."""
	import cv2
	from deepface import DeepFace

	image = cv2.imread(str(image_file))
	if image is None:
		raise FileNotFoundError(f"Face image was not found or could not be read: {image_file}")

	result = DeepFace.analyze(
		image,
		actions=["emotion"],
		enforce_detection=False,
	)
	analysis = result[0] if isinstance(result, list) else result
	return str(analysis.get("dominant_emotion", "neutral")).lower()


def detect_emotion_from_webcam(camera_index: int = 0) -> str:
	"""Capture one webcam frame and detect its dominant emotion."""
	import cv2

	camera = cv2.VideoCapture(camera_index)
	if not camera.isOpened():
		raise RuntimeError("Could not open the webcam. Use --image face.jpg instead.")

	print("Look at the camera. Press SPACE to capture your emotion, or ESC to cancel.")
	frame = None
	try:
		while True:
			ok, preview = camera.read()
			if not ok:
				raise RuntimeError("Could not read a frame from the webcam.")
			cv2.imshow("Austria Alpine Sounds - Emotion Detection", preview)
			key = cv2.waitKey(1) & 0xFF
			if key == 32:
				frame = preview
				break
			if key == 27:
				raise RuntimeError("Emotion detection was cancelled.")
	finally:
		camera.release()
		cv2.destroyAllWindows()

	if frame is None:
		raise RuntimeError("No webcam frame was captured.")

	from deepface import DeepFace

	result = DeepFace.analyze(frame, actions=["emotion"], enforce_detection=False)
	analysis = result[0] if isinstance(result, list) else result
	return str(analysis.get("dominant_emotion", "neutral")).lower()


def choose_source(mood: str) -> Path:
	"""Choose a local music bed based on the detected mood."""
	source_by_mood = {
		"happy": COLLECTIONS / "Beats" / "Happy.mp3",
		"sad": COLLECTIONS / "Beats" / "Hopeful.mp3",
		"stressed": COLLECTIONS / "Beats" / "Relaxed.mp3",
		"neutral": COLLECTIONS / "Beats" / "Relaxed.mp3",
	}
	return source_by_mood.get(mood.lower(), source_by_mood["neutral"])


def build_effects(mood: str, time_of_day: str) -> Pedalboard:
	"""Build effects that match the requested mood and time of day."""
	effects = [Gain(gain_db=-2.0)]

	if mood.lower() in {"sad", "stressed"}:
		effects.extend([
			Reverb(room_size=0.8, damping=0.5, wet_level=0.45),
			HighpassFilter(cutoff_frequency_hz=150),
		])
	elif mood.lower() == "happy":
		effects.append(Chorus(rate_hz=1.0, depth=0.25))

	if time_of_day.lower() == "night":
		effects.append(Reverb(room_size=0.9, wet_level=0.35))

	return Pedalboard(effects)


def generate_soundscape(
	mood: str | None = "neutral",
	season: str = "Summer",
	time_of_day: str = "Day",
	output_file: Path | None = None,
	image_file: Path | None = None,
) -> Path:
	"""Process a local music bed and return the generated file path."""
	if image_file is not None:
		mood = detect_emotion(image_file)
	mood = (mood or "neutral").lower()
	source_file = choose_source(mood)
	if not source_file.exists():
		raise FileNotFoundError(f"Source audio was not found: {source_file}")

	if output_file is None:
		filename = f"generated_{mood.lower()}_{season.lower()}_{time_of_day.lower()}.wav"
		output_file = DEFAULT_OUTPUT / filename
	output_file.parent.mkdir(parents=True, exist_ok=True)

	board = build_effects(mood, time_of_day)
	with AudioFile(str(source_file)) as source:
		with AudioFile(
			str(output_file),
			"w",
			source.samplerate,
			source.num_channels,
		) as destination:
			while source.tell() < source.frames:
				chunk = source.read(source.samplerate)
				destination.write(board(chunk, source.samplerate, reset=False))

	return output_file


def main() -> None:
	parser = ArgumentParser(description="Generate an Austrian alpine soundscape.")
	parser.add_argument("--mood", choices=["happy", "sad", "stressed", "neutral"])
	parser.add_argument("--image", type=Path, help="Face image used to detect the mood automatically")
	parser.add_argument("--season", choices=["Summer", "Winter", "Spring", "Autumn"])
	parser.add_argument("--time", dest="time_of_day", choices=["Day", "Evening", "Night"])
	parser.add_argument("--output", type=Path)
	args = parser.parse_args()

	if args.image is not None:
		mood = detect_emotion(args.image)
	elif args.mood is not None:
		mood = args.mood
	else:
		mood = detect_emotion_from_webcam()
	print(f"Detected mood: {mood}")

	season = args.season or input("Season (Summer/Winter/Spring/Autumn): ").strip().title()
	time_of_day = args.time_of_day or input("Time of day (Day/Evening/Night): ").strip().title()
	if season not in {"Summer", "Winter", "Spring", "Autumn"}:
		parser.error("season must be Summer, Winter, Spring, or Autumn")
	if time_of_day not in {"Day", "Evening", "Night"}:
		parser.error("time must be Day, Evening, or Night")

	output = generate_soundscape(
		mood=mood,
		season=season,
		time_of_day=time_of_day,
		output_file=args.output,
		image_file=None,
	)
	print(f"Generated: {output}")


if __name__ == "__main__":
	main()
