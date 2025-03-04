# main.py

import atexit
import datetime
import json
from apscheduler.schedulers.background import BackgroundScheduler 
from database import Session, SensorLog, DeviceControl, SensorConfig, ControllerConfig
from zoneinfo import ZoneInfo
from sensor import sensor_factory
from actuator import Actuator
from controller import SensorActuatorController

def scheduled_task():
    """
    Reads the current values from all sensors defined in the SensorConfig table.
    Each sensor's reading is logged into the SensorLog table using the sensor's unique name.
    """
    # Open a session and retrieve all sensor configurations
    with Session() as session:
        sensor_configs = session.query(SensorConfig).all()

    # Loop over each sensor configuration to read and log its value
    for sensor_conf in sensor_configs:
        sensor_name = sensor_conf.sensor_name
        sensor_type = sensor_conf.sensor_type
        config = {}
        # Parse additional configuration from JSON if available
        if sensor_conf.config_json:
            try:
                config = json.loads(sensor_conf.config_json)
            except Exception as e:
                print(f"Error parsing config JSON for sensor '{sensor_name}': {e}")
        simulate = sensor_conf.simulate  # Determines if we simulate the sensor reading

        try:
            # Instantiate sensor using the sensor factory
            sensor_instance = sensor_factory(sensor_type, config, simulate=simulate)
            value = sensor_instance.read_value()  # Get the sensor reading
            print(f"Scheduled Reading - {sensor_name}: {value:.2f}")

            # Log the sensor reading to the SensorLog table
            with Session() as session:
                session.add(SensorLog(sensor_type=sensor_name, value=value))
                session.commit()
        except Exception as e:
            print(f"Error reading sensor '{sensor_name}': {e}")

def automation_task():
    """
    Processes automation rules for both time-based and sensor-based control.

    - For time-based control, it processes DeviceControl records with control_mode set to "time".
    - For sensor-based control, it processes ControllerConfig rules. For each rule:
        1. It retrieves the corresponding sensor configuration.
        2. It creates sensor and actuator instances.
        3. It instantiates a SensorActuatorController with the actuator's current state.
        4. It calls check_and_update() and then updates the DeviceControl record's current_status.
    """
    now = datetime.datetime.now(ZoneInfo("America/Chicago"))

    # --- Time-based Control ---
    with Session() as session:
        devices = session.query(DeviceControl).order_by(DeviceControl.id).all()
    for control in devices:
        if control.control_mode == "time":
            try:
                current_time = now.time()
                try:
                    scheduled_time = datetime.datetime.strptime(control.auto_time, "%H:%M").time()
                except Exception as e:
                    print(f"Error parsing auto_time for '{control.device_name}': {e}")
                    continue

                if current_time.hour == scheduled_time.hour and current_time.minute == scheduled_time.minute:
                    if not control.current_status:
                        control.current_status = True
                        control.last_auto_on = now
                        print(f"'{control.device_name}' turned ON (time-based) at {now.strftime('%H:%M')}")
                        if control.gpio_pin is not None:
                            actuator = Actuator(control.gpio_pin, control.device_name, simulate=control.simulate)
                            actuator.turn_on()
                            actuator.cleanup()
                else:
                    if control.current_status and control.last_auto_on:
                        elapsed = (now - control.last_auto_on).total_seconds() / 60.0
                        if elapsed >= control.auto_duration:
                            control.current_status = False
                            print(f"'{control.device_name}' turned OFF (time-based) after {control.auto_duration} minutes")
                            if control.gpio_pin is not None:
                                actuator = Actuator(control.gpio_pin, control.device_name, simulate=control.simulate)
                                actuator.turn_off()
                                actuator.cleanup()
            except Exception as e:
                print(f"Error processing time-based control for '{control.device_name}': {e}")
    with Session() as session:
        session.commit()  # Commit time-based control updates.

    # --- Sensor-based Control ---
    with Session() as session:
        controller_rules = session.query(ControllerConfig).order_by(ControllerConfig.id).all()
    for rule in controller_rules:
        try:
            # Retrieve the sensor configuration from SensorConfig.
            with Session() as session:
                sensor_conf = session.query(SensorConfig).filter_by(sensor_name=rule.sensor_name).first()
            if not sensor_conf:
                print(f"Sensor configuration for '{rule.sensor_name}' not found for controller rule for actuator '{rule.actuator_name}'.")
                continue

            sensor_config = {}
            if sensor_conf.config_json:
                try:
                    sensor_config = json.loads(sensor_conf.config_json)
                except Exception as e:
                    print(f"Error parsing sensor config for '{rule.sensor_name}': {e}")
                    continue

            # Create a sensor instance using the sensor_factory.
            sensor = sensor_factory(sensor_conf.sensor_type, sensor_config, simulate=sensor_conf.simulate)

            # Retrieve the corresponding actuator from DeviceControl.
            with Session() as session:
                actuator_device = session.query(DeviceControl).filter_by(device_name=rule.actuator_name).first()
            if not actuator_device:
                print(f"Actuator device '{rule.actuator_name}' not found for controller rule {rule.id}.")
                continue
            if actuator_device.gpio_pin is None:
                print(f"Actuator device '{rule.actuator_name}' has no GPIO pin set for controller rule {rule.id}.")
                continue

            # Create an actuator instance.
            actuator = Actuator(actuator_device.gpio_pin, actuator_device.device_name, simulate=actuator_device.simulate)

            # Create a SensorActuatorController with the current device state.
            controller = SensorActuatorController(
                sensor=sensor,
                actuator=actuator,
                threshold=rule.threshold,
                control_logic=rule.control_logic,
                hysteresis=rule.hysteresis if rule.hysteresis is not None else 0.5,
                initial_active=actuator_device.current_status  # Pass current state.
            )

            # Run the controller logic.
            controller.check_and_update()

            # Update the DeviceControl record's current_status so the UI reflects the correct state.
            with Session() as session:
                device_to_update = session.query(DeviceControl).filter_by(device_name=rule.actuator_name).first()
                if device_to_update:
                    device_to_update.current_status = controller.active
                    session.commit()
        except Exception as e:
            print(f"Error processing controller rule ID {rule.id}: {e}")


if __name__ == "__main__":
    # Create a background scheduler to run tasks periodically.
    scheduler = BackgroundScheduler()
    # Schedule the sensor logging task every 30 seconds.
    scheduler.add_job(func=scheduled_task, trigger="interval", seconds=30)
    # Schedule the automation task (both time and sensor-based control) every 30 seconds.
    scheduler.add_job(func=automation_task, trigger="interval", seconds=30)
    scheduler.start()
    
    # Ensure the scheduler shuts down when the application exits.
    atexit.register(lambda: scheduler.shutdown())
    
    # Import and run the Flask app.
    from app import app
    app.run(host='0.0.0.0', port=5000, debug=False)
