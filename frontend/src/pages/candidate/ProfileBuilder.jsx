import { useState, useEffect, useCallback } from "react";
import { candidatesApi } from "../../api/candidates";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";

export default function ProfileBuilder() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const loadProfile = useCallback(async () => {
    try {
      const res = await candidatesApi.getProfile();
      setProfile(res.data);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-10">
        <LoadingSkeleton lines={2} className="mb-8" />
        <LoadingSkeleton lines={4} />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 pb-24">
      <h1 className="text-2xl font-display font-semibold">Build your Competency Profile</h1>
      <p className="text-slate text-sm mt-1 mb-8">
        Supply evidence from any combination of the three sources below — none are mandatory.
        Each additional source strengthens your skill verification badges.
      </p>

      <ProfileCompletenessBar percent={profile?.profile_completeness ?? 0} />

      <div className="space-y-6 mt-8">
        <CVSection profile={profile} onUpdated={loadProfile} />
        <GitHubSection profile={profile} onUpdated={loadProfile} />
        <CommunitySection profile={profile} onUpdated={loadProfile} />
      </div>
    </div>
  );
}

function ProfileCompletenessBar({ percent }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="font-medium text-ink">Profile completeness</span>
        <span className="score-figure text-beacon-600">{Math.round(percent)}%</span>
      </div>
      <div className="h-2 bg-ink-50 rounded-full overflow-hidden">
        <div
          className="h-full bg-beacon transition-all duration-500"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------
// Pipeline 1: Formal (CV)
// ---------------------------------------------------------------------

function CVSection({ profile, onUpdated }) {
  const [uploading, setUploading] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const { showToast } = useToast();

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    try {
      const res = await candidatesApi.uploadCV(file);
      setLastResult(res.data);
      showToast("CV processed successfully.", "success");
      onUpdated();
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  const hasCV = !!profile?.cv_skills?.length;

  return (
    <section className="card p-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-display font-semibold text-lg">1. Formal (CV)</h2>
          <p className="text-sm text-slate mt-1">
            Upload a PDF, DOCX, or TXT CV. We extract skills, projects, experience level, and
            detect regional institutions/programmes a conventional ATS would miss.
          </p>
        </div>
        {hasCV && <span className="badge badge-verified shrink-0">Linked</span>}
      </div>

      <label className="btn-secondary inline-block mt-4 cursor-pointer">
        {uploading ? "Processing…" : hasCV ? "Re-upload CV" : "Upload CV"}
        <input
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={handleFileChange}
          disabled={uploading}
        />
      </label>

      {profile?.ats_score != null && (
        <p className="text-xs text-slate mt-3">
          Conventional ATS compatibility score:{" "}
          <span className="score-figure">{Math.round(profile.ats_score)}/100</span>
          {" — "}this measures document formatting, not competency. Your Evidence Score
          (below) is what actually matters for recruiter ranking.
        </p>
      )}

      {lastResult && (
        <div className="mt-4 pt-4 border-t border-ink-100 text-sm space-y-2">
          <p className="font-medium">Extracted from your CV — review before continuing:</p>
          <p><span className="text-slate">Skills:</span> {lastResult.cv_skills.join(", ") || "none detected"}</p>
          <p><span className="text-slate">Experience level:</span> {lastResult.experience_level}</p>
          <p><span className="text-slate">Education tier:</span> {lastResult.education_tier}</p>
          {lastResult.ats_suggestions?.length > 0 && (
            <div>
              <p className="text-slate">Suggestions to improve ATS compatibility:</p>
              <ul className="list-disc list-inside text-slate">
                {lastResult.ats_suggestions.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------
// Pipeline 2: Informal (GitHub)
// ---------------------------------------------------------------------

function GitHubSection({ profile, onUpdated }) {
  const [username, setUsername] = useState("");
  const [linking, setLinking] = useState(false);
  const { showToast } = useToast();

  async function handleLink(e) {
    e.preventDefault();
    if (!username.trim()) return;
    setLinking(true);
    try {
      await candidatesApi.linkGithub(username.trim());
      showToast("GitHub account linked and analysed.", "success");
      setUsername("");
      onUpdated();
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setLinking(false);
    }
  }

  const isLinked = !!profile?.github_username;

  return (
    <section className="card p-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-display font-semibold text-lg">2. Informal (GitHub)</h2>
          <p className="text-sm text-slate mt-1">
            We analyse your public repositories, languages, and activity trend. Forked repos are
            excluded from scoring — only your own original work counts.
          </p>
        </div>
        {isLinked && <span className="badge badge-verified shrink-0">Linked</span>}
      </div>

      {isLinked ? (
        <p className="text-sm mt-4">
          Linked as <span className="font-mono">@{profile.github_username}</span>.
        </p>
      ) : (
        <form onSubmit={handleLink} className="mt-4 flex gap-2">
          <input
            type="text"
            placeholder="your-github-username"
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <button type="submit" disabled={linking} className="btn-secondary shrink-0">
            {linking ? "Analysing…" : "Link"}
          </button>
        </form>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------
// Pipeline 3: Community
// ---------------------------------------------------------------------

function CommunitySection({ profile, onUpdated }) {
  const [certName, setCertName] = useState("");
  const [certIssuer, setCertIssuer] = useState("");
  const [soId, setSoId] = useState("");
  const [devtoUsername, setDevtoUsername] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { showToast } = useToast();

  async function handleAddCert(e) {
    e.preventDefault();
    if (!certName.trim()) return;
    setSubmitting(true);
    try {
      await candidatesApi.addCertification({ name: certName.trim(), issuer: certIssuer.trim() });
      showToast("Certification added.", "success");
      setCertName("");
      setCertIssuer("");
      onUpdated();
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLinkSO(e) {
    e.preventDefault();
    if (!soId.trim()) return;
    setSubmitting(true);
    try {
      await candidatesApi.linkStackOverflow(soId.trim());
      showToast("Stack Overflow linked.", "success");
      setSoId("");
      onUpdated();
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLinkDevTo(e) {
    e.preventDefault();
    if (!devtoUsername.trim()) return;
    setSubmitting(true);
    try {
      await candidatesApi.linkDevTo(devtoUsername.trim());
      showToast("Dev.to linked.", "success");
      setDevtoUsername("");
      onUpdated();
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setSubmitting(false);
    }
  }

  const certs = profile?.certifications || [];

  return (
    <section className="card p-6">
      <h2 className="font-display font-semibold text-lg">3. Community</h2>
      <p className="text-sm text-slate mt-1">
        Certifications, Stack Overflow reputation, Dev.to articles, and peer endorsements.
        Community fellowships (Andela, ALX, Genesys Hub) carry the same weight as formal cloud
        certifications (AWS, Google) here — by design.
      </p>

      {certs.length > 0 && (
        <ul className="mt-4 space-y-1 text-sm">
          {certs.map((c, i) => (
            <li key={i} className="flex items-center gap-2">
              <span className={`badge ${c.tier === 1 ? "badge-verified" : c.tier === 2 ? "badge-confirmed" : "badge-declared"}`}>
                Tier {c.tier}
              </span>
              {c.name} {c.issuer && <span className="text-slate">— {c.issuer}</span>}
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleAddCert} className="mt-4 flex gap-2 flex-wrap">
        <input
          type="text"
          placeholder="Certification name"
          className="input flex-1 min-w-[160px]"
          value={certName}
          onChange={(e) => setCertName(e.target.value)}
        />
        <input
          type="text"
          placeholder="Issuer (optional)"
          className="input flex-1 min-w-[140px]"
          value={certIssuer}
          onChange={(e) => setCertIssuer(e.target.value)}
        />
        <button type="submit" disabled={submitting} className="btn-secondary shrink-0">Add</button>
      </form>

      <div className="grid sm:grid-cols-2 gap-3 mt-4 pt-4 border-t border-ink-100">
        <form onSubmit={handleLinkSO} className="flex gap-2">
          <input
            type="text"
            placeholder="Stack Overflow numeric ID"
            className="input"
            value={soId}
            onChange={(e) => setSoId(e.target.value)}
          />
          <button type="submit" disabled={submitting} className="btn-secondary shrink-0">Link</button>
        </form>
        <form onSubmit={handleLinkDevTo} className="flex gap-2">
          <input
            type="text"
            placeholder="Dev.to username"
            className="input"
            value={devtoUsername}
            onChange={(e) => setDevtoUsername(e.target.value)}
          />
          <button type="submit" disabled={submitting} className="btn-secondary shrink-0">Link</button>
        </form>
      </div>
      <p className="text-xs text-slate mt-2">
        Your Stack Overflow ID is the number in your profile URL (stackoverflow.com/users/
        <span className="font-mono">NUMBER</span>/your-name), not your display name.
      </p>
    </section>
  );
}
