import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { recruitersApi } from "../../api/recruiters";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";
import EmptyState from "../../components/EmptyState";
import SkillBadge from "../../components/SkillBadge";

const STATUS_ACTIONS = [
  { value: "shortlisted", label: "Shortlist" },
  { value: "interview", label: "Request Interview" },
  { value: "offered", label: "Offer" },
  { value: "rejected", label: "Reject" },
];

export default function CompetencyDossier() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [rateLimitMessage, setRateLimitMessage] = useState(null);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const [jobRes, dossierRes] = await Promise.all([
        recruitersApi.getJob(jobId),
        recruitersApi.getDossier(jobId),
      ]);
      setJob(jobRes.data);
      const dossierData = dossierRes.data;
      setCandidates(Array.isArray(dossierData) ? dossierData : dossierData?.candidates || []);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setLoading(false);
    }
  }, [jobId, showToast]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleExpand(applicationId) {
    if (expandedId === applicationId) {
      setExpandedId(null);
      setDetailData(null);
      return;
    }

    setExpandedId(applicationId);
    setDetailLoading(true);
    setRateLimitMessage(null);
    try {
      const res = await recruitersApi.getCandidateDetail(jobId, applicationId);
      setDetailData(res.data);
    } catch (error) {
      if (error.response?.status === 429) {
        setRateLimitMessage(getErrorMessage(error));
      } else {
        showToast(getErrorMessage(error), "error");
      }
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleStatusUpdate(applicationId, status) {
    try {
      const res = await recruitersApi.updateApplicationStatus(jobId, applicationId, status);
      showToast(`Candidate ${status}.`, "success");
      setDetailData(res.data);
      load();
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    }
  }

  async function handleReveal(applicationId) {
    try {
      const res = await recruitersApi.revealCandidate(jobId, applicationId);
      setDetailData(res.data);
      showToast("Identity revealed.", "success");
    } catch (error) {
      showToast(getErrorMessage(error), "error");
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
      <h1 className="text-2xl font-display font-semibold">{job?.title}</h1>
      <p className="text-slate text-sm mt-1 mb-8">
        Screening mode: <span className="font-medium">{job?.screening_mode?.toUpperCase() || "STANDARD"}</span> ·
        Ranked by Evidence Score
      </p>

      {candidates.length === 0 ? (
        <EmptyState title="No applications yet" description="Candidates who apply to this job will appear here, ranked by Evidence Score." />
      ) : (
        <div className="space-y-3">
          {candidates.map((c) => (
            <div key={c.application_id || c.id} className="card overflow-hidden">
              <button
                onClick={() => handleExpand(c.application_id)}
                className="w-full flex items-center gap-4 p-4 text-left hover:bg-ink-50 transition-colors"
              >
                {c.is_anonymized ? (
                  <div className="masked-avatar">
                    <span className="text-ink-400 text-xs font-mono">?</span>
                  </div>
                ) : (
                  <div className="w-12 h-12 rounded-full bg-beacon-50 flex items-center justify-center text-ink font-display font-semibold">
                    {c.full_name?.[0] || "?"}
                  </div>
                )}

                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">
                    {c.is_anonymized ? c.pseudonym : c.full_name}
                  </p>
                  <p className="text-xs text-slate">
                    {c.experience_level} · {c.education_tier} · {c.status}
                  </p>
                </div>

                <span className="score-figure text-xl text-beacon-600 shrink-0">
                  {Math.round((c.evidence_score_breakdown?.evidence_score ?? c.evidence_score ?? 0) * 100)}
                </span>
              </button>

              {expandedId === c.application_id && (
                <div className="border-t border-ink-100 p-4 bg-ink-50/40">
                  {detailLoading ? (
                    <LoadingSkeleton lines={3} />
                  ) : rateLimitMessage ? (
                    <div className="text-sm text-gap bg-gap-50 rounded p-3">{rateLimitMessage}</div>
                  ) : detailData ? (
                    <div className="space-y-4">
                      {!detailData.is_anonymized && (
                        <div className="text-sm space-y-0.5">
                          <p><span className="text-slate">Email:</span> {detailData.email}</p>
                          {detailData.location && <p><span className="text-slate">Location:</span> {detailData.location}</p>}
                          {detailData.github_username && (
                            <p><span className="text-slate">GitHub:</span> @{detailData.github_username}</p>
                          )}
                        </div>
                      )}

                      <div className="flex flex-wrap gap-2">
                        {Object.entries(detailData.skills || {}).map(([skill, meta]) => (
                          <SkillBadge key={skill} skill={skill} tier={meta.tier} sources={meta.sources} />
                        ))}
                      </div>

                      <div className="flex flex-wrap gap-2 pt-2">
                        {STATUS_ACTIONS.map((action) => (
                          <button
                            key={action.value}
                            onClick={() => handleStatusUpdate(c.application_id, action.value)}
                            className="btn-secondary text-xs px-3 py-1.5"
                          >
                            {action.label}
                          </button>
                        ))}
                        {detailData.is_anonymized && (
                          <button
                            onClick={() => handleReveal(c.application_id)}
                            className="btn-beacon text-xs px-3 py-1.5"
                          >
                            Reveal Identity
                          </button>
                        )}
                        {!detailData.is_anonymized && detailData.user_id && (
                          <button
                            onClick={() =>
                              navigate(
                                `/recruiter/messages?with=${detailData.user_id}&job=${jobId}&label=${encodeURIComponent(detailData.full_name)}`
                              )
                            }
                            className="btn-secondary text-xs px-3 py-1.5"
                          >
                            Message
                          </button>
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}