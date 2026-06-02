import os
import json
import time
import pygame

# Try importing librosa for advanced analysis of user uploads, but support clean fallback
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

class RhythmNote:
    def __init__(self, target_time, column=0):
        self.target_time = target_time  # Song time (seconds) when note crosses strike line
        self.column = column            # Note track/column
        self.hit = False
        self.missed = False
        self.visual_y = 0.0

    def update(self, current_time, strike_y, travel_time, track_height):
        """
        Calculates position based on scroll speed.
        Travel time is the seconds a note takes to go from spawn (top) to strike line (bottom).
        """
        time_remaining = self.target_time - current_time
        
        # If note is too far in future, keep it at top (off-screen)
        if time_remaining > travel_time:
            self.visual_y = 0.0
            return
            
        # Linear interpolation from top (0) to strike line (strike_y)
        progress = 1.0 - (time_remaining / travel_time)
        self.visual_y = progress * strike_y
        
        # Mark as missed if it has passed the strike window without being hit
        # Strike window miss threshold is 0.28 seconds
        if time_remaining < -0.28 and not self.hit and not self.missed:
            self.missed = True

class RhythmEngine:
    def __init__(self, difficulty="Medium"):
        self.difficulty = difficulty
        self.current_song_path = None
        self.bpm = 120
        self.beats = []            # List of beat timestamps in seconds
        self.notes = []            # List of active RhythmNote objects
        
        # Configurable scroll and timing settings based on difficulty
        self.set_difficulty(difficulty)

    def set_difficulty(self, difficulty):
        self.difficulty = difficulty
        if difficulty == "Easy":
            self.travel_time = 2.0     # Slow, easy to react
            self.perfect_window = 0.16 # Very generous (±160ms)
            self.good_window = 0.32    # Generous (±320ms)
        elif difficulty == "Hard":
            self.travel_time = 0.9     # Extremely fast speed
            self.perfect_window = 0.09 # Strict (±90ms)
            self.good_window = 0.18    # Tight (±180ms)
        else: # Medium
            self.travel_time = 1.4     # Balanced
            self.perfect_window = 0.12 # Standard (±120ms)
            self.good_window = 0.24    # Standard (±240ms)

    def load_song(self, song_path, default_bpm=120):
        """Loads a song and parses beat markers with multi-layered fallbacks."""
        self.current_song_path = song_path
        self.notes.clear()
        
        # Look for pre-analyzed JSON metadata first
        json_path = song_path.replace('.wav', '.json').replace('.mp3', '.json')
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    self.bpm = data.get("bpm", default_bpm)
                    self.beats = data.get("beats", [])
                    print(f"[RhythmEngine] Loaded pre-cached beats from JSON: {len(self.beats)} beats.")
                    self._generate_notes()
                    return
            except Exception as e:
                print(f"[RhythmEngine] Warning: Failed to load JSON cache: {e}")

        # Fallback 1: Run librosa beat detection if installed
        if LIBROSA_AVAILABLE:
            try:
                print(f"[RhythmEngine] Analyzing {song_path} using Librosa. Please wait...")
                y, sr = librosa.load(song_path, sr=22050)
                tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
                self.bpm = float(tempo)
                self.beats = librosa.frames_to_time(beat_frames, sr=sr).tolist()
                print(f"[RhythmEngine] Librosa analysis complete: {len(self.beats)} beats found.")
                
                # Cache the results for instant subsequent loads
                try:
                    with open(json_path, 'w') as f:
                        json.dump({"song_name": os.path.basename(song_path), "bpm": self.bpm, "beats": self.beats}, f, indent=4)
                except Exception as ex:
                    print(f"[RhythmEngine] Could not write JSON cache: {ex}")
                    
                self._generate_notes()
                return
            except Exception as e:
                print(f"[RhythmEngine] Librosa analysis failed: {e}. Falling back to mathematical mapping.")
                
        # Fallback 2: Mathematical beat mapping based on length & BPM
        # Perfect fallback if librosa/ffmpeg fails
        print(f"[RhythmEngine] Performing mathematical beat generation for {default_bpm} BPM.")
        self.bpm = default_bpm
        beat_interval = 60.0 / default_bpm
        
        # Estimate song duration (typically 60s for our synthesized tracks, fallback to 180s)
        duration = 180.0
        if pygame.mixer.get_init():
            try:
                sound = pygame.mixer.Sound(song_path)
                duration = sound.get_length()
            except Exception:
                pass
                
        self.beats = []
        t = 1.0 # start after 1 second countdown
        while t < (duration - 1.0):
            self.beats.append(t)
            t += beat_interval
            
        self._generate_notes()

    def _generate_notes(self):
        """Spawns game notes based on beat timestamps."""
        self.notes = []
        for beat in self.beats:
            # We can alternate columns for visual spice, or keep single column
            # In a fitness game, single target is usually clearer, but let's support column indexing
            col = len(self.notes) % 2
            self.notes.append(RhythmNote(beat, col))

    def update(self, current_time, strike_y, track_height):
        """Updates positions of all active rhythm notes."""
        for note in self.notes:
            note.update(current_time, strike_y, self.travel_time, track_height)

    def check_hit(self, current_time):
        """
        Called when a player completes a squat.
        Checks if any active note is within a hit timing window.
        Returns (result_string, score_bonus, time_diff) or (None, 0, 0)
        """
        best_note = None
        min_diff = 999.0
        
        # Find the closest unhit note
        for note in self.notes:
            if note.hit or note.missed:
                continue
                
            diff = note.target_time - current_time
            abs_diff = abs(diff)
            
            if abs_diff < min_diff:
                min_diff = abs_diff
                best_note = note
                
        if best_note is not None:
            # If the closest note is within good threshold
            if min_diff <= self.perfect_window:
                best_note.hit = True
                return "PERFECT", 1000, min_diff
            elif min_diff <= self.good_window:
                best_note.hit = True
                return "GOOD", 500, min_diff
            elif min_diff <= 0.35: # Close miss window
                # Let's count a late/early squat as a miss
                pass
                
        return None, 0, 0.0

    def get_upcoming_notes(self, count=10):
        """Returns next count active/unhit notes."""
        upcoming = []
        for note in self.notes:
            if not note.hit and not note.missed:
                upcoming.append(note)
                if len(upcoming) >= count:
                    break
        return upcoming
