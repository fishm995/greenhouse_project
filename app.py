# app.py
import datetime
from flask import Flask, request, jsonify, render_template
from auth import generate_token, token_required
from sensor import Sensor
from actuator import Actuator
from database import Session, User, SensorLog, DeviceControl
from werkzeug.security import check_password_hash
from zoneinfo import ZoneInfo

app = Flask(__name__)

DEVICE_GPIO_MAPPING = {
    "White Light": 18,
    "Black Light": 23,
    "Heat Lamp": 24,
    "Water Valve": 25,
    "Fresh Air Fan": 12
}

@app.route('/login', methods=['POST'])
def login():
    """
    Login endpoint to authenticate a user and return a JWT token.
    Expects a JSON payload with 'username' and 'password'.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    session = Session()
    user = session.query(User).filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        token = generate_token(username, user.role)
        return jsonify({'token': token, 'role': user.role, 'username': user.username})
    else:
        return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/api/sensor', methods=['GET'])
@token_required
def get_sensor_data(current_user):
    """
    Retrieve sensor data and log readings to the database.
    """
    temp_sensor = Sensor('temperature')
    humidity_sensor = Sensor('humidity')
    
    temperature = temp_sensor.read_value()
    humidity = humidity_sensor.read_value()
    
    #session = Session()
    #session.add(SensorLog(sensor_type='temperature', value=temperature))
    #session.add(SensorLog(sensor_type='humidity', value=humidity))
    #session.commit()
    
    return jsonify({
        'temperature': temperature,
        'humidity': humidity,
        'timestamp': datetime.datetime.now(ZoneInfo("America/Chicago")).isoformat()
    })

@app.route('/api/actuator/<string:action>', methods=['POST'])
@token_required
def control_actuator(current_user, action):
    """
    Control an actuator by turning it 'on' or 'off'.
    Expects a JSON payload with 'pin' and an optional 'device' name.
    """
    data = request.get_json()
    pin = data.get('pin', 18)  # Default pin 18 if not specified
    device = data.get('device', 'Light')
    actuator = Actuator(pin, device)
    
    if action == "on":
        actuator.turn_on()
    elif action == "off":
        actuator.turn_off()
    else:
        return jsonify({'message': 'Invalid action'}), 400
    
    return jsonify({'message': f'{device} turned {action}'}), 200

@app.route('/api/controls', methods=['GET'])
@token_required
def get_all_controls(current_user):
    session = Session()
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
    session = Session()
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
        actuator = Actuator(DEVICE_GPIO_MAPPING[device_name], device_name)
        if control.current_status:
            actuator.turn_on()
        else:
            actuator.turn_off()
        
    return jsonify({'device_name': device_name, 'current_status': control.current_status})

@app.route('/api/control/<device_name>/settings', methods=['GET', 'POST'])
@token_required
def control_settings(current_user, device_name):
    session = Session()
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
    
    # GET method: return current settings
    result = {
        'device_name': control.device_name,
        'mode': control.mode,
        'current_status': control.current_status,
        'auto_time': control.auto_time,
        'auto_duration': control.auto_duration,
        'auto_enabled': control.auto_enabled
    }
    return jsonify(result)

@app.route('/')
def index():
    """
    Render the main dashboard page.
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
