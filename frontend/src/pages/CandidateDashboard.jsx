import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import Navbar from "../components/Navbar";
import RecommendedJobs from "../components/RecommendedJobs";
import SkeletonCard, { SkeletonStat } from "../components/SkeletonCard";
export default function CandidateDashboard() {
  const navigate = useNavigate();
  const [intelligence, setIntelligence] = useState(null);
  const [loading, setLoading] = useState(true);

  const userId = localStorage.getItem("user_id") || 1;

  useEffect(() => {
    api
      .get(`/candidates/intelligence/${userId}`)
      .then((res) => setIntelligence(res.data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [userId]);

  const handleLogout = () => {
    localStorage.clear();
    navigate("/login");
  };

  const getTypeStyle = (type) => {
    switch (type) {
      case "warning":
        return "bg-amber-50 border-amber-300 text-amber-800";
      case "tip":
        return "bg-blue-50 border-blue-300 text-blue-800";
      case "success":
        return "bg-green-50 border-green-300 text-green-800";
      default:
        return "bg-gray-50 border-gray-300 text-gray-700";
    }
  };

  const getTypeIcon = (type) => {
    switch (type) {
      case "warning":
        return "⚠️";
      case "tip":
        return "💡";
      case "success":
        return "🎉";
      default:
        return "ℹ️";
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navbar */}
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 py-12">
        <h2 className="text-2xl font-bold text-gray-800 mb-1">
          Welcome back 👋
        </h2>
        <p className="text-gray-500 mb-8">
          Your BDIOF-powered intelligence dashboard
        </p>
        {loading && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonStat key={i} />
              ))}
            </div>
            <SkeletonCard lines={4} />
          </div>
        )}{" "}
        {intelligence && !intelligence.has_profile && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
            <p className="text-gray-400 text-lg mb-2">📄 No CV uploaded yet</p>
            <p className="text-gray-400 text-sm mb-6">{intelligence.message}</p>
            <button
              onClick={() => navigate("/candidate/resume")}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition"
            >
              Upload My CV
            </button>
          </div>
        )}
        {intelligence && intelligence.has_profile && (
          <div className="space-y-6">
            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <h3 className="text-sm font-medium text-gray-500">
                  Profile Views
                </h3>
                <p className="text-3xl font-bold text-blue-600 mt-2">
                  {intelligence.stats.profile_views}
                </p>
                <p className="text-xs text-gray-400 mt-1">By recruiters</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <h3 className="text-sm font-medium text-gray-500">
                  Interview Requests
                </h3>
                <p className="text-3xl font-bold text-green-600 mt-2">
                  {intelligence.stats.interview_requests}
                </p>
                <p className="text-xs text-gray-400 mt-1">Identity reveals</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <h3 className="text-sm font-medium text-gray-500">
                  Conversion Rate
                </h3>
                <p className="text-3xl font-bold text-purple-600 mt-2">
                  {intelligence.stats.conversion_rate}%
                </p>
                <p className="text-xs text-gray-400 mt-1">Views → interviews</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <h3 className="text-sm font-medium text-gray-500">
                  Skill Score
                </h3>
                <p className="text-3xl font-bold text-blue-600 mt-2">
                  {intelligence.stats.skill_score}%
                </p>
                <p className="text-xs text-gray-400 mt-1">Job match rate</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <h3 className="text-sm font-medium text-gray-500">
                  Visibility Score
                </h3>
                <p
                  className={`text-3xl font-bold mt-2 ${
                    intelligence.stats.visibility_score >= 70
                      ? "text-green-600"
                      : intelligence.stats.visibility_score >= 40
                        ? "text-amber-600"
                        : "text-red-500"
                  }`}
                >
                  {intelligence.stats.visibility_score}%
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  Global ATS visibility
                </p>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <h3 className="text-sm font-medium text-gray-500">
                  Skills Detected
                </h3>
                <p className="text-3xl font-bold text-indigo-600 mt-2">
                  {intelligence.stats.skills_count}
                </p>
                <p className="text-xs text-gray-400 mt-1">From your CV</p>
              </div>
            </div>

            {/* Intelligence Feed */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
              <h3 className="text-lg font-bold text-gray-800 mb-1">
                🧠 BDIOF Intelligence Feed
              </h3>
              <p className="text-sm text-gray-500 mb-4">
                Personalized recommendations based on real recruiter interaction
                data.
              </p>
              <div className="space-y-3">
                {intelligence.recommendations.map((rec, i) => (
                  <div
                    key={i}
                    className={`border rounded-xl px-4 py-3 text-sm ${getTypeStyle(rec.type)}`}
                  >
                    {getTypeIcon(rec.type)} {rec.message}
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100 text-center">
                <p className="text-gray-500 mb-3">
                  Update or re-analyze your CV
                </p>
                <button
                  onClick={() => navigate("/candidate/resume")}
                  className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 transition"
                >
                  📄 Identity Optimizer
                </button>
              </div>
              <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100 text-center">
                <p className="text-gray-500 mb-3">
                  Browse available job openings
                </p>
                <button
                  onClick={() => navigate("/candidate/jobs")}
                  className="bg-green-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-green-700 transition"
                >
                  🔍 Browse Jobs
                </button>
                {/* Job Recommendations */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                  <h3 className="text-lg font-bold text-gray-800 mb-1">
                    🎯 Recommended Jobs
                  </h3>
                  <p className="text-sm text-gray-500 mb-4">
                    Top matches based on your skill profile — updated
                    automatically.
                  </p>
                  <RecommendedJobs userId={userId} />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
