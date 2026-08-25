import { useState, useEffect, useCallback } from "react";
import { candidatesApi } from "../../api/candidates";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";
import EmptyState from "../../components/EmptyState";

const STAGES = { IDLE: "idle", ANSWERING: "answering", RESULTS: "results" };

export default function InterviewPrep() {
  const [stage, setStage] = useState(STAGES.IDLE);
  const [starting, setStarting] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState([]);
  const [providerUsed, setProviderUsed] = useState(null);
  const [results, setResults] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const { showToast } = useToast();

  const loadHistory = useCallback(async () => {
    try {
      const res = await candidatesApi.getInterviewHistory();
      setHistory(res.data);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setHistoryLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  async function handleStart() {
    setStarting(true);
    try {
      const res = await candidatesApi.startInterview({ num_questions: 5 });
      setSessionId(res.data.session_id);
      setQuestions(res.data.questions);
      setAnswers(res.data.questions.map(() => ""));
      setProviderUsed(res.data.provider_used);
      setStage(STAGES.ANSWERING);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setStarting(false);
    }
  }

  function updateAnswer(index, value) {
    setAnswers((prev) => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      const payload = questions.map((q, i) => ({ question: q, answer: answers[i] }));
      const res = await candidatesApi.submitInterview(sessionId, payload);
      setResults(res.data);
      setStage(STAGES.RESULTS);
      loadHistory();
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    setStage(STAGES.IDLE);
    setSessionId(null);
    setQuestions([]);
    setAnswers([]);
    setResults(null);
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 pb-24">
      <h1 className="text-2xl font-display font-semibold">AI Mock Interview</h1>
      <p className="text-slate text-sm mt-1 mb-8">
        Questions are generated from your Competency Profile. Practice sessions never affect
        your Evidence Score.
      </p>

      {stage === STAGES.IDLE && (
        <div className="card p-6 text-center">
          <p className="text-sm text-slate mb-4">
            Ready for a 5-question practice interview based on your verified skills?
          </p>
          <button onClick={handleStart} disabled={starting} className="btn-primary">
            {starting ? "Preparing questions…" : "Start Mock Interview"}
          </button>
        </div>
      )}

      {stage === STAGES.ANSWERING && (
        <div className="space-y-5">
          {providerUsed === "rule-based" && (
            <p className="text-xs text-slate bg-ink-50 rounded p-3">
              AI providers are currently unavailable — using template-based questions instead.
            </p>
          )}
          {questions.map((q, i) => (
            <div key={i} className="card p-5">
              <p className="font-medium text-sm mb-3">
                {i + 1}. {q}
              </p>
              <textarea
                rows={4}
                className="input"
                placeholder="Type your answer…"
                value={answers[i]}
                onChange={(e) => updateAnswer(i, e.target.value)}
              />
            </div>
          ))}
          <button
            onClick={handleSubmit}
            disabled={submitting || answers.every((a) => !a.trim())}
            className="btn-primary w-full"
          >
            {submitting ? "Scoring your answers…" : "Submit Answers"}
          </button>
        </div>
      )}

      {stage === STAGES.RESULTS && results && (
        <div className="space-y-5">
          <div className="card p-6 text-center">
            <p className="text-sm text-slate">Overall score</p>
            <p className="score-figure text-4xl text-beacon-600 mt-1">
              {results.overall_score}<span className="text-lg text-slate">/10</span>
            </p>
            <p className="text-xs text-slate mt-2">{results.overall_feedback}</p>
            {results.provider_used === "rule-based" && (
              <p className="text-xs text-gap mt-2">
                Scored with a rule-based fallback (answer length/structure only) — treat this as
                practice, not a precise skill measurement.
              </p>
            )}
          </div>

          {questions.map((q, i) => (
            <div key={i} className="card p-5">
              <div className="flex items-start justify-between gap-3">
                <p className="font-medium text-sm">{i + 1}. {q}</p>
                <span className="score-figure text-sm shrink-0">{results.scores[i]?.score}/10</span>
              </div>
              <p className="text-sm text-slate mt-2 italic">"{answers[i]}"</p>
              <p className="text-xs text-ink-600 mt-2">{results.scores[i]?.feedback}</p>
            </div>
          ))}

          <button onClick={handleReset} className="btn-secondary w-full">
            Start Another Session
          </button>
        </div>
      )}

      <div className="mt-10 pt-8 border-t border-ink-100">
        <h2 className="font-display font-semibold mb-3">Past sessions</h2>
        {historyLoading ? (
          <LoadingSkeleton lines={2} />
        ) : history.length === 0 ? (
          <EmptyState title="No past sessions" description="Your completed mock interviews will appear here." />
        ) : (
          <ul className="space-y-2">
            {history.map((session) => (
              <li key={session.id} className="card p-3 flex items-center justify-between text-sm">
                <span className="text-slate">{new Date(session.created_at).toLocaleDateString()}</span>
                <span className="score-figure">
                  {session.overall_score != null ? `${session.overall_score}/10` : "In progress"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
