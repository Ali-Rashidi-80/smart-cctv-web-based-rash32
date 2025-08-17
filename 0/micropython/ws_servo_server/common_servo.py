"""
Common ServoController module for MicroPython
Eliminates duplicate code across multiple files
"""

from machine import Pin, PWM
from time import sleep
import ujson
import math
import asyncio

class ServoController:
    """
    Unified ServoController class for all MicroPython applications
    Handles servo control with angle persistence and smooth movement
    """
    
    def __init__(self, pin_num, angle_file):
        """
        Initialize servo controller with pin and angle file for persistence
        
        Args:
            pin_num (int): GPIO pin number for servo control
            angle_file (str): File path to store current angle
        """
        self.angle_file = angle_file
        self.servo_pwm = PWM(Pin(pin_num))
        self.servo_pwm.freq(50)  # Standard servo frequency (50 Hz)
        self.current_angle = self.load_angle()
        self.set_angle_immediate(self.current_angle)
    
    def save_angle(self, angle):
        """
        Save current angle to file for persistence across restarts
        
        Args:
            angle (int): Angle to save (0-180 degrees)
        """
        try:
            with open(self.angle_file, "w") as f:
                ujson.dump({"angle": angle}, f)
        except Exception as e:
            print("⚠️ خطا در ذخیره زاویه:", e)
    
    def load_angle(self):
        """
        Load saved angle from file
        
        Returns:
            int: Saved angle or default 90 degrees
        """
        try:
            with open(self.angle_file, "r") as f:
                data = ujson.load(f)
                angle = data.get("angle", 90)
                return max(0, min(180, angle))
        except Exception as e:
            print("⚠️ خطا در بازیابی زاویه. استفاده از مقدار پیش‌فرض 90 درجه:", e)
            return 90
    
    def angle_to_duty(self, angle):
        """
        Convert angle to PWM duty cycle
        
        Args:
            angle (int): Angle in degrees (0-180)
            
        Returns:
            int: PWM duty cycle value
        """
        MIN_DUTY = 1400
        MAX_DUTY = 3000
        return int(MIN_DUTY + (angle / 180) * (MAX_DUTY - MIN_DUTY))
    
    def set_angle_immediate(self, target_angle):
        """
        Set servo angle immediately without smooth movement
        
        Args:
            target_angle (int): Target angle in degrees
            
        Returns:
            int: Actual angle set
        """
        target_angle = max(0, min(180, target_angle))
        duty = self.angle_to_duty(target_angle)
        self.servo_pwm.duty_u16(duty)
        self.current_angle = target_angle
        return self.current_angle
    
    async def set_angle(self, current_angle, target_angle):
        """
        Set servo angle with smooth movement
        
        Args:
            current_angle (int): Current angle
            target_angle (int): Target angle
            
        Returns:
            int: Final angle achieved
        """
        target_angle = max(0, min(180, target_angle))
        
        if current_angle == target_angle:
            return current_angle
        
        # Calculate movement direction and steps
        angle_diff = target_angle - current_angle
        step_direction = 1 if angle_diff > 0 else -1
        steps = abs(angle_diff)
        
        # Smooth movement with configurable speed
        step_delay = 0.02  # 20ms per step for smooth movement
        
        for step in range(steps):
            new_angle = current_angle + (step + 1) * step_direction
            self.set_angle_immediate(new_angle)
            await asyncio.sleep(step_delay)
        
        # Save final angle
        self.save_angle(target_angle)
        return target_angle
    
    def cleanup(self):
        """
        Clean up PWM resources
        """
        try:
            self.servo_pwm.deinit()
        except Exception as e:
            print("⚠️ خطا در cleanup سروو:", e) 