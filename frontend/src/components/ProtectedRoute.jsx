import { Navigate } from 'react-router-dom'

export default function ProtectedRoute({ children, allowedRole }) {
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role')

  if (!token) {
    return <Navigate to="/login" replace />
  }

  if (allowedRole && role !== allowedRole) {
    if (role === 'candidate') return <Navigate to="/candidate/dashboard" replace />
    if (role === 'recruiter') return <Navigate to="/recruiter/dashboard" replace />
    return <Navigate to="/login" replace />
  }

  return children
}