import sys
import os
import time

# Ensure current working directory is set to the application directory
# (supporting PyInstaller bundles as well as raw development execution)
if hasattr(sys, '_MEIPASS'):
    os.chdir(sys._MEIPASS)
else:
    project_dir = os.path.dirname(os.path.abspath(__file__))
    if project_dir:
        os.chdir(project_dir)

def check_dependencies():
    """Validates that pygame can be loaded, showing an instruction guide if it fails."""
    try:
        import pygame
        print("[System] Pygame loaded successfully.")
    except ImportError:
        print("\n" + "="*60)
        print("ERROR: Pygame is not installed or failed to compile in this environment.")
        print("Because your system is running an experimental Python version (Python 3.14),")
        print("you should try installing Pygame Community Edition, which has wider support:")
        print("    pip install pygame-ce")
        print("="*60 + "\n")
        sys.exit(1)

# Check imports before running Pygame window
check_dependencies()

import pygame
from game import PulseFitGame

def main():
    # 1. Initialize Pygame core and audio mixer
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception as e:
        print(f"[Main Setup] Warning: Audio mixer could not initialize: {e}")
        
    # 2. Configure screen display (1280x720 widescreen cyber layout)
    screen_width = 1280
    screen_height = 720
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("PULSEFIT ARENA — AI Cyber Rhythm Fitness")
    
    # 3. Create the game engine instance
    game = PulseFitGame(screen)
    print("[Main Setup] PulseFit Arena initialized. Launching game state loop...")
    
    # 4. Master gameplay loop
    last_time = time.time()
    clock = pygame.time.Clock()
    
    while game.running:
        # Calculate precise delta-time (dt) for frame-rate-independent movement
        current_time = time.time()
        dt = current_time - last_time
        last_time = current_time
        
        # Cap dt to avoid massive physics jumps during lag spikes
        dt = min(0.1, dt)
        
        # State updates and event polling
        game.handle_events()
        game.update(dt)
        
        # Render frame
        game.draw()
        
        # Lock frame rate at 60 FPS
        clock.tick(60)
        
    # 5. Graceful shutdown
    print("[Shutdown] Cleaning up game modules...")
    game.cleanup_gameplay()
    pygame.quit()
    print("[Shutdown] System exited cleanly. See you at the next workout!")

if __name__ == '__main__':
    main()
