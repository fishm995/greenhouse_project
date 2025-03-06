# auth.py

# Import built-in and third-party modules
import os                           # To access environment variables (like SECRET_KEY)
import datetime                     # To work with dates and times, e.g., for token expiration
import jwt                          # PyJWT library for creating and decoding JSON Web Tokens (JWT)
import logging                      # For logging messages (information, warnings, errors)
from flask import request, jsonify, abort  # Flask functions for handling HTTP requests, returning JSON responses, and aborting requests
from dotenv import load_dotenv      # To load environment variables from a .env file into the program's environment
from functools import wraps         # To create decorators that wrap functions (used for protecting routes)
from werkzeug.security import check_password_hash  # For safely comparing password hashes

# ---------------------------
# Logging Configuration
# ---------------------------
# Configure the logging module to output messages at the INFO level and above.
logging.basicConfig(level=logging.INFO)
# Create a logger object specific to this module for logging messages.
logger = logging.getLogger(__name__)

# ---------------------------
# Load Environment Variables
# ---------------------------
# This loads variables from a .env file into the environment, if the file exists.
load_dotenv()

# Retrieve the SECRET_KEY from the environment.
# The SECRET_KEY is used to sign JWT tokens to ensure they haven't been tampered with.
SECRET_KEY = os.environ.get('SECRET_KEY')
# If the SECRET_KEY is not found, raise an error to prevent running the application insecurely.
if not SECRET_KEY:
    raise ValueError("No SECRET_KEY set for Flask application. Please set the SECRET_KEY environment variable.")

# ---------------------------
# JWT Token Generation
# ---------------------------
def generate_token(username, role):
    """
    Generate a JWT token for a given username and role.
    
    The token payload includes:
      - 'username': the username of the authenticated user.
      - 'role': the user's role (e.g., admin, senior, junior).
      - 'exp': the expiration time of the token, set to 1 hour from now (in UTC).
    
    The payload is encoded using the SECRET_KEY and the HS256 algorithm.
    
    Parameters:
      username (str): The username of the user.
      role (str): The role of the user.
    
    Returns:
      str: The generated JWT token as a string.
    """
    # Create a dictionary (payload) with the user's information and expiration time.
    payload = {
        'username': username,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    # Encode the payload into a JWT token using the SECRET_KEY and HS256 algorithm.
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token

# ---------------------------
# JWT Token Verification
# ---------------------------
def verify_token(token):
    """
    Verify the provided JWT token and return its payload if the token is valid.
    
    This function attempts to decode the token using the SECRET_KEY and the HS256 algorithm.
    If the token is expired, invalid, or any error occurs during decoding, an error is logged
    and the request is aborted with a 401 Unauthorized response.
    
    Parameters:
      token (str): The JWT token to be verified.
    
    Returns:
      dict: The decoded payload if the token is valid.
    
    Raises:
      Aborts the request with a 401 status code if token verification fails.
    """
    try:
        # Attempt to decode the token. If successful, this returns the payload as a dictionary.
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError as e:
        # Log an error if the token has expired.
        logger.error("Token expired: %s", e)
        # Abort the request and return a 401 Unauthorized error with the message "Token expired".
        abort(401, description="Token expired")
    except jwt.InvalidTokenError as e:
        # Log an error if the token is invalid.
        logger.error("Invalid token: %s", e)
        abort(401, description="Invalid token")
    except Exception as e:
        # Log any other errors that occur during token verification.
        logger.error("Error verifying token: %s", e)
        abort(401, description="Token verification failed")

# ---------------------------
# Token Required Decorator
# ---------------------------
def token_required(f):
    """
    A decorator to protect routes that require a valid JWT token.
    
    This decorator checks the request headers for a token under the key 'x-access-token'.
    If a token is found, it verifies the token using verify_token().
    If the token is valid, the decoded payload (which includes user details) is passed as the first argument (current_user)
    to the decorated function. If no token is found or the token is invalid, a 401 Unauthorized response is returned.
    
    Parameters:
      f (function): The function (route) that will be protected by this decorator.
    
    Returns:
      function: The wrapped function that requires a valid token to be executed.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Retrieve the token from the request headers. If the header is missing, token will be None.
        token = request.headers.get('x-access-token', None)
        if not token:
            # Log a warning if the token is missing.
            logger.warning("Token is missing in request headers.")
            # Return a 401 response indicating that the token is missing.
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            # Verify the token. If invalid, verify_token() will abort the request.
            data = verify_token(token)
            # Assign the decoded payload (user information) to current_user.
            current_user = data
        except Exception as e:
            # Log an error if token verification fails.
            logger.error("Token verification failed: %s", e)
            # Return a 401 response with the error message.
            return jsonify({'message': str(e)}), 401
        # Call the original function, passing current_user as the first parameter.
        return f(current_user, *args, **kwargs)
    return decorated
