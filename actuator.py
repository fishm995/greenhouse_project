# actuator.py

import time  # Import the time module to allow for delays (e.g., using time.sleep)

class Actuator:
    """
    A class to control an actuator (such as a light or pump) using a Raspberry Pi's GPIO pins.

    This class supports two modes of operation:
      - Simulation mode (simulate=True): Instead of controlling real hardware,
        the actions are printed to the console. This is useful for testing.
      - Real mode (simulate=False): Uses the RPi.GPIO library to control actual hardware
        connected to the Raspberry Pi.

    Parameters:
      - pin (int): The GPIO pin number on the Raspberry Pi that controls this actuator.
      - name (str): A human-readable name for the actuator (e.g., "Light" or "Pump").
      - simulate (bool): A flag to determine if the actuator should run in simulation mode.
                         If True, only messages are printed; if False, actual GPIO operations are performed.
    """
    
    def __init__(self, pin, name="Actuator", simulate=True):
        # Save the provided GPIO pin, actuator name, and simulation flag as instance variables.
        self.pin = pin
        self.name = name
        self.simulate = simulate
        
        # Check if the actuator should run in real mode (simulate=False).
        if not self.simulate:
            # Import the RPi.GPIO module to control GPIO pins.
            import RPi.GPIO as GPIO
            self.GPIO = GPIO  # Save the imported module to use its functions later.
            # Set the pin numbering mode to BCM (Broadcom chip-specific numbering).
            self.GPIO.setmode(GPIO.BCM)
            # Disable warnings
            self.GPIO.setwarnings(False)
            # Configure the specified pin as an output pin.
            self.GPIO.setup(self.pin, GPIO.OUT)
            # Set the output on the pin to LOW to ensure the actuator starts in the OFF state.
            self.GPIO.output(self.pin, self.GPIO.LOW)

    def turn_on(self):
        """
        Turn the actuator on.
        
        In simulation mode, this function prints a message to the console.
        In real mode, it sets the GPIO pin to HIGH (i.e., supplies voltage) to turn the actuator on.
        """
        if self.simulate:
            # In simulation mode, print a message indicating that the actuator has been turned on.
            print(f"{self.name} on pin {self.pin} turned ON.")
        else:
            # In real mode, set the GPIO pin to HIGH to turn the actuator on.
            self.GPIO.output(self.pin, self.GPIO.HIGH)
            print(f"{self.name} on pin {self.pin} turned ON (GPIO).")

    def turn_off(self):
        """
        Turn the actuator off.
        
        In simulation mode, this function prints a message to the console.
        In real mode, it sets the GPIO pin to LOW (i.e., no voltage) to turn the actuator off.
        """
        if self.simulate:
            # In simulation mode, print a message indicating that the actuator has been turned off.
            print(f"{self.name} on pin {self.pin} turned OFF.")
        else:
            # In real mode, set the GPIO pin to LOW to turn the actuator off.
            self.GPIO.output(self.pin, self.GPIO.LOW)
            print(f"{self.name} on pin {self.pin} turned OFF (GPIO).")

    def cleanup(self):
        """
        Clean up GPIO settings.
        
        In simulation mode, this function simply prints a message.
        In real mode, it calls the GPIO.cleanup() method to reset the GPIO pins,
        which is important to avoid issues on subsequent runs.
        """
        if self.simulate:
            # Print a message in simulation mode.
            print("Cleanup called (simulation mode).")
        else:
            # In real mode, call the cleanup function to free the GPIO resources.
            self.GPIO.cleanup()

# The following block of code will only run when this script is executed directly.
# It is not executed if the module is imported elsewhere.
if __name__ == "__main__":
    # Create an instance of Actuator for testing.
    # Here, we simulate an actuator (for example, a light) connected to GPIO pin 18.
    light = Actuator(pin=18, name="Light", simulate=True)
    
    try:
        # Call the turn_on() method to simulate turning the light on.
        light.turn_on()
        # Wait for 2 seconds to simulate the light being on.
        time.sleep(2)
        # Call the turn_off() method to simulate turning the light off.
        light.turn_off()
    finally:
        # Call cleanup() to ensure that any resources (e.g., GPIO pins) are properly released.
        light.cleanup()
