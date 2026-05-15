# ─────────────────────────────────────────────────────────
# api/deps.py — Shared FastAPI Dependencies
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   FastAPI "dependencies" are functions that run BEFORE a route handler.
#   They perform common tasks like:
#     - Extracting and verifying the JWT token
#     - Getting the current logged-in user from the database
#     - Checking role-based permissions
#
# HOW DEPENDENCIES WORK:
#   In a route, you write: current_user = Depends(get_current_user)
#   FastAPI automatically calls get_current_user() before your route runs,
#   and injects the result as the `current_user` parameter.
#   If the dependency raises an HTTPException, the route never runs.
# ─────────────────────────────────────────────────────────

# Depends: The decorator that marks a function as a dependency
# HTTPException: Raises HTTP errors (401, 403, 404, etc.)
# status: HTTP status code constants (e.g., status.HTTP_401_UNAUTHORIZED)
from fastapi import Depends, HTTPException, status

# OAuth2PasswordBearer: Extracts the Bearer token from the Authorization header.
# tokenUrl: The URL where clients get tokens (for Swagger UI's Authorize button)
from fastapi.security import OAuth2PasswordBearer

# AsyncSession: Type hint for the database session
from sqlalchemy.ext.asyncio import AsyncSession

# select: SQLAlchemy query builder — like "SELECT * FROM users WHERE ..."
from sqlalchemy import select

# Our database session dependency
from core.database import get_db

# JWT decoding function
from core.security import decode_access_token

# The User ORM model and UserRole enum
from models.user import User, UserRole


# ── OAuth2 Scheme Setup ───────────────────────────────────
# OAuth2PasswordBearer extracts the token from:
#   Authorization: Bearer eyJhbGci...
# tokenUrl tells Swagger UI where to get a token (the login endpoint)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Core Dependency: Get Current User ─────────────────────
async def get_current_user(
    token: str = Depends(oauth2_scheme),    # Extract token from header
    db: AsyncSession = Depends(get_db)       # Get a DB session
) -> User:
    """
    FastAPI dependency that:
    1. Extracts the JWT token from the Authorization header
    2. Decodes and validates the token
    3. Loads the user from the database
    4. Returns the User object (or raises 401 if anything fails)
    
    Usage in a route:
        @router.get("/profile")
        async def my_profile(current_user: User = Depends(get_current_user)):
            return current_user
    """
    # Define the error we'll raise if authentication fails
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Please login again.",
        # headers: OAuth2 standard requires this header on 401 responses
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Step 1: Decode the JWT token
    payload = decode_access_token(token)
    if payload is None:
        # Token is invalid, expired, or tampered with
        raise credentials_exception

    # Step 2: Extract user email from the "sub" claim
    # "sub" (subject) is the standard JWT claim for user identity
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception

    # Step 3: Load the user from the database
    # select(User).where(...) builds: SELECT * FROM users WHERE email = :email
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()  # Returns User or None

    if user is None:
        # User exists in token but not in DB (e.g., account deleted)
        raise credentials_exception

    # Step 4: Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact support."
        )

    return user


# ── Role-Based Access Dependencies ────────────────────────
# These dependencies call get_current_user first, then check the role.
# Use these on routes that should ONLY be accessible by one role.

async def get_current_super_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Only allows Super Admin users to access the route.
    Raises HTTP 403 if the user is HR or Seeker.
    
    Usage:
        @router.get("/admin/stats")
        async def admin_stats(admin = Depends(get_current_super_admin)):
            ...
    """
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Super Admin privileges required."
        )
    return current_user


async def get_current_hr(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Only allows HR users (and Super Admin) to access the route.
    Raises HTTP 403 for Job Seekers.
    """
    if current_user.role not in [UserRole.HR, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. HR privileges required."
        )
    return current_user


async def get_current_seeker(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Only allows Job Seeker users to access the route.
    """
    if current_user.role != UserRole.SEEKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job Seeker account required."
        )
    return current_user
