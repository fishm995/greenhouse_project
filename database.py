# database.py
"""
This module defines the database models used in our greenhouse project using SQLAlchemy.
It includes models for:
  - User authentication data (User)
  - Greenhouse control settings (GreenhouseSetting)
  - Sensor reading logs (SensorLog)
  - Device control configuration for actuators (DeviceControl)
  - Sensor configuration details (SensorConfig)
  - Automation rules linking sensors to actuators (ControllerConfig)

It also sets up the database engine and creates a session factory for interacting with the database.
"""

# Import standard modules and functions
import os                           # Provides a way of using operating system dependent functionality (like environment variables)
import datetime                     # Used for handling dates and times

# Import SQLAlchemy components for database modeling and session management
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
# sqlalchemy_utils helps to check if a database exists and create one if not
from sqlalchemy_utils import database_exists, create_database

# dotenv is used to load environment variables from a .env file
from dotenv import load_dotenv

# zoneinfo is used to handle time zones (Python 3.9+)
from zoneinfo import ZoneInfo

# ---------------------------
# Load Environment Variables
# ---------------------------
# This will load variables from a .env file into the environment.
load_dotenv()

# Get the DATABASE_URL environment variable. If it's not set, default to using a local SQLite database file named "greenhouse.db"
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///greenhouse.db')

# ---------------------------
# Define Base Class for Models
# ---------------------------
# DeclarativeBase is the base class that all our model classes will inherit from.
class Base(DeclarativeBase):
    pass

# ---------------------------
# Define the User Model
# ---------------------------
class User(Base):
    """
    Model for storing user authentication data.
    
    Fields:
      - id: Unique identifier for the user.
      - username: The user's name (must be unique).
      - password_hash: The hashed version of the user's password.
      - role: The role of the user (e.g., admin, senior, junior). Defaults to 'junior'.
    """
    __tablename__ = 'users'  # Name of the table in the database.
    id = Column(Integer, primary_key=True)  # Primary key column (unique identifier).
    username = Column(String(50), unique=True, nullable=False)  # Username must be unique and cannot be null.
    password_hash = Column(Text, nullable=False)  # Hashed password is stored as text and cannot be null.
    role = Column(String(10), default='junior')    # The role assigned to the user; defaults to 'junior'.

# ---------------------------
# Define the GreenhouseSetting Model
# ---------------------------
class GreenhouseSetting(Base):
    """
    Model for storing greenhouse control settings.
    
    Fields:
      - id: Unique identifier for the setting.
      - function_name: Name of the function (e.g., "lights", "water").
      - start_time: The start time for the function (in HH:MM format).
      - end_time: The end time for the function (in HH:MM format).
      - allowed: A boolean indicating if the function is allowed (True or False).
      - duration: The duration (in minutes) for which the function should run.
    """
    __tablename__ = 'greenhouse_settings'
    id = Column(Integer, primary_key=True)
    function_name = Column(String(50), nullable=False)
    start_time = Column(String(5))  # Format "HH:MM"
    end_time = Column(String(5))    # Format "HH:MM"
    allowed = Column(Boolean, default=True)
    duration = Column(Integer)      # Duration in minutes

# ---------------------------
# Define the SensorLog Model
# ---------------------------
class SensorLog(Base):
    """
    Model for storing logs of sensor readings.
    
    Fields:
      - id: Unique identifier for the log entry.
      - sensor_type: The type or identifier of the sensor.
      - value: The numeric sensor reading.
      - timestamp: The date and time when the reading was taken, stored with timezone information.
    """
    __tablename__ = 'sensor_logs'
    id = Column(Integer, primary_key=True)
    sensor_type = Column(String(50))  # This could be the sensor's name or type.
    value = Column(Float)             # The reading value (e.g., temperature, humidity, etc.)
    # The default timestamp is set to the current time in the "America/Chicago" timezone.
    timestamp = Column(DateTime(timezone=True), 
                       default=lambda: datetime.datetime.now(ZoneInfo("America/Chicago")))

# ---------------------------
# Define the DeviceControl Model
# ---------------------------
class DeviceControl(Base):
    """
    Model for storing device (actuator) settings.
    
    Fields:
      - id: Unique identifier for the device control record.
      - device_name: Unique name for the device.
      - device_type: Type of device (e.g., "actuator").
      - control_mode: Mode of control ("time" or "sensor"). If "time", then time-based settings apply.
      - mode: The current mode, e.g., "manual" or "auto".
      - current_status: Boolean indicating whether the device is currently on (True) or off (False).
      - auto_time: The time at which the device should automatically turn on (format "HH:MM").
      - auto_duration: Duration in minutes for which the device should remain on.
      - auto_enabled: Boolean indicating if automatic time-based control is enabled.
      - last_auto_on: The timestamp when the device was last turned on automatically.
      - gpio_pin: The GPIO pin number used to control the device.
      - sensor_name: (Optional) Identifier of the sensor used for sensor-based control.
      - threshold: (Optional) Threshold value for sensor-based control.
      - control_logic: (Optional) "below" or "above", determining the condition for sensor-based control.
      - hysteresis: (Optional) A numeric tolerance to prevent rapid toggling.
      - simulate: Boolean flag indicating whether the device should run in simulation mode (True for simulation).
    """
    __tablename__ = 'device_controls'
    id = Column(Integer, primary_key=True)
    device_name = Column(String(50), unique=True, nullable=False)
    device_type = Column(String(20), nullable=False, default="actuator")
    control_mode = Column(String(10), default="time")  # "time" or "sensor"
    mode = Column(String(10), default='auto')          # For time-based control, "manual" or "auto"
    current_status = Column(Boolean, default=False)
    auto_time = Column(String(5))               # e.g., "08:00"
    auto_duration = Column(Integer)             # Duration in minutes
    auto_enabled = Column(Boolean, default=True)
    last_auto_on = Column(DateTime(timezone=True), nullable=True)
    gpio_pin = Column(Integer, nullable=True)
    sensor_name = Column(String(100), nullable=True)  # Links to SensorConfig.sensor_name
    threshold = Column(Float, nullable=True)
    control_logic = Column(String(10), nullable=True)  # "below" or "above"
    hysteresis = Column(Float, nullable=True)
    simulate = Column(Boolean, default=True)  # If True, device actions are simulated.

# ---------------------------
# Define the SensorConfig Model
# ---------------------------
class SensorConfig(Base):
    """
    Model for storing sensor configuration settings.
    
    Fields:
      - id: Unique identifier for the sensor configuration.
      - sensor_name: A unique name for the sensor.
      - sensor_type: The type of sensor (e.g., "temperature", "humidity", etc.).
      - config_json: A JSON-formatted string with additional sensor configuration (e.g., GPIO pin, I²C address).
      - simulate: Boolean flag indicating whether to simulate sensor readings.
    """
    __tablename__ = 'sensor_configs'
    id = Column(Integer, primary_key=True)
    sensor_name = Column(String(100), unique=True, nullable=False)  # Unique identifier for the sensor
    sensor_type = Column(String(50), nullable=False)  # e.g., "temperature", "humidity", "co2", "light", "soil_moisture", "wind_speed"
    config_json = Column(Text, nullable=True)  # JSON-formatted string with additional configuration (e.g., GPIO pin, I²C address)
    simulate = Column(Boolean, default=True)  # Whether to simulate readings (True for development)

# ---------------------------
# Define the ControllerConfig Model
# ---------------------------
class ControllerConfig(Base):
    """
    Model for storing automation rules that link a sensor with an actuator.
    
    Fields:
      - id: Unique identifier for the controller rule.
      - sensor_name: References the sensor by name (must match SensorConfig.sensor_name).
      - actuator_name: References the actuator by device name (must match DeviceControl.device_name).
      - threshold: The sensor threshold value for triggering control.
      - control_logic: "below" or "above" indicating when to trigger the actuator.
      - hysteresis: Tolerance value to prevent rapid toggling (default is 0.5).
    """
    __tablename__ = 'controller_configs'
    id = Column(Integer, primary_key=True)
    sensor_name = Column(String(100), nullable=False)   # Reference to SensorConfig.sensor_name
    actuator_name = Column(String(50), nullable=False)    # Reference to DeviceControl.device_name
    threshold = Column(Float, nullable=False)
    control_logic = Column(String(10), nullable=False)    # "below" or "above"
    hysteresis = Column(Float, default=0.5)                 # Tolerance value

# ---------------------------
# Set Up the Database Engine and Session
# ---------------------------
# Create an engine based on the DATABASE_URL.
engine = create_engine(DATABASE_URL)

# Check if the database exists; if not, create it.
if not database_exists(engine.url):
    create_database(engine.url)
    print("Database created.")

# Create all tables in the database based on our models.
Base.metadata.create_all(engine)

# Create a session factory that can be used to create new database sessions.
Session = sessionmaker(bind=engine)

# ---------------------------
# Seeding Data (Only run when this file is executed directly)
# ---------------------------
if __name__ == '__main__':
    from werkzeug.security import generate_password_hash  # Import function to hash passwords securely
    session = Session()  # Create a new database session

    # --- Seed Users ---
    # Define a list of user dictionaries to add to the database.
    users_to_add = [
        {'username': 'admin', 'password': '6let6P18', 'role': 'admin'},
        {'username': 'senior', 'password': '4sA5h66k', 'role': 'senior'},
        {'username': 'junior', 'password': 'nq753MkF', 'role': 'junior'},
    ]

    # Loop through each user and add them if they don't already exist.
    for user_data in users_to_add:
        existing_user = session.query(User).filter_by(username=user_data['username']).first()
        if not existing_user:
            # Create a new User object with a hashed password.
            new_user = User(
                username=user_data['username'],
                password_hash=generate_password_hash(user_data['password']),
                role=user_data['role']
            )
            session.add(new_user)
            print(f"Added user {user_data['username']}")
        else:
            print(f"User {user_data['username']} already exists")
    print("User setup complete.")

    # --- Seed Device Controls ---
    # Define a list of device names for actuators.
    device_names = ['White Light', 'Black Light', 'Heat Lamp', 'Water Valve', 'Fresh Air Fan']
    for name in device_names:
        # Check if a device with this name already exists.
        device = session.query(DeviceControl).filter_by(device_name=name).first()
        if not device:
            # Create a new DeviceControl object with default settings.
            new_device = DeviceControl(
                device_name=name,
                device_type="actuator",  # Specify that this is an actuator
                mode="manual",  # Start in manual mode for testing
                current_status=False,  # Initially off
                auto_time="08:00",  # Default auto time
                auto_duration=30,   # Default duration of 30 minutes
                auto_enabled=True   # Auto control is enabled
                # Note: gpio_pin, sensor_name, threshold, control_logic, hysteresis, and simulate
                # can be updated later via admin settings.
            )
            session.add(new_device)
            print(f"Added device control: {name}")
        else:
            print(f"Device control {name} already exists")
    print("Device control setup complete.")

    # --- Seed Sensor Configurations ---
    # Define a list of sensor configuration dictionaries.
    sensor_configs = [
        {"sensor_name": "Outdoor Temperature", "sensor_type": "temperature", "config_json": "{}", "simulate": True},
        {"sensor_name": "Indoor Temperature",  "sensor_type": "temperature", "config_json": "{}", "simulate": True},
        {"sensor_name": "Humidity Sensor",       "sensor_type": "humidity",    "config_json": '{"pin": 4}', "simulate": True},
        {"sensor_name": "CO2 Sensor",            "sensor_type": "co2",         "config_json": "{}", "simulate": True},
        {"sensor_name": "Light Sensor",          "sensor_type": "light",       "config_json": "{}", "simulate": True},
        {"sensor_name": "Soil Moisture Sensor",  "sensor_type": "soil_moisture", "config_json": "{}", "simulate": True},
        {"sensor_name": "Wind Speed Sensor",     "sensor_type": "wind_speed",    "config_json": "{}", "simulate": True},
    ]
    # Loop through each sensor configuration and add it if it doesn't already exist.
    for conf in sensor_configs:
        existing = session.query(SensorConfig).filter_by(sensor_name=conf["sensor_name"]).first()
        if not existing:
            new_sensor = SensorConfig(
                sensor_name = conf["sensor_name"],
                sensor_type = conf["sensor_type"],
                config_json = conf["config_json"],
                simulate = conf["simulate"]
            )
            session.add(new_sensor)
            print(f"Added sensor config: {conf['sensor_name']}")
        else:
            print(f"Sensor config {conf['sensor_name']} already exists")
    # Commit all seeded data to the database.
    session.commit()
    print("Sensor configuration setup complete.")
