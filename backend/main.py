"""
FastAPI application entrypoint.

Run with:  uvicorn main:app --reload
(from inside the backend/ folder, with your venv activated)

On startup, this creates any tables that don't yet exist in the
database using SQLAlchemy's create_all(). This is deliberately simple
rather than using Alembic migrations, since for a final-year project
built by one person, a migration framework adds process overhead
without a corresponding benefit — there's no team to coordinate schema
changes with. If you extend this project later with multiple
contributors, Alembic (already in your installed packages) would be
the natural next step; note this design decision in Chapter 4.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.database import engine, Base
from app.routers import auth, candidates, recruiters, admin, messages, ws, interview

# Import all models so Base knows about every table before create_all() runs.
from app import models  # noqa: F401

Base.metadata.create_all(bind=engine)

os.makedirs("uploads/cvs", exist_ok=True)
os.makedirs("uploads/chat", exist_ok=True)

app = FastAPI(
    title="EquityEngine API",
    description="NLP-based bias-mitigating recruitment system for African tech talent",
    version="0.1.0",
)

# During development, allow the Vite dev server (default port 5173) to
# call the API directly. Tighten this before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router)
app.include_router(candidates.router)
app.include_router(recruiters.router)
app.include_router(admin.router)
app.include_router(messages.router)
app.include_router(messages.notifications_router)
app.include_router(ws.router)
app.include_router(interview.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "EquityEngine API"}


@app.get("/health")
def health():
    return {"status": "healthy"}
