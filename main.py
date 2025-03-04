# main.py
"""
This script merges the scheduled_task (sensor reading/logging) and automation_task 
(time-based and sensor-based control) into a single function called combined_task().
It ensures we only read each sensor once per cycle, store that reading, and then 
use that same reading for automation logic, so there's no mismatch.
"""

import atexit
import datetime
import json
from apscheduler.schedulers.background import BackgroundScheduler
from database import Session, SensorLog, DeviceControl, SensorConfig, ControllerConfig
from zoneinfo import ZoneInfo
from sensor import sensor_factory
from actuator import Actuator
from controller import SensorActuatorController

def combined_task():
    """
    Reads all sensors once, logs each reading, and then applies both time-based and
    sensor-based control using the exact same sensor values that were just logged.
    
    1) Read each sensor (from SensorConfig) exactly once.
    2) Log the reading in SensorLog.
    3) Perform time-based control on DeviceControl records with control_mode == "time".
    4) Perform sensor-based control by retrieving the latest logged sensor values
       and using SensorActuatorController with those values.
    """

    now = datetime.datetime.now(ZoneInfo("America/Chicago"))
    
    # ---------------------------
    # 1) Read & Log Sensor Values
    # ---------------------------
    # We'll store a dictionary of { sensor_name: sensor_value } for immediate usage.
    sensor_values = {}  # to hold the readings we just took

    with Session() as session:
        sensor_configs = session.query(SensorConfig).all()

    # For each sensor config, read the sensor once and log it
    for sensor_conf in sensor_configs:
        sensor_name = sensor_conf.sensor_name
        sensor_type = sensor_conf.sensor_type
        
        # Parse any JSON config
        config = {}
        if sensor_conf.config_json:
            try:
                config = json.loads(sensor_conf.config_json)
            except Exception as e:
                print(f"[combined_task] Error parsing config JSON for '{sensor_name}': {e}")
                continue
        
        # Create sensor instance (simulate if needed)
        try:
            sensor_instance = sensor_factory(sensor_type, config, simulate=sensor_conf.simulate)
            value = sensor_instance.read_value()
            
            print(f"[combined_task] {sensor_name}: {value:.2f}")
            
            # Store the reading in sensor_values dictionary
            sensor_values[sensor_name] = value

            # Also log this reading in SensorLog
            with Session() as session:
                session.add(SensorLog(sensor_type=sensor_name, value=value))
                session.commit()

        except Exception as e:
            print(f"[combined_task] Error reading sensor '{sensor_name}': {e}")

    # --------------------------------------------------
    # 2) Perform Time-Based Control (DeviceControl)
    # --------------------------------------------------
    # In time-based control, we do not need sensor readings. We just compare the current time 
    # to each device's auto_time and auto_duration.
    
    with Session() as session:
        devices = session.query(DeviceControl).order_by(DeviceControl.id).all()
    
    for control in devices:
        # If control_mode == "time", we check if we need to turn the device on/off
        if control.control_mode == "time":
            try:
                current_time = now.time()
                # Parse auto_time (HH:MM) if present
                if control.auto_time:
                    try:
                        scheduled_time = datetime.datetime.strptime(control.auto_time, "%H:%M").time()
                    except Exception as e:
                        print(f"[combined_task] Error parsing auto_time for '{control.device_name}': {e}")
                        continue
                else:
                    # If there's no auto_time, skip
                    continue

                # Check if it's time to turn on
                if (current_time.hour == scheduled_time.hour and 
                    current_time.minute == scheduled_time.minute):
                    # Turn on if not already on
                    if not control.current_status:
                        control.current_status = True
                        control.last_auto_on = now
                        print(f"[combined_task] '{control.device_name}' turned ON (time-based) at {now.strftime('%H:%M')}")
                        if control.gpio_pin is not None:
                            actuator = Actuator(control.gpio_pin, control.device_name, simulate=control.simulate)
                            actuator.turn_on()
                            actuator.cleanup()
                else:
                    # If the device is on, check if it's been on for auto_duration
                    if control.current_status and control.last_auto_on:
                        elapsed = (now - control.last_auto_on).total_seconds() / 60.0
                        if elapsed >= control.auto_duration:
                            control.current_status = False
                            print(f"[combined_task] '{control.device_name}' turned OFF (time-based) after {control.auto_duration} min")
                            if control.gpio_pin is not None:
                                actuator = Actuator(control.gpio_pin, control.device_name, simulate=control.simulate)
                                actuator.turn_off()
                                actuator.cleanup()

            except Exception as e:
                print(f"[combined_task] Error processing time-based control for '{control.device_name}': {e}")
    
    # Commit any time-based changes
    with Session() as session:
        session.commit()

    # --------------------------------------------------
    # 3) Perform Sensor-Based Control (ControllerConfig)
    # --------------------------------------------------
    # Now we apply sensor-based rules. We DO NOT read the sensor again; 
    # we use the 'sensor_values' dictionary or the newly logged row from the DB.

    with Session() as session:
        rules = session.query(ControllerConfig).order_by(ControllerConfig.id).all()
    
    for rule in rules:
        try:
            # Retrieve the actuator device from DeviceControl
            with Session() as session:
                actuator_device = session.query(DeviceControl).filter_by(device_name=rule.actuator_name).first()
            if not actuator_device:
                print(f"[combined_task] Actuator '{rule.actuator_name}' not found for rule ID {rule.id}.")
                continue
            if actuator_device.gpio_pin is None:
                print(f"[combined_task] Actuator '{rule.actuator_name}' has no GPIO pin set for rule ID {rule.id}.")
                continue
            
            # Create an actuator instance for this device
            actuator = Actuator(actuator_device.gpio_pin, actuator_device.device_name, simulate=actuator_device.simulate)
            
            # Create our SensorActuatorController with the device's current status
            controller = SensorActuatorController(
                actuator=actuator,
                threshold=rule.threshold,
                control_logic=rule.control_logic,
                hysteresis=rule.hysteresis if rule.hysteresis is not None else 0.5,
                initial_active=actuator_device.current_status
            )

            # We have two ways to get the sensor value:
            #   1) Directly from 'sensor_values' dictionary if the sensor_name matches.
            #   2) Or re-query the DB for the most recent row. We'll demonstrate #1.

            # Check if the sensor name is in the dictionary from above
            if rule.sensor_name in sensor_values:
                sensor_value = sensor_values[rule.sensor_name]
            else:
                print(f"[combined_task] No recent reading found in memory for '{rule.sensor_name}'. "
                      f"Check for name mismatch or if sensor was read.")
                continue
            
            # Now pass that sensor_value to the controller
            controller.check_and_update(sensor_value)

            # Update the DeviceControl record's current_status
            with Session() as session:
                device_to_update = session.query(DeviceControl).filter_by(device_name=rule.actuator_name).first()
                if device_to_update:
                    device_to_update.current_status = controller.active
                    session.commit()

        except Exception as e:
            print(f"[combined_task] Error processing sensor-based rule ID {rule.id}: {e}")

if __name__ == "__main__":
    """
    We now schedule only one job: combined_task(), which merges reading sensors 
    and performing automation logic into a single cycle. This ensures each sensor 
    is read exactly once per cycle, and the same value is used for logging and 
    control decisions.
    """
    from app import app
    from apscheduler.schedulers.background import BackgroundScheduler

    import atexit

    scheduler = BackgroundScheduler()
    # For example, run combined_task() every 60 seconds
    scheduler.add_job(func=combined_task, trigger="interval", seconds=30)
    scheduler.start()

    # Ensure the scheduler shuts down gracefully on exit
    atexit.register(lambda: scheduler.shutdown())

    # Run the Flask application
    app.run(host='0.0.0.0', port=5000, debug=False)
