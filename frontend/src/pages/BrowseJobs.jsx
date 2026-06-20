import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import api from "../services/api";

export default function BrowseJobs() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [scores, setScores] = useState({});
  const [gaps, setGaps] = useState({});
  const [loading, setLoading] = useState(true);
  const [applied, setApplied] = useState({});
  const userId = localStorage.getItem("user_id") || 1;

  useEffect(() => {
    api
      .get("/jobs/")
      .then((res) => {
        setJobs(res.data);
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));

    api
      .get(`/candidates/recommended-jobs/${userId}`)
      .then((res) => {
        const scoreMap = {};
        const gapMap = {};
        res.data.recommendations?.forEach((job) => {
          scoreMap[job.job_id] = job.skill_score;
          gapMap[job.job_id] = job.missing_skills;
        });
        setScores(scoreMap);
        setGaps(gapMap);
      })
      .catch((err) => console.error(err));
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold text-gray-800 mb-1">
          Browse Jobs 🔍
        </h2>
        <p className="text-gray-500 mb-8">
          Your profile is automatically matched against these roles using the
          BDIOF Skill-Score engine.
        </p>

        <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-3 mb-8 flex items-center gap-3">
          <span className="text-blue-600 text-xl">🛡️</span>
          <p className="text-sm text-blue-700">
            <strong>BDIOF Active</strong> — Recruiters will see your skills and
            competencies first. Your name and location are hidden until they
            request an interview.
          </p>
        </div>

        {loading && <p className="text-gray-400">Loading jobs...</p>}

        {!loading && jobs.length === 0 && (
          <div className="bg-white rounded-2xl p-8 text-center border border-gray-100">
            <p className="text-gray-400">
              No jobs available yet. Check back soon!
            </p>
          </div>
        )}

        <div className="space-y-4">
          {jobs.map((job) => {
            const score = scores[job.id];
            const missing = gaps[job.id] || [];
            return (
              <div
                key={job.id}
                className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6"
              >
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="text-lg font-bold text-gray-800">
                        {job.title}
                      </h3>
                      {score !== undefined && (
                        <span
                          className={`text-xs font-bold px-2 py-1 rounded-full ${
                            score >= 70
                              ? "bg-green-100 text-green-700"
                              : score >= 40
                                ? "bg-amber-100 text-amber-700"
                                : "bg-red-100 text-red-700"
                          }`}
                        >
                          {score}% match
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      📍 {job.location || "Remote"}
                    </p>
                    <p className="text-sm text-gray-600 mt-2">
                      {job.description}
                    </p>
                    <div className="flex flex-wrap gap-2 mt-3">
                      {job.required_skills.split(",").map((skill, i) => (
                        <span
                          key={i}
                          className="bg-blue-50 text-blue-600 text-xs px-2 py-1 rounded-full"
                        >
                          {skill.trim()}
                        </span>
                      ))}
                    </div>
                    {missing.length > 0 && (
                      <div className="mt-3">
                        <p className="text-xs text-amber-600 font-medium mb-1">
                          ⚡ Skills you're missing:
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {missing.map((skill, i) => (
                            <span
                              key={i}
                              className="bg-amber-50 text-amber-700 text-xs px-2 py-0.5 rounded-full"
                            >
                              {skill}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="shrink-0">
                    {applied[job.id] ? (
                      <span className="bg-green-100 text-green-700 text-sm px-4 py-2 rounded-lg font-medium">
                        ✓ Applied
                      </span>
                    ) : (
                      <button
                        onClick={() =>
                          setApplied((prev) => ({ ...prev, [job.id]: true }))
                        }
                        className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded-lg transition"
                      >
                        Apply Now
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
