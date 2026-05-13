# ─────────────────────────────────────────────────────────
# models/seeker_profile.py — Detailed Seeker Profile
# ─────────────────────────────────────────────────────────
# PURPOSE:
#   Stores all the "Candidate" specific data.
#   Each Job Seeker has exactly one SeekerProfile.
# ─────────────────────────────────────────────────────────

from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from core.database import Base

class SeekerProfile(Base):
    """
    Detailed profile for a Job Seeker.
    
    Database Table: `seeker_profiles`
    """
    __tablename__ = "seeker_profiles"

    id = Column(Integer, primary_key=True, index=True)
    
    # user_id: Links to the main User account.
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # ── Professional Details ──────────────────────────────
    headline = Column(String(255), nullable=True) # e.g., "Full Stack Developer"
    summary = Column(Text, nullable=True)        # Short bio
    
    # skills: Stored as a list of strings in JSON format.
    # e.g., ["Python", "React", "SQL"]
    skills = Column(JSON, nullable=True)
    
    # ── Documents ─────────────────────────────────────────
    # resume_path: Local path to the uploaded PDF/DOCX file.
    resume_path = Column(String(500), nullable=True)
    
    # parsed_data: Stores the structured data extracted by AI from the resume.
    parsed_data = Column(JSON, nullable=True)

    # ── Links ─────────────────────────────────────────────
    github_url = Column(String(255), nullable=True)
    linkedin_url = Column(String(255), nullable=True)
    portfolio_url = Column(String(255), nullable=True)

    # ── Relationships ─────────────────────────────────────
    user = relationship("User", back_populates="seeker_profile")
    applications = relationship("Application", back_populates="seeker", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SeekerProfile id={self.id} user_id={self.user_id}>"
