import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { candidatesApi } from "../../api/candidates";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";
import EmptyState from "../../components/EmptyState";
import SkillBadge from "../../components/SkillBadge";

const COMPONENT_LABELS = {
  p_emb: { label: "Project–Skill Match", weight: "40%" },
  g_act: { label: "GitHub Activity", weight: "25%" },
  c_peer: { label: "Community Standing", weight: "20%" },
  l_traj: { label: "Learning Trajectory", weight: "15%" },
};

export default function CompetencyProfile() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const res = await candidatesApi.getCompetencyProfile();
      setData(res.data);
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

  const skills = Object.entries(data?.skills || {});
  const breakdown = data?.evidence_score_breakdown;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 pb-24">
      <h1 className="text-2xl font-display font-semibold">Your Competency Profile</h1>
      <p className="text-slate text-sm mt-1 mb-8">
        This is the same view a recruiter sees in your Competency Dossier — minus your identity,
        if the job you're applying to uses anonymised (BDIOF) screening.
      </p>

      <section className="card p-6">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display font-semibold text-lg">Evidence Score</h2>
          <span className="score-figure text-3xl text-beacon-600">
            {breakdown ? Math.round(breakdown.evidence_score * 100) : 0}
            <span className="text-sm text-slate">/100</span>
          </span>
        </div>

        <div className="mt-4 space-y-3">
          {breakdown &&
            Object.entries(COMPONENT_LABELS).map(([key, meta]) => (
              <div key={key}>
                <div className="flex justify-between text-xs text-slate mb-1">
                  <span>{meta.label} ({meta.weight})</span>
                  <span className="font-mono">{Math.round((breakdown[key] || 0) * 100)}%</span>
                </div>
                <div className="h-1.5 bg-ink-50 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-ink-400"
                    style={{ width: `${(breakdown[key] || 0) * 100}%` }}
                  />
                </div>
              </div>
            ))}
        </div>
      </section>

      <section className="card p-6 mt-6">
        <h2 className="font-display font-semibold text-lg mb-1">Verified Skills</h2>
        <p className="text-xs text-slate mb-4">
          Badge tier reflects how many independent sources corroborate a skill — not which
          specific sources. Two sources (e.g. GitHub + a community certification) reach
          "Confirmed" with no CV at all.
        </p>

        {skills.length === 0 ? (
          <EmptyState
            title="No skills detected yet"
            description="Build your profile with a CV, GitHub link, or community evidence to see your skills appear here."
            action={<Link to="/candidate/profile" className="btn-primary">Build your profile</Link>}
          />
        ) : (
          <div className="flex flex-wrap gap-2">
            {skills.map(([skill, meta]) => (
              <SkillBadge key={skill} skill={skill} tier={meta.tier} sources={meta.sources} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
