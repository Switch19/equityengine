import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export default function Register() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("candidate");
  const [consentGiven, setConsentGiven] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const { register } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    if (!consentGiven) {
      showToast("You must accept the terms and consent notice to register.", "error");
      return;
    }
    setSubmitting(true);
    try {
      const user = await register({ email, fullName, password, role, consentGiven });
      showToast(`Welcome to EquityEngine, ${user.full_name.split(" ")[0]}.`, "success");
      navigate(`/${user.role}`);
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-display font-semibold">EquityEngine</h1>
          <p className="text-slate mt-1 text-sm">Create your account.</p>
        </div>

        <form onSubmit={handleSubmit} className="card p-6 space-y-4">
          <div>
            <label htmlFor="fullName" className="label">Full name</label>
            <input
              id="fullName"
              type="text"
              required
              className="input"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
            />
          </div>
          <div>
            <label htmlFor="email" className="label">Email</label>
            <input
              id="email"
              type="email"
              required
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>
          <div>
            <label htmlFor="password" className="label">Password</label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
            <p className="text-xs text-slate mt-1">At least 8 characters.</p>
          </div>

          <fieldset>
            <legend className="label">I am joining as a</legend>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setRole("candidate")}
                className={`rounded border px-3 py-2 text-sm font-medium transition-colors ${
                  role === "candidate"
                    ? "border-ink bg-ink text-paper"
                    : "border-ink-100 text-ink hover:border-ink-400"
                }`}
              >
                Candidate
              </button>
              <button
                type="button"
                onClick={() => setRole("recruiter")}
                className={`rounded border px-3 py-2 text-sm font-medium transition-colors ${
                  role === "recruiter"
                    ? "border-ink bg-ink text-paper"
                    : "border-ink-100 text-ink hover:border-ink-400"
                }`}
              >
                Recruiter
              </button>
            </div>
          </fieldset>

          <label className="flex items-start gap-2 text-sm text-slate">
            <input
              type="checkbox"
              checked={consentGiven}
              onChange={(e) => setConsentGiven(e.target.checked)}
              className="mt-0.5"
              required
            />
            <span>
              I accept the{" "}
              <Link to="/terms" className="text-ink underline underline-offset-2" target="_blank">
                Terms and Consent Notice
              </Link>
              , including how EquityEngine processes my CV, GitHub, and community data to
              compute an Evidence Score.
            </span>
          </label>

          <button type="submit" disabled={submitting} className="btn-primary w-full">
            {submitting ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="text-center text-sm text-slate mt-6">
          Already have an account?{" "}
          <Link to="/login" className="text-ink font-medium underline underline-offset-2">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
