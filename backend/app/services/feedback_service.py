"""
Automated post-rejection feedback.

Rejection is normally the point at which a candidate learns nothing.
This module turns it into the one place they learn the most: at the
moment an application is rejected, it compares that candidate's three
evidence pipelines against the MEDIAN of the applicants the recruiter
actually advanced for the same job, finds the pipeline with the largest
deficit, and writes a plain-language `primary_reason` and `growth_tip`
onto the application row.

Why the median of advanced applicants, rather than a fixed threshold:
a fixed bar would tell every rejected candidate the same thing on every
job. A per-job comparison group answers the question the candidate
actually has — "what did the people who got through have that I
didn't?" — and it answers it in the terms this platform already
measures, so the advice points at something they can act on.

Why the median rather than the mean: the comparison group is often
tiny (two or three advanced applicants on a typical job), which is
exactly the size at which one exceptional candidate drags a mean far
above anything the rest of the pool needed to clear. The median stays
representative of the group at n=2 or n=3.

Two deliberate boundaries:

  - NOTHING here is ever shown to the recruiter as a justification for
    their decision, and nothing here influences the decision. The
    feedback is generated AFTER the recruiter has already set the
    status, purely to explain the outcome to the candidate.
  - The text names pipelines and scores, never other candidates. The
    comparison group is only ever referenced as an aggregate, so this
    cannot become a channel that leaks who else applied — the same
    discipline dossier_service.py and chat_service.py apply.
"""
from statistics import median

from sqlalchemy.orm import Session

from app.models import Application, CandidateProfile, Job
from app.services.bias_audit_engine import SELECTED_STATUSES
from app.services.competency_engine import EVIDENCE_WEIGHTS
from app.services.embedding_service import best_match_similarity_batch

# A gap smaller than this is noise, not a finding. Scores are 0.0-1.0,
# so 0.05 is five percentage points on the scale the candidate sees —
# below that, telling someone their CV evidence was "behind" the
# advanced group would be technically true and practically misleading.
MIN_MEANINGFUL_GAP = 0.05

# The three evidence pipelines, in the terms the rest of the system
# uses. `key` is the Evidence Score component each pipeline owns; the
# weight is read from the Competency Engine rather than restated here,
# so a reweighting of the score cannot silently desynchronise the
# advice given about it.
#
# L_traj (learning trajectory) is deliberately not its own dimension:
# it is derived from the same GitHub data as G_act, so a candidate
# behind on both would be told about "GitHub" twice, and there is no
# distinct action a candidate can take on it beyond what the GitHub
# advice already says.
PIPELINES = [
    {
        "key": "p_emb",
        "name": "cv",
        "label": "CV & project evidence",
        # Mid-sentence form. Kept as its own string rather than
        # lower-casing `label`, which would produce "cv & project
        # evidence" and read as a typo.
        "phrase": "your CV and project evidence",
        "reason": (
            "Your CV and project evidence matched this role's requirements less closely than the "
            "applicants who were advanced — your project descriptions scored {candidate} against "
            "their median of {benchmark}."
        ),
        "tip": (
            "Rewrite your project descriptions to name the specific problem, the technologies you "
            "used, and the measurable outcome. This role's requirements were {requirements} — "
            "projects that visibly demonstrate those weigh more here than any other single factor "
            "({weight}% of your Evidence Score)."
        ),
    },
    {
        "key": "g_act",
        "name": "github",
        "label": "GitHub activity",
        "phrase": "your GitHub activity",
        "reason": (
            "Your GitHub activity was the weakest part of your application relative to the "
            "applicants who were advanced — you scored {candidate} against their median of "
            "{benchmark}."
        ),
        "tip": (
            "Commit consistently to two or three public repositories rather than in occasional "
            "bursts, and give each one a README that explains what it does. Steady recent activity "
            "and documented repositories are what this pipeline measures ({weight}% of your "
            "Evidence Score)."
        ),
    },
    {
        "key": "c_peer",
        "name": "community",
        "label": "Community evidence",
        "phrase": "your community evidence",
        "reason": (
            "Your community evidence was thinner than that of the applicants who were advanced — "
            "you scored {candidate} against their median of {benchmark}."
        ),
        "tip": (
            "Add the certifications you already hold, link your Stack Overflow account, and ask "
            "peers you have worked with to endorse specific skills. This is the fastest pipeline "
            "to improve because it credits work you have already done ({weight}% of your Evidence "
            "Score)."
        ),
    },
]


def generate_rejection_feedback(db: Session, application: Application, job: Job) -> dict:
    """
    Returns {"primary_reason": str, "growth_tip": str} for a rejected
    application. Never raises on sparse data — an empty comparison
    group, a profile with no evidence at all, and a candidate who beat
    every median all have their own defined outcome below, because all
    three are ordinary situations on a young platform rather than
    errors.
    """
    profile = application.candidate
    benchmark_profiles = _advanced_applicant_profiles(db, job, exclude_application_id=application.id)

    # Job-specific P_emb for the candidate and every peer at once. Done
    # in one batch because each score otherwise re-encodes this job's
    # requirements — see best_match_similarity_batch().
    p_emb_scores = _job_specific_p_emb(job, [profile] + benchmark_profiles)
    candidate_scores = _pipeline_scores(profile, p_emb_scores[0])
    benchmark_scores = [
        _pipeline_scores(peer, p_emb)
        for peer, p_emb in zip(benchmark_profiles, p_emb_scores[1:])
    ]

    if not benchmark_scores:
        return _no_comparison_group_feedback(candidate_scores, job)

    medians = {
        pipeline["key"]: median(scores[pipeline["key"]] for scores in benchmark_scores)
        for pipeline in PIPELINES
    }

    # Ranked on the RAW gap, not the gap weighted by its Evidence Score
    # share. The candidate is being told which pipeline they are
    # furthest behind on, which is the question they can act on; how
    # much each pipeline is worth is then stated in the tip itself.
    gaps = sorted(
        (
            (medians[pipeline["key"]] - candidate_scores[pipeline["key"]], pipeline)
            for pipeline in PIPELINES
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    largest_gap, pipeline = gaps[0]

    if largest_gap < MIN_MEANINGFUL_GAP:
        return _competitive_pool_feedback(candidate_scores, len(benchmark_scores))

    return {
        "primary_reason": pipeline["reason"].format(
            candidate=_as_score(candidate_scores[pipeline["key"]]),
            benchmark=_as_score(medians[pipeline["key"]]),
        ),
        "growth_tip": pipeline["tip"].format(
            weight=int(EVIDENCE_WEIGHTS[pipeline["key"]] * 100),
            requirements=_format_requirements(job),
        ),
    }


# ---------------------------------------------------------------------
# Comparison group
# ---------------------------------------------------------------------

def _advanced_applicant_profiles(
    db: Session, job: Job, exclude_application_id
) -> list[CandidateProfile]:
    """
    The candidates this recruiter moved forward on this job — the
    benchmark the rejected candidate is measured against.

    SELECTED_STATUSES is reused from the Bias Audit Engine rather than
    restated, so "advanced" means the same thing here as it does in the
    shortlist rates the platform reports. It covers shortlisted,
    interview, and offered: an offered candidate was necessarily
    advanced past both earlier stages, and excluding them would bias
    the benchmark downward on any job that moved quickly to an offer.
    """
    return (
        db.query(CandidateProfile)
        .join(Application, Application.candidate_id == CandidateProfile.id)
        .filter(
            Application.job_id == job.id,
            Application.status.in_(SELECTED_STATUSES),
            Application.id != exclude_application_id,
        )
        .all()
    )


def _job_specific_p_emb(job: Job, profiles: list[CandidateProfile]) -> list[float]:
    """
    P_emb per profile against THIS job's requirements — the same
    computation compute_job_specific_evidence_score() performs for
    dossier ranking, so the candidate is compared on the axis they were
    actually ranked on, not on the profile-level self-consistency
    baseline (which answers a different question entirely).
    """
    job_reference_texts = list(job.required_skills or [])
    if job.description:
        job_reference_texts.append(job.description)

    project_text_groups = [
        [p.get("description", "") for p in (profile.cv_projects or [])]
        + [r.get("description", "") for r in (profile.github_repos or []) if r.get("description")]
        for profile in profiles
    ]
    return [round(score, 3) for score in best_match_similarity_batch(project_text_groups, job_reference_texts)]


def _pipeline_scores(profile: CandidateProfile, job_specific_p_emb: float) -> dict:
    """The three pipeline scores for one profile, 0.0-1.0 each."""
    return {
        "p_emb": job_specific_p_emb,
        "g_act": profile.g_act_score or 0.0,
        "c_peer": profile.c_peer_score or 0.0,
    }


# ---------------------------------------------------------------------
# Fallbacks — both are ordinary cases, not error paths
# ---------------------------------------------------------------------

def _no_comparison_group_feedback(candidate_scores: dict, job: Job) -> dict:
    """
    No one was advanced on this job, so there is no median to compare
    against. Saying nothing would be the worst outcome for the
    candidate, so the advice falls back to their own weakest pipeline in
    absolute terms — still actionable — and is explicit that no
    comparison group existed, rather than implying one did.
    """
    pipeline = min(PIPELINES, key=lambda p: candidate_scores[p["key"]])
    return {
        "primary_reason": (
            f"This role was closed without a shortlist, so there is no comparison group to measure "
            f"your application against. Across your own evidence, {pipeline['phrase']} is "
            f"currently your weakest pipeline at {_as_score(candidate_scores[pipeline['key']])}."
        ),
        "growth_tip": pipeline["tip"].format(
            weight=int(EVIDENCE_WEIGHTS[pipeline["key"]] * 100),
            requirements=_format_requirements(job),
        ),
    }


def _competitive_pool_feedback(candidate_scores: dict, benchmark_size: int) -> dict:
    """
    The candidate matched or beat the advanced group's median on every
    pipeline. Inventing a deficit here would be dishonest, and telling
    them to improve something they were already competitive on wastes
    the one piece of feedback they get — so this says plainly that the
    evidence was competitive, and points the improvement advice at
    their lowest absolute pipeline as a margin-building step rather
    than as the cause of the rejection.
    """
    pipeline = min(PIPELINES, key=lambda p: candidate_scores[p["key"]])
    peers = "applicant" if benchmark_size == 1 else "applicants"
    return {
        "primary_reason": (
            f"Your evidence was competitive — you matched or exceeded the median of the "
            f"{benchmark_size} {peers} advanced for this role on all three pipelines. This "
            f"rejection reflects the recruiter's final choice among strong applications rather "
            f"than a gap in your profile."
        ),
        "growth_tip": (
            f"Nothing here needs fixing. To build margin on future applications, "
            f"{pipeline['phrase']} is your lowest pipeline at "
            f"{_as_score(candidate_scores[pipeline['key']])} — strengthening it raises your "
            f"Evidence Score on every role you apply to, not just this one."
        ),
    }


# ---------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------

def _as_score(value: float) -> str:
    """
    Rendered on the 0-100 scale the candidate already sees everywhere
    else in the UI (dashboards, dossier cards, application rows), not
    the raw 0.0-1.0 the engine works in.
    """
    return str(round(value * 100))


def _format_requirements(job: Job) -> str:
    skills = [s for s in (job.required_skills or []) if s]
    if not skills:
        return "not listed explicitly on this posting"
    if len(skills) <= 4:
        return ", ".join(skills)
    return ", ".join(skills[:4]) + f", and {len(skills) - 4} more"
