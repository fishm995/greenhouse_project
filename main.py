# main.py
import atexit
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from database import Session, SensorLog, DeviceControl, SensorConfig
from zoneinfo import ZoneInfo
from sensors import sensor_factory

def scheduled_task():
    """
    Task to periodically read all sensors defined in the SensorConfig table.
    Each sensor's reading is logged to the database using the sensor's unique name.
    """
    # Retrieve sensor configurations from the database.
    with Session() as session:
        sensor_configs = session.query(SensorConfig).all()

    for sensor_conf in sensor_configs:
        sensor_name = sensor_conf.sensor_name
        sensor_type = sensor_conf.sensor_type
        config = {}
        if sensor_conf.config_json:
            import json
            try:
                config = json.loads(sensor_conf.config_json)
            except Exception as e:
                print(f"Error parsing config JSON for sensor '{sensor_name}': {e}")
        simulate = sensor_conf.simulate
        try:
            sensor_instance = sensor_factory(sensor_type, config, simulate=simulate)
            value = sensor_instance.read_value()
            print(f"Scheduled Reading - {sensor_name}: {value:.2f}")
            with Session() as session:
                session.add(SensorLog(sensor_type=sensor_name, value=value))
                session.commit()
        except Exception as e:
            print(f"Error reading sensor '{sensor_name}': {e}")

def auto_control_task():
    """
    Task to check auto control settings for devices and turn them on/off based on schedule.
    """
    now = datetime.datetime.now(ZoneInfo("America/Chicago"))
    current_time = now.time()

    with Session() as session:
        controls = session.query(DeviceControl).filter(
            DeviceControl.mode == 'auto',
            DeviceControl.auto_enabled == True
        ).order_by(DeviceControl.id).all()

        for control in controls:
            try:
                scheduled_time = datetime.datetime.strptime(control.auto_time, "%H:%M").time()
            except Exception as e:
                print(f"Error parsing time for {control.device_name}: {e}")
                continue

            if current_time.hour == scheduled_time.hour and current_time.minute == scheduled_time.minute:
                if not control.current_status:
                    control.current_status = True
                    control.last_auto_on = now
                    print(f"{control.device_name} turned ON by auto mode at {now.strftime('%H:%M')}")
                    # Use actuator if gpio_pin is set.
                    if control.gpio_pin is not None:
                        from actuator import Actuator
                        actuator = Actuator(control.gpio_pin, control.device_name, simulate=False)
                        actuator.turn_on()
                        actuator.cleanup()
            else:
                if control.current_status and control.last_auto_on:
                    elapsed_minutes = (now - control.last_auto_on).total_seconds() / 60.0
                    if elapsed_minutes >= control.auto_duration:
                        control.current_status = False
                        print(f"{control.device_name} turned OFF after {control.auto_duration} minutes")
                        if control.gpio_pin is not None:
                            from actuator import Actuator
                            actuator = Actuator(control.gpio_pin, control.device_name, simulate=False)
                            actuator.turn_off()
                            actuator.cleanup()
        session.commit()

if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scheduled_task, trigger="interval", seconds=60)
    scheduler.add_job(func=auto_control_task, trigger="interval", seconds=60)
    scheduler.start()
    
    atexit.register(lambda: scheduler.shutdown())
    
    from app import app
    app.run(host='0.0.0.0', port=5000, debug=False)
