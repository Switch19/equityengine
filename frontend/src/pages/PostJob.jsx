import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import Navbar from "../components/Navbar";

export default function PostJob() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    title: "",
    description: "",
    required_skills: "",
    location: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.post("/jobs/?recruiter_id=1", form);
      navigate("/recruiter/jobs");
    } catch (err) {
      setError("Failed to post job. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-2xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold text-gray-800 mb-1">
          Post a New Job
        </h2>
        <p className="text-gray-500 mb-8">
          Candidates will be ranked by Skill-Score and shown anonymously until
          you request an interview.
        </p>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Job Title
              </label>
              <input
                type="text"
                name="title"
                required
                value={form.title}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g. Senior Python Developer"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Job Description
              </label>
              <textarea
                name="description"
                required
                value={form.description}
                onChange={handleChange}
                rows={4}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Describe the role and responsibilities..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Required Skills
                <span className="text-gray-400 font-normal ml-1">
                  (comma separated)
                </span>
              </label>
              <input
                type="text"
                name="required_skills"
                required
                value={form.required_skills}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g. python, react, postgresql, docker"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Location
              </label>
              <input
                type="text"
                name="location"
                value={form.location}
                onChange={handleChange}
                className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g. Remote, London, New York"
              />
            </div>

            {error && (
              <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition disabled:opacity-50"
            >
              {loading ? "Posting..." : "Post Job"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
