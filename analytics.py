import os
import json
import datetime
from utils import draw_neon_line, draw_neon_text, CYAN, PURPLE, PINK, GRAY, DARK_GRAY

class AnalyticsManager:
    def __init__(self, filename="pulsefit_leaderboard.json"):
        self.filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        self.records = self._load_records()

    def _load_records(self):
        """Loads scores from the local JSON database."""
        if not os.path.exists(self.filename):
            return []
        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except Exception:
            return []

    def save_run(self, player_name, song_name, difficulty, score, accuracy, grade, calories, posture_score):
        """Saves a new workout session record and returns the updated leaderboard."""
        record = {
            "player_name": player_name,
            "song_name": song_name,
            "difficulty": difficulty,
            "score": score,
            "accuracy": round(accuracy, 1),
            "grade": grade,
            "calories": round(calories, 1),
            "posture_score": posture_score,
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        self.records.append(record)
        
        # Sort by score descending
        self.records = sorted(self.records, key=lambda x: x["score"], reverse=True)
        
        # Keep top 100
        self.records = self.records[:100]
        
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.records, f, indent=4)
        except Exception as e:
            print(f"[Analytics] Error saving record: {e}")
            
        return self.records

    def get_song_high_score(self, song_name, difficulty):
        """Returns the high score for a specific song and difficulty."""
        for r in self.records:
            if r["song_name"] == song_name and r["difficulty"] == difficulty:
                return r["score"]
        return 0

    def draw_telemetry_graph(self, surface, rect, depth_history):
        """
        Draws a high-tech glowing telemetry line graph inside the specified rectangle.
        Used on the results screen to plot the user's squat-depth performance over time!
        """
        x, y, w, h = rect
        
        # Draw background grid card
        import pygame
        pygame.draw.rect(surface, (15, 15, 25), rect, border_radius=8)
        pygame.draw.rect(surface, PURPLE, rect, 2, border_radius=8)
        
        # Draw grid lines
        grid_rows = 4
        grid_cols = 8
        for i in range(1, grid_rows):
            grid_y = y + (h // grid_rows) * i
            draw_neon_line(surface, (x + 5, grid_y), (x + w - 5, grid_y), DARK_GRAY, 1, 1)
            
        for i in range(1, grid_cols):
            grid_x = x + (w // grid_cols) * i
            draw_neon_line(surface, (grid_x, y + 5), (grid_x, y + h - 5), DARK_GRAY, 1, 1)
            
        # Draw Y-Axis labels (squat depth thresholds)
        font = pygame.font.SysFont("Consolas", 12)
        lbl_deep = font.render("DEEP SQUAT (90 deg)", True, CYAN)
        lbl_shallow = font.render("SHALLOW (130 deg)", True, PINK)
        surface.blit(lbl_deep, (x + 10, y + 10))
        surface.blit(lbl_shallow, (x + 10, y + h - 22))
        
        if not depth_history:
            # Draw no data message
            lbl_no_data = font.render("NO SQUAT DATA RECORDED", True, GRAY)
            surface.blit(lbl_no_data, (x + w//2 - lbl_no_data.get_width()//2, y + h//2))
            return
            
        # Draw data line
        # Map values from [80, 150] knee degrees to [h-10, 10] pixels
        points = []
        for idx, depth in enumerate(depth_history):
            # Calculate coordinates
            pt_x = x + 15 + ((w - 30) / max(1, len(depth_history) - 1)) * idx
            # Normalize depth between 80 (perfect deep squat) and 150 (very shallow squat)
            norm_depth = (depth - 80) / (150 - 80)
            norm_depth = max(0.0, min(1.0, norm_depth))
            pt_y = y + 15 + (h - 30) * norm_depth # 80 is at top, 150 at bottom of graph
            points.append((int(pt_x), int(pt_y)))
            
        # Draw connecting line segments
        if len(points) > 1:
            for idx in range(len(points) - 1):
                # Color changes dynamically depending on the depth achieved!
                depth_val = depth_history[idx]
                col = CYAN if depth_val < 110.0 else (PINK if depth_val > 130.0 else PURPLE)
                draw_neon_line(surface, points[idx], points[idx+1], col, 3, 3)
                
        # Draw data points as neon circles
        for idx, pt in enumerate(points):
            depth_val = depth_history[idx]
            col = CYAN if depth_val < 110.0 else (PINK if depth_val > 130.0 else PURPLE)
            pygame.draw.circle(surface, col, pt, 5)
            pygame.draw.circle(surface, (255, 255, 255), pt, 2)
            
        # Draw total squats counter
        lbl_total = font.render(f"Squats Logged: {len(depth_history)}", True, (255, 255, 255))
        surface.blit(lbl_total, (x + w - lbl_total.get_width() - 10, y + 10))
