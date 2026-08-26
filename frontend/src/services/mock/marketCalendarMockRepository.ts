import type {
  MarketCalendarDailyResponse,
  MarketCalendarEvent,
  MarketCalendarEventInput,
  MarketCalendarMonthlyParams,
  MarketCalendarMonthlyResponse,
} from "@/types/marketCalendar";

let nextEventId = 1;
let events: MarketCalendarEvent[] = [];

const overlaps = (event: MarketCalendarEvent, start: string, end: string) =>
  event.is_active === 1 && event.start_date <= end && event.end_date >= start;

const toEvent = (payload: MarketCalendarEventInput, id = nextEventId++): MarketCalendarEvent => ({
  id,
  period_type: payload.period_type ?? "D",
  start_date: payload.start_date,
  end_date: payload.end_date,
  theme_id: payload.theme_id ?? null,
  theme_name: payload.theme_id ? "Mock Theme" : null,
  theme_group_id: null,
  theme_group_name: null,
  title: payload.title,
  summary: payload.summary ?? null,
  news_url: payload.news_url ?? null,
  event_type: payload.event_type ?? "news",
  importance: payload.importance ?? "medium",
  memo: payload.memo ?? null,
  is_active: 1,
  stocks: [],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
});

export const marketCalendarMockRepository = {
  listMonthly: async (params: MarketCalendarMonthlyParams): Promise<MarketCalendarMonthlyResponse> => {
    const [year, month] = params.month.split("-").map(Number);
    const startDate = `${params.month}-01`;
    const endDate = `${params.month}-${String(new Date(year, month, 0).getDate()).padStart(2, "0")}`;
    return { month: params.month, start_date: startDate, end_date: endDate, events: events.filter((event) => overlaps(event, startDate, endDate)) };
  },
  listDaily: async (date: string): Promise<MarketCalendarDailyResponse> => ({
    date,
    events: events.filter((event) => event.period_type === "D" && overlaps(event, date, date)),
  }),
  create: async (payload: MarketCalendarEventInput): Promise<MarketCalendarEvent> => {
    const event = toEvent(payload);
    events = [event, ...events];
    return event;
  },
  update: async (eventId: number, payload: MarketCalendarEventInput): Promise<MarketCalendarEvent> => {
    const updated = toEvent(payload, eventId);
    events = events.map((event) => (event.id === eventId ? { ...updated, created_at: event.created_at } : event));
    return updated;
  },
  delete: async (eventId: number): Promise<{ success: boolean; event_id: number }> => {
    events = events.map((event) => (event.id === eventId ? { ...event, is_active: 0 } : event));
    return { success: true, event_id: eventId };
  },
};
