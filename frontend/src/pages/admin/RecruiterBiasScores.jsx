import { useState, useEffect, useCallback } from "react";
import { adminApi } from "../../api/admin";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";
import EmptyState from "../../components/EmptyState";

export default function RecruiterBiasScores() {
  const [scores, setScores] = useState([]);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const res = await adminApi.getRecruiterBiasScores();
      setScores(res.data);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <LoadingSkeleton lines={5} />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 pb-24">
      <h1 className="text-2xl font-display font-semibold">Recruiter Bias Scores</h1>
      <p className="text-slate text-sm mt-1 mb-8">
        Admin-only — recruiters never see their own score. Higher score indicates more concerning
        skew, not a "failing grade"; treat as a hand-calibrated diagnostic, not a validated metric.
      </p>

      {scores.length === 0 ? (
        <EmptyState title="No recruiter activity yet" description="Scores appear once recruiters have received applications on their jobs." />
      ) : (
        <div className="space-y-3">
          {scores.map((r) => (
            <div key={r.recruiter_id} className="card p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium">{r.recruiter_name}</p>
                  <p className="text-xs text-slate mt-0.5">
                    {r.total_applications_received} applications received
                    {r.small_sample && " · small sample, preliminary"}
                  </p>
                </div>
                <span className="score-figure text-2xl text-beacon-600 shrink-0">
                  {r.bias_score != null ? r.bias_score : "—"}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 mt-4 text-xs">
                <div>
                  <p className="text-slate">Anonymised shortlist rate</p>
                  <p className="font-mono mt-0.5">
                    {r.anonymized_shortlist_rate != null ? `${Math.round(r.anonymized_shortlist_rate * 100)}%` : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate">Identity-visible shortlist rate</p>
                  <p className="font-mono mt-0.5">
                    {r.identity_visible_shortlist_rate != null ? `${Math.round(r.identity_visible_shortlist_rate * 100)}%` : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate">Applicant pool — Graduate share</p>
                  <p className="font-mono mt-0.5">
                    {r.applicant_pool_graduate_share != null ? `${Math.round(r.applicant_pool_graduate_share * 100)}%` : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate">Shortlisted — Graduate share</p>
                  <p className="font-mono mt-0.5">
                    {r.shortlisted_graduate_share != null ? `${Math.round(r.shortlisted_graduate_share * 100)}%` : "—"}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
