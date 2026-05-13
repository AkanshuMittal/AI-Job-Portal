# ─────────────────────────────────────────────────────────
# models/application.py — Job Application Model
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   Links a Seeker to a Job. 
#   This is where the "Match Score" and "Hiring Status" live.
# ─────────────────────────────────────────────────────────

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from core.database import Base


# ── Application Status Enum ──────────────────────────────
class ApplicationStatus(str, enum.Enum):
    APPLIED = "applied"           # Initial state
    SHORTLISTED = "shortlisted"   # HR liked the profile
    INTERVIEWING = "interviewing" # Currently in AI interview phase
    REJECTED = "rejected"         # HR rejected
    HIRED = "hired"               # Final selection


class Application(Base):
    """
    Represents a specific application for a job.
    
    Database Table: `applications`
    """
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)

    # ── Links ─────────────────────────────────────────────
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    seeker_id = Column(Integer, ForeignKey("seeker_profiles.id", ondelete="CASCADE"), nullable=False)

    # ── AI Scoring ────────────────────────────────────────
    # match_score: Calculated by our AI Matching Engine (0.0 to 100.0)
    match_score = Column(Float, default=0.0)
    
    # score_explanation: Brief AI explanation of why this score was given.
    score_explanation = Column(String(1000), nullable=True)

    # ── Tracking ──────────────────────────────────────────
    status = Column(Enum(ApplicationStatus), default=ApplicationStatus.APPLIED, nullable=False)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ── Relationships ─────────────────────────────────────
    job = relationship("Job", back_populates="applications")
    seeker = relationship("SeekerProfile", back_populates="applications")
    # interview: Link to the AI Interview record (Phase 3)
    interview = relationship("Interview", back_populates="application", uselist=False)

    def __repr__(self):
        return f"<Application id={self.id} job_id={self.job_id} status='{self.status}'>"
