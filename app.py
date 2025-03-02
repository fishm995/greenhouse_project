# app.py
import datetime
from flask import Flask, request, jsonify, render_template
from auth import generate_token, token_required
from sensor import Sensor
from actuator import Actuator
from database import Session, User, SensorLog, DeviceControl
from werkzeug.security import check_password_hash
from zoneinfo import ZoneInfo
from config import DEVICE_GPIO_MAPPING

app = Flask(__name__, static_folder='static')

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

@app.route('/api/sensors', methods=['GET'])
@token_required
def get_all_sensor_data(current_user):
    """
    Returns a JSON object mapping each sensor's unique name to its current reading.
    """
    from config import SENSOR_CONFIGS
    from sensors import sensor_factory
    readings = {}
    for sensor_conf in SENSOR_CONFIGS:
        sensor_name = sensor_conf.get("sensor_name")
        sensor_type = sensor_conf.get("sensor_type")
        try:
            sensor = sensor_factory(sensor_type, sensor_conf.get("config", {}), simulate=sensor_conf.get("simulate", True))
            value = sensor.read_value()
            readings[sensor_name] = value
        except Exception as e:
            readings[sensor_name] = None
            print(f"Error reading sensor '{sensor_name}': {e}")
    return jsonify(readings)

@app.route('/api/sensor', methods=['GET'])
@token_required
def get_sensor_data(current_user):
    """
    Retrieve sensor data.
    """
    temp_sensor = Sensor('temperature')
    humidity_sensor = Sensor('humidity')
    
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
    sensor_filter = request.args.get('type')
    with Session() as session:
        logs = session.query(SensorLog).filter(SensorLog.sensor_type == sensor_filter).order_by(SensorLog.timestamp.asc()).all()
        return jsonify([
            {
                'timestamp': log.timestamp.isoformat(),
                'value': log.value
            } for log in logs
        ])

@app.route('/api/controls', methods=['GET'])
@token_required
def get_all_controls(current_user):
    with Session() as session:
        controls = session.query(DeviceControl).order_by(DeviceControl.id).all()
        result = []
        for control in controls:
            result.append({
                'device_name': control.device_name,
                'mode': control.mode,
                'current_status': control.current_status,
                'auto_time': control.auto_time,
                'auto_duration': control.auto_duration,
                'auto_enabled': control.auto_enabled
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
        # Toggle the state
        control.current_status = not control.current_status
        session.commit()

        # Use the actuator if a GPIO pin is defined for the device.
        if device_name in DEVICE_GPIO_MAPPING:
            actuator = Actuator(DEVICE_GPIO_MAPPING[device_name], device_name, True)
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
            # Only admin and senior can update settings.
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
            # GET method: return current settings.
            result = {
                'device_name': control.device_name,
                'mode': control.mode,
                'current_status': control.current_status,
                'auto_time': control.auto_time,
                'auto_duration': control.auto_duration,
                'auto_enabled': control.auto_enabled
            }
            return jsonify(result)

@app.route('/api/admin/add_device', methods=['POST'])
@token_required
def add_device(current_user):
    # Enforce admin-only access.
    if current_user.get('role') != 'admin':
        return jsonify({'message': 'Not authorized'}), 403

    data = request.get_json()
    # Validate required fields.
    if not data.get('device_name'):
        return jsonify({'message': 'Device name is required'}), 400
    if not data.get('device_type'):
        return jsonify({'message': 'Device type is required'}), 400

    # Validate auto_time format if provided.
    auto_time = data.get('auto_time')
    if auto_time and not (len(auto_time) == 5 and auto_time[2] == ':'):
        return jsonify({'message': 'Auto Time must be in HH:MM format'}), 400

    # For actuators, require a GPIO pin.
    if data.get('device_type') == 'actuator' and not data.get('gpio_pin'):
        return jsonify({'message': 'GPIO pin is required for actuators'}), 400

    with Session() as session:
        # Check if device already exists.
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

    # Validate auto_time if provided.
    auto_time = settings.get('auto_time')
    if auto_time and not (len(auto_time) == 5 and auto_time[2] == ':'):
        return jsonify({'message': 'Auto Time must be in HH:MM format'}), 400

    with Session() as session:
        device = session.query(DeviceControl).filter_by(device_name=device_name).first()
        if not device:
            return jsonify({'message': 'Device not found'}), 404
        # Update fields.
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


@app.route('/')
def index():
    """
    Render the main login page.
    """
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
