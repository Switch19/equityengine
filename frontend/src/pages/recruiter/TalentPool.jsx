import { useState, useEffect, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { recruitersApi } from "../../api/recruiters";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";
import EmptyState from "../../components/EmptyState";
import SkillBadge from "../../components/SkillBadge";

/**
 * Recruiter Talent Pool — proactive sourcing across every registered
 * candidate, as opposed to the Competency Dossier's reactive review of
 * one job's applicants.
 *
 * Filtering is server-side (see routers/recruiters.py), which is why
 * the search box is debounced rather than filtering a cached array: the
 * skill index this searches is the Competency Engine's normalised,
 * badge-tagged skill list, which is computed on the server and is not
 * a field the client holds in full.
 */

const PAGE_SIZE = 25;
const SEARCH_DEBOUNCE_MS = 300;

// Evidence Score is 0.0-1.0 on the wire and 0-100 in the UI, matching
// every other score the candidate and recruiter see.
const SCORE_FILTERS = [
  { label: "Any score", value: 0 },
  { label: "40+", value: 0.4 },
  { label: "55+", value: 0.55 },
  { label: "70+", value: 0.7 },
];

const PIPELINE_ORDER = ["formal", "informal", "community"];

function asScore(value) {
  return Math.round((value || 0) * 100);
}

export default function TalentPool() {
  const [pool, setPool] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [inviteFor, setInviteFor] = useState(null);
  const { showToast } = useToast();

  // Discards a response that a newer request has already superseded —
  // typing quickly can otherwise land an older, broader result set on
  // top of a narrower one the recruiter is already reading.
  const latestRequest = useRef(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput.trim());
      setOffset(0); // a new search invalidates the current page
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const loadPool = useCallback(async () => {
    const requestId = ++latestRequest.current;
    setLoading(true);
    try {
      const res = await recruitersApi.getTalentPool({
        search,
        minScore,
        limit: PAGE_SIZE,
        offset,
      });
      if (requestId !== latestRequest.current) return;
      setPool(res.data);
      setError(null);
    } catch (err) {
      if (requestId === latestRequest.current) setError(getErrorMessage(err));
    } finally {
      if (requestId === latestRequest.current) setLoading(false);
    }
  }, [search, minScore, offset]);

  useEffect(() => {
    loadPool();
  }, [loadPool]);

  // The recruiter's own jobs, for the invite picker. Loaded once —
  // it does not change as the pool is filtered.
  useEffect(() => {
    recruitersApi
      .listJobs()
      .then((res) => setJobs(res.data.filter((job) => job.is_active)))
      .catch((err) => showToast(getErrorMessage(err), "error"));
  }, [showToast]);

  async function handleInvite(candidate, jobId, note) {
    try {
      const res = await recruitersApi.inviteToJob(candidate.candidate_id, jobId, note);
      showToast(res.data.detail, "success");
      setInviteFor(null);
      // Refetch so the candidate's row reflects the new invitation
      // rather than relying on a local guess about server state.
      loadPool();
    } catch (err) {
      showToast(getErrorMessage(err), "error");
    }
  }

  const candidates = pool?.candidates || [];
  const totalCount = pool?.total_count || 0;
  const hasFilters = Boolean(search) || minScore > 0;

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 pb-24">
      <h1 className="text-2xl font-display font-semibold">Talent Pool</h1>
      <p className="text-slate text-sm mt-1 max-w-2xl">
        Every candidate on the platform, ranked by Evidence Score, with the three evidence
        pipelines that produced it. Inviting someone asks them to apply — their application then
        goes through this job's screening mode like any other.
      </p>

      <div className="flex flex-wrap items-center gap-3 mt-6">
        <input
          className="input max-w-xs"
          placeholder="Search by name or skill…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          aria-label="Search candidates by name or skill"
        />
        <select
          className="input max-w-[10rem]"
          value={minScore}
          onChange={(e) => {
            setMinScore(Number(e.target.value));
            setOffset(0);
          }}
          aria-label="Minimum Evidence Score"
        >
          {SCORE_FILTERS.map((filter) => (
            <option key={filter.value} value={filter.value}>
              {filter.label}
            </option>
          ))}
        </select>
        <span className="text-xs text-slate">
          {totalCount} candidate{totalCount === 1 ? "" : "s"}
          {hasFilters ? " match" : ""}
          {totalCount > 0 &&
            ` · showing ${offset + 1}–${Math.min(offset + PAGE_SIZE, totalCount)}`}
        </span>
      </div>

      {jobs.length === 0 && (
        <div className="card p-4 mt-5 border-l-4 border-l-beacon">
          <p className="text-sm font-medium">No active jobs to invite candidates to.</p>
          <p className="text-xs text-slate mt-1">
            <Link to="/recruiter/jobs/new" className="underline underline-offset-2">
              Post a job
            </Link>{" "}
            first — you can browse the pool either way, but an invitation needs an open role.
          </p>
        </div>
      )}

      {error && (
        <div className="card p-4 mt-5 border-l-4 border-l-gap">
          <p className="text-sm font-medium">Could not load the talent pool</p>
          <p className="text-xs text-slate mt-1">{error}</p>
        </div>
      )}

      <div className="mt-5">
        {loading && pool === null ? (
          <div className="card p-6">
            <LoadingSkeleton lines={6} />
          </div>
        ) : candidates.length === 0 ? (
          <EmptyState
            title={hasFilters ? "No candidates match these filters" : "No candidates yet"}
            description={
              hasFilters
                ? "Try a broader skill term, or lower the minimum Evidence Score."
                : "Candidates appear here once they register and build a Competency Profile."
            }
          />
        ) : (
          <div className={`space-y-3 ${loading ? "opacity-60 transition-opacity" : ""}`}>
            {candidates.map((candidate) => (
              <CandidateCard
                key={candidate.candidate_id}
                candidate={candidate}
                jobs={jobs}
                expanded={expandedId === candidate.candidate_id}
                onToggle={() =>
                  setExpandedId(
                    expandedId === candidate.candidate_id ? null : candidate.candidate_id
                  )
                }
                inviteOpen={inviteFor === candidate.candidate_id}
                onOpenInvite={() =>
                  setInviteFor(inviteFor === candidate.candidate_id ? null : candidate.candidate_id)
                }
                onInvite={(jobId, note) => handleInvite(candidate, jobId, note)}
              />
            ))}
          </div>
        )}
      </div>

      {totalCount > PAGE_SIZE && (
        <div className="flex items-center justify-between mt-6">
          <button
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            disabled={offset === 0}
            className="btn-secondary"
          >
            Previous
          </button>
          <span className="text-xs text-slate">
            Page {Math.floor(offset / PAGE_SIZE) + 1} of{" "}
            {Math.max(1, Math.ceil(totalCount / PAGE_SIZE))}
          </span>
          <button
            onClick={() => setOffset(offset + PAGE_SIZE)}
            disabled={offset + PAGE_SIZE >= totalCount}
            className="btn-secondary"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------
// Candidate card
// ---------------------------------------------------------------------

function CandidateCard({
  candidate,
  jobs,
  expanded,
  onToggle,
  inviteOpen,
  onOpenInvite,
  onInvite,
}) {
  const alreadyInvited = candidate.invited_job_ids.length > 0;

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-4 p-4">
        <div className="w-12 h-12 rounded-full bg-beacon-50 flex items-center justify-center text-ink font-display font-semibold shrink-0">
          {candidate.full_name?.[0] || "?"}
        </div>

        <button onClick={onToggle} className="flex-1 min-w-0 text-left" aria-expanded={expanded}>
          <p className="font-medium truncate">{candidate.full_name}</p>
          <p className="text-xs text-slate">
            {candidate.experience_level} · {candidate.education_tier} ·{" "}
            {Math.round(candidate.profile_completeness)}% complete
          </p>
        </button>

        <div className="hidden sm:flex items-center gap-3 shrink-0">
          {PIPELINE_ORDER.map((key) => (
            <PipelineMeter key={key} pipeline={candidate.pipelines[key]} />
          ))}
        </div>

        <div className="text-right shrink-0">
          <span className="score-figure text-xl text-beacon-600">
            {asScore(candidate.evidence_score)}
          </span>
          <p className="text-[10px] text-slate uppercase tracking-wide">Evidence</p>
        </div>

        <button
          onClick={onOpenInvite}
          disabled={jobs.length === 0}
          className={`shrink-0 text-xs px-3 py-1.5 ${
            alreadyInvited ? "btn-secondary" : "btn-beacon"
          }`}
          title={
            jobs.length === 0
              ? "You need an active job before you can invite candidates"
              : "Invite this candidate to one of your active jobs"
          }
        >
          {alreadyInvited ? "Invite again" : "Invite"}
        </button>
      </div>

      {inviteOpen && (
        <InvitePanel
          candidate={candidate}
          jobs={jobs}
          onCancel={onOpenInvite}
          onInvite={onInvite}
        />
      )}

      {expanded && <CandidateDetail candidate={candidate} />}
    </div>
  );
}

/**
 * One pipeline's strength as a short vertical bar. Shows the pipeline's
 * OWN score, not its weighted contribution — a recruiter comparing two
 * candidates wants to know how strong each pipeline is, and the
 * contribution is in the expanded breakdown below where the weights are
 * spelled out alongside it.
 */
function PipelineMeter({ pipeline }) {
  if (!pipeline) return null;
  const height = Math.max(4, Math.round(pipeline.score * 32));
  return (
    <div
      className="flex flex-col items-center gap-1"
      title={`${pipeline.label}: ${asScore(pipeline.score)}/100 · ${pipeline.detail}`}
    >
      <div className="w-2 h-8 bg-ink-50 rounded-sm flex flex-col justify-end overflow-hidden">
        <div
          className={pipeline.linked ? "bg-verified" : "bg-ink-100"}
          style={{ height: `${height}px` }}
        />
      </div>
      <span className="text-[9px] text-slate font-mono uppercase">
        {pipeline.label.charAt(0)}
      </span>
    </div>
  );
}

function CandidateDetail({ candidate }) {
  return (
    <div className="border-t border-ink-100 p-4 bg-ink-50/40 space-y-4">
      <div>
        <p className="text-xs font-medium text-slate mb-2">Evidence pipelines</p>
        <div className="grid sm:grid-cols-3 gap-3">
          {PIPELINE_ORDER.map((key) => (
            <PipelineCard key={key} pipeline={candidate.pipelines[key]} />
          ))}
        </div>
        <p className="text-[11px] text-slate mt-2">
          Each pipeline's contribution is its score times its weight; the three sum to the
          Evidence Score of {asScore(candidate.evidence_score)}.
        </p>
      </div>

      {candidate.top_skills.length > 0 && (
        <div>
          <p className="text-xs font-medium text-slate mb-2">
            Best-corroborated skills{" "}
            {candidate.skills.length > candidate.top_skills.length &&
              `(${candidate.top_skills.length} of ${candidate.skills.length})`}
          </p>
          <div className="flex flex-wrap gap-2">
            {candidate.top_skills.map((entry) => (
              <SkillBadge
                key={entry.skill}
                skill={entry.skill}
                tier={entry.tier}
                sources={entry.sources}
              />
            ))}
          </div>
        </div>
      )}

      <div className="text-xs text-slate space-y-0.5">
        <p>
          <span className="font-medium text-ink">Email:</span> {candidate.email}
        </p>
        {candidate.github_username && (
          <p>
            <span className="font-medium text-ink">GitHub:</span> @{candidate.github_username}
          </p>
        )}
        <p>
          <span className="font-medium text-ink">Applications:</span>{" "}
          {candidate.total_applications} across the platform
        </p>
      </div>
    </div>
  );
}

function PipelineCard({ pipeline }) {
  if (!pipeline) return null;
  return (
    <div className="bg-white rounded border border-ink-100 p-3">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-xs font-medium">{pipeline.label}</p>
        <span className="score-figure text-sm">{asScore(pipeline.score)}</span>
      </div>
      <div className="h-1.5 bg-ink-50 rounded-sm mt-2 overflow-hidden">
        <div
          className={`h-full ${pipeline.linked ? "bg-verified" : "bg-ink-100"}`}
          style={{ width: `${asScore(pipeline.score)}%` }}
        />
      </div>
      <p className="text-[11px] text-slate mt-1.5">{pipeline.detail}</p>
      <p className="text-[10px] text-slate font-mono mt-0.5">
        {Math.round(pipeline.weight * 100)}% weight · +{asScore(pipeline.contribution)} to score
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------
// Invite panel
// ---------------------------------------------------------------------

function InvitePanel({ candidate, jobs, onCancel, onInvite }) {
  const [jobId, setJobId] = useState(jobs[0]?.id || "");
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);

  const alreadyInvitedToSelected = candidate.invited_job_ids.includes(jobId);

  async function submit(e) {
    e.preventDefault();
    if (!jobId) return;
    setSending(true);
    try {
      await onInvite(jobId, note);
    } finally {
      setSending(false);
    }
  }

  return (
    <form onSubmit={submit} className="border-t border-ink-100 p-4 bg-beacon-50/40 space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[12rem]">
          <label className="label" htmlFor={`job-${candidate.candidate_id}`}>
            Invite to
          </label>
          <select
            id={`job-${candidate.candidate_id}`}
            className="input"
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
          >
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title} ({job.screening_mode.toUpperCase()})
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className="btn-primary" disabled={sending || !jobId}>
          {sending ? "Sending…" : "Send invitation"}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">
          Cancel
        </button>
      </div>

      <div>
        <label className="label" htmlFor={`note-${candidate.candidate_id}`}>
          Note (optional, 500 characters max)
        </label>
        <input
          id={`note-${candidate.candidate_id}`}
          className="input"
          maxLength={500}
          placeholder="Why you think they'd be a good fit…"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>

      {alreadyInvitedToSelected && (
        <p className="text-xs text-gap">
          You have already invited this candidate to that role — sending again will be rejected.
        </p>
      )}
    </form>
  );
}
