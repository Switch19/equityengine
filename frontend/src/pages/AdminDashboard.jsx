import { useState, useEffect } from 'react'
import Navbar from '../components/Navbar'
import api from '../services/api'

export default function AdminDashboard() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    api.get('/admin/audit/summary')
      .then(res => setStats(res.data.platform_stats))
      .catch(err => console.error(err))
  }, [])

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto px-6 py-12">
        <h2 className="text-2xl font-bold text-gray-800 mb-1">Admin Dashboard 🔐</h2>
        <p className="text-gray-500 mb-8">Platform overview and bias audit access</p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total Users", value: stats?.total_users ?? '—', color: "text-blue-600" },
            { label: "Candidates", value: stats?.total_candidates ?? '—', color: "text-green-600" },
            { label: "Active Jobs", value: stats?.total_active_jobs ?? '—', color: "text-purple-600" },
            { label: "Talent Pool Views", value: stats?.total_talent_pool_views ?? '—', color: "text-amber-600" },
          ].map((s, i) => (
            <div key={i} className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
              <h3 className="text-xs font-medium text-gray-500">{s.label}</h3>
              <p className={`text-3xl font-bold mt-2 ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
          <p className="text-gray-500 mb-4">📊 View the full Bias Audit report and Visibility Gap analysis</p>
          <a href="/admin/audit" className="bg-purple-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-purple-700 transition inline-block">
            Open Bias Audit Engine
          </a>
        </div>
      </div>
    </div>
  )
}