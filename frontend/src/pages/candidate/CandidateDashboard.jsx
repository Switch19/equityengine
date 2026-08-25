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

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
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

function StatCard({ label, value }) {
  return (
    <div className="card p-4">
      <p className="text-xs text-slate">{label}</p>
      <p className="score-figure text-2xl mt-1">{value}</p>
    </div>
  );
}
