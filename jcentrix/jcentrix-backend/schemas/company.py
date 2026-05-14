from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class CompanyBase(BaseModel):
    name: str
    description: Optional[str] = None
    website: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(CompanyBase):
    name: Optional[str] = None

class CompanyOut(CompanyBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
