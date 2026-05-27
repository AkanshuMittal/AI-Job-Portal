# ─────────────────────────────────────────────────────────
# core/security.py
# Production Ready JWT + Password Security
# ─────────────────────────────────────────────────────────

from jose import JWTError, jwt

# ─────────────────────────────────────────────────────────
# bcrypt compatibility patch
# Fixes bcrypt/passlib issues on live servers
# (Python 3.12+ / bcrypt 4.x)
# ─────────────────────────────────────────────────────────
try:
    import bcrypt

    if not hasattr(bcrypt, "__about__"):
        bcrypt.__about__ = type(
            "Dummy",
            (object,),
            {"__version__": bcrypt.__version__}
        )()

except ImportError:
    pass

# ─────────────────────────────────────────────────────────
# Password Hashing
# ─────────────────────────────────────────────────────────
from passlib.context import CryptContext

# ─────────────────────────────────────────────────────────
# Date & Time
# ─────────────────────────────────────────────────────────
from datetime import datetime, timedelta, timezone

# ─────────────────────────────────────────────────────────
# Typing
# ─────────────────────────────────────────────────────────
from typing import Optional

# ─────────────────────────────────────────────────────────
# App Settings
# ─────────────────────────────────────────────────────────
from core.config import settings

# ─────────────────────────────────────────────────────────
# Password Hashing Configuration
#
# bcrypt_sha256:
# - avoids bcrypt 72-byte limit
# - internally applies SHA256 safely
#
# bcrypt:
# - supports old hashes already stored in DB
# ─────────────────────────────────────────────────────────
pwd_context = CryptContext(
    schemes=["bcrypt_sha256"],
    deprecated="auto"
)

# ─────────────────────────────────────────────────────────
# Hash Password
# ─────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """
    Hash a password securely.
    """

    if len(password) < 8:
        raise ValueError(
            "Password must be at least 8 characters long"
        )

    return pwd_context.hash(password)

# ─────────────────────────────────────────────────────────
# Verify Password
# ─────────────────────────────────────────────────────────
def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """
    Verify password safely.

    Returns:
        True  -> password correct
        False -> invalid password/hash error
    """

    try:
        return pwd_context.verify(
            plain_password,
            hashed_password
        )

    except Exception:
        # Prevents 500 Internal Server Error
        return False

# ─────────────────────────────────────────────────────────
# Create JWT Access Token
# ─────────────────────────────────────────────────────────
def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create signed JWT token.
    """

    to_encode = data.copy()

    # Token expiry
    if expires_delta:
        expire = datetime.now(
            timezone.utc
        ) + expires_delta

    else:
        expire = datetime.now(
            timezone.utc
        ) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    # Add expiry claim
    to_encode.update({
        "exp": expire
    })

    # Create token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt

# ─────────────────────────────────────────────────────────
# Decode JWT Access Token
# ─────────────────────────────────────────────────────────
def decode_access_token(
    token: str
) -> Optional[dict]:
    """
    Decode and verify JWT token.

    Returns:
        payload dict OR None
    """

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        return payload

    except JWTError:
        return None