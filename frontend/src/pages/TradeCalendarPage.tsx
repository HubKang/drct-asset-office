import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type {
  TradeCalendarDaySummary,
  TradeJournal,
  TradeMonthlyStatistics,
} from "@/types/tradeJournal";

type CalendarCell = {
  date: Date;
  dateKey: string;
  inMonth: boolean;
};

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

const pad2 = (value: number): string => String(value).padStart(2, "0");
const toDateKey = (date: Date): string => `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
const toMonthKey = (date: Date): string => `${date.getFullYear()}-${pad2(date.getMonth() + 1)}`;
const formatWon = (value: number): string => `${value.toLocaleString("ko-KR")}원`;
const formatRate = (value?: number | null): string => `${Number(value ?? 0).toFixed(2)}%`;

const resultTypeLabel = (value?: string | null): string => {
  if (value === "profit") return "익절";
  if (value === "loss") return "손절";
  if (value === "break_even") return "본전";
  return "보유중";
};

function buildCalendarCells(selectedMonth: Date): CalendarCell[] {
  const firstDay = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth(), 1);
  const lastDay = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() + 1, 0);
  const start = new Date(firstDay);
  start.setDate(firstDay.getDate() - firstDay.getDay());
  const end = new Date(lastDay);
  end.setDate(lastDay.getDate() + (6 - lastDay.getDay()));

  const result: CalendarCell[] = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    result.push({
      date: new Date(cursor),
      dateKey: toDateKey(cursor),
      inMonth: cursor.getMonth() === selectedMonth.getMonth(),
    });
    cursor.setDate(cursor.getDate() + 1);
  }
  return result;
}

export default function TradeCalendarPage() {
  const now = useMemo(() => new Date(), []);
  const currentMonthKey = useMemo(() => toMonthKey(now), [now]);
  const [selectedMonth, setSelectedMonth] = useState<Date>(new Date());
  const [selectedDate, setSelectedDate] = useState<string>(toDateKey(now));
  const [monthlySummary, setMonthlySummary] = useState<TradeCalendarDaySummary[]>([]);
  const [dailyItems, setDailyItems] = useState<TradeJournal[]>([]);
  const [monthlyStats, setMonthlyStats] = useState<TradeMonthlyStatistics[]>([]);
  const [statsTotal, setStatsTotal] = useState<number>(0);
  const [statsPage, setStatsPage] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [statsRange, setStatsRange] = useState<{ start_month: string; end_month: string }>({
    start_month: currentMonthKey,
    end_month: currentMonthKey,
  });

  const pageSize = 10;
  const monthKey = useMemo(() => toMonthKey(selectedMonth), [selectedMonth]);
  const todayKey = useMemo(() => toDateKey(new Date()), []);
  const cells = useMemo(() => buildCalendarCells(selectedMonth), [selectedMonth]);
  const totalPages = Math.max(1, Math.ceil((statsTotal || 0) / pageSize));
  const monthlyStatsProfitSum = useMemo(
    () => monthlyStats.reduce((acc, item) => acc + Number(item.realized_profit_sum ?? 0), 0),
    [monthlyStats]
  );
  const dailyProfitSum = useMemo(
    () => dailyItems.reduce((acc, item) => acc + Number(item.realized_profit ?? 0), 0),
    [dailyItems]
  );

  const summaryMap = useMemo(() => {
    const map = new Map<string, TradeCalendarDaySummary>();
    monthlySummary.forEach((item) => map.set(item.trade_date, item));
    return map;
  }, [monthlySummary]);

  const loadMonthlySummary = async (month: string) => {
    const items = await repositories.tradeJournals.fetchTradeCalendarMonthly(month);
    setMonthlySummary(items ?? []);
  };

  const loadDailyItems = async (date: string) => {
    const result = await repositories.tradeJournals.fetchTradeCalendarDaily(date);
    setDailyItems(result.items ?? []);
  };

  const loadMonthlyStats = async (page: number, startMonth?: string, endMonth?: string) => {
    const result = await repositories.tradeJournals.fetchTradeMonthlyStatistics({
      page,
      page_size: pageSize,
      start_month: startMonth || undefined,
      end_month: endMonth || undefined,
    });
    setMonthlyStats(result.items ?? []);
    setStatsTotal(result.total ?? 0);
    setStatsPage(result.page ?? page);
  };

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      setError("");
      try {
        await Promise.all([loadMonthlySummary(monthKey), loadDailyItems(selectedDate), loadMonthlyStats(1)]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "매매달력 데이터를 불러오지 못했습니다.");
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, []);

  const handleMoveMonth = async (offset: number) => {
    const next = new Date(selectedMonth.getFullYear(), selectedMonth.getMonth() + offset, 1);
    setSelectedMonth(next);
    setLoading(true);
    setError("");
    try {
      await loadMonthlySummary(toMonthKey(next));
    } catch (e) {
      setError(e instanceof Error ? e.message : "월 이동 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleToday = async () => {
    const now = new Date();
    const dateKey = toDateKey(now);
    setSelectedMonth(now);
    setSelectedDate(dateKey);
    setLoading(true);
    setError("");
    try {
      await Promise.all([loadMonthlySummary(toMonthKey(now)), loadDailyItems(dateKey)]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "오늘 날짜 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDate = async (dateKey: string) => {
    setSelectedDate(dateKey);
    setLoading(true);
    setError("");
    try {
      await loadDailyItems(dateKey);
    } catch (e) {
      setError(e instanceof Error ? e.message : "선택 날짜 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleSearchStats = async () => {
    setLoading(true);
    setError("");
    try {
      await loadMonthlyStats(1, statsRange.start_month, statsRange.end_month);
    } catch (e) {
      setError(e instanceof Error ? e.message : "월별 집계 조회 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = async (nextPage: number) => {
    if (nextPage < 1 || nextPage > totalPages) return;
    setLoading(true);
    setError("");
    try {
      await loadMonthlyStats(nextPage, statsRange.start_month, statsRange.end_month);
    } catch (e) {
      setError(e instanceof Error ? e.message : "월별 집계 페이지 이동 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="매매달력"
        description="월간 달력, 월별 집계, 선택 날짜 매매일지를 한 화면에서 확인합니다."
      />
      {error ? <p className="inline-result inline-error">{error}</p> : null}

      <div className="trade-calendar-top">
        <SectionCard title="월간 매매달력">
          <div className="trade-calendar-toolbar">
            <button type="button" className="btn btn-secondary" onClick={() => void handleMoveMonth(-1)}>
              이전 달
            </button>
            <strong>
              {selectedMonth.getFullYear()}년 {selectedMonth.getMonth() + 1}월
            </strong>
            <button type="button" className="btn btn-secondary" onClick={() => void handleMoveMonth(1)}>
              다음 달
            </button>
            <button type="button" className="btn btn-primary" onClick={() => void handleToday()}>
              오늘
            </button>
          </div>
          <div className="trade-calendar-weekdays">
            {WEEKDAYS.map((day) => (
              <div key={day} className="trade-calendar-weekday">
                {day}
              </div>
            ))}
          </div>
          <div className="trade-calendar-grid">
            {cells.map((cell) => {
              const summary = summaryMap.get(cell.dateKey);
              const isSelected = selectedDate === cell.dateKey;
              const isToday = todayKey === cell.dateKey;
              const signClass =
                !summary || summary.realized_profit_sum === 0 ? "" : summary.realized_profit_sum > 0 ? "plus" : "minus";
              const toneClass =
                !summary || summary.realized_profit_sum === 0
                  ? ""
                  : summary.realized_profit_sum > 0
                    ? "profit-positive"
                    : "profit-negative";

              return (
                <button
                  key={cell.dateKey}
                  type="button"
                  className={[
                    "trade-calendar-cell",
                    cell.inMonth ? "" : "out-month",
                    isSelected ? "selected" : "",
                    isToday ? "today" : "",
                    toneClass,
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  onClick={() => void handleSelectDate(cell.dateKey)}
                >
                  <div className="date">{cell.date.getDate()}</div>
                  {summary ? (
                    <>
                      <div className="count">{summary.trade_count}종목</div>
                      <div className={`profit ${signClass}`}>
                        {summary.realized_profit_sum > 0 ? "+" : ""}
                        {formatWon(summary.realized_profit_sum)}
                      </div>
                    </>
                  ) : null}
                </button>
              );
            })}
          </div>
        </SectionCard>

        <SectionCard title="월별 집계 목록">
          <div className="trade-calendar-stats-filter">
            <input
              className="input-control"
              type="month"
              value={statsRange.start_month}
              onChange={(event) => setStatsRange((prev) => ({ ...prev, start_month: event.target.value }))}
            />
            <input
              className="input-control"
              type="month"
              value={statsRange.end_month}
              onChange={(event) => setStatsRange((prev) => ({ ...prev, end_month: event.target.value }))}
            />
            <button type="button" className="btn btn-primary" onClick={() => void handleSearchStats()}>
              조회
            </button>
          </div>
          <div className="table-shell">
            <table className="data-table compact-table">
              <thead>
                <tr>
                  <th>매매월</th>
                  <th>매매건수</th>
                  <th>익절건수</th>
                  <th>손절건수</th>
                  <th>승률</th>
                  <th>실현손익</th>
                  <th>평균수익률</th>
                </tr>
              </thead>
              <tbody>
                {monthlyStats.map((item) => (
                  <tr key={item.trade_month}>
                    <td>{item.trade_month}</td>
                    <td>{item.trade_count}</td>
                    <td>{item.profit_count}</td>
                    <td>{item.loss_count}</td>
                    <td>{Number(item.win_rate ?? 0).toFixed(1)}%</td>
                    <td>{formatWon(Number(item.realized_profit_sum ?? 0))}</td>
                    <td>{Number(item.avg_profit_rate ?? 0).toFixed(2)}%</td>
                  </tr>
                ))}
                {monthlyStats.length > 0 ? (
                  <tr className="trade-journal-summary-row">
                    <td colSpan={5}>실현손익 합계</td>
                    <td>{formatWon(monthlyStatsProfitSum)}</td>
                    <td>-</td>
                  </tr>
                ) : null}
                {monthlyStats.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-muted">
                      집계 데이터가 없습니다.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <div className="trade-calendar-pager">
            <button
              type="button"
              className="btn btn-secondary"
              disabled={statsPage <= 1}
              onClick={() => void handlePageChange(statsPage - 1)}
            >
              이전
            </button>
            <span>
              {statsPage} / {totalPages}
            </span>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={statsPage >= totalPages}
              onClick={() => void handlePageChange(statsPage + 1)}
            >
              다음
            </button>
          </div>
        </SectionCard>
      </div>

      <SectionCard title={`선택 날짜 매매일지 목록 (${selectedDate})`}>
        {loading ? <p className="text-muted">조회 중...</p> : null}
        <div className="table-shell">
          <table className="data-table compact-table">
            <thead>
              <tr>
                <th>매수일자</th>
                <th>매도일자</th>
                <th>종목테마</th>
                <th>매매기법명</th>
                <th>종목명</th>
                <th>익절/손절</th>
                <th>수익률</th>
                <th>실현손익</th>
                <th>이미지수</th>
              </tr>
            </thead>
            <tbody>
              {dailyItems.map((item) => (
                <tr key={item.id}>
                  <td>{item.buy_date}</td>
                  <td>{item.sell_date || "-"}</td>
                  <td title={item.stock_theme || "-"}>{item.stock_theme || "-"}</td>
                  <td title={item.trade_method_name || "-"}>{item.trade_method_name || "-"}</td>
                  <td title={item.stock_name}>{item.stock_name}</td>
                  <td>{resultTypeLabel(item.result_type)}</td>
                  <td>{formatRate(item.profit_rate)}</td>
                  <td>{formatWon(Number(item.realized_profit ?? 0))}</td>
                  <td>{item.image_count ?? 0}개</td>
                </tr>
              ))}
              {dailyItems.length > 0 ? (
                <tr className="trade-journal-summary-row">
                  <td colSpan={7}>실현손익 합계</td>
                  <td>{formatWon(dailyProfitSum)}</td>
                  <td>-</td>
                </tr>
              ) : null}
              {dailyItems.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-muted">
                    선택한 날짜에 매매일지가 없습니다.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}
