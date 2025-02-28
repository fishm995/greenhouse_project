# actuator.py
import time

class Actuator:
    """
    A class to control an actuator (e.g., a light or pump) using the Raspberry Pi's GPIO pins.
    
    Parameters:
      - pin: The GPIO pin number to control.
      - name: A human-readable name for the actuator.
      - simulate: If True, the actuator will only print actions to the console (default).
                  Set to False to enable actual GPIO control.
    """
    def __init__(self, pin, name="Actuator", simulate=True):
        self.pin = pin
        self.name = name
        self.simulate = simulate
        
        if not self.simulate:
            # If not simulating, initialize GPIO.
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            self.GPIO.setmode(GPIO.BCM)  # Use BCM numbering
            self.GPIO.setup(self.pin, GPIO.OUT)
            self.GPIO.output(self.pin, self.GPIO.LOW)  # Ensure the actuator is off by default

    def turn_on(self):
        """Turn the actuator on."""
        if self.simulate:
            print(f"{self.name} on pin {self.pin} turned ON.")
        else:
            self.GPIO.output(self.pin, self.GPIO.HIGH)
            print(f"{self.name} on pin {self.pin} turned ON (GPIO).")

    def turn_off(self):
        """Turn the actuator off."""
        if self.simulate:
            print(f"{self.name} on pin {self.pin} turned OFF.")
        else:
            self.GPIO.output(self.pin, self.GPIO.LOW)
            print(f"{self.name} on pin {self.pin} turned OFF (GPIO).")

    def cleanup(self):
        """Clean up GPIO settings."""
        if self.simulate:
            print("Cleanup called (simulation mode).")
        else:
            self.GPIO.cleanup()

if __name__ == "__main__":
    # Example usage in simulation mode:
    light = Actuator(pin=18, name="Light", simulate=True)
    try:
        light.turn_on()
        time.sleep(2)
        light.turn_off()
    finally:
        light.cleanup()
