# PulseFit Arena — AI Cyber Rhythm Fitness

PulseFit Arena is an AI-powered rhythm fitness game where players perform squats in sync with high-tempo electronic beats using real-time computer vision pose tracking through a standard webcam. It features a spectacular neon cyberpunk arcade theme, a custom procedural audio synthesizer, dynamic vector particle explosions, and a split-screen single-webcam multiplayer battle arena.

---

## 🚀 Hackathon Pitch: Why PulseFit Arena Wins
1. **Audience Hook**: Gamifying physical rehab and active home workouts. Think *Beat Saber* meets *Just Dance* without expensive headsets—just a standard laptop camera.
2. **Technical Mastery**:
   - **Asynchronous CV**: MediaPipe pose detection runs in a dedicated background thread, keeping the Pygame UI running at a buttery-smooth **60 FPS** even on low-end machines.
   - **Cooperative Single-Webcam Splitscreen**: Tracks two users simultaneously on a single webcam by segmenting the frame into Left (P1) and Right (P2) zones, slashing hardware barriers.
   - **Procedural Synthesizer**: Generates high-fidelity `.wav` sound files and caches mathematically-perfect beat JSONs on startup, rendering the project 100% self-contained.
   - **Biomechanical Coaching**: Uses vector trigonometry to assess knee angle depth and spine tilt, punishing shallow squats and forward leans while rewarding perfect form with point multipliers.

---

## 🛠️ Step-by-Step Installation

### 1. Set Up Your Python Environment
PulseFit Arena is built for modern systems. If your default environment runs the highly experimental **Python 3.14**, standard pip wheels for legacy `pygame` might not exist. 

To solve this, we utilize **Pygame Community Edition (`pygame-ce`)**, which is a high-performance modern fork with active support for Python 3.14.

Run the following command to install the compatible packages:

```bash
# 1. Install compatible high-performance dependencies
pip install pygame-ce opencv-python mediapipe numpy

# Or using the standard client requirements file:
pip install -r requirements_client.txt
```

*(Note: If you encounter compiler errors on Python 3.14, installing `pygame-ce` instead of standard `pygame` will resolve it instantly.)*

### 2. Generate the Cyberpunk Synth Soundtracks
Before playing, run the seeder script to procedurally synthesize the audio files and beat markers:

```bash
python utils.py
```
This builds the following directory folders and audio assets:
- `effects/perfect.wav`, `effects/good.wav`, `effects/miss.wav` (Synth retro-arcade SFX)
- `songs/easy_synth.wav` (110 BPM - "Cyber Pulse" + JSON beat cache)
- `songs/medium_synth.wav` (125 BPM - "Retro Sprint" + JSON beat cache)
- `songs/hard_synth.wav` (140 BPM - "Neon Arena" + JSON beat cache)

---

## 🎮 How to Play

Start the application using:
```bash
python main.py
```

### Main Menu Navigation
- **Navigate Options**: Use `UP / DOWN` arrow keys (or `W / S`).
- **Select / Click Option**: Press `ENTER` or `SPACE` (or click directly with the mouse).
- **Return to Lobby / Pause**: Press `ESC`.

### Keyboard Workout Simulation (No Webcam Debug Mode)
If you don't have a webcam connected or want to test the game at your desk without standing up, the game automatically switches to **Mock Input Mode**:
- **Player 1 Squat**: Press the `SPACEBAR` key on the beat.
- **Player 2 Squat (Battle Mode)**: Press the `ENTER` key on the beat.

### CV Webcam Form Guide
For the full athletic experience, stand back from your camera until your shoulders, hips, knees, and ankles are clearly visible:
1. **Squat Depth**: Squat down until your knee angle dips below **115°** (your thighs should be nearly parallel to the ground) to register a hit. Dipping below **105°** awards a **"DEEP SQUAT"** posture bonus!
2. **Back Posture**: Keep your head up and chest out! If your upper body leans forward too far (more than 28° tilt), the AI coach will flash a red **"STRAIGHTEN BACK"** warning, capping your score multiplier.
3. **Timing**: Reach the lowest point of your squat *exactly* when the descending glowing notes overlap the **Neon Strike Line** at the bottom of the screen.

---

## 📈 Post-Game Telemetry Analytics
Once the song ends, the game displays your **Workout Session Results**:
- **System Grade**: S (Flawless), A, B, C, or F based on note accuracy.
- **Calorie Estimation**: A standard MET-based formula calculates real-time caloric burn based on movement intensity and duration.
- **Biomechanical Line Plot**: An interactive neon coordinate graph plots your exact knee angle depth history across every single squat, helping you visualize your physical stamina and form consistency!
- **AI Coach Review**: The AI compiles your forward tilt ratios and depth markers to offer custom athletic coaching advice.
