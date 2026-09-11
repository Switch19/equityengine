import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { candidatesApi } from "../../api/candidates";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";

export default function CandidateDashboard() {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const [profileRes, appsRes] = await Promise.all([
        candidatesApi.getProfile(),
        candidatesApi.getMyApplications(),
      ]);
      setProfile(profileRes.data);
      setApplications(appsRes.data);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  const firstName = user.full_name.split(" ")[0];

  // A rejection only carries diagnostics if it was recorded after the
  // automated feedback feature existed, so the fields are checked rather
  // than assumed — an older rejection legitimately has neither.
  const diagnostics = applications.filter(
    (app) => app.status === "rejected" && (app.primary_reason || app.growth_tip)
  );

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 pb-24">
      <h1 className="text-2xl font-display font-semibold">Welcome back, {firstName}.</h1>

      {loading ? (
        <LoadingSkeleton lines={3} className="mt-8" />
      ) : (
        <>
          <div className="grid sm:grid-cols-3 gap-4 mt-8">
            <StatCard label="Profile completeness" value={`${Math.round(profile?.profile_completeness ?? 0)}%`} />
            <StatCard label="Evidence Score" value={Math.round((profile?.evidence_score ?? 0) * 100)} />
            <StatCard label="Applications" value={applications.length} />
          </div>

          {(profile?.profile_completeness ?? 0) < 100 && (
            <div className="card p-6 mt-6 flex items-center justify-between">
              <div>
                <p className="font-medium">Your profile isn't complete yet.</p>
                <p className="text-sm text-slate mt-0.5">
                  Add more evidence sources to strengthen your Evidence Score and badge tiers.
                </p>
              </div>
              <Link to="/candidate/profile" className="btn-primary shrink-0">Continue building</Link>
            </div>
          )}

          {diagnostics.length > 0 && <GrowthDiagnostics applications={diagnostics} />}

          <div className="mt-8">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-display font-semibold">Recent applications</h2>
              <Link to="/candidate/applications" className="text-sm text-slate underline underline-offset-2">
                View all
              </Link>
            </div>
            {applications.length === 0 ? (
              <p className="text-sm text-slate">
                You haven't applied to any jobs yet. <Link to="/candidate/jobs" className="underline">Browse open roles</Link>.
              </p>
            ) : (
              <ul className="space-y-2">
                {applications.slice(0, 3).map((app) => (
                  <li key={app.id} className="card p-3 flex items-center justify-between text-sm">
                    <span className="font-mono text-slate">{app.status}</span>
                    <span className="score-figure">
                      {app.evidence_score_at_application != null
                        ? Math.round(app.evidence_score_at_application * 100)
                        : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}

/** How many rejections the feed shows before the "View all" toggle. */
const DIAGNOSTICS_PREVIEW_COUNT = 5;

/**
 * Growth & Application Diagnostics — the automated feedback generated
 * at the moment an application was rejected (see
 * backend/app/services/feedback_service.py).
 *
 * Placed above the application list rather than inside it on purpose:
 * the whole point of the feature is that a rejection should teach the
 * candidate something, and folded into a row of statuses it would read
 * as one more piece of admin. The reason and the tip are shown together
 * and always in that order — a diagnosis with no action attached is the
 * thing candidates already get everywhere else.
 *
 * Expanded in full, though, a candidate with a long rejection history
 * buries the rest of their own dashboard — so each rejection collapses
 * to the line that identifies it (role, date, the score it was judged
 * on) and the feed is both capped and scrollable. The diagnosis is one
 * click away rather than hidden: the first item opens by default, so
 * the teaching half of the feature is never behind an interaction the
 * candidate has to discover first.
 */
function GrowthDiagnostics({ applications }) {
  const [expandedId, setExpandedId] = useState(applications[0]?.id ?? null);
  const [showAll, setShowAll] = useState(false);

  const visible = showAll ? applications : applications.slice(0, DIAGNOSTICS_PREVIEW_COUNT);

  return (
    <section className="card overflow-hidden mt-6 border-l-4 border-l-beacon">
      <div className="max-h-[500px] overflow-y-auto">
        {/* Sticky so the framing stays put while a long history scrolls
            under it — the comparison is what makes the reasons below
            legible, and it shouldn't scroll away from them. */}
        <div className="sticky top-0 bg-white z-10 px-6 pt-6 pb-4 border-b border-ink-100">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2 className="font-display font-semibold">Growth &amp; Application Diagnostics</h2>
            {applications.length > DIAGNOSTICS_PREVIEW_COUNT && (
              <button
                onClick={() => setShowAll(!showAll)}
                className="text-xs text-slate underline underline-offset-2"
              >
                {showAll
                  ? `Show latest ${DIAGNOSTICS_PREVIEW_COUNT}`
                  : `View all ${applications.length}`}
              </button>
            )}
          </div>
          <p className="text-sm text-slate mt-1">
            For each role you weren't selected for, this compares your evidence against the median of
            the applicants who were advanced — so you can see what to strengthen next, not just that
            you weren't chosen.
          </p>
        </div>

        <ul className="px-6 divide-y divide-ink-100">
          {visible.map((app) => (
            <DiagnosticItem
              key={app.id}
              app={app}
              expanded={expandedId === app.id}
              onToggle={() => setExpandedId(expandedId === app.id ? null : app.id)}
            />
          ))}
        </ul>
      </div>

      {/* Outside the scroll container: the two next steps are the point
          of the section, and shouldn't need scrolling to the end of a
          list of rejections to reach. */}
      <div className="px-6 py-4 border-t border-ink-100 flex flex-wrap gap-2">
        <Link to="/candidate/profile" className="btn-primary text-sm">
          Strengthen my profile
        </Link>
        <Link to="/candidate/competency" className="btn-secondary text-sm">
          See my Evidence Score breakdown
        </Link>
      </div>
    </section>
  );
}

/**
 * One rejection, collapsed to its identifying line. The score keeps its
 * "at the time" framing in the tooltip: it is the score the application
 * was judged on, not the candidate's score now, and the whole section
 * would mislead if the two were read as the same number.
 */
function DiagnosticItem({ app, expanded, onToggle }) {
  return (
    <li className="py-4">
      <button
        onClick={onToggle}
        aria-expanded={expanded}
        className="w-full flex items-center gap-3 text-left"
      >
        <ChevronIcon open={expanded} />

        <span className="flex-1 min-w-0">
          <span className="block font-medium text-sm truncate">
            {app.job_title || "A role you applied to"}
          </span>
          <span className="block text-xs text-slate mt-0.5">
            Applied {new Date(app.applied_at).toLocaleDateString()}
          </span>
        </span>

        {app.evidence_score_at_application != null && (
          <span
            className="text-right shrink-0"
            title="Your Evidence Score at the time you applied"
          >
            <span className="score-figure block text-sm text-beacon-600">
              {Math.round(app.evidence_score_at_application * 100)}
            </span>
            <span className="block text-[10px] text-slate uppercase tracking-wide">
              Evidence
            </span>
          </span>
        )}
      </button>

      {expanded && (
        <div className="mt-3 pl-6">
          {app.primary_reason && (
            <div>
              <p className="text-[11px] font-medium text-slate uppercase tracking-wide">
                Primary reason
              </p>
              <p className="text-sm mt-1">{app.primary_reason}</p>
            </div>
          )}

          {app.growth_tip && (
            <div className="mt-3 bg-beacon-50 rounded p-3">
              <p className="text-[11px] font-medium text-beacon-600 uppercase tracking-wide">
                Growth tip
              </p>
              <p className="text-sm mt-1">{app.growth_tip}</p>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function ChevronIcon({ open }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className={`text-slate shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
    >
      <path
        d="M4 2L8.5 6L4 10"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-slate">{label}</p>
      <p className="score-figure text-2xl mt-1">{value}</p>
    </div>
  );
}
