import { useState, useEffect, useCallback } from "react";
import { adminApi } from "../../api/admin";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";

export default function AdminOverview() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const res = await adminApi.getStats();
      setStats(res.data);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDownloadReport() {
    setDownloading(true);
    try {
      const res = await adminApi.downloadReportPdf();
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "equityengine_bias_report.pdf");
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setDownloading(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <LoadingSkeleton lines={5} />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 pb-24">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-display font-semibold">Platform Overview</h1>
        <button onClick={handleDownloadReport} disabled={downloading} className="btn-secondary">
          {downloading ? "Preparing…" : "Download Bias Report (PDF)"}
        </button>
      </div>

      <div className="grid sm:grid-cols-3 gap-4">
        <StatCard label="Candidates" value={stats.total_candidates} />
        <StatCard label="Recruiters" value={stats.total_recruiters} />
        <StatCard label="Companies" value={stats.total_companies} />
        <StatCard label="Jobs posted" value={stats.total_jobs} />
        <StatCard label="Active jobs" value={stats.active_jobs} />
        <StatCard label="Applications" value={stats.total_applications} />
        <StatCard label="Shortlisted" value={stats.total_shortlisted} />
      </div>

      <div className="card p-6 mt-6">
        <h2 className="font-display font-semibold mb-3">Jobs by screening mode</h2>
        <div className="space-y-2">
          {Object.entries(stats.jobs_by_screening_mode).map(([mode, count]) => (
            <div key={mode} className="flex justify-between text-sm">
              <span className="capitalize">{mode}</span>
              <span className="score-figure">{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
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
