# ─────────────────────────────────────────────────────────
# schemas/user.py — Pydantic Schemas for User API
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   Pydantic schemas define the "shape" of data coming IN and going OUT.
#   They are DIFFERENT from SQLAlchemy models:
#
#   SQLAlchemy Model = represents a database TABLE row
#   Pydantic Schema  = represents JSON request/response body
#
# NAMING CONVENTION:
#   UserCreate  → data the client SENDS to create a user (request body)
#   UserLogin   → data the client SENDS to login
#   UserOut     → data we SEND BACK to the client (response)
#   Token       → the JWT response after login
#
# WHY SEPARATE?
#   We never send hashed_password back in responses.
#   We never let clients set the `role` during registration freely.
#   Schemas give us fine-grained control over what's allowed.
# ─────────────────────────────────────────────────────────

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

# Import the UserRole enum from our model to reuse it in schemas
from models.user import UserRole


# ── Request Schemas (Client → Server) ────────────────────

class UserCreate(BaseModel):
    """
    Schema for registering a new user.
    Sent by the client in the request body of POST /auth/register.
    
    EmailStr: Pydantic validates that this is a valid email format.
    Field(min_length=8): Password must be at least 8 characters.
    """
    email: EmailStr                          # e.g., "john@example.com"
    full_name: str = Field(min_length=2)    # e.g., "John Doe"
    password: str = Field(min_length=8)     # Plain text — we hash it before storing
    role: UserRole = UserRole.SEEKER        # Default to seeker if not specified
    company_id: Optional[int] = None        # Required only for HR users


class UserLogin(BaseModel):
    """
    Schema for logging in.
    Sent by the client in the request body of POST /auth/login.
    """
    email: EmailStr
    password: str  # Plain text — we compare against the stored hash


# ── Response Schemas (Server → Client) ───────────────────

class UserOut(BaseModel):
    """
    Schema for sending user data back to the client.
    NOTICE: No `password` or `hashed_password` field here!
    We never expose passwords in API responses.
    """
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    company_id: Optional[int]
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        # from_orm=True (old Pydantic v1) is replaced by:
        # from_attributes=True in Pydantic v2
        # This allows creating a UserOut from a SQLAlchemy User object:
        #   UserOut.model_validate(user_db_object)
        from_attributes = True


class Token(BaseModel):
    """
    Schema for the JWT token response after successful login.
    The client should store this token and send it in the
    Authorization header of future requests:
        Authorization: Bearer <access_token>
    """
    access_token: str       # The JWT string
    token_type: str = "bearer"  # Always "bearer" (OAuth2 standard)
    user: UserOut           # Include user info so frontend knows the role


class TokenData(BaseModel):
    """
    Internal schema for decoded JWT payload.
    Used in api/deps.py when extracting user identity from a token.
    """
    email: Optional[str] = None    # The "sub" (subject) claim in the JWT
    role: Optional[str] = None     # The user's role stored in the token


class UserUpdate(BaseModel):
    """
    Schema for updating a user's profile.
    All fields are Optional — client only sends what they want to change.
    """
    full_name: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=8)
    is_active: Optional[bool] = None
