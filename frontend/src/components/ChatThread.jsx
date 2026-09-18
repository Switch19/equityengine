import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import { messagesApi } from "../api/messages";
import { useWebSocketContext } from "../context/WebSocketContext";
import { useToast } from "../context/ToastContext";
import { getErrorMessage } from "../api/client";
import LoadingSkeleton from "./LoadingSkeleton";

export default function ChatThread({ otherUserId, jobId, otherUserLabel, onBack }) {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [blockedReason, setBlockedReason] = useState(null);
  const { subscribe, sendChatMessage } = useWebSocketContext();
  const { showToast } = useToast();
  const bottomRef = useRef(null);

  const load = useCallback(async () => {
    setBlockedReason(null);
    try {
      const res = await messagesApi.getThread(otherUserId, jobId);
      setMessages(res.data);
    } catch (error) {
      if (error.response?.status === 403) {
        setBlockedReason(getErrorMessage(error));
      } else {
        showToast(getErrorMessage(error), "error");
      }
    } finally {
      setLoading(false);
    }
  }, [otherUserId, jobId, showToast]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const unsubscribe = subscribe("new_message", (payload) => {
      if (payload.sender_id === otherUserId && payload.job_id === jobId) {
        setMessages((prev) => [...prev, {
          id: payload.message_id,
          sender_id: payload.sender_id,
          receiver_id: user.id,
          job_id: payload.job_id,
          content: payload.content,
          created_at: payload.created_at,
        }]);
      }
    });
    return unsubscribe;
  }, [subscribe, otherUserId, jobId, user.id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    const content = text.trim();
    if (!content) return;

    setSending(true);
    const sentViaSocket = sendChatMessage(otherUserId, jobId, content);

    if (!sentViaSocket) {
      try {
        const res = await messagesApi.sendMessage(otherUserId, jobId, content);
        setMessages((prev) => [...prev, res.data]);
      } catch (error) {
        showToast(getErrorMessage(error), "error");
      }
    } else {
      setMessages((prev) => [...prev, {
        id: `temp-${Date.now()}`,
        sender_id: user.id,
        receiver_id: otherUserId,
        job_id: jobId,
        content,
        created_at: new Date().toISOString(),
      }]);
    }

    setText("");
    setSending(false);
  }

  async function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    setSending(true);
    try {
      const res = await messagesApi.sendFile(otherUserId, jobId, file);
      setMessages((prev) => [...prev, res.data]);
    } catch (error) {
      showToast(getErrorMessage(error), "error");
    } finally {
      setSending(false);
      e.target.value = "";
    }
  }

  if (loading) {
    return <LoadingSkeleton lines={4} className="p-4" />;
  }

  if (blockedReason) {
    return (
      <div className="p-6 text-center">
        <p className="text-sm text-slate">{blockedReason}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-ink-100 flex items-center gap-2">
        {onBack && (
          <button onClick={onBack} className="md:hidden text-slate p-1 -ml-1" aria-label="Back to conversations">
            ←
          </button>
        )}
        <p className="font-medium text-sm">{otherUserLabel}</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 ? (
          <p className="text-sm text-slate text-center py-8">No messages yet — say hello.</p>
        ) : (
          messages.map((m) => {
            const isMine = m.sender_id === user.id;
            return (
              <div key={m.id} className={`flex ${isMine ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
                    isMine ? "bg-ink text-paper" : "bg-ink-50 text-ink"
                  }`}
                >
                  {m.content && <p>{m.content}</p>}
                  {m.file_url && (
                    <a
                      href={`${import.meta.env.VITE_API_URL || 'https://equityengine-tecf.onrender.com'}${m.file_url}`}
                      target="_blank"
                      rel="noreferrer"
                      className={`text-xs underline underline-offset-2 ${isMine ? "text-paper" : "text-ink"}`}
                    >
                      📎 {m.file_name || "Attachment"}
                    </a>
                  )}
                  <p className={`text-[10px] mt-1 ${isMine ? "text-ink-100" : "text-slate"}`}>
                    {new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </p>
                </div>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="flex items-center gap-2 p-3 border-t border-ink-100">
        <label className="btn-secondary text-xs px-2 py-1.5 cursor-pointer shrink-0">
          📎
          <input type="file" className="hidden" onChange={handleFileChange} disabled={sending} />
        </label>
        <input
          type="text"
          className="input flex-1"
          placeholder="Type a message…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={sending}
        />
        <button type="submit" disabled={sending || !text.trim()} className="btn-primary text-sm px-4 py-2 shrink-0">
          Send
        </button>
      </form>
    </div>
  );
}
