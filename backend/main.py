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
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os

from app.database import engine, Base, sync_additive_columns
from app.routers import auth, candidates, recruiters, admin, messages, ws, interview

# Import all models so Base knows about every table before create_all() runs.
from app import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Schema setup runs on server STARTUP, not at module import.

    These two calls open a real database connection. At module scope
    that made `import main` block on Postgres being up and responsive —
    so anything that merely imports this module (a test, a script, a
    tooling pass, `python -c "import main"`) would stall or fail on an
    unreachable database, with the traceback pointing at an import line
    rather than at the connection. Running them here keeps the import
    pure and puts the connection where it belongs: in the startup of
    the server that actually needs it.
    """
    Base.metadata.create_all(bind=engine)

    # create_all() cannot add a column to a table that already exists,
    # so nullable columns introduced after a table was first created
    # are applied here. See app/database.py for what this does and does
    # not cover.
    added_columns = sync_additive_columns()
    if added_columns:
        logging.getLogger("uvicorn.error").info(
            "Schema sync added missing columns: %s", ", ".join(added_columns)
        )

    os.makedirs("uploads/cvs", exist_ok=True)
    os.makedirs("uploads/chat", exist_ok=True)

    yield


# StaticFiles checks that the directory exists when it is constructed,
# and the mount below runs at import — so this cannot wait for lifespan.
os.makedirs("uploads/cvs", exist_ok=True)
os.makedirs("uploads/chat", exist_ok=True)

app = FastAPI(
    title="EquityEngine API",
    description="NLP-based bias-mitigating recruitment system for African tech talent",
    version="0.1.0",
    lifespan=lifespan,
)

# During development, allow the Vite dev server (default port 5173) to
# call the API directly. Tighten this before any real deployment.
#
# expose_headers is needed for the PDF download endpoints (the
# candidate's optimized profile and the admin bias report). CORS hides
# every non-simple response header from browser JavaScript by default,
# and Content-Disposition is non-simple — so without this the frontend
# cannot read the filename the server chose and has to fall back to a
# hardcoded one. The download itself works either way; this is what
# makes the saved file come out named <Full_Name>_CV.pdf.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://equityengine.vercel.app",
        "https://equityengine-eight.vercel.app",
    ],
    allow_origin_regex=r"https://equityengine-.*-switch19\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
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
