import { apiRequest } from "@/services/api/apiClient";
import type { DashboardReadinessResponse, DashboardRecentActivitiesResponse } from "@/types/dashboard";

export const dashboardApiRepository = {
  readiness: () => apiRequest<DashboardReadinessResponse>("/dashboard/readiness", { cache: "no-store" }),
  recentActivities: (days = 30, limit = 5) =>
    apiRequest<DashboardRecentActivitiesResponse>(`/dashboard/recent-activities?days=${days}&limit=${limit}`),
};
