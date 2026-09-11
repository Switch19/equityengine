import { apiClient } from "./client";

export const candidatesApi = {
  getProfile: () => apiClient.get("/candidates/me/profile"),

  updateProfile: (data) => apiClient.patch("/candidates/me/profile", data),

  getCompetencyProfile: () => apiClient.get("/candidates/me/competency-profile"),

  // Optimized CV/profile PDF, generated server-side from all three
  // evidence pipelines. responseType "blob" is required: without it
  // axios parses the PDF bytes as text and the saved file is corrupt.
  downloadOptimizedProfile: () =>
    apiClient.get("/candidates/me/cv/download", { responseType: "blob" }),

  uploadCV: (file) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post("/candidates/cv/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  linkGithub: (githubUsername) =>
    apiClient.post("/candidates/github/link", { github_username: githubUsername }),

  addCertification: (data) => apiClient.post("/candidates/certifications", data),

  linkStackOverflow: (stackoverflowUserId) =>
    apiClient.post("/candidates/community/stackoverflow/link", {
      stackoverflow_user_id: stackoverflowUserId,
    }),

  linkDevTo: (devtoUsername) =>
    apiClient.post("/candidates/community/devto/link", { devto_username: devtoUsername }),

  getEndorsements: () => apiClient.get("/candidates/me/endorsements"),

  endorseCandidate: (candidateId, skill) =>
    apiClient.post(`/candidates/${candidateId}/endorse`, { candidate_id: candidateId, skill }),

  browseJobs: () => apiClient.get("/candidates/jobs"),

  getJob: (jobId) => apiClient.get(`/candidates/jobs/${jobId}`),

  applyToJob: (jobId) => apiClient.post(`/candidates/jobs/${jobId}/apply`),

  getMyApplications: () => apiClient.get("/candidates/me/applications"),

  startInterview: (data) => apiClient.post("/candidates/interview/start", data),

  submitInterview: (sessionId, answers) =>
    apiClient.post(`/candidates/interview/${sessionId}/submit`, { answers }),

  getInterviewSession: (sessionId) => apiClient.get(`/candidates/interview/${sessionId}`),

  getInterviewHistory: () => apiClient.get("/candidates/interview"),
};
