"""
Seed data for local testing and screenshots — NOT a substitute for
real empirical results.

IMPORTANT, read before citing any number this script produces in
Chapter 4: this script's PURPOSE is to (a) populate every page with
realistic non-empty states so you can take real screenshots, and
(b) prove the Bias Audit Engine's computation pipeline works
end-to-end without crashing. It is deliberately NOT designed to
produce a specific Visibility Gap outcome — the shortlisting
simulation below uses the same evidence-score threshold for both
Standard and BDIOF applications, and only adds SYMMETRIC, mean-zero
random noise to Standard-mode decisions (representing that additional,
unspecified subjective factors enter a recruiter's judgement once
identity is visible — without hard-coding which direction those
factors point). Whatever Visibility Gap number falls out of that is
genuinely not predetermined.

For your actual Chapter 4 Results section, replace or supplement this
with real usage: real candidates building real profiles, and real
recruiters (e.g. your lecturers) making real shortlisting decisions
across Standard and BDIOF postings. That is what makes the Visibility
Gap finding a genuine empirical result rather than a demonstration.

Run from the backend/ folder, with your venv activated:
    python seed_data.py
"""
import random
from datetime import datetime, timedelta

from app.database import SessionLocal, engine, Base
from app import models  # noqa: F401 — registers all models with Base
from app.models import (
    User, UserRole, Company, CandidateProfile, Job, ScreeningMode,
    Application, ApplicationStatus, AuditLog,
)
from app.security import hash_password
from app.data.skill_taxonomy import ALL_SKILLS
from app.data.regional_terms import AFRICAN_INSTITUTIONS, AFRICAN_TECH_PROGRAMMES
from app.services.competency_engine import recompute_competency_profile, compute_job_specific_evidence_score
from app.services.audit_service import log_action

Base.metadata.create_all(bind=engine)

random.seed(42)  # deterministic across runs, so re-seeding is reproducible for debugging

FIRST_NAMES = [
    "Adaeze", "Chidi", "Ngozi", "Emeka", "Folake", "Tunde", "Amara", "Kwame",
    "Zainab", "Ibrahim", "Chiamaka", "Oluwaseun", "Blessing", "Chukwuemeka",
    "Aisha", "David", "Mary", "James", "Sarah", "Michael", "Grace", "Daniel",
]
LAST_NAMES = [
    "Okonkwo", "Adeyemi", "Okafor", "Balogun", "Eze", "Mensah", "Abubakar",
    "Nwosu", "Adebayo", "Yusuf", "Chukwu", "Okoro", "Bello", "Ibe",
]

CERT_POOL = [
    ("AWS Certified Solutions Architect", "Amazon Web Services"),
    ("Google Cloud Professional Data Engineer", "Google"),
    ("ALX Software Engineering Programme", "ALX Africa"),
    ("Andela Fellowship", "Andela"),
    ("Genesys Hub Full-Stack Track", "Genesys Hub"),
    ("Introduction to Python", "Coursera"),
    ("Meta Front-End Developer Certificate", "Meta"),
]

PROJECT_DESCRIPTIONS = [
    "Built a REST API for a payments platform using FastAPI and PostgreSQL, handling authentication and rate limiting.",
    "Developed a React dashboard for real-time analytics, integrating WebSocket updates and Recharts visualisations.",
    "Created a machine learning pipeline for churn prediction using scikit-learn and pandas.",
    "Implemented a CI/CD pipeline with Docker and GitHub Actions for a microservices architecture.",
    "Built a mobile-first e-commerce storefront with React Native and Stripe integration.",
    "Designed a database schema and ORM layer for a multi-tenant SaaS product.",
]

JOB_TITLES = [
    "Backend Developer", "Frontend Engineer", "Full-Stack Developer",
    "Data Analyst", "DevOps Engineer", "Mobile Developer",
    "Machine Learning Engineer", "QA Engineer",
]

COMPANY_NAMES = [
    "Zenith Digital Labs", "Riverbank Technologies", "Nova Fintech",
    "Cobalt Systems", "Delta Cloud Works", "Highline Analytics",
]


def create_candidates(db, n=20):
    candidates = []
    for i in range(n):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{i}@example.com"

        user = User(
            email=email,
            full_name=f"{first} {last}",
            hashed_password=hash_password("password123"),
            role=UserRole.candidate,
            consent_given=True,
            consent_at=datetime.utcnow(),
        )
        db.add(user)
        db.flush()  # get user.id without a full commit

        profile = CandidateProfile(user_id=user.id, location=random.choice(
            ["Lagos, Nigeria", "Nairobi, Kenya", "Accra, Ghana", "Cape Town, South Africa", None]
        ))

        # --- CV pipeline: give ~85% of candidates CV-derived data ---
        if random.random() < 0.85:
            profile.cv_skills = random.sample(ALL_SKILLS, k=random.randint(3, 7))
            profile.cv_projects = [
                {"title": d.split(".")[0][:60], "description": d}
                for d in random.sample(PROJECT_DESCRIPTIONS, k=random.randint(1, 3))
            ]
            profile.experience_level = random.choice(
                ["Entry-level (0-1 yrs)", "Junior (1-3 yrs)", "Mid-level (3-6 yrs)", "Senior (6+ yrs)"]
            )
            profile.ats_score = random.randint(40, 95)

            # ~40% of candidates with a CV show a detected African institution/programme
            regional = {"institutions": [], "tech_programmes": [], "other_terms": [], "all_matches": []}
            if random.random() < 0.4:
                inst = random.choice(AFRICAN_INSTITUTIONS)
                regional["institutions"] = [inst]
                regional["all_matches"] = [inst]
                profile.education_tier = "Graduate"
            elif random.random() < 0.5:
                prog = random.choice(AFRICAN_TECH_PROGRAMMES)
                regional["tech_programmes"] = [prog]
                regional["all_matches"] = [prog]
                profile.education_tier = "Bootcamp"
            else:
                profile.education_tier = "Self-Taught"
            profile.regional_terms = regional
        else:
            profile.education_tier = "Undisclosed"

        # --- GitHub pipeline: ~65% linked ---
        if random.random() < 0.65:
            profile.github_username = f"{first.lower()}-{last.lower()}"
            langs = random.sample(["Python", "JavaScript", "TypeScript", "Go", "Java"], k=random.randint(1, 3))
            profile.github_languages = {lang: random.randint(1, 8) for lang in langs}
            profile.github_activity = {
                "public_repos": random.randint(2, 25),
                "followers": random.randint(0, 50),
                "total_stars": random.randint(0, 40),
                "original_repos_count": random.randint(2, 20),
                "inferred_skills": random.sample(ALL_SKILLS, k=random.randint(1, 4)),
            }
            profile.github_repos = [
                {
                    "name": f"project-{j}",
                    "description": random.choice(PROJECT_DESCRIPTIONS),
                    "language": random.choice(langs),
                    "stars": random.randint(0, 15),
                    "pushed_at": (datetime.utcnow() - timedelta(days=random.randint(5, 400))).isoformat() + "Z",
                    "created_at": (datetime.utcnow() - timedelta(days=random.randint(400, 900))).isoformat() + "Z",
                }
                for j in range(random.randint(1, 5))
            ]
            profile.learning_trajectory = {
                "trend": random.choice(["Increasing", "Stable", "Declining", "Insufficient data"]),
                "repos_active_last_12mo": random.randint(0, 5),
                "repos_active_prior_12mo": random.randint(0, 5),
            }
            profile.g_act_score = round(random.uniform(0.2, 0.95), 3)

        # --- Community pipeline: ~50% have at least one certification ---
        if random.random() < 0.5:
            cert_name, issuer = random.choice(CERT_POOL)
            tier = 1 if any(k in cert_name.lower() or k in issuer.lower()
                             for k in ["aws", "google", "andela", "alx", "genesys"]) else 2
            profile.certifications = [{
                "name": cert_name, "issuer": issuer, "date_earned": "2025",
                "tier": tier, "added_at": datetime.utcnow().isoformat(),
            }]
        if random.random() < 0.3:
            profile.stackoverflow_data = {
                "user_id": str(random.randint(1000000, 9999999)),
                "reputation": random.randint(1, 5000),
                "badge_counts": {"bronze": random.randint(0, 10), "silver": random.randint(0, 3), "gold": 0},
            }
        profile.c_peer_score = round(random.uniform(0.0, 0.8), 3)

        db.add(profile)
        db.flush()
        candidates.append(profile)

    db.commit()

    # Run every candidate through the REAL Competency Engine — same
    # function the live app calls after any profile update — so
    # evidence_score, badges, and profile_completeness are computed
    # identically to how they would be for a genuine user, not by a
    # separate seed-only scoring path.
    for profile in candidates:
        recompute_competency_profile(profile)
    db.commit()

    print(f"Created {len(candidates)} candidates.")
    return candidates


def create_recruiters_and_jobs(db, n_recruiters=5):
    jobs = []
    for i in range(n_recruiters):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        email = f"recruiter.{first.lower()}{i}@example.com"

        user = User(
            email=email,
            full_name=f"{first} {last}",
            hashed_password=hash_password("password123"),
            role=UserRole.recruiter,
            consent_given=True,
            consent_at=datetime.utcnow(),
        )
        db.add(user)
        db.flush()

        company = Company(
            recruiter_id=user.id,
            name=COMPANY_NAMES[i % len(COMPANY_NAMES)],
            industry=random.choice(["Fintech", "E-commerce", "Healthtech", "Edtech"]),
        )
        db.add(company)
        db.flush()

        # Each recruiter posts 2 jobs, split across modes so both
        # Standard and BDIOF get a meaningful sample size.
        for j in range(2):
            mode = ScreeningMode.bdiof if (i + j) % 2 == 0 else ScreeningMode.standard
            job = Job(
                recruiter_id=user.id,
                company_id=company.id,
                title=random.choice(JOB_TITLES),
                description="We're looking for a skilled engineer to join our growing team, working on "
                             "real production systems from day one.",
                required_skills=random.sample(ALL_SKILLS, k=random.randint(3, 6)),
                location=random.choice(["Remote", "Lagos, Nigeria", "Remote (Africa-based)"]),
                screening_mode=mode,
            )
            db.add(job)
            db.flush()
            jobs.append(job)

    db.commit()
    print(f"Created {n_recruiters} recruiters/companies and {len(jobs)} jobs.")
    return jobs


def simulate_applications(db, candidates, jobs):
    """
    Each candidate applies to 2-4 random jobs. Evidence Score at
    application time is computed via the REAL
    compute_job_specific_evidence_score() function — identical to what
    happens when a real candidate clicks "Apply".

    Shortlisting simulation (see module docstring for the full
    rationale): both modes use the SAME 0.5 evidence-score threshold.
    Standard-mode decisions additionally get symmetric, mean-zero
    random noise (representing unspecified subjective factors that
    enter once identity is visible), BDIOF decisions do not. This is
    the only asymmetry between modes — deliberately not enough to
    guarantee any particular Visibility Gap outcome.
    """
    applications = []
    for profile in candidates:
        chosen_jobs = random.sample(jobs, k=min(random.randint(2, 4), len(jobs)))
        for job in chosen_jobs:
            score_breakdown = compute_job_specific_evidence_score(profile, job)
            evidence_score = score_breakdown["evidence_score"]

            if job.screening_mode == ScreeningMode.standard:
                decision_score = evidence_score + random.gauss(0, 0.15)
            else:
                decision_score = evidence_score
            would_shortlist = decision_score > 0.5

            application = Application(
                candidate_id=profile.id,
                job_id=job.id,
                screening_mode_at_application=job.screening_mode,
                evidence_score_at_application=evidence_score,
                applied_at=datetime.utcnow() - timedelta(days=random.randint(0, 45)),
            )

            if would_shortlist:
                roll = random.random()
                if roll < 0.4:
                    application.status = ApplicationStatus.shortlisted
                elif roll < 0.75:
                    application.status = ApplicationStatus.interview
                else:
                    application.status = ApplicationStatus.offered
            else:
                application.status = random.choice(
                    [ApplicationStatus.applied, ApplicationStatus.viewed, ApplicationStatus.rejected]
                )

            was_anon = job.screening_mode != ScreeningMode.standard
            application.was_anonymized_when_selected = was_anon if application.status != ApplicationStatus.applied else None

            db.add(application)
            db.flush()
            applications.append((application, job, profile))

    db.commit()

    BDIOF_REVEAL = {ApplicationStatus.interview, ApplicationStatus.offered}
    HYBRID_REVEAL = {ApplicationStatus.shortlisted, ApplicationStatus.interview, ApplicationStatus.offered}

    for application, job, profile in applications:
        was_anon = job.screening_mode != ScreeningMode.standard
        log_action(
            db, recruiter_id=job.recruiter_id, candidate_id=profile.id, job_id=job.id,
            action="viewed", was_anonymized=was_anon, screening_mode=job.screening_mode,
        )
        should_reveal = (
            (job.screening_mode == ScreeningMode.bdiof and application.status in BDIOF_REVEAL) or
            (job.screening_mode == ScreeningMode.hybrid and application.status in HYBRID_REVEAL)
        )
        if should_reveal:
            log_action(
                db, recruiter_id=job.recruiter_id, candidate_id=profile.id, job_id=job.id,
                action="revealed", was_anonymized=True, screening_mode=job.screening_mode,
            )

    print(f"Created {len(applications)} applications with simulated shortlisting decisions.")


def main():
    db = SessionLocal()
    try:
        print("=== EquityEngine Seed Data ===\n")
        candidates = create_candidates(db, n=20)
        jobs = create_recruiters_and_jobs(db, n_recruiters=5)
        simulate_applications(db, candidates, jobs)

        print("\n=== Login credentials (all use password: password123) ===")
        print("\nRecruiters:")
        recruiter_emails = (
            db.query(User.email).filter(User.role == UserRole.recruiter).order_by(User.email).all()
        )
        for (email,) in recruiter_emails:
            print(f"  {email}")

        print("\nCandidates:")
        candidate_emails = (
            db.query(User.email).filter(User.role == UserRole.candidate).order_by(User.email).all()
        )
        for (email,) in candidate_emails:
            print(f"  {email}")

        print("\nReminder: this is simulated demonstration data, not a substitute for real")
        print("usage. See this file's module docstring before citing any resulting")
        print("Visibility Gap number as a Chapter 4 finding.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
