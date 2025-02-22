# main.py
import atexit
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from sensor import Sensor
from database import Session, SensorLog, DeviceControl

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

def auto_control_task():
    session = Session()
    now = datetime.datetime.now()
    current_time = now.time()
    
    # Query for all controls in auto mode that are allowed to run
    controls = session.query(DeviceControl).filter(
        DeviceControl.mode == 'auto',
        DeviceControl.auto_enabled == True
    ).order_by(DeviceControl.id).all()

    for control in controls:
        # Convert the stored auto_time (assumed to be in "HH:MM" format) to a time object.
        try:
            scheduled_time = datetime.datetime.strptime(control.auto_time, "%H:%M").time()
        except Exception as e:
            print(f"Error parsing time for {control.device_name}: {e}")
            continue

         # Check if it's time to turn the control on.
        if current_time.hour == scheduled_time.hour and current_time.minute == scheduled_time.minute:
            if not control.current_status:
                # Turn the control on.
                control.current_status = True
                control.last_auto_on = now
                print(f"{control.device_name} turned ON by auto mode at {now.strftime('%H:%M')}")
        else:
            if control.current_status and control.last_auto_on:
                elapsed_minutes = (now - control.last_auto_on).total_seconds() / 60.0
                if elapsed_minutes >= control.auto_duration:
                    control.current_status = False
                    print(f"{control.device_name} turned OFF after {control.auto_duration} minutes")

    session.commit()

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scheduled_task, trigger="interval", seconds=60)
    scheduler.add_job(func=auto_control_task, trigger="interval", seconds=60)
    scheduler.start()
    
    atexit.register(lambda: scheduler.shutdown())
    
    from app import app
    app.run(host='0.0.0.0', port=5000, debug=False)
