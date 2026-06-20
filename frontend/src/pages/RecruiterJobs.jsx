import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import Navbar from "../components/Navbar";
export default function RecruiterJobs() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/jobs/")
      .then((res) => setJobs(res.data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold text-gray-800 mb-1">
          Your Job Postings
        </h2>
        <p className="text-gray-500 mb-8">
          Click a job to view anonymized candidate rankings.
        </p>

        {loading && <p className="text-gray-400">Loading jobs...</p>}

        {!loading && jobs.length === 0 && (
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
            <p className="text-gray-400 text-lg mb-4">No jobs posted yet.</p>
            <button
              onClick={() => navigate("/recruiter/post-job")}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition"
            >
              Post Your First Job
            </button>
          </div>
        )}

        <div className="space-y-4">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:border-blue-300 transition cursor-pointer"
              onClick={() => navigate(`/recruiter/jobs/${job.id}/candidates`)}
            >
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-lg font-bold text-gray-800">
                    {job.title}
                  </h3>
                  <p className="text-sm text-gray-500 mt-1">
                    {job.location || "Remote"}
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
                </div>
                <span
                  className={`text-xs px-3 py-1 rounded-full font-medium ${
                    job.is_active
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-500"
                  }`}
                >
                  {job.is_active ? "Active" : "Closed"}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
