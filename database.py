# database.py
import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy_utils import database_exists, create_database
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///greenhouse.db')

class Base(DeclarativeBase):
    pass

class User(Base):
    """
    Model for storing user authentication data.
    In production, ensure passwords are securely hashed.
    """
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)  # Hashed password
    role = Column(String(10), default='junior')    # Roles: admin, senior, junior

class GreenhouseSetting(Base):
    """
    Model for storing greenhouse control settings.
    """
    __tablename__ = 'greenhouse_settings'
    id = Column(Integer, primary_key=True)
    function_name = Column(String(50), nullable=False)  # e.g., "lights", "water"
    start_time = Column(String(5))  # e.g., "08:00"
    end_time = Column(String(5))    # e.g., "18:00"
    allowed = Column(Boolean, default=True)
    duration = Column(Integer)      # Duration in minutes

class SensorLog(Base):
    """
    Model for storing logs of sensor readings.
    """
    __tablename__ = 'sensor_logs'
    id = Column(Integer, primary_key=True)
    sensor_type = Column(String(50))
    value = Column(Float)
    timestamp = Column(DateTime(timezone=True), 
                       default=lambda: datetime.datetime.now(ZoneInfo("America/Chicago")))

class DeviceControl(Base):
    """
    Model for storing device control settings.
    """
    __tablename__ = 'device_controls'
    id = Column(Integer, primary_key=True)
    device_name = Column(String(50), unique=True, nullable=False)
    device_type = Column(String(20), nullable=False, default="sensor")  # "sensor" or "actuator"
    mode = Column(String(10), default='auto')  # "manual" or "auto"
    current_status = Column(Boolean, default=False)
    auto_time = Column(String(5))       # e.g., "08:00"
    auto_duration = Column(Integer)     # Duration in minutes
    auto_enabled = Column(Boolean, default=True)
    last_auto_on = Column(DateTime(timezone=True), nullable=True)
    gpio_pin = Column(Integer, nullable=True)  # Only for actuators

class SensorConfig(Base):
    """
    Model for storing sensor configuration settings.
    This table holds information about each sensor device used in the greenhouse.
    """
    __tablename__ = 'sensor_configs'
    id = Column(Integer, primary_key=True)
    sensor_name = Column(String(100), unique=True, nullable=False)  # Unique identifier for the sensor
    sensor_type = Column(String(50), nullable=False)  # e.g., "temperature", "humidity", "co2", "light", "soil_moisture", "wind_speed"
    config_json = Column(Text, nullable=True)  # JSON-formatted string with additional configuration (e.g., GPIO pin, I²C address)
    simulate = Column(Boolean, default=True)  # Whether to simulate readings (True for development)

class ControllerConfig(Base):
    """
    Model for storing automation rules that link a sensor with an actuator.
    """
    __tablename__ = 'controller_configs'
    id = Column(Integer, primary_key=True)
    sensor_name = Column(String(100), nullable=False)   # Should match a SensorConfig.sensor_name
    actuator_name = Column(String(50), nullable=False)    # Should match a DeviceControl.device_name
    threshold = Column(Float, nullable=False)
    control_logic = Column(String(10), nullable=False)    # "below" or "above"
    hysteresis = Column(Float, default=0.5)                 # Tolerance value to prevent rapid toggling

# Setup the database engine and session
engine = create_engine(DATABASE_URL)

if not database_exists(engine.url):
    create_database(engine.url)
    print("Database created.")

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

if __name__ == '__main__':
    from werkzeug.security import generate_password_hash
    session = Session()

    # Seed Users
    users_to_add = [
        {'username': 'admin', 'password': '6let6P18', 'role': 'admin'},
        {'username': 'senior', 'password': '4sA5h66k', 'role': 'senior'},
        {'username': 'junior', 'password': 'nq753MkF', 'role': 'junior'},
    ]

    for user_data in users_to_add:
        existing_user = session.query(User).filter_by(username=user_data['username']).first()
        if not existing_user:
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

    # Seed Device Controls (for actuators, etc.)
    device_names = ['White Light', 'Black Light', 'Heat Lamp', 'Water Valve', 'Fresh Air Fan']
    for name in device_names:
        device = session.query(DeviceControl).filter_by(device_name=name).first()
        if not device:
            new_device = DeviceControl(
                device_name=name,
                device_type="actuator",  # or "sensor" as appropriate
                mode="manual",  # For testing manual controls
                current_status=False,
                auto_time="08:00",
                auto_duration=30,
                auto_enabled=True
            )
            session.add(new_device)
            print(f"Added device control: {name}")
        else:
            print(f"Device control {name} already exists")
    print("Device control setup complete.")

    # Seed Sensor Configurations (for sensors)
    sensor_configs = [
        {"sensor_name": "Outdoor Temperature", "sensor_type": "temperature", "config_json": "{}", "simulate": True},
        {"sensor_name": "Indoor Temperature",  "sensor_type": "temperature", "config_json": "{}", "simulate": True},
        {"sensor_name": "Humidity Sensor",       "sensor_type": "humidity",    "config_json": '{"pin": 4}', "simulate": True},
        {"sensor_name": "CO2 Sensor",            "sensor_type": "co2",         "config_json": "{}", "simulate": True},
        {"sensor_name": "Light Sensor",          "sensor_type": "light",       "config_json": "{}", "simulate": True},
        {"sensor_name": "Soil Moisture Sensor",  "sensor_type": "soil_moisture", "config_json": "{}", "simulate": True},
        {"sensor_name": "Wind Speed Sensor",     "sensor_type": "wind_speed",    "config_json": "{}", "simulate": True},
    ]
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
    session.commit()
    print("Sensor configuration setup complete.")
