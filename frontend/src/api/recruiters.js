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
};
