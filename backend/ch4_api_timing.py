"""
Chapter 4 — API response-time measurement (read-only).

Exercises the deployed FastAPI application in-process through Starlette's
TestClient, so every request traverses the real stack: routing, JWT
verification, the role dependency, the service layer, response-model
validation and JSON serialisation. Network transit is excluded, which is
stated in the report alongside the figures.

Only GET endpoints are exercised. Nothing here mutates the database.

Run from backend/ with the venv active:
    python ch4_api_timing.py
"""
from __future__ import annotations

import json
import statistics
import time

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import Application, Job, User, UserRole
from app.security import create_access_token
from main import app

REPEATS = 12


def stats(samples: list[float]) -> dict:
    ordered = sorted(samples)
    return {
        "n": len(samples),
        "mean_ms": round(statistics.fmean(samples), 1),
        "median_ms": round(statistics.median(samples), 1),
        "min_ms": round(min(samples), 1),
        "max_ms": round(max(samples), 1),
        "p95_ms": round(ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))], 1),
    }


db = SessionLocal()
admin = db.query(User).filter(User.role == UserRole.admin).first()
candidate = db.query(User).filter(User.role == UserRole.candidate).first()

# Recruiter owning the job with the most applicants, so the dossier
# figure reflects the heaviest real case in the dataset.
job_counts = sorted(
    ((db.query(Application).filter(Application.job_id == j.id).count(), j)
     for j in db.query(Job).all()),
    key=lambda t: -t[0],
)
biggest_n, biggest_job = job_counts[0]
recruiter = db.query(User).filter(User.id == biggest_job.recruiter_id).first()

bdiof_job = next((j for _, j in job_counts if j.screening_mode.value == "bdiof"), None)
bdiof_recruiter = (
    db.query(User).filter(User.id == bdiof_job.recruiter_id).first() if bdiof_job else None
)

print(f"admin={admin.email if admin else None}")
print(f"recruiter={recruiter.email if recruiter else None}")
print(f"candidate={candidate.email if candidate else None}")
print(f"heaviest job='{biggest_job.title}' ({biggest_job.screening_mode.value}) n={biggest_n}")
db.close()


def hdr(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


ENDPOINTS = [
    ("GET /health",                          "/health",                              None),
    ("GET /admin/stats",                     "/admin/stats",                         admin),
    ("GET /admin/visibility-gap",            "/admin/visibility-gap",                admin),
    ("GET /admin/visibility-gap/timeseries", "/admin/visibility-gap/timeseries",     admin),
    ("GET /admin/diversity-report",          "/admin/diversity-report",              admin),
    ("GET /admin/recruiters/bias-scores",    "/admin/recruiters/bias-scores",        admin),
    ("GET /admin/candidates",                "/admin/candidates",                    admin),
    ("GET /admin/activity-log",              "/admin/activity-log",                  admin),
    ("GET /candidates/jobs",                 "/candidates/jobs",                     candidate),
    ("GET /candidates/me/profile",           "/candidates/me/profile",               candidate),
    ("GET /candidates/me/applications",      "/candidates/me/applications",          candidate),
    ("GET /candidates/me/competency-profile", "/candidates/me/competency-profile",   candidate),
    ("GET /recruiters/jobs",                 "/recruiters/jobs",                     recruiter),
    (f"GET /recruiters/jobs/:id/candidates (n={biggest_n})",
     f"/recruiters/jobs/{biggest_job.id}/candidates",                                recruiter),
    ("GET /recruiters/talent-pool",          "/recruiters/talent-pool",              recruiter),
]

if bdiof_job and bdiof_recruiter:
    n_bdiof = job_counts[[j.id for _, j in job_counts].index(bdiof_job.id)][0]
    ENDPOINTS.append((
        f"GET /recruiters/jobs/:id/candidates [BDIOF] (n={n_bdiof})",
        f"/recruiters/jobs/{bdiof_job.id}/candidates",
        bdiof_recruiter,
    ))

results = {}
unauthorised = {}

with TestClient(app) as client:
    for label, path, user in ENDPOINTS:
        headers = hdr(user) if user else {}
        warm = client.get(path, headers=headers)  # warm caches / model
        if warm.status_code != 200:
            print(f"SKIP {label}: HTTP {warm.status_code} {warm.text[:120]}")
            continue

        samples = []
        for _ in range(REPEATS):
            t0 = time.perf_counter()
            resp = client.get(path, headers=headers)
            samples.append((time.perf_counter() - t0) * 1000.0)
            assert resp.status_code == 200, resp.status_code
        results[label] = {**stats(samples), "bytes": len(warm.content)}
        print(f"{label:58s} {results[label]['median_ms']:8.1f} ms (median)")

    # Access-control probes: role separation and unauthenticated access.
    print("\nAccess-control probes")
    probes = [
        ("admin endpoint, no token",         "/admin/stats",        {}),
        ("admin endpoint, candidate token",  "/admin/stats",        hdr(candidate)),
        ("admin endpoint, recruiter token",  "/admin/stats",        hdr(recruiter)),
        ("recruiter endpoint, candidate token", "/recruiters/jobs", hdr(candidate)),
        ("candidate endpoint, recruiter token", "/candidates/me/profile", hdr(recruiter)),
        ("admin endpoint, malformed token",  "/admin/stats",
         {"Authorization": "Bearer not-a-real-token"}),
    ]
    for label, path, headers in probes:
        resp = client.get(path, headers=headers)
        unauthorised[label] = resp.status_code
        print(f"  {label:42s} -> HTTP {resp.status_code}")

    # Cross-tenant probe: a recruiter requesting another recruiter's job.
    other = next((j for _, j in job_counts if j.recruiter_id != recruiter.id), None)
    if other is not None:
        resp = client.get(f"/recruiters/jobs/{other.id}/candidates", headers=hdr(recruiter))
        unauthorised["recruiter requesting another recruiter's dossier"] = resp.status_code
        print(f"  {'recruiter -> another recruiter dossier':42s} -> HTTP {resp.status_code}")

    # Anonymisation at the HTTP boundary: does the serialised BDIOF
    # dossier response contain any identity field at all?
    if bdiof_job and bdiof_recruiter:
        resp = client.get(
            f"/recruiters/jobs/{bdiof_job.id}/candidates", headers=hdr(bdiof_recruiter)
        )
        payload = resp.json()
        identity_fields = {
            "full_name", "email", "location", "bio", "cv_file_url",
            "github_username", "regional_terms", "user_id",
        }
        non_null = {
            k for row in payload for k, v in row.items()
            if k in identity_fields and v is not None
        }
        print("\nBDIOF dossier over HTTP:")
        print(f"  rows                 : {len(payload)}")
        print(f"  identity fields non-null: {sorted(non_null) or 'none'}")
        print(f"  pseudonyms           : {[r.get('pseudonym') for r in payload][:4]}")
        results["_bdiof_http_check"] = {
            "rows": len(payload),
            "identity_fields_non_null": sorted(non_null),
            "sample_pseudonyms": [r.get("pseudonym") for r in payload][:4],
        }

out = {"endpoints": results, "access_control": unauthorised, "repeats": REPEATS}
with open("ch4_api_results.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("\nWrote ch4_api_results.json")
