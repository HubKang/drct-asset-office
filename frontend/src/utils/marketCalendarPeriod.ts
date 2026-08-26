import type { MarketCalendarEvent, MarketCalendarPeriodType } from "@/types/marketCalendar";

export const calendarMonthStart = (month: string) => `${month}-01`;

export const calendarMonthEnd = (month: string) => {
  const [year, monthNumber] = month.split("-").map(Number);
  const lastDay = new Date(year, monthNumber, 0).getDate();
  return `${month}-${String(lastDay).padStart(2, "0")}`;
};

export const normalizeCalendarDates = (periodType: MarketCalendarPeriodType, startValue: string, endValue: string) => {
  if (periodType === "D") return { start_date: startValue, end_date: endValue };
  return { start_date: calendarMonthStart(startValue), end_date: calendarMonthEnd(endValue) };
};

export const formatCalendarPeriod = (event: Pick<MarketCalendarEvent, "period_type" | "start_date" | "end_date">) => {
  if (event.period_type === "D") {
    return event.start_date === event.end_date ? event.start_date : `${event.start_date} ~ ${event.end_date}`;
  }
  const startMonth = event.start_date.slice(0, 7);
  const endMonth = event.end_date.slice(0, 7);
  const [startYear, startMonthNumber] = startMonth.split("-").map(Number);
  const [endYear, endMonthNumber] = endMonth.split("-").map(Number);
  if (startYear === endYear && startMonthNumber === 1 && endMonthNumber === 12) return "연내";
  if (startMonth === endMonth) return `${startMonthNumber}월 내`;
  if (startYear === endYear) return `${startMonthNumber}~${endMonthNumber}월`;
  return `${String(startYear).slice(2)}.${String(startMonthNumber).padStart(2, "0")} ~ ${String(endYear).slice(2)}.${String(endMonthNumber).padStart(2, "0")}`;
};
