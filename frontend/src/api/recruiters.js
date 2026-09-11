import { apiClient } from "./client";

export const recruitersApi = {
  getCompany: () => apiClient.get("/recruiters/company"),
  createCompany: (data) => apiClient.post("/recruiters/company", data),

  listJobs: () => apiClient.get("/recruiters/jobs"),
  getJob: (jobId) => apiClient.get(`/recruiters/jobs/${jobId}`),
  postJob: (data) => apiClient.post("/recruiters/jobs", data),
  updateJob: (jobId, data) => apiClient.patch(`/recruiters/jobs/${jobId}`, data),

  getDossier: (jobId) => apiClient.get(`/recruiters/jobs/${jobId}/candidates`),
  getCandidateDetail: (jobId, applicationId) =>
    apiClient.get(`/recruiters/jobs/${jobId}/candidates/${applicationId}`),
  getViewLimitStatus: (jobId, applicationId) =>
    apiClient.get(`/recruiters/jobs/${jobId}/candidates/${applicationId}/view-limit`),

  updateApplicationStatus: (jobId, applicationId, status, timeSpentSeconds) =>
    apiClient.patch(`/recruiters/jobs/${jobId}/candidates/${applicationId}/status`, {
      status,
      time_spent_seconds: timeSpentSeconds,
    }),

  revealCandidate: (jobId, applicationId) =>
    apiClient.post(`/recruiters/jobs/${jobId}/candidates/${applicationId}/reveal`),

  // Talent Pool — sourcing across all candidates, not scoped to a job.
  // Filtering is server-side (see routers/recruiters.py), so params are
  // passed through rather than applied to a cached list. Null/empty
  // values are dropped so an untouched filter doesn't become
  // `?search=` in the query string.
  getTalentPool: ({ search, minScore, limit, offset } = {}) =>
    apiClient.get("/recruiters/talent-pool", {
      params: {
        ...(search ? { search } : {}),
        ...(minScore != null && minScore > 0 ? { min_score: minScore } : {}),
        ...(limit != null ? { limit } : {}),
        ...(offset ? { offset } : {}),
      },
    }),

  inviteToJob: (candidateId, jobId, note) =>
    apiClient.post(`/recruiters/talent-pool/${candidateId}/invite`, {
      job_id: jobId,
      note: note || null,
    }),
};
