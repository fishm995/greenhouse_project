# main.py

import atexit
import datetime
import json
from apscheduler.schedulers.background import BackgroundScheduler import Session, SensorLog, DeviceControl, SensorConfig, ControllerConfig
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
    - For time-based control: Process DeviceControl records with control_mode set to "time".
    - For sensor-based control: Process ControllerConfig rules and update the corresponding
      DeviceControl record's current_status.
    """
    # Get the current time in the specified time zone
    now = datetime.datetime.now(ZoneInfo("America/Chicago"))

    # --- Time-based Control ---
    # Open a session to retrieve all devices from DeviceControl
    with Session() as session:
        devices = session.query(DeviceControl).order_by(DeviceControl.id).all()

    # Process each device that uses time-based control
    for control in devices:
        if control.control_mode == "time":
            try:
                current_time = now.time()
                # Parse the scheduled auto_time (expected format "HH:MM")
                try:
                    scheduled_time = datetime.datetime.strptime(control.auto_time, "%H:%M").time()
                except Exception as e:
                    print(f"Error parsing auto_time for '{control.device_name}': {e}")
                    continue

                # Check if the current time matches the scheduled time
                if current_time.hour == scheduled_time.hour and current_time.minute == scheduled_time.minute:
                    # If the device is not already on, turn it on
                    if not control.current_status:
                        control.current_status = True
                        control.last_auto_on = now
                        print(f"'{control.device_name}' turned ON (time-based) at {now.strftime('%H:%M')}")
                        if control.gpio_pin is not None:
                            # Create an actuator instance and turn it on (simulate=True for testing)
                            actuator = Actuator(control.gpio_pin, control.device_name, simulate=True)
                            actuator.turn_on()
                            actuator.cleanup()
                else:
                    # If the device is on and the scheduled time has passed for the duration,
                    # then turn it off.
                    if control.current_status and control.last_auto_on:
                        elapsed = (now - control.last_auto_on).total_seconds() / 60.0
                        if elapsed >= control.auto_duration:
                            control.current_status = False
                            print(f"'{control.device_name}' turned OFF (time-based) after {control.auto_duration} minutes")
                            if control.gpio_pin is not None:
                                actuator = Actuator(control.gpio_pin, control.device_name, simulate=True)
                                actuator.turn_off()
                                actuator.cleanup()
            except Exception as e:
                print(f"Error processing time-based control for '{control.device_name}': {e}")
    # Commit the time-based control changes in one session
    with Session() as session:
        session.commit()

    # --- Sensor-based Control ---
    # Retrieve all controller rules from the ControllerConfig table
    with Session() as session:
        controller_rules = session.query(ControllerConfig).order_by(ControllerConfig.id).all()

    # Process each sensor-based controller rule
    for rule in controller_rules:
        try:
            # Retrieve the sensor configuration corresponding to this rule from SensorConfig
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

            # Create a sensor instance using the sensor factory
            sensor = sensor_factory(sensor_conf.sensor_type, sensor_config, simulate=sensor_conf.simulate)

            # Retrieve the actuator (device) from DeviceControl corresponding to this rule
            with Session() as session:
                actuator_device = session.query(DeviceControl).filter_by(device_name=rule.actuator_name).first()
            if not actuator_device:
                print(f"Actuator device '{rule.actuator_name}' not found for controller rule {rule.id}.")
                continue
            if actuator_device.gpio_pin is None:
                print(f"Actuator device '{rule.actuator_name}' has no GPIO pin set for controller rule {rule.id}.")
                continue

            # Create an actuator instance for the device
            actuator = Actuator(actuator_device.gpio_pin, actuator_device.device_name, simulate=True)

            # Create the SensorActuatorController with the rule's settings
            controller = SensorActuatorController(
                sensor=sensor,
                actuator=actuator,
                threshold=rule.threshold,
                control_logic=rule.control_logic,
                hysteresis=rule.hysteresis if rule.hysteresis is not None else 0.5
            )

            # Execute the control logic (this will turn the actuator on/off based on the sensor reading)
            controller.check_and_update()

            # Update the DeviceControl record's current_status based on the controller's state
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
    # Schedule the sensor logging task every 60 seconds.
    scheduler.add_job(func=scheduled_task, trigger="interval", seconds=60)
    # Schedule the automation task (both time and sensor-based control) every 60 seconds.
    scheduler.add_job(func=automation_task, trigger="interval", seconds=60)
    scheduler.start()
    
    # Ensure the scheduler shuts down when the application exits.
    atexit.register(lambda: scheduler.shutdown())
    
    # Import and run the Flask app.
    from app import app
    app.run(host='0.0.0.0', port=5000, debug=False)
