import os
import math
import wave
import struct
import json
import pygame
import random

# Cyberpunk Neon Color Palette
BLACK = (10, 10, 18)       # #0a0a12
CYAN = (0, 240, 255)       # #00f0ff
PURPLE = (189, 0, 255)     # #bd00ff
PINK = (255, 0, 127)       # #ff007f
WHITE = (255, 255, 255)
DARK_GRAY = (30, 30, 45)
GRAY = (120, 120, 135)
GREEN = (0, 255, 100)
YELLOW = (255, 230, 0)
RED = (255, 30, 30)

# Easing Functions
def ease_out_quad(t):
    return t * (2 - t)

def ease_in_out_quad(t):
    if t < 0.5:
        return 2 * t * t
    return -1 + (4 - 2 * t) * t

# Set up project directory structure
def init_directories():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dirs = ['songs', 'sounds', 'effects', 'ui', 'fonts']
    for d in dirs:
        os.makedirs(os.path.join(base_dir, d), exist_ok=True)
    return base_dir

# --- PROCEDURAL SYNTHESIZER ---
def save_wav_file(filename, samples, sample_rate=44100):
    """Saves a list of float samples (-1.0 to 1.0) into a 16-bit mono WAV file."""
    with wave.open(filename, 'w') as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        
        packed_samples = []
        for s in samples:
            # Clip sample to prevent overflow
            s = max(-1.0, min(1.0, s))
            # Convert to 16-bit integer
            val = int(s * 32767.0)
            packed_samples.append(struct.pack('<h', val))
            
        wav.writeframes(b''.join(packed_samples))

def synth_kick(sample_index, sample_rate, duration_samples):
    """Generates a pitch-sweeping sine wave representing a heavy kick drum."""
    t = sample_index / sample_rate
    # Fast pitch sweep from 150Hz down to 45Hz
    freq = 45 + (150 - 45) * math.exp(-t * 40)
    phase = 2 * math.pi * freq * t
    val = math.sin(phase)
    # Exponential decay
    decay = math.exp(-t * 12)
    return val * decay

def synth_snare(sample_index, sample_rate, duration_samples):
    """Generates bandpass-like filtered white noise representing a crisp snare."""
    t = sample_index / sample_rate
    # White noise sample
    noise = random.uniform(-1.0, 1.0)
    # Pitch component
    freq_phase = 2 * math.pi * 180 * t
    pitch = math.sin(freq_phase) * math.exp(-t * 20)
    
    val = (noise * 0.7 + pitch * 0.3)
    # Exponential decay
    decay = math.exp(-t * 8)
    return val * decay

def synth_bass(sample_index, sample_rate, note_freq, duration_samples):
    """Generates a retro cyberpunk sawtooth bass note with a filter envelope."""
    t = sample_index / sample_rate
    # Sawtooth wave approximation: t * freq - floor(t * freq)
    phase = t * note_freq
    saw = 2.0 * (phase - math.floor(phase + 0.5))
    
    # Filter envelope simulation (harmonic filtering)
    harmonics = 1.0
    val = saw
    # Add a second harmonic for richness
    phase2 = t * (note_freq * 2)
    saw2 = 2.0 * (phase2 - math.floor(phase2 + 0.5))
    val = (val + saw2 * 0.4 * math.exp(-t * 4))
    
    # Volume envelope
    decay = math.exp(-t * 3.5)
    return val * decay * 0.5

def generate_workout_track(filename, bpm, duration_seconds=60, song_name="Cyber Squat"):
    """
    Generates a full, professionally mixed techno workout track and caches beat times.
    This guarantees 100% accurate, high-fidelity audio beats out of the box!
    """
    sample_rate = 44100
    num_samples = int(duration_seconds * sample_rate)
    samples = [0.0] * num_samples
    
    # Beat parameters
    beat_interval = 60.0 / bpm
    samples_per_beat = int(beat_interval * sample_rate)
    
    # Music Theory setup: Cyberpunk style key of A minor (55Hz / A1 bass base)
    # Chord progression: Am -> F -> G -> Em
    chords = [
        [55.00, 110.00],  # Am (A1, A2)
        [43.65, 87.31],   # F (F1, F2)
        [49.00, 98.00],   # G (G1, G2)
        [41.20, 82.41]    # Em (E1, E2)
    ]
    
    beats = []
    
    # Pre-render patterns into samples array
    for i in range(num_samples):
        t = i / sample_rate
        beat_idx = int(t / beat_interval)
        beat_sample_offset = i % samples_per_beat
        
        # Calculate timestamps for JSON beat tracking (the exact strike moments)
        if beat_sample_offset == 0 and t < (duration_seconds - 1):
            beats.append(t)
            
        chord_cycle = int(beat_idx / 8) % len(chords)
        active_chord = chords[chord_cycle]
        
        # 1. KICK DRUM on every beat
        kick_val = synth_kick(beat_sample_offset, sample_rate, samples_per_beat)
        
        # 2. SNARE DRUM on beats 2 and 4 (standard backbeat)
        snare_val = 0.0
        if (beat_idx % 4) in [1, 3]:
            snare_val = synth_snare(beat_sample_offset, sample_rate, samples_per_beat)
            
        # 3. BASSLINE: Offbeat bouncing 16th notes / 8th notes (retro running bass)
        bass_val = 0.0
        sub_beat = int((t % beat_interval) / (beat_interval / 4)) # 4 divisions per beat
        
        # Bass pattern: Note plays on sub-beats 0, 2, 3 (cyberpunk groove)
        if sub_beat in [0, 2, 3]:
            sub_offset = i % int(samples_per_beat / 4)
            freq = active_chord[0] if sub_beat == 0 else active_chord[1]
            # Add octaves/harmonics variation
            bass_val = synth_bass(sub_offset, sample_rate, freq, samples_per_beat / 4)
            
        # 4. HIGH HAT: Crisp metallic noise on off-beats (sub-beat 2)
        hat_val = 0.0
        if sub_beat == 2:
            hat_offset = i % int(samples_per_beat / 4)
            hat_t = hat_offset / sample_rate
            hat_val = random.uniform(-1.0, 1.0) * math.exp(-hat_t * 80) * 0.15
            
        # Mix the layers
        samples[i] = (kick_val * 0.45 + snare_val * 0.25 + bass_val * 0.35 + hat_val * 0.1)
        
    # Apply fade-in and fade-out to prevent pops
    fade_len = int(sample_rate * 1.5)
    for i in range(fade_len):
        fade_in_factor = i / fade_len
        samples[i] *= fade_in_factor
        
        fade_out_factor = i / fade_len
        samples[num_samples - 1 - i] *= fade_out_factor
        
    # Save the WAV file
    save_wav_file(filename, samples, sample_rate)
    
    # Save the exact beats metadata to a JSON file alongside the WAV
    json_filename = filename.replace('.wav', '.json')
    song_metadata = {
        "song_name": song_name,
        "bpm": bpm,
        "duration": duration_seconds,
        "beats": beats
    }
    with open(json_filename, 'w') as f:
        json.dump(song_metadata, f, indent=4)
        
    print(f"Generated track: {song_name} ({bpm} BPM, {len(beats)} beats) saved to {filename}")
    return song_metadata

def generate_sfx():
    """Generates high-fidelity retro arcade neon sound effects."""
    base_dir = init_directories()
    sample_rate = 44100
    
    # 1. PERFECT SFX: Rising rapid laser arpeggio
    perfect_samples = []
    notes = [523.25, 659.25, 783.99, 1046.50] # C5, E5, G5, C6
    note_duration = 0.08
    for freq in notes:
        num_samples = int(note_duration * sample_rate)
        for i in range(num_samples):
            t = i / sample_rate
            val = math.sin(2 * math.pi * freq * t)
            # Add a slight second harmonic
            val = 0.7 * val + 0.3 * math.sin(4 * math.pi * freq * t)
            # Volume envelope
            decay = math.exp(-t * 20)
            perfect_samples.append(val * decay * 0.4)
    save_wav_file(os.path.join(base_dir, 'effects', 'perfect.wav'), perfect_samples)
    
    # 2. GOOD SFX: Quick retro ding
    good_samples = []
    duration = 0.25
    freq_start = 587.33 # D5
    freq_end = 880.00   # A5
    num_samples = int(duration * sample_rate)
    for i in range(num_samples):
        t = i / sample_rate
        # Linear frequency glide
        freq = freq_start + (freq_end - freq_start) * (i / num_samples)
        val = math.sin(2 * math.pi * freq * t)
        decay = math.exp(-t * 12)
        good_samples.append(val * decay * 0.3)
    save_wav_file(os.path.join(base_dir, 'effects', 'good.wav'), good_samples)
    
    # 3. MISS SFX: Low descending buzz
    miss_samples = []
    duration = 0.35
    freq_start = 130.0  # Low C3
    freq_end = 65.0     # Low C2
    num_samples = int(duration * sample_rate)
    for i in range(num_samples):
        t = i / sample_rate
        freq = freq_start + (freq_end - freq_start) * (i / num_samples)
        # Use a combination of square and sawtooth waves for buzz
        phase = t * freq
        saw = 2.0 * (phase - math.floor(phase + 0.5))
        sq = 0.4 if (phase % 1.0) < 0.5 else -0.4
        val = 0.6 * saw + 0.4 * sq
        decay = math.exp(-t * 6)
        miss_samples.append(val * decay * 0.35)
    save_wav_file(os.path.join(base_dir, 'effects', 'miss.wav'), miss_samples)

    # 4. HOVER/CLICK SFX: Short metallic chip beep
    click_samples = []
    duration = 0.05
    num_samples = int(duration * sample_rate)
    for i in range(num_samples):
        t = i / sample_rate
        val = math.sin(2 * math.pi * 1200 * t)
        decay = math.exp(-t * 90)
        click_samples.append(val * decay * 0.15)
    save_wav_file(os.path.join(base_dir, 'effects', 'click.wav'), click_samples)
    
    # 5. ROUND WIN/CHEER SFX: Rising arcade fan-fare
    win_samples = []
    win_notes = [523.25, 523.25, 523.25, 659.25, 783.99, 1046.50]
    win_durs = [0.1, 0.1, 0.1, 0.15, 0.15, 0.4]
    for freq, note_dur in zip(win_notes, win_durs):
        num_samples = int(note_dur * sample_rate)
        for i in range(num_samples):
            t = i / sample_rate
            val = math.sin(2 * math.pi * freq * t)
            # Add a slight triangle sound for brassiness
            triangle = 2.0 * abs(2.0 * (t * freq - math.floor(t * freq + 0.5))) - 1.0
            val = 0.5 * val + 0.5 * triangle
            decay = math.exp(-t * 8)
            win_samples.append(val * decay * 0.35)
    save_wav_file(os.path.join(base_dir, 'effects', 'win.wav'), win_samples)


# --- NEON RENDERING HELPERS ---
def draw_neon_line(surface, start_pos, end_pos, color, width=3, glow_radius=4):
    """Draws a line with a beautiful, glowing semi-transparent neon drop-shadow."""
    # Convert color to RGB if RGBA
    rgb = color[:3] if len(color) >= 3 else color
    
    # Draw glow layers
    for r in range(glow_radius, 0, -1):
        alpha = int((1.0 - (r / (glow_radius + 1))) * 70)
        glow_color = (rgb[0], rgb[1], rgb[2], alpha)
        
        # Create temporary surface with transparency
        temp_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.line(temp_surface, glow_color, start_pos, end_pos, width + r * 2)
        surface.blit(temp_surface, (0, 0))
        
    # Draw core bright line
    pygame.draw.line(surface, WHITE if rgb == CYAN else color, start_pos, end_pos, width)

def draw_neon_rect(surface, rect, color, width=2, glow_radius=5, border_radius=0):
    """Draws a beautiful neon-glowing rectangle with support for rounded borders."""
    rgb = color[:3] if len(color) >= 3 else color
    x, y, w, h = rect
    
    # Draw outer glow layers
    for r in range(glow_radius, 0, -1):
        alpha = int((1.0 - (r / (glow_radius + 1))) * 60)
        glow_color = (rgb[0], rgb[1], rgb[2], alpha)
        
        temp_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        # Expand rect bounds for glow
        glow_rect = (x - r, y - r, w + r * 2, h + r * 2)
        pygame.draw.rect(temp_surface, glow_color, glow_rect, width + r, border_radius=border_radius + r)
        surface.blit(temp_surface, (0, 0))
        
    # Draw central crisp line
    pygame.draw.rect(surface, color, rect, width, border_radius=border_radius)

def draw_neon_circle(surface, center, radius, color, width=0, glow_radius=6):
    """Draws a stunning glowing neon circle."""
    rgb = color[:3] if len(color) >= 3 else color
    cx, cy = center
    
    for r in range(glow_radius, 0, -1):
        alpha = int((1.0 - (r / (glow_radius + 1))) * 65)
        glow_color = (rgb[0], rgb[1], rgb[2], alpha)
        
        temp_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.circle(temp_surface, glow_color, center, radius + r, width + r)
        surface.blit(temp_surface, (0, 0))
        
    # Core circle
    pygame.draw.circle(surface, color, center, radius, width)

def draw_neon_text(surface, text, font, center_pos, color, glow_radius=4):
    """Renders text with a glowing retro drop-shadow centered at center_pos."""
    rgb = color[:3] if len(color) >= 3 else color
    
    # Render the core text surface
    text_core = font.render(text, True, WHITE)
    w, h = text_core.get_size()
    
    # Draw glow layers
    for r in range(glow_radius, 0, -1):
        alpha = int((1.0 - (r / (glow_radius + 1))) * 90)
        glow_color = (rgb[0], rgb[1], rgb[2], alpha)
        text_glow = font.render(text, True, glow_color)
        
        # Blit with small offsets in all 8 directions to simulate blur/glow
        for dx, dy in [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]:
            surface.blit(text_glow, (center_pos[0] - w//2 + dx*r*0.6, center_pos[1] - h//2 + dy*r*0.6))
            
    # Blit core crisp text on top
    surface.blit(text_core, (center_pos[0] - w//2, center_pos[1] - h//2))


# --- CYBERPUNK VECTOR PARTICLE SYSTEM ---
class Particle:
    def __init__(self, x, y, dx, dy, color, size, lifetime):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.color = color
        self.size = size
        self.initial_size = size
        self.lifetime = lifetime
        self.initial_lifetime = lifetime

    def update(self, dt):
        self.x += self.dx * dt * 60
        self.y += self.dy * dt * 60
        # Add friction
        self.dx *= 0.96
        self.dy *= 0.96
        # Add slight gravity
        self.dy += 0.1
        self.lifetime -= dt
        
        # Calculate current size decay
        progress = self.lifetime / self.initial_lifetime
        self.size = self.initial_size * progress

    def draw(self, surface):
        if self.lifetime <= 0 or self.size <= 0:
            return
        
        alpha = int((self.lifetime / self.initial_lifetime) * 255)
        # Create a surface with transparency for drawing the particle
        p_surf = pygame.Surface((int(self.size * 3), int(self.size * 3)), pygame.SRCALPHA)
        p_center = (int(self.size * 1.5), int(self.size * 1.5))
        
        # Draw particle core and soft glow
        p_color = (self.color[0], self.color[1], self.color[2], alpha)
        pygame.draw.circle(p_surf, p_color, p_center, int(self.size))
        pygame.draw.circle(p_surf, (self.color[0], self.color[1], self.color[2], int(alpha * 0.4)), p_center, int(self.size * 1.5))
        
        surface.blit(p_surf, (int(self.x - self.size * 1.5), int(self.y - self.size * 1.5)))

class ParticleSystem:
    def __init__(self):
        self.particles = []

    def spawn(self, x, y, color, count=15):
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(3, 8)
            dx = math.cos(angle) * speed
            dy = math.sin(angle) * speed - random.uniform(1, 4) # bias upward
            
            size = random.uniform(3, 8)
            lifetime = random.uniform(0.3, 0.8)
            
            self.particles.append(Particle(x, y, dx, dy, color, size, lifetime))

    def update(self, dt):
        for p in self.particles[:]:
            p.update(dt)
            if p.lifetime <= 0:
                self.particles.remove(p)

    def draw(self, surface):
        for p in self.particles:
            p.draw(surface)


# --- SOUND AND DIRECTORY SEEDING ON START ---
if __name__ == '__main__':
    # When run directly, generate everything for verification
    print("Seeding asset folders and generating synth sounds...")
    generate_sfx()
    
    base_dir = init_directories()
    generate_workout_track(os.path.join(base_dir, 'songs', 'easy_synth.wav'), bpm=110, duration_seconds=60, song_name="Cyber Pulse")
    generate_workout_track(os.path.join(base_dir, 'songs', 'medium_synth.wav'), bpm=125, duration_seconds=60, song_name="Retro Sprint")
    generate_workout_track(os.path.join(base_dir, 'songs', 'hard_synth.wav'), bpm=140, duration_seconds=60, song_name="Neon Arena")
    print("All synthesized assets successfully generated!")
