# database.py
import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Base(DeclarativeBase):
    pass
    
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///greenhouse.db')

class User(Base):
    """
    Model for storing user authentication data.
    In production, ensure passwords are securely hashed.
    """
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(), nullable=False)  # Hashed password
    role = Column(String(10), default='junior')    # admin, senior, junior

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
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class DeviceControl(Base):
    __tablename__ = 'device_controls'
    id = Column(Integer, primary_key=True)
    device_name = Column(String(50), unique=True, nullable=False)
    # Mode can be "manual" or "auto"
    mode = Column(String(10), default='auto')
    # Current on/off state (True means on, False means off)
    current_status = Column(Boolean, default=False)
    # Auto settings – these are used when mode == "auto"
    auto_time = Column(String(5))       # time of day e.g., "08:00"
    auto_duration = Column(Integer)       # duration in minutes
    auto_enabled = Column(Boolean, default=True)

# Setup the database engine and session
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

if __name__ == '__main__':
    from werkzeug.security import generate_password_hash
    session = Session()

    # Define a list of users to add.
    users_to_add = [
        {'username': 'admin', 'password': '6let6P18', 'role': 'admin'},
        {'username': 'senior', 'password': '4sA5h66k', 'role': 'senior'},
        {'username': 'junior', 'password': 'nq753MkF', 'role': 'junior'},
    ]

    for user_data in users_to_add:
        # Check if the user already exists
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

    session.commit()
    print("Database setup complete.")

