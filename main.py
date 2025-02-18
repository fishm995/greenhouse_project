# main.py
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from sensor import Sensor

def scheduled_task():
    """
    Task to periodically read sensor data.
    This can be expanded to include control logic.
    """
    #Create sensor objects
    temp_sensor = Sensor('temperature')
    humidity_sensor = Sensor('humidity')

    #Read sensor values and print for diagnostics
    temperature = temp_sensor.read_value()
    humidity = humidity_sensor.read_value()
    print(f"Scheduled Sensor Readings - Temperature: {temperature:.2f}°C, Humidity: {humidity:.2f}%")

    #Log sensor data to the database
    session = Session()
    session.add(SensorLog(sensor_type='temperature', value=temperature))
    session.add(SensorLog(sensor_type='humidity', value=humidity))
    session.commit()


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scheduled_task, trigger="interval", seconds=60)
    scheduler.start()
    
    atexit.register(lambda: scheduler.shutdown())
    
    from app import app
    app.run(host='0.0.0.0', port=5000, debug=True)
