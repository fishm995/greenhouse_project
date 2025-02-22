# sensor.py
import random

class Sensor:
    """
    A class representing a sensor.
    Replace the read_value method with your actual sensor interfacing code.
    """
    def __init__(self, sensor_type):
        self.sensor_type = sensor_type

    def read_value(self):
        """
        Simulate reading a sensor value.
        For 'temperature', returns a value in °C.
        For 'humidity', returns a value in %.
        """
        if self.sensor_type == 'temperature':
            celsius = 20.0 + random.uniform(-5, 5)  # Simulated temperature in °C
            fahrenheit = celsius * 9/5 + 32
            return fahrenheit
        elif self.sensor_type == 'humidity':
            return 50.0 + random.uniform(-10, 10)  # Simulated humidity in %
        else:
            return None

if __name__ == "__main__":
    temp_sensor = Sensor('temperature')
    humidity_sensor = Sensor('humidity')
    print("Temperature:", temp_sensor.read_value())
    print("Humidity:", humidity_sensor.read_value())
