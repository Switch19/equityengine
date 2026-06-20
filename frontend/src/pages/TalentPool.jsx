import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Navbar from '../components/Navbar'
import api from '../services/api'

export default function TalentPool() {
  const [skills, setSkills] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [revealed, setRevealed] = useState({})

  const handleSearch = async () => {
    if (!skills.trim()) return
    setLoading(true)
    try {
      const res = await api.get(`/recruiters/talent-pool?skills=${encodeURIComponent(skills)}&recruiter_id=1`)
      setResults(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleReveal = async (candidateId, jobId = 1) => {
    try {
      const res = await api.post(`/jobs/${jobId}/reveal/${candidateId}?recruiter_id=1`)
      setRevealed(prev => ({ ...prev, [candidateId]: res.data.candidate }))
    } catch (err) {
      console.error(err)
    }
  }

  const getScoreColor = (score) => {
    if (score >= 70) return 'text-green-600'
    if (score >= 40) return 'text-amber-600'
    return 'text-red-500'
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 py-10">
        <h2 className="text-2xl font-bold text-gray-800 mb-1">Browse Talent Pool 👥</h2>
        <p className="text-gray-500 mb-6">
          Search for candidates by skills — no job posting required. BDIOF anonymization is always active.
        </p>

        {/* BDIOF Banner */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-3 mb-6 flex items-center gap-3">
          <span className="text-blue-600 text-xl">🛡️</span>
          <p className="text-sm text-blue-700">
            <strong>BDIOF Vector 2 Active</strong> — All candidates are anonymized.
            Identity revealed only after you request an interview.
          </p>
        </div>

        {/* Search */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Search by Skills
            <span className="text-gray-400 font-normal ml-1">(comma separated)</span>
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              value={skills}
              onChange={(e) => setSkills(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="e.g. python, react, postgresql, docker"
              className="flex-1 border border-gray-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
            <button
              onClick={handleSearch}
              disabled={!skills.trim() || loading}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg transition disabled:opacity-50 font-medium"
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>
        </div>

        {/* Results */}
        {results && (
          <div>
            <p className="text-sm text-gray-500 mb-4">
              Found <strong>{results.candidates.length}</strong> candidates matching
              <strong> "{results.searched_skills}"</strong> — ranked by Skill-Score
            </p>

            {results.candidates.length === 0 && (
              <div className="bg-white rounded-2xl p-8 text-center border border-gray-100">
                <p className="text-gray-400">No candidates found with those skills yet.</p>
              </div>
            )}

            <div className="space-y-4">
              {results.candidates.map((candidate, index) => {
                const candidateNum = candidate.anonymous_id.split('-')[1]
                const isRevealed = revealed[candidateNum]

                return (
                  <div key={index} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                    <div className="flex justify-between items-start gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-3">
                          <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold">
                            {index + 1}
                          </div>
                          <div>
                            {isRevealed ? (
                              <div>
                                <p className="font-bold text-gray-800">{isRevealed.full_name}</p>
                                <p className="text-sm text-gray-500">{isRevealed.email}</p>
                              </div>
                            ) : (
                              <div>
                                <p className="font-bold text-gray-800">{candidate.anonymous_id}</p>
                                <p className="text-sm text-blue-600">{candidate.regional_identifier}</p>
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="flex flex-wrap gap-1 mb-3">
                          {candidate.skills?.split(',').slice(0, 8).map((skill, i) => (
                            <span key={i} className="bg-gray-100 text-gray-600 text-xs px-2 py-1 rounded-full">
                              {skill.trim()}
                            </span>
                          ))}
                          {candidate.skills?.split(',').length > 8 && (
                            <span className="text-xs text-gray-400 px-2 py-1">
                              +{candidate.skills.split(',').length - 8} more
                            </span>
                          )}
                        </div>

                        <div className="flex gap-4 text-sm">
                          <span className={`font-semibold ${getScoreColor(candidate.skill_score)}`}>
                            ⚡ Skill Match: {candidate.skill_score}%
                          </span>
                          <span className="text-gray-400">
                            🌍 Visibility: {candidate.visibility_score}%
                          </span>
                        </div>
                      </div>

                      <div className="shrink-0">
                        {!isRevealed ? (
                          <button
                            onClick={() => handleReveal(candidateNum)}
                            className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded-lg transition"
                          >
                            Request Interview
                          </button>
                        ) : (
                          <span className="bg-green-100 text-green-700 text-sm px-4 py-2 rounded-lg font-medium">
                            ✓ Interview Requested
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}