# 🎵 Alpine Sounds - Austria Tourism Soundscape Generator

<img width="1832" height="1017" alt="image" src="https://github.com/user-attachments/assets/593c7c70-9369-46b6-9d31-77bf66e70d94" />


An innovative web application that creates personalized, emotion-driven soundscapes celebrating Austrian alpine beauty and nature. Users have their emotion detected via facial recognition, select their preferred season and time of day, and receive a custom 30-second audio experience blending natural sounds from Austria's landscapes with AI-generated ambient audio.

## ✨ Key Features

### 🎭 **Emotion Detection**
- Real-time facial emotion recognition using DeepFace
- Detects: Happy, Sad, Stressed, Neutral, Surprised, Fearful, Disgusted
- Works with webcam capture or uploaded images
- Fallback to manual mood selection

### 🎵 **Personalized Soundscapes**
- Generates unique 30-second audio tracks based on:
  - **Detected Emotion**: Happy, Sad, Stressed, Neutral moods
  - **Season**: Spring, Summer, Autumn, Winter
  - **Time of Day**: Morning, Afternoon, Evening, Night
- Blends multiple authentic nature sounds with AI-generated audio

### 🗺️ **Interactive Sound Map**
- Browse and explore sounds collected from Austria's natural regions
- Filter sounds by category, season, and location
- Play individual soundscapes directly from the map
- Learn about Austrian fauna and alpine ecosystems

### 🎚️ **Audio Processing**
- Professional effects pipeline using Pedalboard:
  - Emotion-appropriate reverb for depth and space
  - Compression for dynamic control
  - EQ adjustments based on mood
  - High-pass filtering for clarity
  - Chorus effects for brightness
- Mood-aware effect intensity and parameters

### 🤖 **AI Audio Generation**
- Uses `audio_gen.py` to create synthetic Austrian ambient audio
- Generates emotional soundscapes matching mood, season, and time context
- Combines with real nature recordings for authentic experience
- MP3 export for easy sharing and download

### 📱 **Sharing & QR Codes**
- Generate branded QR codes for generated tracks
- Share tracks with Austrian tourism branding
- Track download links with metadata

## 🏗️ Architecture

### Backend (Python)
```
audio_gen.py           # Core AI audio generation pipeline
├── Emotion detection from images/webcam
├── Mood-to-audio mapping
├── Effect chain building (Pedalboard)
└── WAV/MP3 export

app.py                 # FastAPI server
├── REST API endpoints
├── Session management
└── Static file serving

Sound Library Components:
├── sound_sampler.py           # Intelligent sound selection
├── audio_effects.py           # Pedalboard effect chains
├── emotion_mapper.py          # Mood-to-musical characteristics
├── sound_processor_mp3.py     # Audio mixing & MP3 conversion
├── sound_library_ingester.py  # Database management
├── qr_generator.py            # QR code creation
└── config.py                  # Central configuration
```

### Frontend (HTML/CSS/JavaScript)
```
index.html             # Main web interface
├── Emotion detection UI
├── Interactive sound map
├── Season/time selection
├── Audio player
└── Download/share controls
```

### Data
```
collections/
├── Beats/              # Mood-specific music beds (MP3)
│   ├── Happy.mp3
│   ├── Hopeful.mp3
│   └── Relaxed.mp3
└── sounds/             # Nature recordings (by season)

outputs/
└── generated_tracks/   # Generated MP3 files
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- FFmpeg (for MP3 conversion)
- Modern web browser with JavaScript enabled

### Installation

```bash
# Clone the repository
git clone https://github.com/PrahasHegde/Tourism_Austria_App.git
cd Tourism_Austria_App

# Install Python dependencies
pip install -r requirements.txt

# Install optional libraries for full feature support
pip install pedalboard librosa soundfile pydub opencv-python deepface qrcode pillow
```

### Running the Application

**Option 1: Full Web Application**
```bash
# Start the FastAPI server
python app.py

# Or use Uvicorn directly
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Open http://localhost:8000 in your browser
```

**Option 2: Command-Line Generation**
```bash
# Generate with mood detection from webcam
python audio_gen.py --season Summer --time Day

# Generate with image-based emotion detection
python audio_gen.py --image face.jpg --season Winter --time Evening

# Generate with specific mood
python audio_gen.py --mood happy --season Spring --time Morning --output my_track.wav
```

## 📡 API Endpoints

### Emotion Detection
```bash
POST /api/detect-mood
Content-Type: multipart/form-data
Body: image=[binary image file]

Response:
{
  "mood": "happy|sad|stressed|neutral|fearful|disgusted|surprised"
}
```

### Generate Soundscape
```bash
POST /api/generate
Content-Type: application/json

Body:
{
  "mood": "happy",
  "season": "Summer",
  "time_of_day": "Day"
}

Response:
{
  "success": true,
  "file_path": "outputs/generated_tracks/generated_happy_summer_day.wav",
  "metadata": { ... },
  "download_url": "/api/download/generated_happy_summer_day.mp3"
}
```

### Get Available Options
```bash
GET /api/moods          # List available moods
GET /api/seasons        # List available seasons  
GET /api/times          # List available times
```

### Download Track
```bash
GET /api/download/{filename}
Returns: MP3 audio file
```

### Sound Map Data
```bash
GET /api/sounds         # Get all available sounds with locations
GET /api/sounds?season=Summer  # Filter by season
GET /api/sounds?mood=happy     # Filter by mood compatibility
```

## 🎯 How It Works

### User Flow
1. **Emotion Capture** 
   - User enables webcam or uploads photo
   - DeepFace analyzes facial expressions
   - Dominant emotion detected (or user manually selects)

2. **Context Selection**
   - User selects favorite season (Spring, Summer, Autumn, Winter)
   - User selects time of day (Morning, Afternoon, Evening, Night)

3. **Audio Generation**
   - Emotion profile created with musical characteristics
   - Intelligent sound selection from nature library
   - Base music bed chosen based on mood
   - Effects chain built matching emotion intensity
   - Audio mixed and normalized

4. **Playback & Sharing**
   - 30-second personalized track ready
   - User can play, download, or share with QR code
   - Metadata includes mood, season, time, and sustainability message

## 🔧 Audio Generation Pipeline

### audio_gen.py Functions

**Detect Emotion**
```python
def detect_emotion(image_file: Path) -> str
def detect_emotion_from_webcam(camera_index: int = 0) -> str
```

**Build Effects**
```python
def build_effects(mood: str, time_of_day: str) -> Pedalboard
```
Creates mood-appropriate effect chains:
- **Sad/Stressed**: Reverb + High-pass filter (atmospheric, calming)
- **Happy**: Chorus effect (bright, energetic)
- **Night**: Additional reverb for alpine echo effect

**Generate Soundscape**
```python
def generate_soundscape(
    mood: str = "neutral",
    season: str = "Summer",
    time_of_day: str = "Day",
    output_file: Path = None,
    image_file: Path = None
) -> Path
```
Main pipeline combining everything.

## 🎨 Customization

### Mood Profiles
Edit mappings in `audio_gen.py`:
```python
source_by_mood = {
    "happy": COLLECTIONS / "Beats" / "Happy.mp3",
    "sad": COLLECTIONS / "Beats" / "Hopeful.mp3",
    "stressed": COLLECTIONS / "Beats" / "Relaxed.mp3",
}
```

### Effect Parameters
Modify Pedalboard effects in `build_effects()`:
```python
Reverb(room_size=0.8, damping=0.5, wet_level=0.45)  # Adjust room size
HighpassFilter(cutoff_frequency_hz=150)             # Adjust frequency
Chorus(rate_hz=1.0, depth=0.25)                     # Adjust chorus speed
```

### Sound Library
Add new sounds to the collection:
```bash
# Copy audio files to collections/
cp my_sound.mp3 collections/Beats/
cp nature_recording.wav collections/sounds/

# Ingest sounds into database
python sound_library_ingester.py --ingest
```

## 📊 Sound Categories

### **Beats** (Base Music Beds)
- Happy.mp3 - Uplifting, energetic foundation
- Hopeful.mp3 - Inspiring, moderate energy
- Relaxed.mp3 - Calming, soothing baseline

### **Sounds** (Nature Recordings by Season)
- **Spring**: Bird songs, flowing water, gentle breezes
- **Summer**: Alpine insects, meadow ambience, thunder
- **Autumn**: Leaf rustles, wind, harvest sounds
- **Winter**: Snow crunch, wind howls, frozen silence

### **Special Categories**
- **Fauna**: Animal sounds (birds, insects, distant wildlife)
- **Yodelling**: Traditional Austrian vocal performances
- **Ambient**: Atmospheric pads, texture loops

## ⚙️ Configuration

Key settings in `config.py` and `audio_gen.py`:

```python
# Audio output
TARGET_DURATION = 30              # seconds
SAMPLE_RATE = 44100               # Hz
OUTPUT_FORMAT = "mp3"             # or "wav"

# Paths
COLLECTIONS = ROOT / "collections"
DEFAULT_OUTPUT = ROOT / "static"

# Moods supported
MOODS = ["happy", "sad", "stressed", "neutral"]
SEASONS = ["Summer", "Winter", "Spring", "Autumn"]
TIMES = ["Day", "Evening", "Night"]
```

## 📦 Dependencies

See `requirements.txt`:
- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **Pedalboard** - Professional audio effects
- **librosa** - Audio analysis
- **soundfile** - Audio I/O
- **pydub** - Audio manipulation & MP3 conversion
- **DeepFace** - Emotion detection
- **OpenCV** - Image processing
- **qrcode** - QR code generation
- **Pillow** - Image processing

## 🌐 Deployment

### Local Development
```bash
python app.py
```

### Production with Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

### Docker
```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t alpine-sounds .
docker run -p 8000:8000 alpine-sounds
```

## 🗺️ Interactive Sound Map Features

- **Geographical Display**: Shows locations where sounds were recorded
- **Sound Preview**: Click any location to hear the actual recording
- **Metadata**: Season, time of day, mood compatibility, audio characteristics
- **Filtering**: Filter by season, mood, fauna type
- **Sharing**: Share specific sounds with metadata

## 📝 Example Workflow

```bash
# 1. User accesses web app
open http://localhost:8000

# 2. Emotion detection via webcam
# (SPACE to capture, ESC to cancel)

# 3. System detects: "happy"
# User selects: Season=Summer, Time=Day

# 4. Backend generates:
# - Gets Happy.mp3 base track
# - Applies Chorus effect (bright, energetic)
# - Selects complementary summer day sounds
# - Mixes audio layers
# - Normalizes output

# 5. Result: 30-second personalized track
# User can:
# - Play it immediately
# - Download as MP3
# - Share with QR code
# - Explore related sounds on map
```

## 🎓 Learning Resources

- **Pedalboard Documentation**: https://github.com/spotify/pedalboard
- **DeepFace**: https://github.com/serengp/deepface
- **Librosa Audio Processing**: https://librosa.org/
- **FastAPI**: https://fastapi.tiangolo.com/

## 🤝 Contributing

Contributions welcome! Ways to help:
- Add more Austrian nature recordings
- Improve emotion detection accuracy
- Enhance the interactive map
- Add new mood/season combinations
- Optimize audio processing

## 📄 License

[Add your license here - e.g., MIT, Apache 2.0]

## 🎬 Credits

- Emotion detection: DeepFace
- Audio effects: Spotify Pedalboard
- Alpine sounds: Collected from Austrian nature reserves
- Frontend design: Austrian tourism aesthetic

---

**Experience the alpine soundscapes of Austria — personalized for your emotion, season, and time. 🏔️🎵**

### Quick Demo
```bash
# Generate a quick sample
python audio_gen.py --mood happy --season Summer --time Day
# Listen to: static/generated_happy_summer_day.wav
```

Enjoy your personalized Austrian soundscape experience! 🇦🇹
