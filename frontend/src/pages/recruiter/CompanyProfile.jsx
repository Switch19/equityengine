import { useState, useEffect, useCallback } from "react";
import { recruitersApi } from "../../api/recruiters";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";

export default function CompanyProfile() {
  const [company, setCompany] = useState(null);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [website, setWebsite] = useState("");
  const [industry, setIndustry] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const res = await recruitersApi.getCompany();
      setCompany(res.data);
    } catch (error) {
      if (error.response?.status !== 404) {
        showToast(getErrorMessage(error), "error");
      }
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await recruitersApi.createCompany({ name, website, industry });
      setCompany(res.data);
      showToast("Company profile created.", "success");
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-10">
        <LoadingSkeleton lines={4} />
      </div>
    );
  }

  if (company) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-display font-semibold">Company Profile</h1>
        <div className="card p-6 mt-6">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="font-display font-semibold text-lg">{company.name}</h2>
              {company.industry && <p className="text-sm text-slate">{company.industry}</p>}
              {company.website && (
                <a href={company.website} target="_blank" rel="noreferrer" className="text-sm text-ink underline underline-offset-2 mt-1 inline-block">
                  {company.website}
                </a>
              )}
            </div>
            {company.badge_earned && (
              <span className="badge badge-verified shrink-0">Bias-Neutral Employer</span>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-display font-semibold">Create your Company Profile</h1>
      <p className="text-slate text-sm mt-1 mb-6">
        Required before you can post a job.
      </p>

      <form onSubmit={handleSubmit} className="card p-6 space-y-4">
        <div>
          <label className="label">Company name</label>
          <input type="text" required className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label">Website</label>
          <input type="url" className="input" value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="https://" />
        </div>
        <div>
          <label className="label">Industry</label>
          <input type="text" className="input" value={industry} onChange={(e) => setIndustry(e.target.value)} />
        </div>
        <button type="submit" disabled={submitting} className="btn-primary w-full">
          {submitting ? "Creating…" : "Create Company Profile"}
        </button>
      </form>
    </div>
  );
}
