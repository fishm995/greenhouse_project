# main.py

import atexit
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from database import Session, SensorLog, DeviceControl, SensorConfig, ControllerConfig
from zoneinfo import ZoneInfo
from sensors import sensor_factory
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

def automation_task():
    """
    Task that loops through all controller configurations,
    instantiates a SensorActuatorController for each, and calls check_and_update().
    """
    with Session() as session:
        controllers = session.query(ControllerConfig).order_by(ControllerConfig.id).all()
    for rule in controllers:
        try:
            # Get sensor configuration for this rule.
            # Here we assume the sensor_name in ControllerConfig matches the sensor_name in SensorConfig.
            with Session() as session:
                sensor_conf = session.query(SensorConfig).filter_by(sensor_name=rule.sensor_name).first()
                if not sensor_conf:
                    print(f"Sensor configuration for '{rule.sensor_name}' not found.")
                    continue
            # Build sensor instance.
            import json
            config = {}
            if sensor_conf.config_json:
                try:
                    config = json.loads(sensor_conf.config_json)
                except Exception as e:
                    print(f"Error parsing sensor config for {rule.sensor_name}: {e}")
            sensor = sensor_factory(sensor_conf.sensor_type, config, simulate=sensor_conf.simulate)
            
            # Build actuator instance.
            # Assume actuator is stored in DeviceControl with device_name = rule.actuator_name.
            with Session() as session:
                actuator_device = session.query(DeviceControl).filter_by(device_name=rule.actuator_name).first()
                if not actuator_device:
                    print(f"Actuator device '{rule.actuator_name}' not found.")
                    continue
            if actuator_device.gpio_pin is None:
                print(f"Actuator device '{rule.actuator_name}' has no GPIO pin set.")
                continue
            actuator = Actuator(actuator_device.gpio_pin, actuator_device.device_name, simulate=False)
            
            # Create controller instance with the rule settings.
            controller = SensorActuatorController(
                sensor=sensor,
                actuator=actuator,
                threshold=rule.threshold,
                control_logic=rule.control_logic,
                hysteresis=rule.hysteresis
            )
            # Check sensor reading and update actuator accordingly.
            controller.check_and_update()
        except Exception as e:
            print(f"Error processing controller rule ID {rule.id}: {e}")


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scheduled_task, trigger="interval", seconds=60)
    scheduler.add_job(func=auto_control_task, trigger="interval", seconds=60)
    scheduler.add_job(func=automation_task, trigger="interval", seconds=60)
    scheduler.start()
    
    atexit.register(lambda: scheduler.shutdown())
    
    from app import app
    app.run(host='0.0.0.0', port=5000, debug=False)
