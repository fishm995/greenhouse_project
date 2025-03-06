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
    # Create an empty dictionary to store sensor readings.
    # The dictionary will have keys as sensor names and values as the sensor reading.
    sensor_values = {}
    
    # Open a new database session to retrieve all sensor configurations.
    with Session() as session:
        sensor_configs = session.query(SensorConfig).all()
    
    # Loop through each sensor configuration.
    for sensor_conf in sensor_configs:
        sensor_name = sensor_conf.sensor_name  # Unique name for this sensor.
        sensor_type = sensor_conf.sensor_type  # Type of sensor (e.g., "temperature").
        
        # Initialize an empty dictionary to hold any additional configuration.
        config = {}
        if sensor_conf.config_json:
            try:
                # Parse the JSON string into a Python dictionary.
                config = json.loads(sensor_conf.config_json)
            except Exception as e:
                print(f"[combined_task] Error parsing config JSON for '{sensor_name}': {e}")
                continue  # Skip this sensor if configuration parsing fails.
        
        try:
            # Create a sensor instance using the factory.
            # The 'simulate' flag from SensorConfig determines whether we use simulated readings.
            sensor_instance = sensor_factory(sensor_type, config, simulate=sensor_conf.simulate)
            # Read the sensor value.
            value = sensor_instance.read_value()
            # Print the sensor reading for debugging.
            print(f"[combined_task] {sensor_name}: {value:.2f}")
            
            # Store the reading in our in-memory dictionary for later use.
            sensor_values[sensor_name] = value

            # Log the sensor reading in the SensorLog table.
            with Session() as session:
                session.add(SensorLog(sensor_type=sensor_name, value=value))
                session.commit()  # Commit the log entry to the database.

        except Exception as e:
            print(f"[combined_task] Error reading sensor '{sensor_name}': {e}")
    
    # -------------------------------------------
    # Step 2: Perform Time-Based Control
    # -------------------------------------------
    # Open a database session to retrieve all device control records.
    with Session() as session:
        devices = session.query(DeviceControl).order_by(DeviceControl.id).all()
    
    # Loop through each device.
    for control in devices:
        # Only process devices that use "time" control mode.
        if control.control_mode == "time":
            try:
                # Get the current time (as a time object).
                current_time = now.time()
                
                # Check if the device has an auto_time setting.
                if control.auto_time:
                    try:
                        # Convert the auto_time string ("HH:MM") into a time object.
                        scheduled_time = datetime.datetime.strptime(control.auto_time, "%H:%M").time()
                    except Exception as e:
                        print(f"[combined_task] Error parsing auto_time for '{control.device_name}': {e}")
                        continue
                else:
                    # If no auto_time is set, skip time-based control for this device.
                    continue

                # Check if the current time exactly matches the scheduled time.
                if current_time.hour == scheduled_time.hour and current_time.minute == scheduled_time.minute:
                    # If the device is not already on, turn it on.
                    if not control.current_status:
                        control.current_status = True
                        control.last_auto_on = now  # Record the time when the device was turned on.
                        print(f"[combined_task] '{control.device_name}' turned ON (time-based) at {now.strftime('%H:%M')}")
                        # If a GPIO pin is configured, create an actuator instance and turn it on.
                        if control.gpio_pin is not None:
                            actuator = Actuator(control.gpio_pin, control.device_name, simulate=control.simulate)
                            actuator.turn_on()
                            actuator.cleanup()
                else:
                    # If the device is currently on, check how long it has been on.
                    if control.current_status and control.last_auto_on:
                        # Calculate the elapsed time in minutes.
                        elapsed = (now - control.last_auto_on).total_seconds() / 60.0
                        # If the elapsed time exceeds the device's auto_duration, turn it off.
                        if elapsed >= control.auto_duration:
                            control.current_status = False
                            print(f"[combined_task] '{control.device_name}' turned OFF (time-based) after {control.auto_duration} min")
                            if control.gpio_pin is not None:
                                actuator = Actuator(control.gpio_pin, control.device_name, simulate=control.simulate)
                                actuator.turn_off()
                                actuator.cleanup()

            except Exception as e:
                print(f"[combined_task] Error processing time-based control for '{control.device_name}': {e}")
    
    # Commit the changes for time-based control.
    with Session() as session:
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
    #app.run(host='0.0.0.0', port=5000, debug=False)
