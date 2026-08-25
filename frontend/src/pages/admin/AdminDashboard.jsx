import { useAuth } from "../../context/AuthContext";

export default function AdminDashboard() {
  const { user, logout } = useAuth();
  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      <h1 className="text-2xl font-display font-semibold">Welcome, {user.full_name}</h1>
      <p className="text-slate mt-2">
        Admin dashboard — Visibility Gap, diversity report, and recruiter bias scores are coming
        in the next build phase.
      </p>
      <button onClick={logout} className="btn-secondary mt-6">Log out</button>
    </div>
  );
}
