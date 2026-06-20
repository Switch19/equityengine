from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import auth, candidates, recruiters, jobs
from app.routers import auth, candidates, recruiters, jobs, admin
from app.routers import auth, candidates, recruiters, jobs, admin, messages

from app.models import message
# Create all database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EquityEngine API",
    description="A Bias-Mitigating AI-Powered Recruitment Platform",
    version="1.0.0"
)

# Allow React frontend to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(candidates.router, prefix="/api/candidates", tags=["Candidates"])
app.include_router(recruiters.router, prefix="/api/recruiters", tags=["Recruiters"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(messages.router, prefix="/api/messages", tags=["Messages"])
@app.get("/")
def root():
    return {
        "message": "Welcome to EquityEngine API",
        "status": "running",
        "version": "1.0.0"
    }