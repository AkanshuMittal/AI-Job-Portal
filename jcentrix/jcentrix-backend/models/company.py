# ─────────────────────────────────────────────────────────
# models/company.py — Company ORM Model
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   Defines the `companies` database table.
#   Each row = one Partner Company (e.g., "TechCorp India Pvt Ltd").
#   Super Admin creates companies. HR users belong to a company.
# ─────────────────────────────────────────────────────────

# Column types from SQLAlchemy
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func           # func.now() → current timestamp
from sqlalchemy.orm import relationship  # Links Company → Users and Jobs

# Import the shared Base class that all models inherit from
from core.database import Base


class Company(Base):
    """
    Represents a Partner Company in the Jcentrix platform.
    
    Database Table: `companies`
    
    Relationships:
        - A Company has MANY Users (HR staff)
        - A Company has MANY Jobs
    """

    # ── Table Name ────────────────────────────────────────
    # SQLAlchemy uses this to name the actual MySQL table
    __tablename__ = "companies"

    # ── Primary Key ───────────────────────────────────────
    # id: Auto-incrementing integer. Every company gets a unique ID.
    # index=True: Creates a DB index for fast lookups by ID.
    id = Column(Integer, primary_key=True, index=True)

    # ── Company Info ──────────────────────────────────────
    # name: Company's official name. Required. Indexed for fast search.
    name = Column(String(255), nullable=False, index=True)

    # industry: The company's industry (e.g., "Technology", "Finance")
    industry = Column(String(100), nullable=True)

    # website: Optional company website URL
    website = Column(String(255), nullable=True)

    # description: Long text about the company (shown to job seekers)
    description = Column(Text, nullable=True)

    # logo_path: Local file path to the company logo image
    logo_path = Column(String(500), nullable=True)

    # location: Where the company is based
    location = Column(String(255), nullable=True)

    # ── Status ────────────────────────────────────────────
    # is_active: Super Admin can deactivate a company (soft delete).
    # Default True = active. False = deactivated (can't login).
    is_active = Column(Boolean, default=True, nullable=False)

    # ── Timestamps ────────────────────────────────────────
    # created_at: Automatically set when the row is first inserted.
    # server_default=func.now(): The DB server sets this, not Python.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # updated_at: Automatically updates whenever the row changes.
    # onupdate=func.now(): DB updates this timestamp on every UPDATE.
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # ── Relationships ─────────────────────────────────────
    # users: All HR users who belong to this company.
    # back_populates="company": The User model has a `company` field
    #                           that links back here.
    # lazy="selectin": SQLAlchemy loads related users with one extra query
    #                  (not N+1 queries). Good default for async.
    users = relationship("User", back_populates="company", lazy="selectin")

    # jobs: All job postings created by this company's HR users.
    jobs = relationship("Job", back_populates="company", lazy="selectin")

    def __repr__(self):
        """String representation — useful for debugging."""
        return f"<Company id={self.id} name='{self.name}'>"
