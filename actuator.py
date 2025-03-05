# actuator.py
import time  # Import the time module to allow for delays (e.g., sleep)

class Actuator:
    """
    A class to control an actuator (such as a light or pump) using a Raspberry Pi's GPIO pins.
    
    The actuator can work in two modes:
      - Simulation mode (simulate=True): Actions are printed to the console instead of actually controlling hardware.
      - Real mode (simulate=False): Uses the RPi.GPIO library to control real hardware.
    
    Parameters:
      - pin: The GPIO pin number on the Raspberry Pi that controls this actuator.
      - name: A human-readable name for the actuator (e.g., "Light" or "Pump").
      - simulate: A boolean flag. If True, the actuator only prints actions (simulation mode).
                  If False, it will perform real GPIO operations.
    """
    
    def __init__(self, pin, name="Actuator", simulate=True):
        # Save the provided pin number, name, and simulation flag in the object.
        self.pin = pin
        self.name = name
        self.simulate = simulate
        
        # If we are not in simulation mode, then we want to set up the GPIO for real hardware control.
        if not self.simulate:
            # Import the RPi.GPIO module, which provides access to the Raspberry Pi's GPIO pins.
            import RPi.GPIO as GPIO
            self.GPIO = GPIO  # Save the GPIO module reference for later use.
            self.GPIO.setmode(GPIO.BCM)  # Use the Broadcom chip-specific numbering for GPIO pins.
            self.GPIO.setup(self.pin, GPIO.OUT)  # Set the specified pin as an output.
            self.GPIO.output(self.pin, self.GPIO.LOW)  # Ensure the actuator is off initially.

    def turn_on(self):
        """Turn the actuator on."""
        if self.simulate:
            # In simulation mode, simply print a message indicating the actuator is turned on.
            print(f"{self.name} on pin {self.pin} turned ON.")
        else:
            # In real mode, set the GPIO output to HIGH (voltage on) to turn the actuator on.
            self.GPIO.output(self.pin, self.GPIO.HIGH)
            print(f"{self.name} on pin {self.pin} turned ON (GPIO).")

    def turn_off(self):
        """Turn the actuator off."""
        if self.simulate:
            # In simulation mode, simply print a message indicating the actuator is turned off.
            print(f"{self.name} on pin {self.pin} turned OFF.")
        else:
            # In real mode, set the GPIO output to LOW (voltage off) to turn the actuator off.
            self.GPIO.output(self.pin, self.GPIO.LOW)
            print(f"{self.name} on pin {self.pin} turned OFF (GPIO).")

    def cleanup(self):
        """Clean up GPIO settings."""
        if self.simulate:
            # In simulation mode, just print a message indicating cleanup is called.
            print("Cleanup called (simulation mode).")
        else:
            # In real mode, call the cleanup method to reset the GPIO pins.
            self.GPIO.cleanup()

# The following code will only run if this file is executed directly (not imported as a module).
if __name__ == "__main__":
    # Create an instance of Actuator for testing in simulation mode.
    # Here, we are simulating an actuator (for example, a light) on GPIO pin 18.
    light = Actuator(pin=18, name="Light", simulate=True)
    
    try:
        # Turn the light on.
        light.turn_on()
        # Wait for 2 seconds so you can see the "on" state.
        time.sleep(2)
        # Turn the light off.
        light.turn_off()
    finally:
        # Always call cleanup() to clean up the resources.
        light.cleanup()
