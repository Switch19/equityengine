"""
Creates an admin account directly in the database.

Registration via /auth/register deliberately rejects role="admin"
(see schemas.py's no_admin_self_registration validator) — admin
accounts are meant to be provisioned out-of-band, not self-served.
This script is that out-of-band mechanism.

Usage (from the backend/ folder, with your venv activated):
    python create_admin.py
"""
import getpass
from datetime import datetime

from app.database import SessionLocal, engine, Base
from app.models import User, UserRole
from app.security import hash_password

# Ensure tables exist (harmless if they already do — same as main.py's startup step)
from app import models  # noqa: F401
Base.metadata.create_all(bind=engine)


def main():
    print("=== EquityEngine: Create Admin Account ===\n")
    email = input("Admin email: ").strip().lower()
    full_name = input("Admin full name: ").strip()
    password = getpass.getpass("Admin password (min 8 characters): ")

    if len(password) < 8:
        print("Password must be at least 8 characters. Aborting.")
        return

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"An account with email '{email}' already exists (role: {existing.role.value}).")
            return

        admin = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=UserRole.admin,
            consent_given=True,
            consent_at=datetime.utcnow(),
        )
        db.add(admin)
        db.commit()
        print(f"\nAdmin account created: {email}")
        print("Log in via POST /auth/login with this email and password.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
