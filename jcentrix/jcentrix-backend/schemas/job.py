from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum

from .company import CompanyOut

class JobStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"

class JobBase(BaseModel):
    title: str
    description: str
    requirements: Optional[str] = None
    short_description: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = 'full_time'
    salary_range: Optional[str] = None
    experience_required: Optional[str] = None
    status: JobStatus = JobStatus.PUBLISHED

class JobCreate(JobBase):
    pass

class JobUpdate(JobBase):
    title: Optional[str] = None
    description: Optional[str] = None

class JobOut(BaseModel):
    id: int
    title: str
    description: str
    requirements: Optional[str] = None
    short_description: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    salary_range: Optional[str] = None
    experience_required: Optional[str] = None
    status: JobStatus = JobStatus.PUBLISHED
    company_id: int
    creator_id: Optional[int] = None
    company: Optional[CompanyOut] = None
    created_at: datetime

    class Config:
        from_attributes = True
