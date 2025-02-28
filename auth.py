# auth.py
import os
import datetime
import jwt
import logging
from flask import request, jsonify, abort
from dotenv import load_dotenv
from functools import wraps
from werkzeug.security import check_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("No SECRET_KEY set for Flask application. Please set the SECRET_KEY environment variable.")

def generate_token(username, role):
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
    except jwt.ExpiredSignatureError as e:
        logger.error("Token expired: %s", e)
        abort(401, description="Token expired")
    except jwt.InvalidTokenError as e:
        logger.error("Invalid token: %s", e)
        abort(401, description="Invalid token")
    except Exception as e:
        logger.error("Error verifying token: %s", e)
        abort(401, description="Token verification failed")

def token_required(f):
    """
    Decorator to protect routes requiring authentication.
    The client must send the token in the request header 'x-access-token'.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('x-access-token', None)
        if not token:
            logger.warning("Token is missing in request headers.")
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = verify_token(token)
            # Pass the entire payload as current_user
            current_user = data
        except Exception as e:
            logger.error("Token verification failed: %s", e)
            return jsonify({'message': str(e)}), 401
        return f(current_user, *args, **kwargs)
    return decorated

