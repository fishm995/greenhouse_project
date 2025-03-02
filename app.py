# app.py
import datetime
from flask import Flask, request, jsonify, render_template
from auth import generate_token, token_required
from sensor import sensor_factory
from actuator import Actuator
from database import Session, User, SensorLog, DeviceControl, SensorConfig
from werkzeug.security import check_password_hash
from zoneinfo import ZoneInfo

app = Flask(__name__, static_folder='static')

# -------------------------
# Authentication Endpoints
# -------------------------
@app.route('/login', methods=['POST'])
def login():
    """
    Login endpoint to authenticate a user and return a JWT token.
    Expects a JSON payload with 'username' and 'password'.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    with Session() as session:
        user = session.query(User).filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            token = generate_token(username, user.role)
            return jsonify({'token': token, 'role': user.role, 'username': user.username})
        else:
            return jsonify({'message': 'Invalid credentials'}), 401

# -------------------------
# Sensor Endpoints
# -------------------------
@app.route('/api/sensor', methods=['GET'])
@token_required
def get_sensor_data(current_user):
    """
    Legacy endpoint to retrieve sensor data from hard-coded sensors.
    (This might be deprecated once /api/sensors is in use.)
    """
    temp_sensor = sensor_factory("temperature", {}, simulate=True)
    humidity_sensor = sensor_factory("humidity", {"pin": 4}, simulate=True)
    temperature = temp_sensor.read_value()
    humidity = humidity_sensor.read_value()
    return jsonify({
        'temperature': temperature,
        'humidity': humidity,
        'timestamp': datetime.datetime.now(ZoneInfo("America/Chicago")).isoformat()
    })

@app.route('/api/sensor/logs', methods=['GET'])
@token_required
def sensor_logs(current_user):
    """
    Returns sensor logs for a given sensor (filtered by sensor name).
    Use ?type=<sensor_name> to filter.
    """
    sensor_filter = request.args.get('type')
    with Session() as session:
        logs = session.query(SensorLog).filter(SensorLog.sensor_type == sensor_filter).order_by(SensorLog.timestamp.asc()).all()
        return jsonify([
            {'timestamp': log.timestamp.isoformat(), 'value': log.value}
            for log in logs
        ])

@app.route('/api/sensors', methods=['GET'])
@token_required
def get_all_sensor_data(current_user):
    """
    Loop through all sensor configurations stored in the SensorConfig table,
    instantiate the appropriate sensor via the factory, and return current readings.
    """
    readings = {}
    with Session() as session:
        sensor_configs = session.query(SensorConfig).all()
    for sensor_conf in sensor_configs:
        sensor_name = sensor_conf.sensor_name
        sensor_type = sensor_conf.sensor_type
        config = {}
        if sensor_conf.config_json:
            try:
                import json
                config = json.loads(sensor_conf.config_json)
            except Exception as e:
                print(f"Error parsing JSON for {sensor_name}: {e}")
        simulate = sensor_conf.simulate
        try:
            sensor = sensor_factory(sensor_type, config, simulate=simulate)
            value = sensor.read_value()
            readings[sensor_name] = value
        except Exception as e:
            readings[sensor_name] = None
            print(f"Error reading sensor '{sensor_name}': {e}")
    return jsonify(readings)

@app.route('/api/sensors/list', methods=['GET'])
@token_required
def list_available_sensors(current_user):
    with Session() as session:
        sensors = session.query(SensorConfig).order_by(SensorConfig.id).all()
        result = []
        for s in sensors:
            result.append({
                'sensor_name': s.sensor_name,
                'sensor_type': s.sensor_type,
                'simulate': s.simulate,
                'config_json': s.config_json
            })
    return jsonify(result)

# -------------------------
# Device Control Endpoints
# -------------------------
@app.route('/api/controls', methods=['GET'])
@token_required
def get_all_controls(current_user):
    with Session() as session:
        controls = session.query(DeviceControl).order_by(DeviceControl.id).all()
        result = []
        for control in controls:
            result.append({
                'device_name': control.device_name,
                'device_type': control.device_type,
                'mode': control.mode,
                'current_status': control.current_status,
                'auto_time': control.auto_time,
                'auto_duration': control.auto_duration,
                'auto_enabled': control.auto_enabled,
                'gpio_pin': control.gpio_pin
            })
    return jsonify(result)

@app.route('/api/control/<device_name>/toggle', methods=['POST'])
@token_required
def toggle_control(current_user, device_name):
    with Session() as session:
        control = session.query(DeviceControl).filter_by(device_name=device_name).first()
        if not control:
            return jsonify({'message': 'Device not found'}), 404
        if control.mode != 'manual':
            return jsonify({'message': 'Device is not in manual mode'}), 400
        
        # Toggle state.
        control.current_status = not control.current_status
        session.commit()
        
        # If gpio_pin is defined, use the Actuator.
        if control.gpio_pin is not None:
            actuator = Actuator(control.gpio_pin, control.device_name, simulate=False)
            if control.current_status:
                actuator.turn_on()
            else:
                actuator.turn_off()
            actuator.cleanup()
        
        return jsonify({'device_name': device_name, 'current_status': control.current_status})

@app.route('/api/control/<device_name>/settings', methods=['GET', 'POST'])
@token_required
def control_settings(current_user, device_name):
    with Session() as session:
        control = session.query(DeviceControl).filter_by(device_name=device_name).first()
        if not control:
            return jsonify({'message': 'Device not found'}), 404

        if request.method == 'POST':
            # Role check is still enforced.
            if current_user.get('role') not in ['admin', 'senior']:
                return jsonify({'message': 'Not authorized to modify settings'}), 403
            data = request.get_json()
            new_mode = data.get('mode')
            if new_mode == "auto" and not control.auto_enabled:
                return jsonify({'message': 'Auto mode is not allowed for this control'}), 400
            
            control.auto_time = data.get('auto_time', control.auto_time)
            control.auto_duration = data.get('auto_duration', control.auto_duration)
            control.auto_enabled = data.get('auto_enabled', control.auto_enabled)
            if new_mode in ['manual', 'auto']:
                control.mode = new_mode
            session.commit()
            return jsonify({'message': 'Settings updated successfully'})
        else:
            result = {
                'device_name': control.device_name,
                'mode': control.mode,
                'current_status': control.current_status,
                'auto_time': control.auto_time,
                'auto_duration': control.auto_duration,
                'auto_enabled': control.auto_enabled,
                'gpio_pin': control.gpio_pin
            }
            return jsonify(result)

# -------------------------
# Admin Endpoints (CRUD for devices)
# -------------------------
@app.route('/api/admin/add_device', methods=['POST'])
@token_required
def add_device(current_user):
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
            mode=data.get('mode', 'manual'),
            current_status=False,
            auto_time=auto_time,
            auto_duration=int(data.get('auto_duration')) if data.get('auto_duration') else None,
            auto_enabled=data.get('auto_enabled', True),
            gpio_pin=int(data.get('gpio_pin')) if data.get('gpio_pin') else None
        )
        session.add(new_device)
        session.commit()
    return jsonify({'message': 'Device added successfully'})

@app.route('/api/admin/devices', methods=['GET'])
@token_required
def list_devices(current_user):
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    with Session() as session:
        devices = session.query(DeviceControl).order_by(DeviceControl.id).all()
        result = []
        for d in devices:
            result.append({
                'device_name': d.device_name,
                'device_type': d.device_type,
                'mode': d.mode,
                'current_status': d.current_status,
                'auto_time': d.auto_time,
                'auto_duration': d.auto_duration,
                'auto_enabled': d.auto_enabled,
                'gpio_pin': d.gpio_pin
            })
    return jsonify(result)

@app.route('/api/admin/update_device', methods=['POST'])
@token_required
def update_device(current_user):
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    device_name = data.get('device_name')
    settings = data.get('settings', {})
    if not device_name:
        return jsonify({'message': 'Device name is required'}), 400
    auto_time = settings.get('auto_time')
    if auto_time and not (len(auto_time) == 5 and auto_time[2] == ':'):
        return jsonify({'message': 'Auto Time must be in HH:MM format'}), 400

    with Session() as session:
        device = session.query(DeviceControl).filter_by(device_name=device_name).first()
        if not device:
            return jsonify({'message': 'Device not found'}), 404
        device.mode = settings.get('mode', device.mode)
        device.auto_time = settings.get('auto_time', device.auto_time)
        device.auto_duration = int(settings.get('auto_duration')) if settings.get('auto_duration') else device.auto_duration
        device.auto_enabled = settings.get('auto_enabled', device.auto_enabled)
        if device.device_type == 'actuator' and settings.get('gpio_pin'):
            device.gpio_pin = int(settings.get('gpio_pin'))
        session.commit()
    return jsonify({'message': 'Device updated successfully'})

@app.route('/api/admin/delete_device', methods=['DELETE'])
@token_required
def delete_device(current_user):
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
# Admin Endpoints (CRUD for Sensors)
# -------------------------
@app.route('/api/admin/add_sensor', methods=['POST'])
@token_required
def add_sensor(current_user):
    # Only admin users can add sensor configurations.
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403

    data = request.get_json()
    if not data.get('sensor_name'):
        return jsonify({'message': 'Sensor name is required'}), 400
    if not data.get('sensor_type'):
        return jsonify({'message': 'Sensor type is required'}), 400

    # Validate sensor_type against supported types
    supported_types = ["temperature", "humidity", "co2", "light", "soil_moisture", "wind_speed"]
    if data.get('sensor_type').lower() not in supported_types:
        return jsonify({'message': f"Unsupported sensor type. Supported types: {', '.join(supported_types)}"}), 400

    # Use provided config_json or default to an empty JSON object.
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
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403
    data = request.get_json()
    sensor_name = data.get('sensor_name')
    new_settings = data.get('settings', {})
    if not sensor_name:
        return jsonify({'message': 'Sensor name is required'}), 400
    if 'sensor_type' in new_settings:
        supported_types = ["temperature", "humidity", "co2", "light", "soil_moisture", "wind_speed"]
        if new_settings.get('sensor_type').lower() not in supported_types:
            return jsonify({'message': f"Unsupported sensor type. Supported types: {', '.join(supported_types)}"}), 400

    with Session() as session:
        sensor = session.query(SensorConfig).filter_by(sensor_name=sensor_name).first()
        if not sensor:
            return jsonify({'message': 'Sensor not found'}), 404
        sensor.sensor_type = new_settings.get('sensor_type', sensor.sensor_type).lower()
        sensor.config_json = new_settings.get('config_json', sensor.config_json)
        sensor.simulate = new_settings.get('simulate', sensor.simulate)
        session.commit()
    return jsonify({'message': 'Sensor updated successfully'})

@app.route('/api/admin/delete_sensor', methods=['DELETE'])
@token_required
def delete_sensor(current_user):
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
# Rendering Routes
# -------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html')

@app.route('/control')
def control_page():
    return render_template('control.html')

@app.route('/settings')
def settings_page():
    return render_template('settings.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
