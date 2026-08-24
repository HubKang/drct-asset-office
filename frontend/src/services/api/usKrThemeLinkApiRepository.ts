import { apiRequest } from "@/services/api/apiClient";
import type { UsKrLeadAnalysis, UsKrThemeLink, UsKrThemeLinkInput, UsKrThemeLinkOverview, UsKrTodayObservation } from "@/types/usKrThemeLink";

export const usKrThemeLinkApiRepository = {
  overview: () => apiRequest<UsKrThemeLinkOverview>("/us-kr-theme-links/overview", { cache: "no-store" }),
  create: (payload: UsKrThemeLinkInput) => apiRequest<UsKrThemeLink>("/us-kr-theme-links", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: number, payload: Partial<UsKrThemeLinkInput>) => apiRequest<UsKrThemeLink>(`/us-kr-theme-links/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  delete: (id: number) => apiRequest<UsKrThemeLink>(`/us-kr-theme-links/${id}`, { method: "DELETE" }),
  leadAnalysis: (id: number, window: number, usMetric: "theme_strength" | "simple_return") =>
    apiRequest<UsKrLeadAnalysis>(`/us-kr-theme-links/${id}/lead-analysis?window=${window}&us_metric=${usMetric}`, { cache: "no-store" }),
  todayObservation: (window: number, usMetric: "theme_strength" | "simple_return") =>
    apiRequest<UsKrTodayObservation>(`/us-kr-theme-links/today-observation?window=${window}&us_metric=${usMetric}`, { cache: "no-store" }),
};
