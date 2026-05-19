from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from core.database import get_db
from api.deps import get_current_hr
from models.user import User
from models.job import Job
from models.application import Application
from models.seeker_profile import SeekerProfile
from models.company import Company
from schemas.job import JobCreate, JobOut, JobUpdate
from schemas.application import ApplicationOut

router = APIRouter(prefix="/hr", tags=["Partner HR"])

@router.get("/my-company")
async def get_my_company(
    db: AsyncSession = Depends(get_db),
    hr: User = Depends(get_current_hr)
):
    """
    Get the details of the HR user's company.
    """
    if not hr.company_id:
        raise HTTPException(status_code=400, detail="HR user is not linked to a company")
    
    result = await db.execute(select(Company).where(Company.id == hr.company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: JobCreate,
    db: AsyncSession = Depends(get_db),
    hr: User = Depends(get_current_hr)
):
    """
    HR creates a new job posting for their company.
    """
    if not hr.company_id:
        raise HTTPException(status_code=400, detail="HR user is not linked to a company")
    
    new_job = Job(
        **job_data.model_dump(),
        company_id=hr.company_id,
        creator_id=hr.id
    )
    # 3. Save job
    db.add(new_job)
    await db.commit()
    
    # 4. Load company relationship for the response
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.company))
        .where(Job.id == new_job.id)
    )
    return result.scalar_one()


@router.get("/jobs", response_model=List[JobOut])
async def list_my_jobs(
    db: AsyncSession = Depends(get_db),
    hr: User = Depends(get_current_hr)
):
    """
    List all jobs posted by the HR user's company.
    """
    result = await db.execute(
        select(Job)
        .options(selectinload(Job.company))
        .where(Job.company_id == hr.company_id)
    )
    return result.scalars().all()

@router.get("/applications/{job_id}", response_model=List[ApplicationOut])
async def get_job_applications(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    hr: User = Depends(get_current_hr)
):
    """
    List all applications for a specific job posted by the HR user's company.
    """
    # Verify job belongs to this HR's company
    job_result = await db.execute(select(Job).where(Job.id == job_id, Job.company_id == hr.company_id))
    if not job_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not authorized to view applications for this job")
    
    query = select(Application).where(Application.job_id == job_id).options(
        selectinload(Application.seeker).selectinload(SeekerProfile.user),
        selectinload(Application.job).selectinload(Job.company),
        selectinload(Application.interview)
    )
    result = await db.execute(query)
    return result.scalars().all()
