import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'

export default function RecommendedJobs({ userId }) {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/candidates/recommended-jobs/${userId}`)
      .then(res => setData(res.data))
      .catch(err => console.error(err))
      .finally(() => setLoading(false))
  }, [userId])

  if (loading) return <p className="text-gray-400 text-sm">Loading recommendations...</p>

  if (!data?.has_profile) return (
    <p className="text-gray-400 text-sm">Upload your CV to get personalized job recommendations.</p>
  )

  if (data.recommendations.length === 0) return (
    <p className="text-gray-400 text-sm">No matching jobs found yet. Check back soon!</p>
  )

  return (
    <div className="space-y-3">
      {data.recommendations.map((job, i) => (
        <div key={i} className="border border-gray-100 rounded-xl p-4 hover:border-blue-200 transition">
          <div className="flex justify-between items-start gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <p className="font-semibold text-gray-800">{job.title}</p>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                  job.skill_score >= 70 ? 'bg-green-100 text-green-700' :
                  job.skill_score >= 40 ? 'bg-amber-100 text-amber-700' :
                  'bg-red-100 text-red-700'
                }`}>
                  {job.skill_score}% match
                </span>
              </div>
              <p className="text-xs text-gray-500 mb-2">📍 {job.location || 'Remote'}</p>
              {job.missing_skills.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-amber-600 font-medium mb-1">
                    ⚡ Skill gap — you're missing:
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {job.missing_skills.map((skill, j) => (
                      <span key={j} className="bg-amber-50 text-amber-700 text-xs px-2 py-0.5 rounded-full">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={() => navigate('/candidate/jobs')}
              className="shrink-0 bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-2 rounded-lg transition"
            >
              View Job
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}