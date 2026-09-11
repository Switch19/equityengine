import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { candidatesApi } from "../../api/candidates";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage, getBlobErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";
import EmptyState from "../../components/EmptyState";
import SkillBadge from "../../components/SkillBadge";

const COMPONENT_LABELS = {
  p_emb: { label: "Project–Skill Match", weight: "40%" },
  g_act: { label: "GitHub Activity", weight: "25%" },
  c_peer: { label: "Community Standing", weight: "20%" },
  l_traj: { label: "Learning Trajectory", weight: "15%" },
};

/**
 * Pulls the PDF filename out of the response's Content-Disposition
 * header so the saved file matches what the server named it
 * (<Full_Name>_CV.pdf), instead of hardcoding a guess at the name on
 * the client. Falls back to a sensible default when the header is
 * absent — which is what happens if CORS ever stops exposing it.
 */
function filenameFromResponse(response, fallback) {
  const disposition = response.headers?.["content-disposition"];
  const match = disposition && /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  return match ? decodeURIComponent(match[1].trim()) : fallback;
}

export default function CompetencyProfile() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
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

  async function handleDownloadProfile() {
    setDownloading(true);
    let objectUrl;
    try {
      const res = await candidatesApi.downloadOptimizedProfile();

      // The explicit MIME type matters: a Blob built without it gets
      // type "" and some browsers then refuse to treat the download as
      // a PDF (opening a blank tab or saving an extensionless file)
      // rather than saving it cleanly.
      const blob = new Blob([res.data], { type: "application/pdf" });
      objectUrl = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = objectUrl;
      link.setAttribute("download", filenameFromResponse(res, "EquityEngine_Profile.pdf"));
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      showToast(await getBlobErrorMessage(error), "error");
    } finally {
      // Revoking releases the blob; without this the PDF stays held in
      // memory for the lifetime of the tab, once per download.
      if (objectUrl) window.URL.revokeObjectURL(objectUrl);
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

  const skills = Object.entries(data?.skills || {});
  const breakdown = data?.evidence_score_breakdown;

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 pb-24">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-semibold">Your Competency Profile</h1>
          <p className="text-slate text-sm mt-1">
            This is the same view a recruiter sees in your Competency Dossier — minus your identity,
            if the job you're applying to uses anonymised (BDIOF) screening.
          </p>
        </div>
        <button
          onClick={handleDownloadProfile}
          disabled={downloading}
          className="btn-secondary shrink-0"
        >
          {downloading ? "Preparing…" : "Download Profile (PDF)"}
        </button>
      </div>

      <p className="text-xs text-slate mt-3 mb-8">
        The PDF is generated from all three evidence pipelines combined — CV, GitHub, and community
        — so it works even if you never uploaded a formal CV.
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
