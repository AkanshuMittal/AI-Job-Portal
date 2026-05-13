# ─────────────────────────────────────────────────────────
# models/__init__.py
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   Import all models here so that SQLAlchemy's `Base.metadata`
#   can discover them automatically when we call `create_all_tables()`.
# ─────────────────────────────────────────────────────────

from .user import User, UserRole
from .company import Company
from .job import Job
from .application import Application
from .seeker_profile import SeekerProfile
from .interview import Interview

# This list helps when using 'from models import *'
__all__ = [
    "User",
    "UserRole",
    "Company",
    "Job",
    "Application",
    "SeekerProfile",
    "Interview"
]
