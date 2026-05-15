from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from core.database import get_db
from core.security import hash_password
from api.deps import get_current_super_admin
from models.company import Company
from models.user import User, UserRole
from models.job import Job
from models.application import Application
from schemas.company import CompanyCreate, CompanyOut
from schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/admin", tags=["Super Admin"])

@router.post("/companies", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_super_admin)
):
    """
    Super Admin creates a new partner company.
    """
    # Check if company with same name exists
    result = await db.execute(select(Company).where(Company.name == company_data.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Company name already exists")
    
    new_company = Company(**company_data.model_dump())
    db.add(new_company)
    await db.commit()
    await db.refresh(new_company)
    return new_company

@router.get("/companies", response_model=List[CompanyOut])
async def list_companies(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_super_admin)
):
    """
    List all partner companies.
    """
    result = await db.execute(select(Company))
    return result.scalars().all()

@router.post("/hr", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_hr_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_super_admin)
):
    """
    Super Admin creates an HR user for a company.
    """
    if user_data.role != UserRole.HR:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only HR users may be created with this endpoint. Set role to hr."
        )

    if user_data.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_id is required when creating an HR user."
        )

    company_result = await db.execute(
        select(Company).where(Company.id == user_data.company_id, Company.is_active == True)
    )
    company = company_result.scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company with id={user_data.company_id} not found or inactive."
        )

    existing_result = await db.execute(select(User).where(User.email == user_data.email))
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{user_data.email}' is already registered."
        )

    new_hr = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
        role=UserRole.HR,
        company_id=user_data.company_id,
        is_active=True,
        is_verified=False,
    )
    db.add(new_hr)
    await db.commit()
    await db.refresh(new_hr)
    return UserOut.model_validate(new_hr)


@router.get("/stats")
async def get_platform_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_super_admin)
):
    """
    Get high-level platform statistics.
    """
    total_companies = await db.scalar(select(func.count(Company.id)))
    total_jobs = await db.scalar(select(func.count(Job.id)))
    total_seekers = await db.scalar(select(func.count(User.id)).where(User.role == UserRole.SEEKER))
    total_apps = await db.scalar(select(func.count(Application.id)))
    
    return {
        "total_companies": total_companies,
        "total_jobs": total_jobs,
        "total_seekers": total_seekers,
        "total_applications": total_apps
    }
