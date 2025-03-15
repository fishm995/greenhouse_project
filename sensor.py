# sensors.py
"""
This module defines various sensor classes and a factory function for creating sensor instances.
Each sensor class simulates (or in production, reads from) a different type of sensor used in the greenhouse.
The sensors include:
  - TemperatureSensor (for DS18B20 sensors or DHT22 for temperature)
  - HumiditySensor (for DHT22 or other humidity sensors)
  - CO2Sensor (for CO₂ measurements)
  - LightSensor (for light level readings)
  - SoilMoistureSensor (for soil moisture readings)
  - WindSpeedSensor (for wind speed measurements)

Each sensor class implements a read_value() method that returns a sensor reading.
In simulation mode, the reading is generated randomly.
For real sensors, you would implement the code to read from the actual hardware.
"""

import random       # Used to generate random sensor readings in simulation mode
import json         # For parsing JSON configuration strings from the database
from abc import ABC, abstractmethod  # For creating an abstract base class (BaseSensor)
import time         # For adding delays when reading sensors (e.g., retries)

# ---------------------------
# Global Cache for Sensor Readings
# ---------------------------
# SENSOR_CACHE will store the most recent reading for each sensor to avoid multiple hardware reads.
# The key is a unique identifier for the sensor (for a DHT22 sensor, we use "dht22_<pin>").
# The value is a dictionary with:
#   - "timestamp": when the reading was taken (in seconds since epoch),
#   - "temperature_c": the temperature reading in Celsius,
#   - "humidity": the humidity reading.
SENSOR_CACHE = {}
# CACHE_DURATION defines how long (in seconds) a cached reading remains valid.
CACHE_DURATION = 45.0

def read_dht22_with_cache(sensor, pin):
    """
    Reads from a DHT22 sensor using a caching mechanism.
    
    If a cached reading exists for the sensor (identified by its GPIO pin) and is
    still fresh (i.e., taken less than CACHE_DURATION seconds ago), the cached values
    are returned. Otherwise, a new reading is performed and the cache is updated.
    
    Parameters:
      sensor: The sensor constant from the Adafruit_DHT library (e.g., Adafruit_DHT.DHT22).
      pin (int): The GPIO pin number where the sensor is connected.
      
    Returns:
      tuple: A tuple (humidity, temperature_c) where:
        - humidity: The humidity percentage.
        - temperature_c: The temperature in Celsius.
    """
    # Create a unique key for caching, e.g., "dht22_4" for a DHT22 sensor on GPIO pin 4.
    cache_key = f"dht22_{pin}"
    # Get the current time in seconds.
    current_time = time.time()
    # Check if we already have a cached reading for this sensor.
    if cache_key in SENSOR_CACHE:
        cached = SENSOR_CACHE[cache_key]
        # If the cached reading is still within the valid duration, return it.
        if current_time - cached["timestamp"] < CACHE_DURATION:
            return cached["humidity"], cached["temperature_c"]
    # If no valid cached reading exists, perform a new sensor read.
    import Adafruit_DHT
    # Use Adafruit_DHT.read_retry to attempt reading from the sensor.
    humidity, temperature_c = Adafruit_DHT.read_retry(sensor, pin)
    # Update the cache with the new reading along with the current timestamp.
    SENSOR_CACHE[cache_key] = {
        "timestamp": current_time,
        "humidity": humidity,
        "temperature_c": temperature_c
    }
    # Return the new reading.
    return humidity, temperature_c

# ---------------------------
# BaseSensor Abstract Class
# ---------------------------
class BaseSensor(ABC):
    """
    Abstract Base Class for all sensor types.
    Any sensor class that inherits from BaseSensor must implement the read_value() method.
    """
    @abstractmethod
    def read_value(self):
        """Read and return the sensor value."""
        pass  # No implementation here; this is an abstract method.

# -------------------------------------------
# TemperatureSensor Class (modified for DHT22 caching)
# -------------------------------------------
class TemperatureSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initializes a TemperatureSensor instance.
        
        Parameters:
          config (dict): A dictionary containing configuration settings. It must include a key
                         "sensor_hardware". For a DHT22 sensor, the config should include:
                           {"sensor_hardware": "dht22", "pin": <GPIO_PIN>}
                         Otherwise, it will assume a DS18B20 sensor.
          simulate (bool): If True, the sensor returns a simulated reading.
                           If False, it will attempt to read from real hardware.
        """
        self.simulate = simulate       # Store the simulation flag.
        self.config = config           # Store the configuration dictionary.
        # Determine the sensor type from the configuration (default to "temperature").
        self.sensor_hardware = config.get("sensor_hardware", "temperature").lower()
        if not self.simulate:
            if self.sensor_hardware == "dht22":
                # For DHT22, import the Adafruit_DHT library and set up the sensor.
                import Adafruit_DHT
                self.sensor = Adafruit_DHT.DHT22
                # Retrieve the GPIO pin from the configuration.
                self.pin = config.get("pin")
                if self.pin is None:
                    raise ValueError("DHT22 sensor requires a 'pin' configuration.")
            else:
                # For DS18B20 sensors (or other temperature sensors), set up 1-Wire interface.
                import os, glob
                os.system('modprobe w1-gpio')
                os.system('modprobe w1-therm')
                base_dir = '/sys/bus/w1/devices/'
                # DS18B20 sensor folders typically start with '28'
                device_folders = glob.glob(base_dir + '28*')
                if not device_folders:
                    raise Exception("No DS18B20 sensor found.")
                # Use the first detected sensor.
                self.device_file = f"{device_folders[0]}/w1_slave"
        else:
            # In simulation mode, we don't need to set up hardware.
            self.device_file = None

    def read_value(self):
        if self.simulate:
            # In simulation mode, generate a random temperature in Celsius between 15 and 30,
            # then convert it to Fahrenheit.
            celsius = random.uniform(15, 30)
            return celsius * 9/5 + 32
        else:
            if self.sensor_hardware == "dht22":
                # For DHT22, use our caching mechanism to get the reading.
                import Adafruit_DHT
                humidity, temperature_c = read_dht22_with_cache(self.sensor, self.pin)
                if temperature_c is None:
                    raise Exception("Failed to read temperature from DHT22 sensor.")
                # Convert the temperature from Celsius to Fahrenheit.
                return temperature_c * 9/5 + 32
            else:
                # For DS18B20, read from the device file.
                with open(self.device_file, 'r') as f:
                    lines = f.readlines()
                attempts = 0
                # Retry reading until the sensor data is confirmed valid ("YES" at the end of the first line).
                while lines[0].strip()[-3:] != 'YES' and attempts < 5:
                    time.sleep(0.2)
                    with open(self.device_file, 'r') as f:
                        lines = f.readlines()
                    attempts += 1
                if lines[0].strip()[-3:] != 'YES':
                    raise Exception("Failed to get a valid reading from DS18B20 sensor.")
                # Find the temperature value in the second line after "t=".
                equals_pos = lines[1].find('t=')
                if equals_pos != -1:
                    temp_string = lines[1][equals_pos+2:]
                    celsius = float(temp_string) / 1000.0
                    return celsius * 9/5 + 32
                else:
                    raise Exception("Could not parse temperature value.")

# -------------------------------------------
# HumiditySensor Class (modified for DHT22 caching)
# -------------------------------------------
class HumiditySensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initializes a HumiditySensor instance.
        
        Parameters:
          config (dict): A dictionary containing configuration details.
                         It must include "sensor_type". For a DHT22 sensor, the config should include:
                           {"sensor_type": "dht22", "pin": <GPIO_PIN>}
          simulate (bool): If True, returns a simulated humidity value.
        """
        self.simulate = simulate       # Store simulation flag.
        self.config = config           # Store configuration.
        # Determine the sensor type (default to "humidity").
        self.sensor_hardware = config.get("sensor_hardware", "humidity").lower()
        if not self.simulate:
            if self.sensor_hardware == "dht22":
                # For DHT22, import the Adafruit_DHT library.
                import Adafruit_DHT
                self.sensor = Adafruit_DHT.DHT22
                self.pin = config.get("pin")
                if self.pin is None:
                    raise ValueError("DHT22 sensor requires a 'pin' configuration.")
            else:
                # If a different humidity sensor is used, additional code would be needed.
                raise NotImplementedError("Non-DHT22 humidity sensor not implemented.")
        else:
            self.pin = None

    def read_value(self):
        if self.simulate:
            # In simulation mode, generate a random humidity value between 40% and 70%.
            return random.uniform(40, 70)
        else:
            if self.sensor_hardware == "dht22":
                import Adafruit_DHT
                # Use the caching mechanism to get the sensor reading.
                humidity, _ = read_dht22_with_cache(self.sensor, self.pin)
                if humidity is None:
                    raise Exception("Failed to read humidity from DHT22 sensor.")
                return humidity
            else:
                raise NotImplementedError("Non-DHT22 humidity sensor not implemented.")

# ---------------------------
# CO2Sensor Class
# ---------------------------
class CO2Sensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initializes a CO2Sensor instance.
        
        Parameters:
          config (dict): May include additional parameters (I²C address, serial port, etc.).
          simulate (bool): If True, returns simulated CO2 readings.
        """
        self.simulate = simulate
        self.config = config

    def read_value(self):
        """
        Reads the CO2 sensor value.
        
        In simulation mode:
          - Returns a random CO2 concentration (in parts per million) between 400 and 800.
        In real mode:
          - Not implemented yet.
        """
        if self.simulate:
            return random.uniform(400, 800)
        else:
            raise NotImplementedError("Actual CO2 sensor reading not implemented.")

# ---------------------------
# LightSensor Class
# ---------------------------
class LightSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initializes a LightSensor instance.
        
        Parameters:
          config (dict): Contains configuration details such as I²C address.
          simulate (bool): If True, returns simulated light levels.
        """
        self.simulate = simulate
        self.config = config

    def read_value(self):
        """
        Reads the light level from the sensor.
        
        In simulation mode:
          - Returns a random light level in lux between 100 and 1000.
        In real mode:
          - Not implemented yet.
        """
        if self.simulate:
            return random.uniform(100, 1000)
        else:
            raise NotImplementedError("Actual light sensor reading not implemented.")

# ---------------------------
# SoilMoistureSensor Class
# ---------------------------
class SoilMoistureSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initializes a SoilMoistureSensor instance.
        
        Parameters:
          config (dict): May include ADC channel or other configuration details.
          simulate (bool): If True, returns simulated soil moisture values.
        """
        self.simulate = simulate
        self.config = config

    def read_value(self):
        """
        Reads the soil moisture level.
        
        In simulation mode:
          - Returns a random value (arbitrary units) between 200 and 800.
        In real mode:
          - Not implemented yet.
        """
        if self.simulate:
            return random.uniform(200, 800)
        else:
            raise NotImplementedError("Actual soil moisture sensor reading not implemented.")

# ---------------------------
# WindSpeedSensor Class
# ---------------------------
class WindSpeedSensor(BaseSensor):
    def __init__(self, config, simulate=True):
        """
        Initializes a WindSpeedSensor instance.
        
        Parameters:
          config (dict): May include configuration such as GPIO pin and calibration info.
          simulate (bool): If True, returns simulated wind speed values.
        """
        self.simulate = simulate
        self.config = config

    def read_value(self):
        """
        Reads the wind speed.
        
        In simulation mode:
          - Returns a random wind speed (e.g., in mph) between 0 and 15.
        In real mode:
          - Not implemented yet.
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
      sensor_type (str): The type of sensor. Supported types include:
                         "temperature", "humidity", "co2", "light", "soil_moisture", "wind_speed"
      config (dict): A dictionary of configuration parameters (e.g., GPIO pin, I²C address).
      simulate (bool): If True, the sensor instance will return simulated readings.
      
    Returns:
      An instance of the sensor class corresponding to the provided sensor_type.
      
    Raises:
      ValueError: If an unsupported sensor type is provided.
    """
    # Convert the sensor_type to lowercase to ensure case-insensitivity.
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
        # Raise an error if the provided sensor type is not supported.
        raise ValueError("Unsupported sensor type: " + sensor_type)
