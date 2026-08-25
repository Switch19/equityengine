import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { recruitersApi } from "../../api/recruiters";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";
import EmptyState from "../../components/EmptyState";

export default function JobsList() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const res = await recruitersApi.listJobs();
      setJobs(res.data);
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
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-display font-semibold">My Jobs</h1>
        <Link to="/recruiter/jobs/new" className="btn-primary">Post a Job</Link>
      </div>

      {loading ? (
        <LoadingSkeleton lines={4} />
      ) : jobs.length === 0 ? (
        <EmptyState
          title="No jobs posted yet"
          description="Post your first job to start reviewing candidates through the Competency Dossier."
          action={<Link to="/recruiter/jobs/new" className="btn-primary">Post a Job</Link>}
        />
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <Link
              key={job.id}
              to={`/recruiter/jobs/${job.id}`}
              className="card p-5 flex items-center justify-between hover:border-ink-400 transition-colors"
            >
              <div>
                <h2 className="font-display font-semibold">{job.title}</h2>
                <p className="text-xs text-slate mt-1">
                  {job.location || "Remote"} · {job.is_active ? "Active" : "Closed"}
                </p>
              </div>
              <span className={`badge shrink-0 ${job.screening_mode === "bdiof" ? "badge-verified" : "badge-declared"}`}>
                {job.screening_mode.toUpperCase()}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
