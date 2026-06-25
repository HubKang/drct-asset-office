import { apiRequest } from "@/services/api/apiClient";
import type {
  MarketCalendarDailyResponse,
  MarketCalendarEvent,
  MarketCalendarEventInput,
  MarketCalendarMonthlyParams,
  MarketCalendarMonthlyResponse,
} from "@/types/marketCalendar";

export const marketCalendarApiRepository = {
  listMonthly: (params: MarketCalendarMonthlyParams) => {
    const search = new URLSearchParams();
    search.set("month", params.month);
    if (params.theme_group_id !== undefined) search.set("theme_group_id", String(params.theme_group_id));
    if (params.theme_id !== undefined) search.set("theme_id", String(params.theme_id));
    if (params.keyword) search.set("keyword", params.keyword);
    if (params.event_type) search.set("event_type", params.event_type);
    return apiRequest<MarketCalendarMonthlyResponse>(`/market-calendar/events/monthly?${search.toString()}`);
  },
  listDaily: (date: string) =>
    apiRequest<MarketCalendarDailyResponse>(`/market-calendar/events/daily?date=${encodeURIComponent(date)}`),
  create: (payload: MarketCalendarEventInput) =>
    apiRequest<MarketCalendarEvent>("/market-calendar/events", { method: "POST", body: JSON.stringify(payload) }),
  update: (eventId: number, payload: MarketCalendarEventInput) =>
    apiRequest<MarketCalendarEvent>(`/market-calendar/events/${eventId}`, { method: "PUT", body: JSON.stringify(payload) }),
  delete: (eventId: number) =>
    apiRequest<{ success: boolean; event_id: number }>(`/market-calendar/events/${eventId}`, { method: "DELETE" }),
};
