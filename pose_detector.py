import cv2
import os
import threading
import time
import math
import numpy as np
import urllib.request

# Try importing modern MediaPipe, but support graceful mock fallback if it fails
try:
    import mediapipe as mp
    mp_tasks = mp.tasks
    mp_vision = mp.tasks.vision
    MEDIAPIPE_AVAILABLE = True
except (ImportError, AttributeError, ModuleNotFoundError) as e:
    print(f"[PoseDetector] MediaPipe is not available in this environment: {e}. Running in MOCK mode.")
    MEDIAPIPE_AVAILABLE = False

def download_pose_model():
    """
    Downloads the CPU-optimized, ultra-low-latency MediaPipe Pose Lite model (2.9 MB) 
    from Google Storage API and caches it locally.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(base_dir, "assets")
    os.makedirs(model_dir, exist_ok=True)
    # Use LITE model for ultra-low CPU latency in gaming loops
    model_path = os.path.join(model_dir, "pose_landmarker_lite.task")
    
    if not os.path.exists(model_path):
        print("[PoseDetector] Downloading ultra-low-latency MediaPipe Lite model...")
        url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req) as response, open(model_path, 'wb') as out_file:
                out_file.write(response.read())
            print("[PoseDetector] Lite model successfully cached to:", model_path)
        except Exception as e:
            print(f"[PoseDetector] Error downloading Lite model: {e}")
    return model_path

class PoseDetector:
    def __init__(self, player_idx=0, split_mode=False, camera_src=0):
        self.player_idx = player_idx
        self.split_mode = split_mode
        self.camera_src = camera_src
        
        # CV dimensions
        self.width = 640
        self.height = 480
        
        # Threading & Decoupled Grabber Control
        self.running = False
        self.cap = None
        self.thread = None        # Grabber thread
        self.proc_thread = None   # Inference thread
        self.lock = threading.Lock()
        
        # Thread-shared frame buffers
        self.latest_raw_frame = None
        self.frame = None          # Resized frame for main loop
        self.annotated_frame = None # Processed frame with visual skeleton
        self.landmarks = None      # Raw extracted landmarks
        self.connected = False     # Camera status
        
        # Biomechanical State Metrics
        self.knee_angle = 180.0
        self.back_angle = 0.0
        self.hip_symmetry = 0.0
        self.l_elbow_angle = 180.0
        self.r_elbow_angle = 180.0
        self.active_exercise = "SQUATS" # SQUATS, JUMPING_JACKS, CYBER_PUNCHES
        
        # In-Frame Joint Visibility Tracking (Calibration)
        self.shoulders_in_frame = False
        self.hips_in_frame = False
        self.knees_in_frame = False
        self.ankles_in_frame = False
        self.body_in_frame = False # ALL necessary joints visible
        
        # State Machine for Squat Detection
        self.squat_state = "STANDING"
        self.max_squat_depth = 180.0
        self.squat_count = 0
        self.is_squat_just_completed = False
        self.squat_feedback = "STAND BY"
        self.back_warning_count = 0
        
        # State Machine for Jumping Jacks
        self.jumping_jack_state = "CLOSED"
        self.jumping_jack_count = 0
        self.is_jumping_jack_just_completed = False
        
        # State Machine for Cyber Punches
        self.left_punch_state = "RETRACTED"
        self.right_punch_state = "RETRACTED"
        self.punch_count = 0
        self.is_punch_just_completed = False
        self.last_punch_hand = None
        
        # EMA Smoothing filter
        self.alpha_smooth = 0.35
        
        # Initialize modern PoseLandmarker
        self.pose_tracker = None
        self.use_modern_api = False
        
        if MEDIAPIPE_AVAILABLE:
            try:
                model_path = download_pose_model()
                if os.path.exists(model_path):
                    from mediapipe.tasks.python import BaseOptions
                    options = mp_vision.PoseLandmarkerOptions(
                        base_options=BaseOptions(model_asset_path=model_path),
                        running_mode=mp_vision.RunningMode.IMAGE
                    )
                    self.pose_tracker = mp_vision.PoseLandmarker.create_from_options(options)
                    self.use_modern_api = True
                    print(f"[P{self.player_idx+1}] Modern TFLite Pose Lite Landmarker initialized.")
                else:
                    self.use_modern_api = False
                    print(f"[P{self.player_idx+1}] Pose model file is missing. Falling back to MOCK.")
            except Exception as e:
                print(f"[P{self.player_idx+1}] PoseLandmarker failed to load: {e}. Falling back to MOCK.")
                self.pose_tracker = None
                self.use_modern_api = False

    def start(self, shared_cap=None):
        """Starts background grabber and processor threads."""
        self.running = True
        if shared_cap is not None:
            self.cap = shared_cap
            self.connected = True
            # For multiplayer split camera, frames are injected externally
            self.proc_thread = threading.Thread(target=self._processing_loop, daemon=True)
            self.proc_thread.start()
        else:
            # Independent camera capture loops
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()

    def stop(self):
        """Stops the threads and releases resources cleanly."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        if self.cap and not self.split_mode:
            self.cap.release()
        if self.pose_tracker and self.use_modern_api:
            try:
                self.pose_tracker.close()
            except Exception:
                pass
            
    def _capture_loop(self):
        """Webcam Grabber Thread: Reads frames at max speed to flush OS buffer."""
        self.cap = cv2.VideoCapture(self.camera_src)
        if not self.cap.isOpened():
            print(f"[P{self.player_idx+1}] Camera source {self.camera_src} failed.")
            self.connected = False
            self._mock_loop()
            return
            
        self.connected = True
        
        # Configure Camera Buffer Size to 1 to minimize delay
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
            
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width) if hasattr(cv2, 'CAP_PROP_FRAME_WIDTH') else None
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height) if hasattr(cv2, 'CAP_PROP_FRAME_HEIGHT') else None

        # Start decoupled CV processing worker thread
        self.proc_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.proc_thread.start()

        while self.running:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                time.sleep(0.005)
                continue
                
            frame = cv2.flip(frame, 1)
            # Store the raw frame as the absolute newest coordinate set
            with self.lock:
                self.latest_raw_frame = frame.copy()
            time.sleep(0.005)
            
        self.cap.release()

    def _processing_loop(self):
        """Inference Worker Thread: Reads only the latest raw frame, avoiding buffer queues."""
        while self.running:
            frame_to_process = None
            with self.lock:
                if self.latest_raw_frame is not None:
                    frame_to_process = self.latest_raw_frame.copy()
                    # Reset buffer to process once, ignoring skipped frames if CPU is busy
                    self.latest_raw_frame = None
            
            if frame_to_process is None:
                time.sleep(0.005)
                continue
                
            self._process_frame(frame_to_process)
            time.sleep(0.005)

    def inject_shared_frame(self, frame):
        """Receives a frame from the shared manager, crops it, and updates process buffer."""
        if not self.running or frame is None:
            return
            
        h, w = frame.shape[:2]
        if self.player_idx == 0:
            cropped = frame[:, :w//2]
        else:
            cropped = frame[:, w//2:]
            
        cropped = cv2.resize(cropped, (self.width, self.height))
        with self.lock:
            self.latest_raw_frame = cropped

    def _mock_loop(self):
        """Provides simulated results if no camera is available."""
        mock_img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        cv2.putText(mock_img, f"MOCK WEBCAM P{self.player_idx+1}", (150, 240), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 127), 2)
        cv2.putText(mock_img, "Press SPACE to simulate squat", (130, 280), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 240, 255), 2)
                    
        while self.running:
            # Mock mode simulates standard calibration visibility
            self.shoulders_in_frame = True
            self.hips_in_frame = True
            self.knees_in_frame = True
            self.ankles_in_frame = True
            self.body_in_frame = True
            
            with self.lock:
                self.frame = mock_img.copy()
                self.annotated_frame = mock_img.copy()
            time.sleep(0.03)

    def _process_frame(self, frame):
        """Performs MediaPipe pose estimation and checks calibration visibility."""
        with self.lock:
            self.frame = frame.copy()

        if not MEDIAPIPE_AVAILABLE or self.pose_tracker is None:
            # Set mock frame visibility parameters
            self.shoulders_in_frame = True
            self.hips_in_frame = True
            self.knees_in_frame = True
            self.ankles_in_frame = True
            self.body_in_frame = True
            with self.lock:
                self.annotated_frame = frame.copy()
            return

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        annotated = frame.copy()
        landmarks = None
        
        try:
            if self.use_modern_api:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                result = self.pose_tracker.detect(mp_image)
                
                if result.pose_landmarks:
                    landmarks = result.pose_landmarks[0]
                    self._analyze_pose_landmarks(landmarks)
                    self._draw_neon_skeleton(annotated, landmarks)
                else:
                    self.knee_angle = 180.0
                    self.back_angle = 0.0
                    self.shoulders_in_frame = False
                    self.hips_in_frame = False
                    self.knees_in_frame = False
                    self.ankles_in_frame = False
                    self.body_in_frame = False
                    self.squat_feedback = "NO USER FOUND"
        except Exception as e:
            self.squat_feedback = f"DETECTION FAULT: {e}"

        with self.lock:
            self.landmarks = landmarks
            self.annotated_frame = annotated

    def _calculate_angle(self, p1, p2, p3):
        """Calculates 3D angle at p2 (joint) formed by coordinates p1 -> p2 -> p3."""
        v1 = np.array([p1.x - p2.x, p1.y - p2.y, p1.z - p2.z])
        v2 = np.array([p3.x - p2.x, p3.y - p2.y, p3.z - p2.z])
        
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        
        if norm_v1 == 0 or norm_v2 == 0:
            return 180.0
            
        cos_angle = dot_product / (norm_v1 * norm_v2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.arccos(cos_angle)
        
        return np.degrees(angle)

    def _analyze_pose_landmarks(self, lm):
        """Core biomechanics and calibration joint visibility analysis."""
        # Key landmark references
        l_hp, r_hp = lm[23], lm[24]
        l_hip, r_hip = l_hp, r_hp
        l_knee, r_knee = lm[25], lm[26]
        l_ankle, r_ankle = lm[27], lm[28]
        l_shldr, r_shldr = lm[11], lm[12]
        l_wrst, r_wrst = lm[15], lm[16]
        l_elbw, r_elbw = lm[13], lm[14]
        
        # --- CALIBRATION VISIBILITY CHECKS ---
        self.shoulders_in_frame = (l_shldr.visibility > 0.65 and r_shldr.visibility > 0.65)
        self.hips_in_frame = (l_hp.visibility > 0.65 and r_hp.visibility > 0.65)
        self.knees_in_frame = (l_knee.visibility > 0.65 and r_knee.visibility > 0.65)
        self.ankles_in_frame = (l_ankle.visibility > 0.65 and r_ankle.visibility > 0.65)
        self.wrists_in_frame = (l_wrst.visibility > 0.65 and r_wrst.visibility > 0.65)
        self.elbows_in_frame = (l_elbw.visibility > 0.65 and r_elbw.visibility > 0.65)
        
        # Determine presence based on requirements of chosen exercise
        if self.active_exercise == "SQUATS":
            self.body_in_frame = (self.shoulders_in_frame and self.hips_in_frame and 
                                  self.knees_in_frame and self.ankles_in_frame)
        elif self.active_exercise == "JUMPING_JACKS":
            self.body_in_frame = (self.shoulders_in_frame and self.hips_in_frame and 
                                  self.knees_in_frame and self.ankles_in_frame and self.wrists_in_frame)
        elif self.active_exercise == "CYBER_PUNCHES":
            self.body_in_frame = (self.shoulders_in_frame and self.elbows_in_frame and self.wrists_in_frame)
        
        if not self.body_in_frame:
            self.squat_feedback = "KEEP BODY IN FRAME"
            return
            
        # Common biomechanic calculations
        mid_shldr_x = (l_shldr.x + r_shldr.x) / 2.0
        mid_shldr_y = (l_shldr.y + r_shldr.y) / 2.0
        mid_hip_x = (l_hp.x + r_hp.x) / 2.0
        mid_hip_y = (l_hp.y + r_hp.y) / 2.0
        
        dx = mid_shldr_x - mid_hip_x
        dy = mid_shldr_y - mid_hip_y
        
        raw_back_angle = math.degrees(math.atan2(abs(dx), abs(dy)))
        self.back_angle = (self.alpha_smooth * raw_back_angle) + ((1 - self.alpha_smooth) * self.back_angle)
        
        dy_hip = abs(l_hp.y - r_hp.y)
        self.hip_symmetry = (self.alpha_smooth * dy_hip) + ((1 - self.alpha_smooth) * self.hip_symmetry)

        # --- EXERCISE SPECIFIC LOGIC ---
        if self.active_exercise == "SQUATS":
            l_angle = self._calculate_angle(l_hip, l_knee, l_ankle)
            r_angle = self._calculate_angle(r_hip, r_knee, r_ankle)
            raw_knee_angle = (l_angle + r_angle) / 2.0
            self.knee_angle = (self.alpha_smooth * raw_knee_angle) + ((1 - self.alpha_smooth) * self.knee_angle)
            
            if self.squat_state == "STANDING":
                self.squat_feedback = "STANDING"
                if self.knee_angle < 125.0:
                    self.squat_state = "SQUATTING"
                    self.max_squat_depth = self.knee_angle
                    self.is_squat_just_completed = False
                    
            elif self.squat_state == "SQUATTING":
                self.squat_feedback = "SQUATTING"
                if self.knee_angle < self.max_squat_depth:
                    self.max_squat_depth = self.knee_angle
                    
                if self.back_angle > 28.0:
                    self.squat_feedback = "STRAIGHTEN BACK"
                    self.back_warning_count += 1
                elif self.knee_angle < 98.0:
                    self.squat_feedback = "DEEP SQUAT"
                else:
                    self.squat_feedback = "FORM GOOD"
                    
                if self.knee_angle > 155.0:
                    self.squat_state = "STANDING"
                    self.squat_count += 1
                    self.is_squat_just_completed = True

        elif self.active_exercise == "JUMPING_JACKS":
            # Wrist Y is lower than shoulder Y for raised hands (coordinate increases downward)
            hands_up = (l_wrst.y < l_shldr.y and r_wrst.y < r_shldr.y)
            
            # Ankle separation vs. shoulder separation
            sh_width = abs(l_shldr.x - r_shldr.x)
            ankle_width = abs(l_ankle.x - r_ankle.x)
            feet_ratio = ankle_width / max(0.01, sh_width)
            feet_spread = (feet_ratio > 1.35)
            
            if self.jumping_jack_state == "CLOSED":
                self.squat_feedback = "OPEN HANDS & FEET"
                if hands_up and feet_spread:
                    self.jumping_jack_state = "OPEN"
                    self.is_jumping_jack_just_completed = False
            elif self.jumping_jack_state == "OPEN":
                self.squat_feedback = "CLOSE HANDS & FEET"
                hands_down = (l_wrst.y > l_shldr.y and r_wrst.y > r_shldr.y)
                feet_closed = (feet_ratio < 1.15)
                if hands_down and feet_closed:
                    self.jumping_jack_state = "CLOSED"
                    self.jumping_jack_count += 1
                    self.is_jumping_jack_just_completed = True
                    self.squat_feedback = "PERFECT JACK"

        elif self.active_exercise == "CYBER_PUNCHES":
            l_el_angle = self._calculate_angle(l_shldr, l_elbw, l_wrst)
            r_el_angle = self._calculate_angle(r_shldr, r_elbw, r_wrst)
            
            self.l_elbow_angle = (self.alpha_smooth * l_el_angle) + ((1 - self.alpha_smooth) * self.l_elbow_angle)
            self.r_elbow_angle = (self.alpha_smooth * r_el_angle) + ((1 - self.alpha_smooth) * self.r_elbow_angle)
            
            self.is_punch_just_completed = False
            
            # Left punch check
            if self.left_punch_state == "RETRACTED":
                if self.l_elbow_angle > 155.0:
                    self.left_punch_state = "EXTENDED"
                    self.punch_count += 1
                    self.is_punch_just_completed = True
                    self.last_punch_hand = "LEFT"
                    self.squat_feedback = "LEFT PUNCH"
            elif self.left_punch_state == "EXTENDED":
                if self.l_elbow_angle < 115.0:
                    self.left_punch_state = "RETRACTED"
                    
            # Right punch check
            if self.right_punch_state == "RETRACTED":
                if self.r_elbow_angle > 155.0:
                    self.right_punch_state = "EXTENDED"
                    self.punch_count += 1
                    self.is_punch_just_completed = True
                    self.last_punch_hand = "RIGHT"
                    self.squat_feedback = "RIGHT PUNCH"
            elif self.right_punch_state == "EXTENDED":
                if self.r_elbow_angle < 115.0:
                    self.right_punch_state = "RETRACTED"

            if not self.is_punch_just_completed:
                self.squat_feedback = "GUARD UP"

    def get_and_clear_squat_event(self):
        """Returns True if a rep of the active exercise was completed since last call."""
        if self.active_exercise == "JUMPING_JACKS":
            val = self.is_jumping_jack_just_completed
            self.is_jumping_jack_just_completed = False
            return val
        elif self.active_exercise == "CYBER_PUNCHES":
            val = self.is_punch_just_completed
            self.is_punch_just_completed = False
            return val
        else:
            val = self.is_squat_just_completed
            self.is_squat_just_completed = False
            return val

    def simulate_key_squat(self, depth=95.0):
        """Simulates a rep event for mock mode (e.g. keyboard triggers)."""
        if self.active_exercise == "JUMPING_JACKS":
            self.jumping_jack_count += 1
            self.is_jumping_jack_just_completed = True
            self.squat_feedback = "PERFECT JACK"
        elif self.active_exercise == "CYBER_PUNCHES":
            self.punch_count += 1
            self.is_punch_just_completed = True
            self.last_punch_hand = "RIGHT" if self.last_punch_hand == "LEFT" else "LEFT"
            self.squat_feedback = f"{self.last_punch_hand} PUNCH"
        else:
            self.max_squat_depth = depth
            self.squat_count += 1
            self.is_squat_just_completed = True
            self.squat_feedback = "PERFECT FORM" if depth < 105.0 else "GO LOWER"

    def _draw_neon_skeleton(self, img, lm):
        """Draws a beautiful neon skeleton overlay on the webcam feed."""
        h, w, _ = img.shape
        
        def to_pix(landmark):
            return int(landmark.x * w), int(landmark.y * h)
            
        l_sh, r_sh = to_pix(lm[11]), to_pix(lm[12])
        l_hp, r_hp = to_pix(lm[23]), to_pix(lm[24])
        l_kn, r_kn = to_pix(lm[25]), to_pix(lm[26])
        l_ak, r_ak = to_pix(lm[27]), to_pix(lm[28])
        l_el, r_el = to_pix(lm[13]), to_pix(lm[14])
        l_wr, r_wr = to_pix(lm[15]), to_pix(lm[16])
        
        # Color state logic
        form_color = (30, 30, 255) if (self.active_exercise == "SQUATS" and self.back_angle > 28.0) else (0, 240, 255)
        secondary_color = (189, 0, 255)
        
        # Draw torso box
        cv2.line(img, l_sh, r_sh, form_color, 4)
        cv2.line(img, l_hp, r_hp, form_color, 4)
        cv2.line(img, l_sh, l_hp, form_color, 4)
        cv2.line(img, r_sh, r_hp, form_color, 4)
        
        # Draw Left Arm
        cv2.line(img, l_sh, l_el, secondary_color, 4)
        cv2.line(img, l_el, l_wr, secondary_color, 4)
        
        # Draw Right Arm
        cv2.line(img, r_sh, r_el, secondary_color, 4)
        cv2.line(img, r_el, r_wr, secondary_color, 4)
        
        # Draw Left Leg
        cv2.line(img, l_hp, l_kn, secondary_color, 4)
        cv2.line(img, l_kn, l_ak, secondary_color, 4)
        
        # Draw Right Leg
        cv2.line(img, r_hp, r_kn, secondary_color, 4)
        cv2.line(img, r_kn, r_ak, secondary_color, 4)
        
        # Draw joints (nodes)
        joints = [l_sh, r_sh, l_hp, r_hp, l_kn, r_kn, l_ak, r_ak, l_el, r_el, l_wr, r_wr]
        for node in joints:
            cv2.circle(img, node, 6, (255, 255, 255), -1)
            cv2.circle(img, node, 10, form_color, 2)


    def get_latest_frame(self):
        """Safely returns the latest frame and annotated frame."""
        with self.lock:
            if self.annotated_frame is not None:
                return self.frame, self.annotated_frame
            return self.frame, self.frame
