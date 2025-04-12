# app.py
"""
This module defines a Flask web application that exposes a REST API for our greenhouse project.
It provides endpoints for:
  - User authentication
  - Retrieving sensor data and sensor logs
  - Controlling devices (actuators) and their settings
  - Admin operations to create, update, and delete devices, sensors, and controller rules

JWT-based authentication is used to secure these endpoints.
"""

# Import standard and third-party modules
import json
import threading
import datetime  # For handling dates and times
from flask import Flask, request, jsonify, render_template  # For creating a web app and handling HTTP requests/responses
from auth import generate_token, token_required  # For generating JWT tokens and protecting routes with token verification
from sensor import sensor_factory  # Factory function to create sensor instances based on configuration
from actuator import Actuator  # Class to control actuators (or simulate them)
from database import Session, User, SensorLog, DeviceControl, SensorConfig, ControllerConfig
# Explanation:
# - Session: SQLAlchemy session factory to interact with the database.
# - User: Model representing user authentication data.
# - SensorLog: Model to log sensor readings.
# - DeviceControl: Model to store settings for actuators (devices).
# - SensorConfig: Model with configuration details for sensors.
# - ControllerConfig: Model with rules linking sensors to actuators.
from werkzeug.security import check_password_hash  # To verify hashed passwords during login
from zoneinfo import ZoneInfo  # For working with time zones (used in timestamps)
from flask_socketio import SocketIO  # For real-time communication
import ffmpeg_controller  # Import FFmpeg controller functions

# Create a Flask application instance.
# The 'static_folder' parameter tells Flask where to look for static files (CSS, JS, images, etc.).
app = Flask(__name__, static_folder='static')

# Initialize Flask-SocketIO with Flask app.
socketio = SocketIO(app, cors_allowed_origins="*", ping_interval=25, ping_timeout=60, logger=True, engineio_logger=True)

ffmpeg_controller.set_socketio(socketio)
ffmpeg_stop_timer = None
stop_timer_lock = threading.Lock()

# Dictionary to map each Socket.IO connection (session id) to the client's unique ID.
# For example: { 'socket_id1': 'uniqueID123', 'socket_id2': 'uniqueID456' }
session_map = {}

# A lock to protect the shared data structures from race conditions
sessions_lock = threading.Lock()

# -------------------------
# Authentication Endpoint
# -------------------------
@app.route('/login', methods=['POST'])
def login():
    """
    Endpoint to log in a user.
    
    Expected Input (JSON):
      - username: The user's username.
      - password: The user's password.
    
    Process:
      1. Parses the JSON payload from the request.
      2. Retrieves the corresponding user from the database.
      3. Verifies the password using check_password_hash.
      4. If valid, generates a JWT token that includes the username and role.
      5. Returns the token, role, and username in a JSON response.
      6. If credentials are invalid, returns a 401 Unauthorized response.
    """
    data = request.get_json()  # Parse the incoming JSON payload
    username = data.get('username')  # Extract the username from the payload
    password = data.get('password')  # Extract the password from the payload
    with Session() as session:
        # Query the database for a user with the given username
        user = session.query(User).filter_by(username=username).first()
        # Check if the user exists and the provided password matches the stored hash
        if user and check_password_hash(user.password_hash, password):
            # Generate a JWT token with a 1-hour expiration time
            token = generate_token(username, user.role)
            # Return the token along with the user's role and username
            return jsonify({'token': token, 'role': user.role, 'username': user.username})
        else:
            # If credentials are invalid, return a 401 Unauthorized response with an error message
            return jsonify({'message': 'Invalid credentials'}), 401

# -------------------------
# Public Endpoints
# -------------------------
@app.route('/public/status', methods=['GET'])
def public_status():
    """
    Public endpoint that returns current sensor readings and actuator statuses.
    WARNING: Exposing this data publicly can have security implications.
    """
    data = {}

    with Session() as session:
        sensor_configs = session.query(SensorConfig).all()
        sensor_readings = {}
        for sensor in sensor_configs:
            try:
                # Parse configuration, or use an empty dict if not provided.
                config = json.loads(sensor.config_json) if sensor.config_json else {}
                # Log which sensor we're reading, along with its configuration.
                print(f"[Public Status] Reading sensor: {sensor.sensor_name} (type: {sensor.sensor_type}) with config: {config}", flush=True)
                
                # Create the sensor instance (simulate will be True for simulation)
                sensor_instance = sensor_factory(sensor.sensor_type, config, simulate=sensor.simulate)
                # Read the sensor value.
                value = sensor_instance.read_value()
                print(f"[Public Status] Sensor '{sensor.sensor_name}' reading: {value}", flush=True)
                sensor_readings[sensor.sensor_name] = value
            except Exception as e:
                print(f"[Public Status] Error reading sensor '{sensor.sensor_name}': {e}", flush=True)
                sensor_readings[sensor.sensor_name] = None
        data['sensors'] = sensor_readings

        # Retrieve actuator (device) statuses.
        devices = session.query(DeviceControl).all()
        device_status = {}
        for device in devices:
            device_status[device.device_name] = {
                "status": "On" if device.current_status else "Off",
                "control_mode": device.control_mode
            }
        data['devices'] = device_status

    return jsonify(data)


# -------------------------
# Sensor Endpoints
# -------------------------
@app.route('/api/sensor/logs', methods=['GET'])
@token_required
def sensor_logs(current_user):
    """
    Endpoint to retrieve sensor logs filtered by sensor type.
    
    Expected Query Parameter:
      - type: The sensor type or identifier (e.g., "Indoor Temperature").
    
    Process:
      1. Retrieves the 'type' query parameter from the request.
      2. Queries the SensorLog table for log entries that match the sensor type.
      3. Orders the logs by timestamp in ascending order.
      4. Returns the logs as a JSON array, where each entry includes a timestamp (ISO format) and a value.
    """
    sensor_filter = request.args.get('type')  # Get the sensor type filter from the URL query parameters
    with Session() as session:
        # Query SensorLog entries for the given sensor type and order them by timestamp (oldest first)
        logs = session.query(SensorLog).filter(SensorLog.sensor_type == sensor_filter).order_by(SensorLog.timestamp.asc()).all()
        # Build a list of dictionaries representing each log entry and return as JSON
        return jsonify([{'timestamp': log.timestamp.isoformat(), 'value': log.value} for log in logs])

@app.route('/api/sensors', methods=['GET'])
@token_required
def get_all_sensor_data(current_user):
    """
    Endpoint to retrieve current readings from all sensors defined in SensorConfig.
    
    Process:
      1. Retrieve all sensor configurations from the database.
      2. For each sensor, create a sensor instance using sensor_factory.
      3. Read the sensor value by calling read_value().
      4. Store the reading in a dictionary mapping sensor names to their readings.
      5. Return the dictionary as a JSON response.
    """
    readings = {}  # Dictionary to hold sensor readings keyed by sensor name
    with Session() as session:
        # Retrieve all sensor configuration records from the database
        sensor_configs = session.query(SensorConfig).all()
    for sensor_conf in sensor_configs:
        sensor_name = sensor_conf.sensor_name  # Unique identifier for the sensor
        sensor_type = sensor_conf.sensor_type  # Type of sensor (e.g., "temperature")
        config = {}
        if sensor_conf.config_json:
            try:
                # Parse any extra configuration from the config_json field
                import json
                config = json.loads(sensor_conf.config_json)
            except Exception as e:
                print(f"Error parsing JSON for {sensor_name}: {e}")
        try:
            # Create a sensor instance using the factory function
            sensor = sensor_factory(sensor_type, config, simulate=sensor_conf.simulate)
            # Read the sensor's current value
            value = sensor.read_value()
            # Save the sensor reading in the dictionary
            readings[sensor_name] = value
        except Exception as e:
            # If an error occurs, save None as the sensor reading and print an error message
            readings[sensor_name] = None
            print(f"Error reading sensor '{sensor_name}': {e}")
    # Return all sensor readings as a JSON response
    return jsonify(readings)

@app.route('/api/sensors/list', methods=['GET'])
@token_required
def list_available_sensors(current_user):
    """
    Endpoint to list all sensor configurations available in the system.
    
    Process:
      1. Retrieve all SensorConfig records from the database.
      2. Build a list of dictionaries where each dictionary contains:
         - sensor_name: The unique name of the sensor.
         - sensor_type: The type of sensor.
         - simulate: Whether the sensor is in simulation mode.
         - config_json: Additional configuration in JSON format.
      3. Return the list as a JSON response.
    """
    with Session() as session:
        sensors = session.query(SensorConfig).order_by(SensorConfig.id).all()
        result = []
        for sensor in sensors:
            result.append({
                'sensor_name': sensor.sensor_name,
                'sensor_type': sensor.sensor_type,
                'simulate': sensor.simulate,
                'config_json': sensor.config_json
            })
    return jsonify(result)

# -------------------------
# Device Control Endpoints
# -------------------------
@app.route('/api/controls', methods=['GET'])
@token_required
def get_all_controls(current_user):
    """
    Endpoint to retrieve all device control records (actuators).
    
    Process:
      1. Query the DeviceControl table for all records.
      2. For each record, build a dictionary with all the device settings (including simulation flag).
      3. Return the list of devices as a JSON array.
    """
    with Session() as session:
        controls = session.query(DeviceControl).order_by(DeviceControl.id).all()
        result = []
        for control in controls:
            result.append({
                'device_name': control.device_name,
                'device_type': control.device_type,
                'control_mode': control.control_mode,
                'mode': control.mode,
                'current_status': control.current_status,
                'auto_time': control.auto_time,
                'auto_duration': control.auto_duration,
                'auto_enabled': control.auto_enabled,
                'gpio_pin': control.gpio_pin,
                'sensor_name': control.sensor_name,
                'threshold': control.threshold,
                'control_logic': control.control_logic,
                'hysteresis': control.hysteresis,
                'simulate': control.simulate  # Indicates if the device is simulated
            })
    return jsonify(result)

@app.route('/api/control/<device_name>/toggle', methods=['POST'])
@token_required
def toggle_control(current_user, device_name):
    """
    Endpoint to toggle a device's on/off status (only in manual mode).
    
    Process:
      1. Retrieve the device from DeviceControl by device_name.
      2. Check if the device exists and is in manual mode.
      3. Toggle its current_status (if on, turn off; if off, turn on).
      4. Commit the change to the database.
      5. If the device has a GPIO pin set, create an Actuator instance using its simulation flag
         and call turn_on() or turn_off() accordingly.
      6. Return the updated device status as a JSON response.
    """
    with Session() as session:
        control = session.query(DeviceControl).filter_by(device_name=device_name).first()
        if not control:
            return jsonify({'message': 'Device not found'}), 404
        if control.mode != 'manual':
            return jsonify({'message': 'Device is not in manual mode'}), 400
        
        # Toggle the device status (True becomes False, False becomes True)
        control.current_status = not control.current_status
        session.commit()
        
        if control.gpio_pin is not None:
            # Create an Actuator instance using the device's simulate flag.
            actuator = Actuator(int(control.gpio_pin), control.device_name, simulate=control.simulate)
            # Turn on or off the actuator based on the new status.
            if control.current_status:
                actuator.turn_on()
            else:
                actuator.turn_off()
            actuator.cleanup()
        # Return the device's name and updated status.
        return jsonify({'device_name': device_name, 'current_status': control.current_status})

@app.route('/api/control/<device_name>/settings', methods=['GET', 'POST'])
@token_required
def control_settings(current_user, device_name):
    """
    GET: Retrieves the settings for the device specified by device_name.
    POST: Updates the device settings.
          Only admin and senior users are allowed to modify settings.
          Updatable fields include auto_time, auto_duration, auto_enabled, control_mode, sensor details,
          threshold, control_logic, hysteresis, and the simulation flag.
    """
    with Session() as session:
        control = session.query(DeviceControl).filter_by(device_name=device_name).first()
        if not control:
            return jsonify({'message': 'Device not found'}), 404
        if request.method == 'POST':
            # Only allow admin and senior users to update settings.
            if current_user.get('role') not in ['admin', 'senior']:
                return jsonify({'message': 'Not authorized to modify settings'}), 403
            data = request.get_json()
            new_mode = data.get('mode')
            # Prevent switching to auto mode if auto control is not enabled.
            if new_mode == "auto" and not control.auto_enabled:
                return jsonify({'message': 'Auto mode is not allowed for this control'}), 400
            
            # Update each setting with the new value, if provided.
            control.auto_time = data.get('auto_time', control.auto_time)
            control.auto_duration = data.get('auto_duration', control.auto_duration)
            control.auto_enabled = data.get('auto_enabled', control.auto_enabled)
            control.control_mode = data.get('control_mode', control.control_mode)
            control.sensor_name = data.get('sensor_name', control.sensor_name)
            if 'threshold' in data and data['threshold']:
                control.threshold = float(data.get('threshold'))
            if 'control_logic' in data:
                control.control_logic = data.get('control_logic')
            if 'hysteresis' in data and data['hysteresis']:
                control.hysteresis = float(data.get('hysteresis'))
            # Update the simulation flag; converting a string 'true' to boolean True.
            if 'simulate' in data:
                control.simulate = data.get('simulate') == 'true'
            if new_mode in ['manual', 'auto']:
                control.mode = new_mode
            session.commit()
            return jsonify({'message': 'Settings updated successfully'})
        else:
            # For a GET request, return all settings for the device as a JSON object.
            result = {
                'device_name': control.device_name,
                'device_type': control.device_type,
                'control_mode': control.control_mode,
                'mode': control.mode,
                'current_status': control.current_status,
                'auto_time': control.auto_time,
                'auto_duration': control.auto_duration,
                'auto_enabled': control.auto_enabled,
                'gpio_pin': control.gpio_pin,
                'sensor_name': control.sensor_name,
                'threshold': control.threshold,
                'control_logic': control.control_logic,
                'hysteresis': control.hysteresis,
                'simulate': control.simulate
            }
            return jsonify(result)

# -------------------------
# Admin Endpoints for Device CRUD
# -------------------------
@app.route('/api/admin/add_device', methods=['POST'])
@token_required
def add_device(current_user):
    """
    Adds a new device (actuator) to the system.
    
    Expected JSON payload should contain:
      - device_name: Unique name for the device.
      - device_type: The type of device (e.g., "actuator").
      - gpio_pin: The GPIO pin number (required for actuators).
      - Optional fields: control_mode, mode, auto_time, auto_duration, auto_enabled, sensor_name, threshold,
                         control_logic, hysteresis, and simulate (simulation flag).
    
    Only admin users are allowed to perform this operation.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    if not data.get('device_name'):
        return jsonify({'message': 'Device name is required'}), 400
    if not data.get('device_type'):
        return jsonify({'message': 'Device type is required'}), 400

    auto_time = data.get('auto_time')
    # Validate auto_time format "HH:MM" if provided.
    if auto_time and not (len(auto_time) == 5 and auto_time[2] == ':'):
        return jsonify({'message': 'Auto Time must be in HH:MM format'}), 400

    # For actuators, gpio_pin must be provided.
    if data.get('device_type') == 'actuator' and not data.get('gpio_pin'):
        return jsonify({'message': 'GPIO pin is required for actuators'}), 400

    with Session() as session:
        # Check if a device with the given name already exists.
        existing = session.query(DeviceControl).filter_by(device_name=data.get('device_name')).first()
        if existing:
            return jsonify({'message': 'Device already exists'}), 400
        # Create a new DeviceControl record with the provided settings.
        new_device = DeviceControl(
            device_name=data.get('device_name'),
            device_type=data.get('device_type'),
            control_mode=data.get('control_mode', 'time'),
            mode=data.get('mode', 'manual'),
            current_status=False,  # New devices start off.
            auto_time=auto_time,
            auto_duration=int(data.get('auto_duration')) if data.get('auto_duration') else None,
            auto_enabled=data.get('auto_enabled', True),
            gpio_pin=int(data.get('gpio_pin')) if data.get('gpio_pin') else None,
            sensor_name=data.get('sensor_name'),
            threshold=float(data.get('threshold')) if data.get('threshold') else None,
            control_logic=data.get('control_logic'),
            hysteresis=float(data.get('hysteresis')) if data.get('hysteresis') else None,
            simulate=data.get('simulate') == 'true'  # Convert the simulate flag to a boolean.
        )
        session.add(new_device)
        session.commit()
    return jsonify({'message': 'Device added successfully'})

@app.route('/api/admin/devices', methods=['GET'])
@token_required
def list_devices(current_user):
    """
    Retrieves a list of all devices (actuators) in the system.
    Only admin users are allowed to access this endpoint.
    Returns:
      A JSON array of device records, each with all device settings.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    with Session() as session:
        devices = session.query(DeviceControl).order_by(DeviceControl.id).all()
        result = []
        for d in devices:
            result.append({
                'device_name': d.device_name,
                'device_type': d.device_type,
                'control_mode': d.control_mode,
                'mode': d.mode,
                'current_status': d.current_status,
                'auto_time': d.auto_time,
                'auto_duration': d.auto_duration,
                'auto_enabled': d.auto_enabled,
                'gpio_pin': d.gpio_pin,
                'sensor_name': d.sensor_name,
                'threshold': d.threshold,
                'control_logic': d.control_logic,
                'hysteresis': d.hysteresis,
                'simulate': d.simulate
            })
    return jsonify(result)

@app.route('/api/admin/update_device', methods=['POST'])
@token_required
def update_device(current_user):
    """
    Updates an existing device's settings.
    
    Expected JSON payload:
      - device_name: The name of the device to update.
      - settings: A dictionary containing the new settings (e.g., auto_time, auto_duration, gpio_pin, simulate, etc.).
    
    Only admin users are allowed to perform this operation.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    device_name = data.get('device_name')
    settings = data.get('settings', {})
    if not device_name:
        return jsonify({'message': 'Device name is required'}), 400

    # Validate the auto_time format if provided
    if 'auto_time' in settings and settings['auto_time'] and not (len(settings['auto_time']) == 5 and settings['auto_time'][2] == ':'):
        return jsonify({'message': 'Auto Time must be in HH:MM format'}), 400

    with Session() as session:
        device = session.query(DeviceControl).filter_by(device_name=device_name).first()
        if not device:
            return jsonify({'message': 'Device not found'}), 404
        # Update device fields with new settings if provided; otherwise, keep existing values.
        device.mode = settings.get('mode', device.mode)
        device.auto_time = settings.get('auto_time', device.auto_time)
        device.auto_duration = int(settings.get('auto_duration')) if settings.get('auto_duration') else device.auto_duration
        device.auto_enabled = settings.get('auto_enabled', device.auto_enabled)
        device.control_mode = settings.get('control_mode', device.control_mode)
        device.sensor_name = settings.get('sensor_name', device.sensor_name)
        if 'threshold' in settings and settings['threshold']:
            device.threshold = float(settings.get('threshold'))
        if 'control_logic' in settings:
            device.control_logic = settings.get('control_logic')
        if 'hysteresis' in settings and settings['hysteresis']:
            device.hysteresis = float(settings.get('hysteresis'))
        if device.device_type == 'actuator' and settings.get('gpio_pin'):
            device.gpio_pin = int(settings.get('gpio_pin'))
        if 'simulate' in settings:
            device.simulate = settings.get('simulate') == 'true'
        session.commit()
    return jsonify({'message': 'Device updated successfully'})

@app.route('/api/admin/delete_device', methods=['DELETE'])
@token_required
def delete_device(current_user):
    """
    Deletes a device from the system.
    
    Expects a query parameter 'device_name' specifying which device to delete.
    Only admin users are allowed to perform this operation.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    device_name = request.args.get('device_name')
    if not device_name:
        return jsonify({'message': 'Device name is required'}), 400
    with Session() as session:
        device = session.query(DeviceControl).filter_by(device_name=device_name).first()
        if not device:
            return jsonify({'message': 'Device not found'}), 404
        session.delete(device)
        session.commit()
    return jsonify({'message': 'Device deleted successfully'})

# -------------------------
# Admin Endpoints for Sensor CRUD
# -------------------------
@app.route('/api/admin/add_sensor', methods=['POST'])
@token_required
def add_sensor(current_user):
    """
    Adds a new sensor configuration to the system.
    
    Expected JSON payload should include:
      - sensor_name: Unique identifier for the sensor.
      - sensor_type: Type of the sensor (e.g., "temperature").
      - config_json: A JSON-formatted string with additional configuration.
      - simulate: A flag indicating whether to simulate sensor readings.
    
    Only admin users are allowed to perform this operation.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    if not data.get('sensor_name'):
        return jsonify({'message': 'Sensor name is required'}), 400
    if not data.get('sensor_type'):
        return jsonify({'message': 'Sensor type is required'}), 400
    supported_types = ["temperature", "humidity", "co2", "light", "soil_moisture", "wind_speed"]
    if data.get('sensor_type').lower() not in supported_types:
        return jsonify({'message': f"Unsupported sensor type. Supported types: {', '.join(supported_types)}"}), 400

    config_json = data.get('config_json', "{}")
    simulate = data.get('simulate', True)

    with Session() as session:
        # Check if a sensor with the same name already exists.
        existing = session.query(SensorConfig).filter_by(sensor_name=data.get('sensor_name')).first()
        if existing:
            return jsonify({'message': 'Sensor already exists'}), 400
        # Create a new SensorConfig record.
        new_sensor = SensorConfig(
            sensor_name=data.get('sensor_name'),
            sensor_type=data.get('sensor_type').lower(),
            config_json=config_json,
            simulate=simulate
        )
        session.add(new_sensor)
        session.commit()
    return jsonify({'message': 'Sensor added successfully'})

@app.route('/api/admin/sensors', methods=['GET'])
@token_required
def list_sensors(current_user):
    """
    Retrieves a list of all sensor configurations.
    Only admin users are allowed to access this endpoint.
    Returns:
      A JSON array where each entry contains sensor_name, sensor_type, config_json, and simulate flag.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    with Session() as session:
        sensors = session.query(SensorConfig).order_by(SensorConfig.id).all()
        result = []
        for sensor in sensors:
            result.append({
                'sensor_name': sensor.sensor_name,
                'sensor_type': sensor.sensor_type,
                'config_json': sensor.config_json,
                'simulate': sensor.simulate
            })
    return jsonify(result)

@app.route('/api/admin/update_sensor', methods=['POST'])
@token_required
def update_sensor(current_user):
    """
    Updates an existing sensor configuration.
    
    Expected JSON payload:
      - sensor_name: The name of the sensor to update.
      - settings: A dictionary containing the new configuration values.
    Only admin users are allowed to perform this operation.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    sensor_name = data.get('sensor_name')
    settings = data.get('settings', {})
    if not sensor_name:
        return jsonify({'message': 'Sensor name is required'}), 400
    supported_types = ["temperature", "humidity", "co2", "light", "soil_moisture", "wind_speed"]
    if 'sensor_type' in settings and settings.get('sensor_type').lower() not in supported_types:
        return jsonify({'message': f"Unsupported sensor type. Supported types: {', '.join(supported_types)}"}), 400
    with Session() as session:
        sensor = session.query(SensorConfig).filter_by(sensor_name=sensor_name).first()
        if not sensor:
            return jsonify({'message': 'Sensor not found'}), 404
        sensor.sensor_type = settings.get('sensor_type', sensor.sensor_type).lower()
        sensor.config_json = settings.get('config_json', sensor.config_json)
        sensor.simulate = settings.get('simulate', sensor.simulate)
        session.commit()
    return jsonify({'message': 'Sensor updated successfully'})

@app.route('/api/admin/delete_sensor', methods=['DELETE'])
@token_required
def delete_sensor(current_user):
    """
    Deletes a sensor configuration from the system.
    
    Expects a query parameter 'sensor_name' specifying which sensor to delete.
    Only admin users are allowed to perform this operation.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    sensor_name = request.args.get('sensor_name')
    if not sensor_name:
        return jsonify({'message': 'Sensor name is required'}), 400
    with Session() as session:
        sensor = session.query(SensorConfig).filter_by(sensor_name=sensor_name).first()
        if not sensor:
            return jsonify({'message': 'Sensor not found'}), 404
        session.delete(sensor)
        session.commit()
    return jsonify({'message': 'Sensor deleted successfully'})

# -------------------------
# Admin Endpoints for Controller CRUD
# -------------------------
@app.route('/api/admin/add_controller', methods=['POST'])
@token_required
def add_controller(current_user):
    """
    Adds a new controller rule linking a sensor to an actuator.
    
    Expected JSON payload should include:
      - sensor_name: The name of the sensor (must match SensorConfig.sensor_name).
      - actuator_name: The name of the actuator (must match DeviceControl.device_name).
      - threshold: The numeric threshold value.
      - control_logic: A string, either "below" or "above".
      - hysteresis: (Optional) A numeric tolerance to prevent rapid toggling (default is 0.5).
      
    Only admin users are allowed to perform this operation.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    required_fields = ['sensor_name', 'actuator_name', 'threshold', 'control_logic']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'{field} is required.'}), 400
    supported_logic = ['below', 'above']
    if data.get('control_logic') not in supported_logic:
        return jsonify({'message': 'control_logic must be "below" or "above".'}), 400
    with Session() as session:
        # Check if a rule for the same sensor and actuator already exists.
        existing = session.query(ControllerConfig).filter_by(
            sensor_name=data.get('sensor_name'),
            actuator_name=data.get('actuator_name')
        ).first()
        if existing:
            return jsonify({'message': 'A controller rule for this sensor and actuator already exists.'}), 400
        # Create a new controller rule with the provided values.
        new_rule = ControllerConfig(
            sensor_name=data.get('sensor_name'),
            actuator_name=data.get('actuator_name'),
            threshold=float(data.get('threshold')),
            control_logic=data.get('control_logic'),
            hysteresis=float(data.get('hysteresis')) if data.get('hysteresis') else 0.5
        )
        session.add(new_rule)
        session.commit()
    return jsonify({'message': 'Controller rule added successfully'})

@app.route('/api/admin/controllers', methods=['GET'])
@token_required
def list_controllers(current_user):
    """
    Retrieves a list of all controller rules from the system.
    
    Only admin users are allowed to access this endpoint.
    Returns:
      A JSON array where each entry includes the controller rule's id, sensor_name, actuator_name,
      threshold, control_logic, and hysteresis.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    with Session() as session:
        controllers = session.query(ControllerConfig).order_by(ControllerConfig.id).all()
        result = []
        for c in controllers:
            result.append({
                'id': c.id,
                'sensor_name': c.sensor_name,
                'actuator_name': c.actuator_name,
                'threshold': c.threshold,
                'control_logic': c.control_logic,
                'hysteresis': c.hysteresis
            })
    return jsonify(result)

@app.route('/api/admin/update_controller', methods=['POST'])
@token_required
def update_controller(current_user):
    """
    Updates an existing controller rule.
    
    This endpoint supports both a flat payload and a payload with a nested 'settings' dictionary.
    Expected JSON payload should include:
      - id: The identifier of the controller rule to update.
      - Optionally, sensor_name, actuator_name, threshold, control_logic, and hysteresis in a dictionary named 'settings'.
      
    Only admin users are allowed to perform this operation.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    # Support for both flat and nested payload structures.
    if 'settings' in data:
        settings = data['settings']
        controller_id = data.get('id')
    else:
        settings = data
        controller_id = data.get('id')
    if not controller_id:
        return jsonify({'message': 'Controller ID is required'}), 400
    with Session() as session:
        controller = session.query(ControllerConfig).filter_by(id=controller_id).first()
        if not controller:
            return jsonify({'message': 'Controller rule not found'}), 404
        # Update controller fields with new values if provided.
        controller.sensor_name = settings.get('sensor_name', controller.sensor_name)
        controller.actuator_name = settings.get('actuator_name', controller.actuator_name)
        if 'threshold' in settings:
            controller.threshold = float(settings.get('threshold'))
        if 'control_logic' in settings:
            controller.control_logic = settings.get('control_logic')
        if 'hysteresis' in settings:
            controller.hysteresis = float(settings.get('hysteresis'))
        session.commit()
    return jsonify({'message': 'Controller rule updated successfully'})

@app.route('/api/admin/delete_controller', methods=['DELETE'])
@token_required
def delete_controller(current_user):
    """
    Deletes a controller rule from the system.
    
    Expects a query parameter 'id' indicating the ID of the controller rule to delete.
    Only admin users are allowed to perform this operation.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    controller_id = request.args.get('id')
    if not controller_id:
        return jsonify({'message': 'Controller ID is required'}), 400
    with Session() as session:
        controller = session.query(ControllerConfig).filter_by(id=controller_id).first()
        if not controller:
            return jsonify({'message': 'Controller rule not found'}), 404
        session.delete(controller)
        session.commit()
    return jsonify({'message': 'Controller rule deleted successfully'})

# -------------------------
# SocketIO Event Handlers for Managing FFmpeg
# -------------------------

@socketio.on('connect')
def handle_connect():
    # Get the Socket.IO connection ID.
    sid = request.sid

    # Retrieve the uniqueID that the client passed as a query parameter.
    # If not provided (should not happen ideally), use sid as the fallback.
    unique_id = request.args.get('uniqueID', default=sid)

    # Lock to safely update the global session_map.
    with sessions_lock:
        # Map the current connection to its unique ID.
        session_map[sid] = unique_id
        
        # Calculate the total number of unique viewers by taking the set of values.
        unique_viewers = len(set(session_map.values()))
        print(f"[SocketIO] Connection '{sid}' mapped to unique session '{unique_id}'.")
        print(f"[SocketIO] Total unique viewers now: {unique_viewers}")

    # If this is the very first unique viewer and FFmpeg is not running, start the stream.
    if unique_viewers == 1 and not ffmpeg_controller.is_ffmpeg_ready():
        ffmpeg_controller.start_ffmpeg()
    else:
        # If the FFmpeg stream is already running, notify the newly connected client.
        if ffmpeg_controller.is_ffmpeg_ready():
            socketio.emit('ffmpeg_ready', {'ready': True})

@socketio.on('disconnect')
def handle_disconnect():
    # Get the Socket.IO connection ID for the disconnecting client.
    sid = request.sid
    
    with sessions_lock:
        # Remove the connection from the session_map.
        if sid in session_map:
            removed_unique = session_map[sid]
            del session_map[sid]
            print(f"[SocketIO] Connection '{sid}' from unique session '{removed_unique}' disconnected.")

        # Recalculate the total number of unique viewers.
        unique_viewers = len(set(session_map.values()))
        print(f"[SocketIO] Total unique viewers after disconnect: {unique_viewers}")
    
    # If no unique viewers remain, schedule the FFmpeg stream to stop.
    if unique_viewers == 0:
        schedule_stop_ffmpeg()

def schedule_stop_ffmpeg():
    global ffmpeg_stop_timer
    with stop_timer_lock:
        if ffmpeg_stop_timer is None:
            # Schedule stop for 60 seconds after the last disconnect.
            ffmpeg_stop_timer = threading.Timer(60.0, delayed_stop)
            ffmpeg_stop_timer.start()
            print("[SocketIO] Scheduled FFmpeg stop in 60 seconds.")

def delayed_stop():
    global ffmpeg_stop_timer
    # Check if there are any viewers remaining before stopping the stream.
    with sessions_lock:
        unique_viewers = len(set(session_map.values()))
    if unique_viewers == 0:
        print("[SocketIO] No unique viewers remain. Stopping FFmpeg.")
        ffmpeg_controller.stop_ffmpeg()
    else:
        print("[SocketIO] Unique viewers still active; FFmpeg will remain running.")
    with stop_timer_lock:
        ffmpeg_stop_timer = None

# -------------------------
# Rendering Routes
# -------------------------
@app.route('/')
def index():
    """
    Renders and returns the login page.
    """
    return render_template('index.html')

@app.route('/dashboard')
def dashboard_page():
    """
    Renders and returns the dashboard page.
    """
    return render_template('dashboard.html')

@app.route('/control')
def control_page():
    """
    Renders and returns the control page.
    """
    return render_template('control.html')

@app.route('/settings')
def settings_page():
    """
    Renders and returns the settings page.
    """
    return render_template('settings.html')

@app.route('/admin')
def admin_page():
    """
    Renders and returns the admin page.
    """
    return render_template('admin.html')

# -------------------------
# Run the Flask Application
# -------------------------
if __name__ == '__main__':

    # Instead of using app.run(), we use socketio.run() for WebSocket support.
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
