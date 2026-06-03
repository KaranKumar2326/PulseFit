import json
import threading
import time

# Safely catch import errors if library install glitches
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

class NetworkClient:
    def __init__(self, server_url="ws://localhost:8765"):
        self.server_url = server_url
        self.ws = None
        self.thread = None
        self.running = False
        
        # Thread-safe telemetry shared buffers
        self.lock = threading.Lock()
        self.connected = False
        self.room_code = None
        self.role = None                # "HOST" or "GUEST"
        self.opponent_connected = False
        
        # Network event buffers
        self.selected_song = None       # Set when song selection is broadcasted
        self.opponent_calibration = {
            "shoulders": False, "hips": False, "knees": False, "ankles": False, "body_in_frame": False
        }
        self.opponent_telemetry = {
            "score": 0, "combo": 0, "multiplier": 1, "energy": 100.0,
            "knee_angle": 180.0, "back_angle": 0.0, "landmarks": None, "is_paused": False
        }
        self.room_closed = False
        self.opponent_disconnected = False
        self.error_message = None

    def connect(self):
        """Spins up the WebSocket App client inside an independent daemon worker thread."""
        if not WEBSOCKET_AVAILABLE:
            self.error_message = "websocket-client package missing"
            return False
            
        self.running = True
        self.room_closed = False
        self.opponent_disconnected = False
        self.error_message = None
        
        self.thread = threading.Thread(target=self._run_socket_loop, daemon=True)
        self.thread.start()
        return True

    def close(self):
        """Terminates socket loops and joins the thread."""
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        if self.thread:
            self.thread.join(timeout=0.5)

    def _run_socket_loop(self):
        """Asynchronous socket loop running in background."""
        while self.running:
            try:
                # Initialize WebSocket App
                self.ws = websocket.WebSocketApp(
                    self.server_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                self.ws.run_forever()
            except Exception as e:
                with self.lock:
                    self.error_message = f"Connection failed: {e}"
            
            # If socket loses connection, wait a little bit before auto-reconnecting
            if self.running:
                time.sleep(2.0)

    # --- WEBSOCKET EVENT HOOKS ---
    def _on_open(self, ws):
        with self.lock:
            self.connected = True
            self.error_message = None
        print("[NetworkClient] Successfully connected to coordinate server!")

    def _on_close(self, ws, close_status_code, close_msg):
        with self.lock:
            self.connected = False
            self.opponent_connected = False
        print(f"[NetworkClient] Socket closed: {close_status_code} - {close_msg}")

    def _on_error(self, ws, error):
        with self.lock:
            self.error_message = str(error)
        print(f"[NetworkClient] Socket error caught: {error}")

    def _on_message(self, ws, message):
        """Receives JSON payloads and updates telemetry coordinate banks."""
        try:
            data = json.loads(message)
            action = data.get("action")
            
            with self.lock:
                if action == "ROOM_CREATED":
                    self.room_code = data.get("code")
                    self.role = "HOST"
                    self.opponent_connected = False
                    
                elif action == "ROOM_JOINED":
                    self.room_code = data.get("code")
                    self.role = "GUEST"
                    self.opponent_connected = True
                    
                elif action == "PLAYER_JOINED":
                    self.opponent_connected = True
                    self.opponent_disconnected = False
                    
                elif action == "SONG_SELECTED":
                    self.selected_song = data.get("song")
                    
                elif action == "OPPONENT_CALIBRATING":
                    self.opponent_calibration = {
                        "shoulders": data.get("shoulders", False),
                        "hips": data.get("hips", False),
                        "knees": data.get("knees", False),
                        "ankles": data.get("ankles", False),
                        "body_in_frame": data.get("body_in_frame", False)
                    }
                    
                elif action == "OPPONENT_TELEMETRY":
                    self.opponent_telemetry = {
                        "score": data.get("score", 0),
                        "combo": data.get("combo", 0),
                        "multiplier": data.get("multiplier", 1),
                        "energy": data.get("energy", 100.0),
                        "knee_angle": data.get("knee_angle", 180.0),
                        "back_angle": data.get("back_angle", 0.0),
                        "landmarks": data.get("landmarks"),
                        "is_paused": data.get("is_paused", False)
                    }
                    
                elif action == "ROOM_CLOSED":
                    self.room_closed = True
                    self.room_code = None
                    
                elif action == "OPPONENT_DISCONNECTED":
                    self.opponent_connected = False
                    self.opponent_disconnected = True
                    
                elif action == "ERROR":
                    self.error_message = data.get("message")
                    
        except Exception as e:
            print(f"[NetworkClient] Failed parsing server packet: {e}")

    # --- CLIENT-TO-SERVER SEND HELPERS ---
    def _send_payload(self, payload):
        """Asynchronously sends a JSON command if connected."""
        if not self.connected or not self.ws:
            return False
        try:
            self.ws.send(json.dumps(payload))
            return True
        except Exception as e:
            print(f"[NetworkClient] Failed sending command: {e}")
            return False

    def send_create_room(self):
        """Sends a request to create a new online match room."""
        return self._send_payload({"action": "CREATE"})

    def send_join_room(self, code):
        """Requests to join an existing alphanumeric Room Code match."""
        return self._send_payload({"action": "JOIN", "code": code.upper()})

    def send_select_song(self, song_name, song_file, bpm, diff, exercise="SQUATS"):
        """Synchronizes host song selection with the guest client."""
        return self._send_payload({
            "action": "SELECT_SONG",
            "song": {"name": song_name, "file": song_file, "bpm": bpm, "diff": diff, "exercise": exercise}
        })

    def send_calibration(self, shoulders, hips, knees, ankles, body_in_frame):
        """Sends real-time diagnostic calibration checkpoints to the opponent client."""
        return self._send_payload({
            "action": "CALIBRATE",
            "shoulders": shoulders,
            "hips": hips,
            "knees": knees,
            "ankles": ankles,
            "body_in_frame": body_in_frame
        })

    def send_telemetry(self, score, combo, multiplier, energy, knee_angle, back_angle, landmarks=None, is_paused=False):
        """Streams active scoring, postural angles, and skeletal coordinates."""
        # Convert MediaPipe landmarks object to primitive list for clean JSON serializing
        serialized_landmarks = None
        if landmarks:
            try:
                serialized_landmarks = [{"x": float(lm.x), "y": float(lm.y), "z": float(lm.z)} for lm in landmarks]
            except Exception:
                pass
                
        return self._send_payload({
            "action": "TELEMETRY",
            "score": score,
            "combo": combo,
            "multiplier": multiplier,
            "energy": energy,
            "knee_angle": knee_angle,
            "back_angle": back_angle,
            "landmarks": serialized_landmarks,
            "is_paused": is_paused
        })
