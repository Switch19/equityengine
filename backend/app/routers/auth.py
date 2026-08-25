"""
Authentication endpoints: register, login, /me, and password reset.
"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, CandidateProfile, UserRole
from app.schemas import (
    UserRegister, UserLogin, UserOut, Token, ForgotPasswordRequest, ResetPasswordRequest,
)
from app.security import hash_password, verify_password, create_access_token
from app.deps import get_current_user
from app.services.email_service import send_welcome_email, send_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])

RESET_TOKEN_EXPIRY_MINUTES = 60


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        consent_given=payload.consent_given,
        consent_at=datetime.utcnow() if payload.consent_given else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # A candidate gets an empty CandidateProfile row created immediately,
    # so every other candidate-facing endpoint can assume it exists
    # rather than checking for it everywhere.
    if user.role == UserRole.candidate:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()

    # Best-effort — send_welcome_email() already never raises (see
    # email_service.py), so a misconfigured or unreachable SMTP server
    # cannot break registration itself.
    await send_welcome_email(user.email, user.full_name, user.role.value)

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return Token(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return Token(access_token=access_token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Always returns the same generic response whether or not the email
    exists on the platform — confirming or denying an email's
    existence via this endpoint's response would let someone enumerate
    registered accounts, which is a real (if minor) information leak
    in most auth systems that this project's threat model doesn't need
    to accept for free.
    """
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    generic_response = {"detail": "If an account with that email exists, a reset link has been sent."}

    if not user:
        return generic_response

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)
    db.commit()

    await send_password_reset_email(user.email, user.full_name, token)
    return generic_response


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == payload.token).first()

    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    user.hashed_password = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return {"detail": "Password has been reset. You can now log in with your new password."}
