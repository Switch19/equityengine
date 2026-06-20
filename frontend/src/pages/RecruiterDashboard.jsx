import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";

export default function RecruiterDashboard() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 py-12">
        <h2 className="text-2xl font-bold text-gray-800 mb-2">
          Recruiter Portal 🎯
        </h2>
        <p className="text-gray-500 mb-8">
          Bias-neutral candidate screening powered by BDIOF
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <h3 className="text-sm font-medium text-gray-500">Active Jobs</h3>
            <p className="text-3xl font-bold text-blue-600 mt-2">0</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <h3 className="text-sm font-medium text-gray-500">
              Candidates Screened
            </h3>
            <p className="text-3xl font-bold text-green-600 mt-2">0</p>
          </div>
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <h3 className="text-sm font-medium text-gray-500">Bias Score</h3>
            <p className="text-3xl font-bold text-purple-600 mt-2">—</p>
          </div>
        </div>

        <div className="mt-8 bg-blue-50 border border-blue-100 rounded-2xl p-6">
          <h3 className="font-semibold text-blue-800 mb-1">
            🛡️ BDIOF Vector 2 Active
          </h3>
          <p className="text-sm text-blue-600">
            All candidate profiles are anonymized by default. You see skills and
            competencies first. Identity is only revealed after you request an
            interview.
          </p>
        </div>
      </div>
    </div>
  );
}
