import { apiRequest } from "@/services/api/apiClient";
import type { DashboardRecentActivitiesResponse } from "@/types/dashboard";

export const dashboardApiRepository = {
  recentActivities: (days = 30, limit = 5) =>
    apiRequest<DashboardRecentActivitiesResponse>(`/dashboard/recent-activities?days=${days}&limit=${limit}`),
};
