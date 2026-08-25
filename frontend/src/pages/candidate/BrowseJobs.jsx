import { useState, useEffect, useCallback } from "react";
import { candidatesApi } from "../../api/candidates";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";
import EmptyState from "../../components/EmptyState";

const MODE_LABELS = {
  standard: { label: "Standard", hint: "Identity visible to recruiter" },
  bdiof: { label: "BDIOF", hint: "Fully anonymised until interview request" },
  hybrid: { label: "Hybrid", hint: "Anonymised until shortlisted" },
};

export default function BrowseJobs() {
  const [jobs, setJobs] = useState([]);
  const [appliedJobIds, setAppliedJobIds] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [applyingId, setApplyingId] = useState(null);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const [jobsRes, appsRes] = await Promise.all([
        candidatesApi.browseJobs(),
        candidatesApi.getMyApplications(),
      ]);
      setJobs(jobsRes.data);
      setAppliedJobIds(new Set(appsRes.data.map((a) => a.job_id)));
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleApply(jobId) {
    setApplyingId(jobId);
    try {
      await candidatesApi.applyToJob(jobId);
      showToast("Application submitted.", "success");
      setAppliedJobIds((prev) => new Set(prev).add(jobId));
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setApplyingId(null);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 pb-24">
      <h1 className="text-2xl font-display font-semibold">Browse Jobs</h1>
      <p className="text-slate text-sm mt-1 mb-8">
        Each job shows its screening mode — how you'll be evaluated matters as much as the role.
      </p>

      {loading ? (
        <LoadingSkeleton lines={5} />
      ) : jobs.length === 0 ? (
        <EmptyState title="No open jobs right now" description="Check back soon — new postings appear here as recruiters add them." />
      ) : (
        <div className="space-y-4">
          {jobs.map((job) => {
            const mode = MODE_LABELS[job.screening_mode] || MODE_LABELS.standard;
            const alreadyApplied = appliedJobIds.has(job.id);
            return (
              <div key={job.id} className="card p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="font-display font-semibold text-lg">{job.title}</h2>
                    {job.location && <p className="text-sm text-slate">{job.location}</p>}
                  </div>
                  <span
                    className={`badge shrink-0 ${
                      job.screening_mode === "bdiof" ? "badge-verified" : "badge-declared"
                    }`}
                    title={mode.hint}
                  >
                    {mode.label}
                  </span>
                </div>

                <p className="text-sm text-ink-600 mt-3 line-clamp-3">{job.description}</p>

                {job.required_skills?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {job.required_skills.map((skill) => (
                      <span key={skill} className="text-xs bg-ink-50 text-ink-600 px-2 py-0.5 rounded-sm">
                        {skill}
                      </span>
                    ))}
                  </div>
                )}

                <div className="mt-4">
                  {alreadyApplied ? (
                    <span className="text-sm text-verified font-medium">Applied ✓</span>
                  ) : (
                    <button
                      onClick={() => handleApply(job.id)}
                      disabled={applyingId === job.id}
                      className="btn-primary"
                    >
                      {applyingId === job.id ? "Applying…" : "Apply"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
