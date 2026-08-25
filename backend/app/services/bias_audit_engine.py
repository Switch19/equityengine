"""
Bias Audit Engine — computes the Visibility Gap metric and related
diagnostics from audit_logs and applications data.

IMPORTANT STATISTICAL CAVEAT, read before citing these numbers in
Chapter 4's Results section:

The Visibility Gap here is a BETWEEN-GROUPS comparison (shortlist rate
under BDIOF-mode jobs vs. shortlist rate under Standard-mode jobs), not
a matched-pairs comparison of the same candidates evaluated both ways.
A recruiter chooses which screening mode to use per job, so jobs using
different modes could differ in other ways too (different roles,
different applicant pools, different recruiters with different
baseline standards) — this is confounding, and it means the Visibility
Gap is correlational evidence consistent with the bias-mitigation
hypothesis, not proof that anonymisation alone caused any observed
difference. Say this plainly in Chapter 4/5 rather than overclaiming
causation; a truly controlled comparison would require randomising
screening mode assignment across otherwise-identical job postings,
which is out of scope for this project (see Chapter 1, Scope).

All rate computations also carry a small-sample warning when the
underlying count is low, since a "gap" computed from three
applications is not a meaningful finding.
"""
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from app.models import Application, ApplicationStatus, ScreeningMode, CandidateProfile, Job, User, UserRole

SELECTED_STATUSES = {ApplicationStatus.shortlisted, ApplicationStatus.interview, ApplicationStatus.offered}
MIN_MEANINGFUL_SAMPLE = 10


def _shortlist_rate(total: int, selected: int) -> float | None:
    return round(selected / total, 4) if total > 0 else None


# ---------------------------------------------------------------------
# Core Visibility Gap
# ---------------------------------------------------------------------

def compute_shortlist_rate_by_mode(db: Session) -> dict:
    results = {}
    for mode in ScreeningMode:
        total = db.query(Application).filter(Application.screening_mode_at_application == mode).count()
        selected = (
            db.query(Application)
            .filter(
                Application.screening_mode_at_application == mode,
                Application.status.in_(SELECTED_STATUSES),
            )
            .count()
        )
        results[mode.value] = {
            "total_applications": total,
            "selected_count": selected,
            "shortlist_rate": _shortlist_rate(total, selected),
            "small_sample": 0 < total < MIN_MEANINGFUL_SAMPLE,
        }
    return results


def compute_visibility_gap(db: Session) -> dict:
    rates = compute_shortlist_rate_by_mode(db)
    standard_rate = rates["standard"]["shortlist_rate"]
    bdiof_rate = rates["bdiof"]["shortlist_rate"]

    gap = None
    gap_percent_improvement = None
    if standard_rate is not None and bdiof_rate is not None:
        gap = round(bdiof_rate - standard_rate, 4)
        if standard_rate > 0:
            gap_percent_improvement = round((gap / standard_rate) * 100, 1)

    warnings = [
        f"Sample size for '{mode}' is below {MIN_MEANINGFUL_SAMPLE} applications — "
        "treat this mode's rate as preliminary, not a reliable estimate."
        for mode, data in rates.items()
        if data["small_sample"]
    ]

    return {
        "rates_by_mode": rates,
        "visibility_gap": gap,
        "visibility_gap_percent_improvement": gap_percent_improvement,
        "warnings": warnings,
        "methodology_note": (
            "This is a between-groups comparison across different job postings, not a "
            "matched-pairs comparison of identical candidates evaluated under both modes. "
            "See bias_audit_engine.py module docstring for the full caveat."
        ),
    }


# ---------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------

def compute_visibility_gap_timeseries(db: Session, bucket: str = "week") -> list[dict]:
    """
    Recomputed on demand from raw application data rather than stored
    as periodic snapshots — simpler and always consistent with live
    data, appropriate at this project's scale. A production system
    with a much larger dataset would likely materialise this instead
    of recomputing it per request.
    """
    rows = db.query(
        Application.applied_at, Application.screening_mode_at_application, Application.status
    ).all()

    buckets: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"total": 0, "selected": 0})
    )
    for applied_at, mode, status in rows:
        key = applied_at.strftime("%Y-W%W") if bucket == "week" else applied_at.strftime("%Y-%m")
        buckets[key][mode.value]["total"] += 1
        if status in SELECTED_STATUSES:
            buckets[key][mode.value]["selected"] += 1

    timeseries = []
    for period in sorted(buckets.keys()):
        period_data = buckets[period]
        standard = period_data.get("standard", {"total": 0, "selected": 0})
        bdiof = period_data.get("bdiof", {"total": 0, "selected": 0})
        standard_rate = _shortlist_rate(standard["total"], standard["selected"])
        bdiof_rate = _shortlist_rate(bdiof["total"], bdiof["selected"])
        gap = (
            round(bdiof_rate - standard_rate, 4)
            if standard_rate is not None and bdiof_rate is not None
            else None
        )
        timeseries.append({
            "period": period,
            "standard_shortlist_rate": standard_rate,
            "bdiof_shortlist_rate": bdiof_rate,
            "visibility_gap": gap,
            "standard_sample_size": standard["total"],
            "bdiof_sample_size": bdiof["total"],
        })
    return timeseries


# ---------------------------------------------------------------------
# Diversity report
# ---------------------------------------------------------------------

def compute_diversity_report(db: Session) -> dict:
    all_tiers = [
        row[0] for row in
        db.query(CandidateProfile.education_tier).filter(CandidateProfile.education_tier.isnot(None)).all()
    ]
    total_candidates = len(all_tiers)
    all_distribution = (
        {tier: round(count / total_candidates * 100, 1) for tier, count in Counter(all_tiers).items()}
        if total_candidates else {}
    )

    shortlisted_candidate_ids = [
        row[0] for row in
        db.query(Application.candidate_id).filter(Application.status.in_(SELECTED_STATUSES)).distinct().all()
    ]
    shortlisted_tiers = [
        row[0] for row in
        db.query(CandidateProfile.education_tier)
        .filter(CandidateProfile.id.in_(shortlisted_candidate_ids), CandidateProfile.education_tier.isnot(None))
        .all()
    ] if shortlisted_candidate_ids else []
    total_shortlisted = len(shortlisted_tiers)
    shortlisted_distribution = (
        {tier: round(count / total_shortlisted * 100, 1) for tier, count in Counter(shortlisted_tiers).items()}
        if total_shortlisted else {}
    )

    return {
        "all_candidates_distribution": all_distribution,
        "shortlisted_candidates_distribution": shortlisted_distribution,
        "total_candidates": total_candidates,
        "total_shortlisted": total_shortlisted,
        "small_sample": total_shortlisted < MIN_MEANINGFUL_SAMPLE,
    }


# ---------------------------------------------------------------------
# Recruiter bias scores (admin-only — never exposed to the recruiter
# themselves, per the original design requirement)
# ---------------------------------------------------------------------

def compute_recruiter_bias_scores(db: Session) -> list[dict]:
    """
    A hand-calibrated composite score, 0-100 (higher = more concerning
    skew), NOT a statistically validated instrument — same limitation
    as the Evidence Score's component weights, and worth disclosing
    identically in Chapter 5. It combines two signals: (1) the gap
    between a recruiter's own shortlist rate when selection happened
    anonymously vs. with identity visible (a large gap suggests
    identity access changes their decisions), and (2) how far the
    education-tier mix of their shortlisted candidates deviates from
    the education-tier mix of everyone who applied to their jobs.
    """
    recruiters = db.query(User).filter(User.role == UserRole.recruiter).all()
    results = []

    for recruiter in recruiters:
        job_ids = [row[0] for row in db.query(Job.id).filter(Job.recruiter_id == recruiter.id).all()]
        if not job_ids:
            continue

        applications = db.query(Application).filter(Application.job_id.in_(job_ids)).all()
        if not applications:
            continue

        anon_apps = [a for a in applications if a.was_anonymized_when_selected is True]
        visible_apps = [a for a in applications if a.was_anonymized_when_selected is False]

        anon_rate = _shortlist_rate(len(anon_apps), sum(1 for a in anon_apps if a.status in SELECTED_STATUSES))
        visible_rate = _shortlist_rate(
            len(visible_apps), sum(1 for a in visible_apps if a.status in SELECTED_STATUSES)
        )

        internal_gap = (
            round(visible_rate - anon_rate, 4) if anon_rate is not None and visible_rate is not None else None
        )

        applicant_ids = [a.candidate_id for a in applications]
        applicant_tiers = [
            row[0] for row in
            db.query(CandidateProfile.education_tier)
            .filter(CandidateProfile.id.in_(applicant_ids), CandidateProfile.education_tier.isnot(None))
            .all()
        ]
        applicant_graduate_share = (
            applicant_tiers.count("Graduate") / len(applicant_tiers) if applicant_tiers else None
        )

        shortlisted_ids = [a.candidate_id for a in applications if a.status in SELECTED_STATUSES]
        shortlisted_tiers = [
            row[0] for row in
            db.query(CandidateProfile.education_tier)
            .filter(CandidateProfile.id.in_(shortlisted_ids), CandidateProfile.education_tier.isnot(None))
            .all()
        ] if shortlisted_ids else []
        shortlisted_graduate_share = (
            shortlisted_tiers.count("Graduate") / len(shortlisted_tiers) if shortlisted_tiers else None
        )

        score_components = []
        if internal_gap is not None:
            score_components.append(min(abs(internal_gap) * 200, 60))
        if applicant_graduate_share is not None and shortlisted_graduate_share is not None:
            skew = abs(shortlisted_graduate_share - applicant_graduate_share)
            score_components.append(min(skew * 100, 40))

        bias_score = round(sum(score_components), 1) if score_components else None

        results.append({
            "recruiter_id": str(recruiter.id),
            "recruiter_name": recruiter.full_name,
            "total_applications_received": len(applications),
            "anonymized_shortlist_rate": anon_rate,
            "identity_visible_shortlist_rate": visible_rate,
            "internal_visibility_gap": internal_gap,
            "applicant_pool_graduate_share": (
                round(applicant_graduate_share, 3) if applicant_graduate_share is not None else None
            ),
            "shortlisted_graduate_share": (
                round(shortlisted_graduate_share, 3) if shortlisted_graduate_share is not None else None
            ),
            "bias_score": bias_score,
            "small_sample": len(applications) < MIN_MEANINGFUL_SAMPLE,
        })

    return sorted(results, key=lambda r: (r["bias_score"] is None, -(r["bias_score"] or 0)))


# ---------------------------------------------------------------------
# Platform-wide statistics
# ---------------------------------------------------------------------

def compute_platform_stats(db: Session) -> dict:
    from app.models import Company

    return {
        "total_candidates": db.query(User).filter(User.role == UserRole.candidate).count(),
        "total_recruiters": db.query(User).filter(User.role == UserRole.recruiter).count(),
        "total_companies": db.query(Company).count(),
        "total_jobs": db.query(Job).count(),
        "active_jobs": db.query(Job).filter(Job.is_active == True).count(),  # noqa: E712
        "total_applications": db.query(Application).count(),
        "total_shortlisted": db.query(Application).filter(Application.status.in_(SELECTED_STATUSES)).count(),
        "jobs_by_screening_mode": {
            mode.value: db.query(Job).filter(Job.screening_mode == mode).count() for mode in ScreeningMode
        },
    }
