from pydantic import BaseModel
from typing import Optional

class JobCreate(BaseModel):
    title: str
    description: str
    required_skills: str
    location: Optional[str] = None

class JobResponse(BaseModel):
    id: int
    title: str
    description: str
    required_skills: str
    location: Optional[str]
    recruiter_id: int
    is_active: bool

    class Config:
        from_attributes = True