import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { candidatesApi } from "../../api/candidates";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";
import EmptyState from "../../components/EmptyState";

const STATUS_STYLES = {
  applied: "badge-declared",
  viewed: "badge-declared",
  shortlisted: "badge-confirmed",
  interview: "badge-confirmed",
  offered: "badge-verified",
  rejected: "bg-gap-50 text-gap",
};

export default function Applications() {
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const res = await candidatesApi.getMyApplications();
      setApplications(res.data);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 pb-24">
      <h1 className="text-2xl font-display font-semibold">Your Applications</h1>
      <p className="text-slate text-sm mt-1 mb-8">
        The Evidence Score shown is a snapshot from when you applied — your live score may have
        changed since.
      </p>

      {loading ? (
        <LoadingSkeleton lines={5} />
      ) : applications.length === 0 ? (
        <EmptyState
          title="No applications yet"
          description="Once you apply to a job, you'll be able to track its status here."
          action={<Link to="/candidate/jobs" className="btn-primary">Browse jobs</Link>}
        />
      ) : (
        <div className="space-y-3">
          {applications.map((app) => (
            <div key={app.id} className="card p-4 flex items-center justify-between gap-4">
              <div>
                <span className={`badge ${STATUS_STYLES[app.status] || "badge-declared"}`}>
                  {app.status}
                </span>
                <p className="text-xs text-slate mt-1.5">
                  Applied {new Date(app.applied_at).toLocaleDateString()} ·{" "}
                  {app.screening_mode_at_application.toUpperCase()} mode
                </p>
              </div>
              <span className="score-figure text-lg text-beacon-600 shrink-0">
                {app.evidence_score_at_application != null
                  ? Math.round(app.evidence_score_at_application * 100)
                  : "—"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
