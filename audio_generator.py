from pydub import AudioSegment
import random

# 1. CATALOG YOUR EXACT FILE PATHS
SOUNDS = {
    "atmosphere": {
        "spring": ["collections/Ambient/Mountain Air.mp3", "collections/Ambient/At the water.mp3"],
        "summer": ["collections/Ambient/Mountain Air.mp3", "collections/Ambient/At the water.mp3"],
        "autumn": ["collections/Ambient/Hiking.mp3"],
        "winter": ["collections/Ambient/Winter wind.mp3"]
    },
    "musical_core": {
        "happy": "collections/Beats/Happy.mp3",
        "neutral": "collections/Beats/Relaxed.mp3", # Or collections/Tracks/main song.mp3
        "sad": "collections/Beats/Hopeful.mp3"
    },
    "time_accents": {
        "day": [
            "collections/Fauna/Birds.mp3", 
            "collections/Fauna/Cow.mp3", 
            "collections/Fauna/Horses Galopp.mp3",
            "collections/Ambient/Churchbells.mp3"
        ],
        "evening": [
            "collections/Ambient/Crowd Evening Event.mp3", 
            "collections/Ambient/Cutlery.mp3", 
            "collections/Ambient/Wineglass.mp3",
            "collections/Ambient/Bottles.mp3"
        ],
        "night": [
            "collections/Ambient/Evening wind.mp3", 
            "collections/Fauna/Horses whicker.mp3"
        ]
    },
    "mood_accents": {
        "happy": [
            "collections/Yodelling/Yodelling.mp3", 
            "collections/Instruments/Dance Schuachplattler.mp3",
            "collections/Ambient/Cheerful crowd.mp3"
        ],
        "neutral": ["collections/Instruments/Accordion.mp3"],
        "sad": [] # Keep sad sparse
    }
}

def generate_alpine_mix(mood, time_of_day, season, duration_ms=60000):
    # 2. BUILD THE FOUNDATION (Atmosphere + Musical Core)
    # Load atmosphere (Season)
    atmos_path = random.choice(SOUNDS["atmosphere"].get(season, SOUNDS["atmosphere"]["summer"]))
    atmosphere = AudioSegment.from_file(atmos_path)
    
    # Load musical core (Mood)
    core_path = SOUNDS["musical_core"].get(mood, SOUNDS["musical_core"]["neutral"])
    core_music = AudioSegment.from_file(core_path)

    # Loop or trim core music to target duration
    if len(core_music) < duration_ms:
        core_music = core_music * (duration_ms // len(core_music) + 1)
    final_mix = core_music[:duration_ms]

    # Loop or trim atmosphere, lower its volume, and overlay onto the music
    if len(atmosphere) < duration_ms:
        atmosphere = atmosphere * (duration_ms // len(atmosphere) + 1)
    atmosphere = atmosphere[:duration_ms] - 6 # Reduce atmosphere volume by 6dB
    final_mix = final_mix.overlay(atmosphere)

    # 3. GATHER ACCENTS (Time of Day + Mood)
    accents_to_play = []
    
    # Pick 1 or 2 time-of-day accents
    time_pool = SOUNDS["time_accents"].get(time_of_day, [])
    if time_pool:
        accents_to_play.extend(random.sample(time_pool, min(2, len(time_pool))))
        
    # Pick 1 mood-specific accent if available
    mood_pool = SOUNDS["mood_accents"].get(mood, [])
    if mood_pool:
        accents_to_play.append(random.choice(mood_pool))

    # 4. MIX THE ACCENTS
    for accent_path in accents_to_play:
        accent_audio = AudioSegment.from_file(accent_path)
        
        # Adjust accent volume based on mood
        if mood == "sad":
            accent_audio = accent_audio - 5
        elif mood == "happy":
            accent_audio = accent_audio + 2
            
        # Random stereo panning (-0.7 left to 0.7 right)
        accent_audio = accent_audio.pan(random.uniform(-0.7, 0.7))
        
        # Insert at a random timestamp
        max_start = max(0, duration_ms - len(accent_audio))
        play_at = random.randint(0, max_start)
        
        final_mix = final_mix.overlay(accent_audio, position=play_at)

    # 5. FADE OUT AND EXPORT
    final_mix = final_mix.fade_in(2000).fade_out(3000)
    output_filename = f"alpine_mix_{mood}_{season}_{time_of_day}_{random.randint(100,999)}.mp3"
    final_mix.export(output_filename, format="mp3")
    
    print(f"Successfully generated: {output_filename}")
    return output_filename

# --- Example Trigger ---
generate_alpine_mix(mood="happy", time_of_day="day", season="summer")