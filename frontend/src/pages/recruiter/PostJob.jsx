import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { recruitersApi } from "../../api/recruiters";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";

const MODES = [
  {
    value: "standard",
    label: "Standard",
    description: "Candidate identity fully visible from the start.",
  },
  {
    value: "bdiof",
    label: "BDIOF",
    description: "Fully anonymised — identity revealed only when you request an interview.",
  },
  {
    value: "hybrid",
    label: "Hybrid",
    description: "Anonymised for the first round — identity revealed once shortlisted.",
  },
];

export default function PostJob() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [skillsInput, setSkillsInput] = useState("");
  const [location, setLocation] = useState("");
  const [screeningMode, setScreeningMode] = useState("bdiof");
  const [submitting, setSubmitting] = useState(false);
  const { showToast } = useToast();
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const required_skills = skillsInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const res = await recruitersApi.postJob({
        title,
        description,
        required_skills,
        location,
        screening_mode: screeningMode,
      });
      showToast("Job posted.", "success");
      navigate(`/recruiter/jobs/${res.data.id}`);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 pb-24">
      <h1 className="text-2xl font-display font-semibold">Post a Job</h1>

      <form onSubmit={handleSubmit} className="card p-6 mt-6 space-y-4">
        <div>
          <label className="label">Job title</label>
          <input type="text" required className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <label className="label">Description</label>
          <textarea
            required
            rows={5}
            className="input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div>
          <label className="label">Required skills (comma-separated)</label>
          <input
            type="text"
            className="input"
            placeholder="Python, FastAPI, PostgreSQL"
            value={skillsInput}
            onChange={(e) => setSkillsInput(e.target.value)}
          />
        </div>
        <div>
          <label className="label">Location</label>
          <input type="text" className="input" value={location} onChange={(e) => setLocation(e.target.value)} />
        </div>

        <fieldset>
          <legend className="label">Screening mode</legend>
          <div className="space-y-2">
            {MODES.map((mode) => (
              <label
                key={mode.value}
                className={`flex items-start gap-3 p-3 rounded border cursor-pointer transition-colors ${
                  screeningMode === mode.value ? "border-ink bg-ink-50" : "border-ink-100"
                }`}
              >
                <input
                  type="radio"
                  name="screeningMode"
                  className="mt-1"
                  checked={screeningMode === mode.value}
                  onChange={() => setScreeningMode(mode.value)}
                />
                <div>
                  <p className="font-medium text-sm">{mode.label}</p>
                  <p className="text-xs text-slate">{mode.description}</p>
                </div>
              </label>
            ))}
          </div>
        </fieldset>

        <button type="submit" disabled={submitting} className="btn-primary w-full">
          {submitting ? "Posting…" : "Post Job"}
        </button>
      </form>
    </div>
  );
}
