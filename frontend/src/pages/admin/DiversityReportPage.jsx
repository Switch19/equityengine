import { useState, useEffect, useCallback } from "react";
import { adminApi } from "../../api/admin";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";

export default function DiversityReportPage() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const res = await adminApi.getDiversityReport();
      setReport(res.data);
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
      <h1 className="text-2xl font-display font-semibold">Diversity Report</h1>
      <p className="text-slate text-sm mt-1 mb-8">
        Education tier distribution across all candidates versus those shortlisted.
      </p>

      {report.small_sample && (
        <div className="text-sm bg-gap-50 text-gap rounded p-4 mb-4">
          Fewer than 10 shortlisted candidates — treat this distribution as preliminary.
        </div>
      )}

      <div className="grid sm:grid-cols-2 gap-4">
        <DistributionCard
          title="All candidates"
          distribution={report.all_candidates_distribution}
          total={report.total_candidates}
        />
        <DistributionCard
          title="Shortlisted candidates"
          distribution={report.shortlisted_candidates_distribution}
          total={report.total_shortlisted}
        />
      </div>
    </div>
  );
}

function DistributionCard({ title, distribution, total }) {
  const entries = Object.entries(distribution || {});
  return (
    <div className="card p-5">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="font-display font-semibold">{title}</h2>
        <span className="text-xs text-slate">n={total}</span>
      </div>
      {entries.length === 0 ? (
        <p className="text-sm text-slate">No data yet.</p>
      ) : (
        <div className="space-y-3">
          {entries.map(([tier, pct]) => (
            <div key={tier}>
              <div className="flex justify-between text-xs mb-1">
                <span>{tier}</span>
                <span className="font-mono">{pct}%</span>
              </div>
              <div className="h-2 bg-ink-50 rounded-full overflow-hidden">
                <div className="h-full bg-beacon" style={{ width: `${pct}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
