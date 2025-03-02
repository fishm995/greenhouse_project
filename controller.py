# controller.py

class SensorActuatorController:
    """
    A modular controller that monitors a sensor and controls an actuator based on a threshold.
    
    Parameters:
      sensor: an instance that implements read_value()
      actuator: an instance that implements turn_on() and turn_off()
      threshold: numeric value representing the desired threshold
      control_logic: either "below" or "above"
          - "below": if sensor reading is below the threshold, turn on the actuator.
          - "above": if sensor reading is above the threshold, turn on the actuator.
      hysteresis: a tolerance value to prevent rapid toggling.
    """
    def __init__(self, sensor, actuator, threshold, control_logic="below", hysteresis=0.5):
        self.sensor = sensor
        self.actuator = actuator
        self.threshold = threshold
        self.control_logic = control_logic
        self.hysteresis = hysteresis
        self.active = False  # Tracks whether the actuator is currently on.

    def check_and_update(self):
        """
        Read the sensor and update the actuator's state.
        Returns the sensor value.
        """
        try:
            value = self.sensor.read_value()
        except Exception as e:
            print(f"Error reading sensor: {e}")
            return None
        
        if self.control_logic == "below":
            if not self.active and value < self.threshold - self.hysteresis:
                self.actuator.turn_on()
                self.active = True
            elif self.active and value > self.threshold + self.hysteresis:
                self.actuator.turn_off()
                self.active = False
        elif self.control_logic == "above":
            if not self.active and value > self.threshold + self.hysteresis:
                self.actuator.turn_on()
                self.active = True
            elif self.active and value < self.threshold - self.hysteresis:
                self.actuator.turn_off()
                self.active = False
        else:
            print("Invalid control_logic specified.")
        return value
