import { apiRequest } from "@/services/api/apiClient";
import type {
  TelegramAuthStartResult, TelegramAuthStatus, TelegramAuthVerifyResult,
  TelegramCollectAllResult, TelegramCollectResult, TelegramItemListResponse,
  TelegramSource, TelegramSourceConnectionTest, TelegramSummarizeResult,
} from "@/types/telegram";

export const telegramApiRepository = {
  getAuthStatus: () => apiRequest<TelegramAuthStatus>("/telegram/auth/status"),
  startAuth: () => apiRequest<TelegramAuthStartResult>("/telegram/auth/start", { method: "POST" }),
  verifyAuthCode: (code: string) => apiRequest<TelegramAuthVerifyResult>("/telegram/auth/verify-code", { method: "POST", body: JSON.stringify({ code }) }),
  verifyAuthPassword: (password: string) => apiRequest<TelegramAuthVerifyResult>("/telegram/auth/verify-password", { method: "POST", body: JSON.stringify({ password }) }),
  listSources: (includeDeleted = false) => apiRequest<TelegramSource[]>(`/telegram/sources?include_deleted=${includeDeleted}`),
  createSource: (payload: { source_name: string; channel_username: string; channel_title?: string; description?: string; is_active?: boolean; memo?: string }) =>
    apiRequest<TelegramSource>("/telegram/sources", { method: "POST", body: JSON.stringify(payload) }),
  updateSource: (sourceId: number, payload: Record<string, unknown>) =>
    apiRequest<TelegramSource>(`/telegram/sources/${sourceId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteSource: (sourceId: number) => apiRequest<{ success: boolean }>(`/telegram/sources/${sourceId}`, { method: "DELETE" }),
  testSourceConnection: (sourceId: number) => apiRequest<TelegramSourceConnectionTest>(`/telegram/sources/${sourceId}/test-connection`, { method: "POST" }),
  collectByDate: (payload: { source_id: number; target_date: string }) =>
    apiRequest<TelegramCollectResult>("/telegram/collect/date", { method: "POST", body: JSON.stringify(payload) }),
  collectAllByDate: (payload: { target_date: string }) =>
    apiRequest<TelegramCollectAllResult>("/telegram/collect/date/all", { method: "POST", body: JSON.stringify(payload) }),
  listItems: (params: Record<string, string | number | undefined>) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && String(value).trim()) search.set(key, String(value));
    });
    return apiRequest<TelegramItemListResponse>(`/telegram/items?${search.toString()}`);
  },
  deleteItems: (itemIds: number[]) => apiRequest<{ requested_count: number; deleted_count: number }>("/telegram/items/delete-selected", {
    method: "POST", body: JSON.stringify({ item_ids: itemIds }),
  }),
  summarizeItems: (itemIds: number[]) => apiRequest<TelegramSummarizeResult>("/telegram/items/summarize", {
    method: "POST", body: JSON.stringify({ item_ids: itemIds }),
  }),
};
