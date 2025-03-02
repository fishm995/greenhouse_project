# sensors.py
import random
from abc import ABC, abstractmethod
import time

class BaseSensor(ABC):
    @abstractmethod
    def read_value(self):
        """Read and return the sensor value."""
        pass

class TemperatureSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        For DS18B20 sensor.
        config: dictionary, can include additional parameters if needed.
        simulate: If True, returns simulated temperature.
        """
        self.simulate = simulate
        self.config = config
        if not self.simulate:
            # Enable 1-Wire interface and find the DS18B20 device.
            import os, glob
            os.system('modprobe w1-gpio')
            os.system('modprobe w1-therm')
            base_dir = '/sys/bus/w1/devices/'
            device_folders = glob.glob(base_dir + '28*')
            if not device_folders:
                raise Exception("No DS18B20 sensor found.")
            self.device_file = f"{device_folders[0]}/w1_slave"
        else:
            self.device_file = None

    def read_value(self):
        if self.simulate:
            # Simulate a temperature in Celsius between 15°C and 30°C.
            celsius = random.uniform(15, 30)
            return celsius * 9/5 + 32
        else:
            with open(self.device_file, 'r') as f:
                lines = f.readlines()
            attempts = 0
            while lines[0].strip()[-3:] != 'YES' and attempts < 5:
                time.sleep(0.2)
                with open(self.device_file, 'r') as f:
                    lines = f.readlines()
                attempts += 1
            if lines[0].strip()[-3:] != 'YES':
                raise Exception("Failed to get a valid reading from DS18B20 sensor.")
            equals_pos = lines[1].find('t=')
            if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
                celsius = float(temp_string) / 1000.0
                return celsius * 9/5 + 32
            else:
                raise Exception("Could not parse temperature value.")

class HumiditySensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        For sensors like the DHT22.
        config should include the GPIO pin (e.g., {"pin": 4}).
        """
        self.simulate = simulate
        self.config = config
        if not self.simulate:
            import Adafruit_DHT
            self.sensor = Adafruit_DHT.DHT22
            self.pin = config.get("pin")
            if self.pin is None:
                raise ValueError("DHT22 sensor requires a 'pin' configuration.")
        else:
            self.pin = None

    def read_value(self):
        if self.simulate:
            # Simulate humidity percentage between 40% and 70%.
            return random.uniform(40, 70)
        else:
            import Adafruit_DHT
            humidity, _ = Adafruit_DHT.read_retry(self.sensor, self.pin)
            if humidity is None:
                raise Exception("Failed to read humidity from DHT22 sensor.")
            return humidity

class CO2Sensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        For a CO₂ sensor.
        config: dictionary may include I²C address or serial port information.
        """
        self.simulate = simulate
        self.config = config

    def read_value(self):
        if self.simulate:
            # Simulate CO2 levels (ppm) between 400 and 800.
            return random.uniform(400, 800)
        else:
            # Implement actual sensor reading code here.
            raise NotImplementedError("Actual CO2 sensor reading not implemented.")

class LightSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        For a light sensor (e.g., TSL2561).
        config: dictionary with sensor parameters (I²C address, etc.).
        """
        self.simulate = simulate
        self.config = config

    def read_value(self):
        if self.simulate:
            # Simulate light level in lux.
            return random.uniform(100, 1000)
        else:
            # Implement actual sensor reading code here.
            raise NotImplementedError("Actual light sensor reading not implemented.")

class SoilMoistureSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        For soil moisture sensor.
        config: dictionary with ADC channel information, etc.
        """
        self.simulate = simulate
        self.config = config

    def read_value(self):
        if self.simulate:
            # Simulate soil moisture in arbitrary units.
            return random.uniform(200, 800)
        else:
            # Implement actual sensor reading code here.
            raise NotImplementedError("Actual soil moisture sensor reading not implemented.")

class WindSpeedSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        For a wind speed sensor (e.g., an anemometer).
        config: dictionary with GPIO pin and calibration info.
        """
        self.simulate = simulate
        self.config = config

    def read_value(self):
        if self.simulate:
            # Simulate wind speed (in mph, for example).
            return random.uniform(0, 15)
        else:
            # Implement actual sensor reading code here.
            raise NotImplementedError("Actual wind speed sensor reading not implemented.")

def sensor_factory(sensor_type, config, simulate=True):
    """
    Factory function to create sensor instances.
    
    sensor_type: one of "temperature", "humidity", "co2", "light", "soil_moisture", "wind_speed"
    config: dictionary of configuration parameters (e.g., GPIO pin, I²C address)
    simulate: if True, sensor readings are simulated.
    """
    sensor_type = sensor_type.lower()
    if sensor_type == "temperature":
        return TemperatureSensor(config, simulate=simulate)
    elif sensor_type == "humidity":
        return HumiditySensor(config, simulate=simulate)
    elif sensor_type == "co2":
        return CO2Sensor(config, simulate=simulate)
    elif sensor_type == "light":
        return LightSensor(config, simulate=simulate)
    elif sensor_type == "soil_moisture":
        return SoilMoistureSensor(config, simulate=simulate)
    elif sensor_type == "wind_speed":
        return WindSpeedSensor(config, simulate=simulate)
    else:
        raise ValueError("Unsupported sensor type: " + sensor_type)
