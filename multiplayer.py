import cv2
import threading
import time
import pygame

class MultiplayerManager:
    def __init__(self, p1_detector, p2_detector, camera_src=0):
        self.p1 = p1_detector
        self.p2 = p2_detector
        self.camera_src = camera_src
        
        self.running = False
        self.cap = None
        self.thread = None
        self.lock = threading.Lock()
        
        self.latest_frame = None

    def start(self):
        """Spins up a single camera feed and distributes frames to both player tracking engines."""
        self.running = True
        self.cap = cv2.VideoCapture(self.camera_src)
        
        if not self.cap.isOpened():
            print(f"[MultiplayerManager] Failed to open shared camera source {self.camera_src}. Running in MOCK keyboard mode.")
            # Trigger mock loops in detectors
            self.p1.start()
            self.p2.start()
            return

        # Configure shared camera resolution
        # We want wide resolution so when we split it, each side has decent proportions
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280) if hasattr(cv2, 'CAP_PROP_FRAME_WIDTH') else None
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720) if hasattr(cv2, 'CAP_PROP_FRAME_HEIGHT') else None
        
        # Start P1 and P2 processors in shared-feed listening mode
        self.p1.start(shared_cap=self.cap)
        self.p2.start(shared_cap=self.cap)
        
        self.thread = threading.Thread(target=self._capture_grabber_loop, daemon=True)
        self.thread.start()
        print("[MultiplayerManager] Cooperative camera thread initialized successfully!")

    def stop(self):
        """Releases shared video capture and joins background threads."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            
        self.p1.stop()
        self.p2.stop()
        
        if self.cap:
            self.cap.release()
        print("[MultiplayerManager] Cooperative camera resources released.")

    def _capture_grabber_loop(self):
        """Reads frames at high speed and pushes cropped coordinates to respective players."""
        while self.running:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                time.sleep(0.005)
                continue
                
            # Mirror the frame so users feel naturally oriented
            frame = cv2.flip(frame, 1)
            
            with self.lock:
                self.latest_frame = frame.copy()
                
            # Inject frames asynchronously into detectors (they will crop and process in their own threads!)
            self.p1.inject_shared_frame(frame)
            self.p2.inject_shared_frame(frame)
            
            # Throttle slightly to align with ~30 FPS input capture to prevent CPU overload
            time.sleep(0.02)

    def get_shared_cam_overlay(self):
        """Returns the full combined split-frame with neon center dividers for background HUD display."""
        with self.lock:
            if self.latest_frame is None:
                return None
            return self.latest_frame.copy()

    def process_keyboard_simulation(self, event):
        """
        Processes simulated physical squats from keyboard inputs:
        Player 1: Space Bar
        Player 2: Enter Key
        """
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                # Player 1 simulated squat
                self.p1.simulate_key_squat()
                print("[Simulation] P1 Squat Triggered (SPACE)")
                return "P1"
            elif event.key == pygame.K_RETURN:
                # Player 2 simulated squat
                self.p2.simulate_key_squat()
                print("[Simulation] P2 Squat Triggered (ENTER)")
                return "P2"
        return None
