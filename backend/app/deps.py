"""
Shared FastAPI dependencies. Every protected route in the app takes
one of these as a parameter rather than re-implementing token parsing.

Usage in a router:
    @router.get("/me")
    def read_me(current_user: User = Depends(get_current_user)):
        ...

    @router.post("/jobs")
    def post_job(current_user: User = Depends(require_role(UserRole.recruiter))):
        ...
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    return user


def require_role(*allowed_roles: UserRole):
    """
    Returns a dependency that only allows through users whose role is
    in allowed_roles. Used to protect recruiter-only or admin-only
    endpoints, e.g. Depends(require_role(UserRole.admin)).
    """

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires role: {', '.join(r.value for r in allowed_roles)}",
            )
        return current_user

    return role_checker
