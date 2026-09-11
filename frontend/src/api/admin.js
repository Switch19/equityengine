import { apiClient } from "./client";

export const adminApi = {
  getStats: () => apiClient.get("/admin/stats"),
  getVisibilityGap: () => apiClient.get("/admin/visibility-gap"),
  getVisibilityGapTimeseries: (bucket = "week") =>
    apiClient.get("/admin/visibility-gap/timeseries", { params: { bucket } }),
  getDiversityReport: () => apiClient.get("/admin/diversity-report"),
  getRecruiterBiasScores: () => apiClient.get("/admin/recruiters/bias-scores"),

  // Registry + live audit feed. These are admin-only server-side
  // (require_role(UserRole.admin) on every /admin route); the client
  // guard in App.jsx only decides what to render, never what the API
  // will hand out.
  getCandidateRegistry: () => apiClient.get("/admin/candidates"),
  getRecruiterRegistry: () => apiClient.get("/admin/recruiters"),
  getActivityLog: ({ limit = 50, offset = 0, action = null } = {}) =>
    apiClient.get("/admin/activity-log", {
      params: { limit, offset, ...(action ? { action } : {}) },
    }),

  downloadReportPdf: () =>
    apiClient.get("/admin/report/pdf", { responseType: "blob" }),
};
