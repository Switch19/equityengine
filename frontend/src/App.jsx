import { Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Register from "./pages/Register";
import CandidateDashboard from "./pages/CandidateDashboard";
import RecruiterDashboard from "./pages/RecruiterDashboard";
import ResumeAnalysis from "./pages/ResumeAnalysis";
import RecruiterJobs from "./pages/RecruiterJobs";
import PostJob from "./pages/PostJob";
import CandidateList from "./pages/CandidateList";
import AuditDashboard from "./pages/AuditDashboard";
import ProtectedRoute from "./components/ProtectedRoute";
import BrowseJobs from "./pages/BrowseJobs";
import AdminDashboard from "./pages/AdminDashboard";
import AdminAudit from "./pages/AdminAudit";
import TalentPool from "./pages/TalentPool";
import Messages from "./pages/Messages";
function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Candidate Routes */}
      <Route
        path="/candidate/dashboard"
        element={
          <ProtectedRoute allowedRole="candidate">
            <CandidateDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidate/resume"
        element={
          <ProtectedRoute allowedRole="candidate">
            <ResumeAnalysis />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidate/jobs"
        element={
          <ProtectedRoute allowedRole="candidate">
            <BrowseJobs />
          </ProtectedRoute>
        }
      />
      <Route
        path="/candidate/messages"
        element={
          <ProtectedRoute allowedRole="candidate">
            <Messages />
          </ProtectedRoute>
        }
      />

      {/* Recruiter Routes */}
      <Route
        path="/recruiter/dashboard"
        element={
          <ProtectedRoute allowedRole="recruiter">
            <RecruiterDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recruiter/jobs"
        element={
          <ProtectedRoute allowedRole="recruiter">
            <RecruiterJobs />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recruiter/post-job"
        element={
          <ProtectedRoute allowedRole="recruiter">
            <PostJob />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recruiter/jobs/:jobId/candidates"
        element={
          <ProtectedRoute allowedRole="recruiter">
            <CandidateList />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recruiter/audit"
        element={
          <ProtectedRoute allowedRole="recruiter">
            <AuditDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recruiter/talent"
        element={
          <ProtectedRoute allowedRole="recruiter">
            <TalentPool />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recruiter/messages"
        element={
          <ProtectedRoute allowedRole="recruiter">
            <Messages />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/dashboard"
        element={
          <ProtectedRoute allowedRole="admin">
            <AdminDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/audit"
        element={
          <ProtectedRoute allowedRole="admin">
            <AdminAudit />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export default App;
