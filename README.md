# ⚡ PULSEFIT ARENA — AI Cyber Rhythm Fitness

PulseFit Arena is a spectacular, production-ready AI-powered rhythm fitness desktop game. Players perform physical squats in sync with high-tempo cyberpunk electronic tracks using real-time computer vision pose tracking via a standard webcam. 

The game features immersive neon cyberpunk visuals, a custom procedural audio synthesizer, dynamic vector particle explosions, real-time biomechanical posture coaching, and cooperative/competitive multiplayer modes (both local split-screen co-op and real-time online room-code lobbies).

---

## 🎮 Game Modes: Play Locally or Compete Online

PulseFit Arena is designed to support both local play and live online competition out-of-the-box:

*   **Offline Solo Workouts**: Calibrate your camera and squat to lock in high scores, maintaining perfect form to earn combo multipliers.
*   **Local Splitscreen Cooperative Co-Op**: Play side-by-side with a friend using a **single webcam**. The game segments the webcam feed into Left (P1) and Right (P2) zones, allowing dual skeletal tracking on a single computer.
*   **Online Arena (Room Codes)**: Join or host room lobbies using a simple 4-letter Room Code. Connect with players anywhere in the world over our live Render production coordinator. Players' skeletons are streamed asynchronously at 30 Hz and drawn on screen in real-time.
*   **Mock Keyboard Mode**: No webcam? No problem! The game automatically switches to keyboard simulation so you can play at your desk:
    *   **Player 1**: Press `SPACEBAR` on the beat.
    *   **Player 2 (Splitscreen)**: Press `ENTER` on the beat.

---

## ⚡ Core Features

1.  **Dual-Threaded Decoupled Camera Pipeline**: The webcam frame grabber runs in a background thread to fully flush OpenCV buffers. The MediaPipe CV inference runs in a separate thread, feeding only the absolute newest frame to the UI. This eliminates input lag, keeping the game UI running at **60 FPS** with zero delay.
2.  **Webcam Calibration Silhouette Guide**: Overlay silhouette vectors guide players to stand back and align their entire body (shoulders, hips, knees, ankles) in frame before the countdown triggers.
3.  **In-Game Out-of-Frame Auto-Pause**: If a player steps out of the webcam frame during a song, the music and note highways freeze instantly. Gameplay resumes as soon as they step back into position.
4.  **Real-Time Biomechanical Coaching**: Uses vector math to measure knee angle depth and spine tilt. Warns players with `"STRAIGHTEN BACK"` if leaning forward, and rewards `"DEEP SQUATS"` for optimal range of motion.
5.  **Procedural Audio Synthesizer**: No copyrighted audio bloat! Synthesizes high-fidelity `.wav` techno tracks and caches mathematically precise beat timestamps in JSON files on startup.

---

## 🏗️ System Architecture

PulseFit Arena decouples heavy AI inference and network communication from the main rendering loop to achieve high-performance gameplay.

```mermaid
graph TD
    subgraph Client Application (60 FPS Pygame Loop)
        MainLoop[main.py: Game Loop]
        GameEngine[game.py: PulseFitGame]
        UI[Neon Visuals & Particle Emitter]
        AudioMixer[pygame.mixer: Soundtrack & SFX]
        RhythmEngine[rhythm_engine.py: Beats & Notes]
        
        MainLoop --> GameEngine
        GameEngine --> UI
        GameEngine --> AudioMixer
        GameEngine --> RhythmEngine
    end

    subgraph Decoupled Vision Thread
        CamThread[pose_detector.py: Webcam Grabber]
        CVThread[pose_detector.py: MediaPipe Lite Model]
        
        CamThread -->|Newest Frame| CVThread
        CVThread -->|Skeletal Coordinates & Joint Angles| GameEngine
    end

    subgraph Network Thread (Multiplayer)
        NetClient[network_client.py: Websocket Daemon]
        
        GameEngine -->|Local Telemetry 30Hz| NetClient
        NetClient -->|Opponent Skeletons| GameEngine
    end

    subgraph Remote Server (Render Cloud hosting)
        WS_Server[server.py: Async Websocket Coordinator]
        
        NetClient <==>|Bi-directional WS Relay| WS_Server
    end
```

---

## 📦 Windows Standalone Release (No Python Required)

For players who want to jump straight into the workout:
1.  Download and extract [PulseFitArena.zip](dist/PulseFitArena.zip) (approx. 115 MB).
2.  Open the folder and double-click **`PulseFitArena.exe`**.
3.  Everything is bundled inside, including Pygame CE, MediaPipe TFLite pose models, and soundtracks. It connects automatically to the live Render online server.

---

## 🛠️ Developer Setup & Launch

To run or modify the source code locally, ensure you have Python 3.8+ installed (compatible up to Python 3.14 via Pygame Community Edition).

### 1. Install Dependencies
```bash
pip install -r requirements_client.txt
```
*(This installs `pygame-ce`, `opencv-python`, `mediapipe`, and `numpy`.)*

### 2. Generate Audio Assets
Seed the folder structures and synthesize the synth workout soundtracks:
```bash
python utils.py
```

### 3. Launch the Game
```bash
python main.py
```

---

## 🌐 Running Your Own Multiplayer Server

If you want to host your own WebSocket room coordinator:
1.  Launch the server script:
    ```bash
    python server.py
    ```
2.  Configure client connections in `game.py` or compile the client to point to your custom WebSocket endpoint.

---

## 🏆 Hackathon Submission Details
*   **Client Remote Repo**: [KaranKumar2326/PulseFit](https://github.com/KaranKumar2326/PulseFit.git)
*   **Live Coordinator URL**: `wss://pulsefit-i8mb.onrender.com` / `https://pulsefit-i8mb.onrender.com` (Includes Render health-check compatibility monkeypatches).
*   **Engine**: Pygame CE 2.5.7, OpenCV, MediaPipe CPU Pose Lite Model.
