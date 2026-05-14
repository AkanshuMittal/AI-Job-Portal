from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class SeekerProfileBase(BaseModel):
    headline: Optional[str] = None
    summary: Optional[str] = None
    skills: Optional[Any] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None

class SeekerProfileCreate(SeekerProfileBase):
    pass

class SeekerProfileUpdate(SeekerProfileBase):
    pass

class SeekerProfileOut(SeekerProfileBase):
    id: int
    user_id: int
    resume_path: Optional[str] = None
    parsed_data: Optional[Any] = None

    class Config:
        from_attributes = True
