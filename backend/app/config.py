"""
Centralised application settings.

Every other module reads configuration from here rather than calling
os.getenv() directly, so there is exactly one place to change if a
setting moves. Uses python-dotenv rather than pydantic-settings, since
the latter is a separate package you may not have installed.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# backend/app/config.py -> parent is app/, parent.parent is backend/.
# Used below to resolve EMBEDDING_MODEL_PATH to an absolute path.
BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _resolve_model_path(raw_path: str) -> str:
    """
    EMBEDDING_MODEL_PATH is meant to point at a LOCAL folder
    (backend/models/all-MiniLM-L6-v2/) so Sentence Transformers never
    needs network access. If given as a bare relative path like
    "models/all-MiniLM-L6-v2", Python resolves that relative to the
    CURRENT WORKING DIRECTORY the process was launched from — not
    relative to this config file or to backend/. If uvicorn is
    launched from anywhere other than the backend/ folder itself
    (e.g. from an IDE's default terminal cwd, or a task runner), that
    relative path silently points at the wrong location, sentence-
    transformers can't find a local model there, and it falls back to
    treating the string as a Hugging Face Hub repo ID instead —
    which is exactly the confusing "Repository Not Found" /
    "Invalid username or password" error this caused. Resolving to an
    absolute path here, once, removes that entire failure mode.
    """
    path = Path(raw_path)
    if path.is_absolute():
        return str(path)
    return str((BACKEND_ROOT / path).resolve())


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://equityuser:equity2025@localhost:5432/equityengine"
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    EMBEDDING_MODEL_PATH: str = _resolve_model_path(
        os.getenv("EMBEDDING_MODEL_PATH", "models/all-MiniLM-L6-v2")
    )

    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "EquityEngine")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")


settings = Settings()

if not settings.SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set. Check that backend/.env exists and is being loaded "
        "from the directory you run uvicorn from."
    )

# If local folder doesn't exist, fallback to Hugging Face Hub ID directly
if not Path(settings.EMBEDDING_MODEL_PATH).exists():
    settings.EMBEDDING_MODEL_PATH = "sentence-transformers/all-MiniLM-L6-v2"
