"""
Authentication Routes for Umuve Backend
Handles phone verification, email login, Apple Sign In, password reset.

Audit remediation 2026-09-10 (findings F01, F19, F20):
  * Apple Sign In accepts ONLY a verified identity_token (signature, issuer,
    audience, expiry, nonce, subject). Email / email_verified come from the
    verified claims, never from the request body. The legacy
    "userIdentifier only" branch is gone.
  * Phone identities, OTP challenges and password-reset tokens are persisted
    (models_auth.py). Nothing auth-related lives in process memory any more.
  * Every JWT carries a session version claim ``tv`` that must match
    ``User.token_version``; any password / role / status change or org
    membership removal bumps it and revokes outstanding tokens. Tokens that
    predate the claim are treated as version 0 until the user's next login,
    which sunsets them (see ``issue_session_token``).
  * Base auth rejects any user whose status is not ``active``.
"""

from flask import Blueprint, request, jsonify
import secrets
import hashlib
import jwt
import datetime
import os
import re
import unicodedata
import logging as _logging
from functools import wraps
import requests
from typing import Optional, Dict, Tuple
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Referral, generate_referral_code
import models_auth  # noqa: F401  (registers otp_challenges / password_reset_tokens for create_all)
from models_auth import OtpChallenge, PasswordResetToken
from extensions import limiter
from app_config import is_production

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

_auth_logger = _logging.getLogger(__name__)


def _load_jwt_secret():
    """JWT signing secret. Fails closed: in production a missing JWT_SECRET
    aborts startup instead of silently minting tokens with a random,
    per-process secret (which also made portal and base tokens disagree)."""
    secret = os.environ.get('JWT_SECRET', '')
    if secret:
        return secret
    if is_production():
        raise RuntimeError(
            "FATAL: JWT_SECRET must be set in production. Refusing to start "
            "with an auto-generated signing secret."
        )
    return 'dev-only-' + secrets.token_hex(32)


JWT_SECRET = _load_jwt_secret()

ACCESS_TOKEN_TTL = datetime.timedelta(days=30)
REFRESH_GRACE = datetime.timedelta(days=7)
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_SENDS_PER_HOUR = 5

RESET_TOKEN_TTL_MINUTES = 60
RESET_REQUESTS_PER_HOUR = 3

# Apple public keys cache (expires after 24 hours)
_apple_keys_cache = {
    'keys': None,
    'fetched_at': None
}

APPLE_ISSUER = 'https://appleid.apple.com'
APPLE_AUDIENCES = [
    a.strip() for a in os.environ.get(
        'APPLE_CLIENT_IDS', 'com.goumuve.app,com.goumuve.pro'
    ).split(',') if a.strip()
]

# MARK: - Normalisation helpers


def normalize_email(value) -> Optional[str]:
    """Safe email normalisation: NFKC, trimmed, lower-cased. Returns None for
    empty or malformed input (whitespace / control characters, no '@')."""
    if not value:
        return None
    email = unicodedata.normalize('NFKC', str(value)).strip().lower()
    if not email or '@' not in email or len(email) > 254:
        return None
    if any(ch.isspace() or ord(ch) < 32 for ch in email):
        return None
    return email


def normalize_phone(raw) -> Optional[str]:
    """Return an E.164 string ('+15615550100') or None if unparseable.
    Bare 10-digit / leading-1 11-digit numbers are treated as NANP."""
    if not raw:
        return None
    s = str(raw).strip()
    has_plus = s.startswith('+')
    digits = re.sub(r'\D', '', s)
    if not digits:
        return None
    if has_plus:
        return '+' + digits if 8 <= len(digits) <= 15 else None
    if len(digits) == 10:
        return '+1' + digits
    if len(digits) == 11 and digits[0] == '1':
        return '+' + digits
    return None


def password_policy_error(password) -> Optional[str]:
    """One password policy for every credential-setting path."""
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        return 'Password must be at least {} characters'.format(MIN_PASSWORD_LENGTH)
    if len(password) > MAX_PASSWORD_LENGTH:
        return 'Password is too long'
    return None


def _client_ip():
    fwd = request.headers.get('X-Forwarded-For', '')
    return (fwd.split(',')[0].strip() if fwd else request.remote_addr) or None


# MARK: - Apple token validation

def get_apple_public_keys() -> Optional[Dict]:
    """Fetch Apple's public keys for JWT verification (cached for 24 hours)"""
    now = datetime.datetime.utcnow()

    # Check cache
    if _apple_keys_cache['keys'] and _apple_keys_cache['fetched_at']:
        age = (now - _apple_keys_cache['fetched_at']).total_seconds()
        if age < 86400:  # 24 hours
            return _apple_keys_cache['keys']

    # Fetch from Apple
    try:
        response = requests.get('https://appleid.apple.com/auth/keys', timeout=5)
        if response.status_code == 200:
            keys = response.json()
            _apple_keys_cache['keys'] = keys
            _apple_keys_cache['fetched_at'] = now
            return keys
    except Exception as e:
        _auth_logger.error(f"Failed to fetch Apple public keys: {e}")

    return None


def validate_apple_identity_token(identity_token: str, nonce: Optional[str] = None) -> Optional[Dict]:
    """Validate an Apple identity token: RS256 signature against Apple's JWKS,
    issuer, audience, expiry, required subject, and nonce (when the token
    carries one, the caller must supply the matching raw or SHA-256 nonce).
    Returns the verified claims or None."""
    try:
        unverified_header = jwt.get_unverified_header(identity_token)
        kid = unverified_header.get('kid')
        if not kid:
            _auth_logger.error("No kid in Apple identity token")
            return None

        keys_response = get_apple_public_keys()
        if not keys_response:
            _auth_logger.error("Could not fetch Apple public keys")
            return None

        public_key = None
        for key in keys_response.get('keys', []):
            if key.get('kid') == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break
        if not public_key:
            _auth_logger.error(f"No matching Apple public key for kid: {kid}")
            return None

        payload = jwt.decode(
            identity_token,
            public_key,
            algorithms=['RS256'],
            audience=APPLE_AUDIENCES,
            issuer=APPLE_ISSUER,
            options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']},
        )

        sub = payload.get('sub')
        if not sub or not isinstance(sub, str):
            _auth_logger.error("Apple identity token has no subject")
            return None

        token_nonce = payload.get('nonce')
        if token_nonce:
            provided = (nonce or '').strip()
            if not provided:
                _auth_logger.error("Apple identity token carries a nonce but none was supplied")
                return None
            hashed = hashlib.sha256(provided.encode()).hexdigest()
            if not (secrets.compare_digest(str(token_nonce), hashed)
                    or secrets.compare_digest(str(token_nonce), provided)):
                _auth_logger.error("Nonce mismatch in Apple identity token")
                return None

        return payload

    except jwt.ExpiredSignatureError:
        _auth_logger.error("Apple identity token expired")
        return None
    except jwt.InvalidTokenError as e:
        _auth_logger.error(f"Invalid Apple identity token: {e}")
        return None
    except Exception as e:
        _auth_logger.error(f"Error validating Apple identity token: {e}")
        return None


def _claim_true(value) -> bool:
    """Apple sends email_verified as bool or the strings 'true'/'false'."""
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() == 'true'


def generate_verification_code():
    """Generate random 6-digit verification code"""
    return str(secrets.randbelow(900000) + 100000)


def hash_password(password):
    """Secure password hashing using Werkzeug (scrypt/pbkdf2)"""
    return generate_password_hash(password)


def verify_password(stored_hash: str, provided_password: str) -> bool:
    """Verify password against Werkzeug hashes with legacy sha256 fallback.
    """
    if not stored_hash or not provided_password:
        return False

    # Werkzeug hashes usually start with an algorithm prefix, e.g. "scrypt:" / "pbkdf2:"
    if ":" in stored_hash:
        try:
            return check_password_hash(stored_hash, provided_password)
        except Exception:
            return False

    # Legacy fallback: direct sha256 comparison for old accounts
    legacy_hash = hashlib.sha256(provided_password.encode()).hexdigest()
    return secrets.compare_digest(stored_hash, legacy_hash)


def _upgrade_legacy_hash(user, password):
    """Re-hash an unsalted legacy sha256 password with Werkzeug on a
    successful login. Setting password_hash bumps token_version via the model
    listener; the caller mints the new token afterwards so the current login
    is unaffected."""
    if user.password_hash and ':' not in user.password_hash:
        user.password_hash = generate_password_hash(password)


# MARK: - Session tokens

def _user_token_version(user) -> int:
    return int(getattr(user, 'token_version', 0) or 0)


def account_is_active(user) -> bool:
    return user is not None and (getattr(user, 'status', None) or 'active') == 'active'


def generate_token(user_id):
    """Generate a 30-day access JWT carrying the user's current session version."""
    user = db.session.get(User, user_id)
    now = datetime.datetime.utcnow()
    payload = {
        'user_id': user_id,
        'tv': _user_token_version(user) if user else 0,
        'iat': now,
        'exp': now + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def issue_session_token(user):
    """Login path. The first login after the token_version rollout moves the
    user from version 0 to 1 so tokens minted before the ``tv`` claim existed
    (treated as version 0) stop working — legacy tokens are honoured only
    until the next login. Later logins do not bump (other devices stay in)."""
    if _user_token_version(user) == 0:
        user.token_version = 1
    db.session.commit()
    return generate_token(user.id)


def _decode_access_token(token, verify_exp=True):
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, JWT_SECRET, algorithms=['HS256'],
            options={'verify_exp': verify_exp},
        )
    except jwt.InvalidTokenError:
        return None
    # Audience separation: portal tokens (typ=portal) are not base tokens.
    if payload.get('typ') not in (None, 'access'):
        return None
    if not payload.get('user_id'):
        return None
    return payload


def authenticate_access_token(token, allow_expired_within=None) -> Tuple[Optional[User], str]:
    """Resolve a base JWT to a usable User.

    Returns (user, reason). ``user`` is None on failure and ``reason`` is a
    client-safe message. Checks: signature/expiry, user exists, account
    status is active, and the token's session version matches.
    ``allow_expired_within`` (timedelta) lets /refresh accept a token expired
    by at most that long."""
    payload = _decode_access_token(token, verify_exp=allow_expired_within is None)
    if not payload:
        return None, 'Unauthorized'
    if allow_expired_within is not None:
        exp = payload.get('exp')
        if not exp:
            return None, 'Unauthorized'
        exp_date = datetime.datetime.utcfromtimestamp(exp)
        if datetime.datetime.utcnow() > exp_date + allow_expired_within:
            return None, 'Token expired beyond refresh period'
    user = db.session.get(User, payload['user_id'])
    if user is None:
        return None, 'Unauthorized'
    status = getattr(user, 'status', None) or 'active'
    if status == 'deleted':
        return None, 'Account deleted'
    if status != 'active':
        return None, 'Account suspended'
    if int(payload.get('tv', 0) or 0) != _user_token_version(user):
        return None, 'Session expired. Please sign in again.'
    return user, ''


def verify_token(token):
    """Verify JWT token and return user_id (None if invalid, revoked, or the
    account is not active)."""
    user, _ = authenticate_access_token(token)
    return user.id if user else None


def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user, reason = authenticate_access_token(token)
        if not user:
            return jsonify({'error': reason or 'Unauthorized'}), 401
        return f(user_id=user.id, *args, **kwargs)
    return decorated_function


def optional_auth(f):
    """Decorator that passes user_id if authenticated, None otherwise."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user, _ = authenticate_access_token(token) if token else (None, '')
        return f(user_id=user.id if user else None, *args, **kwargs)
    return decorated_function


def _user_payload(user):
    return {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'phoneNumber': user.phone,
        'role': user.role,
    }


# MARK: - Phone Authentication Routes

@auth_bp.route('/send-code', methods=['POST'])
@limiter.limit("5 per minute")
def send_verification_code():
    """Send SMS verification code to phone number"""
    data = request.get_json(silent=True) or {}
    raw_phone = (data.get('phoneNumber') or data.get('phone') or '').strip()

    if not raw_phone:
        return jsonify({'error': 'Phone number required'}), 400
    phone = normalize_phone(raw_phone)
    if not phone:
        return jsonify({'error': 'Enter a valid phone number'}), 400

    now = datetime.datetime.utcnow()

    # Per-identity throttle (independent of the per-IP limiter).
    recent = (
        db.session.query(OtpChallenge)
        .filter(OtpChallenge.identity == phone,
                OtpChallenge.created_at >= now - datetime.timedelta(hours=1))
        .count()
    )
    if recent >= OTP_SENDS_PER_HOUR:
        return jsonify({'error': 'Too many codes requested. Try again later.'}), 429

    # A new code supersedes any open challenge for this phone.
    (db.session.query(OtpChallenge)
     .filter(OtpChallenge.identity == phone, OtpChallenge.consumed_at.is_(None))
     .update({OtpChallenge.consumed_at: now}, synchronize_session=False))

    code = generate_verification_code()
    challenge = OtpChallenge.issue(
        phone, code, OTP_TTL_MINUTES, requester_ip=_client_ip(),
        max_attempts=OTP_MAX_ATTEMPTS,
    )
    db.session.add(challenge)
    db.session.commit()

    # Send SMS via Twilio (falls back to console print in dev mode)
    from notifications import send_verification_sms
    send_verification_sms(phone, code)

    response_data = {
        'success': True,
        'message': 'Verification code sent',
    }
    # Echo the OTP in the response ONLY in explicit development mode (and
    # only when Twilio isn't configured to actually send it). Never echo in
    # production — an unset FLASK_ENV or missing Twilio creds must not leak
    # login codes.
    if os.environ.get("FLASK_ENV") == "development" and not os.environ.get("TWILIO_ACCOUNT_SID"):
        response_data['code'] = code

    return jsonify(response_data)


def _find_user_by_phone(e164: str, raw: str) -> Optional[User]:
    """Match the normalized number first, then legacy un-normalized spellings
    stored by older signup paths."""
    digits = re.sub(r'\D', '', raw or '')
    candidates = [e164]
    for c in (raw.strip() if raw else None, digits, e164[1:],
              e164[2:] if e164.startswith('+1') else None):
        if c and c not in candidates:
            candidates.append(c)
    rows = User.query.filter(User.phone.in_(candidates)).all()
    if not rows:
        return None
    rows.sort(key=lambda u: 0 if u.phone == e164 else 1)
    return rows[0]


@auth_bp.route('/verify-code', methods=['POST'])
@limiter.limit("10 per minute")
def verify_code():
    """Verify SMS code and create/login user"""
    data = request.get_json(silent=True) or {}
    raw_phone = (data.get('phoneNumber') or data.get('phone') or '').strip()
    code = (data.get('code') or '').strip()

    if not raw_phone or not code:
        return jsonify({'error': 'Phone number and code required'}), 400
    phone = normalize_phone(raw_phone)
    if not phone:
        return jsonify({'error': 'Enter a valid phone number'}), 400

    now = datetime.datetime.utcnow()
    challenge = (
        db.session.query(OtpChallenge)
        .filter(OtpChallenge.identity == phone, OtpChallenge.consumed_at.is_(None))
        .order_by(OtpChallenge.created_at.desc())
        .first()
    )
    if not challenge:
        return jsonify({'error': 'No verification code found'}), 400

    if challenge.is_expired:
        challenge.consumed_at = now
        db.session.commit()
        return jsonify({'error': 'Verification code expired'}), 401

    if challenge.is_locked:
        challenge.consumed_at = now
        db.session.commit()
        return jsonify({'error': 'Too many attempts. Request a new code.'}), 429

    if not challenge.matches(code):
        challenge.attempts = (challenge.attempts or 0) + 1
        if challenge.is_locked:
            challenge.consumed_at = now
        db.session.commit()
        return jsonify({'error': 'Invalid verification code'}), 401

    challenge.consumed_at = now

    # Code is valid — resolve the persisted phone identity.
    user = _find_user_by_phone(phone, raw_phone)
    if user is None:
        user = User(
            id=secrets.token_hex(16),
            phone=phone,
            email=None,
            name=None,
            role='customer',
            phone_verified_at=now,
        )
        db.session.add(user)
    else:
        if not account_is_active(user):
            db.session.commit()
            return jsonify({'error': 'Account is not active'}), 403
        if user.phone != phone:
            # Upgrade a legacy spelling to E.164 when nothing else owns it.
            clash = User.query.filter(User.phone == phone, User.id != user.id).first()
            if clash is None:
                user.phone = phone
        if not user.phone_verified_at:
            user.phone_verified_at = now

    token = issue_session_token(user)

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'phoneNumber': user.phone,
        }
    })

# MARK: - Email Authentication Routes

@auth_bp.route('/signup', methods=['POST'])
@limiter.limit("3 per minute")
def signup():
    """Create new user account with email/password"""
    data = request.get_json(force=True)
    email = normalize_email(data.get('email'))
    password = data.get('password')
    name = data.get('name')
    first_name = data.get('first_name', '')
    last_name = data.get('last_name', '')
    if not name and (first_name or last_name):
        name = f"{first_name} {last_name}".strip()

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    # Check if email already exists in DB
    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify({'error': 'Email already registered'}), 409

    # Extract optional referral code
    referral_code_input = (data.get('referral_code') or '').strip().upper() or None

    # Generate a unique referral code for the new user
    new_user_referral_code = None
    for _ in range(10):
        candidate = generate_referral_code()
        if not User.query.filter_by(referral_code=candidate).first():
            new_user_referral_code = candidate
            break

    raw_phone = (data.get('phone') or data.get('phoneNumber') or '').strip() or None
    phone = normalize_phone(raw_phone) or raw_phone

    # Create user in database
    new_user = User(
        email=email,
        name=name,
        phone=phone,
        password_hash=generate_password_hash(password),
        role='customer',
        referral_code=new_user_referral_code,
    )
    db.session.add(new_user)
    db.session.flush()  # flush to get new_user.id before creating referral

    # If a valid referral code was provided, link the referral
    if referral_code_input:
        referrer = User.query.filter_by(referral_code=referral_code_input).first()
        if referrer and referrer.id != new_user.id:
            referral = Referral(
                referrer_id=referrer.id,
                referee_id=new_user.id,
                referral_code=referral_code_input,
                status='signed_up',
            )
            db.session.add(referral)

    db.session.commit()

    # --- Send welcome email ---
    try:
        from notifications import send_welcome_email
        if new_user.email:
            send_welcome_email(new_user.email, new_user.name)
    except Exception:
        pass  # Notifications must never block the main flow

    token = issue_session_token(new_user)

    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': new_user.id,
            'name': new_user.name,
            'email': new_user.email,
            'phoneNumber': new_user.phone,
            'referral_code': new_user.referral_code
        }
    })


def _lookup_login_user(email, phone):
    if email:
        return User.query.filter_by(email=email).first()
    if phone:
        e164 = normalize_phone(phone)
        if e164:
            return _find_user_by_phone(e164, phone)
        return User.query.filter_by(phone=phone).first()
    return None


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """Login with email/phone and password"""
    data = request.get_json(force=True)
    email = normalize_email(data.get('email')) if data.get('email') else None
    phone = data.get('phone') or data.get('phoneNumber')
    password = data.get('password')

    if (not email and not phone) or not password:
        return jsonify({'error': 'Email or phone number and password required'}), 400

    db_user = _lookup_login_user(email, phone)

    if not db_user or not db_user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401
    if not account_is_active(db_user):
        return jsonify({'error': 'Account is not active'}), 403

    _upgrade_legacy_hash(db_user, password)
    token = issue_session_token(db_user)
    return jsonify({
        'success': True,
        'token': token,
        'user': _user_payload(db_user),
    })

# MARK: - Apple Sign In

_APP_FOR_ROLE = {'customer': 'customer', 'driver': 'driver', 'operator': 'driver'}


def _role_mismatch_response(existing_role, requested_role):
    app_name = _APP_FOR_ROLE.get(existing_role, existing_role or 'other')
    return jsonify({
        'error': 'This account is registered as a {}. Please use the {} app.'.format(
            existing_role, app_name),
        'code': 'role_mismatch',
    }), 403


def _audit_identity_link(user, apple_sub, how, role):
    """Record every Apple-ID-to-account link. Logs plus an append-only
    PortalAuditLog row (org_id NULL). Never raises into the request."""
    sub_ref = hashlib.sha256(apple_sub.encode()).hexdigest()[:16]
    _auth_logger.info(
        "apple_signin: linked apple sub(sha256:%s) to user %s via %s (role=%s)",
        sub_ref, user.id, how, role,
    )
    try:
        from models import PortalAuditLog
        db.session.add(PortalAuditLog(
            org_id=None,
            user_id=user.id,
            action='auth.apple_link',
            object_type='user',
            object_id=user.id,
            after={'apple_sub_sha256': sub_ref, 'via': how, 'role': role},
            ip=_client_ip(),
            user_agent=(request.headers.get('User-Agent') or '')[:240],
        ))
        db.session.commit()
    except Exception as exc:  # pragma: no cover
        db.session.rollback()
        _auth_logger.warning("apple link audit row failed: %s", exc)


def _link_apple_by_verified_email(existing, apple_sub, email_verified, role, name):
    """Return (user, error_response). Links only when Apple says the email is
    verified and the account isn't already bound to a different Apple ID."""
    if not email_verified:
        return None, (jsonify({
            'error': 'An account with this email already exists. Sign in with your '
                     'password (or reset it) to continue.',
            'code': 'email_unverified',
        }), 409)
    if existing.apple_id and existing.apple_id != apple_sub:
        return None, (jsonify({
            'error': 'This email is already linked to a different Apple ID.',
            'code': 'apple_id_conflict',
        }), 409)
    if not account_is_active(existing):
        return None, (jsonify({'error': 'Account is not active'}), 403)
    if existing.role and existing.role != role:
        return None, _role_mismatch_response(existing.role, role)
    linked = existing.apple_id != apple_sub
    existing.apple_id = apple_sub
    if not existing.role:
        existing.role = role
    if name and not existing.name:
        existing.name = name
    db.session.commit()
    if linked:
        _audit_identity_link(existing, apple_sub, 'verified_email_match', role)
    return existing, None


@auth_bp.route('/apple', methods=['POST'])
@limiter.limit("10 per minute")
def apple_signin():
    """Authenticate with an Apple Sign In identity token.

    Body: {identity_token (required), nonce, role?, name?}. The request-body
    ``email`` is ignored: identity comes from the verified token only.
    """
    from models import Contractor

    data = request.get_json(silent=True) or {}
    identity_token = data.get('identity_token')
    nonce = data.get('nonce')
    name = (data.get('name') or '').strip() or None
    role = data.get('role', 'customer')  # Default to customer if not specified

    if role not in ['customer', 'driver', 'operator']:
        return jsonify({'error': 'Invalid role'}), 400

    if not identity_token or not isinstance(identity_token, str):
        # The legacy "userIdentifier only" flow (no token validation) was an
        # account-takeover vector (audit F01) and is gone for good.
        return jsonify({'error': 'identity_token required'}), 400

    payload = validate_apple_identity_token(identity_token, nonce)
    if not payload:
        return jsonify({'error': 'Invalid Apple Sign In token'}), 401

    apple_sub = payload['sub']
    claim_email = normalize_email(payload.get('email'))
    email_verified = _claim_true(payload.get('email_verified'))

    user = User.query.filter_by(apple_id=apple_sub).first()
    if user:
        if not account_is_active(user):
            return jsonify({'error': 'Account is not active'}), 403
        if user.role and user.role != role:
            return _role_mismatch_response(user.role, role)
        if not user.role:
            user.role = role
        if name and not user.name:
            user.name = name
        db.session.commit()

    # Link to an existing account by email ONLY on Apple's verified claim.
    if not user and claim_email:
        existing = User.query.filter_by(email=claim_email).first()
        if existing:
            user, err = _link_apple_by_verified_email(
                existing, apple_sub, email_verified, role, name)
            if err:
                return err

    # Create new user if not found
    if not user:
        user_id = secrets.token_hex(16)
        db_user = User(
            id=user_id,
            apple_id=apple_sub,
            email=claim_email,
            name=name,
            phone=None,
            role=role,
        )
        db.session.add(db_user)

        if role == 'driver':
            db.session.add(Contractor(
                user_id=user_id,
                is_online=False,
                avg_rating=5.0,
            ))

        try:
            db.session.commit()
            user = db_user
        except Exception:
            # A concurrent insert won the race. Recover under the same rules
            # as the happy path: exact Apple-ID match, else verified-email link.
            db.session.rollback()
            _auth_logger.exception("apple_signin: user create failed, recovering")
            user = User.query.filter_by(apple_id=apple_sub).first()
            if user:
                if not account_is_active(user):
                    return jsonify({'error': 'Account is not active'}), 403
                if user.role and user.role != role:
                    return _role_mismatch_response(user.role, role)
            else:
                existing = User.query.filter_by(email=claim_email).first() if claim_email else None
                if not existing:
                    return jsonify({'error': 'Could not complete Apple Sign In. Please try again.'}), 500
                user, err = _link_apple_by_verified_email(
                    existing, apple_sub, email_verified, role, name)
                if err:
                    return err

    token = issue_session_token(user)

    return jsonify({
        'success': True,
        'token': token,
        'user': _user_payload(user),
    })

# MARK: - Password reset

_GENERIC_RESET_MESSAGE = 'If an account exists for that email, a reset link has been sent.'


@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per minute")
def forgot_password():
    """Request a password reset link. The response is identical whether or
    not the email is registered (no account enumeration)."""
    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get('email'))

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    db_user = User.query.filter_by(email=email).first()
    if db_user and account_is_active(db_user):
        now = datetime.datetime.utcnow()
        recent = (
            db.session.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == db_user.id,
                    PasswordResetToken.created_at >= now - datetime.timedelta(hours=1))
            .count()
        )
        if recent < RESET_REQUESTS_PER_HOUR:
            # Newest request wins; earlier unused tokens are retired.
            (db.session.query(PasswordResetToken)
             .filter(PasswordResetToken.user_id == db_user.id,
                     PasswordResetToken.used_at.is_(None))
             .update({PasswordResetToken.used_at: now}, synchronize_session=False))
            row, raw_token = PasswordResetToken.issue(
                db_user.id, RESET_TOKEN_TTL_MINUTES, requester_ip=_client_ip())
            db.session.add(row)
            db.session.commit()
            try:
                from notifications import send_password_reset_email
                send_password_reset_email(email, raw_token, db_user.name)
            except Exception:
                _auth_logger.exception("forgot_password: email send failed")
        else:
            _auth_logger.info("forgot_password: throttled for user %s", db_user.id)

    return jsonify({'success': True, 'message': _GENERIC_RESET_MESSAGE})


@auth_bp.route('/reset-password', methods=['POST'])
@limiter.limit("5 per minute")
def reset_password():
    """Redeem a reset token: {token, password}. Single use, expiring; a
    successful reset revokes every existing session for the account."""
    data = request.get_json(silent=True) or {}
    raw_token = (data.get('token') or '').strip()
    password = data.get('password')

    if not raw_token or not password:
        return jsonify({'error': 'Token and new password are required'}), 400
    policy_error = password_policy_error(password)
    if policy_error:
        return jsonify({'error': policy_error}), 400

    row = PasswordResetToken.query.filter_by(
        token_hash=PasswordResetToken.hash_token(raw_token)).first()
    if not row or not row.is_valid:
        return jsonify({'error': 'This reset link is invalid or has expired.'}), 400

    user = db.session.get(User, row.user_id)
    if not user or not account_is_active(user):
        row.used_at = datetime.datetime.utcnow()
        db.session.commit()
        return jsonify({'error': 'This reset link is invalid or has expired.'}), 400

    user.password_hash = generate_password_hash(password)   # bumps token_version
    row.used_at = datetime.datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'message': 'Password updated. Please sign in.'})


# MARK: - Customer Bookings

@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user(user_id):
    """Get current authenticated user profile"""
    db_user = db.session.get(User, user_id)
    if db_user:
        return jsonify({
            'success': True,
            'user': db_user.to_dict()
        })
    return jsonify({'error': 'User not found'}), 404


@auth_bp.route('/me', methods=['PUT'])
@require_auth
def update_profile(user_id):
    """Update current user profile (name, email, phone)"""
    db_user = db.session.get(User, user_id)
    if not db_user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(force=True)

    # Update name if provided
    if 'name' in data and data['name'] is not None:
        db_user.name = data['name'].strip() or db_user.name

    # Update email if provided, checking uniqueness
    if 'email' in data and data['email'] is not None:
        new_email = normalize_email(data['email'])
        if new_email and new_email != db_user.email:
            existing = User.query.filter_by(email=new_email).first()
            if existing and existing.id != db_user.id:
                return jsonify({'error': 'Email already in use'}), 409
            db_user.email = new_email

    # Update phone if provided
    if 'phone' in data and data['phone'] is not None:
        raw = data['phone'].strip()
        new_phone = normalize_phone(raw) or raw
        if new_phone and new_phone != db_user.phone:
            existing = User.query.filter_by(phone=new_phone).first()
            if existing and existing.id != db_user.id:
                return jsonify({'error': 'Phone number already in use'}), 409
            db_user.phone = new_phone
            db_user.phone_verified_at = None

    db.session.commit()

    return jsonify({
        'success': True,
        'user': db_user.to_dict()
    })


@auth_bp.route('/change-password', methods=['PUT'])
@require_auth
def change_password(user_id):
    """Change the current user's password. Revokes every other session and
    returns a fresh token for this one."""
    db_user = db.session.get(User, user_id)
    if not db_user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json(force=True)
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({'error': 'Current password and new password are required'}), 400

    if not db_user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 401

    policy_error = password_policy_error(new_password)
    if policy_error:
        return jsonify({'error': 'New password must be at least {} characters'.format(MIN_PASSWORD_LENGTH)
                        if 'at least' in policy_error else policy_error}), 400

    db_user.password_hash = generate_password_hash(new_password)   # bumps token_version
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Password changed successfully',
        'token': generate_token(db_user.id),
    })


@auth_bp.route('/me', methods=['DELETE'])
@require_auth
def delete_account(user_id):
    """Permanently delete the current user account.

    Anonymizes all personally identifiable info (email, phone, name,
    apple_id, password, avatar, referral code, Stripe customer link)
    and marks status='deleted'. The row stays for foreign-key integrity
    on historical jobs, ratings, and audit trails — but the user can
    no longer log in, no notifications go out, and prior JWTs are
    rejected on the next request.

    Apple Guideline 5.1.1(v): a real deletion, not a deactivation.
    Once this returns success the user is unrecoverable from the
    client's perspective — they would have to sign up fresh.
    """
    db_user = db.session.get(User, user_id)
    if not db_user:
        return jsonify({'error': 'User not found'}), 404

    db_user.email = None
    db_user.phone = None
    db_user.phone_verified_at = None
    db_user.name = None
    db_user.password_hash = None
    db_user.apple_id = None
    db_user.avatar_url = None
    db_user.stripe_customer_id = None
    db_user.referral_code = None
    db_user.status = 'deleted'
    db_user.revoke_sessions()

    # Revoke push tokens — no more notifications to a deleted account.
    try:
        for dt in list(db_user.device_tokens):
            db.session.delete(dt)
    except Exception:
        # device_tokens relationship may not exist on legacy rows; ignore.
        pass

    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Account deleted'
    })


# MARK: - Seed Admin

@auth_bp.route('/seed-admin', methods=['POST'])
@limiter.limit("5 per hour")
def seed_admin():
    """Promote a user to admin role. Requires a seed secret."""
    data = request.get_json(force=True)
    secret = data.get('secret')
    email = normalize_email(data.get('email'))

    # Use env var — no hardcoded fallback for security
    expected = os.environ.get('ADMIN_SEED_SECRET', '')
    if not expected:
        return jsonify({'error': 'ADMIN_SEED_SECRET is not configured'}), 503
    # Constant-time comparison to avoid leaking the secret via timing
    if not secret or not secrets.compare_digest(
        str(secret).encode('utf-8'), expected.encode('utf-8')
    ):
        return jsonify({'error': 'Unauthorized'}), 403

    user = User.query.filter_by(email=email).first() if email else None
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user.role = 'admin'   # role change bumps token_version (model listener)
    db.session.commit()
    return jsonify({'success': True, 'message': f'{email} is now admin'})


@auth_bp.route('/bootstrap-admin', methods=['POST'])
@limiter.limit("5 per hour")
def bootstrap_admin():
    """One-time admin bootstrap. Only works when zero admins exist."""
    admin_count = User.query.filter_by(role='admin').count()
    if admin_count > 0:
        return jsonify({'error': 'Admin already exists. Use seed-admin instead.'}), 403

    data = request.get_json(force=True)
    email = normalize_email(data.get('email')) or 'admin@goumuve.com'
    password = data.get('password')
    name = data.get('name', 'Admin')

    policy_error = password_policy_error(password)
    if policy_error:
        return jsonify({'error': 'A password with at least 8 characters is required'}), 400

    user = User.query.filter_by(email=email).first()
    if user:
        user.role = 'admin'
        user.password_hash = generate_password_hash(password)
    else:
        user = User(
            email=email,
            name=name,
            role='admin',
            password_hash=generate_password_hash(password),
            referral_code=generate_referral_code(),
        )
        db.session.add(user)

    db.session.commit()
    return jsonify({'success': True, 'message': f'{email} is now admin', 'user_id': user.id})


# MARK: - Token Validation

@auth_bp.route('/validate', methods=['POST'])
def validate_token_endpoint():
    """Validate existing auth token"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user, reason = authenticate_access_token(token)
    if not user:
        return jsonify({'error': reason if reason != 'Unauthorized' else 'Invalid token'}), 401
    return jsonify({
        'success': True,
        'user': user.to_dict()
    })


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token_endpoint():
    """Refresh JWT token (allows refresh within 7 days of expiry). The
    account must still be active and the token's session version current —
    a suspended user or a revoked session cannot refresh its way back in."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user, reason = authenticate_access_token(token, allow_expired_within=REFRESH_GRACE)
    if not user:
        return jsonify({'error': reason if reason != 'Unauthorized' else 'Invalid token'}), 401

    return jsonify({
        'success': True,
        'token': generate_token(user.id)
    })


# NOTE: the temporary /upgrade_operator testing endpoint was removed
# (security audit 2026-07-02) — use the admin dashboard / seed-admin flow.

# MARK: - Dev/Test Login for Drivers

@auth_bp.route('/dev-driver-login', methods=['POST'])
def dev_driver_login():
    """Dev-only endpoint to quickly login as a test driver"""
    if os.environ.get('FLASK_ENV') != 'development':
        return jsonify(error="Not available"), 404

    from models import Contractor, generate_uuid

    data = request.get_json() or {}
    email = normalize_email(data.get('email')) or 'testdriver@goumuve.com'

    # Find or create test driver
    test_driver = User.query.filter_by(email=email, role='driver').first()

    if not test_driver:
        test_driver = User(
            id=secrets.token_hex(16),
            email=email,
            name="Test Driver",
            role="driver"
        )
        db.session.add(test_driver)

        # Create contractor
        contractor = Contractor(
            id=generate_uuid(),
            user_id=test_driver.id,
            is_online=False,
            avg_rating=5.0
        )
        db.session.add(contractor)
        db.session.commit()

    token = issue_session_token(test_driver)

    return jsonify({
        'success': True,
        'token': token,
        'user': _user_payload(test_driver),
    })

# MARK: - Email/Password Auth for Drivers

@auth_bp.route('/driver-signup', methods=['POST'])
def driver_signup():
    """Sign up as a driver with email and password"""
    from models import Contractor, OperatorInvite, generate_uuid
    import traceback

    try:
        data = request.get_json(silent=True) or {}
        email = normalize_email(data.get('email'))
        password = data.get('password')
        name = (data.get('name') or '').strip() or None
        invite_code = (data.get('inviteCode') or '').strip() or None

        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        policy_error = password_policy_error(password)
        if policy_error:
            return jsonify({'error': policy_error}), 400
    except Exception as e:
        _auth_logger.error(f"driver-signup error (parsing): {e}\n{traceback.format_exc()}")
        return jsonify({'error': 'Invalid request data'}), 400

    try:
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'error': 'Email already registered'}), 409

        # Validate invite code if provided
        operator_id = None
        if invite_code:
            invite = OperatorInvite.query.filter_by(invite_code=invite_code).first()

            if not invite:
                return jsonify({'error': 'Invalid invite code'}), 400

            if not invite.is_active:
                return jsonify({'error': 'Invite code is no longer active'}), 400

            if invite.expires_at and invite.expires_at < datetime.datetime.utcnow():
                return jsonify({'error': 'Invite code has expired'}), 400

            if invite.use_count >= invite.max_uses:
                return jsonify({'error': 'Invite code has reached maximum uses'}), 400

            operator_id = invite.operator_id
            invite.use_count += 1

        # Create driver user
        user_id = secrets.token_hex(16)
        new_user = User(
            id=user_id,
            email=email,
            password_hash=generate_password_hash(password),
            name=name,
            role='driver'
        )
        db.session.add(new_user)

        # Create contractor record
        contractor = Contractor(
            id=generate_uuid(),
            user_id=user_id,
            is_online=False,
            avg_rating=5.0,
            operator_id=operator_id
        )
        db.session.add(contractor)
        db.session.commit()

        # --- Send welcome email to driver ---
        try:
            from notifications import send_welcome_email
            if new_user.email:
                send_welcome_email(new_user.email, new_user.name)
        except Exception:
            pass  # Notifications must never block the main flow

        token = issue_session_token(new_user)

        return jsonify({
            'success': True,
            'token': token,
            'user': _user_payload(new_user),
        })

    except Exception as e:
        db.session.rollback()
        _auth_logger.error(f"driver-signup error: {e}\n{traceback.format_exc()}")
        return jsonify({'error': 'Server error. Please try again.'}), 500


@auth_bp.route('/driver-login', methods=['POST'])
def driver_login():
    """Login as a driver with email/phone and password"""
    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get('email')) if data.get('email') else None
    phone = (data.get('phone') or data.get('phoneNumber') or '').strip()
    password = data.get('password')

    if (not email and not phone) or not password:
        return jsonify({'error': 'Email or phone number and password required'}), 400

    try:
        user = _lookup_login_user(email, phone)

        if not user or not verify_password(user.password_hash or '', password):
            return jsonify({'error': 'Invalid credentials'}), 401

        # Verify role
        if user.role != 'driver':
            return jsonify({'error': 'This account is not registered as a driver. Please use the customer app.'}), 403
        if not account_is_active(user):
            return jsonify({'error': 'Account is not active'}), 403

        _upgrade_legacy_hash(user, password)
        token = issue_session_token(user)

        return jsonify({
            'success': True,
            'token': token,
            'user': _user_payload(user),
        })
    except Exception as e:
        _auth_logger.exception("Driver login failed unexpectedly: %s", e)
        return jsonify({'error': 'Login failed. Please try again.'}), 500
