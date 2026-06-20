from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    regional_identifier = Column(String, nullable=True)
    raw_resume_path = Column(String, nullable=True)
    optimized_resume_path = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    skills = Column(Text, nullable=True)
    skill_score = Column(Float, default=0.0)
    visibility_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="profile")