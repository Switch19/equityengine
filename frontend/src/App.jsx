import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { ErrorBoundary } from "./components/ErrorBoundary";
import CandidateLayout from "./components/CandidateLayout";
import RecruiterLayout from "./components/RecruiterLayout";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Terms from "./pages/Terms";
import NotFound from "./pages/NotFound";

import CandidateDashboard from "./pages/candidate/CandidateDashboard";
import ProfileBuilder from "./pages/candidate/ProfileBuilder";
import CompetencyProfile from "./pages/candidate/CompetencyProfile";
import BrowseJobs from "./pages/candidate/BrowseJobs";
import Applications from "./pages/candidate/Applications";
import InterviewPrep from "./pages/candidate/InterviewPrep";
import CandidateMessages from "./pages/candidate/Messages";

import RecruiterDashboard from "./pages/recruiter/RecruiterDashboard";
import CompanyProfile from "./pages/recruiter/CompanyProfile";
import PostJob from "./pages/recruiter/PostJob";
import JobsList from "./pages/recruiter/JobsList";
import CompetencyDossier from "./pages/recruiter/CompetencyDossier";
import RecruiterMessages from "./pages/recruiter/Messages";
import AdminLayout from "./components/AdminLayout";
import AdminOverview from "./pages/admin/AdminOverview";
import VisibilityGapPage from "./pages/admin/VisibilityGapPage";
import DiversityReportPage from "./pages/admin/DiversityReportPage";
import RecruiterBiasScores from "./pages/admin/RecruiterBiasScores";

export default function App() {
  const { user } = useAuth();

  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<Navigate to={user ? `/${user.role}` : "/login"} replace />} />
        <Route path="/login" element={user ? <Navigate to={`/${user.role}`} replace /> : <Login />} />
        <Route path="/register" element={user ? <Navigate to={`/${user.role}`} replace /> : <Register />} />
        <Route path="/terms" element={<Terms />} />

        <Route
          path="/candidate"
          element={
            <ProtectedRoute allowedRole="candidate">
              <CandidateLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<CandidateDashboard />} />
          <Route path="profile" element={<ProfileBuilder />} />
          <Route path="competency" element={<CompetencyProfile />} />
          <Route path="jobs" element={<BrowseJobs />} />
          <Route path="applications" element={<Applications />} />
          <Route path="interview-prep" element={<InterviewPrep />} />
          <Route path="messages" element={<CandidateMessages />} />
        </Route>

        <Route
          path="/recruiter"
          element={
            <ProtectedRoute allowedRole="recruiter">
              <RecruiterLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<RecruiterDashboard />} />
          <Route path="company" element={<CompanyProfile />} />
          <Route path="jobs" element={<JobsList />} />
          <Route path="jobs/new" element={<PostJob />} />
          <Route path="jobs/:jobId" element={<CompetencyDossier />} />
          <Route path="messages" element={<RecruiterMessages />} />
        </Route>

        <Route
          path="/admin"
          element={
            <ProtectedRoute allowedRole="admin">
              <AdminLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<AdminOverview />} />
          <Route path="visibility-gap" element={<VisibilityGapPage />} />
          <Route path="diversity" element={<DiversityReportPage />} />
          <Route path="recruiters" element={<RecruiterBiasScores />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </ErrorBoundary>
  );
}
