import { useNavigate, useLocation } from 'react-router-dom'

export default function Navbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const role = localStorage.getItem('role')

  const handleLogout = () => {
    localStorage.clear()
    navigate('/login')
  }

  const candidateLinks = [
    { label: 'Dashboard', path: '/candidate/dashboard' },
    { label: 'Identity Optimizer', path: '/candidate/resume' },
    { label: 'Browse Jobs', path: '/candidate/jobs' },
    { label: 'Messages', path: '/candidate/messages' },
  ]

  const recruiterLinks = [
    { label: 'Dashboard', path: '/recruiter/dashboard' },
    { label: 'Post a Job', path: '/recruiter/post-job' },
    { label: 'View Jobs', path: '/recruiter/jobs' },
    { label: 'Browse Talent', path: '/recruiter/talent' },
    { label: 'Messages', path: '/recruiter/messages' },
  ]

  const adminLinks = [
    { label: 'Dashboard', path: '/admin/dashboard' },
    { label: 'Bias Audit', path: '/admin/audit' },
  ]

  const links = role === 'candidate' ? candidateLinks
    : role === 'recruiter' ? recruiterLinks
    : role === 'admin' ? adminLinks
    : []

  return (
    <nav className="bg-white shadow-sm px-8 py-4 flex justify-between items-center sticky top-0 z-50">
      <div className="flex items-center gap-8">
        <h1
          onClick={() => navigate(role ? `/${role}/dashboard` : '/login')}
          className="text-xl font-bold text-blue-600 cursor-pointer"
        >
          EquityEngine
        </h1>
        <div className="hidden md:flex items-center gap-1">
          {links.map(link => (
            <button
              key={link.path}
              onClick={() => navigate(link.path)}
              className={`text-sm px-3 py-2 rounded-lg transition ${
                location.pathname === link.path
                  ? 'bg-blue-50 text-blue-600 font-medium'
                  : 'text-gray-500 hover:text-gray-800 hover:bg-gray-50'
              }`}
            >
              {link.label}
            </button>
          ))}
        </div>
      </div>
      <button
        onClick={handleLogout}
        className="text-sm text-gray-400 hover:text-red-500 transition"
      >
        Logout
      </button>
    </nav>
  )
}