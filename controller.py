# controller.py

class SensorActuatorController:
    """
    A controller that monitors a sensor and controls an actuator based on a threshold.

    Parameters:
      sensor: An instance that implements a read_value() method to obtain the sensor reading.
      actuator: An instance that implements turn_on() and turn_off() methods to control the actuator.
      threshold: The numeric threshold value against which the sensor reading is compared.
      control_logic: A string, either "below" or "above". 
                     - "below" means the actuator should turn on if the sensor value is sufficiently below the threshold.
                     - "above" means the actuator should turn on if the sensor value is sufficiently above the threshold.
      hysteresis: A numeric tolerance to prevent rapid toggling (default is 0.5).
      initial_active: The current state of the actuator (True if it's already on, False if off).
    """
    def __init__(self, sensor, actuator, threshold, control_logic="below", hysteresis=0.5, initial_active=False):
        self.sensor = sensor
        self.actuator = actuator
        self.threshold = threshold
        self.control_logic = control_logic
        self.hysteresis = hysteresis
        # Initialize the active state from the DeviceControl record.
        self.active = initial_active

    def check_and_update(self):
        """
        Reads the sensor value and updates the actuator state based on the threshold,
        control logic, and hysteresis.

        Returns the sensor value if successful; otherwise, returns None.
        """
        try:
            # Get the current sensor reading.
            value = self.sensor.read_value()
            print(f"[Controller] Sensor reading: {value}, Threshold: {self.threshold}, "
                  f"Hysteresis: {self.hysteresis}, Current active: {self.active}")
        except Exception as e:
            print(f"[Controller] Error reading sensor: {e}")
            return None

        # Process control logic based on the desired behavior.
        if self.control_logic == "below":
            # If the actuator is off and the sensor reading is sufficiently below the threshold,
            # then turn the actuator on.
            if not self.active and value < self.threshold - self.hysteresis:
                print(f"[Controller] Turning ON: {value} < {self.threshold - self.hysteresis}")
                self.actuator.turn_on()
                self.active = True
            # If the actuator is on and the sensor reading is above the threshold (with hysteresis),
            # then turn the actuator off.
            elif self.active and value > self.threshold + self.hysteresis:
                print(f"[Controller] Turning OFF: {value} > {self.threshold + self.hysteresis}")
                self.actuator.turn_off()
                self.active = False
            else:
                print(f"[Controller] No change required for 'below' logic.")
        elif self.control_logic == "above":
            # If the actuator is off and the sensor reading is sufficiently above the threshold,
            # then turn the actuator on.
            if not self.active and value > self.threshold + self.hysteresis:
                print(f"[Controller] Turning ON: {value} > {self.threshold + self.hysteresis}")
                self.actuator.turn_on()
                self.active = True
            # If the actuator is on and the sensor reading is below the threshold (with hysteresis),
            # then turn the actuator off.
            elif self.active and value < self.threshold - self.hysteresis:
                print(f"[Controller] Turning OFF: {value} > {self.threshold + self.hysteresis}")
                self.actuator.turn_off()
                self.active = False
            else:
                print(f"[Controller] No change required for 'above' logic.")
        else:
            print("[Controller] Invalid control_logic specified.")
        
        return value
