import { apiRequest } from "@/services/api/apiClient";
import type {
  TelegramCollectAllResult,
  TelegramCollectResult,
  TelegramDailySummary,
  TelegramItemListResponse,
  TelegramItemSummarizeResult,
  TelegramSource,
  TelegramSourceConnectionTest,
} from "@/types/telegram";

export const telegramApiRepository = {
  listSources: (includeDeleted = false) => apiRequest<TelegramSource[]>(`/telegram/sources?include_deleted=${includeDeleted ? "true" : "false"}`),
  createSource: (payload: { source_name: string; channel_username: string; channel_title?: string; description?: string; is_active?: boolean; memo?: string }) =>
    apiRequest<TelegramSource>("/telegram/sources", { method: "POST", body: JSON.stringify(payload) }),
  updateSource: (sourceId: number, payload: Record<string, unknown>) =>
    apiRequest<TelegramSource>(`/telegram/sources/${sourceId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteSource: (sourceId: number) => apiRequest<{ success: boolean }>(`/telegram/sources/${sourceId}`, { method: "DELETE" }),
  testSourceConnection: (sourceId: number) =>
    apiRequest<TelegramSourceConnectionTest>(`/telegram/sources/${sourceId}/test-connection`, { method: "POST" }),
  collectByDate: (payload: { source_id: number; target_date: string; summarize_new_items: boolean; include_notice: boolean; include_advertisement: boolean }) =>
    apiRequest<TelegramCollectResult>("/telegram/collect/date", { method: "POST", body: JSON.stringify(payload) }),
  collectAllByDate: (payload: { target_date: string; summarize_new_items: boolean; include_notice: boolean; include_advertisement: boolean }) =>
    apiRequest<TelegramCollectAllResult>("/telegram/collect/date/all", { method: "POST", body: JSON.stringify(payload) }),
  listItems: (params: Record<string, string | number | undefined>) => {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && String(v).trim() !== "") search.set(k, String(v));
    });
    return apiRequest<TelegramItemListResponse>(`/telegram/items?${search.toString()}`);
  },
  summarizeItem: (itemId: number) =>
    apiRequest<TelegramItemSummarizeResult>(`/telegram/items/${itemId}/summarize`, { method: "POST" }),
  deleteItems: (itemIds: number[]) =>
    apiRequest<{ requested_count: number; deleted_count: number }>("/telegram/items/delete-selected", {
      method: "POST",
      body: JSON.stringify({ item_ids: itemIds }),
    }),
  generateDailySummary: (payload: { target_date: string; source_id: number | null }) =>
    apiRequest<TelegramDailySummary>("/telegram/daily-summaries/generate", { method: "POST", body: JSON.stringify(payload) }),
};
