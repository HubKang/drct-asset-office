import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { RefreshCw, Search } from "lucide-react";
import SectionCard from "@/components/common/SectionCard";
import UsThemeDetailDrawer from "@/components/marketThemes/UsThemeDetailDrawer";
import { repositories } from "@/services";
import type { UsStock } from "@/types/usStock";
import type { UsStockCharts, UsTheme, UsThemeGroup, UsThemeStock, UsThemeStockRole, UsThemeSummary, UsThemeTrend, UsThemeTrendItem } from "@/types/usMarketTheme";
import { getThemeReturnHeatmapColor, getThemeReturnTextColor, THEME_RETURN_HEATMAP_COLORS, THEME_RETURN_HEATMAP_LABELS } from "@/utils/marketThemeReturnColor";

type Props = { activeTab: "themes" | "mapping"; onSummaryChange: (summary: UsThemeSummary) => void };
type ViewMode = "group" | "theme" | "trend";
type EditTarget = { kind: "group"; value: UsThemeGroup | null } | { kind: "theme"; value: UsTheme | null };
const chartCache = new Map<number, Promise<UsStockCharts>>();

const pct = (value: number | null | undefined) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
const US_TREND_COLORS = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2", "#4f46e5", "#be123c", "#65a30d", "#7c3aed", "#0f766e", "#c2410c"];
const compactValue = (value: number | null | undefined) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
const trendColor = (themeId: number) => US_TREND_COLORS[(Math.max(1, Math.abs(themeId)) - 1) % US_TREND_COLORS.length];
const valueTone = (value: number | null | undefined) => value == null || value === 0 ? "" : value > 0 ? "value-up" : "value-down";
const linePath = (points: Array<{ x: number; y: number }>) => points.map((point, index) => `${index ? "L" : "M"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
const lineSegments = (points: Array<{ x: number; y: number } | null>) => {
  const segments: Array<Array<{ x: number; y: number }>> = []; let current: Array<{ x: number; y: number }> = [];
  points.forEach((point) => { if (point) current.push(point); else if (current.length) { segments.push(current); current = []; } });
  if (current.length) segments.push(current); return segments;
};

function UsThemeIntegratedLineChart({ themes, dates, metric, period, onOpen }: { themes: UsThemeTrendItem[]; dates: string[]; metric: "theme_strength" | "simple_return"; period: 20 | 30 | 60; onOpen: (themeId: number, date: string) => void }) {
  const [hoveredThemeId, setHoveredThemeId] = useState<number | null>(null);
  const width = 840, height = 500, margin = { top: 24, right: 18, bottom: 34, left: 44 };
  const innerWidth = width - margin.left - margin.right, innerHeight = height - margin.top - margin.bottom;
  const series = themes.map((theme) => {
    const pointMap = new Map(theme.points.map((point) => [point.trade_date, point]));
    const rollingMetric = metric === "theme_strength" ? "rolling_30d_theme_strength" : "rolling_30d_simple_return";
    const values = dates.map((date) => pointMap.get(date)?.[rollingMetric] ?? null);
    const latestDaily = [...dates].reverse().map((date) => pointMap.get(date)?.[metric]).find((value) => value != null) ?? null;
    return { ...theme, color: trendColor(theme.theme_id), values, latestDaily, cumulative: [...values].reverse().find((value) => value != null) ?? null };
  });
  const allValues = series.flatMap((item) => item.values.filter((value): value is number => value != null));
  if (!allValues.length || !dates.length) return <div className="theme-return-line-empty">선그래프로 표시할 거래일 데이터가 없습니다.</div>;
  const rawMin = Math.min(...allValues), rawMax = Math.max(...allValues);
  const yMin = rawMin < -30 ? Math.floor(rawMin / 10) * 10 : -30;
  const yMax = rawMax > 30 ? Math.ceil(rawMax / 10) * 10 : 30;
  const xScale = (index: number) => margin.left + (dates.length <= 1 ? innerWidth / 2 : innerWidth * index / (dates.length - 1));
  const yScale = (value: number) => margin.top + innerHeight - ((value - yMin) / Math.max(yMax - yMin, 1)) * innerHeight;
  const yTicks = Array.from({ length: Math.floor((yMax - yMin) / 10) + 1 }, (_, index) => yMin + index * 10);
  const tickStep = Math.max(1, Math.ceil(dates.length / 7));
  const xTickIndexes = dates.map((_, index) => index).filter((index) => index === 0 || index === dates.length - 1 || index % tickStep === 0);
  const style = { "--theme-return-line-chart-height": `${height}px` } as CSSProperties;
  return <div className="theme-return-line-panel us-theme-integrated-line" style={style}>
    <div className="theme-return-line-header"><div><strong>테마별 30일 누적 등락률 선그래프</strong><span>각 날짜 기준 최근 30일 일별 테마 값을 단순 합산해 비교합니다. 히트맵은 기존처럼 일별 값을 표시합니다.</span></div></div>
    <div className="theme-return-line-body"><div className="theme-return-line-chart"><svg className="theme-return-line-svg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={`미국 테마 ${period}거래일 30일 누적 선그래프`}>
      {yTicks.map((tick) => { const y = yScale(tick); return <g key={tick}><line className="theme-return-line-grid" x1={margin.left} x2={width - margin.right} y1={y} y2={y}/><text className="theme-return-line-axis-label theme-return-line-y-label" x={margin.left - 9} y={y + 3} textAnchor="end">{compactValue(tick)}%</text></g>; })}
      {xTickIndexes.map((index) => { const date = dates[index], x = xScale(index), monthChanged = index === 0 || date.slice(5, 7) !== dates[index - 1]?.slice(5, 7); return <g key={date}><line className="theme-return-line-grid theme-return-line-grid--vertical" x1={x} x2={x} y1={margin.top} y2={margin.top + innerHeight}/><text className="theme-return-line-axis-label theme-return-line-x-label" x={x} y={height - 13} textAnchor="middle">{monthChanged ? `${Number(date.slice(5, 7))}월 ` : ""}{date.slice(8)}</text></g>; })}
      <line className="theme-return-line-zero" x1={margin.left} x2={width - margin.right} y1={yScale(0)} y2={yScale(0)}/>
      {series.map((item) => { const active = hoveredThemeId === item.theme_id, muted = hoveredThemeId != null && !active; const points = item.values.map((value, index) => value == null ? null : { x: xScale(index), y: yScale(value) }); return <g key={item.theme_id} className={muted ? "theme-flow-line-series is-muted" : active ? "theme-flow-line-series is-active" : "theme-flow-line-series"}>
        {lineSegments(points).filter((segment) => segment.length > 1).map((segment, segmentIndex) => <path key={segmentIndex} className="theme-return-line-path" d={linePath(segment)} fill="none" stroke={item.color} onMouseEnter={() => setHoveredThemeId(item.theme_id)} onMouseLeave={() => setHoveredThemeId(null)}><title>{`${item.theme_name}\n30일 누적 ${pct(item.cumulative)}\n최근 일별 ${pct(item.latestDaily)}`}</title></path>)}
        {points.map((point, index) => point == null ? null : <circle key={dates[index]} className="theme-flow-line-point us-theme-line-hit-point" cx={point.x} cy={point.y} r={5} fill="transparent" stroke="transparent" tabIndex={0} onMouseEnter={() => setHoveredThemeId(item.theme_id)} onMouseLeave={() => setHoveredThemeId(null)} onFocus={() => setHoveredThemeId(item.theme_id)} onBlur={() => setHoveredThemeId(null)} onClick={() => onOpen(item.theme_id, dates[index])}><title>{`${item.theme_name}\n${dates[index]}\n30일 누적 ${pct(item.values[index])}`}</title></circle>)}
      </g>; })}
    </svg></div><div className="theme-return-line-legend-shell" onMouseLeave={() => setHoveredThemeId(null)}><div className="theme-return-line-legend">{series.map((item) => { const active = hoveredThemeId === item.theme_id, muted = hoveredThemeId != null && !active; const lastDate = [...dates].reverse().find((date) => item.values[dates.indexOf(date)] != null); return <button key={item.theme_id} type="button" className={`theme-return-line-legend-item ${active ? "theme-return-line-legend-item-active" : ""} ${muted ? "theme-return-line-legend-item-muted" : ""}`} onMouseEnter={() => setHoveredThemeId(item.theme_id)} onFocus={() => setHoveredThemeId(item.theme_id)} onBlur={() => setHoveredThemeId(null)} onClick={() => lastDate && onOpen(item.theme_id, lastDate)}><span className="theme-return-line-legend-color" style={{ background: item.color }}/><span className="theme-return-line-legend-text"><strong>{item.theme_name}</strong><em>30일 누적 {pct(item.cumulative)} · 최근 일별 {pct(item.latestDaily)}</em></span></button>; })}</div></div></div>
  </div>;
}

function UsThemeTrendPanel({ groups, themes, onOpenDetail }: { groups: UsThemeGroup[]; themes: UsTheme[]; onOpenDetail: (themeId: number, tradeDate: string) => void }) {
  const [period, setPeriod] = useState<20 | 30 | 60>(30); const [metric, setMetric] = useState<"theme_strength" | "simple_return">("theme_strength"); const [view, setView] = useState<"heatmap" | "line">("heatmap");
  const [data, setData] = useState<UsThemeTrend | null>(null); const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  const [referenceDate, setReferenceDate] = useState(""); const [groupFilter, setGroupFilter] = useState("all"); const [activeFilter, setActiveFilter] = useState("1"); const [keyword, setKeyword] = useState("");
  const load = async (date = referenceDate) => { setLoading(true); setError(""); try { const next = await repositories.usMarketThemes.trend(period, { end_date: date || undefined, active: activeFilter === "all" ? null : Number(activeFilter) }); setData(next); setReferenceDate((current) => current || next.dates[next.dates.length - 1] || ""); } catch (reason) { setError(errorText(reason, "미국 테마 등락추이를 불러오지 못했습니다.")); } finally { setLoading(false); } };
  useEffect(() => { void load(); }, [period, activeFilter]);
  const themeMeta = useMemo(() => new Map(themes.map((theme) => [theme.id, theme])), [themes]);
  const filteredItems = useMemo(() => (data?.items ?? []).filter((item) => groupFilter === "all" || String(item.theme_group_id) === groupFilter).filter((item) => { const meta = themeMeta.get(item.theme_id); return !keyword.trim() || `${item.theme_group_name} ${item.theme_name} ${meta?.keywords.join(" ") ?? ""}`.toLowerCase().includes(keyword.trim().toLowerCase()); }), [data, groupFilter, keyword, themeMeta]);
  const latestTradeDate = useMemo(() => (data?.dates ?? []).reduce((latest, current) => current > latest ? current : latest, ""), [data]);
  const displayedItems = useMemo(() => filteredItems.map((item, index) => ({ item, index })).sort((left, right) => {
    const leftPoint = left.item.points.find((point) => point.trade_date === latestTradeDate);
    const rightPoint = right.item.points.find((point) => point.trade_date === latestTradeDate);
    const leftValue = leftPoint?.[metric] ?? null;
    const rightValue = rightPoint?.[metric] ?? null;
    if (leftValue == null && rightValue != null) return 1;
    if (leftValue != null && rightValue == null) return -1;
    if (leftValue != null && rightValue != null && leftValue !== rightValue) return rightValue - leftValue;
    const leftRolling = leftPoint ? (metric === "theme_strength" ? leftPoint.rolling_30d_theme_strength : leftPoint.rolling_30d_simple_return) : null;
    const rightRolling = rightPoint ? (metric === "theme_strength" ? rightPoint.rolling_30d_theme_strength : rightPoint.rolling_30d_simple_return) : null;
    if (leftRolling == null && rightRolling != null) return 1;
    if (leftRolling != null && rightRolling == null) return -1;
    if (leftRolling != null && rightRolling != null && leftRolling !== rightRolling) return rightRolling - leftRolling;
    return left.item.theme_name.localeCompare(right.item.theme_name, "ko-KR") || left.index - right.index;
  }).map(({ item }) => item), [filteredItems, latestTradeDate, metric]);
  const summary = useMemo(() => {
    const dates = data?.dates ?? [], latestDate = latestTradeDate;
    const rows = displayedItems.map((theme) => { const points = new Map(theme.points.map((point) => [point.trade_date, point])); const latest = latestDate ? points.get(latestDate) : undefined; const cumulative = latest ? (metric === "theme_strength" ? latest.rolling_30d_theme_strength : latest.rolling_30d_simple_return) : null; const cumulativeEligible = (latest?.rolling_30d_valid_count ?? 0) >= 20; let streak = 0; for (let index = dates.length - 1; index >= 0; index -= 1) { const value = points.get(dates[index])?.[metric]; if (value == null || value <= 0) break; streak += 1; } return { theme, latest, cumulative, cumulativeEligible, streak }; });
    return {
      strength: [...rows].filter((row) => row.latest).sort((a, b) => (b.latest?.theme_strength ?? -Infinity) - (a.latest?.theme_strength ?? -Infinity))[0],
      cumulative: [...rows].filter((row) => row.cumulative != null && row.cumulativeEligible).sort((a, b) => (b.cumulative ?? -Infinity) - (a.cumulative ?? -Infinity))[0],
      breadth: [...rows].filter((row) => row.latest).sort((a, b) => (b.latest?.breadth_ratio ?? -Infinity) - (a.latest?.breadth_ratio ?? -Infinity) || (b.latest?.valid_stock_count ?? 0) - (a.latest?.valid_stock_count ?? 0) || (b.latest?.theme_strength ?? 0) - (a.latest?.theme_strength ?? 0))[0],
      streak: [...rows].filter((row) => row.latest?.[metric] != null).sort((a, b) => b.streak - a.streak || (b.latest?.[metric] ?? -Infinity) - (a.latest?.[metric] ?? -Infinity))[0],
    };
  }, [data, displayedItems, latestTradeDate, metric]);
  return <SectionCard title="미국 테마등락추이" className="us-theme-trend-card">
    <div className="us-theme-trend-toolbar-grid"><label><span>기준일</span><input className="input-control" type="date" value={referenceDate} onChange={(e) => setReferenceDate(e.target.value)}/></label><label><span>기간</span><select className="select-control" value={period} onChange={(e) => setPeriod(Number(e.target.value) as 20 | 30 | 60)}><option value={20}>20거래일</option><option value={30}>30거래일</option><option value={60}>60거래일</option></select></label><label><span>테마그룹</span><select className="select-control" value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)}><option value="all">테마그룹 전체</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label><label><span>상태</span><select className="select-control" value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)}><option value="all">상태 전체</option><option value="1">활성</option><option value="0">비활성</option></select></label><label className="us-theme-trend-search"><span>테마 검색</span><Search size={15}/><input className="input-control" value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="테마명 또는 키워드"/></label><button type="button" className="btn btn-secondary" disabled={loading} onClick={() => void load()}><RefreshCw size={14} className={loading ? "animate-spin" : ""}/> 새로고침</button><div className="us-theme-trend-toolbar-metric"><span>계산 기준</span><div className="theme-view-mode-tabs"><button className={`theme-view-mode-tab ${metric === "theme_strength" ? "active" : ""}`} onClick={() => setMetric("theme_strength")}>테마강도</button><button className={`theme-view-mode-tab ${metric === "simple_return" ? "active" : ""}`} onClick={() => setMetric("simple_return")}>단순등락률</button></div></div></div>
    {error ? <div className="inline-result inline-error">{error}</div> : null}{loading ? <div className="us-theme-loading">불러오는 중...</div> : null}
    {!loading && (!data || displayedItems.length === 0) ? <div className="us-theme-empty">조건에 맞는 미국 테마등락률이 없습니다.</div> : null}
    {data && displayedItems.length ? <div className="us-theme-trend-summary-row"><div className="us-theme-trend-summary"><article><span>현재 강도 1위</span><strong>{summary.strength?.theme.theme_name ?? "-"}</strong><em className={valueTone(summary.strength?.latest?.theme_strength)}>{pct(summary.strength?.latest?.theme_strength)}</em></article><article><span>30일 누적 1위</span><strong>{summary.cumulative?.theme.theme_name ?? "-"}</strong><em className={valueTone(summary.cumulative?.cumulative)}>{pct(summary.cumulative?.cumulative)}</em></article><article><span>상승 확산 1위</span><strong>{summary.breadth?.theme.theme_name ?? "-"}</strong><em>{summary.breadth?.latest ? `${summary.breadth.latest.up_count}/${summary.breadth.latest.valid_stock_count} · ${(summary.breadth.latest.breadth_ratio * 100).toFixed(0)}%` : "-"}</em></article><article><span>상승 지속 1위</span><strong>{summary.streak?.theme.theme_name ?? "-"}</strong><em>{summary.streak ? `${summary.streak.streak}거래일` : "-"}</em></article></div><div className="theme-view-mode-tabs us-theme-trend-view-switch" aria-label="그래프 선택"><button className={`theme-view-mode-tab ${view === "heatmap" ? "active" : ""}`} onClick={() => setView("heatmap")}>히트맵</button><button className={`theme-view-mode-tab ${view === "line" ? "active" : ""}`} onClick={() => setView("line")}>선그래프</button></div></div> : null}
    {data && displayedItems.length > 0 && view === "heatmap" ? <div className="theme-return-legend">{THEME_RETURN_HEATMAP_LABELS.map((label, index) => <span key={label} className="theme-return-legend__item"><i className="theme-return-legend__chip" style={{ background: THEME_RETURN_HEATMAP_COLORS[index] }}/>{label}</span>)}</div> : null}
    {data && displayedItems.length > 0 ? <div className="us-theme-trend-sort-note" title="테마는 가장 최근 거래일의 선택 계산기준 값이 높은 순서로 표시됩니다."><span>{latestTradeDate} 최신값 기준 내림차순</span></div> : null}
    {data && displayedItems.length > 0 && view === "heatmap" ? <div className={`us-theme-trend-scroll period-${period}`}><table className="us-theme-trend-heatmap"><colgroup><col className="us-theme-name-col"/>{data.dates.map((day) => <col key={day}/>)}</colgroup><thead><tr><th>테마</th>{data.dates.map((day, index) => { const monthChanged = index === 0 || day.slice(5, 7) !== data.dates[index - 1]?.slice(5, 7), latest = day === latestTradeDate; return <th key={day} className={latest ? "is-latest" : ""} title={day} aria-label={day}>{monthChanged ? <small>{Number(day.slice(5, 7))}월</small> : null}<span>{day.slice(8)}</span></th>; })}</tr></thead><tbody>{displayedItems.map((theme) => { const points = new Map(theme.points.map((point) => [point.trade_date, point])); const duplicate = theme.theme_group_name.trim().toLowerCase() === theme.theme_name.trim().toLowerCase(); return <tr key={theme.theme_id}><th title={`${theme.theme_group_name} / ${theme.theme_name}`}>{!duplicate ? <small>{theme.theme_group_name}</small> : null}<strong>{theme.theme_name}</strong></th>{data.dates.map((day) => { const point = points.get(day); const value = point?.[metric]; const hasValue = value != null && Number.isFinite(Number(value)); const metricLabel = metric === "theme_strength" ? "테마강도" : "단순등락률"; return <td key={day} className={day === latestTradeDate ? "is-latest" : ""}><button className={hasValue ? "" : "theme-return-heatmap__value-cell--empty"} style={{ background: getThemeReturnHeatmapColor(hasValue ? value : null), color: getThemeReturnTextColor(hasValue ? value : null) }} disabled={!hasValue} title={`${theme.theme_name}\n${day}\n${metricLabel} ${hasValue ? pct(value) : "-"}`} aria-label={`${theme.theme_name} ${day} ${metricLabel} ${hasValue ? pct(value) : "-"}`} onClick={() => hasValue && onOpenDetail(theme.theme_id, day)}>{hasValue ? compactValue(value) : "-"}</button></td>; })}</tr>; })}</tbody></table></div> : null}
    {data && displayedItems.length > 0 && view === "line" ? <UsThemeIntegratedLineChart themes={displayedItems} dates={data.dates} metric={metric} period={period} onOpen={onOpenDetail}/> : null}
  </SectionCard>;
}

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message.trim() ? error.message : fallback;
}

function UsChartCells({ stock, onOpen }: { stock: UsThemeStock; onOpen: (chart: { url: string; title: string }) => void }) {
  const rootRef = useRef<HTMLTableCellElement | null>(null);
  const [charts, setCharts] = useState<UsStockCharts | null>(null);
  const [requested, setRequested] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    setCharts(null); setRequested(false); setRetryCount(0);
    const element = rootRef.current;
    if (!element || !stock.naver_code) return;
    const request = () => setRequested(true);
    if (typeof IntersectionObserver === "undefined") { request(); return; }
    const observer = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) { request(); observer.disconnect(); } }, { rootMargin: "120px" });
    observer.observe(element);
    return () => observer.disconnect();
  }, [stock.naver_code, stock.us_stock_id]);

  useEffect(() => {
    if (!requested) return;
    let active = true;
    let retryTimer: number | undefined;
    let promise = chartCache.get(stock.us_stock_id);
    if (!promise) { promise = repositories.usMarketThemes.charts(stock.us_stock_id); chartCache.set(stock.us_stock_id, promise); }
    promise.then((value) => {
      if (!value.available) chartCache.delete(stock.us_stock_id);
      if (active) setCharts(value);
      if (active && !value.available && retryCount < 1) retryTimer = window.setTimeout(() => setRetryCount((count) => count + 1), 2500);
    }).catch(() => {
      chartCache.delete(stock.us_stock_id);
      if (active) setCharts({ stock_id: stock.us_stock_id, naver_code: stock.naver_code, day: null, week: null, month: null, available: false });
      if (active && retryCount < 1) retryTimer = window.setTimeout(() => setRetryCount((count) => count + 1), 2500);
    });
    return () => { active = false; if (retryTimer !== undefined) window.clearTimeout(retryTimer); };
  }, [requested, retryCount, stock.naver_code, stock.us_stock_id]);

  return <>
    {(["day", "week", "month"] as const).map((period) => {
      const label = period === "day" ? "일봉" : period === "week" ? "주봉" : "월봉";
      const url = charts?.[period];
      return <td key={period} ref={period === "day" ? rootRef : undefined} className="us-theme-chart-cell">{url ? <button type="button" className="theme-linked-stock-chart-button" onClick={() => onOpen({ url, title: `${stock.symbol} ${label}` })}><img className="theme-linked-stock-chart" src={url} alt={`${stock.symbol} ${label}`} loading="lazy" decoding="async" /></button>
        : <div className="theme-linked-stock-chart-fallback">{!stock.naver_code ? "차트없음" : !requested ? "차트 준비" : !charts ? "조회 중" : "조회불가"}</div>}</td>;
    })}
  </>;
}

export default function UsMarketThemesPanel({ activeTab, onSummaryChange }: Props) {
  const [groups, setGroups] = useState<UsThemeGroup[]>([]);
  const [themes, setThemes] = useState<UsTheme[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>("theme");
  const [groupFilter, setGroupFilter] = useState("all");
  const [activeFilter, setActiveFilter] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [selectedThemeId, setSelectedThemeId] = useState<number | null>(null);
  const [mappings, setMappings] = useState<UsThemeStock[]>([]);
  const [stockKeyword, setStockKeyword] = useState("");
  const [stockResults, setStockResults] = useState<UsStock[]>([]);
  const [editTarget, setEditTarget] = useState<EditTarget | null>(null);
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formGroupId, setFormGroupId] = useState("");
  const [formKeywords, setFormKeywords] = useState("");
  const [formSortOrder, setFormSortOrder] = useState(100);
  const [formActive, setFormActive] = useState(1);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [zoomed, setZoomed] = useState<{ url: string; title: string } | null>(null);
  const [detailTarget, setDetailTarget] = useState<{ themeId: number; tradeDate: string | null } | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const activeGroups = useMemo(() => groups.filter((group) => group.active === 1), [groups]);
  const selectableThemes = useMemo(() => themes.filter((theme) => theme.active === 1 && (groupFilter === "all" || String(theme.theme_group_id) === groupFilter)), [groupFilter, themes]);
  const filteredGroups = useMemo(() => groups.filter((group) => activeFilter === "all" || String(group.active) === activeFilter).filter((group) => !keyword.trim() || `${group.name} ${group.description || ""}`.toLowerCase().includes(keyword.trim().toLowerCase())), [activeFilter, groups, keyword]);
  const filteredThemes = useMemo(() => {
    const groupOrder = new Map(
      [...groups]
        .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name, "ko-KR") || a.id - b.id)
        .map((group, index) => [group.id, index]),
    );
    return themes
      .filter((theme) => groupFilter === "all" || String(theme.theme_group_id) === groupFilter)
      .filter((theme) => activeFilter === "all" || String(theme.active) === activeFilter)
      .filter((theme) => !keyword.trim() || `${theme.theme_group_name} ${theme.name} ${theme.keywords.join(" ")}`.toLowerCase().includes(keyword.trim().toLowerCase()))
      .sort((a, b) => (groupOrder.get(a.theme_group_id) ?? Number.MAX_SAFE_INTEGER) - (groupOrder.get(b.theme_group_id) ?? Number.MAX_SAFE_INTEGER)
        || a.sort_order - b.sort_order
        || a.name.localeCompare(b.name, "ko-KR")
        || a.id - b.id);
  }, [activeFilter, groupFilter, groups, keyword, themes]);
  const connectedIds = useMemo(() => new Set(mappings.map((mapping) => mapping.us_stock_id)), [mappings]);

  const loadBase = async () => {
    setLoading(true); setError("");
    try {
      const [summary, nextGroups, nextThemes] = await Promise.all([repositories.usMarketThemes.summary(), repositories.usMarketThemes.listGroups(), repositories.usMarketThemes.listThemes()]);
      onSummaryChange(summary); setGroups(nextGroups); setThemes(nextThemes);
      setSelectedThemeId((current) => current && nextThemes.some((theme) => theme.id === current && theme.active === 1) ? current : nextThemes.find((theme) => theme.active === 1)?.id ?? null);
    } catch (reason) { setError(errorText(reason, "미국 테마 정보를 불러오지 못했습니다.")); }
    finally { setLoading(false); }
  };

  const loadMappings = async (themeId: number | null) => {
    if (!themeId) { setMappings([]); return; }
    try { setMappings(await repositories.usMarketThemes.listThemeStocks(themeId)); }
    catch (reason) { setError(errorText(reason, "연결 종목을 불러오지 못했습니다.")); }
  };

  useEffect(() => { void loadBase(); }, []);
  useEffect(() => { if (activeTab === "mapping") void loadMappings(selectedThemeId); }, [activeTab, selectedThemeId]);

  const openEditor = (target: EditTarget) => {
    setEditTarget(target); setError("");
    const value = target.value;
    setFormName(value?.name ?? ""); setFormDescription(value?.description ?? ""); setFormSortOrder(value?.sort_order ?? 100); setFormActive(value?.active ?? 1);
    if (target.kind === "theme") {
      setFormGroupId(String(target.value?.theme_group_id ?? activeGroups[0]?.id ?? ""));
      setFormKeywords(target.value?.keywords.join(", ") ?? "");
    } else {
      setFormGroupId("");
      setFormKeywords("");
    }
  };

  const saveEditor = async () => {
    if (!editTarget || !formName.trim()) return;
    setLoading(true); setError("");
    try {
      if (editTarget.kind === "group") {
        const payload = { name: formName.trim(), description: formDescription.trim() || null, sort_order: formSortOrder, active: formActive };
        if (editTarget.value) await repositories.usMarketThemes.updateGroup(editTarget.value.id, payload); else await repositories.usMarketThemes.createGroup(payload);
      } else {
        if (!formGroupId) throw new Error("테마그룹을 선택해 주세요.");
        const payload = { theme_group_id: Number(formGroupId), name: formName.trim(), description: formDescription.trim() || null, keywords: formKeywords.split(/,|\n/).map((item) => item.trim()).filter(Boolean), sort_order: formSortOrder, active: formActive };
        if (editTarget.value) await repositories.usMarketThemes.updateTheme(editTarget.value.id, payload); else await repositories.usMarketThemes.createTheme(payload);
      }
      setEditTarget(null); setMessage("저장되었습니다."); await loadBase();
    } catch (reason) { setError(errorText(reason, "저장하지 못했습니다.")); }
    finally { setLoading(false); }
  };

  const toggleGroup = async (group: UsThemeGroup) => { await repositories.usMarketThemes.updateGroup(group.id, { active: group.active ? 0 : 1 }); await loadBase(); };
  const toggleTheme = async (theme: UsTheme) => { await repositories.usMarketThemes.updateTheme(theme.id, { active: theme.active ? 0 : 1 }); await loadBase(); };
  const searchStocks = async () => {
    setError("");
    try { const result = await repositories.usStocks.list({ keyword: stockKeyword.trim() || undefined, is_active: 1, page: 1, page_size: 100 }); setStockResults(result.items); }
    catch (reason) { setError(errorText(reason, "미국 종목을 검색하지 못했습니다.")); }
  };
  const linkStock = async (stockId: number) => {
    if (!selectedThemeId) return;
    try { await repositories.usMarketThemes.linkStock(selectedThemeId, { us_stock_id: stockId, role: "RELATED", is_representative: 0, sort_order: mappings.length + 1 }); await Promise.all([loadMappings(selectedThemeId), loadBase()]); setMessage("미국 종목을 연결했습니다."); }
    catch (reason) { setError(errorText(reason, "종목을 연결하지 못했습니다.")); }
  };
  const updateMapping = async (mappingId: number, payload: { role?: UsThemeStockRole; is_representative?: number }) => { await repositories.usMarketThemes.updateMapping(mappingId, payload); await loadMappings(selectedThemeId); await loadBase(); };
  const unlink = async (mappingId: number) => { await repositories.usMarketThemes.unlinkMapping(mappingId); await Promise.all([loadMappings(selectedThemeId), loadBase()]); setMessage("연결을 해제했습니다."); };
  const refreshMarket = async () => { if (!window.confirm("활성 미국 테마에 연결된 종목을 전체 점검합니다. 과거가격이 부족한 종목은 260일 이력을 보완하고, 정상 종목은 최신 종가를 수집한 뒤 활성 테마 전체를 재계산합니다. 계속할까요?")) return; setRefreshing(true); setError(""); try { const result = await repositories.usMarketThemes.refresh(); setMessage(result.message); await loadBase(); } catch (reason) { setError(errorText(reason, "미국 종가·테마 갱신에 실패했습니다.")); } finally { setRefreshing(false); } };

  return <>
    {message ? <div className="inline-result inline-success">{message}</div> : null}
    {error ? <div className="inline-result inline-error">{error}</div> : null}
    {activeTab === "themes" ? <SectionCard title="" className="market-theme-management-card us-theme-management-card">
      <div className="us-theme-management-header">
        <div className="theme-view-mode-tabs market-theme-view-toggle">
          <button type="button" className={`theme-view-mode-tab ${viewMode === "group" ? "active" : ""}`} onClick={() => setViewMode("group")}>테마그룹별</button>
          <button type="button" className={`theme-view-mode-tab ${viewMode === "theme" ? "active" : ""}`} onClick={() => setViewMode("theme")}>테마별</button>
          <button type="button" className={`theme-view-mode-tab ${viewMode === "trend" ? "active" : ""}`} onClick={() => setViewMode("trend")}>미국테마등락추이</button>
        </div>
        {viewMode !== "trend" ? <div className="us-theme-refresh-row"><span>최종 테마등락률 {themes.map((theme) => theme.latest_return_date).filter((value): value is string => Boolean(value)).sort().slice(-1)[0] || "-"}</span><button type="button" className="btn btn-danger" disabled={refreshing} onClick={() => void refreshMarket()}><RefreshCw size={14} className={refreshing ? "animate-spin" : ""}/> {refreshing ? "갱신 중..." : "미국 종가·테마 갱신"}</button></div> : null}
      </div>
      {viewMode === "trend" ? <UsThemeTrendPanel groups={groups} themes={themes} onOpenDetail={(themeId, tradeDate) => setDetailTarget({ themeId, tradeDate })} /> : <><div className="market-theme-filter-toolbar us-theme-filter-toolbar">
        {viewMode === "theme" ? <select className="select-control" value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}><option value="all">테마그룹 전체</option>{groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select> : null}
        <select className="select-control" value={activeFilter} onChange={(event) => setActiveFilter(event.target.value)}><option value="all">활성 전체</option><option value="1">활성</option><option value="0">비활성</option></select>
        <input className="input-control" placeholder="테마그룹명, 테마명 또는 키워드 검색" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
        <button type="button" className="btn btn-secondary" onClick={() => openEditor({ kind: viewMode === "group" ? "group" : "theme", value: null })}>+ {viewMode === "group" ? "그룹" : "테마"} 등록</button>
      </div>
      <div className="table-shell"><table className="data-table compact-table">
        {viewMode === "group" ? <><thead><tr><th>상태</th><th>테마그룹명</th><th>활성 테마</th><th>전체 테마</th><th>연결 종목</th><th>정렬</th><th>작업</th></tr></thead><tbody>{filteredGroups.map((group) => <tr key={group.id}><td><span className={`status-pill ${group.active ? "active" : "inactive"}`}>{group.active ? "활성" : "비활성"}</span></td><td><strong>{group.name}</strong>{group.description ? <small className="us-theme-subtext">{group.description}</small> : null}</td><td>{group.active_theme_count}</td><td>{group.theme_count}</td><td>{group.linked_stock_count}</td><td>{group.sort_order}</td><td><div className="us-theme-row-actions"><button className="btn btn-secondary btn-table-sm" onClick={() => openEditor({ kind: "group", value: group })}>수정</button><button className="btn btn-secondary btn-table-sm" onClick={() => void toggleGroup(group)}>{group.active ? "비활성화" : "활성화"}</button></div></td></tr>)}</tbody></>
          : <><thead><tr><th>상태</th><th>테마그룹</th><th>테마명</th><th>연결</th><th>대표 종목</th><th>기준일</th><th>등락률</th><th>테마강도</th><th>상승비율</th><th>작업</th></tr></thead><tbody>{filteredThemes.map((theme) => <tr key={theme.id} className="us-theme-clickable-row" tabIndex={0} aria-label={`${theme.name} 상세 보기`} onClick={() => setDetailTarget({ themeId: theme.id, tradeDate: theme.latest_return_date })} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setDetailTarget({ themeId: theme.id, tradeDate: theme.latest_return_date }); } }}><td><span className={`status-pill ${theme.active ? "active" : "inactive"}`}>{theme.active ? "활성" : "비활성"}</span></td><td>{theme.theme_group_name}</td><td><button type="button" className="us-theme-name-button" tabIndex={-1}>{theme.name}</button></td><td>{theme.linked_stock_count}</td><td>{theme.representative_symbols.join(", ") || "-"}</td><td>{theme.latest_return_date || "-"}</td><td className={theme.latest_simple_return == null ? "" : theme.latest_simple_return >= 0 ? "value-up" : "value-down"}>{pct(theme.latest_simple_return)}</td><td className={theme.latest_theme_strength == null ? "" : theme.latest_theme_strength >= 0 ? "value-up" : "value-down"}>{pct(theme.latest_theme_strength)}</td><td>{theme.latest_breadth_ratio == null ? "-" : `${(theme.latest_breadth_ratio * 100).toFixed(0)}%`}</td><td><div className="us-theme-row-actions"><button className="btn btn-secondary btn-table-sm" onClick={(event) => { event.stopPropagation(); openEditor({ kind: "theme", value: theme }); }}>수정</button><button className="btn btn-secondary btn-table-sm" onClick={(event) => { event.stopPropagation(); void toggleTheme(theme); }}>{theme.active ? "비활성화" : "활성화"}</button></div></td></tr>)}</tbody></>}
      </table>{loading ? <div className="us-theme-loading">불러오는 중...</div> : null}{!loading && (viewMode === "group" ? filteredGroups.length : filteredThemes.length) === 0 ? <div className="us-theme-empty">등록된 항목이 없습니다.</div> : null}</div></>}
    </SectionCard> : <div className="space-y-4">
      <SectionCard title="미국 종목 연결">
        <div className="us-theme-mapping-toolbar">
          <select className="select-control" value={groupFilter} onChange={(event) => { setGroupFilter(event.target.value); setSelectedThemeId(null); }}><option value="all">테마그룹 전체</option>{activeGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select>
          <select className="select-control" value={selectedThemeId ?? ""} onChange={(event) => setSelectedThemeId(Number(event.target.value) || null)}><option value="">미국 테마 선택</option>{selectableThemes.map((theme) => <option key={theme.id} value={theme.id}>{theme.name}</option>)}</select>
          <input className="input-control" placeholder="Ticker 또는 종목명 검색" value={stockKeyword} onChange={(event) => setStockKeyword(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void searchStocks(); }} />
          <button className="btn btn-primary" type="button" onClick={() => void searchStocks()}>검색</button>
        </div>
        {stockResults.length ? <div className="us-theme-stock-results">{stockResults.map((stock) => <div key={stock.id}><span><strong>{stock.symbol}</strong> {stock.name_ko || stock.name || ""} · {stock.exchange}</span><button className="btn btn-secondary btn-table-sm" disabled={!selectedThemeId || connectedIds.has(stock.id)} onClick={() => void linkStock(stock.id)}>{connectedIds.has(stock.id) ? "연결됨" : "연결"}</button></div>)}</div> : null}
      </SectionCard>
      <SectionCard title="연결 종목 목록">
        {!selectedThemeId ? <p className="selected-empty-message">미국 테마를 선택해 주세요.</p> : <div className="table-shell us-theme-mapping-table-shell"><table className="data-table compact-table us-theme-mapping-table"><colgroup><col className="us-theme-mapping-col-stock"/><col className="us-theme-mapping-col-exchange"/><col className="us-theme-mapping-col-primary"/><col className="us-theme-mapping-col-status"/><col className="us-theme-mapping-col-chart"/><col className="us-theme-mapping-col-chart"/><col className="us-theme-mapping-col-chart"/><col className="us-theme-mapping-col-action"/></colgroup><thead><tr><th>종목</th><th>거래소</th><th>대표</th><th>상태</th><th>일봉</th><th>주봉</th><th>월봉</th><th>작업</th></tr></thead><tbody>{mappings.map((mapping) => <tr key={mapping.mapping_id}><td><div className="stock-cell"><strong>{mapping.symbol}</strong><span>{mapping.name_ko || mapping.name || "-"}</span></div></td><td>{mapping.exchange}</td><td><label className="us-theme-representative"><input type="checkbox" checked={mapping.is_representative === 1} onChange={(event) => void updateMapping(mapping.mapping_id, { is_representative: event.target.checked ? 1 : 0 })} /> 대표</label></td><td>{mapping.active ? "활성" : "비활성"}</td><UsChartCells stock={mapping} onOpen={setZoomed} /><td><button className="btn btn-secondary btn-table-sm" onClick={() => void unlink(mapping.mapping_id)}>해제</button></td></tr>)}</tbody></table>{mappings.length === 0 ? <div className="us-theme-empty">연결된 미국 종목이 없습니다.</div> : null}</div>}
      </SectionCard>
    </div>}

    <UsThemeDetailDrawer open={detailTarget != null} themeId={detailTarget?.themeId ?? null} tradeDate={detailTarget?.tradeDate} onClose={() => setDetailTarget(null)} />
    {editTarget ? <div className="us-theme-modal-backdrop" onClick={() => setEditTarget(null)}><section className="us-theme-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}><header><div><h3>{editTarget.value ? "수정" : "등록"}</h3><p>{editTarget.kind === "group" ? "미국 테마그룹" : "미국 테마"}</p></div><button className="btn btn-secondary btn-table-sm" onClick={() => setEditTarget(null)}>닫기</button></header><div className="us-theme-form">
      {editTarget.kind === "theme" ? <label><span>테마그룹</span><select className="select-control" value={formGroupId} onChange={(event) => setFormGroupId(event.target.value)}>{activeGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label> : null}
      <label><span>이름</span><input className="input-control" value={formName} onChange={(event) => setFormName(event.target.value)} /></label>
      <label className="wide"><span>설명</span><textarea className="input-control" value={formDescription} onChange={(event) => setFormDescription(event.target.value)} /></label>
      {editTarget.kind === "theme" ? <label className="wide"><span>키워드</span><input className="input-control" placeholder="쉼표로 구분" value={formKeywords} onChange={(event) => setFormKeywords(event.target.value)} /></label> : null}
      <label><span>정렬</span><input className="input-control" type="number" min={0} value={formSortOrder} onChange={(event) => setFormSortOrder(Number(event.target.value) || 0)} /></label>
      <label><span>상태</span><select className="select-control" value={formActive} onChange={(event) => setFormActive(Number(event.target.value))}><option value={1}>활성</option><option value={0}>비활성</option></select></label>
    </div><footer><button className="btn btn-secondary" onClick={() => setEditTarget(null)}>취소</button><button className="btn btn-primary" disabled={loading || !formName.trim()} onClick={() => void saveEditor()}>저장</button></footer></section></div> : null}
    {zoomed ? <div className="theme-linked-stock-chart-modal" onClick={() => setZoomed(null)}><div className="theme-linked-stock-chart-modal-panel" onClick={(event) => event.stopPropagation()}><div className="theme-linked-stock-chart-modal-header"><h3>{zoomed.title}</h3><button className="btn btn-secondary btn-table-sm" onClick={() => setZoomed(null)}>닫기</button></div><img src={zoomed.url} alt={zoomed.title} className="theme-linked-stock-chart-modal-image" /></div></div> : null}
  </>;
}
