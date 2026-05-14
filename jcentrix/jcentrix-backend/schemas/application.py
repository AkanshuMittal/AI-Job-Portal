from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
from enum import Enum

from schemas.seeker_profile import SeekerProfileBase
from schemas.user import UserOut

class ApplicationStatus(str, Enum):
    APPLIED = "applied"           # Initial state
    SHORTLISTED = "shortlisted"   # HR liked the profile
    INTERVIEWING = "interviewing" # Currently in AI interview phase
    REJECTED = "rejected"         # HR rejected
    HIRED = "hired"               # Final selection

class ApplicationBase(BaseModel):
    job_id: int

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationUpdate(BaseModel):
    status: ApplicationStatus

class SeekerProfileWithUser(SeekerProfileBase):
    id: int
    user: Optional[UserOut] = None

    class Config:
        from_attributes = True

class ApplicationOut(ApplicationBase):
    id: int
    seeker_id: int
    status: ApplicationStatus
    match_score: Optional[float] = None
    applied_at: datetime
    seeker: Optional[SeekerProfileWithUser] = None

    class Config:
        from_attributes = True
