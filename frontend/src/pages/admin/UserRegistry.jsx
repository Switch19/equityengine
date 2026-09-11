import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { adminApi } from "../../api/admin";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";
import EmptyState from "../../components/EmptyState";

/**
 * Admin-only registry and live audit feed — the in-app replacement for
 * inspecting candidate_profiles / users / audit_logs directly in psql.
 *
 * "Real-time" here is interval polling, not WebSocket push. The
 * existing socket layer (routers/ws.py + connection_manager) is built
 * around per-user personal delivery for chat and notifications; adding
 * an admin broadcast channel would mean touching the connection
 * manager, audit_service, and every recruiter action site that writes
 * a log row. Polling a read-only endpoint every few seconds gets the
 * same result for a dashboard someone is actively watching, at the
 * cost of up to POLL_INTERVAL_MS of staleness, and touches only this
 * file plus the admin router. Worth revisiting if the audit log ever
 * needs sub-second latency.
 */

const POLL_INTERVAL_MS = 5000;
const PAGE_SIZE = 50;

const TABS = [
  { key: "candidates", label: "Candidates" },
  { key: "recruiters", label: "Recruiters" },
  { key: "activity", label: "Activity Log" },
];

const ACTION_STYLES = {
  revealed: "badge-confirmed",
  shortlisted: "badge-verified",
  offered: "badge-verified",
  viewed: "badge-declared",
  rejected: "badge-declared",
};

/**
 * The API returns naive UTC timestamps (models.py defaults to
 * datetime.utcnow), so the serialized strings carry no timezone
 * designator. JavaScript parses a designator-less ISO date-time as
 * LOCAL time, which would silently shift every timestamp on this page
 * by the viewer's UTC offset — so mark it as UTC before parsing.
 */
function parseUtc(value) {
  if (!value) return null;
  const normalized = /(Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatDate(value) {
  const date = parseUtc(value);
  return date ? date.toLocaleDateString() : "—";
}

function formatDateTime(value) {
  const date = parseUtc(value);
  return date ? `${date.toLocaleDateString()} ${date.toLocaleTimeString()}` : "—";
}

function pct(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

export default function UserRegistry() {
  const [tab, setTab] = useState("candidates");
  const [live, setLive] = useState(true);
  const [candidates, setCandidates] = useState(null);
  const [recruiters, setRecruiters] = useState(null);
  const [feed, setFeed] = useState(null);
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Number of requests currently open, and a monotonic id for the most
  // recently *started* one. Together these keep interval polling from
  // either piling up or clobbering the view — see refresh() below.
  const pendingCount = useRef(0);
  const latestRequest = useRef(0);

  /**
   * Fetches the active tab's data.
   *
   * `manual` — a button press rather than a background poll. Only a
   * manual refresh drives the button's busy label; otherwise it would
   * flicker to "Refreshing…" and back every few seconds on its own,
   * which reads as a glitch rather than as feedback.
   *
   * `skipIfBusy` — set only by the interval, so a slow endpoint can't
   * build up a backlog of timer-fired requests. A deliberate action
   * (tab switch, filter, pagination, manual refresh) must never skip:
   * dropping one of those would leave the new view stuck on its
   * loading skeleton until the next tick, or forever while paused.
   */
  const refresh = useCallback(
    async ({ manual = false, skipIfBusy = false } = {}) => {
      if (skipIfBusy && pendingCount.current > 0) return;

      const requestId = ++latestRequest.current;
      pendingCount.current += 1;
      if (manual) setRefreshing(true);

      try {
        let applyResult;
        if (tab === "candidates") {
          const res = await adminApi.getCandidateRegistry();
          applyResult = () => setCandidates(res.data);
        } else if (tab === "recruiters") {
          const res = await adminApi.getRecruiterRegistry();
          applyResult = () => setRecruiters(res.data);
        } else {
          const res = await adminApi.getActivityLog({
            limit: PAGE_SIZE,
            offset,
            action: actionFilter || null,
          });
          applyResult = () => setFeed(res.data);
        }

        // Discard a response that a newer request has already
        // superseded. Without this, a slow reply for the tab or page
        // the user just left can land afterwards and overwrite what
        // they are now looking at.
        if (requestId !== latestRequest.current) return;

        applyResult();
        setError(null);
        setLastUpdated(new Date());
      } catch (err) {
        // Shown inline rather than as a toast: this runs on a timer,
        // and one toast per failed poll would stack up a wall of
        // identical messages within seconds of the API going down.
        if (requestId === latestRequest.current) setError(getErrorMessage(err));
      } finally {
        pendingCount.current -= 1;
        if (manual) setRefreshing(false);
      }
    },
    [tab, offset, actionFilter]
  );

  // Fetch immediately whenever the active tab, page, or filter changes.
  useEffect(() => {
    refresh();
  }, [refresh]);

  // The interval calls through a ref so it is created once per live
  // toggle. Depending on `refresh` directly would tear down and
  // recreate the timer on every tab/filter change, restarting the
  // countdown each time.
  const refreshRef = useRef(refresh);
  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  useEffect(() => {
    if (!live) return undefined;
    const id = setInterval(() => refreshRef.current(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [live]);

  function switchTab(key) {
    if (key === tab) return;
    setTab(key);
    setSearch("");
    setOffset(0);
    setError(null);
  }

  const rows = tab === "candidates" ? candidates : tab === "recruiters" ? recruiters : feed?.logs;
  const initialLoading = rows === null || rows === undefined;

  const filteredRoster = useMemo(() => {
    const source = tab === "candidates" ? candidates : recruiters;
    if (!source) return [];
    const needle = search.trim().toLowerCase();
    if (!needle) return source;
    return source.filter(
      (row) =>
        row.full_name.toLowerCase().includes(needle) ||
        row.email.toLowerCase().includes(needle) ||
        (row.company_name || "").toLowerCase().includes(needle)
    );
  }, [tab, candidates, recruiters, search]);

  return (
    <div className="max-w-6xl mx-auto px-6 py-10 pb-24">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-semibold">Users &amp; Activity</h1>
          <p className="text-slate text-sm mt-1 max-w-2xl">
            Admin-only. Live candidate and recruiter rosters plus the raw audit trail — the same
            data the Bias Audit Engine aggregates, viewable here without querying the database
            directly.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={() => setLive((value) => !value)}
            className="btn-secondary flex items-center gap-2"
            aria-pressed={live}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                live ? "bg-verified animate-pulse" : "bg-ink-100"
              }`}
              aria-hidden="true"
            />
            {live ? "Live" : "Paused"}
          </button>
          <button onClick={() => refresh({ manual: true })} disabled={refreshing} className="btn-secondary">
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      <p className="text-xs text-slate mt-3">
        {live
          ? `Auto-refreshing every ${POLL_INTERVAL_MS / 1000}s.`
          : "Auto-refresh paused — use Refresh to update."}
        {lastUpdated && ` Last updated ${lastUpdated.toLocaleTimeString()}.`}
      </p>

      {error && (
        <div className="card p-4 mt-4 border-l-4 border-l-beacon">
          <p className="text-sm font-medium">Could not refresh</p>
          <p className="text-xs text-slate mt-1">{error}</p>
        </div>
      )}

      <div className="flex gap-1 mt-6 border-b border-ink-100" role="tablist">
        {TABS.map((item) => (
          <button
            key={item.key}
            role="tab"
            aria-selected={tab === item.key}
            onClick={() => switchTab(item.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === item.key
                ? "border-ink text-ink"
                : "border-transparent text-slate hover:text-ink"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 mt-5">
        {tab !== "activity" ? (
          <>
            <input
              className="input max-w-xs"
              placeholder="Search name, email, or company…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <span className="text-xs text-slate">
              {filteredRoster.length} of {(tab === "candidates" ? candidates : recruiters)?.length ?? 0}{" "}
              {tab === "candidates" ? "candidates" : "recruiters"}
            </span>
          </>
        ) : (
          <>
            <select
              className="input max-w-[12rem]"
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setOffset(0); // a filter change invalidates the current page
              }}
            >
              <option value="">All actions</option>
              {(feed?.available_actions || []).map((action) => (
                <option key={action} value={action}>
                  {action}
                </option>
              ))}
            </select>
            <span className="text-xs text-slate">
              {feed
                ? `${feed.total_count} entr${feed.total_count === 1 ? "y" : "ies"}${
                    feed.total_count > 0
                      ? ` · showing ${feed.offset + 1}–${Math.min(
                          feed.offset + feed.limit,
                          feed.total_count
                        )}`
                      : ""
                  }`
                : ""}
            </span>
          </>
        )}
      </div>

      <div className="mt-5">
        {initialLoading ? (
          <div className="card p-6">
            <LoadingSkeleton lines={6} />
          </div>
        ) : tab === "candidates" ? (
          <CandidateTable rows={filteredRoster} />
        ) : tab === "recruiters" ? (
          <RecruiterTable rows={filteredRoster} />
        ) : (
          <ActivityTable feed={feed} offset={offset} setOffset={setOffset} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------
// Tables
// ---------------------------------------------------------------------

function TableShell({ headers, children }) {
  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-ink-100 text-left">
            {headers.map((header) => (
              <th key={header} className="px-4 py-3 text-xs font-medium text-slate whitespace-nowrap">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function CandidateTable({ rows }) {
  if (!rows.length) {
    return <EmptyState title="No candidates found" description="No candidate accounts match this view yet." />;
  }

  return (
    <TableShell
      headers={[
        "Candidate", "Status", "Evidence", "Complete", "Pipelines",
        "Apps", "Shortlisted", "Tier", "Registered",
      ]}
    >
      {rows.map((row) => (
        <tr key={row.user_id} className="border-b border-ink-100 last:border-0 hover:bg-ink-50/50">
          <td className="px-4 py-3">
            <p className="font-medium">{row.full_name}</p>
            <p className="text-xs text-slate">{row.email}</p>
          </td>
          <td className="px-4 py-3 whitespace-nowrap">
            {!row.is_active ? (
              <span className="badge badge-declared">Deactivated</span>
            ) : row.has_profile ? (
              <span className="badge badge-verified">Active</span>
            ) : (
              <span className="badge badge-declared">No profile</span>
            )}
          </td>
          <td className="px-4 py-3 score-figure">{Math.round((row.evidence_score || 0) * 100)}</td>
          <td className="px-4 py-3 font-mono text-xs">{pct(row.profile_completeness)}</td>
          <td className="px-4 py-3">
            <div className="flex gap-1">
              <PipelineDot active={row.has_cv} label="CV" />
              <PipelineDot active={row.has_github} label="GH" />
              <PipelineDot active={row.has_community} label="Com" />
            </div>
          </td>
          <td className="px-4 py-3 score-figure">{row.total_applications}</td>
          <td className="px-4 py-3 score-figure">{row.total_shortlisted}</td>
          <td className="px-4 py-3 text-xs whitespace-nowrap">{row.education_tier || "—"}</td>
          <td className="px-4 py-3 text-xs text-slate whitespace-nowrap">
            {formatDate(row.registered_at)}
          </td>
        </tr>
      ))}
    </TableShell>
  );
}

function RecruiterTable({ rows }) {
  if (!rows.length) {
    return <EmptyState title="No recruiters found" description="No recruiter accounts match this view yet." />;
  }

  return (
    <TableShell
      headers={[
        "Recruiter", "Company", "Status", "Jobs", "Apps received",
        "Shortlisted", "Views", "Reveals", "Last action",
      ]}
    >
      {rows.map((row) => (
        <tr key={row.user_id} className="border-b border-ink-100 last:border-0 hover:bg-ink-50/50">
          <td className="px-4 py-3">
            <p className="font-medium">{row.full_name}</p>
            <p className="text-xs text-slate">{row.email}</p>
          </td>
          <td className="px-4 py-3 text-xs">{row.company_name || "—"}</td>
          <td className="px-4 py-3 whitespace-nowrap">
            <span className={`badge ${row.is_active ? "badge-verified" : "badge-declared"}`}>
              {row.is_active ? "Active" : "Deactivated"}
            </span>
          </td>
          <td className="px-4 py-3 font-mono text-xs whitespace-nowrap">
            {row.active_jobs}/{row.total_jobs}
          </td>
          <td className="px-4 py-3 score-figure">{row.total_applications_received}</td>
          <td className="px-4 py-3 score-figure">{row.total_shortlisted}</td>
          <td className="px-4 py-3 score-figure">{row.total_views}</td>
          <td className="px-4 py-3 score-figure">{row.total_reveals}</td>
          <td className="px-4 py-3 text-xs text-slate whitespace-nowrap">
            {row.last_action_at ? formatDateTime(row.last_action_at) : "—"}
          </td>
        </tr>
      ))}
    </TableShell>
  );
}

function ActivityTable({ feed, offset, setOffset }) {
  const logs = feed?.logs || [];
  const totalCount = feed?.total_count || 0;
  const limit = feed?.limit || PAGE_SIZE;

  if (!logs.length) {
    return (
      <EmptyState
        title="No activity logged yet"
        description="Entries appear here as recruiters view, reveal, shortlist, or decide on candidates."
      />
    );
  }

  return (
    <>
      <TableShell
        headers={["Time", "Recruiter", "Action", "Candidate", "Job", "Mode", "Anonymised", "Time spent"]}
      >
        {logs.map((log) => (
          <tr key={log.id} className="border-b border-ink-100 last:border-0 hover:bg-ink-50/50">
            <td className="px-4 py-3 text-xs text-slate whitespace-nowrap">
              {formatDateTime(log.created_at)}
            </td>
            <td className="px-4 py-3 text-xs font-medium">{log.recruiter_name}</td>
            <td className="px-4 py-3 whitespace-nowrap">
              <span className={`badge ${ACTION_STYLES[log.action] || "badge-declared"}`}>
                {log.action}
              </span>
            </td>
            <td className="px-4 py-3 text-xs font-medium">{log.candidate_name}</td>
            <td className="px-4 py-3 text-xs">{log.job_title || "—"}</td>
            <td className="px-4 py-3 text-xs capitalize">{log.screening_mode || "—"}</td>
            <td className="px-4 py-3 text-xs">
              {log.was_anonymized ? (
                <span className="badge badge-confirmed">Yes</span>
              ) : (
                <span className="text-slate">No</span>
              )}
            </td>
            <td className="px-4 py-3 font-mono text-xs">
              {log.time_spent_seconds != null ? `${log.time_spent_seconds}s` : "—"}
            </td>
          </tr>
        ))}
      </TableShell>

      <div className="flex items-center justify-between mt-4">
        <button
          onClick={() => setOffset(Math.max(0, offset - limit))}
          disabled={offset === 0}
          className="btn-secondary"
        >
          Newer
        </button>
        <span className="text-xs text-slate">
          Page {Math.floor(offset / limit) + 1} of {Math.max(1, Math.ceil(totalCount / limit))}
        </span>
        <button
          onClick={() => setOffset(offset + limit)}
          disabled={offset + limit >= totalCount}
          className="btn-secondary"
        >
          Older
        </button>
      </div>
    </>
  );
}

function PipelineDot({ active, label }) {
  return (
    <span
      title={`${label}: ${active ? "linked" : "not linked"}`}
      className={`inline-flex items-center px-1.5 py-0.5 rounded-sm text-[10px] font-medium ${
        active ? "bg-verified-50 text-verified" : "bg-slate-50 text-slate"
      }`}
    >
      {label}
    </span>
  );
}
