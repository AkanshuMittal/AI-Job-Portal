# ─────────────────────────────────────────────────────────
# api/auth.py — Authentication Routes (Register + Login)
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   This file contains the two most fundamental routes:
#   1. POST /auth/register → Create a new account
#   2. POST /auth/login    → Get a JWT token
#   3. GET  /auth/me       → Get current user's profile
#
# FLOW FOR REGISTRATION:
#   Client sends email + password + role
#   → We check email isn't already taken
#   → We hash the password
#   → We save the new user to MySQL
#   → We return user info (without password)

# FLOW FOR LOGIN:
#   Client sends email + password
#   → We find user by email
#   → We verify password against hash
#   → We create a JWT token
#   → We return the token + user info
# ─────────────────────────────────────────────────────────


from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

# Import our core modules
from core.database import get_db
from core.security import hash_password, verify_password, create_access_token

# Import ORM models
from models.user import User, UserRole
from models.company import Company

# Import Pydantic schemas
from schemas.user import UserCreate, UserLogin, UserOut, Token

# Import auth dependency to protect the /me endpoint
from api.deps import get_current_user


# ── Router Setup ──────────────────────────────────────────
# APIRouter: A mini-application for grouping related routes.
# prefix="/auth": All routes in this file start with /auth
#                 e.g., /auth/register, /auth/login
# tags=["Authentication"]: Groups these routes under "Authentication"
#                          in the Swagger UI documentation
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Route 1: Register a New User ─────────────────────────
@router.post(
    "/register",
    response_model=UserOut,                     # Response shape is UserOut
    status_code=status.HTTP_201_CREATED,        # 201 = Created (not 200)
    summary="Register a new user account"
)
async def register(
    user_data: UserCreate,                      # Request body (auto-validated)
    db: AsyncSession = Depends(get_db)          # DB session from dependency
):
    """
    Registers a new user (Super Admin, HR, or Job Seeker).
    
    Steps:
    1. Check if email is already taken
    2. If HR role, validate company_id exists
    3. Hash the password
    4. Create and save the User record
    5. Return UserOut (without password)
    """

    # ── Step 1: Check for duplicate email ─────────────────
    # Build query: SELECT * FROM users WHERE email = :email LIMIT 1
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()  # Returns User or None

    if existing_user:
        # Email already registered → return 400 Bad Request
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{user_data.email}' is already registered."
        )

    # ── Step 2: Validate company_id for HR users ──────────
    if user_data.role == UserRole.HR:
        if user_data.company_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HR users must provide a company_id."
            )
        # Verify the company exists and is active
        company_result = await db.execute(
            select(Company).where(
                Company.id == user_data.company_id,
                Company.is_active == True
            )
        )
        company = company_result.scalar_one_or_none()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company with id={user_data.company_id} not found or inactive."
            )

    # ── Step 3: Hash the password ─────────────────────────
    # We NEVER store plain passwords. Convert to bcrypt hash.
    hashed_pw = hash_password(user_data.password)

    # ── Step 4: Create the User object ────────────────────
    # We create a SQLAlchemy model instance (not saved to DB yet)
    new_user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hashed_pw,          # Stored hashed, not plain
        role=user_data.role,
        company_id=user_data.company_id,    # None for non-HR users
        is_active=True,
        is_verified=False,                  # Email verification future feature
    )

    # ── Step 5: Save to database ──────────────────────────
    db.add(new_user)        # Mark the object to be inserted
    await db.flush()        # Execute INSERT and get the auto-generated ID
                            # (but don't commit yet — get_db handles commit)
    await db.refresh(new_user)  # Reload the object to get server-set values
                                # (like created_at from server_default)

    # ── Step 6: Return the new user ───────────────────────
    # UserOut.model_validate(): Converts SQLAlchemy model → Pydantic schema
    # from_attributes=True in UserOut.Config enables this conversion
    return UserOut.model_validate(new_user)


# ── Route 2: Login ────────────────────────────────────────
@router.post(
    "/login",
    response_model=Token,
    summary="Login and receive a JWT access token"
)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticates a user and returns a JWT token.
    
    Steps:
    1. Find user by email
    2. Verify the password
    3. Check account is active
    4. Create a JWT token with user info as claims
    5. Return token + user info
    """
    try:
        # ── Step 1: Find user by email ────────────────────────
        result = await db.execute(
            select(User).where(User.email == login_data.email)
        )
        user = result.scalar_one_or_none()

        # Use a generic error message for security.
        # Never tell attackers whether the email OR password was wrong —
        # that helps them enumerate valid emails.
        auth_error = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

        if user is None:
            raise auth_error  # Email not found

        # ── Step 2: Verify password ───────────────────────────
        # verify_password() uses bcrypt to check plain vs stored hash
        if not verify_password(login_data.password, user.hashed_password):
            raise auth_error  # Wrong password

        # ── Step 3: Check account status ─────────────────────
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account deactivated. Contact Jcentrix support."
            )

        # ── Step 4: Update last_login timestamp ──────────────
        user.last_login = datetime.now(timezone.utc)
        # No explicit save needed — get_db() auto-commits at end of request

        # ── Step 5: Create JWT token ──────────────────────────
        # The token payload (claims) — stored inside the signed JWT
        # "sub" (subject): standard JWT claim for user identity
        token_payload = {
            "sub": user.email,          # Used to look up user on every request
            "role": user.role.value,    # e.g., "hr" — for quick role checks
            "user_id": user.id          # Useful for some operations
        }
        access_token = create_access_token(data=token_payload)

    # ── Step 6: Return token + user info ─────────────────
        return Token(
            access_token=access_token,
            token_type="bearer",
            user=UserOut.model_validate(user)
        )
    except Exception as e:
        # Log the exception for debugging (in real app, use proper logging)
        print(f"Login error: {e}")
        # Return a generic error message to the client
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def authenticate_user(
    email: str,
    password: str,
    db: AsyncSession
) -> User:
    """Authenticate email/password and return the active user."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if user is None or not verify_password(password, user.hashed_password):
        raise auth_error

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated. Contact Jcentrix support."
        )

    return user


@router.post(
    "/token",
    response_model=Token,
    summary="Login using OAuth2 password form"
)
async def login_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Login endpoint compatible with Swagger OAuth2 Authorize."""
    user = await authenticate_user(form_data.username, form_data.password, db)
    user.last_login = datetime.now(timezone.utc)

    token_payload = {
        "sub": user.email,
        "role": user.role.value,
        "user_id": user.id
    }
    access_token = create_access_token(data=token_payload)

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user)
    )


# ── Route 3: Get Current User Profile ─────────────────────
@router.get(
    "/me",
    response_model=UserOut,
    summary="Get the currently authenticated user's profile"
)
async def get_me(
    # Depends(get_current_user) runs the dependency:
    # 1. Extracts Bearer token from Authorization header
    # 2. Decodes JWT → gets email
    # 3. Loads User from DB
    # 4. Returns User object here as `current_user`
    current_user: User = Depends(get_current_user)
):
    """
    Returns the profile of the currently logged-in user.
    Requires a valid Bearer token in the Authorization header.
    
    The client should call this after login to confirm their identity.
    """
    return UserOut.model_validate(current_user)

