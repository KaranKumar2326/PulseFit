class ScoringSystem:
    def __init__(self):
        # Primary Score Telemetry
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.multiplier = 1
        
        # Accuracy Counters
        self.perfect_count = 0
        self.good_count = 0
        self.miss_count = 0
        
        # Vitality (Energy Bar)
        self.energy = 100.0  # Percentage (0 - 100)
        self.is_failed = False

    def register_hit(self, timing_rating, form_score=100.0):
        """
        Calculates points awarded based on timing accuracy AND physical squat form.
        Form score represents posture quality from 0 to 100.
        """
        # Base Points
        if timing_rating == "PERFECT":
            base_points = 1000
            self.perfect_count += 1
            energy_gain = 6.0
        elif timing_rating == "GOOD":
            base_points = 500
            self.good_count += 1
            energy_gain = 3.0
        else:
            return 0
            
        # Combo management
        self.combo += 1
        if self.combo > self.max_combo:
            self.max_combo = self.combo
            
        # Update Multiplier
        if self.combo >= 20:
            self.multiplier = 4
        elif self.combo >= 10:
            self.multiplier = 3
        elif self.combo >= 5:
            self.multiplier = 2
        else:
            self.multiplier = 1
            
        # Biomechanical Multiplier: Reward deep squats and perfect back angles
        # If squat form is poor (e.g. 50%), points are scaled down slightly
        form_multiplier = 0.5 + (form_score / 200.0) # scales from 0.5 to 1.0
        
        # Final Score calculation
        added_score = int(base_points * self.multiplier * form_multiplier)
        self.score += added_score
        
        # Energy Recovery
        if not self.is_failed:
            self.energy = min(100.0, self.energy + energy_gain)
            
        return added_score

    def register_miss(self):
        """Fired when a note is missed or player fails to squat."""
        self.miss_count += 1
        self.combo = 0
        self.multiplier = 1
        
        # Energy Penalty
        if not self.is_failed:
            self.energy = max(0.0, self.energy - 10.0)
            if self.energy <= 0.0:
                self.is_failed = True # Energy depleted!
                
        return 0

    def get_accuracy(self):
        """Computes the overall accuracy percentage."""
        total_attempts = self.perfect_count + self.good_count + self.miss_count
        if total_attempts == 0:
            return 100.0
        return ((self.perfect_count + self.good_count) / total_attempts) * 100.0

    def get_performance_grade(self):
        """Returns standard gaming letter grades based on accuracy and combo performance."""
        acc = self.get_accuracy()
        if self.is_failed:
            return "F"
        if acc >= 96.0 and self.miss_count == 0:
            return "S" # Perfect run!
        elif acc >= 90.0:
            return "A"
        elif acc >= 78.0:
            return "B"
        elif acc >= 60.0:
            return "C"
        else:
            return "D"
            
    def get_calories_burned_estimate(self, duration_seconds=60):
        """
        Estimates calories burned using standard Metabolic Equivalent (MET) formulas
        for physical fitness squatting routines. MET for vigorous squats ~ 6.0
        """
        # Calories = MET * 3.5 * weight_kg / 200 * duration_minutes
        weight_kg = 75.0 # Average default weight
        duration_minutes = duration_seconds / 60.0
        
        # Active intensity depends on squat count and accuracy
        squats_completed = self.perfect_count + self.good_count
        intensity_modifier = min(1.5, max(0.5, squats_completed / 15.0))
        
        met = 6.0 * intensity_modifier
        calories = met * 3.5 * weight_kg / 200.0 * duration_minutes
        return calories
