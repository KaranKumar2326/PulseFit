import os
import time
import math
import pygame
import random
import cv2

# Project Imports
from utils import (
    BLACK, CYAN, PURPLE, PINK, WHITE, GRAY, DARK_GRAY, GREEN, YELLOW, RED,
    draw_neon_line, draw_neon_rect, draw_neon_circle, draw_neon_text,
    ParticleSystem, ease_out_quad
)
from pose_detector import PoseDetector
from rhythm_engine import RhythmEngine
from scoring import ScoringSystem
from ai_coach import AICoach
from analytics import AnalyticsManager
from multiplayer import MultiplayerManager
from network_client import NetworkClient

class PulseFitGame:
    def __init__(self, screen):
        self.screen = screen
        self.width, self.height = screen.get_size()
        
        # State Machine States: MENU, SONG_SELECT, CALIBRATION, COUNTDOWN, GAMEPLAY, RESULTS, LEADERBOARD,
        # plus Online states: ONLINE_LOBBY, ONLINE_WAITING, ONLINE_CALIBRATION, ONLINE_COUNTDOWN, ONLINE_GAMEPLAY
        self.state = "MENU"
        self.clock = pygame.time.Clock()
        self.fps = 60
        self.running = True
        
        # Managers
        self.analytics = AnalyticsManager()
        self.particles = ParticleSystem()
        
        # UI & Animation Telemetry
        button_actions = [
            {"label": "SOLO WORKOUT", "action": "SOLO"},
            {"label": "LOCAL Splitscreen BATTLE", "action": "BATTLE"},
            {"label": "ONLINE ARENA (ROOM CODES)", "action": "ONLINE"},
            {"label": "ARCADE LEADERBOARD", "action": "LEADERBOARD"},
            {"label": "EXIT SYSTEM", "action": "EXIT"}
        ]
        self.menu_buttons = [{"label": b["label"], "action": b["action"], "rect": pygame.Rect(0, 0, 0, 0)} for b in button_actions]
        self.selected_button_idx = 0
        self.grid_pulse_scale = 1.0
        self.grid_scroll_offset = 0.0
        self.screen_shake_time = 0.0
        
        # Calibration & Countdown states
        self.calibration_stabilize_time = 0.0  
        self.countdown_timer = 0.0              
        self.last_countdown_sec = 4             
        self.is_paused_out_of_frame = False     
        self.out_of_frame_stabilize = 0.0       
        
        # Online Multiplayer states
        self.net_client = None
        self.typed_room_code = ""               # Alphanumeric room code input
        self.net_error = None                   # Connection/Room error feedback
        self.network_send_timer = 0.0           # Throttles socket transmissions to 30 Hz
        
        # Font initialization
        self.init_fonts()
        
        # Game modes
        self.game_mode = "SOLO"  # SOLO, MULTIPLAYER, ONLINE
        self.difficulty = "Medium"
        self.player_name = "Player 1"
        self.player2_name = "Player 2"
        
        # Selected song metadata
        self.songs_list = [
            {"name": "Cyber Pulse (Easy)", "file": "songs/easy_synth.wav", "bpm": 110, "diff": "Easy"},
            {"name": "Retro Sprint (Medium)", "file": "songs/medium_synth.wav", "bpm": 125, "diff": "Medium"},
            {"name": "Neon Arena (Hard)", "file": "songs/hard_synth.wav", "bpm": 140, "diff": "Hard"}
        ]
        self.selected_song_idx = 0
        
        # Selected exercise metadata
        self.exercises_list = [
            {"name": "SQUATS", "desc": "Triggers on deep knee bend. Focus on a straight back."},
            {"name": "JUMPING JACKS", "desc": "Hands above head, feet open wide. High cardio tempo."},
            {"name": "CYBER PUNCHES", "desc": "Alternate rapid left and right arm punches. Fast reflex test."}
        ]
        self.selected_exercise_idx = 0
        self.active_exercise = "SQUATS"
        
        # Game State Objects
        self.p1_detector = None
        self.p2_detector = None
        self.multiplayer_mgr = None
        self.rhythm_engine_p1 = None
        self.rhythm_engine_p2 = None
        self.score_p1 = None
        self.score_p2 = None
        self.coach_p1 = None
        self.coach_p2 = None
        
        # Beat tracking variables
        self.song_start_time = 0.0
        self.song_duration = 0.0
        self.current_song_time = 0.0
        self.playback_offset_sec = 0.15
        
        # Telemetry logs for results screen
        self.depth_history_p1 = []
        self.depth_history_p2 = []
        self.floating_popups = []
        
        # Initialize SFX
        self.init_sfx()
        
        from utils import generate_sfx
        generate_sfx()

    def init_fonts(self):
        """Initializes game fonts, falling back gracefully to system fonts."""
        pygame.font.init()
        font_choices = ["Consolas", "Courier New", "Lucida Console", "Segoe UI Semibold"]
        self.font_title = None
        self.font_header = None
        self.font_hud = None
        self.font_small = None
        
        for name in font_choices:
            try:
                self.font_title = pygame.font.SysFont(name, 56, bold=True)
                self.font_header = pygame.font.SysFont(name, 32, bold=True)
                self.font_hud = pygame.font.SysFont(name, 22, bold=True)
                self.font_small = pygame.font.SysFont(name, 14)
                break
            except Exception:
                continue
                
        if not self.font_title:
            self.font_title = pygame.font.Font(None, 56)
            self.font_header = pygame.font.Font(None, 32)
            self.font_hud = pygame.font.Font(None, 22)
            self.font_small = pygame.font.Font(None, 14)

    def init_sfx(self):
        """Pre-loads generated SFX files safely."""
        self.sfx_perfect = None
        self.sfx_good = None
        self.sfx_miss = None
        self.sfx_click = None
        self.sfx_win = None
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        try:
            pygame.mixer.init()
            self.sfx_perfect = pygame.mixer.Sound(os.path.join(base_dir, 'effects', 'perfect.wav'))
            self.sfx_good = pygame.mixer.Sound(os.path.join(base_dir, 'effects', 'good.wav'))
            self.sfx_miss = pygame.mixer.Sound(os.path.join(base_dir, 'effects', 'miss.wav'))
            self.sfx_click = pygame.mixer.Sound(os.path.join(base_dir, 'effects', 'click.wav'))
            self.sfx_win = pygame.mixer.Sound(os.path.join(base_dir, 'effects', 'win.wav'))
        except Exception as e:
            print(f"[Game init] Sound mixer error: {e}. Running without SFX.")

    def play_sound(self, sound):
        """Safely triggers sound playback."""
        if sound:
            try:
                sound.play()
            except Exception:
                pass

    def start_song(self, song_path, bpm):
        """Initializes trackers and prepares song loading (paused until calibration completes)."""
        print(f"[Gameplay] Initializing song {song_path} at {bpm} BPM...")
        self.depth_history_p1 = []
        self.depth_history_p2 = []
        self.floating_popups.clear()
        
        self.calibration_stabilize_time = 0.0
        self.countdown_timer = 0.0
        self.last_countdown_sec = 4
        self.is_paused_out_of_frame = False
        self.out_of_frame_stabilize = 0.0
        self.current_song_time = 0.0
        
        # Set up Player 1 systems
        self.p1_detector = PoseDetector(player_idx=0, camera_src=0)
        self.p1_detector.active_exercise = self.active_exercise
        self.rhythm_engine_p1 = RhythmEngine(self.difficulty)
        self.rhythm_engine_p1.load_song(song_path, bpm)
        self.score_p1 = ScoringSystem()
        self.coach_p1 = AICoach(self.active_exercise)
        
        if self.game_mode == "ONLINE":
            # For online mode, Player 2 is remote, so we only launch P1's physical camera
            self.p1_detector.start()
            # Opponent scores are updated asynchronously via network telemetry relayer
            self.score_p2 = ScoringSystem()
            self.coach_p2 = AICoach(self.active_exercise)
            
        elif self.game_mode == "MULTIPLAYER":
            # Split-screen cooperative mode
            self.p2_detector = PoseDetector(player_idx=1, camera_src=0)
            self.p2_detector.active_exercise = self.active_exercise
            self.rhythm_engine_p2 = RhythmEngine(self.difficulty)
            self.rhythm_engine_p2.load_song(song_path, bpm)
            self.score_p2 = ScoringSystem()
            self.coach_p2 = AICoach(self.active_exercise)
            
            self.multiplayer_mgr = MultiplayerManager(self.p1_detector, self.p2_detector, camera_src=0)
            self.multiplayer_mgr.start()
        else:
            # Solo play
            self.p1_detector.start()
            
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.load(song_path)
                pygame.mixer.music.play()
                pygame.mixer.music.pause() # hold music until countdown Go!
                self.song_duration = pygame.mixer.Sound(song_path).get_length()
            except Exception as e:
                print(f"[Rhythm Playback] Load error: {e}")
                self.song_duration = 60.0
        else:
            self.song_duration = 60.0

    def cleanup_gameplay(self):
        """Safely stops threads, network clients, and audio streams."""
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            
        if self.game_mode == "MULTIPLAYER" and self.multiplayer_mgr:
            self.multiplayer_mgr.stop()
            self.multiplayer_mgr = None
        else:
            if self.p1_detector:
                self.p1_detector.stop()
                
        if self.net_client:
            self.net_client.close()
            self.net_client = None
            
        self.p1_detector = None
        self.p2_detector = None

    def trigger_popup(self, text, x, y, color):
        """Creates an animated neon text rating float popup."""
        self.floating_popups.append({
            "text": text,
            "x": x,
            "y": y,
            "color": color,
            "timer": 0.65,
            "scale": 1.4
        })

    def handle_events(self):
        """Processes keystrokes, clicks, and state transitions."""
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.running = False
                return
                
            # Keyboard Simulation Hook for testing poses (Spacebar for P1, Enter for P2)
            if self.state in ["CALIBRATION", "ONLINE_CALIBRATION", "GAMEPLAY", "ONLINE_GAMEPLAY"]:
                if self.game_mode == "MULTIPLAYER" and self.multiplayer_mgr:
                    self.multiplayer_mgr.process_keyboard_simulation(event)
                else:
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                        if self.p1_detector:
                            self.p1_detector.simulate_key_squat()
                            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state in ["CALIBRATION", "COUNTDOWN", "GAMEPLAY", "ONLINE_LOBBY", "ONLINE_WAITING", "ONLINE_CALIBRATION", "ONLINE_COUNTDOWN", "ONLINE_GAMEPLAY"]:
                        self.cleanup_gameplay()
                        self.state = "MENU"
                        self.play_sound(self.sfx_click)
                    elif self.state in ["SONG_SELECT", "EXERCISE_SELECT", "RESULTS", "LEADERBOARD"]:
                        self.state = "MENU"
                        self.play_sound(self.sfx_click)
                        
                # Menu navigation controls
                elif self.state == "MENU":
                    if event.key in [pygame.K_UP, pygame.K_w]:
                        self.selected_button_idx = (self.selected_button_idx - 1) % len(self.menu_buttons)
                        self.play_sound(self.sfx_click)
                    elif event.key in [pygame.K_DOWN, pygame.K_s]:
                        self.selected_button_idx = (self.selected_button_idx + 1) % len(self.menu_buttons)
                        self.play_sound(self.sfx_click)
                    elif event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                        self.play_sound(self.sfx_click)
                        self._trigger_menu_action()
                        
                elif self.state == "EXERCISE_SELECT":
                    if event.key in [pygame.K_UP, pygame.K_w]:
                        self.selected_exercise_idx = (self.selected_exercise_idx - 1) % len(self.exercises_list)
                        self.play_sound(self.sfx_click)
                    elif event.key in [pygame.K_DOWN, pygame.K_s]:
                        self.selected_exercise_idx = (self.selected_exercise_idx + 1) % len(self.exercises_list)
                        self.play_sound(self.sfx_click)
                    elif event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                        self.play_sound(self.sfx_click)
                        selected = self.exercises_list[self.selected_exercise_idx]["name"]
                        self.active_exercise = selected.replace(" ", "_")
                        self.state = "SONG_SELECT"
                        
                elif self.state == "SONG_SELECT":
                    if event.key in [pygame.K_UP, pygame.K_w]:
                        self.selected_song_idx = (self.selected_song_idx - 1) % len(self.songs_list)
                        self.play_sound(self.sfx_click)
                    elif event.key in [pygame.K_DOWN, pygame.K_s]:
                        self.selected_song_idx = (self.selected_song_idx + 1) % len(self.songs_list)
                        self.play_sound(self.sfx_click)
                    elif event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                        self.play_sound(self.sfx_click)
                        song = self.songs_list[self.selected_song_idx]
                        self.difficulty = song["diff"]
                        
                        if self.game_mode == "ONLINE":
                            # Host selects the song: send it over WebSockets
                            if self.net_client and self.net_client.role == "HOST":
                                self.net_client.send_select_song(
                                    song["name"], song["file"], song["bpm"], song["diff"], self.active_exercise
                                )
                                self.state = "ONLINE_CALIBRATION"
                                self.start_song(song["file"], song["bpm"])
                        else:
                            # Local solo / split screen
                            self.state = "CALIBRATION"
                            self.start_song(song["file"], song["bpm"])
                            
                elif self.state == "ONLINE_LOBBY":
                    # Alphanumeric room code typing handler
                    if event.key == pygame.K_BACKSPACE:
                        self.typed_room_code = self.typed_room_code[:-1]
                        self.play_sound(self.sfx_click)
                    elif event.key in [pygame.K_RETURN, pygame.K_KP_ENTER]:
                        if len(self.typed_room_code) == 4 and self.net_client:
                            self.net_client.send_join_room(self.typed_room_code)
                            self.play_sound(self.sfx_click)
                    elif event.key == pygame.K_c:
                        # Press 'C' key to Create a Room
                        if self.net_client:
                            self.net_client.send_create_room()
                            self.play_sound(self.sfx_click)
                    else:
                        # Standard character typing
                        char = event.unicode.upper()
                        if char.isalnum() and len(self.typed_room_code) < 4:
                            self.typed_room_code += char
                            self.play_sound(self.sfx_click)
                            
                elif self.state == "RESULTS":
                    if event.key in [pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE]:
                        self.play_sound(self.sfx_click)
                        self.state = "MENU"
                        
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = pygame.mouse.get_pos()
                if self.state == "MENU":
                    for idx, btn in enumerate(self.menu_buttons):
                        if btn["rect"].collidepoint(mouse_pos):
                            self.selected_button_idx = idx
                            self.play_sound(self.sfx_click)
                            self._trigger_menu_action()
                            break

    def _trigger_menu_action(self):
        """Action handler mapping selected menu buttons to game states."""
        action = self.menu_buttons[self.selected_button_idx]["action"]
        if action == "SOLO":
            self.game_mode = "SOLO"
            self.state = "EXERCISE_SELECT"
        elif action == "BATTLE":
            self.game_mode = "MULTIPLAYER"
            self.state = "EXERCISE_SELECT"
        elif action == "ONLINE":
            # Spin up online multiplayer client socket
            self.game_mode = "ONLINE"
            self.state = "ONLINE_LOBBY"
            self.typed_room_code = ""
            self.net_error = None
            
            # Start asynchronous background client!
            # (Checks ws://localhost:8765. In production, this can point to a remote server)
            self.net_client = NetworkClient(server_url="wss://pulsefit-i8mb.onrender.com")
            if not self.net_client.connect():
                self.net_error = "WEBSOCKET LIBRARY ERROR"
                self.net_client = None
        elif action == "LEADERBOARD":
            self.state = "LEADERBOARD"
        elif action == "EXIT":
            self.running = False

    def _save_and_transition_results(self):
        """Saves player stats to analytics and switches the game state to RESULTS."""
        if self.score_p1:
            score = self.score_p1.score
            accuracy = self.score_p1.get_accuracy()
            grade = self.score_p1.get_performance_grade()
            calories = self.score_p1.get_calories_burned_estimate(self.song_duration)
            
            coach_data = self.coach_p1.get_final_analytics() if self.coach_p1 else {"overall_score": 100}
            posture_score = coach_data["overall_score"]
            
            song_name = self.songs_list[self.selected_song_idx]["name"]
            
            self.analytics.save_run(
                player_name=self.player_name,
                song_name=song_name,
                difficulty=self.difficulty,
                score=score,
                accuracy=accuracy,
                grade=grade,
                calories=calories,
                posture_score=posture_score
            )
            
        self.cleanup_gameplay()
        self.state = "RESULTS"

    def update(self, dt):
        """Core math updates: transitions, note feeds, scoring triggers."""
        if self.screen_shake_time > 0:
            self.screen_shake_time -= dt
            
        self.grid_scroll_offset = (self.grid_scroll_offset + dt * 40) % 80
        self.grid_pulse_scale = max(1.0, self.grid_pulse_scale - dt * 2.0)
        
        # State Machine routers
        if self.state == "CALIBRATION":
            self._update_calibration(dt)
        elif self.state == "COUNTDOWN":
            self._update_countdown(dt)
        elif self.state == "GAMEPLAY":
            self._update_gameplay_loop(dt)
        elif self.state == "ONLINE_LOBBY":
            self._update_online_lobby(dt)
        elif self.state == "ONLINE_WAITING":
            self._update_online_waiting(dt)
        elif self.state == "ONLINE_CALIBRATION":
            self._update_online_calibration(dt)
        elif self.state == "ONLINE_COUNTDOWN":
            self._update_online_countdown(dt)
        elif self.state == "ONLINE_GAMEPLAY":
            self._update_online_gameplay(dt)
            
        # Update float popups
        for popup in self.floating_popups[:]:
            popup["timer"] -= dt
            popup["y"] -= dt * 65
            popup["scale"] = max(1.0, popup["scale"] - dt * 1.5)
            if popup["timer"] <= 0:
                self.floating_popups.remove(popup)
                
        self.particles.update(dt)

    def _update_calibration(self, dt):
        """Monitors skeletal joint presence and locks calibration on 1.5s hold."""
        if self.game_mode == "MULTIPLAYER":
            all_in_frame = (self.p1_detector and self.p1_detector.body_in_frame and 
                            self.p2_detector and self.p2_detector.body_in_frame)
        else:
            all_in_frame = (self.p1_detector and self.p1_detector.body_in_frame)
            
        if all_in_frame:
            self.calibration_stabilize_time += dt
            if self.calibration_stabilize_time >= 1.5:
                self.state = "COUNTDOWN"
                self.countdown_timer = 3.0
                self.last_countdown_sec = 4
                self.play_sound(self.sfx_click)
        else:
            self.calibration_stabilize_time = 0.0

    def _update_countdown(self, dt):
        """Updates the 3-second visual countdown, triggering beep audio SFX."""
        self.countdown_timer -= dt
        
        current_sec = math.ceil(self.countdown_timer)
        if current_sec < self.last_countdown_sec and current_sec > 0:
            self.last_countdown_sec = current_sec
            self.play_sound(self.sfx_click)
            self.grid_pulse_scale = 1.25
            
        if self.countdown_timer <= 0:
            self.state = "GAMEPLAY"
            self.song_start_time = time.time()
            if pygame.mixer.get_init():
                pygame.mixer.music.unpause()
            self.play_sound(self.sfx_perfect)

    def _update_gameplay_loop(self, dt):
        """Updates camera states, note scrolling, and checks real-time out-of-frame pausing."""
        if self.p1_detector is None:
            return
            
        if self.game_mode == "MULTIPLAYER":
            out_of_frame = (not self.p1_detector.body_in_frame or not self.p2_detector.body_in_frame)
        else:
            out_of_frame = (not self.p1_detector.body_in_frame)
            
        if out_of_frame:
            if not self.is_paused_out_of_frame:
                self.is_paused_out_of_frame = True
                self.out_of_frame_stabilize = 0.0
                if pygame.mixer.get_init():
                    pygame.mixer.music.pause()
            return
        else:
            if self.is_paused_out_of_frame:
                self.out_of_frame_stabilize += dt
                if self.out_of_frame_stabilize >= 0.6:
                    self.is_paused_out_of_frame = False
                    if pygame.mixer.get_init():
                        pygame.mixer.music.unpause()
                    self.out_of_frame_stabilize = 0.0
                return

        # Normal loop
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            self.current_song_time = pygame.mixer.music.get_pos() / 1000.0 - self.playback_offset_sec
        else:
            self.current_song_time += dt
            
        if self.current_song_time >= self.song_duration:
            self.play_sound(self.sfx_win)
            self._save_and_transition_results()
            return
            
        # P1 Highway notes
        strike_y = self.height - 120
        self.rhythm_engine_p1.update(self.current_song_time, strike_y, self.height)
        
        for note in self.rhythm_engine_p1.notes:
            if note.missed and not note.hit:
                note.hit = True
                self.score_p1.register_miss()
                self.play_sound(self.sfx_miss)
                self.screen_shake_time = 0.2
                self.trigger_popup("MISS", self.width - 250 if self.game_mode == "SOLO" else self.width // 4 + 80, strike_y - 20, PINK)
                
        if self.p1_detector.get_and_clear_squat_event():
            if self.active_exercise == "SQUATS":
                depth = self.p1_detector.max_squat_depth
                back = self.p1_detector.back_angle
                self.depth_history_p1.append(depth)
                fb_msg, form_score = self.coach_p1.evaluate_squat(depth, back)
            elif self.active_exercise == "JUMPING_JACKS":
                self.depth_history_p1.append(100.0)
                fb_msg, form_score = self.coach_p1.evaluate_jumping_jack()
            else:
                self.depth_history_p1.append(100.0)
                fb_msg, form_score = self.coach_p1.evaluate_punch()
            rating, points, time_diff = self.rhythm_engine_p1.check_hit(self.current_song_time)
            
            if rating:
                self.score_p1.register_hit(rating, form_score)
                if rating == "PERFECT":
                    self.play_sound(self.sfx_perfect)
                    self.particles.spawn(self.width - 200 if self.game_mode == "SOLO" else self.width // 4, strike_y, CYAN, count=20)
                    self.grid_pulse_scale = 1.35
                    self.trigger_popup(f"PERFECT! +{points}", self.width - 250 if self.game_mode == "SOLO" else self.width // 4 + 80, strike_y - 20, CYAN)
                else:
                    self.play_sound(self.sfx_good)
                    self.particles.spawn(self.width - 200 if self.game_mode == "SOLO" else self.width // 4, strike_y, PURPLE, count=12)
                    self.trigger_popup(f"GOOD! +{points}", self.width - 250 if self.game_mode == "SOLO" else self.width // 4 + 80, strike_y - 20, PURPLE)
            else:
                self.trigger_popup("OFF BEAT", self.width - 250 if self.game_mode == "SOLO" else self.width // 4 + 80, strike_y - 20, YELLOW)

        # P2 splitscreen updates
        if self.game_mode == "MULTIPLAYER" and self.p2_detector:
            self.rhythm_engine_p2.update(self.current_song_time, strike_y, self.height)
            
            for note in self.rhythm_engine_p2.notes:
                if note.missed and not note.hit:
                    note.hit = True
                    self.score_p2.register_miss()
                    self.play_sound(self.sfx_miss)
                    self.screen_shake_time = 0.2
                    self.trigger_popup("MISS", (self.width // 4) * 3 + 80, strike_y - 20, PINK)
                    
            if self.p2_detector.get_and_clear_squat_event():
                if self.active_exercise == "SQUATS":
                    depth = self.p2_detector.max_squat_depth
                    back = self.p2_detector.back_angle
                    self.depth_history_p2.append(depth)
                    fb_msg, form_score = self.coach_p2.evaluate_squat(depth, back)
                elif self.active_exercise == "JUMPING_JACKS":
                    self.depth_history_p2.append(100.0)
                    fb_msg, form_score = self.coach_p2.evaluate_jumping_jack()
                else:
                    self.depth_history_p2.append(100.0)
                    fb_msg, form_score = self.coach_p2.evaluate_punch()
                rating, points, time_diff = self.rhythm_engine_p2.check_hit(self.current_song_time)
                
                if rating:
                    self.score_p2.register_hit(rating, form_score)
                    if rating == "PERFECT":
                        self.play_sound(self.sfx_perfect)
                        self.particles.spawn((self.width // 4) * 3, strike_y, CYAN, count=20)
                        self.grid_pulse_scale = 1.35
                        self.trigger_popup(f"PERFECT! +{points}", (self.width // 4) * 3 + 80, strike_y - 20, CYAN)
                    else:
                        self.play_sound(self.sfx_good)
                        self.particles.spawn((self.width // 4) * 3, strike_y, PURPLE, count=12)
                        self.trigger_popup(f"GOOD! +{points}", (self.width // 4) * 3 + 80, strike_y - 20, PURPLE)
                else:
                    self.trigger_popup("OFF BEAT", (self.width // 4) * 3 + 80, strike_y - 20, YELLOW)

    # --- ONLINE MULTIPLAYER STATE CONTROLLERS ---
    def _update_online_lobby(self, dt):
        """Monitors network client connection hooks and navigates lobbies."""
        if not self.net_client:
            return
            
        with self.net_client.lock:
            # Sync server errors
            if self.net_client.error_message:
                self.net_error = self.net_client.error_message
                self.net_client.error_message = None
                
            # If successfully connected to a Room Code
            if self.net_client.room_code:
                code = self.net_client.room_code
                role = self.net_client.role
                
                if role == "HOST":
                    self.state = "ONLINE_WAITING"
                else: # GUEST
                    # Guest joined! Wait for the host to select track
                    self.state = "ONLINE_WAITING"

    def _update_online_waiting(self, dt):
        """Monitors room joins and song selections in network lobby."""
        if not self.net_client:
            return
            
        with self.net_client.lock:
            role = self.net_client.role
            
            # Host: If opponent has successfully connected, transition to Exercise Selection!
            if role == "HOST" and self.net_client.opponent_connected:
                self.state = "EXERCISE_SELECT"
                self.play_sound(self.sfx_perfect)
                
            # Guest: Wait for Host's song selection package, then auto-load track and exercise
            if role == "GUEST" and self.net_client.selected_song:
                song = self.net_client.selected_song
                self.difficulty = song["diff"]
                self.selected_song_idx = next(
                    (i for i, s in enumerate(self.songs_list) if s["file"] == song["file"]), 0
                )
                self.active_exercise = song.get("exercise", "SQUATS")
                # Clear selected buffer
                self.net_client.selected_song = None
                
                self.state = "ONLINE_CALIBRATION"
                self.start_song(song["file"], song["bpm"])

    def _update_online_calibration(self, dt):
        """Synchronizes calibration checklists between both remote clients."""
        if not self.net_client or not self.p1_detector:
            return
            
        # 1. Periodically send local calibration checklist to opponent (every ~33ms)
        self.network_send_timer += dt
        if self.network_send_timer >= 0.033:
            self.network_send_timer = 0.0
            self.net_client.send_calibration(
                self.p1_detector.shoulders_in_frame,
                self.p1_detector.hips_in_frame,
                self.p1_detector.knees_in_frame,
                self.p1_detector.ankles_in_frame,
                self.p1_detector.body_in_frame
            )
            
        # 2. Read opponent's calibration status from shared network client
        with self.net_client.lock:
            if self.net_client.room_closed or self.net_client.opponent_disconnected:
                # Opponent left lobby: disconnect cleanly
                self.cleanup_gameplay()
                self.state = "ONLINE_LOBBY"
                self.net_error = "OPPONENT DISCONNECTED"
                return
                
            opp_cal = self.net_client.opponent_calibration
            
        # 3. Verify both are aligned concurrently
        all_ready = (self.p1_detector.body_in_frame and opp_cal.get("body_in_frame", False))
        
        if all_ready:
            self.calibration_stabilize_time += dt
            if self.calibration_stabilize_time >= 1.5:
                # Both fully aligned: trigger online countdown!
                self.state = "ONLINE_COUNTDOWN"
                self.countdown_timer = 3.0
                self.last_countdown_sec = 4
                self.play_sound(self.sfx_click)
        else:
            self.calibration_stabilize_time = 0.0

    def _update_online_countdown(self, dt):
        """Pulsing count visual timer before online match starts."""
        self.countdown_timer -= dt
        
        current_sec = math.ceil(self.countdown_timer)
        if current_sec < self.last_countdown_sec and current_sec > 0:
            self.last_countdown_sec = current_sec
            self.play_sound(self.sfx_click)
            self.grid_pulse_scale = 1.25
            
        if self.countdown_timer <= 0:
            self.state = "ONLINE_GAMEPLAY"
            self.song_start_time = time.time()
            if pygame.mixer.get_init():
                pygame.mixer.music.unpause() # Unleash beat track!
            self.play_sound(self.sfx_perfect)

    def _update_online_gameplay(self, dt):
        """Streams client score telemetry and parses opponent's skeletal coordinates live."""
        if not self.net_client or not self.p1_detector:
            return
            
        # 1. Check if opponent closed room or disconnected
        with self.net_client.lock:
            if self.net_client.room_closed or self.net_client.opponent_disconnected:
                self.cleanup_gameplay()
                self.state = "ONLINE_LOBBY"
                self.net_error = "CONNECTION LOST"
                return
                
            # Get opponent's out-of-frame pause state
            opp_telemetry = self.net_client.opponent_telemetry
            opp_paused = opp_telemetry.get("is_paused", False)
            
        # 2. Local Pause triggers (if local player steps out of frame)
        local_paused = not self.p1_detector.body_in_frame
        
        # If EITHER player is out of frame, the match pauses to preserve multiplayer fairness!
        any_paused = (local_paused or opp_paused)
        
        if any_paused:
            if not self.is_paused_out_of_frame:
                self.is_paused_out_of_frame = True
                self.out_of_frame_stabilize = 0.0
                if pygame.mixer.get_init():
                    pygame.mixer.music.pause()
            
            # Send pause notification telemetry to server immediately
            self.net_client.send_telemetry(
                self.score_p1.score, self.score_p1.combo, self.score_p1.multiplier, self.score_p1.energy,
                self.p1_detector.knee_angle, self.p1_detector.back_angle, landmarks=None, is_paused=True
            )
            return # Freeze notes and time
        else:
            if self.is_paused_out_of_frame:
                self.out_of_frame_stabilize += dt
                if self.out_of_frame_stabilize >= 0.6:
                    self.is_paused_out_of_frame = False
                    if pygame.mixer.get_init():
                        pygame.mixer.music.unpause()
                    self.out_of_frame_stabilize = 0.0
                return

        # 3. Normal playback clock tick
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            self.current_song_time = pygame.mixer.music.get_pos() / 1000.0 - self.playback_offset_sec
        else:
            self.current_song_time += dt
            
        if self.current_song_time >= self.song_duration:
            self.play_sound(self.sfx_win)
            self._save_and_transition_results()
            return
            
        # 4. Update local rhythm notes scrolling
        strike_y = self.height - 120
        self.rhythm_engine_p1.update(self.current_song_time, strike_y, self.height)
        
        # Check missed notes local
        for note in self.rhythm_engine_p1.notes:
            if note.missed and not note.hit:
                note.hit = True
                self.score_p1.register_miss()
                self.play_sound(self.sfx_miss)
                self.screen_shake_time = 0.2
                self.trigger_popup("MISS", self.width // 4 + 80, strike_y - 20, PINK)
                
        # Squat triggers P1
        if self.p1_detector.get_and_clear_squat_event():
            if self.active_exercise == "SQUATS":
                depth = self.p1_detector.max_squat_depth
                back = self.p1_detector.back_angle
                self.depth_history_p1.append(depth)
                fb_msg, form_score = self.coach_p1.evaluate_squat(depth, back)
            elif self.active_exercise == "JUMPING_JACKS":
                self.depth_history_p1.append(100.0)
                fb_msg, form_score = self.coach_p1.evaluate_jumping_jack()
            else:
                self.depth_history_p1.append(100.0)
                fb_msg, form_score = self.coach_p1.evaluate_punch()
            rating, points, time_diff = self.rhythm_engine_p1.check_hit(self.current_song_time)
            
            if rating:
                self.score_p1.register_hit(rating, form_score)
                if rating == "PERFECT":
                    self.play_sound(self.sfx_perfect)
                    self.particles.spawn(self.width // 4, strike_y, CYAN, count=20)
                    self.grid_pulse_scale = 1.35
                    self.trigger_popup(f"PERFECT! +{points}", self.width // 4 + 80, strike_y - 20, CYAN)
                else:
                    self.play_sound(self.sfx_good)
                    self.particles.spawn(self.width // 4, strike_y, PURPLE, count=12)
                    self.trigger_popup(f"GOOD! +{points}", self.width // 4 + 80, strike_y - 20, PURPLE)
            else:
                self.trigger_popup("OFF BEAT", self.width // 4 + 80, strike_y - 20, YELLOW)

        # 5. Load network opponent's score and combo states directly for the splitscreen HUD
        with self.net_client.lock:
            opp_t = self.net_client.opponent_telemetry
            
        self.score_p2.score = opp_t.get("score", 0)
        self.score_p2.combo = opp_t.get("combo", 0)
        self.score_p2.multiplier = opp_t.get("multiplier", 1)
        self.score_p2.energy = opp_t.get("energy", 100.0)
        self.p2_detector.knee_angle = opp_t.get("knee_angle", 180.0)
        self.p2_detector.back_angle = opp_t.get("back_angle", 0.0)
        
        # 6. Stream P1 telemetry to opponent (throttled to 30 FPS to avoid clogging)
        self.network_send_timer += dt
        if self.network_send_timer >= 0.033:
            self.network_send_timer = 0.0
            self.net_client.send_telemetry(
                self.score_p1.score, self.score_p1.combo, self.score_p1.multiplier, self.score_p1.energy,
                self.p1_detector.knee_angle, self.p1_detector.back_angle,
                landmarks=self.p1_detector.landmarks, is_paused=False
            )

    # --- MAIN STATE SWITCH ROUTER DRAW LOOPS ---
    def draw(self):
        """Aggregates graphic layers and applies retro screen shakes."""
        canvas = pygame.Surface((self.width, self.height))
        canvas.fill(BLACK)
        
        self._draw_ambient_neon_grid(canvas)
        
        if self.state == "MENU":
            self._draw_menu(canvas)
        elif self.state == "EXERCISE_SELECT":
            self._draw_exercise_select(canvas)
        elif self.state == "SONG_SELECT":
            self._draw_song_select(canvas)
        elif self.state == "CALIBRATION":
            self._draw_calibration(canvas)
        elif self.state == "COUNTDOWN":
            self._draw_gameplay(canvas)
            self._draw_countdown_overlay(canvas)
        elif self.state == "ONLINE_LOBBY":
            self._draw_online_lobby(canvas)
        elif self.state == "ONLINE_WAITING":
            self._draw_online_waiting(canvas)
        elif self.state == "ONLINE_CALIBRATION":
            self._draw_online_calibration(canvas)
        elif self.state == "ONLINE_COUNTDOWN":
            self._draw_gameplay(canvas)
            self._draw_online_countdown_overlay(canvas)
        elif self.state == "GAMEPLAY":
            self._draw_gameplay(canvas)
            if self.is_paused_out_of_frame:
                self._draw_out_of_frame_overlay(canvas)
        elif self.state == "ONLINE_GAMEPLAY":
            self._draw_online_gameplay(canvas)
            if self.is_paused_out_of_frame:
                self._draw_out_of_frame_overlay(canvas)
        elif self.state == "RESULTS":
            self._draw_results(canvas)
        elif self.state == "LEADERBOARD":
            self._draw_leaderboard(canvas)
            
        self.particles.draw(canvas)
        
        for popup in self.floating_popups:
            font_scale = int(22 * popup["scale"])
            scaled_font = pygame.font.SysFont("Consolas", font_scale, bold=True)
            draw_neon_text(canvas, popup["text"], scaled_font, (popup["x"], popup["y"]), popup["color"], glow_radius=3)
            
        shake_offset_x = 0
        shake_offset_y = 0
        if self.screen_shake_time > 0:
            shake_offset_x = random.randint(-8, 8)
            shake_offset_y = random.randint(-8, 8)
            
        self.screen.blit(canvas, (shake_offset_x, shake_offset_y))
        pygame.display.flip()

    def _draw_ambient_neon_grid(self, surface):
        """Draws a beautiful, deep-space neon cyberpunk vector grid that scrolls and pulses."""
        # Clean ambient dark overlay
        surface.fill(BLACK)
        
        # Grid lines color with transparency
        pulse = self.grid_pulse_scale
        grid_color = (
            int(30 * pulse),
            int(10 * pulse),
            int(50 * pulse)
        ) # Deep purple glow
        
        grid_w = 80
        # Horizontal lines (scrolling down)
        y_start = int(self.grid_scroll_offset) % grid_w
        for y in range(y_start, self.height, grid_w):
            pygame.draw.line(surface, grid_color, (0, y), (self.width, y), 1)
            
        # Vertical lines (static or scrolling side-to-side)
        for x in range(0, self.width, grid_w):
            pygame.draw.line(surface, grid_color, (x, 0), (x, self.height), 1)
            
        # Add a subtle radial gradient at the center
        # We can draw some faint concentric circles in the background
        center_x, center_y = self.width // 2, self.height // 2
        for r in range(100, 600, 150):
            rad_color = (
                int(0 * pulse),
                int(20 * pulse),
                int(35 * pulse),
                int(15 * (1.0 - r / 600.0))
            )
            # draw with transparency
            temp_s = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            pygame.draw.circle(temp_s, rad_color, (center_x, center_y), r, 2)
            surface.blit(temp_s, (0, 0))

    def _draw_menu(self, surface):
        """Draws the main menu with cyber-arcade typography and glowing buttons."""
        cx = self.width // 2
        
        # Draw large title with pulsing logo
        logo_glow = int(6 + 4 * math.sin(time.time() * 5.0))
        draw_neon_text(surface, "PULSEFIT ARENA", self.font_title, (cx, 160), CYAN, logo_glow)
        draw_neon_text(surface, "AI-POWERED NEON RHYTHM FITNESS", self.font_hud, (cx, 220), PURPLE, 2)
        
        # Position menu buttons vertically
        start_y = 280
        btn_w, btn_h = 440, 50
        dy = 65
        
        for idx, btn in enumerate(self.menu_buttons):
            btn_rect = pygame.Rect(cx - btn_w // 2, start_y + idx * dy, btn_w, btn_h)
            btn["rect"] = btn_rect  # Save rect for event click checking
            
            is_selected = (idx == self.selected_button_idx)
            
            # Button background
            bg_col = (20, 20, 40) if is_selected else (10, 10, 20)
            pygame.draw.rect(surface, bg_col, btn_rect, border_radius=8)
            
            # Neon border glow and text color
            border_col = CYAN if is_selected else DARK_GRAY
            text_col = WHITE if is_selected else GRAY
            glow_rad = 6 if is_selected else 0
            
            # Hover animation offset
            draw_x = cx
            if is_selected:
                draw_x = cx + int(10 * math.sin(time.time() * 8.0)) # subtle wiggle or shift
                
            draw_neon_rect(surface, btn_rect, border_col, width=2, border_radius=8, glow_radius=glow_rad)
            draw_neon_text(surface, btn["label"], self.font_hud, (draw_x, btn_rect.centery), text_col, 2 if is_selected else 0)
            
        # Draw arcade instructions at the bottom
        lbl_inst = self.font_small.render("USE [UP / DOWN] TO NAVIGATE — PRESS [ENTER / SPACE] TO SELECT", True, GRAY)
        surface.blit(lbl_inst, (cx - lbl_inst.get_width() // 2, self.height - 50))

    def _draw_exercise_select(self, surface):
        """Draws high-tech exercise selection list and profile analytics card."""
        cx = self.width // 2
        draw_neon_text(surface, "SELECT SYSTEM WORKOUT", self.font_title, (cx, 80), PURPLE, 4)
        
        # Left Panel: Exercise List
        list_x = 80
        list_y = 170
        list_w = 520
        list_h = 440
        
        list_rect = pygame.Rect(list_x, list_y, list_w, list_h)
        pygame.draw.rect(surface, (12, 12, 28), list_rect, border_radius=12)
        draw_neon_rect(surface, list_rect, PURPLE, 2, border_radius=12, glow_radius=3)
        
        dy = 110
        for idx, ex in enumerate(self.exercises_list):
            ex_rect = pygame.Rect(list_x + 20, list_y + 20 + idx * dy, list_w - 40, 90)
            is_selected = (idx == self.selected_exercise_idx)
            
            bg_col = (20, 30, 50) if is_selected else (15, 15, 25)
            pygame.draw.rect(surface, bg_col, ex_rect, border_radius=10)
            
            border_col = CYAN if is_selected else DARK_GRAY
            glow_rad = 5 if is_selected else 0
            
            draw_neon_rect(surface, ex_rect, border_col, width=2, border_radius=10, glow_radius=glow_rad)
            
            # Text alignment
            text_x = ex_rect.x + 30
            text_y = ex_rect.centery - 15
            
            lbl_title = self.font_header.render(ex["name"], True, WHITE if is_selected else GRAY)
            surface.blit(lbl_title, (text_x, text_y))
            
            lbl_bpm = self.font_small.render("GESTURE SYSTEM: MediaPipe AI Pose Tracking", True, CYAN if is_selected else GRAY)
            surface.blit(lbl_bpm, (text_x, text_y + 35))
            
        # Right Panel: Exercise Analysis card
        card_x = 650
        card_y = 170
        card_w = 550
        card_h = 440
        
        card_rect = pygame.Rect(card_x, card_y, card_w, card_h)
        pygame.draw.rect(surface, (12, 12, 28), card_rect, border_radius=12)
        draw_neon_rect(surface, card_rect, CYAN, 2, border_radius=12, glow_radius=3)
        
        # Analyze current selected exercise
        sel_ex = self.exercises_list[self.selected_exercise_idx]
        
        draw_neon_text(surface, "WORKOUT PROFILE LOGS", self.font_header, (card_rect.centerx, card_rect.y + 40), WHITE, 1)
        draw_neon_line(surface, (card_rect.x + 30, card_rect.y + 70), (card_rect.x + card_w - 30, card_rect.y + 70), DARK_GRAY, 1, 1)
        
        # Word wrap helper
        def wrap_text(text, max_w, font):
            words = text.split(' ')
            lines = []
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                if font.size(test_line)[0] < max_w:
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(' '.join(current_line))
            return lines
            
        # Drawing details inside card
        card_text_y = card_rect.y + 100
        
        # Draw exercise description
        desc_wrapped = wrap_text(sel_ex["desc"], card_w - 60, self.font_hud)
        for line in desc_wrapped:
            lbl_desc = self.font_hud.render(line, True, WHITE)
            surface.blit(lbl_desc, (card_rect.x + 30, card_text_y))
            card_text_y += 30
            
        card_text_y += 10
        
        # Joint Tracking details
        lbl_tracker = self.font_header.render("TRACKED JOINTS:", True, PURPLE)
        surface.blit(lbl_tracker, (card_rect.x + 30, card_text_y))
        card_text_y += 35
        
        if sel_ex["name"] == "SQUATS":
            joints_text = "Hips, Knees, Ankles, Shoulders (Back Angle)"
        elif sel_ex["name"] == "JUMPING JACKS":
            joints_text = "Wrists, Shoulders, Ankles (Hands height & feet spread)"
        else:
            joints_text = "Elbows, Shoulders, Wrists (Punch full extension)"
            
        lbl_joints = self.font_hud.render(joints_text, True, CYAN)
        surface.blit(lbl_joints, (card_rect.x + 30, card_text_y))
        card_text_y += 45
        
        # Form Tips
        lbl_tips = self.font_header.render("TRAINING TIPS:", True, PURPLE)
        surface.blit(lbl_tips, (card_rect.x + 30, card_text_y))
        card_text_y += 35
        
        if sel_ex["name"] == "SQUATS":
            tips_text = "Keep chest puffed out. Try to bend knees below 115 degrees."
        elif sel_ex["name"] == "JUMPING JACKS":
            tips_text = "Open arms and legs wide on the beat. Coordinate hand raise."
        else:
            tips_text = "Punches must be rapid and reach full extension. Keep your guard up."
            
        lbl_tip_val = self.font_hud.render(tips_text, True, WHITE)
        surface.blit(lbl_tip_val, (card_rect.x + 30, card_text_y))
        
        # Draw arcade instructions at the bottom
        lbl_inst = self.font_small.render("USE [UP / DOWN] TO NAVIGATE — PRESS [ENTER / SPACE] TO SELECT", True, GRAY)
        surface.blit(lbl_inst, (cx - lbl_inst.get_width() // 2, self.height - 50))

    def _draw_song_select(self, surface):
        """Draws high-tech track list and music selection analytics card."""
        cx = self.width // 2
        draw_neon_text(surface, "SELECT BEAT TRACK", self.font_title, (cx, 80), PURPLE, 4)
        
        # Left Panel: Track List
        list_x = 80
        list_y = 170
        list_w = 520
        list_h = 440
        
        list_rect = pygame.Rect(list_x, list_y, list_w, list_h)
        pygame.draw.rect(surface, (12, 12, 28), list_rect, border_radius=12)
        draw_neon_rect(surface, list_rect, PURPLE, 2, border_radius=12, glow_radius=3)
        
        dy = 110
        for idx, song in enumerate(self.songs_list):
            song_rect = pygame.Rect(list_x + 20, list_y + 20 + idx * dy, list_w - 40, 90)
            is_selected = (idx == self.selected_song_idx)
            
            bg_col = (20, 30, 50) if is_selected else (15, 15, 25)
            pygame.draw.rect(surface, bg_col, song_rect, border_radius=10)
            
            border_col = CYAN if is_selected else DARK_GRAY
            glow_rad = 5 if is_selected else 0
            
            draw_neon_rect(surface, song_rect, border_col, width=2, border_radius=10, glow_radius=glow_rad)
            
            # Text alignment
            text_x = song_rect.x + 30
            text_y = song_rect.centery - 15
            
            lbl_title = self.font_header.render(song["name"], True, WHITE if is_selected else GRAY)
            surface.blit(lbl_title, (text_x, text_y))
            
            lbl_bpm = self.font_small.render(f"TEMPO: {song['bpm']} BPM  |  DIFFICULTY: {song['diff'].upper()}", True, CYAN if is_selected else GRAY)
            surface.blit(lbl_bpm, (text_x, text_y + 35))
            
        # Right Panel: Track Analysis card
        card_x = 650
        card_y = 170
        card_w = 550
        card_h = 440
        
        card_rect = pygame.Rect(card_x, card_y, card_w, card_h)
        pygame.draw.rect(surface, (12, 12, 28), card_rect, border_radius=12)
        draw_neon_rect(surface, card_rect, CYAN, 2, border_radius=12, glow_radius=3)
        
        # Analyze current selected song
        sel_song = self.songs_list[self.selected_song_idx]
        
        draw_neon_text(surface, "TRACK PROFILE LOGS", self.font_header, (card_rect.centerx, card_rect.y + 40), WHITE, 1)
        draw_neon_line(surface, (card_rect.x + 30, card_rect.y + 70), (card_rect.x + card_w - 30, card_rect.y + 70), DARK_GRAY, 1, 1)
        
        # Detailed stats inside card
        stats_y = card_y + 100
        stats_dy = 35
        
        def draw_card_stat(label, val, val_col):
            nonlocal stats_y
            lbl = self.font_hud.render(label, True, GRAY)
            surface.blit(lbl, (card_rect.x + 40, stats_y))
            val_lbl = self.font_hud.render(val, True, val_col)
            surface.blit(val_lbl, (card_rect.x + 280, stats_y))
            stats_y += stats_dy
            
        diff_col = GREEN if sel_song["diff"] == "Easy" else (YELLOW if sel_song["diff"] == "Medium" else RED)
        draw_card_stat("TARGET RHYTHM:", f"{sel_song['bpm']} BPM", CYAN)
        draw_card_stat("INTENSITY RATE:", sel_song['diff'].upper(), diff_col)
        draw_card_stat("EST. BURNT RATE:", "450 kcal/hr" if sel_song["diff"] == "Easy" else ("620 kcal/hr" if sel_song["diff"] == "Medium" else "840 kcal/hr"), PINK)
        draw_card_stat("BIOMECH TARGET:", "Knee Extension / Quad", WHITE)
        draw_card_stat("AI FEEDBACK RATE:", "Real-Time Tracking", GREEN)
        
        # Synthesized audio waveform graphic (animated mock lines)
        wave_rect = pygame.Rect(card_rect.x + 40, card_rect.y + card_h - 100, card_w - 80, 60)
        pygame.draw.rect(surface, (8, 8, 16), wave_rect, border_radius=6)
        draw_neon_rect(surface, wave_rect, PURPLE, 1, border_radius=6, glow_radius=1)
        
        # Draw neon waveform lines
        half_h = wave_rect.height // 2
        for x_idx in range(10, wave_rect.width - 10, 4):
            # animated wave scaling
            wave_scale = math.sin((x_idx * 0.05) + (time.time() * 8.0)) * math.cos(x_idx * 0.02)
            wave_h = int(half_h * 0.7 * wave_scale)
            # Clip limits
            wave_h = max(-half_h + 5, min(half_h - 5, wave_h))
            
            p_start = (wave_rect.x + x_idx, wave_rect.centery - wave_h)
            p_end = (wave_rect.x + x_idx, wave_rect.centery + wave_h)
            pygame.draw.line(surface, PINK if x_idx % 8 == 0 else CYAN, p_start, p_end, 2)
            
        lbl_exit = self.font_hud.render("PRESS [ENTER] TO CONFIRM   |   [ESC] TO CANCEL", True, WHITE)
        surface.blit(lbl_exit, (cx - lbl_exit.get_width() // 2, self.height - 40))

    def _draw_calibration(self, surface):
        """Displays checklist verifying local players are aligned before song starts."""
        draw_neon_text(surface, "SYSTEM MOTION CALIBRATION", self.font_header, (self.width // 2, 60), CYAN, 4)
        
        if self.game_mode == "MULTIPLAYER":
            half_w = self.width // 2
            # Left Lane: Player 1
            self._draw_local_calibration_lane(surface, 0, 0, half_w)
            # Right Lane: Player 2
            self._draw_local_calibration_lane(surface, 1, half_w, half_w)
            # Divider
            draw_neon_line(surface, (half_w, 40), (half_w, self.height), PURPLE, 2, 3)
        else:
            # Full screen solo lane
            self._draw_local_calibration_lane(surface, 0, 0, self.width)
            
        lbl_exit = self.font_small.render("PRESS [ESC] TO CANCEL AND RETURN TO LOBBY", True, GRAY)
        surface.blit(lbl_exit, (self.width // 2 - lbl_exit.get_width() // 2, self.height - 40))

    def _draw_local_calibration_lane(self, surface, p_idx, start_x, width):
        """Draws camera panels and joint presence checklists for local players."""
        cam_w, cam_h = 420 if width > 800 else 320, 300 if width > 800 else 240
        cam_x = start_x + (width // 2 - cam_w // 2)
        cam_y = 120
        
        cam_rect = pygame.Rect(cam_x, cam_y, cam_w, cam_h)
        pygame.draw.rect(surface, (15, 15, 25), cam_rect, border_radius=8)
        draw_neon_rect(surface, cam_rect, CYAN if p_idx == 0 else PINK, 2, border_radius=8, glow_radius=2)
        
        # Retrieve detector
        det = self.p1_detector if p_idx == 0 else self.p2_detector
        
        # Draw direct camera feed
        if det:
            raw_f, ann_f = det.get_latest_frame()
            if ann_f is not None:
                ann_pyg = cv2.resize(ann_f, (cam_w, cam_h))
                ann_pyg = cv2.cvtColor(ann_pyg, cv2.COLOR_BGR2RGB)
                ann_surf = pygame.surfarray.make_surface(ann_pyg.swapaxes(0, 1))
                surface.blit(ann_surf, (cam_x, cam_y))
            else:
                draw_neon_text(surface, "CAMERA WARMING UP...", self.font_small, cam_rect.center, CYAN if p_idx == 0 else PINK, 1)
        else:
            draw_neon_text(surface, "INITIALIZING CAMERA...", self.font_small, cam_rect.center, GRAY, 0)
            
        all_in_frame = det.body_in_frame if det else False
        if not all_in_frame:
            # Draw holographic posture guide silhouette
            guide_surf = pygame.Surface((cam_w, cam_h), pygame.SRCALPHA)
            guide_color = (0, 240, 255, 80) if p_idx == 0 else (255, 0, 127, 80)
            
            gc_x = cam_w // 2
            
            head_center = (gc_x, int(cam_h * 0.22))
            shoulder_y = int(cam_h * 0.32)
            l_sh = (gc_x - int(cam_w * 0.15), shoulder_y)
            r_sh = (gc_x + int(cam_w * 0.15), shoulder_y)
            
            hip_y = int(cam_h * 0.52)
            l_hp = (gc_x - int(cam_w * 0.11), hip_y)
            r_hp = (gc_x + int(cam_w * 0.11), hip_y)
            
            knee_y = int(cam_h * 0.72)
            l_kn = (gc_x - int(cam_w * 0.11), knee_y)
            r_kn = (gc_x + int(cam_w * 0.11), knee_y)
            
            ankle_y = int(cam_h * 0.90)
            l_ak = (gc_x - int(cam_w * 0.11), ankle_y)
            r_ak = (gc_x + int(cam_w * 0.11), ankle_y)
            
            # Head
            pygame.draw.circle(guide_surf, guide_color, head_center, int(cam_h * 0.08), 2)
            # Spine & Shoulders/Hips
            pygame.draw.line(guide_surf, guide_color, l_sh, r_sh, 3)
            pygame.draw.line(guide_surf, guide_color, l_hp, r_hp, 3)
            pygame.draw.line(guide_surf, guide_color, (gc_x, shoulder_y), (gc_x, hip_y), 3)
            # Legs
            pygame.draw.line(guide_surf, guide_color, l_hp, l_kn, 3)
            pygame.draw.line(guide_surf, guide_color, l_kn, l_ak, 3)
            pygame.draw.line(guide_surf, guide_color, r_hp, r_kn, 3)
            pygame.draw.line(guide_surf, guide_color, r_kn, r_ak, 3)
            # Arms
            pygame.draw.line(guide_surf, guide_color, l_sh, (l_sh[0] - 10, int(cam_h * 0.5)), 3)
            pygame.draw.line(guide_surf, guide_color, r_sh, (r_sh[0] + 10, int(cam_h * 0.5)), 3)
            
            surface.blit(guide_surf, (cam_x, cam_y))
            draw_neon_text(surface, "ALIGN BODY TO SILHOUETTE", self.font_small, (cam_x + cam_w//2, cam_y + 25), WHITE, 1)
            
        checklist = [
            ("Shoulders Visible", det.shoulders_in_frame if det else False),
            ("Hips Visible", det.hips_in_frame if det else False),
            ("Knees Visible", det.knees_in_frame if det else False),
            ("Ankles Visible", det.ankles_in_frame if det else False)
        ]
        all_in_frame = det.body_in_frame if det else False
        p_name = f"PLAYER {p_idx+1} (YOU)" if self.game_mode == "MULTIPLAYER" else "PLAYER WORKOUT POSTURE"
        
        # Draw small checklist cards below camera
        list_y = cam_y + cam_h + 20
        list_w = cam_w
        list_h = 200
        list_rect = pygame.Rect(cam_x, list_y, list_w, list_h)
        
        pygame.draw.rect(surface, (12, 12, 28), list_rect, border_radius=10)
        draw_neon_rect(surface, list_rect, PURPLE, 1, border_radius=10, glow_radius=1)
        
        draw_neon_text(surface, p_name, self.font_hud, (list_rect.centerx, list_rect.y + 25), WHITE, 1)
        draw_neon_line(surface, (list_rect.x + 20, list_rect.y + 45), (list_rect.x + list_w - 20, list_rect.y + 45), DARK_GRAY, 1, 1)
        
        dy_y = list_rect.y + 60
        for label, status in checklist:
            dot_col = GREEN if status else PINK
            draw_neon_circle(surface, (list_rect.x + 30, dy_y + 8), 6, dot_col, 0 if status else 1, 2)
            lbl_item = self.font_small.render(label, True, WHITE if status else GRAY)
            surface.blit(lbl_item, (list_rect.x + 50, dy_y))
            dy_y += 24
            
        # Aligned holds status bar
        blink = (int(time.time() * 2.5) % 2 == 0)
        draw_neon_line(surface, (list_rect.x + 20, list_rect.y + 160), (list_rect.x + list_w - 20, list_rect.y + 160), DARK_GRAY, 1, 1)
        
        if all_in_frame:
            draw_neon_text(surface, "✨ POSITION LOCKED", self.font_small, (list_rect.centerx, list_rect.y + 178), GREEN, 2)
        else:
            warn_c = PINK if blink else (230, 80, 80)
            draw_neon_text(surface, "⚠️ ALIGN ENTIRE BODY IN FRAME", self.font_small, (list_rect.centerx, list_rect.y + 178), warn_c, 2)

    def _draw_gameplay(self, surface):
        """Routes gameplay drawing based on local SOLO / MULTIPLAYER mode."""
        if self.game_mode == "SOLO":
            self._draw_solo_gameplay(surface)
        elif self.game_mode == "MULTIPLAYER":
            self._draw_multiplayer_gameplay(surface)

    # --- MAIN STATE SWITCH ROUTER DRAW LOOPS ---
    def _draw_online_lobby(self, surface):
        """Renders alphanumeric Room code lobby screen."""
        draw_neon_text(surface, "ONLINE MULTIPLAYER ARENA", self.font_header, (self.width // 2, 70), CYAN, 5)
        
        panel_w = 480
        panel_h = 360
        blink = (int(time.time() * 2.5) % 2 == 0)
        
        # --- LEFT PANEL: CREATE LOBBY CARD ---
        c_rect = pygame.Rect(self.width//4 - panel_w//4, 150, panel_w - 40, panel_h)
        pygame.draw.rect(surface, (12, 12, 28), c_rect, border_radius=12)
        draw_neon_rect(surface, c_rect, CYAN, 2, border_radius=12, glow_radius=2)
        
        draw_neon_text(surface, "HOST AN ARENA", self.font_hud, (c_rect.centerx, c_rect.y + 40), WHITE, 1)
        draw_neon_line(surface, (c_rect.x + 20, c_rect.y + 65), (c_rect.x + c_rect.width - 20, c_rect.y + 65), DARK_GRAY, 1, 1)
        
        lbl_c_desc1 = self.font_small.render("GENERATE A SECURE ROOM CODE", True, GRAY)
        lbl_c_desc2 = self.font_small.render("AND INVITE YOUR FRIEND OVER THE WEB", True, GRAY)
        surface.blit(lbl_c_desc1, (c_rect.centerx - lbl_c_desc1.get_width()//2, c_rect.y + 110))
        surface.blit(lbl_c_desc2, (c_rect.centerx - lbl_c_desc2.get_width()//2, c_rect.y + 135))
        
        btn_create = pygame.Rect(c_rect.centerx - 140, c_rect.y + 220, 280, 50)
        pygame.draw.rect(surface, (20, 30, 50), btn_create, border_radius=6)
        draw_neon_rect(surface, btn_create, CYAN, 2, border_radius=6, glow_radius=4 if blink else 1)
        draw_neon_text(surface, "PRESS [ C ] TO HOST", self.font_hud, btn_create.center, WHITE, 2)
        
        # --- RIGHT PANEL: JOIN LOBBY CARD ---
        j_rect = pygame.Rect((self.width//4)*3 - panel_w//4, 150, panel_w - 40, panel_h)
        pygame.draw.rect(surface, (12, 12, 28), j_rect, border_radius=12)
        draw_neon_rect(surface, j_rect, PINK, 2, border_radius=12, glow_radius=2)
        
        draw_neon_text(surface, "JOIN AN ARENA", self.font_hud, (j_rect.centerx, j_rect.y + 40), WHITE, 1)
        draw_neon_line(surface, (j_rect.x + 20, j_rect.y + 65), (j_rect.x + j_rect.width - 20, j_rect.y + 65), DARK_GRAY, 1, 1)
        
        lbl_j_desc = self.font_small.render("ENTER PLAYER 1'S 4-LETTER LOBBY CODE", True, GRAY)
        surface.blit(lbl_j_desc, (j_rect.centerx - lbl_j_desc.get_width()//2, j_rect.y + 110))
        
        # Glowing text-input panel
        inp_box = pygame.Rect(j_rect.centerx - 140, j_rect.y + 160, 280, 60)
        pygame.draw.rect(surface, (25, 10, 20), inp_box, border_radius=8)
        draw_neon_rect(surface, inp_box, PINK, 2, border_radius=8, glow_radius=4)
        
        # Render typed characters
        typed_str = self.typed_room_code
        if len(typed_str) < 4 and blink:
            # draw cursor
            display_str = typed_str + "_"
        else:
            display_str = typed_str
            
        # Draw spaces between characters for hi-tech visual styling
        spaced_str = "  ".join(list(display_str)) if display_str else "TYPE CODE"
        inp_col = WHITE if display_str != "TYPE CODE" else GRAY
        draw_neon_text(surface, spaced_str, self.font_header, inp_box.center, inp_col, 2 if inp_col == WHITE else 0)
        
        btn_join = pygame.Rect(j_rect.centerx - 140, j_rect.y + 245, 280, 45)
        pygame.draw.rect(surface, (40, 10, 20), btn_join, border_radius=6)
        draw_neon_rect(surface, btn_join, PINK, 1, border_radius=6, glow_radius=1)
        draw_neon_text(surface, "PRESS [ ENTER ] TO JOIN", self.font_small, btn_join.center, WHITE, 1)
        
        # Display Server connection status / errors
        if self.net_error:
            draw_neon_text(surface, f"⚠️ {self.net_error}", self.font_hud, (self.width // 2, self.height - 110), PINK, 4)
        else:
            draw_neon_text(surface, "Connected to: Local Server Coordinator", self.font_small, (self.width // 2, self.height - 110), GREEN, 0)
            
        lbl_exit = self.font_small.render("PRESS [ESC] TO CANCEL AND GO LOBBY", True, GRAY)
        surface.blit(lbl_exit, (self.width // 2 - lbl_exit.get_width() // 2, self.height - 50))

    def _draw_online_waiting(self, surface):
        """Displays lobby waiting panel for opponent connection."""
        role_label = "ROOM HOST" if self.net_client and self.net_client.role == "HOST" else "ROOM GUEST"
        draw_neon_text(surface, f"ONLINE MATCH LOBBY ({role_label})", self.font_header, (self.width // 2, 70), CYAN, 4)
        
        card_w = 600
        card_h = 320
        card_rect = pygame.Rect(self.width//2 - card_w//2, 160, card_w, card_h)
        
        pygame.draw.rect(surface, (12, 12, 28), card_rect, border_radius=12)
        draw_neon_rect(surface, card_rect, PURPLE, 2, border_radius=12, glow_radius=3)
        
        code = self.net_client.room_code if self.net_client else "NONE"
        draw_neon_text(surface, "MATCH ROOM CODE", self.font_hud, (card_rect.centerx, card_rect.y + 45), GRAY, 0)
        
        # Huge Room Code
        spaced_code = "  ".join(list(code))
        draw_neon_text(surface, spaced_code, pygame.font.SysFont("Consolas", 64, bold=True), (card_rect.centerx, card_rect.y + 115), CYAN, 6)
        
        draw_neon_line(surface, (card_rect.x + 30, card_rect.y + 180), (card_rect.x + card_w - 30, card_rect.y + 180), DARK_GRAY, 1, 1)
        
        blink = (int(time.time() * 2.0) % 2 == 0)
        
        # Waiting status text
        if self.net_client and self.net_client.role == "HOST":
            warn_col = PURPLE if blink else CYAN
            draw_neon_text(surface, "WAITING FOR OPPONENT TO JOIN...", self.font_hud, (card_rect.centerx, card_rect.y + 235), warn_col, 3)
            lbl_ins = self.font_small.render("SHARE THE 4-LETTER ROOM CODE WITH PLAYER 2", True, GRAY)
            surface.blit(lbl_ins, (card_rect.centerx - lbl_ins.get_width()//2, card_rect.y + 270))
        else:
            draw_neon_text(surface, "CONNECTED! WAITING FOR HOST TO START MATCH...", self.font_hud, (card_rect.centerx, card_rect.y + 235), GREEN, 3)
            lbl_ins = self.font_small.render("HOST IS SELECTING SONGS AND BPM INTENSITIES", True, GRAY)
            surface.blit(lbl_ins, (card_rect.centerx - lbl_ins.get_width()//2, card_rect.y + 270))
            
        lbl_exit = self.font_small.render("PRESS [ESC] TO DISCONNECT AND CANCEL", True, GRAY)
        surface.blit(lbl_exit, (self.width // 2 - lbl_exit.get_width() // 2, self.height - 50))

    def _draw_online_calibration(self, surface):
        """Displays splitscreen checklist verifying both remote players are aligned."""
        draw_neon_text(surface, "MULTIPLAYER SYNC CALIBRATION", self.font_header, (self.width // 2, 60), CYAN, 4)
        
        half_w = self.width // 2
        
        # Left Side: Player 1 (Local)
        self._draw_online_calibration_lane(surface, 0, 0, half_w)
        
        # Right Side: Player 2 (Network Opponent)
        self._draw_online_calibration_lane(surface, 1, half_w, half_w)
        
        # Draw central divider line
        draw_neon_line(surface, (half_w, 40), (half_w, self.height), PURPLE, 2, 3)

    def _draw_online_calibration_lane(self, surface, p_idx, start_x, width):
        """Draws camera panels and joint presence lists for online lane segments."""
        cam_w, cam_h = 320, 240
        cam_x = start_x + 20
        cam_y = 120
        
        cam_rect = pygame.Rect(cam_x, cam_y, cam_w, cam_h)
        pygame.draw.rect(surface, (15, 15, 25), cam_rect, border_radius=8)
        draw_neon_rect(surface, cam_rect, CYAN if p_idx == 0 else PINK, 2, border_radius=8, glow_radius=2)
        
        # Retrieve calibration items
        if p_idx == 0:
            # Local player: draw direct camera feed
            if self.p1_detector:
                raw_f, ann_f = self.p1_detector.get_latest_frame()
                if ann_f is not None:
                    ann_pyg = cv2.resize(ann_f, (cam_w, cam_h))
                    ann_pyg = cv2.cvtColor(ann_pyg, cv2.COLOR_BGR2RGB)
                    ann_surf = pygame.surfarray.make_surface(ann_pyg.swapaxes(0, 1))
                    surface.blit(ann_surf, (cam_x, cam_y))
            det = self.p1_detector
            checklist = [
                ("Shoulders Visible", det.shoulders_in_frame if det else False),
                ("Hips Visible", det.hips_in_frame if det else False),
                ("Knees Visible", det.knees_in_frame if det else False),
                ("Ankles Visible", det.ankles_in_frame if det else False)
            ]
            all_in_frame = det.body_in_frame if det else False
            
            if not all_in_frame:
                # Draw holographic posture guide silhouette (320x240 size)
                guide_surf = pygame.Surface((cam_w, cam_h), pygame.SRCALPHA)
                guide_color = (0, 240, 255, 80)
                
                gc_x = cam_w // 2
                
                head_center = (gc_x, int(cam_h * 0.22))
                shoulder_y = int(cam_h * 0.32)
                l_sh = (gc_x - int(cam_w * 0.15), shoulder_y)
                r_sh = (gc_x + int(cam_w * 0.15), shoulder_y)
                
                hip_y = int(cam_h * 0.52)
                l_hp = (gc_x - int(cam_w * 0.11), hip_y)
                r_hp = (gc_x + int(cam_w * 0.11), hip_y)
                
                knee_y = int(cam_h * 0.72)
                l_kn = (gc_x - int(cam_w * 0.11), knee_y)
                r_kn = (gc_x + int(cam_w * 0.11), knee_y)
                
                ankle_y = int(cam_h * 0.90)
                l_ak = (gc_x - int(cam_w * 0.11), ankle_y)
                r_ak = (gc_x + int(cam_w * 0.11), ankle_y)
                
                # Head
                pygame.draw.circle(guide_surf, guide_color, head_center, int(cam_h * 0.08), 2)
                # Spine & Shoulders/Hips
                pygame.draw.line(guide_surf, guide_color, l_sh, r_sh, 3)
                pygame.draw.line(guide_surf, guide_color, l_hp, r_hp, 3)
                pygame.draw.line(guide_surf, guide_color, (gc_x, shoulder_y), (gc_x, hip_y), 3)
                # Legs
                pygame.draw.line(guide_surf, guide_color, l_hp, l_kn, 3)
                pygame.draw.line(guide_surf, guide_color, l_kn, l_ak, 3)
                pygame.draw.line(guide_surf, guide_color, r_hp, r_kn, 3)
                pygame.draw.line(guide_surf, guide_color, r_kn, r_ak, 3)
                # Arms
                pygame.draw.line(guide_surf, guide_color, l_sh, (l_sh[0] - 10, int(cam_h * 0.5)), 3)
                pygame.draw.line(guide_surf, guide_color, r_sh, (r_sh[0] + 10, int(cam_h * 0.5)), 3)
                
                surface.blit(guide_surf, (cam_x, cam_y))
                draw_neon_text(surface, "ALIGN TO SILHOUETTE", self.font_small, (cam_x + cam_w//2, cam_y + 20), WHITE, 1)
                
            p_name = "PLAYER 1 (YOU)"
        else:
            # Remote Opponent: Draw static cyber silhouette with glowing scan dots
            pygame.draw.rect(surface, (10, 10, 20), cam_rect, border_radius=8)
            # scanner overlay line
            scan_y = cam_y + int((time.time() * 120) % cam_h)
            pygame.draw.line(surface, (255, 30, 100, 100), (cam_x, scan_y), (cam_x + cam_w, scan_y), 2)
            
            draw_neon_text(surface, "REMOTE SKELETON FEED", self.font_small, cam_rect.center, PINK, 1)
            
            opp_cal = self.net_client.opponent_calibration if self.net_client else {}
            checklist = [
                ("Shoulders Visible", opp_cal.get("shoulders", False)),
                ("Hips Visible", opp_cal.get("hips", False)),
                ("Knees Visible", opp_cal.get("knees", False)),
                ("Ankles Visible", opp_cal.get("ankles", False))
            ]
            all_in_frame = opp_cal.get("body_in_frame", False)
            p_name = "PLAYER 2 (OPPONENT)"
            
        # Draw small checklist cards below camera
        list_y = cam_y + cam_h + 20
        list_w = cam_w
        list_h = 240
        list_rect = pygame.Rect(cam_x, list_y, list_w, list_h)
        
        pygame.draw.rect(surface, (12, 12, 28), list_rect, border_radius=10)
        draw_neon_rect(surface, list_rect, PURPLE, 1, border_radius=10, glow_radius=1)
        
        draw_neon_text(surface, p_name, self.font_hud, (list_rect.centerx, list_rect.y + 25), WHITE, 1)
        draw_neon_line(surface, (list_rect.x + 20, list_rect.y + 45), (list_rect.x + list_w - 20, list_rect.y + 45), DARK_GRAY, 1, 1)
        
        dy_y = list_rect.y + 65
        for label, status in checklist:
            dot_col = GREEN if status else PINK
            
            draw_neon_circle(surface, (list_rect.x + 30, dy_y + 10), 8, dot_col, 0 if status else 1, 2)
            lbl_item = self.font_small.render(label, True, WHITE if status else GRAY)
            surface.blit(lbl_item, (list_rect.x + 55, dy_y + 2))
            
            dy_y += 32
            
        # Aligned holds
        blink = (int(time.time() * 2.5) % 2 == 0)
        draw_neon_line(surface, (list_rect.x + 20, list_rect.y + 195), (list_rect.x + list_w - 20, list_rect.y + 195), DARK_GRAY, 1, 1)
        
        if all_in_frame:
            draw_neon_text(surface, "✨ POSITION LOCKED", self.font_small, (list_rect.centerx, list_rect.y + 218), GREEN, 2)
        else:
            warn_c = PINK if blink else (230, 80, 80)
            draw_neon_text(surface, "⚠️ ALIGN ENTIRE BODY", self.font_small, (list_rect.centerx, list_rect.y + 218), warn_c, 2)

    def _draw_online_countdown_overlay(self, surface):
        """Pulsing giant digits before online match starts."""
        self._draw_countdown_overlay(surface)

    def _draw_online_gameplay(self, surface):
        """Splits screen vertically, rendering remote coordinates live."""
        half_w = self.width // 2
        
        # 1. Draw Player 1 (Local player on Left Half)
        self._draw_multiplayer_lane(surface, 0, 0, half_w)
        
        # 2. Draw Player 2 (Remote opponent on Right Half)
        # Renders scores, multiplier, note highway notes scrolling, AND opponent's skeleton coords!
        self._draw_online_opponent_lane(surface, half_w, half_w)
        
        # Pulsing center separator
        draw_neon_line(surface, (half_w, 40), (half_w, self.height), PURPLE, 3, 5)

    def _draw_online_opponent_lane(self, surface, start_x, width):
        """Custom draws the remote opponent's telemetry lane."""
        cam_w, cam_h = 320, 240
        cam_x = start_x + 20
        cam_y = 60
        
        cam_rect = pygame.Rect(cam_x, cam_y, cam_w, cam_h)
        pygame.draw.rect(surface, (15, 15, 25), cam_rect, border_radius=8)
        draw_neon_rect(surface, cam_rect, PINK, 2, border_radius=8, glow_radius=2)
        
        # Draw remote player's coordinate skeleton!
        with self.net_client.lock:
            landmarks = self.net_client.opponent_telemetry.get("landmarks")
            opp_knee = self.net_client.opponent_telemetry.get("knee_angle", 180.0)
            opp_back = self.net_client.opponent_telemetry.get("back_angle", 0.0)
            
        if landmarks:
            # Draw a black canvas backing inside webcam window
            pygame.draw.rect(surface, (10, 10, 20), cam_rect, border_radius=8)
            # Reconstruct and draw opponent skeleton nodes onto Pygame frame coordinate space!
            self._draw_remote_skeleton(surface, cam_rect, landmarks, opp_back)
        else:
            # Display loader silhouette
            pygame.draw.rect(surface, (8, 8, 16), cam_rect, border_radius=8)
            draw_neon_text(surface, "RECEIVING TELEMETRY...", self.font_small, cam_rect.center, GRAY, 0)
            
        # Draw scoring hud Player 2
        score = self.score_p2.score
        combo = self.score_p2.combo
        energy = self.score_p2.energy
        
        lbl_p_name = self.font_hud.render(f"P2 SCORE: {score}", True, WHITE)
        surface.blit(lbl_p_name, (cam_x, cam_y + cam_h + 15))
        
        lbl_p_combo = self.font_hud.render(f"COMBO: {combo}", True, PINK)
        surface.blit(lbl_p_combo, (cam_x + 190, cam_y + cam_h + 15))
        
        e_color = GREEN if energy > 40.0 else (YELLOW if energy > 15.0 else RED)
        pygame.draw.rect(surface, DARK_GRAY, (cam_x, cam_y + cam_h + 45, cam_w, 8), border_radius=4)
        pygame.draw.rect(surface, e_color, (cam_x, cam_y + cam_h + 45, int(cam_w * (energy / 100.0)), 8), border_radius=4)
        
        # Draw P2 rhythm track scrolling
        track_w = 200
        track_x = start_x + width - track_w - 20
        track_y = 60
        track_h = self.height - 160
        
        track_rect = pygame.Rect(track_x, track_y, track_w, track_h)
        pygame.draw.rect(surface, (8, 8, 16), track_rect, border_radius=8)
        draw_neon_rect(surface, track_rect, PURPLE, 1, border_radius=8, glow_radius=2)
        
        strike_y = self.height - 120
        draw_neon_line(surface, (track_x + 5, strike_y), (track_x + track_w - 5, strike_y), PINK, 3, 5)
        
        if self.rhythm_engine_p1: # Sync note Hwy spawns mathematically
            for note in self.rhythm_engine_p1.notes:
                if note.visual_y > 0 and not note.hit and not note.missed:
                    circle_x = track_x + (track_w // 4) * (1 if note.column == 0 else 3)
                    circle_y = track_y + note.visual_y
                    
                    if circle_y < (track_y + track_h):
                        draw_neon_circle(surface, (int(circle_x), int(circle_y)), 15, PINK, 0, 4)
                        pygame.draw.circle(surface, WHITE, (int(circle_x), int(circle_y)), 5)
                        
        # Live coaching panel
        coach_rect = pygame.Rect(cam_x, self.height - 85, cam_w, 55)
        pygame.draw.rect(surface, (12, 12, 28), coach_rect, border_radius=6)
        draw_neon_rect(surface, coach_rect, PINK, 1, border_radius=6, glow_radius=1)
        
        feedback_txt = "FORM GOOD"
        feedback_col = GREEN
        if opp_back > 28.0:
            feedback_txt = "STRAIGHTEN BACK"
            feedback_col = YELLOW
        elif opp_knee < 105.0:
            feedback_txt = "DEEP SQUAT!"
            feedback_col = CYAN
        elif opp_knee > 130.0 and opp_knee < 170.0:
            feedback_txt = "GO LOWER..."
            feedback_col = RED
            
        draw_neon_text(surface, feedback_txt, self.font_hud, coach_rect.center, feedback_col, glow_radius=3)

    def _draw_remote_skeleton(self, surface, rect, landmarks, back_angle):
        """Draws Player 2's compiled neon skeleton vectors inside specified panel rect."""
        rx, ry, rw, rh = rect
        
        def to_pix(lm_dict):
            # Coordinates are normalized (0 to 1), map to bounding panel bounds
            x = rx + int(lm_dict["x"] * rw)
            y = ry + int(lm_dict["y"] * rh)
            return x, y
            
        try:
            # Map essential indexes
            l_sh, r_sh = to_pix(landmarks[11]), to_pix(landmarks[12])
            l_hp, r_hp = to_pix(landmarks[23]), to_pix(landmarks[24])
            l_kn, r_kn = to_pix(landmarks[25]), to_pix(landmarks[26])
            l_ak, r_ak = to_pix(landmarks[27]), to_pix(landmarks[28])
            
            form_color = (30, 30, 255) if back_angle > 28.0 else PINK
            sec_color = PURPLE
            
            # Draw bones
            pygame.draw.line(surface, form_color, l_sh, r_sh, 3)
            pygame.draw.line(surface, form_color, l_hp, r_hp, 3)
            
            pygame.draw.line(surface, sec_color, l_hp, l_kn, 3)
            pygame.draw.line(surface, sec_color, l_kn, l_ak, 3)
            
            pygame.draw.line(surface, sec_color, r_hp, r_kn, 3)
            pygame.draw.line(surface, sec_color, r_kn, r_ak, 3)
            
            # Nodes
            for pt in [l_sh, r_sh, l_hp, r_hp, l_kn, r_kn, l_ak, r_ak]:
                pygame.draw.circle(surface, form_color, pt, 6)
                pygame.draw.circle(surface, WHITE, pt, 3)
        except Exception as e:
            pass

    # --- SHARED OVERLAY RENDERING UTILS ---
    def _draw_countdown_overlay(self, surface):
        """Draws a dramatic full-screen transparent grid overlay and huge pulsing neon numerals."""
        dim_bg = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        dim_bg.fill((0, 0, 0, 110))
        surface.blit(dim_bg, (0, 0))
        
        cx, cy = self.width // 2, self.height // 2
        
        rem_sec = math.ceil(self.countdown_timer)
        fractional_part = self.countdown_timer - math.floor(self.countdown_timer)
        if fractional_part == 0.0: fractional_part = 1.0
        
        pulse_scale = 1.0 + fractional_part * 0.8
        pulse_alpha = int(fractional_part * 255)
        
        count_color = CYAN if rem_sec == 3 else (PURPLE if rem_sec == 2 else PINK)
        if rem_sec <= 0:
            count_text = "GO!"
            count_color = GREEN
            pulse_scale = 1.2
            pulse_alpha = 255
        else:
            count_text = str(rem_sec)
            
        ring_radius = int(80 * pulse_scale)
        draw_neon_circle(surface, (cx, cy), ring_radius, count_color, 4, glow_radius=8)
        
        scaled_font_sz = int(120 * pulse_scale)
        scaled_font = pygame.font.SysFont("Consolas", scaled_font_sz, bold=True)
        
        draw_neon_text(surface, count_text, scaled_font, (cx, cy), count_color, glow_radius=10)
        
        lbl_prepare = self.font_header.render("GET READY TO SQUAT!", True, WHITE)
        surface.blit(lbl_prepare, (cx - lbl_prepare.get_width()//2, cy - 160))

    def _draw_out_of_frame_overlay(self, surface):
        """Renders flashing fullscreen red pause alert overlay."""
        dim_bg = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        blink_alpha = int(100 + 70 * math.sin(time.time() * 6.5))
        dim_bg.fill((45, 0, 10, blink_alpha))
        surface.blit(dim_bg, (0, 0))
        
        box_w, box_h = 640, 240
        box_x = self.width//2 - box_w//2
        box_y = self.height//2 - box_h//2
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        
        pygame.draw.rect(surface, (20, 8, 12), box_rect, border_radius=12)
        draw_neon_rect(surface, box_rect, PINK, 3, border_radius=12, glow_radius=8)
        
        draw_neon_text(surface, "⚠️ TRACKER ALIGNMENT LOST", self.font_header, (self.width//2, box_y + 50), PINK, 6)
        draw_neon_text(surface, "WORKOUT PAUSED", self.font_hud, (self.width//2, box_y + 95), WHITE, 2)
        
        det = self.p1_detector
        missing_joints = []
        if det:
            if not det.shoulders_in_frame: missing_joints.append("Shoulders")
            if not det.hips_in_frame: missing_joints.append("Hips")
            if not det.knees_in_frame: missing_joints.append("Knees")
            if not det.ankles_in_frame: missing_joints.append("Ankles")
            
        missing_text = "Missing: " + (", ".join(missing_joints) if missing_joints else "Full Body")
        lbl_miss = self.font_small.render(missing_text.upper(), True, YELLOW)
        surface.blit(lbl_miss, (self.width//2 - lbl_miss.get_width()//2, box_y + 140))
        
        lbl_prompt = self.font_small.render("STEP BACK & ALIGN FULL BODY TO RESUME WORKOUT", True, GRAY)
        surface.blit(lbl_prompt, (self.width//2 - lbl_prompt.get_width()//2, box_y + 185))

    def _draw_solo_gameplay(self, surface):
        """Renders camera frame, skeleton overlay, score hud, and solo note track."""
        cam_w, cam_h = 580, 420
        cam_x, cam_y = 40, 70
        
        cam_rect = pygame.Rect(cam_x, cam_y, cam_w, cam_h)
        pygame.draw.rect(surface, (15, 15, 25), cam_rect, border_radius=10)
        draw_neon_rect(surface, cam_rect, PURPLE, width=2, border_radius=10, glow_radius=4)
        
        if self.p1_detector:
            raw_f, ann_f = self.p1_detector.get_latest_frame()
            if ann_f is not None:
                ann_pygame = cv2.resize(ann_f, (cam_w, cam_h))
                ann_pygame = cv2.cvtColor(ann_pygame, cv2.COLOR_BGR2RGB)
                ann_surface = pygame.surfarray.make_surface(ann_pygame.swapaxes(0, 1))
                surface.blit(ann_surface, (cam_x, cam_y))
                
        k_angle = int(self.p1_detector.knee_angle) if self.p1_detector else 180
        lbl_knee = self.font_hud.render(f"KNEE DEGREE: {k_angle}°", True, CYAN)
        surface.blit(lbl_knee, (cam_x + 20, cam_y + 20))
        
        track_w = 400
        track_x = self.width - track_w - 40
        track_y = 70
        track_h = self.height - 180
        
        track_rect = pygame.Rect(track_x, track_y, track_w, track_h)
        pygame.draw.rect(surface, (8, 8, 16), track_rect, border_radius=12)
        draw_neon_rect(surface, track_rect, PURPLE, width=2, border_radius=12, glow_radius=3)
        
        pygame.draw.line(surface, DARK_GRAY, (track_x + track_w//2, track_y), (track_x + track_w//2, track_y + track_h), 1)
        
        strike_y = self.height - 120
        draw_neon_line(surface, (track_x + 10, strike_y), (track_x + track_w - 10, strike_y), CYAN, 4, 6)
        
        if self.rhythm_engine_p1:
            notes = self.rhythm_engine_p1.notes
            for note in notes:
                if note.visual_y > 0 and not note.hit and not note.missed:
                    color = CYAN if note.column == 0 else PINK
                    circle_x = track_x + (track_w // 4) * (1 if note.column == 0 else 3)
                    circle_y = track_y + note.visual_y
                    
                    if circle_y < (track_y + track_h):
                        draw_neon_circle(surface, (int(circle_x), int(circle_y)), 18, color, width=0, glow_radius=5)
                        pygame.draw.circle(surface, WHITE, (int(circle_x), int(circle_y)), 6)
                        
        hud_card = pygame.Rect(track_x, 70, track_w, 130)
        pygame.draw.rect(surface, (12, 12, 28), hud_card, border_radius=12)
        draw_neon_rect(surface, hud_card, PURPLE, 2, border_radius=12, glow_radius=2)
        
        score = self.score_p1.score if self.score_p1 else 0
        combo = self.score_p1.combo if self.score_p1 else 0
        mult = self.score_p1.multiplier if self.score_p1 else 1
        acc = self.score_p1.get_accuracy() if self.score_p1 else 100.0
        
        draw_neon_text(surface, f"SCORE: {score:06d}", self.font_hud, (hud_card.centerx, hud_card.y + 25), WHITE, 2)
        draw_neon_text(surface, f"COMBO: {combo} (x{mult})", self.font_hud, (hud_card.centerx - 80, hud_card.y + 60), CYAN, 1)
        draw_neon_text(surface, f"ACCURACY: {acc:.1f}%", self.font_hud, (hud_card.centerx + 80, hud_card.y + 60), PINK, 1)
        
        energy = self.score_p1.energy if self.score_p1 else 100.0
        e_color = GREEN if energy > 40.0 else (YELLOW if energy > 15.0 else RED)
        bar_w = 340
        pygame.draw.rect(surface, DARK_GRAY, (hud_card.x + 30, hud_card.y + 90, bar_w, 12), border_radius=6)
        pygame.draw.rect(surface, e_color, (hud_card.x + 30, hud_card.y + 90, int(bar_w * (energy / 100.0)), 12), border_radius=6)
        
        coach_rect = pygame.Rect(cam_x, self.height - 85, cam_w, 60)
        pygame.draw.rect(surface, (12, 12, 28), coach_rect, border_radius=8)
        draw_neon_rect(surface, coach_rect, CYAN, width=1, border_radius=8, glow_radius=2)
        
        if self.p1_detector and self.coach_p1:
            feedback_txt, feedback_col = self.coach_p1.get_realtime_hud_coaching(
                self.p1_detector.squat_state,
                self.p1_detector.knee_angle,
                self.p1_detector.back_angle
            )
            lbl_tag = self.font_small.render("AI POSTURE COACH:", True, GRAY)
            surface.blit(lbl_tag, (coach_rect.x + 20, coach_rect.y + 12))
            draw_neon_text(surface, feedback_txt, self.font_header, (coach_rect.centerx, coach_rect.y + 35), feedback_col, glow_radius=4)

    def _draw_multiplayer_gameplay(self, surface):
        """Splits screen vertically into dual camera, dynamic note- highway corridors."""
        half_w = self.width // 2
        draw_neon_line(surface, (half_w, 40), (half_w, self.height), PURPLE, 3, 5)
        self._draw_multiplayer_lane(surface, 0, 0, half_w)
        self._draw_multiplayer_lane(surface, 1, half_w, half_w)

    def _draw_multiplayer_lane(self, surface, p_idx, start_x, width):
        """Draws player panel configurations for split screen lanes."""
        p_detector = self.p1_detector if p_idx == 0 else self.p2_detector
        p_score = self.score_p1 if p_idx == 0 else self.score_p2
        p_coach = self.coach_p1 if p_idx == 0 else self.coach_p2
        p_rhythm = self.rhythm_engine_p1 if p_idx == 0 else self.rhythm_engine_p2
        
        cam_w, cam_h = 320, 240
        cam_x = start_x + 20
        cam_y = 60
        
        cam_rect = pygame.Rect(cam_x, cam_y, cam_w, cam_h)
        pygame.draw.rect(surface, (15, 15, 25), cam_rect, border_radius=8)
        draw_neon_rect(surface, cam_rect, CYAN if p_idx == 0 else PINK, width=2, border_radius=8, glow_radius=2)
        
        if p_detector:
            raw_f, ann_f = p_detector.get_latest_frame()
            if ann_f is not None:
                ann_pyg = cv2.resize(ann_f, (cam_w, cam_h))
                ann_pyg = cv2.cvtColor(ann_pyg, cv2.COLOR_BGR2RGB)
                ann_surf = pygame.surfarray.make_surface(ann_pyg.swapaxes(0, 1))
                surface.blit(ann_surf, (cam_x, cam_y))
                
        score = p_score.score if p_score else 0
        combo = p_score.combo if p_score else 0
        energy = p_score.energy if p_score else 100.0
        
        lbl_p_name = self.font_hud.render(f"P{p_idx+1} SCORE: {score}", True, WHITE)
        surface.blit(lbl_p_name, (cam_x, cam_y + cam_h + 15))
        
        lbl_p_combo = self.font_hud.render(f"COMBO: {combo}", True, CYAN if p_idx == 0 else PINK)
        surface.blit(lbl_p_combo, (cam_x + 190, cam_y + cam_h + 15))
        
        e_color = GREEN if energy > 40.0 else (YELLOW if energy > 15.0 else RED)
        pygame.draw.rect(surface, DARK_GRAY, (cam_x, cam_y + cam_h + 45, cam_w, 8), border_radius=4)
        pygame.draw.rect(surface, e_color, (cam_x, cam_y + cam_h + 45, int(cam_w * (energy / 100.0)), 8), border_radius=4)
        
        track_w = 200
        track_x = start_x + width - track_w - 20
        track_y = 60
        track_h = self.height - 160
        
        track_rect = pygame.Rect(track_x, track_y, track_w, track_h)
        pygame.draw.rect(surface, (8, 8, 16), track_rect, border_radius=8)
        draw_neon_rect(surface, track_rect, PURPLE, width=1, border_radius=8, glow_radius=2)
        
        strike_y = self.height - 120
        draw_neon_line(surface, (track_x + 5, strike_y), (track_x + track_w - 5, strike_y), CYAN if p_idx == 0 else PINK, 3, 5)
        
        if p_rhythm:
            for note in p_rhythm.notes:
                if note.visual_y > 0 and not note.hit and not note.missed:
                    circle_x = track_x + (track_w // 4) * (1 if note.column == 0 else 3)
                    circle_y = track_y + note.visual_y
                    
                    if circle_y < (track_y + track_h):
                        color = CYAN if p_idx == 0 else PINK
                        draw_neon_circle(surface, (int(circle_x), int(circle_y)), 15, color, 0, 4)
                        pygame.draw.circle(surface, WHITE, (int(circle_x), int(circle_y)), 5)
                        
        coach_rect = pygame.Rect(cam_x, self.height - 85, cam_w, 55)
        pygame.draw.rect(surface, (12, 12, 28), coach_rect, border_radius=6)
        draw_neon_rect(surface, coach_rect, CYAN if p_idx == 0 else PINK, 1, border_radius=6, glow_radius=1)
        
        if p_detector and p_coach:
            feedback_txt, feedback_col = p_coach.get_realtime_hud_coaching(
                p_detector.squat_state,
                p_detector.knee_angle,
                p_detector.back_angle
            )
            draw_neon_text(surface, feedback_txt, self.font_hud, coach_rect.center, feedback_col, glow_radius=3)

    def _draw_results(self, surface):
        """Displays biomechanics stats card + high score analytics graph."""
        draw_neon_text(surface, "WORKOUT SESSION RESULTS", self.font_title, (self.width // 2, 70), CYAN, 5)
        
        card_w = 480
        card_x = 40
        card_y = 150
        card_h = self.height - 230
        
        stats_card = pygame.Rect(card_x, card_y, card_w, card_h)
        pygame.draw.rect(surface, (12, 12, 28), stats_card, border_radius=12)
        draw_neon_rect(surface, stats_card, PURPLE, width=2, border_radius=12, glow_radius=4)
        
        score = self.score_p1.score if self.score_p1 else 0
        grade = self.score_p1.get_performance_grade() if self.score_p1 else "C"
        acc = self.score_p1.get_accuracy() if self.score_p1 else 100.0
        cal = self.score_p1.get_calories_burned_estimate(self.song_duration) if self.score_p1 else 0.0
        
        coach_data = self.coach_p1.get_final_analytics() if self.coach_p1 else {"overall_score": 100, "advice": ""}
        posture = coach_data["overall_score"]
        advice = coach_data["advice"]
        
        draw_neon_text(surface, "RANK", self.font_hud, (card_x + 90, card_y + 40), GRAY, 0)
        draw_neon_text(surface, grade, pygame.font.SysFont("Consolas", 64, bold=True), (card_x + 90, card_y + 90), PINK, 8)
        
        lbl_x = card_x + 190
        lbl_y = card_y + 35
        dy = 28
        
        def draw_stat(lbl, val, col=WHITE):
            nonlocal lbl_y
            surface.blit(self.font_small.render(lbl, True, GRAY), (lbl_x, lbl_y))
            surface.blit(self.font_hud.render(str(val), True, col), (lbl_x + 130, lbl_y - 4))
            lbl_y += dy
            
        draw_stat("FINAL SCORE:", f"{score}", WHITE)
        draw_stat("ACCURACY:", f"{acc:.1f}%", CYAN)
        draw_stat("POSTURE:", f"{posture}%", GREEN if posture > 75 else RED)
        draw_stat("CALORIES:", f"{cal:.1f} kcal", PINK)
        
        draw_neon_line(surface, (card_x + 20, card_y + 160), (card_x + card_w - 20, card_y + 160), DARK_GRAY, 1, 1)
        
        if self.score_p1 and self.coach_p1:
            squat_y = card_y + 180
            surface.blit(self.font_small.render("PERFECT DEPTH SQUATS:", True, GRAY), (card_x + 40, squat_y))
            surface.blit(self.font_hud.render(f"{self.coach_p1.perfect_form_count}", True, GREEN), (card_x + 280, squat_y - 4))
            squat_y += 30
            surface.blit(self.font_small.render("SHALLOW SQUATS LOGGED:", True, GRAY), (card_x + 40, squat_y))
            surface.blit(self.font_hud.render(f"{self.coach_p1.shallow_count}", True, RED), (card_x + 280, squat_y - 4))
            squat_y += 30
            surface.blit(self.font_small.render("BACK TILT WARNINGS:", True, GRAY), (card_x + 40, squat_y))
            surface.blit(self.font_hud.render(f"{self.coach_p1.bad_posture_count}", True, YELLOW), (card_x + 280, squat_y - 4))
            
        advice_box = pygame.Rect(card_x + 20, card_y + card_h - 100, card_w - 40, 80)
        pygame.draw.rect(surface, (18, 18, 35), advice_box, border_radius=6)
        
        words = advice.split()
        lines = []
        current_line = []
        for w in words:
            current_line.append(w)
            test_line = " ".join(current_line)
            if self.font_small.size(test_line)[0] > (advice_box.width - 20):
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [w]
        lines.append(" ".join(current_line))
        
        line_y = advice_box.y + 10
        for line in lines[:3]:
            surface.blit(self.font_small.render(line, True, CYAN), (advice_box.x + 10, line_y))
            line_y += 18

        graph_w = self.width - card_w - 120
        graph_x = card_x + card_w + 40
        graph_rect = pygame.Rect(graph_x, card_y, graph_w, card_h)
        
        self.analytics.draw_telemetry_graph(surface, graph_rect, self.depth_history_p1)
        
        lbl_exit = self.font_hud.render("PRESS [ENTER/SPACE/ESC] TO RETURN TO LOBBY", True, WHITE)
        surface.blit(lbl_exit, (self.width // 2 - lbl_exit.get_width() // 2, self.height - 60))

    def _draw_leaderboard(self, surface):
        """Displays arcade persistent leaderboards."""
        draw_neon_text(surface, "SYSTEM ARCADE LEADERBOARD", self.font_title, (self.width // 2, 85), CYAN, 5)
        
        panel_w = 700
        panel_h = 320
        panel_x = self.width // 2 - panel_w // 2
        panel_y = 160
        
        board_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(surface, (12, 12, 28), board_rect, border_radius=12)
        draw_neon_rect(surface, board_rect, PURPLE, 2, border_radius=12, glow_radius=3)
        
        lbl_rank = self.font_hud.render("RANK", True, PINK)
        lbl_name = self.font_hud.render("PLAYER", True, WHITE)
        lbl_song = self.font_hud.render("TRACK", True, WHITE)
        lbl_score = self.font_hud.render("SCORE", True, CYAN)
        lbl_grade = self.font_hud.render("GRADE", True, WHITE)
        
        surface.blit(lbl_rank, (panel_x + 30, panel_y + 20))
        surface.blit(lbl_name, (panel_x + 110, panel_y + 20))
        surface.blit(lbl_song, (panel_x + 280, panel_y + 20))
        surface.blit(lbl_score, (panel_x + 500, panel_y + 20))
        surface.blit(lbl_grade, (panel_x + 620, panel_y + 20))
        
        draw_neon_line(surface, (panel_x + 20, panel_y + 45), (panel_x + panel_w - 20, panel_y + 45), DARK_GRAY, 1, 1)
        
        records = self.analytics.records[:7]
        line_y = panel_y + 60
        
        if not records:
            lbl_empty = self.font_hud.render("NO RECORDS FOUND. BE THE FIRST!", True, GRAY)
            surface.blit(lbl_empty, (panel_x + panel_w//2 - lbl_empty.get_width()//2, panel_y + 150))
        else:
            for idx, r in enumerate(records):
                rank_col = PINK if idx == 0 else (CYAN if idx == 1 else (PURPLE if idx == 2 else WHITE))
                
                txt_rank = self.font_hud.render(f"#{idx+1}", True, rank_col)
                txt_name = self.font_hud.render(r.get("player_name", "UNKNOWN"), True, WHITE)
                s_name = r.get("song_name", "TRACK")
                if len(s_name) > 16: s_name = s_name[:14] + ".."
                txt_song = self.font_hud.render(s_name, True, GRAY)
                txt_score = self.font_hud.render(f"{r.get('score', 0):,}", True, CYAN)
                txt_grade = self.font_hud.render(r.get("grade", "C"), True, GREEN if r.get("grade") in ["S","A"] else YELLOW)
                
                surface.blit(txt_rank, (panel_x + 35, line_y))
                surface.blit(txt_name, (panel_x + 110, line_y))
                surface.blit(txt_song, (panel_x + 280, line_y))
                surface.blit(txt_score, (panel_x + 500, line_y))
                surface.blit(txt_grade, (panel_x + 630, line_y))
                
                line_y += 34
                
        lbl_exit = self.font_hud.render("PRESS [ESC] TO LOBBY", True, WHITE)
        surface.blit(lbl_exit, (self.width // 2 - lbl_exit.get_width() // 2, self.height - 60))
