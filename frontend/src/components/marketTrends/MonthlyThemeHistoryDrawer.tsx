import { useEffect, useMemo, useRef, useState } from "react";
import NaverStockChartModal, { type NaverStockChartModalData } from "@/components/common/NaverStockChartModal";
import { ThemeLinkedStockChart } from "@/components/marketThemes/MarketThemeDetailDrawer";
import { repositories } from "@/services";
import type { MonthlyThemeHistoryResponse } from "@/types/marketTrend";
import { getNaverChartSessionSidcode, normalizeNaverStockCode } from "@/utils/naverChart";

type ThemeSummary = {
  marketThemeId: number;
  themeName: string;
  themeGroupName: string | null;
};

const historyCache = new Map<number, MonthlyThemeHistoryResponse>();

const heatmapReturnClass = (value: number | null | undefined) => {
  if (value == null || Number.isNaN(Number(value))) return "is-empty";
  const n = Number(value);
  if (n >= 20) return "positive-20";
  if (n >= 15) return "positive-15";
  if (n >= 10) return "positive-10";
  if (n >= 5) return "positive-5";
  if (n > 0) return "positive-near-zero";
  return "neutral";
};

const signedPct = (value: number | null | undefined, digits = 1) =>
  value == null || Number.isNaN(Number(value)) ? "-" : `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(digits)}%`;

const circledCount = (value: number) => {
  const count = Math.max(0, Math.trunc(value));
  if (count >= 1 && count <= 20) return String.fromCodePoint(0x245f + count);
  if (count >= 21 && count <= 35) return String.fromCodePoint(0x3251 + count - 21);
  if (count >= 36 && count <= 50) return String.fromCodePoint(0x32b1 + count - 36);
  return `(${count})`;
};

export default function MonthlyThemeHistoryDrawer({ theme, onClose }: { theme: ThemeSummary; onClose: () => void }) {
  const [data, setData] = useState<MonthlyThemeHistoryResponse | null>(() => historyCache.get(theme.marketThemeId) ?? null);
  const [loading, setLoading] = useState(!historyCache.has(theme.marketThemeId));
  const [error, setError] = useState("");
  const [selectedStockCode, setSelectedStockCode] = useState<string | null>(null);
  const [zoomedChart, setZoomedChart] = useState<NaverStockChartModalData | null>(null);
  const [dayColumnWidth, setDayColumnWidth] = useState(32);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const sidcode = getNaverChartSessionSidcode();

  const load = (useCache = true) => {
    const cached = useCache ? historyCache.get(theme.marketThemeId) : null;
    if (cached) {
      setData(cached);
      setLoading(false);
      setError("");
      return () => undefined;
    }
    const controller = new AbortController();
    setLoading(true);
    setError("");
    repositories.marketTrends.getMonthlyThemeHistory(theme.marketThemeId, controller.signal)
      .then((result) => {
        historyCache.set(theme.marketThemeId, result);
        setData(result);
      })
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name === "AbortError") return;
        setError(reason instanceof Error && reason.message ? reason.message : "테마 수급 이력을 불러오지 못했습니다.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  };

  useEffect(() => {
    setSelectedStockCode(null);
    setZoomedChart(null);
    setData(historyCache.get(theme.marketThemeId) ?? null);
    const cancel = load(true);
    return cancel;
  }, [theme.marketThemeId]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (zoomedChart) setZoomedChart(null);
      else onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose, zoomedChart]);

  useEffect(() => {
    if (!data || !scrollRef.current) return;
    const frame = window.requestAnimationFrame(() => {
      if (scrollRef.current) scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [data, dayColumnWidth, theme.marketThemeId]);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return undefined;
    const updateColumnWidth = () => setDayColumnWidth(Math.max(14, (element.clientWidth - 52) / 35));
    updateColumnWidth();
    if (typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(updateColumnWidth);
    observer.observe(element);
    return () => observer.disconnect();
  }, [data]);

  const eventByDate = useMemo(
    () => new Map((data?.daily_events ?? []).map((event) => [event.date, event])),
    [data],
  );
  const selectedStock = data?.stocks.find((stock) => normalizeNaverStockCode(stock.stock_code) === selectedStockCode) ?? null;

  return (
    <div className="theme-return-drawer-backdrop monthly-theme-history-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <aside className="theme-return-drawer monthly-theme-history-drawer" role="dialog" aria-modal="true" aria-labelledby="monthly-theme-history-title">
        <header className="theme-return-drawer-header">
          <div>
            <span>수급 테마 상세</span>
            <h3 id="monthly-theme-history-title">{theme.themeName}</h3>
            <p>{theme.themeGroupName ? `${theme.themeGroupName} · ` : ""}{data ? `최근 수급 출현 ${data.appearance_days}일 · 출현 종목 ${data.unique_stock_count}개` : "저장 수급 이력 조회"}</p>
          </div>
          <button ref={closeButtonRef} type="button" className="btn btn-secondary btn-table-sm" onClick={onClose} aria-label="수급 테마 상세 닫기">닫기</button>
        </header>

        <div className="theme-return-drawer-body monthly-theme-history-body">
          {loading ? <div className="monthly-theme-history-state">수급 테마 이력을 불러오는 중입니다.</div> : null}
          {error ? (
            <div className="monthly-theme-history-state is-error" role="alert">
              <span>{error}</span>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => load(false)}>다시 시도</button>
            </div>
          ) : null}
          {!loading && !error && data ? (
            <>
              <section className="monthly-theme-history-chart-section">
                <div className="monthly-theme-history-section-head">
                  <div>
                    <h4>일별 테마 수급 등락률</h4>
                    <p>{data.period.from_date} ~ {data.period.to_date} · 좌우로 스크롤해 전체 저장 이력을 확인할 수 있습니다.</p>
                  </div>
                  {selectedStock ? (
                    <button type="button" className="monthly-theme-history-selection" onClick={() => setSelectedStockCode(null)}>
                      선택 종목: {selectedStock.stock_name} <span aria-hidden="true">×</span>
                    </button>
                  ) : null}
                </div>
                <div className="monthly-supply-heatmap-legend monthly-theme-history-legend">
                  <span><i className="neutral" />0%</span><span><i className="positive-5" />+5%</span>
                  <span><i className="positive-10" />+10%</span><span><i className="positive-15" />+15%</span>
                  <span><i className="positive-20" />+20% 이상</span>
                </div>
                <div ref={scrollRef} className="monthly-theme-history-chart-scroll">
                  <div className="monthly-theme-history-chart" style={{ gridTemplateColumns: `repeat(${Math.max(data.calendar_dates.length, 1)}, minmax(${dayColumnWidth}px, 1fr))` }}>
                    <div className="monthly-theme-history-gridline line-30"><span>30%</span></div>
                    <div className="monthly-theme-history-gridline line-20"><span>20%</span></div>
                    <div className="monthly-theme-history-gridline line-10"><span>10%</span></div>
                    <div className="monthly-theme-history-gridline line-0"><span>0</span></div>
                    {data.calendar_dates.map((date) => {
                      const event = eventByDate.get(date);
                      const value = event?.theme_return ?? null;
                      const includesSelected = !selectedStockCode || Boolean(event?.stock_codes.some((code) => normalizeNaverStockCode(code) === selectedStockCode));
                      const names = event?.stock_names ?? [];
                      const tooltip = event
                        ? `${date}\n테마 등락률 ${signedPct(value)}\n출현 종목 ${event.stock_count}개${names.length ? `\n${names.slice(0, 3).join("\n")}${names.length > 3 ? `\n외 ${names.length - 3}종목` : ""}` : ""}`
                        : `${date}\n수급 이벤트 없음`;
                      return (
                        <div key={date} className="monthly-theme-history-day" title={tooltip}>
                          <div className="monthly-theme-history-bar-slot">
                            {event ? (
                              <div
                                className={`monthly-theme-history-bar ${heatmapReturnClass(value)}${includesSelected ? "" : " is-dimmed"}`}
                                style={{ height: `${Math.max(3, Math.min(100, Math.max(0, Number(value ?? 0)) / 30 * 100))}%` }}
                              >
                                <span className="monthly-theme-history-bar-value">{value == null ? "-" : `${value >= 0 ? "+" : ""}${value.toFixed(1)}`}</span>
                                <span className="monthly-theme-history-bar-count" aria-label={`출현 종목 ${event.stock_count}개`} title={`출현 종목 ${event.stock_count}개`}>
                                  {circledCount(event.stock_count)}
                                </span>
                              </div>
                            ) : null}
                          </div>
                          <time dateTime={date}>{date.slice(5).replace("-", "/")}</time>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </section>

              <section className="monthly-theme-history-stock-section">
                <div className="monthly-theme-history-section-head">
                  <div><h4>출현 종목</h4><p>저장된 테마 이벤트에 실제 포함된 종목이며, 출현 횟수와 최근 출현일 순입니다.</p></div>
                </div>
                {data.stocks.length ? (
                  <div className="monthly-theme-history-stock-list" role="table" aria-label={`${data.theme.name} 출현 종목`}>
                    <div className="monthly-theme-history-stock-header" role="row">
                      <span>종목명</span><span>등락률</span><span>출현횟수</span><span>일봉</span><span>주봉</span><span>월봉</span>
                    </div>
                    {data.stocks.map((stock) => {
                      const code = normalizeNaverStockCode(stock.stock_code);
                      const selected = selectedStockCode === code;
                      return (
                        <div key={`${stock.stock_id}-${stock.stock_code}`} className={`monthly-theme-history-stock-row${selected ? " is-selected" : ""}`} role="row">
                          <button type="button" className="monthly-theme-history-stock-info" onClick={() => setSelectedStockCode(selected ? null : code)} aria-pressed={selected}>
                            <span className="stock-cell"><strong>{stock.stock_name}</strong><small>{code || stock.stock_code || "-"}</small></span>
                            <span className={stock.latest_change_rate != null && stock.latest_change_rate > 0 ? "rate-positive" : stock.latest_change_rate != null && stock.latest_change_rate < 0 ? "rate-negative" : ""}>{signedPct(stock.latest_change_rate)}</span>
                            <span><strong>{stock.appearance_count}회</strong><small>최근 {stock.latest_occurrence_date ?? "-"}</small></span>
                          </button>
                          {(["day", "week", "month"] as const).map((period, index) => (
                            <div className="monthly-theme-history-chart-cell" role="cell" key={period} onClick={(event) => event.stopPropagation()}>
                              <ThemeLinkedStockChart stockCode={code} stockName={stock.stock_name} period={period} label={["일봉", "주봉", "월봉"][index]} sidcode={sidcode} onOpen={setZoomedChart} variant="detail" />
                            </div>
                          ))}
                        </div>
                      );
                    })}
                  </div>
                ) : <div className="monthly-theme-history-state">저장된 출현 종목이 없습니다.</div>}
              </section>
            </>
          ) : null}
        </div>
      </aside>
      {zoomedChart ? <NaverStockChartModal chart={zoomedChart} onClose={() => setZoomedChart(null)} /> : null}
    </div>
  );
}
