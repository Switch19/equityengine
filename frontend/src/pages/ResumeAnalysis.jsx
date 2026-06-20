import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import api from "../services/api";
import SkillBadge from "../components/SkillBadge";
import SuggestionCard from "../components/SuggestionCard";
import Navbar from "../components/Navbar";
export default function ResumeAnalysis() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [decisions, setDecisions] = useState({});
  const [githubUrl, setGithubUrl] = useState("");
  const [githubData, setGithubData] = useState(null);
  const [githubLoading, setGithubLoading] = useState(false);
  const [generatingCV, setGeneratingCV] = useState(false);
  const userId = localStorage.getItem("user_id") || 1;

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await axios.post(
        `/api/candidates/upload-resume/${userId}`,
        formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      setAnalysis(res.data.analysis);
      setDecisions({});
    } catch (err) {
      setError("Failed to analyze resume. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleGithub = async () => {
    if (!githubUrl) return;
    setGithubLoading(true);
    try {
      const res = await api.post(
        `/candidates/github/${userId}?github_url=${encodeURIComponent(githubUrl)}`,
      );
      setGithubData(res.data.github_analysis);
    } catch (err) {
      console.error(err);
    } finally {
      setGithubLoading(false);
    }
  };
  const handleGenerateCV = async () => {
    setGeneratingCV(true);
    try {
      const approvedList = analysis.regional_term_suggestions.filter(
        (_, i) => decisions[i] === "approved",
      );

      const response = await axios.post(
        `/api/candidates/generate-optimized-cv/${userId}`,
        approvedList,
        { responseType: "blob" },
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "EquityEngine_Optimized_CV.pdf");
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("CV generation failed:", err);
      alert("Failed to generate CV. Please try again.");
    } finally {
      setGeneratingCV(false);
    }
  };
  const handleDecision = (index, decision) => {
    setDecisions((prev) => ({ ...prev, [index]: decision }));
  };

  const approvedCount = Object.values(decisions).filter(
    (d) => d === "approved",
  ).length;
  const rejectedCount = Object.values(decisions).filter(
    (d) => d === "rejected",
  ).length;
  const totalSuggestions = analysis?.suggestion_count || 0;
  const pendingCount = totalSuggestions - approvedCount - rejectedCount;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold text-gray-800 mb-1">
          Identity Optimizer
        </h2>
        <p className="text-gray-500 mb-8">
          Upload your CV and link your GitHub — our BDIOF engine will analyze
          and suggest global visibility improvements.
        </p>

        {!analysis && (
          <div className="space-y-4">
            {/* CV Upload */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
              <div className="text-5xl mb-4">📄</div>
              <p className="text-gray-600 mb-4">Upload your CV (PDF or DOCX)</p>
              <input
                type="file"
                accept=".pdf,.docx"
                onChange={(e) => setFile(e.target.files[0])}
                className="block mx-auto mb-4 text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-600 file:font-medium hover:file:bg-blue-100"
              />
              {file && (
                <p className="text-sm text-gray-500 mb-4">
                  Selected:{" "}
                  <span className="font-medium text-gray-700">{file.name}</span>
                </p>
              )}
              {error && <p className="text-red-500 text-sm mb-4">{error}</p>}
              <button
                onClick={handleUpload}
                disabled={!file || loading}
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-8 py-3 rounded-lg transition disabled:opacity-50"
              >
                {loading ? "🔍 Analyzing..." : "Analyze My CV"}
              </button>
            </div>

            {/* GitHub Integration */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
              <div className="text-center mb-4">
                <div className="text-5xl mb-2">🐙</div>
                <p className="text-gray-600 font-medium">
                  Link Your GitHub Profile
                </p>
                <p className="text-sm text-gray-400 mt-1">
                  We'll analyze your repos and merge languages with your CV
                  skills
                </p>
              </div>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={githubUrl}
                  onChange={(e) => setGithubUrl(e.target.value)}
                  placeholder="https://github.com/yourusername"
                  className="flex-1 border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
                <button
                  onClick={handleGithub}
                  disabled={!githubUrl || githubLoading}
                  className="bg-gray-800 hover:bg-gray-900 text-white px-6 py-3 rounded-lg transition disabled:opacity-50 text-sm font-medium"
                >
                  {githubLoading ? "Analyzing..." : "Analyze"}
                </button>
              </div>

              {githubData && (
                <div className="mt-4 bg-gray-50 rounded-xl p-4">
                  <p className="font-semibold text-gray-800">
                    @{githubData.username}
                  </p>
                  <p className="text-sm text-gray-500">
                    {githubData.public_repos} repos · {githubData.followers}{" "}
                    followers
                  </p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {githubData.top_languages.map((lang, i) => (
                      <span
                        key={i}
                        className="bg-gray-800 text-white text-xs px-2 py-1 rounded-full"
                      >
                        {lang}
                      </span>
                    ))}
                  </div>
                  <p className="text-xs text-green-600 mt-2">
                    ✅ GitHub languages merged with your CV skills
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Analysis Results */}
        {analysis && (
          <div className="space-y-6">
            {/* Visibility Score */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">
                🌍 Global Visibility Score
              </h3>
              <div className="flex items-center gap-4">
                <div className="flex-1 bg-gray-200 rounded-full h-4">
                  <div
                    className={`h-4 rounded-full transition-all ${
                      analysis.visibility_score >= 70
                        ? "bg-green-500"
                        : analysis.visibility_score >= 40
                          ? "bg-amber-500"
                          : "bg-red-500"
                    }`}
                    style={{ width: `${analysis.visibility_score}%` }}
                  />
                </div>
                <span
                  className={`text-2xl font-bold ${
                    analysis.visibility_score >= 70
                      ? "text-green-600"
                      : analysis.visibility_score >= 40
                        ? "text-amber-600"
                        : "text-red-600"
                  }`}
                >
                  {analysis.visibility_score}%
                </span>
              </div>
              <p className="text-sm text-gray-500 mt-2">
                {analysis.visibility_score < 70
                  ? "⚠️ Your CV may be penalized by global ATS systems. Review the suggestions below."
                  : "✅ Your CV has good global visibility!"}
              </p>
            </div>

            {/* Skills Detected */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
              <h3 className="text-lg font-bold text-gray-800 mb-1">
                ⚡ Skills Detected
                <span className="ml-2 text-sm font-normal text-blue-600">
                  ({analysis.skill_count} found)
                </span>
              </h3>
              <p className="text-sm text-gray-500 mb-4">
                These skills were extracted from your CV and will be used for
                Skill-Score matching.
              </p>
              <div className="flex flex-wrap">
                {analysis.skills_detected.map((skill, i) => (
                  <SkillBadge key={i} skill={skill} />
                ))}
              </div>
            </div>

            {/* Regional Term Suggestions */}
            {analysis.suggestion_count > 0 && (
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <h3 className="text-lg font-bold text-gray-800 mb-1">
                  🔄 BDIOF Optimization Suggestions
                  <span className="ml-2 text-sm font-normal text-amber-600">
                    ({pendingCount} pending review)
                  </span>
                </h3>
                <p className="text-sm text-gray-500 mb-4">
                  Review each suggestion and approve or reject. Only approved
                  changes will be applied to your optimized CV.
                </p>
                <div className="flex gap-4 mb-4 text-sm">
                  <span className="text-green-600 font-medium">
                    ✓ {approvedCount} Approved
                  </span>
                  <span className="text-red-500 font-medium">
                    ✗ {rejectedCount} Rejected
                  </span>
                  <span className="text-amber-600 font-medium">
                    ⏳ {pendingCount} Pending
                  </span>
                </div>
                {analysis.regional_term_suggestions.map((suggestion, i) => (
                  <SuggestionCard
                    key={i}
                    suggestion={suggestion}
                    approved={decisions[i] === "approved"}
                    rejected={decisions[i] === "rejected"}
                    onApprove={() => handleDecision(i, "approved")}
                    onReject={() => handleDecision(i, "rejected")}
                  />
                ))}
                {pendingCount === 0 && totalSuggestions > 0 && (
                  <div className="mt-4 p-4 bg-blue-50 rounded-xl text-center">
                    <p className="text-blue-700 font-medium mb-3">
                      All suggestions reviewed! Ready to generate your optimized
                      CV.
                    </p>
                    <p className="text-sm text-blue-500 mb-4">
                      ✓ {approvedCount} approved · ✗ {rejectedCount} rejected
                    </p>
                    <button
                      onClick={handleGenerateCV}
                      disabled={generatingCV || approvedCount === 0}
                      className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-2 rounded-lg transition disabled:opacity-50"
                    >
                      {generatingCV
                        ? "⏳ Generating..."
                        : "📄 Download Optimized CV"}
                    </button>
                    {approvedCount === 0 && (
                      <p className="text-xs text-gray-400 mt-2">
                        Approve at least one suggestion to generate your CV.
                      </p>
                    )}
                  </div>
                )}{" "}
              </div>
            )}

            <div className="text-center">
              <button
                onClick={() => {
                  setAnalysis(null);
                  setFile(null);
                }}
                className="text-sm text-gray-500 hover:text-blue-600 underline transition"
              >
                Upload a different CV
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
