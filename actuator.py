# actuator.py
#import RPi.GPIO as GPIO
import time

class Actuator:
    """
    A class to control an actuator (e.g., a light or pump) using the Raspberry Pi's GPIO pins.
    """
    def __init__(self, pin, name="Actuator"):
        self.pin = pin
        self.name = name
      #  GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
      #  GPIO.setup(self.pin, GPIO.OUT)
      #  GPIO.output(self.pin, GPIO.LOW)  # Ensure the actuator is off by default

    def turn_on(self):
        """Turn the actuator on."""
        #GPIO.output(self.pin, GPIO.HIGH)
        print(f"{self.name} on pin {self.pin} turned ON.")

    def turn_off(self):
        """Turn the actuator off."""
      #  GPIO.output(self.pin, GPIO.LOW)
        print(f"{self.name} on pin {self.pin} turned OFF.")

    def cleanup(self):
        """Clean up GPIO settings."""
       # GPIO.cleanup()

if __name__ == "__main__":
    light = Actuator(pin=18, name="Light")
    try:
        light.turn_on()
        time.sleep(2)
        light.turn_off()
    finally:
        light.cleanup()
