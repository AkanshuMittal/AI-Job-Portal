from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List

from core.database import get_db
from api.deps import get_current_seeker, get_current_user
from models.user import User
from models.job import Job, JobStatus
from models.application import Application
from models.seeker_profile import SeekerProfile
from schemas.job import JobCreate, JobOut
from schemas.application import ApplicationCreate, ApplicationOut
from schemas.seeker_profile import SeekerProfileCreate, SeekerProfileOut, SeekerProfileUpdate

router = APIRouter(prefix="/seeker", tags=["Job Seeker"])

@router.post("/profile", response_model=SeekerProfileOut)
async def create_or_update_profile(
    profile_data: SeekerProfileCreate,
    db: AsyncSession = Depends(get_db),
    seeker: User = Depends(get_current_seeker)
):
    """
    Job Seeker creates or updates their profile.
    """
    result = await db.execute(select(SeekerProfile).where(SeekerProfile.user_id == seeker.id))
    profile = result.scalar_one_or_none()
    
    if profile:
        # Update existing profile
        for key, value in profile_data.model_dump().items():
            setattr(profile, key, value)
    else:
        # Create new profile
        profile = SeekerProfile(**profile_data.model_dump(), user_id=seeker.id)
        db.add(profile)
    
    await db.commit()
    await db.refresh(profile)
    return profile

@router.get("/jobs", response_model=List[JobOut])
async def search_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search all published jobs. (Open to all authenticated users)
    """
    result = await db.execute(select(Job).where(Job.status == "published"))
    return result.scalars().all()

@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a single published job by ID with company details.
    """
    job_result = await db.execute(
        select(Job)
        .options(selectinload(Job.company))
        .where(Job.id == job_id, Job.status == JobStatus.PUBLISHED)
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/apply/{job_id}", response_model=ApplicationOut)
async def apply_to_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    seeker: User = Depends(get_current_seeker)
):
    """
    Apply for a job.
    """
    # 1. Check if job exists and is published
    job_result = await db.execute(select(Job).where(Job.id == job_id, Job.status == "published"))
    if not job_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found or not accepting applications")

    # 1.5. Fetch Seeker Profile (required to apply)
    profile_result = await db.execute(select(SeekerProfile).where(SeekerProfile.user_id == seeker.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="You must create a profile before applying to jobs")

    # 2. Check if already applied
    app_result = await db.execute(select(Application).where(
        Application.job_id == job_id, 
        Application.seeker_id == profile.id
    ))
    if app_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You have already applied for this job")
    
    # 3. Create application
    new_app = Application(job_id=job_id, seeker_id=profile.id)
    db.add(new_app)
    await db.commit()
    await db.refresh(new_app)
    return new_app
