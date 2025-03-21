# controller.py

"""
This module defines the SensorActuatorController class, which decides whether to
turn an actuator on or off based on a sensor reading, a defined threshold, and a
hysteresis value. It supports both sensors that return a single float value and
sensors (such as a DHT22) that return a dictionary containing multiple measurements.

When a sensor returns a dictionary, the 'measurement' parameter tells the controller
which value to use for its comparisons (e.g., "temperature" or "humidity").

In "below" logic:
  - If the actuator is off and the sensor value is less than (threshold - hysteresis),
    the actuator is turned ON.
  - If the actuator is on and the sensor value is greater than (threshold + hysteresis),
    the actuator is turned OFF.

In "above" logic (the reverse):
  - If the actuator is off and the sensor value is greater than (threshold + hysteresis),
    the actuator is turned ON.
  - If the actuator is on and the sensor value is less than (threshold - hysteresis),
    the actuator is turned OFF.

The controller uses the sensor_value provided (which may be a float or a dictionary)
to make its decision.
"""

class SensorActuatorController:
    def __init__(self, actuator, threshold, control_logic="below", hysteresis=0.5, initial_active=False, measurement="value"):
        """
        Initialize the SensorActuatorController.

        Parameters:
          actuator (object): An instance that implements turn_on() and turn_off() methods.
          threshold (float): The numeric threshold value against which sensor readings are compared.
          control_logic (str): A string, either "below" or "above". Determines when to turn on the actuator.
          hysteresis (float): A tolerance value to prevent rapid toggling (default is 0.5).
          initial_active (bool): The starting state of the actuator (True if it is already on, False if off).
          measurement (str): If the sensor returns a dictionary, this key specifies which measurement
                             to use (e.g., "temperature" or "humidity"). For sensors that return a single
                             value, this can be "value".
        """
        # Save the actuator instance and control parameters.
        self.actuator = actuator
        self.threshold = threshold
        self.control_logic = control_logic
        self.hysteresis = hysteresis
        self.active = initial_active
        self.measurement = measurement

    def check_and_update(self, sensor_value):
        """
        Uses the provided sensor_value to determine whether the actuator should be toggled.
        The decision is based on the control_logic ("below" or "above") and the hysteresis value.

        If the sensor_value is a dictionary (as returned by a DHT22 sensor), it extracts the
        value corresponding to the key specified by the 'measurement' parameter.

        Parameters:
          sensor_value (float or dict): The sensor reading to evaluate.

        Behavior for "below" logic:
          - If the actuator is off and sensor_value is less than (threshold - hysteresis), turn it ON.
          - If the actuator is on and sensor_value is greater than (threshold + hysteresis), turn it OFF.
        
        Behavior for "above" logic:
          - If the actuator is off and sensor_value is greater than (threshold + hysteresis), turn it ON.
          - If the actuator is on and sensor_value is less than (threshold - hysteresis), turn it OFF.

        """
        # Determine the numeric value to use for comparisons.
        # If sensor_value is a dictionary (e.g., from a DHT22), extract the value by key.
        if isinstance(sensor_value, dict):
            try:
                # Extract the measurement (e.g., "temperature" or "humidity") from the dictionary.
                value_to_compare = sensor_value[self.measurement]
            except KeyError:
                print(f"[Controller] Error: Measurement key '{self.measurement}' not found in sensor value.", flush=True)
                return None
        else:
            # If sensor_value is already a numeric value, use it directly.
            value_to_compare = sensor_value

        # Print the current sensor value and controller settings for debugging purposes.
        print(f"[Controller] Using sensor value={value_to_compare}, threshold={self.threshold}, "
              f"hysteresis={self.hysteresis}, active={self.active}", flush=True)

        # Apply the control logic based on the specified mode.
        if self.control_logic == "below":
            # For "below" logic: we want the actuator ON when sensor value is low.
            if not self.active and value_to_compare < self.threshold - self.hysteresis:
                print(f"[Controller] Turning ON: {value_to_compare} < {self.threshold - self.hysteresis}", flush=True)
                self.actuator.turn_on()
                self.actuator.cleanup()
                self.active = True
            elif self.active and value_to_compare > self.threshold + self.hysteresis:
                print(f"[Controller] Turning OFF: {value_to_compare} > {self.threshold + self.hysteresis}", flush=True)
                self.actuator.turn_off()
                self.actuator.cleanup()
                self.active = False
            else:
                print("[Controller] No change required for 'below' logic.", flush=True)
        elif self.control_logic == "above":
            # For "above" logic: we want the actuator ON when sensor value is high.
            if not self.active and value_to_compare > self.threshold + self.hysteresis:
                print(f"[Controller] Turning ON: {value_to_compare} > {self.threshold + self.hysteresis}", flush=True)
                self.actuator.turn_on()
                self.actuator.cleanup()
                self.active = True
            elif self.active and value_to_compare < self.threshold - self.hysteresis:
                print(f"[Controller] Turning OFF: {value_to_compare} < {self.threshold - self.hysteresis}", flush=True)
                self.actuator.turn_off()
                self.actuator.cleanup()
                self.active = False
            else:
                print("[Controller] No change required for 'above' logic.", flush=True)
        else:
            # If an unknown control_logic is provided, log an error.
            print("[Controller] Invalid control_logic specified.", flush=True)

