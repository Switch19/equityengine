"""
Admin-only endpoints: platform statistics, the Bias Audit Engine's
outputs (Visibility Gap, time series, diversity report, recruiter bias
scores), the candidate/recruiter registry and live audit-log feed, and
a downloadable PDF summary.

ACCESS CONTROL — read before adding a route here or elsewhere:

Every route in this router takes Depends(require_role(UserRole.admin)).
That dependency IS the access-control boundary for admin data; there is
no separate middleware layer, so a route that omits it is unguarded
even though it sits in this file. FastAPI resolves the dependency
before the handler body runs, so a non-admin token gets 403 without
the handler ever touching the database.

The candidate roster, recruiter roster, and audit-log feed below expose
real identities and cross-recruiter behaviour, and are reachable ONLY
through this router. Two consequences worth keeping in mind:

  - Do not add a candidate- or recruiter-facing convenience route that
    returns audit rows, even a filtered one. A recruiter able to read
    even their own audit trail can infer the view-limit state and the
    bias metrics the design deliberately withholds from them (see
    get_recruiter_bias_scores below).
  - The feed shows candidate names against actions taken under
    anonymised screening. That is correct for an auditor and wrong for
    anyone else — it is the reason this data is admin-gated rather
    than merely authenticated.
"""
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    VisibilityGapOut, TimeseriesPointOut, DiversityReportOut,
    RecruiterBiasScoreOut, PlatformStatsOut,
    AdminCandidateRowOut, AdminRecruiterRowOut, AdminActivityFeedOut,
)
from app.deps import require_role
from app.services.bias_audit_engine import (
    compute_visibility_gap, compute_visibility_gap_timeseries, compute_diversity_report,
    compute_recruiter_bias_scores, compute_platform_stats,
)
from app.services.admin_registry_service import (
    list_candidates, list_recruiters, list_activity_log, KNOWN_ACTIONS,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=PlatformStatsOut)
def get_platform_stats(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    return compute_platform_stats(db)


@router.get("/visibility-gap", response_model=VisibilityGapOut)
def get_visibility_gap(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    return compute_visibility_gap(db)


@router.get("/visibility-gap/timeseries", response_model=list[TimeseriesPointOut])
def get_visibility_gap_timeseries(
    bucket: str = "week",
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    if bucket not in ("week", "month"):
        bucket = "week"
    return compute_visibility_gap_timeseries(db, bucket=bucket)


@router.get("/diversity-report", response_model=DiversityReportOut)
def get_diversity_report(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    return compute_diversity_report(db)


@router.get("/recruiters/bias-scores", response_model=list[RecruiterBiasScoreOut])
def get_recruiter_bias_scores(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """
    Admin-only by design — see Chapter 1's Definition of Terms and the
    original requirement that recruiters never see their own bias
    score. require_role(UserRole.admin) is what enforces that; there
    is deliberately no equivalent endpoint reachable by a recruiter
    token anywhere in this router or recruiters.py.
    """
    return compute_recruiter_bias_scores(db)


@router.get("/candidates", response_model=list[AdminCandidateRowOut])
def get_candidate_registry(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """
    Full candidate roster for the Admin Dashboard's monitoring view —
    the replacement for inspecting candidate_profiles directly in psql.

    Returns every candidate account, including those that registered
    but never built a profile (those come back with has_profile false
    and zeroed scores rather than being omitted, since signup drop-off
    is one of the things an admin is looking for here).
    """
    return list_candidates(db)


@router.get("/recruiters", response_model=list[AdminRecruiterRowOut])
def get_recruiter_registry(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """
    Full recruiter roster with posting and screening volume.

    Bias scores are NOT included here — they stay on
    /admin/recruiters/bias-scores so that this roster remains cheap
    enough for the dashboard to poll on an interval without kicking
    off a full Bias Audit Engine recomputation each time.
    """
    return list_recruiters(db)


@router.get("/activity-log", response_model=AdminActivityFeedOut)
def get_activity_log(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """
    Newest-first page of the raw audit trail, with recruiter names,
    candidate names, and job titles resolved for display.

    An unrecognised `action` is treated as no filter rather than an
    error: the dashboard polls this endpoint on a timer, and a stale
    filter value in a still-open tab should degrade to showing
    everything instead of turning the live feed into a 422 loop.
    """
    if action not in KNOWN_ACTIONS:
        action = None
    return list_activity_log(db, limit=limit, offset=offset, action=action)


@router.get("/report/pdf")
def download_bias_report_pdf(
    current_user: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    stats = compute_platform_stats(db)
    gap = compute_visibility_gap(db)
    diversity = compute_diversity_report(db)

    pdf_bytes = _build_pdf_report(stats, gap, diversity)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=equityengine_bias_report.pdf"},
    )


def _build_pdf_report(stats: dict, gap: dict, diversity: dict) -> bytes:
    """
    Minimal text-based PDF built with pymupdf (already in the
    installed package list — no new dependency needed). Deliberately
    simple: headings and key figures, no charts. If you want a more
    polished report before your defence, this is a reasonable thing
    to hand-build in the frontend instead (render the same data as an
    HTML/CSS page and let the browser's print-to-PDF handle layout),
    since pymupdf's text-positioning API is tedious for anything more
    visual than what's here.
    """
    # pymupdf (imported as `fitz`) loads a large native extension that
    # costs several seconds. Only this report endpoint needs it, so it
    # is imported here rather than at module scope, where it would be
    # paid on every app startup.
    import fitz  # pymupdf — also used for PDF generation here, not just reading

    doc = fitz.open()
    page = doc.new_page()
    y = 50
    line_height = 18

    def write_line(text, size=11, bold=False, gap_after=0):
        nonlocal y, page
        if y > 780:  # near the bottom of an A4 page — start a new one
            page = doc.new_page()
            y = 50
        # PyMuPDF's base-14 font aliases: "helv" = Helvetica,
        # "hebo" = Helvetica-Bold. ("helv-bold" is not a valid alias —
        # caught this before it shipped a silently-unbolded report.)
        font = "hebo" if bold else "helv"
        page.insert_text((50, y), text, fontsize=size, fontname=font)
        y += line_height + gap_after

    write_line("EquityEngine — Bias Audit Report", size=18, bold=True, gap_after=10)
    write_line("Delta State University — Faculty of Computing", size=10, gap_after=20)

    write_line("Platform Statistics", size=13, bold=True, gap_after=4)
    write_line(f"Total candidates: {stats['total_candidates']}")
    write_line(f"Total recruiters: {stats['total_recruiters']}")
    write_line(f"Total jobs posted: {stats['total_jobs']} ({stats['active_jobs']} active)")
    write_line(f"Total applications: {stats['total_applications']}")
    write_line(f"Total shortlisted: {stats['total_shortlisted']}", gap_after=16)

    write_line("Visibility Gap", size=13, bold=True, gap_after=4)
    standard = gap["rates_by_mode"].get("standard", {})
    bdiof = gap["rates_by_mode"].get("bdiof", {})
    write_line(f"Standard mode shortlist rate: {_fmt_pct(standard.get('shortlist_rate'))}")
    write_line(f"BDIOF mode shortlist rate: {_fmt_pct(bdiof.get('shortlist_rate'))}")
    write_line(f"Visibility Gap: {_fmt_pct(gap.get('visibility_gap'))}")
    if gap.get("visibility_gap_percent_improvement") is not None:
        write_line(f"Relative improvement: {gap['visibility_gap_percent_improvement']}%")
    for warning in gap.get("warnings", []):
        write_line(f"Note: {warning}", size=9)
    write_line("", gap_after=8)
    write_line(gap.get("methodology_note", ""), size=8, gap_after=16)

    write_line("Diversity Report", size=13, bold=True, gap_after=4)
    write_line("Education tier — all candidates:")
    for tier, pct in diversity["all_candidates_distribution"].items():
        write_line(f"  {tier}: {pct}%")
    write_line("Education tier — shortlisted candidates:")
    for tier, pct in diversity["shortlisted_candidates_distribution"].items():
        write_line(f"  {tier}: {pct}%")

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _fmt_pct(value) -> str:
    return f"{round(value * 100, 1)}%" if value is not None else "insufficient data"
