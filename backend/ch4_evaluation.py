"""
Chapter 4 evaluation harness — read-only.

Runs the measurements reported in Chapter Four Sections 4.4 and 4.5
against the live development database and the deployed build, so that
every figure quoted in the report is measured rather than asserted.

Nothing here writes to the database. The single session opened below is
rolled back and closed on exit.

Run from backend/ with the venv active:
    python ch4_evaluation.py
"""
from __future__ import annotations

import json
import statistics
import time
import uuid as uuid_lib
from collections import Counter

from sqlalchemy import text

from app.database import SessionLocal, engine
from app.models import (
    Application, ApplicationStatus, AuditLog, CandidateProfile, Company, Job,
    ScreeningMode, User, UserRole,
)
from app.services import bias_audit_engine as bae
from app.services.competency_engine import (
    BADGE_TIERS, EVIDENCE_WEIGHTS, build_competency_profile,
    compute_evidence_score, compute_job_specific_evidence_score,
)
from app.services.dossier_service import (
    build_anonymized_candidate_view, build_revealed_candidate_view,
    generate_pseudonym, rank_applications_by_evidence_score,
)
from app.services.embedding_service import (
    best_match_similarity, best_match_similarity_batch, encode_texts,
    get_embedding_model,
)
from app.services.feedback_service import MIN_MEANINGFUL_GAP, generate_rejection_feedback

RESULTS: dict = {}


def section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def timed(fn, repeats: int = 1):
    """Returns (result, list_of_elapsed_ms)."""
    samples = []
    out = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        out = fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return out, samples


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

try:
    # -----------------------------------------------------------------
    # 0. Environment
    # -----------------------------------------------------------------
    section("0. ENVIRONMENT")
    with engine.connect() as conn:
        pg_version = conn.execute(text("select version()")).scalar()
    print("PostgreSQL:", pg_version.split(",")[0])
    RESULTS["postgres"] = pg_version.split(",")[0]

    _, load_samples = timed(get_embedding_model, repeats=1)
    print(f"Embedding model cold load: {load_samples[0]:.0f} ms")
    RESULTS["model_cold_load_ms"] = round(load_samples[0], 0)

    # -----------------------------------------------------------------
    # 1. Dataset snapshot (cross-checks the admin screenshots)
    # -----------------------------------------------------------------
    section("1. DATASET SNAPSHOT")
    platform = bae.compute_platform_stats(db)
    print(json.dumps(platform, indent=2))
    RESULTS["platform_stats"] = platform

    tiers = Counter(
        row[0] for row in db.query(CandidateProfile.education_tier).all() if row[0]
    )
    print("Education tiers:", dict(tiers))
    RESULTS["education_tiers"] = dict(tiers)

    status_mix = Counter(row[0].value for row in db.query(Application.status).all())
    print("Application statuses:", dict(status_mix))
    RESULTS["status_mix"] = dict(status_mix)

    audit_actions = Counter(row[0] for row in db.query(AuditLog.action).all())
    print("Audit actions:", dict(audit_actions))
    RESULTS["audit_actions"] = dict(audit_actions)

    # -----------------------------------------------------------------
    # 2. UNIT-LEVEL PROPERTY CHECKS
    # -----------------------------------------------------------------
    section("2. UNIT-LEVEL PROPERTY CHECKS")
    unit = {}

    # T-U1  Evidence Score weights sum to unity => bounded in [0,1]
    weight_sum = round(sum(EVIDENCE_WEIGHTS.values()), 10)
    unit["weights_sum_to_one"] = (weight_sum == 1.0, weight_sum)

    # T-U2  Boundary values
    unit["score_all_zero"] = compute_evidence_score(0, 0, 0, 0)
    unit["score_all_one"] = compute_evidence_score(1, 1, 1, 1)

    # T-U3  Monotonicity + bounds over a random sweep
    import random
    random.seed(4)
    out_of_range = 0
    non_monotonic = 0
    for _ in range(10000):
        a, b, c, d = (random.random() for _ in range(4))
        s = compute_evidence_score(a, b, c, d)
        if not (0.0 <= s <= 1.0):
            out_of_range += 1
        bumped = compute_evidence_score(min(a + 0.01, 1.0), b, c, d)
        if bumped < s - 1e-9:
            non_monotonic += 1
    unit["sweep_out_of_range"] = out_of_range
    unit["sweep_non_monotonic"] = non_monotonic

    # T-U4  Badge tier is a pure function of corroborating-source count
    unit["badge_tiers"] = BADGE_TIERS

    # T-U5  Word-boundary guard on community skill matching.
    # A naive substring test would match the language "R" inside
    # ordinary words; confirm the shipped logic does not.
    class _Stub:
        cv_skills = []
        github_activity = None
        github_languages = None
        certifications = [{"name": "Software Engineering Professional", "issuer": "Coursera"}]
        peer_endorsements = []

    stub_profile = _Stub()
    stub_skills = build_competency_profile(stub_profile)
    unit["r_false_positive_present"] = "R" in stub_skills
    unit["stub_matched_skills"] = sorted(stub_skills.keys())

    # T-U6  Pseudonym determinism and uniqueness across the live cohort
    profile_ids = [row[0] for row in db.query(CandidateProfile.id).all()]
    pseudonyms = [generate_pseudonym(pid) for pid in profile_ids]
    repeat = [generate_pseudonym(pid) for pid in profile_ids]
    unit["pseudonym_stable"] = pseudonyms == repeat
    unit["pseudonym_unique"] = len(set(pseudonyms)) == len(pseudonyms)
    unit["pseudonym_count"] = len(pseudonyms)
    unit["pseudonym_sample"] = pseudonyms[:3]

    # T-U7  Median vs mean on a small skewed comparison group
    skewed = [0.30, 0.32, 0.95]
    unit["median_vs_mean"] = {
        "group": skewed,
        "median": statistics.median(skewed),
        "mean": round(statistics.fmean(skewed), 4),
    }

    # T-U8  Empty-input handling in the similarity function
    unit["similarity_empty_candidate"] = best_match_similarity([], ["Python"])
    unit["similarity_empty_reference"] = best_match_similarity(["Built an API"], [])
    unit["similarity_blank_strings"] = best_match_similarity(["   "], ["  "])

    # T-U9  Unit-normalised embeddings => cosine reduces to dot product
    import numpy as np
    vecs = encode_texts(["Built a REST API for order management", "Backend Development"])
    norms = [float(np.linalg.norm(v)) for v in vecs]
    unit["embedding_norms"] = [round(n, 6) for n in norms]
    unit["embedding_dim"] = int(vecs.shape[1])

    # T-U10 Semantic (not lexical) matching: no shared tokens, still similar
    lexical_overlap = set("built a rest api for order management".split()) & set(
        "backend development".split()
    )
    unit["semantic_pair_shared_tokens"] = sorted(lexical_overlap)
    unit["semantic_pair_similarity"] = round(float(np.dot(vecs[0], vecs[1])), 4)

    for k, v in unit.items():
        print(f"  {k}: {v}")
    RESULTS["unit"] = unit

    # -----------------------------------------------------------------
    # 3. ANONYMISATION INTEGRITY (every application in the database)
    # -----------------------------------------------------------------
    section("3. ANONYMISATION INTEGRITY SWEEP")

    IDENTITY_KEYS = {
        "full_name", "email", "location", "bio", "cv_file_url",
        "github_username", "regional_terms", "user_id",
    }

    applications = db.query(Application).all()
    leak_key_hits = 0
    leak_value_hits = 0
    checked = 0
    token_checks = 0
    per_field_hits: Counter = Counter()

    for app_row in applications:
        profile = app_row.candidate
        job = app_row.job
        if profile is None or job is None:
            continue
        user = profile.user
        view = build_anonymized_candidate_view(profile, job, app_row)
        checked += 1

        # (a) structural: no identity-bearing KEY may exist in the view
        present = IDENTITY_KEYS & set(view.keys())
        if present:
            leak_key_hits += 1
            per_field_hits.update(present)

        # (b) content: no identity VALUE may appear anywhere in the
        #     serialised view, matched token-wise against the real data
        blob = json.dumps(view, default=str).lower()
        tokens = []
        if user and user.full_name:
            tokens += [t for t in user.full_name.split() if len(t) > 2]
        if user and user.email:
            tokens.append(user.email)
            tokens.append(user.email.split("@")[0])
        if profile.location:
            tokens += [t for t in profile.location.replace(",", " ").split() if len(t) > 2]
        if profile.github_username:
            tokens.append(profile.github_username)
        if profile.cv_file_url:
            tokens.append(str(profile.cv_file_url))
        for term in (profile.regional_terms or []):
            if isinstance(term, str) and len(term) > 3:
                tokens.append(term)
        for token in tokens:
            token_checks += 1
            if token and token.lower() in blob:
                leak_value_hits += 1
                per_field_hits[f"value:{token[:20]}"] += 1

    anon = {
        "applications_checked": checked,
        "identity_key_leaks": leak_key_hits,
        "identity_token_comparisons": token_checks,
        "identity_value_leaks": leak_value_hits,
        "per_field_hits": dict(per_field_hits),
        "effectiveness_rate_percent": round(
            100.0 * (checked - leak_key_hits) / checked, 2
        ) if checked else None,
    }
    print(json.dumps(anon, indent=2))
    RESULTS["anonymisation"] = anon

    # Positive control: the revealed view MUST carry identity, otherwise
    # the sweep above would pass trivially on an empty projection.
    sample_app = next(
        (a for a in applications if a.candidate and a.job and a.candidate.user), None
    )
    if sample_app:
        rv = build_revealed_candidate_view(
            sample_app.candidate, sample_app.candidate.user, sample_app.job, sample_app
        )
        av = build_anonymized_candidate_view(
            sample_app.candidate, sample_app.job, sample_app
        )
        control = {
            "revealed_has_identity_keys": sorted(IDENTITY_KEYS & set(rv.keys())),
            "anonymised_field_count": len(av),
            "revealed_field_count": len(rv),
            "anonymised_keys": sorted(av.keys()),
            "same_evidence_score": (
                rv["evidence_score_breakdown"]["evidence_score"]
                == av["evidence_score_breakdown"]["evidence_score"]
            ),
        }
        print(json.dumps(control, indent=2))
        RESULTS["anonymisation_control"] = control

    # -----------------------------------------------------------------
    # 4. RANKING INVARIANCE ACROSS SCREENING MODES
    # -----------------------------------------------------------------
    section("4. RANKING INVARIANCE ACROSS SCREENING MODES")
    invariance = []
    for job in db.query(Job).all():
        apps = db.query(Application).filter(Application.job_id == job.id).all()
        apps = [a for a in apps if a.candidate]
        if len(apps) < 2:
            continue
        anon_rank = [
            v["application_id"]
            for v in rank_applications_by_evidence_score(
                [build_anonymized_candidate_view(a.candidate, job, a) for a in apps]
            )
        ]
        rev_rank = [
            v["application_id"]
            for v in rank_applications_by_evidence_score(
                [
                    build_revealed_candidate_view(a.candidate, a.candidate.user, job, a)
                    for a in apps
                ]
            )
        ]
        invariance.append({
            "job": job.title,
            "mode": job.screening_mode.value,
            "n": len(apps),
            "identical_order": anon_rank == rev_rank,
        })
    identical = sum(1 for r in invariance if r["identical_order"])
    print(f"Jobs compared: {len(invariance)}; identical ordering: {identical}")
    for r in invariance:
        print("  ", r)
    RESULTS["ranking_invariance"] = {
        "jobs_compared": len(invariance),
        "identical": identical,
        "detail": invariance,
    }

    # -----------------------------------------------------------------
    # 5. EVIDENCE SCORE LATENCY
    # -----------------------------------------------------------------
    section("5. EVIDENCE SCORE LATENCY")
    scoring_job = (
        db.query(Job).filter(Job.required_skills.isnot(None)).first()
        or db.query(Job).first()
    )
    profiles = db.query(CandidateProfile).all()

    # warm the model / caches
    compute_job_specific_evidence_score(profiles[0], scoring_job)

    single_samples = []
    for profile in profiles:
        _, s = timed(lambda p=profile: compute_job_specific_evidence_score(p, scoring_job))
        single_samples.extend(s)
    single_stats = stats(single_samples)
    print("Single job-specific Evidence Score:", single_stats)
    RESULTS["evidence_score_single_ms"] = single_stats

    # Full dossier construction for the largest job in the dataset
    job_sizes = [
        (db.query(Application).filter(Application.job_id == j.id).count(), j)
        for j in db.query(Job).all()
    ]
    job_sizes.sort(key=lambda t: -t[0])
    biggest_n, biggest_job = job_sizes[0]

    def build_full_dossier():
        apps = db.query(Application).filter(Application.job_id == biggest_job.id).all()
        views = [
            build_anonymized_candidate_view(a.candidate, biggest_job, a)
            for a in apps if a.candidate
        ]
        return rank_applications_by_evidence_score(views)

    build_full_dossier()  # warm
    _, dossier_samples = timed(build_full_dossier, repeats=5)
    dossier_stats = stats(dossier_samples)
    print(f"Dossier build ({biggest_job.title}, n={biggest_n}):", dossier_stats)
    RESULTS["dossier_build_ms"] = {
        "job": biggest_job.title, "applicants": biggest_n, **dossier_stats
    }

    # -----------------------------------------------------------------
    # 6. BATCH-ENCODING EFFICIENCY (evidence for NFR1)
    # -----------------------------------------------------------------
    section("6. BATCH VS PER-CANDIDATE ENCODING")
    ref_texts = list(scoring_job.required_skills or []) + [scoring_job.description or ""]
    groups = [
        [p.get("description", "") for p in (pr.cv_projects or [])]
        + [r.get("description", "") for r in (pr.github_repos or []) if r.get("description")]
        for pr in profiles
    ]
    groups = [g for g in groups if g]

    _, naive = timed(
        lambda: [best_match_similarity(g, ref_texts) for g in groups], repeats=3
    )
    _, batched = timed(
        lambda: best_match_similarity_batch(groups, ref_texts), repeats=3
    )
    naive_stats, batch_stats = stats(naive), stats(batched)
    speedup = round(naive_stats["median_ms"] / batch_stats["median_ms"], 2)
    print(f"groups={len(groups)} refs={len(ref_texts)}")
    print("  per-candidate:", naive_stats)
    print("  batched:      ", batch_stats)
    print("  speed-up:     ", speedup, "x")
    RESULTS["batch_encoding"] = {
        "groups": len(groups), "reference_texts": len(ref_texts),
        "per_candidate": naive_stats, "batched": batch_stats, "speedup": speedup,
    }

    # -----------------------------------------------------------------
    # 7. FEEDBACK LOOP BEHAVIOUR
    # -----------------------------------------------------------------
    section("7. CANDIDATE-DIRECTED FEEDBACK LOOP")
    rejected = (
        db.query(Application)
        .filter(Application.status == ApplicationStatus.rejected)
        .all()
    )
    fb_rows = []
    fb_samples = []
    all_names = [
        u.full_name for u in db.query(User).filter(User.role == UserRole.candidate).all()
        if u.full_name
    ]

    for app_row in rejected:
        if not app_row.candidate or not app_row.job:
            continue
        out, s = timed(lambda a=app_row: generate_rejection_feedback(db, a, a.job))
        fb_samples.extend(s)
        text_blob = f"{out['primary_reason']} {out['growth_tip']}"
        # No other candidate may be named anywhere in the generated text.
        owner = app_row.candidate.user.full_name if app_row.candidate.user else ""
        others = [
            n for n in all_names
            if n != owner and any(
                part.lower() in text_blob.lower() for part in n.split() if len(part) > 2
            )
        ]
        case = (
            "competitive_pool" if "competitive" in out["primary_reason"].lower()
            else "no_comparison_group" if "no comparison group" in out["primary_reason"].lower()
            else "diagnosed_deficit"
        )
        fb_rows.append({
            "job": app_row.job.title,
            "case": case,
            "names_other_candidates": others,
            "reason": out["primary_reason"][:110],
        })

    case_mix = Counter(r["case"] for r in fb_rows)
    leaks = [r for r in fb_rows if r["names_other_candidates"]]
    print(f"Rejected applications diagnosed: {len(fb_rows)}")
    print("Case mix:", dict(case_mix))
    print("Rows naming another candidate:", len(leaks))
    if fb_samples:
        print("Latency:", stats(fb_samples))
    for r in fb_rows:
        print(f"  [{r['case']}] {r['job']}: {r['reason']}")
    RESULTS["feedback"] = {
        "diagnosed": len(fb_rows),
        "case_mix": dict(case_mix),
        "cross_candidate_leaks": len(leaks),
        "latency_ms": stats(fb_samples) if fb_samples else None,
        "rows": fb_rows,
        "min_meaningful_gap": MIN_MEANINGFUL_GAP,
    }

    # Persistence check: rejected rows carry stored feedback; non-rejected
    # rows must not.
    stored_on_rejected = sum(
        1 for a in rejected if a.primary_reason and a.growth_tip
    )
    stale_on_active = db.query(Application).filter(
        Application.status != ApplicationStatus.rejected,
        Application.primary_reason.isnot(None),
    ).count()
    print(f"Rejected rows with stored diagnosis: {stored_on_rejected}/{len(rejected)}")
    print(f"Non-rejected rows carrying stale diagnosis: {stale_on_active}")
    RESULTS["feedback_persistence"] = {
        "rejected_total": len(rejected),
        "rejected_with_stored": stored_on_rejected,
        "stale_on_non_rejected": stale_on_active,
    }

    # -----------------------------------------------------------------
    # 8. BIAS AUDIT ENGINE OUTPUTS
    # -----------------------------------------------------------------
    section("8. BIAS AUDIT ENGINE")
    vg, vg_samples = timed(lambda: bae.compute_visibility_gap(db), repeats=5)
    print(json.dumps(vg, indent=2))
    print("Latency:", stats(vg_samples))
    RESULTS["visibility_gap"] = vg
    RESULTS["visibility_gap_latency_ms"] = stats(vg_samples)

    ts, ts_samples = timed(lambda: bae.compute_visibility_gap_timeseries(db), repeats=5)
    print(json.dumps(ts, indent=2))
    RESULTS["timeseries"] = ts
    RESULTS["timeseries_latency_ms"] = stats(ts_samples)

    div, div_samples = timed(lambda: bae.compute_diversity_report(db), repeats=5)
    print(json.dumps(div, indent=2))
    RESULTS["diversity"] = div
    RESULTS["diversity_latency_ms"] = stats(div_samples)

    bias, bias_samples = timed(lambda: bae.compute_recruiter_bias_scores(db), repeats=5)
    print(json.dumps(bias, indent=2))
    RESULTS["recruiter_bias"] = bias
    RESULTS["recruiter_bias_latency_ms"] = stats(bias_samples)

finally:
    db.rollback()
    db.close()

with open("ch4_results.json", "w", encoding="utf-8") as fh:
    json.dump(RESULTS, fh, indent=2, default=str)
print("\nWrote ch4_results.json")
