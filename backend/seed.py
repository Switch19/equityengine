"""
EquityEngine Seed Script
Run: python seed.py
Resets demo data and creates realistic test users, jobs, and interactions.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.profile import CandidateProfile
from app.models.job import Job
from app.models.audit import AuditLog
from app.models.message import Message
from passlib.context import CryptContext
import shutil

Base.metadata.create_all(bind=engine)
db = SessionLocal()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_pw(pw): return pwd_context.hash(pw)

print("🌱 Starting EquityEngine seed...")

# ── Clear existing demo data ──────────────────────────────────────────────────
print("🧹 Clearing old demo data...")
db.query(Message).delete()
db.query(AuditLog).delete()
db.query(CandidateProfile).delete()
db.query(Job).delete()
db.query(User).filter(User.email != "admin@equityengine.com").delete()
db.commit()

# ── Candidates ────────────────────────────────────────────────────────────────
print("👤 Creating candidate accounts...")

candidates_data = [
    {
        "email": "chukwuemeka@equityengine.com",
        "full_name": "Chukwuemeka Obi",
        "password": "demo1234",
        "skills": "python, javascript, typescript, react, node.js, fastapi, django, postgresql, mysql, mongodb, redis, docker, aws, git, github, linux, rest api, machine learning, nlp, tensorflow, html, css, tailwind, java, go, figma, sql, firebase, supabase",
        "visibility_score": 40.0,
        "skill_score": 100.0
    },
    {
        "email": "amara@equityengine.com",
        "full_name": "Amara Nwosu",
        "password": "demo1234",
        "skills": "html, css, javascript, react, tailwind, figma, git, github, bootstrap, vue",
        "visibility_score": 60.0,
        "skill_score": 0.0
    },
    {
        "email": "tunde@equityengine.com",
        "full_name": "Tunde Adeyemi",
        "password": "demo1234",
        "skills": "python, django, fastapi, postgresql, redis, docker, kubernetes, aws, linux, git, github, rest api, graphql, celery, nginx",
        "visibility_score": 50.0,
        "skill_score": 0.0
    },
    {
        "email": "ngozi@equityengine.com",
        "full_name": "Ngozi Eze",
        "password": "demo1234",
        "skills": "python, machine learning, tensorflow, pytorch, nlp, pandas, numpy, sql, postgresql, git, github, jupyter, scikit-learn, data science",
        "visibility_score": 45.0,
        "skill_score": 0.0
    },
]

candidate_users = []
for c in candidates_data:
    user = User(
        email=c["email"],
        full_name=c["full_name"],
        hashed_password=hash_pw(c["password"]),
        role=UserRole.candidate
    )
    db.add(user)
    db.flush()

    profile = CandidateProfile(
        user_id=user.id,
        skills=c["skills"],
        visibility_score=c["visibility_score"],
        skill_score=c["skill_score"],
        regional_identifier=f"Senior Full-Stack Professional"
    )
    db.add(profile)
    candidate_users.append(user)
    print(f"   ✅ {c['full_name']} ({c['email']})")

db.commit()

# ── Recruiters ────────────────────────────────────────────────────────────────
print("🏢 Creating recruiter accounts...")

recruiters_data = [
    {"email": "techcorp@equityengine.com", "full_name": "TechCorp Global HR", "password": "demo1234"},
    {"email": "startupng@equityengine.com", "full_name": "StartupNG Talent", "password": "demo1234"},
    {"email": "datahive@equityengine.com", "full_name": "DataHive Inc Recruiting", "password": "demo1234"},
]

recruiter_users = []
for r in recruiters_data:
    user = User(
        email=r["email"],
        full_name=r["full_name"],
        hashed_password=hash_pw(r["password"]),
        role=UserRole.recruiter
    )
    db.add(user)
    recruiter_users.append(user)
    print(f"   ✅ {r['full_name']} ({r['email']})")

db.commit()

# ── Jobs ──────────────────────────────────────────────────────────────────────
print("💼 Creating job postings...")

jobs_data = [
    {
        "title": "Senior Python Developer",
        "description": "We are looking for an experienced Python developer to join our remote team building scalable APIs.",
        "required_skills": "python, fastapi, postgresql, docker, git, react",
        "location": "Remote (Global)",
        "recruiter_idx": 0
    },
    {
        "title": "Full-Stack Engineer",
        "description": "Join our fast-growing Lagos-based startup to build our core product using modern web technologies.",
        "required_skills": "javascript, react, node.js, postgresql, git, html, css",
        "location": "Remote / Lagos",
        "recruiter_idx": 1
    },
    {
        "title": "Machine Learning Engineer",
        "description": "Help us build intelligent data pipelines and ML models for our analytics platform.",
        "required_skills": "python, machine learning, tensorflow, sql, git, docker",
        "location": "Remote",
        "recruiter_idx": 2
    },
]

job_objects = []
for j in jobs_data:
    db.flush()
    recruiter = recruiter_users[j["recruiter_idx"]]
    job = Job(
        recruiter_id=recruiter.id,
        title=j["title"],
        description=j["description"],
        required_skills=j["required_skills"],
        location=j["location"],
        is_active=True
    )
    db.add(job)
    db.flush()
    job_objects.append(job)
    print(f"   ✅ {j['title']} — posted by {recruiter.full_name}")

db.commit()

# ── Audit Interactions ─────────────────────────────────────────────────────────
print("📊 Simulating recruiter interactions for Bias Audit Engine...")

interactions = [
    (0, 0, 0, "viewed_anonymized", True),
    (0, 1, 0, "viewed_anonymized", True),
    (0, 2, 0, "viewed_anonymized", True),
    (0, 3, 0, "viewed_anonymized", True),
    (0, 0, 0, "identity_revealed", False),
    (0, 2, 0, "identity_revealed", False),
    (1, 0, 1, "viewed_anonymized", True),
    (1, 1, 1, "viewed_anonymized", True),
    (1, 2, 1, "viewed_anonymized", True),
    (1, 0, 1, "identity_revealed", False),
    (2, 0, 2, "viewed_anonymized", True),
    (2, 3, 2, "viewed_anonymized", True),
    (2, 3, 2, "identity_revealed", False),
    (0, 0, 0, "talent_pool_view", True),
    (1, 1, 1, "talent_pool_view", True),
]

for rec_idx, cand_idx, job_idx, action, was_anon in interactions:
    log = AuditLog(
        recruiter_id=recruiter_users[rec_idx].id,
        candidate_id=candidate_users[cand_idx].id,
        job_id=job_objects[job_idx].id,
        action=action,
        was_anonymized=was_anon
    )
    db.add(log)

db.commit()
print(f"   ✅ {len(interactions)} interactions logged")

# ── Sample Messages ───────────────────────────────────────────────────────────
print("💬 Creating sample chat messages...")

messages = [
    (recruiter_users[0].id, candidate_users[0].id, job_objects[0].id,
     "Hello! I reviewed your profile and I'm very impressed with your Python and FastAPI skills. Would you be available for an interview this week?"),
    (candidate_users[0].id, recruiter_users[0].id, job_objects[0].id,
     "Thank you so much! Yes, I'm available. I'm excited about this opportunity at TechCorp Global."),
    (recruiter_users[0].id, candidate_users[0].id, job_objects[0].id,
     "Great! How does Wednesday at 3pm WAT work for you? We'll do a 45-minute technical interview via Google Meet."),
    (candidate_users[0].id, recruiter_users[0].id, job_objects[0].id,
     "Wednesday at 3pm WAT works perfectly. I'll send my calendar invite. Looking forward to it!"),
]

for sender_id, receiver_id, job_id, content in messages:
    msg = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        job_id=job_id,
        content=content
    )
    db.add(msg)

db.commit()
print(f"   ✅ {len(messages)} messages created")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n✅ Seed complete! Here's your demo data:\n")
print(f"   👤 Candidates: {len(candidates_data)}")
print(f"   🏢 Recruiters: {len(recruiters_data)}")
print(f"   💼 Jobs: {len(jobs_data)}")
print(f"   📊 Audit logs: {len(interactions)}")
print(f"   💬 Messages: {len(messages)}")
print(f"\n🔑 All demo accounts use password: demo1234")
print(f"\n👤 Candidate logins:")
for c in candidates_data:
    print(f"   {c['email']}")
print(f"\n🏢 Recruiter logins:")
for r in recruiters_data:
    print(f"   {r['email']}")
print(f"\n🔐 Admin login: admin@equityengine.com / admin2025")
print(f"\n🚀 Start your servers and go to http://localhost:5173")

db.close()