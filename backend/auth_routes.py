"""
Authentication Routes for JunkOS Backend
Handles phone verification, email login, and Apple Sign In
"""

from flask import Blueprint, request, jsonify
import secrets
import hashlib
import jwt
import datetime
from functools import wraps

from models import db, User
from extensions import limiter

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# In-memory storage for demo (use Redis in production)
verification_codes = {}  # phone_number: {code, expires_at}
users_db = {}  # user_id: {id, name, email, phone, password_hash}

# JWT secret — read from env (shared with app_config.Config.JWT_SECRET)
import os
import logging as _logging
_auth_logger = _logging.getLogger(__name__)

JWT_SECRET = os.environ.get('JWT_SECRET', '')
if not JWT_SECRET:
    # Generate a random secret for development; will rotate on restart
    import secrets as _s
    JWT_SECRET = 'dev-only-' + _s.token_hex(32)
    if os.environ.get('FLASK_ENV', 'development') != 'development':
        _auth_logger.warning("JWT_SECRET is not set! Using a random value that will not survive restarts.")

# MARK: - Helper Functions

def generate_verification_code():
    """Generate random 6-digit verification code"""
    return str(secrets.randbelow(900000) + 100000)

def hash_password(password):
    """Simple password hashing (use bcrypt in production)"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token(user_id):
    """Generate JWT token for user"""
    payload = {
        'user_id': user_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_token(token):
    """Verify JWT token and return user_id"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload.get('user_id')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user_id = verify_token(token)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        # Verify user exists in either in-memory or SQLAlchemy store
        if user_id not in users_db and not db.session.get(User, user_id):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(user_id=user_id, *args, **kwargs)
    return decorated_function

# MARK: - Phone Authentication Routes

@auth_bp.route('/send-code', methods=['POST'])
def send_verification_code():
    """Send SMS verification code to phone number"""
    data = request.get_json()
    phone_number = data.get('phoneNumber')
    
    if not phone_number:
        return jsonify({'error': 'Phone number required'}), 400
    
    # Generate and store code
    code = generate_verification_code()
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    
    verification_codes[phone_number] = {
        'code': code,
        'expires_at': expires_at
    }
    
    # Send SMS via Twilio (falls back to console print in dev mode)
    from notifications import send_verification_sms
    send_verification_sms(phone_number, code)

    response_data = {
        'success': True,
        'message': 'Verification code sent',
    }
    # Include code in response only when Twilio is not configured (dev mode)
    import os
    if not os.environ.get("TWILIO_ACCOUNT_SID"):
        response_data['code'] = code

    return jsonify(response_data)

@auth_bp.route('/verify-code', methods=['POST'])
def verify_code():
    """Verify SMS code and create/login user"""
    data = request.get_json()
    phone_number = data.get('phoneNumber')
    code = data.get('code')
    
    if not phone_number or not code:
        return jsonify({'error': 'Phone number and code required'}), 400
    
    # Check if code exists
    if phone_number not in verification_codes:
        return jsonify({'error': 'No verification code found'}), 400
    
    stored_data = verification_codes[phone_number]
    
    # Check if code matches
    if stored_data['code'] != code:
        return jsonify({'error': 'Invalid verification code'}), 401
    
    # Check if code expired
    if datetime.datetime.utcnow() > stored_data['expires_at']:
        del verification_codes[phone_number]
        return jsonify({'error': 'Verification code expired'}), 401
    
    # Code is valid - create or get user
    user_id = find_or_create_user_by_phone(phone_number)
    user = users_db[user_id]
    
    # Clear verification code
    del verification_codes[phone_number]
    
    # Generate token
    token = generate_token(user_id)
    
    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user['id'],
            'name': user.get('name'),
            'email': user.get('email'),
            'phoneNumber': user['phoneNumber']
        }
    })

# MARK: - Email Authentication Routes

@auth_bp.route('/signup', methods=['POST'])
@limiter.limit("3 per minute")
def signup():
    """Create new user account with email/password"""
    from werkzeug.security import generate_password_hash
    data = request.get_json(force=True)
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    if not name and (first_name or last_name):
        name = f"{first_name} {last_name}".strip()

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    # Check if email already exists in DB
    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    # Create user in database
    new_user = User(
        email=email,
        name=name,
        password_hash=generate_password_hash(password),
        role='driver'
    )
    db.session.add(new_user)
    db.session.commit()

    # --- Send welcome email ---
    try:
        from notifications import send_welcome_email
        if new_user.email:
            send_welcome_email(new_user.email, new_user.name)
    except Exception:
        pass  # Notifications must never block the main flow

    # Generate token
    token = generate_token(new_user.id)

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': new_user.id,
            'name': new_user.name,
            'email': new_user.email,
            'phoneNumber': new_user.phone
        }
    })

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """Login with email and password"""
    data = request.get_json(force=True)
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    # Check database
    db_user = User.query.filter_by(email=email).first()
    if not db_user or not db_user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401

    token = generate_token(db_user.id)
    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': db_user.id,
            'name': db_user.name,
            'email': db_user.email,
            'phoneNumber': db_user.phone,
            'role': db_user.role
        }
    })

# MARK: - Apple Sign In

@auth_bp.route('/apple', methods=['POST'])
def apple_signin():
    """Authenticate with Apple Sign In credential"""
    data = request.get_json()
    user_identifier = data.get('userIdentifier')
    email = data.get('email')
    name = data.get('name')
    
    if not user_identifier:
        return jsonify({'error': 'Apple user identifier required'}), 400
    
    # Find or create user
    user = None
    user_id = None
    
    # Search by Apple ID
    for uid, u in users_db.items():
        if u.get('apple_id') == user_identifier:
            user = u
            user_id = uid
            break
    
    # Create new user if not found
    if not user:
        user_id = secrets.token_hex(16)
        users_db[user_id] = {
            'id': user_id,
            'apple_id': user_identifier,
            'email': email,
            'name': name,
            'phoneNumber': None
        }
        user = users_db[user_id]
    
    # Generate token
    token = generate_token(user_id)
    
    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user['id'],
            'name': user.get('name'),
            'email': user.get('email'),
            'phoneNumber': user.get('phoneNumber')
        }
    })

# MARK: - Forgot Password

@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per minute")
def forgot_password():
    """Request a password reset link"""
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    # Check if user exists in database
    db_user = User.query.filter_by(email=email).first()
    if not db_user:
        # Also check in-memory store
        found = any(u.get('email') == email for u in users_db.values())
        if not found:
            return jsonify({'error': 'No account found with that email'}), 404

    # Generate reset token and send via email
    reset_token = secrets.token_urlsafe(32)
    from notifications import send_password_reset_email
    send_password_reset_email(email, reset_token)

    return jsonify({
        'success': True,
        'message': 'Password reset link sent to your email'
    })


# MARK: - Customer Bookings

@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user(user_id):
    """Get current authenticated user profile"""
    # Check database first
    db_user = db.session.get(User, user_id)
    if db_user:
        return jsonify({
            'success': True,
            'user': db_user.to_dict()
        })

    # Check in-memory store
    if user_id in users_db:
        user = users_db[user_id]
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'name': user.get('name'),
                'email': user.get('email'),
                'phoneNumber': user.get('phoneNumber'),
                'role': 'customer'
            }
        })

    return jsonify({'error': 'User not found'}), 404


# MARK: - Seed Admin

@auth_bp.route('/seed-admin', methods=['POST'])
def seed_admin():
    """Promote a user to admin role. Requires a seed secret."""
    import os
    data = request.get_json(force=True)
    secret = data.get('secret')
    email = data.get('email')

    # Use env var — no hardcoded fallback for security
    expected = os.environ.get('ADMIN_SEED_SECRET', '')
    if not expected:
        return jsonify({'error': 'ADMIN_SEED_SECRET is not configured'}), 503
    if secret != expected:
        return jsonify({'error': 'Unauthorized'}), 403

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user.role = 'admin'
    db.session.commit()
    return jsonify({'success': True, 'message': f'{email} is now admin'})


# MARK: - Token Validation

@auth_bp.route('/validate', methods=['POST'])
def validate_token():
    """Validate existing auth token"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    
    if not user_id or user_id not in users_db:
        return jsonify({'error': 'Invalid token'}), 401
    
    user = users_db[user_id]
    
    return jsonify({
        'success': True,
        'user': {
            'id': user['id'],
            'name': user.get('name'),
            'email': user.get('email'),
            'phoneNumber': user.get('phoneNumber')
        }
    })

# MARK: - Helper Functions

def find_or_create_user_by_phone(phone_number):
    """Find existing user by phone or create new one"""
    # Search for existing user
    for user_id, user in users_db.items():
        if user.get('phoneNumber') == phone_number:
            return user_id
    
    # Create new user
    user_id = secrets.token_hex(16)
    users_db[user_id] = {
        'id': user_id,
        'phoneNumber': phone_number,
        'email': None,
        'name': None
    }
    
    return user_id
