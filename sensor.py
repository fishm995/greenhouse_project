# sensors.py
"""
This module defines various sensor classes and a factory function for creating sensor instances.
Each sensor class simulates (or in production, reads from) a different type of sensor used in the greenhouse.
The sensors include:
  - TemperatureSensor (for DS18B20 sensors)
  - HumiditySensor (for sensors like DHT22)
  - CO2Sensor (for CO₂ measurements)
  - LightSensor (for light level readings)
  - SoilMoistureSensor (for soil moisture readings)
  - WindSpeedSensor (for wind speed measurements)

Each sensor class implements a read_value() method that returns a sensor reading.
In simulation mode, the reading is generated randomly.
For real sensors, code should be implemented to read the actual hardware.
"""

import random       # Used to generate random sensor readings in simulation mode
from abc import ABC, abstractmethod  # For defining abstract base classes (interfaces)
import time         # For adding delays when reading sensors

# ---------------------------
# Base Sensor Class
# ---------------------------
class BaseSensor(ABC):
    """
    Abstract Base Class for all sensors.
    Any sensor class that inherits from BaseSensor must implement the read_value() method.
    """
    @abstractmethod
    def read_value(self):
        """Read and return the sensor value."""
        pass  # Abstract method; no implementation here

# ---------------------------
# Temperature Sensor Class
# ---------------------------
class TemperatureSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initialize a TemperatureSensor, typically for a DS18B20 sensor.

        Parameters:
          config (dict): A dictionary that can include additional parameters for sensor setup.
          simulate (bool): If True, the sensor will return simulated temperature readings.
                           If False, it will attempt to read from the actual DS18B20 sensor.
        """
        self.simulate = simulate  # Flag to decide between simulation and real sensor reading
        self.config = config      # Store the configuration dictionary
        if not self.simulate:
            # In real mode, set up the 1-Wire interface to read the DS18B20 sensor.
            import os, glob
            # Run system commands to load necessary modules for 1-Wire communication.
            os.system('modprobe w1-gpio')
            os.system('modprobe w1-therm')
            base_dir = '/sys/bus/w1/devices/'
            # Find device folders that start with '28', which is typical for DS18B20 sensors.
            device_folders = glob.glob(base_dir + '28*')
            if not device_folders:
                # Raise an exception if no DS18B20 sensor is found.
                raise Exception("No DS18B20 sensor found.")
            # Use the first detected sensor's w1_slave file as the data file.
            self.device_file = f"{device_folders[0]}/w1_slave"
        else:
            # In simulation mode, there's no real device file.
            self.device_file = None

    def read_value(self):
        """
        Read the temperature sensor value and return it in Fahrenheit.
        
        In simulation mode:
          - Generates a random temperature in Celsius between 15°C and 30°C,
            then converts it to Fahrenheit.
        
        In real mode:
          - Reads from the DS18B20 sensor's data file.
          - Retries a few times if the reading is not valid.
          - Converts the temperature from Celsius to Fahrenheit.
        """
        if self.simulate:
            # Generate a simulated temperature in Celsius.
            celsius = random.uniform(15, 30)
            # Convert Celsius to Fahrenheit and return the value.
            return celsius * 9/5 + 32
        else:
            # Open the sensor's device file to read the raw data.
            with open(self.device_file, 'r') as f:
                lines = f.readlines()
            # Retry up to 5 times if the first line doesn't indicate a valid reading ("YES").
            attempts = 0
            while lines[0].strip()[-3:] != 'YES' and attempts < 5:
                time.sleep(0.2)  # Wait briefly before trying again
                with open(self.device_file, 'r') as f:
                    lines = f.readlines()
                attempts += 1
            if lines[0].strip()[-3:] != 'YES':
                raise Exception("Failed to get a valid reading from DS18B20 sensor.")
            # Find the position of 't=' in the second line, which contains the temperature.
            equals_pos = lines[1].find('t=')
            if equals_pos != -1:
                # Extract the temperature string (in thousandths of a degree Celsius).
                temp_string = lines[1][equals_pos+2:]
                # Convert the string to a float and then scale it to Celsius.
                celsius = float(temp_string) / 1000.0
                # Convert Celsius to Fahrenheit and return the value.
                return celsius * 9/5 + 32
            else:
                raise Exception("Could not parse temperature value.")

# ---------------------------
# Humidity Sensor Class
# ---------------------------
class HumiditySensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initialize a HumiditySensor, typically for sensors like the DHT22.
        
        Parameters:
          config (dict): Should include necessary configuration, such as the GPIO pin (e.g., {"pin": 4}).
          simulate (bool): If True, returns simulated humidity values; otherwise, reads from the actual sensor.
        """
        self.simulate = simulate  # Flag to decide simulation vs. real sensor
        self.config = config      # Store configuration details
        if not self.simulate:
            # In real mode, import the Adafruit_DHT library for reading the sensor.
            import Adafruit_DHT
            self.sensor = Adafruit_DHT.DHT22  # Specify sensor type (DHT22)
            self.pin = config.get("pin")      # Get the GPIO pin from the config
            if self.pin is None:
                raise ValueError("DHT22 sensor requires a 'pin' configuration.")
        else:
            self.pin = None  # No pin required in simulation mode

    def read_value(self):
        """
        Read the humidity value from the sensor.
        
        In simulation mode:
          - Generates a random humidity value between 40% and 70%.
        
        In real mode:
          - Uses the Adafruit_DHT library to read the sensor.
          - Raises an exception if a valid humidity reading cannot be obtained.
        """
        if self.simulate:
            return random.uniform(40, 70)
        else:
            import Adafruit_DHT
            # Read humidity (and temperature, which we ignore here) using a retry mechanism.
            humidity, _ = Adafruit_DHT.read_retry(self.sensor, self.pin)
            if humidity is None:
                raise Exception("Failed to read humidity from DHT22 sensor.")
            return humidity

# ---------------------------
# CO2 Sensor Class
# ---------------------------
class CO2Sensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initialize a CO2Sensor.
        
        Parameters:
          config (dict): May include additional parameters (I²C address, serial port, etc.).
          simulate (bool): If True, returns a simulated CO2 reading.
        """
        self.simulate = simulate  # Simulation flag
        self.config = config      # Store configuration details

    def read_value(self):
        """
        Read the CO2 sensor value.
        
        In simulation mode:
          - Generates a random CO2 concentration (in parts per million) between 400 and 800.
        
        In real mode:
          - Not implemented yet; raises NotImplementedError.
        """
        if self.simulate:
            return random.uniform(400, 800)
        else:
            # Here, you would add the code to interact with a real CO2 sensor.
            raise NotImplementedError("Actual CO2 sensor reading not implemented.")

# ---------------------------
# Light Sensor Class
# ---------------------------
class LightSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initialize a LightSensor.
        
        Parameters:
          config (dict): Contains sensor parameters such as I²C address.
          simulate (bool): If True, returns simulated light levels.
        """
        self.simulate = simulate
        self.config = config

    def read_value(self):
        """
        Read the light level from the sensor.
        
        In simulation mode:
          - Generates a random light level in lux between 100 and 1000.
        
        In real mode:
          - Not implemented yet; raises NotImplementedError.
        """
        if self.simulate:
            return random.uniform(100, 1000)
        else:
            raise NotImplementedError("Actual light sensor reading not implemented.")

# ---------------------------
# Soil Moisture Sensor Class
# ---------------------------
class SoilMoistureSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initialize a SoilMoistureSensor.
        
        Parameters:
          config (dict): May include ADC channel information or other parameters.
          simulate (bool): If True, returns simulated soil moisture values.
        """
        self.simulate = simulate
        self.config = config

    def read_value(self):
        """
        Read the soil moisture level.
        
        In simulation mode:
          - Generates a random value (in arbitrary units) between 200 and 800.
        
        In real mode:
          - Not implemented yet; raises NotImplementedError.
        """
        if self.simulate:
            return random.uniform(200, 800)
        else:
            raise NotImplementedError("Actual soil moisture sensor reading not implemented.")

# ---------------------------
# Wind Speed Sensor Class
# ---------------------------
class WindSpeedSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initialize a WindSpeedSensor.
        
        Parameters:
          config (dict): May include configuration like GPIO pin and calibration info.
          simulate (bool): If True, returns simulated wind speed values.
        """
        self.simulate = simulate
        self.config = config

    def read_value(self):
        """
        Read the wind speed.
        
        In simulation mode:
          - Generates a random wind speed (e.g., in miles per hour) between 0 and 15.
        
        In real mode:
          - Not implemented yet; raises NotImplementedError.
        """
        if self.simulate:
            return random.uniform(0, 15)
        else:
            raise NotImplementedError("Actual wind speed sensor reading not implemented.")

# ---------------------------
# Sensor Factory Function
# ---------------------------
def sensor_factory(sensor_type, config, simulate=True):
    """
    Factory function to create a sensor instance based on the sensor type.
    
    Parameters:
      sensor_type (str): The type of sensor. Supported types are:
                         "temperature", "humidity", "co2", "light", "soil_moisture", "wind_speed".
      config (dict): A dictionary of configuration parameters for the sensor (e.g., GPIO pin, I²C address).
      simulate (bool): If True, the sensor instance will simulate readings.
    
    Returns:
      An instance of the corresponding sensor class.
      
    Raises:
      ValueError: If an unsupported sensor type is provided.
    """
    sensor_type = sensor_type.lower()  # Normalize the sensor type to lowercase
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
        # Raise an error if the sensor type is not supported.
        raise ValueError("Unsupported sensor type: " + sensor_type)
