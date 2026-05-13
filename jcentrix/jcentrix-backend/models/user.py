# ─────────────────────────────────────────────────────────
# models/user.py — User ORM Model
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   Defines the `users` database table.
#   All three roles (super_admin, hr, seeker) live in this
#   single table, differentiated by the `role` column.
#   This is called "Single Table Inheritance" pattern.
#
# ROLES:
#   - "super_admin" → Jcentrix platform owner
#   - "hr"          → Partner company HR staff
#   - "seeker"      → Job applicant
# ─────────────────────────────────────────────────────────

from sqlalchemy import (
    Column, Integer, String, Boolean,
    DateTime, ForeignKey, Enum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum  # Python's built-in enum module for defining choices

from core.database import Base


# ── Role Enum ─────────────────────────────────────────────
# Using Python enum ensures only valid roles can be stored.
# SQLAlchemy will create a PostgreSQL ENUM type for this column.
class UserRole(str, enum.Enum):
    """
    Defines the three user roles in the system.
    Inheriting from str makes JSON serialization work automatically.
    """
    SUPER_ADMIN = "super_admin"
    HR = "hr"
    SEEKER = "seeker"


class User(Base):
    """
    Represents any user in the Jcentrix system regardless of role.
    
    Database Table: `users`
    
    Relationships:
        - A User (HR) belongs to one Company
        - A User (Seeker) has one SeekerProfile
        - A User (HR) creates many Jobs
    """

    __tablename__ = "users"

    # ── Primary Key ───────────────────────────────────────
    id = Column(Integer, primary_key=True, index=True)

    # ── Identity ──────────────────────────────────────────
    # email: The login identifier. Must be unique across all users.
    email = Column(String(255), unique=True, index=True, nullable=False)

    # full_name: Display name shown in the UI
    full_name = Column(String(255), nullable=False)

    # hashed_password: NEVER store plain text. bcrypt hash goes here.
    hashed_password = Column(String(255), nullable=False)

    # ── Role ──────────────────────────────────────────────
    # role: Determines what this user can do (access control).
    # We use the UserRole enum to restrict valid values.
    role = Column(
        Enum(UserRole),
        nullable=False,
        default=UserRole.SEEKER  # Default role when registering
    )

    # ── Company Link (HR only) ────────────────────────────
    # company_id: Foreign key linking an HR user to their company.
    # NULL for super_admin and seeker (they don't belong to a company).
    # ForeignKey("companies.id"): References the `id` column in `companies` table.
    # ondelete="SET NULL": If the company is deleted, set this to NULL
    #                      (don't delete the user).
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True   # NULL for super_admin and seeker
    )

    # ── Status ────────────────────────────────────────────
    # is_active: Deactivated users cannot login.
    # Super Admin can deactivate any user.
    is_active = Column(Boolean, default=True, nullable=False)

    # is_verified: Email verification flag (future use)
    is_verified = Column(Boolean, default=False, nullable=False)

    # ── Timestamps ────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # ── Last Login ────────────────────────────────────────
    # Tracking when users last logged in (useful for analytics)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # ── Relationships ─────────────────────────────────────
    # company: The Company this HR user belongs to.
    # back_populates="users": Company model has a `users` list field.
    company = relationship("Company", back_populates="users")

    # seeker_profile: One-to-one link to the SeekerProfile (Phase 2)
    # uselist=False: This is a one-to-one relationship (not a list)
    seeker_profile = relationship(
        "SeekerProfile", back_populates="user", uselist=False
    )

    def __repr__(self):
        return f"<User id={self.id} email='{self.email}' role='{self.role}'>"
