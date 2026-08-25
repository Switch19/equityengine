import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { messagesApi } from "../../api/messages";
import { useToast } from "../../context/ToastContext";
import { getErrorMessage } from "../../api/client";
import LoadingSkeleton from "../../components/LoadingSkeleton";
import EmptyState from "../../components/EmptyState";
import ChatThread from "../../components/ChatThread";

export default function Messages() {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [searchParams] = useSearchParams();
  const { showToast } = useToast();

  const load = useCallback(async () => {
    try {
      const res = await messagesApi.getConversations();
      setConversations(res.data);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const withUser = searchParams.get("with");
    const job = searchParams.get("job");
    const label = searchParams.get("label");
    if (withUser && job) {
      setSelected({
        other_user_id: withUser,
        job_id: job,
        other_user_name: label || "Candidate",
        job_title: "",
      });
    }
  }, [searchParams]);

  return (
    <div className="h-[calc(100vh-3.5rem)] md:h-screen pt-14 md:pt-0 flex">
      <div
        className={`w-full md:w-72 md:shrink-0 border-r border-ink-100 overflow-y-auto ${
          selected ? "hidden md:block" : "block"
        }`}
      >
        <div className="px-4 py-4 border-b border-ink-100">
          <h1 className="font-display font-semibold">Messages</h1>
        </div>

        {loading ? (
          <LoadingSkeleton lines={3} className="p-4" />
        ) : conversations.length === 0 ? (
          <div className="p-4">
            <EmptyState
              title="No conversations yet"
              description="Reveal a candidate's identity from a job's Competency Dossier to start a conversation."
            />
          </div>
        ) : (
          <ul>
            {conversations.map((c) => (
              <li key={`${c.other_user_id}-${c.job_id}`}>
                <button
                  onClick={() => setSelected(c)}
                  className={`w-full text-left px-4 py-3 border-b border-ink-50 hover:bg-ink-50 transition-colors ${
                    selected?.other_user_id === c.other_user_id && selected?.job_id === c.job_id
                      ? "bg-ink-50"
                      : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-sm truncate">{c.other_user_name}</p>
                    {c.unread_count > 0 && (
                      <span className="bg-gap text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1">
                        {c.unread_count}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate truncate">{c.job_title}</p>
                  <p className="text-xs text-ink-600 truncate mt-0.5">{c.last_message}</p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className={`flex-1 min-w-0 ${selected ? "block" : "hidden md:block"}`}>
        {selected ? (
          <ChatThread
            key={`${selected.other_user_id}-${selected.job_id}`}
            otherUserId={selected.other_user_id}
            jobId={selected.job_id}
            otherUserLabel={`${selected.other_user_name} — ${selected.job_title}`}
            onBack={() => setSelected(null)}
          />
        ) : (
          <div className="h-full items-center justify-center text-sm text-slate hidden md:flex">
            Select a conversation to view messages.
          </div>
        )}
      </div>
    </div>
  );
}
