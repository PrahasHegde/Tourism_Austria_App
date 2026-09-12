from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import cv2
import numpy as np
import os
from deepface import DeepFace
from pedalboard import Pedalboard, Reverb, Chorus, Gain, HighpassFilter
from pedalboard.io import AudioFile

app = FastAPI()

# This tells FastAPI to serve your local "images" folder to the web!
app.mount("/images", StaticFiles(directory="images"), name="images")

# Serve generated audio files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.post("/api/detect-mood")
async def detect_mood(image: UploadFile = File(...)):
    """Receives a webcam snapshot from the frontend and returns the emotion."""
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    try:
        # enforce_detection=False prevents crashes if lighting is bad
        result = DeepFace.analyze(img, actions=['emotion'], enforce_detection=False)
        mood = result[0]['dominant_emotion']
        return {"mood": mood}
    except Exception as e:
        return {"mood": "neutral"} # Fallback

@app.post("/api/generate-soundscape")
async def generate_soundscape(
    mood: str = Form(...), 
    season: str = Form(...), 
    time_of_day: str = Form(...)
):
    """Mixes the audio dynamically based on parameters."""
    
    # 1. Base Audio Selection 
    input_file = f"sounds/{season.lower()}_{time_of_day.lower()}.wav"
    output_file = f"static/generated_{mood}.wav"
    
    # 2. Build the Audio Architecture with Pedalboard
    board = Pedalboard([Gain(gain_db=-2.0)]) # Prevent clipping
    
    if mood in ["sad", "stressed", "fear", "disgust"]:
        # Slow, atmospheric, restorative
        board.append(Reverb(room_size=0.8, damping=0.5, wet_level=0.5))
        board.append(HighpassFilter(cutoff_frequency_hz=150)) # Remove harsh low rumble
    elif mood in ["happy", "surprise"]:
        # Bright, wide, energetic
        board.append(Chorus(rate_hz=1.0, depth=0.25))
        
    if time_of_day == "Night":
        board.append(Reverb(room_size=0.9)) # Massive Alpine echo
        
    # 3. Process the file
    if os.path.exists(input_file):
        with AudioFile(input_file) as f:
            with AudioFile(output_file, 'w', f.samplerate, f.num_channels) as o:
                while f.tell() < f.frames:
                    chunk = f.read(f.samplerate)
                    effected = board(chunk, f.samplerate, reset=False)
                    o.write(effected)
                    
    return {"track_url": f"/{output_file}"}

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("index.html") as f:
        return f.read()