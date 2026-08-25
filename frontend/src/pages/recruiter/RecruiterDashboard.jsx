import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { recruitersApi } from "../../api/recruiters";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";

export default function RecruiterDashboard() {
  const { user } = useAuth();
  const [company, setCompany] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const jobsRes = await recruitersApi.listJobs();
      setJobs(jobsRes.data);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    }
    try {
      const companyRes = await recruitersApi.getCompany();
      setCompany(companyRes.data);
    } catch {
      // No company yet — handled by the CTA card below, not an error toast.
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  const firstName = user.full_name.split(" ")[0];
  const activeJobs = jobs.filter((j) => j.is_active).length;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-display font-semibold">Welcome back, {firstName}.</h1>

      {loading ? (
        <LoadingSkeleton lines={3} className="mt-8" />
      ) : !company ? (
        <div className="card p-6 mt-8 flex items-center justify-between">
          <div>
            <p className="font-medium">Create your company profile to get started.</p>
            <p className="text-sm text-slate mt-0.5">Required before you can post a job.</p>
          </div>
          <Link to="/recruiter/company" className="btn-primary shrink-0">Create profile</Link>
        </div>
      ) : (
        <>
          <div className="grid sm:grid-cols-2 gap-4 mt-8">
            <StatCard label="Active jobs" value={activeJobs} />
            <StatCard label="Total jobs posted" value={jobs.length} />
          </div>

          <div className="mt-8">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-display font-semibold">Your jobs</h2>
              <Link to="/recruiter/jobs/new" className="text-sm text-slate underline underline-offset-2">
                Post a new job
              </Link>
            </div>
            {jobs.length === 0 ? (
              <p className="text-sm text-slate">No jobs posted yet.</p>
            ) : (
              <ul className="space-y-2">
                {jobs.slice(0, 5).map((job) => (
                  <li key={job.id}>
                    <Link to={`/recruiter/jobs/${job.id}`} className="card p-3 flex items-center justify-between text-sm hover:border-ink-400 transition-colors">
                      <span>{job.title}</span>
                      <span className="badge badge-declared">{job.screening_mode.toUpperCase()}</span>
                    </Link>
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

function StatCard({ label, value }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-slate">{label}</p>
      <p className="score-figure text-2xl mt-1">{value}</p>
    </div>
  );
}
