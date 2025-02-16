# database.py
import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

Base = declarative_base()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///greenhouse.db')

class User(Base):
    """
    Model for storing user authentication data.
    In production, ensure passwords are securely hashed.
    """
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)  # Hashed password

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
    timestamp = Column(DateTime, default=datetime.datetime.now(datetime.UTC))

# Setup the database engine and session
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

if __name__ == "__main__":
    session = Session()
    # Example: Create a dummy user (password hashing should be used in production)
    from werkzeug.security import generate_password_hash
    user = User(username="admin", password_hash=generate_password_hash("password"))
    session.add(user)
    session.commit()
    print("Database setup complete.")
