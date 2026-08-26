export type MarketCalendarImportance = "high" | "medium" | "low";
export type MarketCalendarEventType = "news" | "policy" | "issue" | "earnings" | "disclosure" | "supply" | "other";
export type MarketCalendarPeriodType = "D" | "M";

export type MarketCalendarStock = {
  stock_id: number;
  stock_code: string | null;
  stock_name: string | null;
};

export type MarketCalendarEvent = {
  id: number;
  period_type: MarketCalendarPeriodType;
  start_date: string;
  end_date: string;
  theme_id: number | null;
  theme_name: string | null;
  theme_group_id?: number | null;
  theme_group_name?: string | null;
  title: string;
  summary?: string | null;
  news_url?: string | null;
  event_type: MarketCalendarEventType;
  importance: MarketCalendarImportance;
  memo?: string | null;
  is_active: number;
  stocks: MarketCalendarStock[];
  created_at: string;
  updated_at: string;
};

export type MarketCalendarEventInput = {
  period_type?: MarketCalendarPeriodType;
  start_date: string;
  end_date: string;
  theme_id?: number | null;
  title: string;
  summary?: string | null;
  news_url?: string | null;
  event_type?: MarketCalendarEventType;
  importance?: MarketCalendarImportance;
  memo?: string | null;
  stock_ids?: number[];
};

export type MarketCalendarMonthlyParams = {
  month: string;
  theme_group_id?: number;
  theme_id?: number;
  keyword?: string;
  event_type?: MarketCalendarEventType;
};

export type MarketCalendarMonthlyResponse = {
  month: string;
  start_date: string;
  end_date: string;
  events: MarketCalendarEvent[];
};

export type MarketCalendarDailyResponse = {
  date: string;
  events: MarketCalendarEvent[];
};
