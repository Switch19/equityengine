import { Link } from "react-router-dom";

export default function Terms() {
  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      <Link to="/register" className="text-sm text-slate underline underline-offset-2">
        ← Back to registration
      </Link>

      <h1 className="text-3xl font-display font-semibold mt-6 mb-6">Terms and Consent Notice</h1>

      <div className="prose prose-sm text-ink space-y-4">
        <p className="text-slate">
          This notice explains what EquityEngine does with your data, in plain terms, before
          you agree to it.
        </p>

        <h2 className="font-display text-lg font-semibold mt-6">What we collect</h2>
        <p>
          If you register as a candidate, EquityEngine may process: your CV (if you choose to
          upload one), your public GitHub activity (if you choose to link an account),
          certifications and community contributions you add, and any peer endorsements you
          receive. No single source is mandatory — you can build a profile from any combination
          of these.
        </p>

        <h2 className="font-display text-lg font-semibold mt-6">How it's used</h2>
        <p>
          This data feeds a Competency Engine that computes your Evidence Score and skill
          verification badges. Formal credentials (degrees, named institutions) carry zero
          weight in this score by default — evaluation is based on demonstrated evidence across
          your CV, GitHub, and community activity.
        </p>

        <h2 className="font-display text-lg font-semibold mt-6">Anonymised screening</h2>
        <p>
          Recruiters may choose to screen candidates anonymously (BDIOF mode). Under this mode,
          your name, email, location, institution, and GitHub username are withheld from
          recruiters until you are shortlisted for an interview or a recruiter explicitly
          reveals your profile. This is a platform feature designed to reduce bias, not a
          guarantee against all possible re-identification from context.
        </p>

        <h2 className="font-display text-lg font-semibold mt-6">Audit logging</h2>
        <p>
          Recruiter interactions with candidate profiles (views, shortlisting decisions, and
          identity reveals) are logged for the platform's Bias Audit Engine, which measures
          aggregate outcomes across screening modes. This audit data is used for platform-level
          fairness reporting, not for individual candidate scoring.
        </p>

        <h2 className="font-display text-lg font-semibold mt-6">Your control</h2>
        <p>
          You can edit or remove CV-derived data at any time from your profile. GitHub and
          community data can be re-synced or unlinked. Contact the platform administrator to
          request full account deletion.
        </p>

        <p className="text-slate text-xs mt-8">
          This platform is a final-year academic project at Delta State University. It is not a
          commercial recruitment service.
        </p>
      </div>
    </div>
  );
}
