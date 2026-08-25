import { apiClient } from "./client";

export const adminApi = {
  getStats: () => apiClient.get("/admin/stats"),
  getVisibilityGap: () => apiClient.get("/admin/visibility-gap"),
  getVisibilityGapTimeseries: (bucket = "week") =>
    apiClient.get("/admin/visibility-gap/timeseries", { params: { bucket } }),
  getDiversityReport: () => apiClient.get("/admin/diversity-report"),
  getRecruiterBiasScores: () => apiClient.get("/admin/recruiters/bias-scores"),
  downloadReportPdf: () =>
    apiClient.get("/admin/report/pdf", { responseType: "blob" }),
};
