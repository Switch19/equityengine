"""
Chapter 4 — dossier scaling probe (read-only).

Section 4.5 reports that the Competency Dossier endpoint is the slowest
path in the system. This script establishes WHY, and what the ceiling is,
by timing dossier construction as the applicant count grows.

Two paths are compared over the same profiles and the same job:

  current : one compute_job_specific_evidence_score() call per applicant,
            which is what routers/recruiters.py does today. Each call
            re-encodes the job's reference texts.
  batched : one best_match_similarity_batch() call for all applicants,
            encoding the job's reference texts once — the routine already
            used by feedback_service.py.

Applicant pools larger than the live dataset are produced by cycling the
real candidate profiles in memory. Nothing is written to the database;
this is a latency probe, not a data generator.

Run from backend/ with the venv active:
    python ch4_scaling.py
"""
from __future__ import annotations

import json
import statistics
import time

from app.database import SessionLocal
from app.models import Application, CandidateProfile, Job
from app.services.competency_engine import (
    build_competency_profile, compute_evidence_score, compute_job_specific_evidence_score,
)
from app.services.embedding_service import best_match_similarity_batch, get_embedding_model

REPEATS = 3
SIZES = [8, 25, 50, 100]


def median_ms(fn, repeats: int = REPEATS) -> float:
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return round(statistics.median(samples), 1)


db = SessionLocal()
try:
    get_embedding_model()  # pay the load once, outside every measurement

    job = sorted(
        db.query(Job).all(),
        key=lambda j: -db.query(Application).filter(Application.job_id == j.id).count(),
    )[0]
    real_profiles = db.query(CandidateProfile).all()
    print(f"job='{job.title}' mode={job.screening_mode.value} "
          f"required_skills={len(job.required_skills or [])} profiles={len(real_profiles)}")

    reference_texts = list(job.required_skills or [])
    if job.description:
        reference_texts.append(job.description)

    def project_texts(profile: CandidateProfile) -> list[str]:
        return [p.get("description", "") for p in (profile.cv_projects or [])] + [
            r.get("description", "") for r in (profile.github_repos or []) if r.get("description")
        ]

    def pool(n: int) -> list[CandidateProfile]:
        return [real_profiles[i % len(real_profiles)] for i in range(n)]

    def current_path(profiles):
        views = []
        for p in profiles:
            views.append({
                "score": compute_job_specific_evidence_score(p, job),
                "skills": build_competency_profile(p),
            })
        return sorted(views, key=lambda v: v["score"]["evidence_score"], reverse=True)

    def batched_path(profiles):
        p_embs = best_match_similarity_batch(
            [project_texts(p) for p in profiles], reference_texts
        )
        views = []
        for p, p_emb in zip(profiles, p_embs):
            views.append({
                "score": {
                    "p_emb": round(p_emb, 3),
                    "evidence_score": compute_evidence_score(
                        round(p_emb, 3), p.g_act_score or 0.0,
                        p.c_peer_score or 0.0, p.l_traj_score or 0.0,
                    ),
                },
                "skills": build_competency_profile(p),
            })
        return sorted(views, key=lambda v: v["score"]["evidence_score"], reverse=True)

    # Equivalence check before timing anything: the batched path must
    # produce the same scores as the current one, or the comparison is
    # meaningless.
    sample = pool(8)
    cur = [round(v["score"]["evidence_score"], 6) for v in current_path(sample)]
    bat = [round(v["score"]["evidence_score"], 6) for v in batched_path(sample)]
    print(f"equivalence over n=8: identical={cur == bat}")

    rows = []
    for n in SIZES:
        profiles = pool(n)
        cur_ms = median_ms(lambda: current_path(profiles))
        bat_ms = median_ms(lambda: batched_path(profiles))
        rows.append({
            "applicants": n,
            "current_ms": cur_ms,
            "batched_ms": bat_ms,
            "current_per_applicant_ms": round(cur_ms / n, 1),
            "batched_per_applicant_ms": round(bat_ms / n, 1),
            "speedup": round(cur_ms / bat_ms, 2),
            "current_meets_nfr1_3s": cur_ms <= 3000,
            "batched_meets_nfr1_3s": bat_ms <= 3000,
        })
        print(json.dumps(rows[-1]))

    # Linear projection to the NFR1 target of 500 applicants, fitted on
    # the marginal cost between the two largest measured pools.
    a, b = rows[-2], rows[-1]
    for key, label in (("current_ms", "current"), ("batched_ms", "batched")):
        slope = (b[key] - a[key]) / (b["applicants"] - a["applicants"])
        intercept = b[key] - slope * b["applicants"]
        projected = slope * 500 + intercept
        print(f"projected {label} at n=500: {projected / 1000:.1f} s "
              f"(marginal {slope:.1f} ms/applicant)")
        rows.append({
            "projection": label,
            "marginal_ms_per_applicant": round(slope, 1),
            "projected_500_ms": round(projected, 0),
            "projected_500_s": round(projected / 1000, 1),
            "meets_nfr1_3s": projected <= 3000,
        })

    with open("ch4_scaling_results.json", "w", encoding="utf-8") as fh:
        json.dump({"job": job.title, "rows": rows}, fh, indent=2)
    print("\nWrote ch4_scaling_results.json")
finally:
    db.rollback()
    db.close()
