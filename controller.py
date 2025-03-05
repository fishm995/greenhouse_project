# controller.py

"""
This module defines the SensorActuatorController class, which decides whether to turn an actuator
(on or off) based on a sensor reading, a defined threshold, and a hysteresis value. The class
implements different logic depending on whether the control logic is "below" or "above".

In "below" logic:
  - If the actuator is off and the sensor value is below (threshold - hysteresis), the actuator is turned on.
  - If the actuator is on and the sensor value is above (threshold + hysteresis), the actuator is turned off.

In "above" logic (the reverse):
  - If the actuator is off and the sensor value is above (threshold + hysteresis), the actuator is turned on.
  - If the actuator is on and the sensor value is below (threshold - hysteresis), the actuator is turned off.
  
The controller uses the sensor_value provided (read externally) to make its decision.
"""

class SensorActuatorController:
    def __init__(self, actuator, threshold, control_logic="below", hysteresis=0.5, initial_active=False):
        """
        Initialize the SensorActuatorController.

        Parameters:
          actuator (object): An instance that implements turn_on() and turn_off() methods.
          threshold (float): The numeric threshold value against which sensor readings are compared.
          control_logic (str): A string, either "below" or "above". Determines when to turn on the actuator.
          hysteresis (float): A tolerance value to prevent rapid toggling (default is 0.5).
          initial_active (bool): The starting state of the actuator (True if it is already on, False if off).
        """
        # Save the actuator instance and control parameters.
        self.actuator = actuator
        self.threshold = threshold
        self.control_logic = control_logic
        self.hysteresis = hysteresis
        # The active property holds the current on/off state of the actuator.
        self.active = initial_active

    def check_and_update(self, sensor_value):
        """
        Uses the provided sensor_value to determine whether the actuator should be toggled.
        The decision is based on the control_logic ("below" or "above") and the hysteresis value.

        Parameters:
          sensor_value (float): The sensor reading to evaluate.

        Behavior for "below" logic:
          - If the actuator is off and sensor_value is less than (threshold - hysteresis), turn it ON.
          - If the actuator is on and sensor_value is greater than (threshold + hysteresis), turn it OFF.
        
        Behavior for "above" logic:
          - If the actuator is off and sensor_value is greater than (threshold + hysteresis), turn it ON.
          - If the actuator is on and sensor_value is less than (threshold - hysteresis), turn it OFF.

        Returns:
          float: The sensor_value that was used for the decision (for logging or further processing).
        """
        # Print the current sensor value and controller settings for debugging purposes.
        print(f"[Controller] sensor_value={sensor_value}, threshold={self.threshold}, "
              f"hysteresis={self.hysteresis}, active={self.active}")

        if self.control_logic == "below":
            # For "below" logic: We want the actuator ON when sensor_value is very low.
            if not self.active and sensor_value < self.threshold - self.hysteresis:
                print(f"[Controller] Turning ON: {sensor_value} < {self.threshold - self.hysteresis}")
                self.actuator.turn_on()
                self.active = True
            elif self.active and sensor_value > self.threshold + self.hysteresis:
                print(f"[Controller] Turning OFF: {sensor_value} > {self.threshold + self.hysteresis}")
                self.actuator.turn_off()
                self.active = False
            else:
                print("[Controller] No change required for 'below' logic.")
        elif self.control_logic == "above":
            # For "above" logic: We want the actuator ON when sensor_value is very high.
            if not self.active and sensor_value > self.threshold + self.hysteresis:
                print(f"[Controller] Turning ON: {sensor_value} > {self.threshold + self.hysteresis}")
                self.actuator.turn_on()
                self.active = True
            elif self.active and sensor_value < self.threshold - self.hysteresis:
                print(f"[Controller] Turning OFF: {sensor_value} < {self.threshold - self.hysteresis}")
                self.actuator.turn_off()
                self.active = False
            else:
                print("[Controller] No change required for 'above' logic.")
        else:
            # If the control_logic is not recognized, print an error.
            print("[Controller] Invalid control_logic specified.")
