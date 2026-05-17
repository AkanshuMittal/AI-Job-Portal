# ─────────────────────────────────────────────────────────
# core/security.py — JWT Tokens + Password Hashing
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   This file handles ALL authentication security:
#   1. Hashing passwords before storing in DB (bcrypt)
#   2. Verifying a plain password against a stored hash
#   3. Creating JWT access tokens (on login)
#   4. Decoding/verifying JWT tokens (on each request)
#
# WHAT IS JWT?
#   JSON Web Token — a signed string that proves who you are.
#   Format: header.payload.signature
#   Example: eyJhbGci...eyJ1c2VyX2lk...SflKxwRJSM
#   The server signs it with SECRET_KEY, so it can't be faked.
# ─────────────────────────────────────────────────────────

# jwt: The library that creates and decodes JWT tokens
from jose import JWTError, jwt

# CryptContext: Manages password hashing schemes (we use bcrypt)
from passlib.context import CryptContext

# datetime: For calculating token expiry time
from datetime import datetime, timedelta, timezone

# Optional: Return type hint for functions that may return None
from typing import Optional

# Our settings (SECRET_KEY, ALGORITHM, EXPIRE_MINUTES)
from core.config import settings


import hashlib
import base64

# ── Password Hashing Setup ────────────────────────────────
# We use bcrypt_sha256 which automatically handles the 72-byte limit
# and is more stable on Windows systems.
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hashes a password using SHA-256 pre-hash + Bcrypt.
    This solves the 72-byte limit perfectly for any password length.
    """
    pw_hash = hashlib.sha256(plain_password.encode()).digest()
    pw_b64 = base64.b64encode(pw_hash).decode()
    return pwd_context.hash(pw_b64)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a password using SHA-256 pre-hash + Bcrypt.
    """
    pw_hash = hashlib.sha256(plain_password.encode()).digest()
    pw_b64 = base64.b64encode(pw_hash).decode()
    return pwd_context.verify(pw_b64, hashed_password)


# ── JWT Token Creation ────────────────────────────────────
def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Creates a signed JWT token that encodes user information.
    
    HOW IT WORKS:
    1. We take user data (e.g., {"sub": "user@email.com", "role": "hr"})
    2. We add an expiry timestamp (exp)
    3. We sign it with SECRET_KEY using HS256 algorithm
    4. The result is a compact string the frontend stores in localStorage
    
    Args:
        data: Dictionary of claims to encode (e.g., user ID, role)
        expires_delta: Custom expiry duration; defaults to settings value
    
    Returns:
        A signed JWT string
    """
    # Copy the data so we don't mutate the original dict
    to_encode = data.copy()
    
    # Calculate expiry time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default: use ACCESS_TOKEN_EXPIRE_MINUTES from .env (e.g., 30 mins)
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    # Add expiry to the token payload
    # "exp" is a standard JWT claim — jose library checks it automatically
    to_encode.update({"exp": expire})
    
    # Encode (sign) the token
    # jwt.encode() creates the final token string
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,    # Sign with our secret key
        algorithm=settings.ALGORITHM  # HS256
    )
    
    return encoded_jwt


# ── JWT Token Decoding ────────────────────────────────────
def decode_access_token(token: str) -> Optional[dict]:
    """
    Decodes and verifies a JWT token.
    Returns the payload (claims) if valid, or None if invalid/expired.
    
    Called on every protected API request to identify the user.
    
    Args:
        token: The JWT string from the Authorization header
    
    Returns:
        dict with user claims (e.g., {"sub": "user@email.com", "role": "hr"})
        or None if the token is invalid or expired
    """
    try:
        # jwt.decode() verifies the signature AND checks expiry automatically
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        # Token is invalid, expired, or tampered with — return None
        # The caller (api/deps.py) will raise HTTP 401
        return None
