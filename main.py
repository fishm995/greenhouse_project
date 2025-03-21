# main.py
"""
This script combines two functionalities into one single task called combined_task():
  1) Reading sensor values (once per cycle) and logging them to the database.
  2) Applying automation logic:
       - Time-based control: turning devices on/off based on the current time.
       - Sensor-based control: using the most recent sensor readings (from our single read)
         to decide whether to change an actuator's state based on controller rules.
         
By combining these, we ensure that each sensor is read only once per cycle,
and the same reading is used both for logging and for automation decisions.
"""

import atexit                             # For registering cleanup functions at program exit
import datetime                           # For working with dates and times
import time
import json                               # For handling JSON data
from apscheduler.schedulers.background import BackgroundScheduler  # Scheduler for running tasks periodically
from database import Session, SensorLog, DeviceControl, SensorConfig, ControllerConfig
from zoneinfo import ZoneInfo             # For handling time zones
from sensor import sensor_factory         # Factory function to create sensor instances based on configuration
from actuator import Actuator             # Class to control actuators (or simulate them)
from controller import SensorActuatorController  # Class to manage sensor-actuator control logic

def combined_task():
    """
    The combined_task function performs the following steps in a single cycle:
    
    1) Read and log sensor values:
       - For every sensor configuration (from SensorConfig), create a sensor instance.
       - Read the sensor's value once.
       - Print the reading for debugging.
       - Save the reading in the SensorLog table.
       - Also store the reading in a dictionary (sensor_values) for immediate use in automation.
       
    2) Time-based Control:
       - Retrieve all devices from DeviceControl.
       - For each device with control_mode set to "time", compare the current time to the scheduled auto_time.
       - Turn the device on if the current time matches the scheduled time.
       - Turn the device off if it has been on for longer than auto_duration.
       
    3) Sensor-based Control:
       - Retrieve all controller rules from ControllerConfig.
       - For each rule, get the corresponding actuator from DeviceControl.
       - Look up the sensor reading from the sensor_values dictionary using the sensor name from the rule.
       - Create a SensorActuatorController instance (which uses the sensor reading to decide if the actuator should toggle).
       - Call check_and_update() with the sensor_value.
       - Update the actuator's current status in the DeviceControl record based on the controller decision.
    """

    # Get the current date and time in the America/Chicago timezone.
    now = datetime.datetime.now(ZoneInfo("America/Chicago"))
    
    # ------------------------------------
    # Step 1: Read and Log Sensor Values
    # ------------------------------------
    with Session() as session:
        sensor_configs = session.query(SensorConfig).all()
    
    # Dictionary to hold the latest readings for each sensor.
    sensor_values = {}
    
    for sensor in sensor_configs:
        try:
            # Parse configuration from JSON, or use an empty dictionary if not provided.
            config = json.loads(sensor.config_json) if sensor.config_json else {}
            # Create the sensor instance. The simulate flag is used as configured.
            sensor_instance = sensor_factory(sensor.sensor_type, config, simulate=sensor.simulate)
            # Read the sensor value. For a DHT22, this might return a dictionary.
            value = sensor_instance.read_value()
            # Save the reading in our in-memory dictionary.
            sensor_values[sensor.sensor_name] = value
            # Log the sensor reading(s) to the database.
            if isinstance(value, dict):
                # If the configuration name ends with "_temp", log the temperature.
                if sensor.sensor_name.lower().endswith("_temp"):
                    print(f"Logging {sensor.sensor_name}: temperature = {value['temperature']}", flush=True)
                    session.add(SensorLog(sensor_type=sensor.sensor_name, value=value["temperature"]))
                # If the configuration name ends with "_humid", log the humidity.
                elif sensor.sensor_name.lower().endswith("_humid"):
                    print(f"Logging {sensor.sensor_name}: humidity = {value['humidity']}", flush=True)
                    session.add(SensorLog(sensor_type=sensor.sensor_name, value=value["humidity"]))
                else:
                    # Fallback: log the entire dictionary if naming doesn't match.
                    session.add(SensorLog(sensor_type=sensor.sensor_name, value=value))
            else:
                # For other sensors that return a single value.
                session.add(SensorLog(sensor_type=sensor.sensor_name, value=value))
                print(f"[combined_task] Logged {sensor.sensor_name} reading: {value}", flush=True)
        except Exception as e:
            print(f"[combined_task] Error reading sensor '{sensor.sensor_name}': {e}", flush=True)
            sensor_values[sensor.sensor_name] = None
    
        session.commit()  # Commit the log entry to the database.
  
    # -------------------------------------------
    # Step 2: Perform Time-Based Control
    # -------------------------------------------
    # Open a single database session for reading and updating device controls.
    with Session() as session:
        # Query for devices that use time-based control.
        devices = session.query(DeviceControl).filter_by(control_mode="time").all()

        # Process each device control record.
        for control in devices:
            try:
                # Parse the scheduled auto_time from the device record.
                if not control.auto_time:
                    # Skip if auto_time is not set.
                    continue

                # Convert auto_time (string, e.g., "08:00") to a time object.
                scheduled_time = datetime.datetime.strptime(control.auto_time, "%H:%M").time()
                current_time = now.time()

                # Check if the current time matches the scheduled time.
                # NOTE: This simple check means that during the entire minute that current_time matches,
                # the condition will be true. Consider adding a guard to only trigger once.
                if current_time.hour == scheduled_time.hour and current_time.minute == scheduled_time.minute:
                    # If the device is not yet on, turn it on.
                    if not control.current_status:
                        control.current_status = True
                        control.last_auto_on = now
                        print(f"[Time Control] Turning ON {control.device_name} at {now.strftime('%H:%M')}", flush=True)
                        if control.gpio_pin is not None:
                            actuator = Actuator(control.gpio_pin, control.device_name, simulate=control.simulate)
                            actuator.turn_on()
                            actuator.cleanup()
                    else:
                        # Device is already on; do nothing or log that it remains on.
                        print(f"[Time Control] {control.device_name} is already ON.", flush=True)
                else:
                    # If the device is on, check if it should now be turned off based on auto_duration.
                    if control.current_status and control.last_auto_on:
                        # Calculate elapsed time in minutes.
                        elapsed = (now - control.last_auto_on).total_seconds() / 60.0
                        if elapsed >= control.auto_duration:
                            control.current_status = False
                            print(f"[Time Control] Turning OFF {control.device_name} after {control.auto_duration} min", flush=True)
                            if control.gpio_pin is not None:
                                actuator = Actuator(control.gpio_pin, control.device_name, simulate=control.simulate)
                                actuator.turn_off()
                                actuator.cleanup()
            except Exception as e:
                # Log any errors encountered for this device.
                print(f"[Time Control] Error processing {control.device_name}: {e}", flush=True)

        # Commit all updates to the database.
        session.commit()
    # -------------------------------------------
    # Step 3: Perform Sensor-Based Control
    # -------------------------------------------
    # Retrieve all controller rules (automation rules linking a sensor to an actuator)
    with Session() as session:
        rules = session.query(ControllerConfig).order_by(ControllerConfig.id).all()
    
    # Loop through each automation rule.
    for rule in rules:
        try:
            # Retrieve the corresponding actuator device from DeviceControl based on the rule.
            with Session() as session:
                actuator_device = session.query(DeviceControl).filter_by(device_name=rule.actuator_name).first()
            if not actuator_device:
                print(f"[combined_task] Actuator '{rule.actuator_name}' not found for rule ID {rule.id}.")
                continue
            if actuator_device.gpio_pin is None:
                print(f"[combined_task] Actuator '{rule.actuator_name}' has no GPIO pin set for rule ID {rule.id}.")
                continue
            
            # Create an actuator instance using the device's simulate flag.
            actuator = Actuator(actuator_device.gpio_pin, actuator_device.device_name, simulate=actuator_device.simulate)
            
            # Create a SensorActuatorController instance with the following parameters:
            # - actuator: The actuator instance created above.
            # - threshold: The threshold from the rule.
            # - control_logic: "below" or "above" from the rule.
            # - hysteresis: The hysteresis value (default 0.5 if not provided).
            # - initial_active: The current status of the actuator (from DeviceControl).
            controller = SensorActuatorController(
                actuator=actuator,
                threshold=rule.threshold,
                control_logic=rule.control_logic,
                hysteresis=rule.hysteresis if rule.hysteresis is not None else 0.5,
                initial_active=actuator_device.current_status
            )
            
            # Retrieve the sensor value for this rule.
            # We use the sensor_values dictionary that was populated in Step 1.
            if rule.sensor_name in sensor_values:
                sensor_value = sensor_values[rule.sensor_name]
            else:
                print(f"[combined_task] No recent reading found in memory for '{rule.sensor_name}'. Check for name mismatch.")
                continue
            
            # Pass the sensor_value to the controller to check and update the actuator state.
            controller.check_and_update(sensor_value)
            
            # Update the DeviceControl record's current_status based on the controller's decision.
            with Session() as session:
                device_to_update = session.query(DeviceControl).filter_by(device_name=rule.actuator_name).first()
                if device_to_update:
                    device_to_update.current_status = controller.active
                    session.commit()
        
        except Exception as e:
            print(f"[combined_task] Error processing sensor-based rule ID {rule.id}: {e}")

# -------------------------------------------
# Main Section: Scheduler and Flask App
# -------------------------------------------
if __name__ == "__main__":
    """
    The main section sets up a background scheduler to run combined_task() periodically.
    This ensures that each sensor is read exactly once per cycle and the same reading is used
    for both logging and automation control.
    """
    # Import the Flask app instance from app.py.
    from app import app
    # Import the BackgroundScheduler to schedule tasks.
    from apscheduler.schedulers.background import BackgroundScheduler
    import atexit  # For graceful shutdown of the scheduler
    
    # Create a BackgroundScheduler instance.
    scheduler = BackgroundScheduler()
    # Add the combined_task to the scheduler to run every 30 seconds (adjust as needed).
    scheduler.add_job(func=combined_task, trigger="interval", seconds=30)
    # Start the scheduler.
    scheduler.start()
    
    # Register a function to shut down the scheduler gracefully when the program exits.
    atexit.register(lambda: scheduler.shutdown())
    
    # Run the Flask web application on host 0.0.0.0 (accessible externally) and port 5000.
    app.run(host='0.0.0.0', port=5000, debug=False)
