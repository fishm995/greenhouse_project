# auth.py

# Import built-in and third-party modules
import os                           # For accessing environment variables
import datetime                     # For working with dates and times
import jwt                          # PyJWT library for creating and decoding JSON Web Tokens
import logging                      # For logging messages (errors, warnings, info)
from flask import request, jsonify, abort  # Flask functions for HTTP requests and responses
from dotenv import load_dotenv      # To load environment variables from a .env file
from functools import wraps         # To create decorators that wrap functions
from werkzeug.security import check_password_hash  # For safely checking hashed passwords

# Configure logging
# Set the logging level to INFO so that INFO, WARNING, and ERROR messages are shown.
logging.basicConfig(level=logging.INFO)
# Create a logger specific to this module.
logger = logging.getLogger(__name__)

# Load environment variables from a .env file if it exists
load_dotenv()

# Retrieve the SECRET_KEY from environment variables.
# This secret key is used for encoding and decoding JWT tokens.
SECRET_KEY = os.environ.get('SECRET_KEY')
# If the SECRET_KEY is not found, raise an error so the application won't run insecurely.
if not SECRET_KEY:
    raise ValueError("No SECRET_KEY set for Flask application. Please set the SECRET_KEY environment variable.")

def generate_token(username, role):
    """
    Generate a JWT token for a given username and role.
    
    The token contains a payload with the following information:
      - 'username': the username of the authenticated user.
      - 'role': the user's role (e.g., admin, senior, junior).
      - 'exp': an expiration time, set to 1 hour from the current UTC time.
    
    The token is then encoded using the SECRET_KEY and the HS256 algorithm.
    
    Parameters:
      username (str): The user's username.
      role (str): The user's role.
    
    Returns:
      str: A JWT token string.
    """
    # Create a payload dictionary that holds the information to be encoded in the token.
    payload = {
        'username': username,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    # Encode the payload into a JWT token using the SECRET_KEY and the HS256 algorithm.
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token

def verify_token(token):
    """
    Verify the provided JWT token and return its payload if the token is valid.
    
    This function attempts to decode the token using the SECRET_KEY and the HS256 algorithm.
    If the token is expired or invalid, appropriate errors are logged and an HTTP 401 Unauthorized 
    response is generated using Flask's abort function.
    
    Parameters:
      token (str): The JWT token to verify.
    
    Returns:
      dict: The decoded payload if the token is valid.
    
    Raises:
      HTTP 401 error: If the token is expired or invalid.
    """
    try:
        # Attempt to decode the token. If successful, the payload (a dictionary) is returned.
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError as e:
        # Log an error if the token has expired.
        logger.error("Token expired: %s", e)
        # Abort the request with a 401 Unauthorized status and an error description.
        abort(401, description="Token expired")
    except jwt.InvalidTokenError as e:
        # Log an error if the token is invalid.
        logger.error("Invalid token: %s", e)
        abort(401, description="Invalid token")
    except Exception as e:
        # Log any other exceptions that occur during token verification.
        logger.error("Error verifying token: %s", e)
        abort(401, description="Token verification failed")

def token_required(f):
    """
    A decorator function to protect routes that require authentication.
    
    It checks for the presence of a JWT token in the request headers (using the 'x-access-token' key).
    If a token is found, it is verified using the verify_token() function.
    If verification succeeds, the payload (containing user information) is passed to the decorated function.
    If the token is missing or invalid, a 401 Unauthorized response is returned.
    
    Parameters:
      f (function): The function to wrap/protect.
    
    Returns:
      function: The wrapped function which now requires a valid token to execute.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get the token from the request headers; default to None if not provided.
        token = request.headers.get('x-access-token', None)
        if not token:
            # Log a warning if the token is missing.
            logger.warning("Token is missing in request headers.")
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            # Verify the token. This will raise an error and abort if the token is invalid.
            data = verify_token(token)
            # Pass the decoded payload as 'current_user' to the wrapped function.
            current_user = data
        except Exception as e:
            logger.error("Token verification failed: %s", e)
            return jsonify({'message': str(e)}), 401
        # Call the original function with current_user added as the first argument.
        return f(current_user, *args, **kwargs)
    return decorated
