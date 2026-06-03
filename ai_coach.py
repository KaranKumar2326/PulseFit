import random

class AICoach:
    def __init__(self, exercise_type="SQUATS"):
        self.exercise_type = exercise_type
        # Live HUD text message
        self.hud_message = "READY TO SQUAT" if exercise_type == "SQUATS" else "READY SYSTEM"
        self.hud_color = (0, 240, 255) # Cyan
        
        # Telemetry aggregators
        self.total_squats = 0
        self.perfect_form_count = 0
        self.shallow_count = 0
        self.bad_posture_count = 0
        
        # Running sum for averaging
        self.depth_sum = 0.0
        self.back_angle_sum = 0.0
        
        # Motivational triggers
        self.perfect_phrases = [
            "FLAWLESS FORM!", 
            "DEEP SQUAT! NICE!", 
            "PERFECT ALIGNMENT!", 
            "BEAST MODE!", 
            "SOLID DEPTH!"
        ]

    def evaluate_squat(self, max_depth, avg_back_angle):
        """
        Called when a squat is completed.
        Evaluates the form and returns (feedback_text, form_score_0_to_100).
        """
        self.total_squats += 1
        self.depth_sum += max_depth
        self.back_angle_sum += avg_back_angle
        
        form_score = 100.0
        feedback = ""
        
        # 1. Evaluate depth (Knee angle at lowest point)
        # Deep squat is knee angle < 105 degrees.
        # Good squat is knee angle < 120 degrees.
        # Above 125 is too shallow.
        if max_depth > 125.0:
            form_score -= 30.0
            feedback = "SHALLOW SQUAT! GO LOWER"
            self.shallow_count += 1
            self.hud_color = (255, 30, 30) # Red
        elif max_depth < 105.0:
            form_score += 10.0 # depth bonus!
            feedback = random.choice(self.perfect_phrases)
            self.perfect_form_count += 1
            self.hud_color = (0, 255, 100) # Green
        else:
            feedback = "GOOD DEPTH! KEEP IT UP"
            self.perfect_form_count += 1
            self.hud_color = (0, 240, 255) # Cyan
            
        # 2. Evaluate Back Posture (shoulders tilt against vertical)
        # Leaning forward too much (> 28 degrees) causes lower back strain
        if avg_back_angle > 28.0:
            form_score -= 25.0
            feedback = "STRAIGHTEN BACK! chest up"
            self.bad_posture_count += 1
            self.hud_color = (255, 230, 0) # Yellow/Orange
            
        # Clamp form score between 0 and 100
        form_score = max(10.0, min(100.0, form_score))
        self.hud_message = feedback
        
        return feedback, form_score

    def evaluate_jumping_jack(self):
        """Evaluates a completed jumping jack rep."""
        self.total_squats += 1 # treat as total reps
        self.perfect_form_count += 1
        self.depth_sum += 100.0 # dummy value for average calculations
        
        self.hud_color = (0, 255, 100) # Green
        phrases = ["EXCELLENT JACK!", "SPEEDY TEMPO!", "STAY ACTIVE!", "POWERFUL JUMP!"]
        feedback = random.choice(phrases)
        self.hud_message = feedback
        return feedback, 100.0
        
    def evaluate_punch(self):
        """Evaluates a completed cyber punch rep."""
        self.total_squats += 1
        self.perfect_form_count += 1
        self.depth_sum += 100.0
        
        self.hud_color = (189, 0, 255) # Purple
        phrases = ["CRISP PUNCH!", "FAST EXTENSION!", "GUARD UP!", "CYBER STRIKE!"]
        feedback = random.choice(phrases)
        self.hud_message = feedback
        return feedback, 100.0

    def get_realtime_hud_coaching(self, current_state, knee_angle, back_angle):
        """Returns the appropriate string and color to display on the HUD during motion."""
        if self.exercise_type == "JUMPING_JACKS":
            # Realtime guide
            if current_state == "OPEN":
                return "HANDS UP!", (0, 255, 100)
            return self.hud_message, self.hud_color
        elif self.exercise_type == "CYBER_PUNCHES":
            return self.hud_message, self.hud_color
            
        # Provide real-time tips as the user is squatting down
        if current_state == "SQUATTING":
            if back_angle > 28.0:
                return "STRAIGHTEN BACK", (255, 30, 30)
            elif knee_angle > 130.0:
                return "GO LOWER...", (189, 0, 255)
            else:
                return "DEPTH GOOD!", (0, 255, 100)
                
        return self.hud_message, self.hud_color

    def get_final_analytics(self):
        """Generates a complete post-game analysis report."""
        if self.total_squats == 0:
            return {
                "overall_score": 100,
                "avg_depth": 180,
                "form_grade": "A+",
                "advice": "Start working out to see your fitness analytics!"
            }
            
        avg_depth = self.depth_sum / self.total_squats
        avg_back = self.back_angle_sum / self.total_squats
        
        # Calculate overall form percentage
        total_penalties = (self.shallow_count * 30.0) + (self.bad_posture_count * 25.0)
        overall_form = max(10.0, 100.0 - (total_penalties / self.total_squats))
        
        # Determine advice based on exercise type
        if self.exercise_type == "JUMPING_JACKS":
            advice = "ADVICE: Excellent jumping jacks! Focus on fully extending your arms above your head and spreading your feet wide on every rep to maximize calorie burn."
        elif self.exercise_type == "CYBER_PUNCHES":
            advice = "ADVICE: Great punches! Focus on full elbow extension and speed. Keep your shoulders relaxed and guard hands up to protect your face."
        else: # SQUATS
            if self.bad_posture_count / self.total_squats > 0.3:
                advice = "ADVICE: Focus on core stability. Keep your gaze forward and chest puffed out to prevent leaning too far forward."
            elif self.shallow_count / self.total_squats > 0.3:
                advice = "ADVICE: Work on hip mobility. Push your hips backward and down, trying to get your thighs parallel to the floor."
            else:
                advice = "ADVICE: Phenomenal form! Your back alignment and squat depth are excellent. Try a harder difficulty for a faster tempo!"
            
        return {
            "overall_score": int(overall_form),
            "avg_depth": int(avg_depth),
            "avg_back_angle": int(avg_back),
            "perfect_form_ratio": int((self.perfect_form_count / self.total_squats) * 100),
            "advice": advice
        }
