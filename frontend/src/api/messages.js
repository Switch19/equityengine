import { apiClient } from "./client";

export const messagesApi = {
  getConversations: () => apiClient.get("/messages/conversations"),

  getThread: (otherUserId, jobId) =>
    apiClient.get(`/messages/thread/${otherUserId}/${jobId}`),

  sendMessage: (receiverId, jobId, content) =>
    apiClient.post("/messages/send", { receiver_id: receiverId, job_id: jobId, content }),

  sendFile: (receiverId, jobId, file, caption = "") => {
    const formData = new FormData();
    formData.append("receiver_id", receiverId);
    formData.append("job_id", jobId);
    formData.append("caption", caption);
    formData.append("file", file);
    return apiClient.post("/messages/send-file", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
};

export const notificationsApi = {
  getAll: () => apiClient.get("/notifications"),
  getUnreadCount: () => apiClient.get("/notifications/unread-count"),
  markRead: (notificationId) => apiClient.patch(`/notifications/${notificationId}/read`),
  markAllRead: () => apiClient.patch("/notifications/read-all"),
};
