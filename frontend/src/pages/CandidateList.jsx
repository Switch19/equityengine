import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Navbar from "../components/Navbar";
import ChatBox from "../components/ChatBox";
import api from "../services/api";

export default function CandidateList() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [revealed, setRevealed] = useState({});
  const [activeChat, setActiveChat] = useState(null);
  const recruiterId = parseInt(localStorage.getItem("user_id") || "1");

  useEffect(() => {
    api
      .get(`/jobs/${jobId}/candidates?recruiter_id=${recruiterId}`)
      .then((res) => {
        setData(res.data);
        // Pre-populate revealed state for already revealed candidates
        const preRevealed = {};
        res.data.candidates?.forEach((candidate) => {
          const candidateNum = candidate.anonymous_id.split("-")[1];
          if (!candidate.is_anonymized && candidate.revealed) {
            preRevealed[candidateNum] = candidate.revealed;
          }
        });
        setRevealed(preRevealed);
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [jobId]);

  const handleReveal = async (candidateId) => {
    try {
      const res = await api.post(
        `/jobs/${jobId}/reveal/${candidateId}?recruiter_id=${recruiterId}`,
      );
      setRevealed((prev) => ({ ...prev, [candidateId]: res.data.candidate }));
    } catch (err) {
      console.error(err);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 70) return "text-green-600";
    if (score >= 40) return "text-amber-600";
    return "text-red-500";
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold text-gray-800 mb-1">
          {data?.job || "Loading..."}
        </h2>
        <p className="text-gray-500 mb-2">
          Candidates ranked by Skill-Score. Identity hidden until you request an
          interview.
        </p>

        <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-3 mb-8 flex items-center gap-3">
          <span className="text-blue-600 text-xl">🛡️</span>
          <p className="text-sm text-blue-700">
            <strong>BDIOF Vector 2 Active</strong> — Candidate names, photos,
            and locations are hidden. You are seeing skills and competencies
            only. Identity is revealed only after you request an interview.
          </p>
        </div>

        {loading && <p className="text-gray-400">Loading candidates...</p>}

        {!loading && data?.candidates?.length === 0 && (
          <div className="bg-white rounded-2xl p-8 text-center border border-gray-100">
            <p className="text-gray-400">No candidates have applied yet.</p>
          </div>
        )}

        <div className="space-y-4">
          {data?.candidates?.map((candidate, index) => {
            const candidateNum = candidate.anonymous_id.split("-")[1];
            const isRevealed = revealed[candidateNum];
            const isChatOpen = activeChat === candidateNum;

            return (
              <div
                key={index}
                className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6"
              >
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold">
                        {index + 1}
                      </div>
                      <div>
                        {isRevealed ? (
                          <div>
                            <p className="font-bold text-gray-800">
                              {isRevealed.full_name}
                            </p>
                            <p className="text-sm text-gray-500">
                              {isRevealed.email}
                            </p>
                          </div>
                        ) : (
                          <div>
                            <p className="font-bold text-gray-800">
                              {candidate.anonymous_id}
                            </p>
                            <p className="text-sm text-blue-600">
                              {candidate.regional_identifier}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-1 mb-3">
                      {candidate.skills
                        ?.split(",")
                        .slice(0, 8)
                        .map((skill, i) => (
                          <span
                            key={i}
                            className="bg-gray-100 text-gray-600 text-xs px-2 py-1 rounded-full"
                          >
                            {skill.trim()}
                          </span>
                        ))}
                      {candidate.skills?.split(",").length > 8 && (
                        <span className="text-xs text-gray-400 px-2 py-1">
                          +{candidate.skills.split(",").length - 8} more
                        </span>
                      )}
                    </div>

                    <div className="flex gap-4 text-sm">
                      <span
                        className={`font-semibold ${getScoreColor(candidate.skill_score)}`}
                      >
                        ⚡ Skill Match: {candidate.skill_score}%
                      </span>
                      <span className="text-gray-400">
                        🌍 Visibility: {candidate.visibility_score}%
                      </span>
                    </div>
                  </div>

                  <div className="shrink-0 flex flex-col gap-2 items-end">
                    {!isRevealed ? (
                      <button
                        onClick={() => handleReveal(candidateNum)}
                        className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded-lg transition"
                      >
                        Request Interview
                      </button>
                    ) : (
                      <>
                        <span className="bg-green-100 text-green-700 text-sm px-4 py-2 rounded-lg font-medium">
                          ✓ Interview Requested
                        </span>
                        <button
                          onClick={() =>
                            setActiveChat(isChatOpen ? null : candidateNum)
                          }
                          className="bg-blue-50 hover:bg-blue-100 text-blue-600 text-xs px-3 py-1.5 rounded-lg transition"
                        >
                          💬 {isChatOpen ? "Close Chat" : "Message Candidate"}
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Chat Box */}
                {isChatOpen && isRevealed && (
                  <div className="mt-4 border-t border-gray-100 pt-4">
                    <ChatBox
                      jobId={parseInt(jobId)}
                      senderId={recruiterId}
                      receiverId={parseInt(candidateNum)}
                      receiverName={isRevealed.full_name}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
