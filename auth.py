# auth.py
import os
import datetime
import jwt
from flask import request, jsonify, abort
from dotenv import load_dotenv
from functools import wraps
from werkzeug.security import check_password_hash

# Load environment variables
load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY', 'default-insecure-key')

def generate_token(username):
    """
    Generate a JWT token for a given username.
    Token expires after 1 hour.
    """
    payload = {
        'username': username,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token

def verify_token(token):
    """
    Verify the JWT token and return its payload if valid.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        abort(401, description="Token expired")
    except jwt.InvalidTokenError:
        abort(401, description="Invalid token")

def token_required(f):
    """
    Decorator to protect routes requiring authentication.
    The client must send the token in the request header 'x-access-token'.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('x-access-token', None)
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = verify_token(token)
            current_user = data['username']
        except Exception as e:
            return jsonify({'message': str(e)}), 401
        return f(current_user, *args, **kwargs)
    return decorated
