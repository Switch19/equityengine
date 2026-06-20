import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import Navbar from "../components/Navbar";

export default function AuditDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/recruiters/audit/summary")
      .then((res) => setData(res.data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  const getGapColor = (gap) => {
    if (gap >= 80) return "text-green-600";
    if (gap >= 50) return "text-amber-600";
    return "text-red-500";
  };

  const getGapBg = (gap) => {
    if (gap >= 80) return "bg-green-100";
    if (gap >= 50) return "bg-amber-100";
    return "bg-red-100";
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold text-gray-800 mb-1">
          Bias Audit Engine 📊
        </h2>
        <p className="text-gray-500 mb-8">
          BDIOF Vector 3 — Real-time transparency report on recruiter
          interaction patterns and the Visibility Gap metric.
        </p>

        {loading && <p className="text-gray-400">Loading audit data...</p>}

        {data && (
          <div className="space-y-6">
            {/* Visibility Gap Hero */}
            <div
              className={`rounded-2xl p-6 ${getGapBg(data.summary.visibility_gap)}`}
            >
              <h3 className="text-sm font-semibold text-gray-600 uppercase mb-2">
                Visibility Gap Metric
              </h3>
              <div className="flex items-end gap-4">
                <p
                  className={`text-6xl font-bold ${getGapColor(data.summary.visibility_gap)}`}
                >
                  {data.summary.visibility_gap}%
                </p>
                <p className="text-gray-600 pb-2 max-w-sm">{data.insight}</p>
              </div>
              <div className="mt-4 bg-white bg-opacity-60 rounded-xl p-3">
                <p className="text-xs text-gray-500">
                  The Visibility Gap measures the percentage of candidates
                  evaluated purely on skills before identity was revealed.
                  Higher = fairer hiring process.
                </p>
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <h3 className="text-sm font-medium text-gray-500">
                  Anonymous Views
                </h3>
                <p className="text-4xl font-bold text-blue-600 mt-2">
                  {data.summary.total_anonymized_views}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  Candidates viewed without identity
                </p>
              </div>
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <h3 className="text-sm font-medium text-gray-500">
                  Identity Reveals
                </h3>
                <p className="text-4xl font-bold text-purple-600 mt-2">
                  {data.summary.total_identity_reveals}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  Interview requests made
                </p>
              </div>
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <h3 className="text-sm font-medium text-gray-500">
                  Conversion Rate
                </h3>
                <p className="text-4xl font-bold text-green-600 mt-2">
                  {data.summary.overall_conversion_rate}%
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  Views that led to interview requests
                </p>
              </div>
            </div>

            {/* Job Breakdown */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">
                Per Job Breakdown
              </h3>
              {data.job_breakdown.length === 0 && (
                <p className="text-gray-400 text-sm">No job data yet.</p>
              )}
              <div className="space-y-4">
                {data.job_breakdown.map((job, i) => (
                  <div
                    key={i}
                    className="border border-gray-100 rounded-xl p-4"
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <p className="font-semibold text-gray-800">
                          {job.job_title}
                        </p>
                        <p className="text-xs text-gray-400">
                          Job ID: {job.job_id}
                        </p>
                      </div>
                      <span className="bg-blue-50 text-blue-600 text-xs px-3 py-1 rounded-full font-medium">
                        {job.conversion_rate}% conversion
                      </span>
                    </div>
                    <div className="flex gap-6 text-sm">
                      <div>
                        <p className="text-gray-500">Anonymous Views</p>
                        <p className="font-bold text-gray-800">
                          {job.anonymized_views}
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-500">Reveals</p>
                        <p className="font-bold text-purple-600">
                          {job.identity_reveals}
                        </p>
                      </div>
                    </div>
                    <div className="mt-3 bg-gray-100 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full transition-all"
                        style={{ width: `${job.conversion_rate}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Academic Note */}
            <div className="bg-gray-800 rounded-2xl p-6 text-white">
              <h3 className="font-bold mb-2">
                📝 For Your Results & Discussion Chapter
              </h3>
              <p className="text-gray-300 text-sm leading-relaxed">
                The Visibility Gap metric of{" "}
                <strong className="text-white">
                  {data.summary.visibility_gap}%
                </strong>{" "}
                indicates that {data.summary.total_anonymized_views} recruiter
                interactions occurred under anonymized conditions before
                identity was revealed. This data provides empirical evidence
                that the BDIOF framework successfully enforces skills-first
                evaluation in {data.summary.overall_conversion_rate}% of cases
                where identity was ultimately revealed only after a deliberate
                interview commitment was made.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
