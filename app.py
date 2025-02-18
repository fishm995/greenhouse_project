# app.py
import datetime
from flask import Flask, request, jsonify, render_template
from auth import generate_token, token_required
from sensor import Sensor
from actuator import Actuator
from database import Session, User, SensorLog
from werkzeug.security import check_password_hash

app = Flask(__name__)

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
        token = generate_token(username)
        return jsonify({'token': token})
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
        'timestamp': datetime.datetime.utcnow().isoformat() + "Z"
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

@app.route('/')
def index():
    """
    Render the main dashboard page.
    """
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
