# app.py
"""
This module defines a Flask web application that exposes a REST API for our greenhouse project.
It includes endpoints for:
  - User authentication
  - Retrieving sensor data and sensor logs
  - Controlling devices (actuators) and their settings
  - Admin operations to create, update, and delete devices, sensors, and controller rules

It uses JWT-based authentication to protect endpoints.
"""

import datetime  # For handling date and time operations
from flask import Flask, request, jsonify, render_template  # Import Flask and helper functions for HTTP requests/responses and HTML rendering
from auth import generate_token, token_required  # Import functions for generating and verifying JWT tokens
from sensor import sensor_factory  # Import sensor_factory to create sensor instances based on configuration
from actuator import Actuator  # Import Actuator class to control hardware actuators (or simulate them)
from database import Session, User, SensorLog, DeviceControl, SensorConfig, ControllerConfig
# Session: SQLAlchemy session for interacting with the database
# User: Model for user authentication data
# SensorLog: Model to store sensor readings
# DeviceControl: Model for actuator settings
# SensorConfig: Model for sensor configuration
# ControllerConfig: Model for rules linking sensors to actuators
from werkzeug.security import check_password_hash  # For verifying password hashes
from zoneinfo import ZoneInfo  # For timezone handling

# Create the Flask application instance.
app = Flask(__name__, static_folder='static')

# -------------------------
# Authentication Endpoint
# -------------------------
@app.route('/login', methods=['POST'])
def login():
    """
    Endpoint to log in a user.
    - Expects a JSON payload with 'username' and 'password'.
    - Checks the provided credentials against the User table.
    - If valid, generates a JWT token that includes the user's role and returns it.
    - If invalid, returns a 401 Unauthorized response.
    """
    data = request.get_json()  # Parse the incoming JSON data
    username = data.get('username')
    password = data.get('password')
    with Session() as session:
        # Query the database for a user with the provided username.
        user = session.query(User).filter_by(username=username).first()
        # Check if user exists and the password hash matches.
        if user and check_password_hash(user.password_hash, password):
            token = generate_token(username, user.role)  # Generate a JWT token
            return jsonify({'token': token, 'role': user.role, 'username': user.username})
        else:
            return jsonify({'message': 'Invalid credentials'}), 401

# -------------------------
# Sensor Endpoints
# -------------------------
@app.route('/api/sensor/logs', methods=['GET'])
@token_required
def sensor_logs(current_user):
    """
    Endpoint to retrieve sensor logs for a given sensor type.
    - Expects a query parameter 'type' to filter logs by sensor type.
    - Returns a JSON array of log entries, each with a timestamp and value.
    """
    sensor_filter = request.args.get('type')  # Get the sensor type from query parameters
    with Session() as session:
        # Query SensorLog for entries matching the sensor type, ordered by timestamp (oldest first)
        logs = session.query(SensorLog).filter(SensorLog.sensor_type == sensor_filter).order_by(SensorLog.timestamp.asc()).all()
        # Create a list of dictionaries with the timestamp (in ISO format) and sensor value.
        return jsonify([{'timestamp': log.timestamp.isoformat(), 'value': log.value} for log in logs])

@app.route('/api/sensors', methods=['GET'])
@token_required
def get_all_sensor_data(current_user):
    """
    Endpoint to retrieve current sensor readings from all sensors defined in SensorConfig.
    - For each sensor, it creates a sensor instance using sensor_factory and calls read_value().
    - Returns a JSON object mapping each sensor's name to its current reading.
    """
    readings = {}
    with Session() as session:
        sensor_configs = session.query(SensorConfig).all()  # Get all sensor configurations
    for sensor_conf in sensor_configs:
        sensor_name = sensor_conf.sensor_name
        sensor_type = sensor_conf.sensor_type
        config = {}
        if sensor_conf.config_json:
            try:
                import json
                config = json.loads(sensor_conf.config_json)  # Parse any extra configuration provided in JSON
            except Exception as e:
                print(f"Error parsing JSON for {sensor_name}: {e}")
        try:
            # Create a sensor instance using the factory, passing the simulation flag from the config.
            sensor = sensor_factory(sensor_type, config, simulate=sensor_conf.simulate)
            value = sensor.read_value()  # Read the sensor value
            readings[sensor_name] = value  # Save the reading in our dictionary
        except Exception as e:
            readings[sensor_name] = None  # If there's an error, store None
            print(f"Error reading sensor '{sensor_name}': {e}")
    return jsonify(readings)

@app.route('/api/sensors/list', methods=['GET'])
@token_required
def list_available_sensors(current_user):
    """
    Endpoint to list all available sensor configurations.
    - Returns a JSON array with each sensor's name, type, simulation flag, and extra configuration.
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
    - Returns a JSON array of devices with their settings, including whether they run in simulation mode.
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
                'simulate': control.simulate  # Include simulation flag.
            })
    return jsonify(result)

@app.route('/api/control/<device_name>/toggle', methods=['POST'])
@token_required
def toggle_control(current_user, device_name):
    """
    Endpoint to toggle a device's on/off status when in manual mode.
    - Flips the current_status and commits the change.
    - If a GPIO pin is configured, it creates an Actuator instance (using the simulate flag)
      and calls the appropriate turn_on() or turn_off() method.
    """
    with Session() as session:
        control = session.query(DeviceControl).filter_by(device_name=device_name).first()
        if not control:
            return jsonify({'message': 'Device not found'}), 404
        if control.mode != 'manual':
            return jsonify({'message': 'Device is not in manual mode'}), 400
        
        # Toggle the current_status (if on, turn off; if off, turn on)
        control.current_status = not control.current_status
        session.commit()
        
        if control.gpio_pin is not None:
            # Create an actuator instance using the device's simulate flag.
            actuator = Actuator(control.gpio_pin, control.device_name, simulate=control.simulate)
            if control.current_status:
                actuator.turn_on()
            else:
                actuator.turn_off()
            actuator.cleanup()
        return jsonify({'device_name': device_name, 'current_status': control.current_status})

@app.route('/api/control/<device_name>/settings', methods=['GET', 'POST'])
@token_required
def control_settings(current_user, device_name):
    """
    GET: Returns the settings for the device specified by device_name.
    POST: Updates the device settings (only allowed for admin and senior users).
          Fields such as auto_time, auto_duration, auto_enabled, control_mode, sensor details,
          and the simulation flag can be updated.
    """
    with Session() as session:
        control = session.query(DeviceControl).filter_by(device_name=device_name).first()
        if not control:
            return jsonify({'message': 'Device not found'}), 404
        if request.method == 'POST':
            if current_user.get('role') not in ['admin', 'senior']:
                return jsonify({'message': 'Not authorized to modify settings'}), 403
            data = request.get_json()
            new_mode = data.get('mode')
            # If trying to set auto mode when auto is disabled, return error.
            if new_mode == "auto" and not control.auto_enabled:
                return jsonify({'message': 'Auto mode is not allowed for this control'}), 400
            
            # Update each setting, using the provided value or falling back to the existing one.
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
            # Update the simulation flag (convert string 'true' to boolean True)
            if 'simulate' in data:
                control.simulate = data.get('simulate') == 'true'
            if new_mode in ['manual', 'auto']:
                control.mode = new_mode
            session.commit()
            return jsonify({'message': 'Settings updated successfully'})
        else:
            # For GET requests, return all the settings for the device as a JSON object.
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
    - Expects a JSON payload with required fields (device_name, device_type, gpio_pin, etc.)
    - Also saves the simulation flag.
    - Only admin users are allowed.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    if not data.get('device_name'):
        return jsonify({'message': 'Device name is required'}), 400
    if not data.get('device_type'):
        return jsonify({'message': 'Device type is required'}), 400

    auto_time = data.get('auto_time')
    if auto_time and not (len(auto_time) == 5 and auto_time[2] == ':'):
        return jsonify({'message': 'Auto Time must be in HH:MM format'}), 400

    if data.get('device_type') == 'actuator' and not data.get('gpio_pin'):
        return jsonify({'message': 'GPIO pin is required for actuators'}), 400

    with Session() as session:
        existing = session.query(DeviceControl).filter_by(device_name=data.get('device_name')).first()
        if existing:
            return jsonify({'message': 'Device already exists'}), 400
        new_device = DeviceControl(
            device_name=data.get('device_name'),
            device_type=data.get('device_type'),
            control_mode=data.get('control_mode', 'time'),
            mode=data.get('mode', 'manual'),
            current_status=False,
            auto_time=auto_time,
            auto_duration=int(data.get('auto_duration')) if data.get('auto_duration') else None,
            auto_enabled=data.get('auto_enabled', True),
            gpio_pin=int(data.get('gpio_pin')) if data.get('gpio_pin') else None,
            sensor_name=data.get('sensor_name'),
            threshold=float(data.get('threshold')) if data.get('threshold') else None,
            control_logic=data.get('control_logic'),
            hysteresis=float(data.get('hysteresis')) if data.get('hysteresis') else None,
            simulate=data.get('simulate') == 'true'  # Store simulation flag as boolean.
        )
        session.add(new_device)
        session.commit()
    return jsonify({'message': 'Device added successfully'})

@app.route('/api/admin/devices', methods=['GET'])
@token_required
def list_devices(current_user):
    """
    Returns a list of all devices (actuators) in the system.
    - Only accessible to admin users.
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
    - Expects a JSON payload with 'device_name' and a 'settings' dictionary.
    - Updates fields such as auto_time, auto_duration, gpio_pin, and simulation flag.
    - Only admin users are allowed.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    device_name = data.get('device_name')
    settings = data.get('settings', {})
    if not device_name:
        return jsonify({'message': 'Device name is required'}), 400

    if 'auto_time' in settings and settings['auto_time'] and not (len(settings['auto_time']) == 5 and settings['auto_time'][2] == ':'):
        return jsonify({'message': 'Auto Time must be in HH:MM format'}), 400

    with Session() as session:
        device = session.query(DeviceControl).filter_by(device_name=device_name).first()
        if not device:
            return jsonify({'message': 'Device not found'}), 404
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
    - Expects a query parameter 'device_name'.
    - Only admin users are allowed.
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
    Adds a new sensor configuration.
    - Expects sensor_name, sensor_type, config_json, and simulate flag.
    - Only admin users are allowed.
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
        existing = session.query(SensorConfig).filter_by(sensor_name=data.get('sensor_name')).first()
        if existing:
            return jsonify({'message': 'Sensor already exists'}), 400
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
    Returns a list of all sensor configurations.
    - Only admin users are allowed.
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
    Updates a sensor configuration.
    - Expects sensor_name and a settings object containing updated values.
    - Only admin users are allowed.
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
    Deletes a sensor configuration.
    - Expects a query parameter 'sensor_name'.
    - Only admin users are allowed.
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
    - Expects sensor_name, actuator_name, threshold, control_logic, and optionally hysteresis.
    - Only admin users are allowed.
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
        existing = session.query(ControllerConfig).filter_by(
            sensor_name=data.get('sensor_name'),
            actuator_name=data.get('actuator_name')
        ).first()
        if existing:
            return jsonify({'message': 'A controller rule for this sensor and actuator already exists.'}), 400
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
    Returns a list of all controller rules.
    - Only admin users are allowed.
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
    - Supports a payload with an optional nested 'settings' dictionary.
    - Only admin users are allowed.
    """
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    # Support nested 'settings' or a flat payload
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
    Deletes a controller rule.
    - Expects a query parameter 'id' for the controller rule.
    - Only admin users are allowed.
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
# Rendering Routes
# -------------------------
@app.route('/')
def index():
    """
    Renders the login page.
    """
    return render_template('index.html')

@app.route('/dashboard')
def dashboard_page():
    """
    Renders the dashboard page.
    """
    return render_template('dashboard.html')

@app.route('/control')
def control_page():
    """
    Renders the control page.
    """
    return render_template('control.html')

@app.route('/settings')
def settings_page():
    """
    Renders the settings page.
    """
    return render_template('settings.html')

@app.route('/admin')
def admin_page():
    """
    Renders the admin page.
    """
    return render_template('admin.html')

if __name__ == '__main__':
    # Start the Flask app on host 0.0.0.0 and port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
