# main.py

import atexit
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from database import Session, SensorLog, DeviceControl, SensorConfig
from zoneinfo import ZoneInfo
from sensor import sensor_factory
from actuator import Actuator
from controller import SensorActuatorController

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

def automation_task():
    """
    Loop through all DeviceControl records and apply control based on the chosen control_mode.
    """
    with Session() as session:
        controls = session.query(DeviceControl).order_by(DeviceControl.id).all()
    for control in controls:
        try:
            if control.control_mode == "time":
                # Time-based control logic.
                now = datetime.datetime.now(ZoneInfo("America/Chicago"))
                current_time = now.time()
                try:
                    scheduled_time = datetime.datetime.strptime(control.auto_time, "%H:%M").time()
                except Exception as e:
                    print(f"Error parsing auto_time for {control.device_name}: {e}")
                    continue

                if current_time.hour == scheduled_time.hour and current_time.minute == scheduled_time.minute:
                    if not control.current_status:
                        control.current_status = True
                        control.last_auto_on = now
                        print(f"{control.device_name} turned ON by time-based control at {now.strftime('%H:%M')}")
                        if control.gpio_pin is not None:
                            actuator = Actuator(control.gpio_pin, control.device_name, simulate=False)
                            actuator.turn_on()
                            actuator.cleanup()
                else:
                    if control.current_status and control.last_auto_on:
                        elapsed = (now - control.last_auto_on).total_seconds() / 60.0
                        if elapsed >= control.auto_duration:
                            control.current_status = False
                            print(f"{control.device_name} turned OFF after {control.auto_duration} minutes")
                            if control.gpio_pin is not None:
                                actuator = Actuator(control.gpio_pin, control.device_name, simulate=False)
                                actuator.turn_off()
                                actuator.cleanup()
            elif control.control_mode == "sensor":
                # Sensor-based control.
                # Retrieve sensor configuration using control.sensor_name.
                with Session() as session:
                    sensor_conf = session.query(SensorConfig).filter_by(sensor_name=control.sensor_name).first()
                if not sensor_conf:
                    print(f"Sensor configuration for '{control.sensor_name}' not found for device '{control.device_name}'.")
                    continue
                import json
                sensor_config = {}
                if sensor_conf.config_json:
                    try:
                        sensor_config = json.loads(sensor_conf.config_json)
                    except Exception as e:
                        print(f"Error parsing sensor config for '{control.sensor_name}': {e}")
                        continue
                sensor = sensor_factory(sensor_conf.sensor_type, sensor_config, simulate=sensor_conf.simulate)
                # Create an actuator instance.
                if control.gpio_pin is None:
                    print(f"Device '{control.device_name}' has no GPIO pin set.")
                    continue
                actuator = Actuator(control.gpio_pin, control.device_name, simulate=False)
                # Create controller instance.
                controller = SensorActuatorController(
                    sensor=sensor,
                    actuator=actuator,
                    threshold=control.threshold,
                    control_logic=control.control_logic,
                    hysteresis=control.hysteresis if control.hysteresis is not None else 0.5
                )
                # Execute control logic.
                controller.check_and_update()
            else:
                print(f"Unknown control mode for device '{control.device_name}'")
        except Exception as e:
            print(f"Error processing device '{control.device_name}': {e}")
    with Session() as session:
        session.commit()


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scheduled_task, trigger="interval", seconds=60)
    scheduler.add_job(func=automation_task, trigger="interval", seconds=60)
    scheduler.start()
    
    atexit.register(lambda: scheduler.shutdown())
    
    from app import app
    app.run(host='0.0.0.0', port=5000, debug=False)
