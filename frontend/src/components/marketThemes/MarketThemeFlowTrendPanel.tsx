import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { repositories } from "@/services";
import type {
  MarketThemeFlowTrendActor, MarketThemeFlowTrendAttribution, MarketThemeFlowTrendCell,
  MarketThemeFlowTrendMetric, MarketThemeFlowTrendResponse, MarketThemeFlowTrendTheme,
} from "@/types/marketTheme";

const ACTORS: Array<{ value: MarketThemeFlowTrendActor; label: string }> = [
  { value: "FOREIGN", label: "외국인" }, { value: "INSTITUTION", label: "기관" },
  { value: "FOREIGN_INSTITUTION", label: "외국인+기관" }, { value: "INDIVIDUAL", label: "개인" },
  { value: "PROGRAM", label: "프로그램" },
];
const METRICS: Array<{ value: MarketThemeFlowTrendMetric; label: string }> = [
  { value: "FLOW_STRENGTH", label: "수급 강도" }, { value: "NET_AMOUNT", label: "순매수 금액" },
  { value: "BREADTH", label: "연결종목 확산도" },
];
const ATTRIBUTIONS: Array<{ value: MarketThemeFlowTrendAttribution; label: string }> = [
  { value: "FRACTIONAL", label: "중복테마별 1/n" }, { value: "FULL", label: "중복테마별 1" },
];
const ACTOR_LABEL: Record<MarketThemeFlowTrendActor, string> = Object.fromEntries(ACTORS.map((item) => [item.value, item.label])) as Record<MarketThemeFlowTrendActor, string>;
const FLOW_COLORS = ["#2563EB", "#60A5FA", "#93C5FD", "#DBEAFE", "#E5E7EB", "#FEE2E2", "#FCA5A5", "#F87171", "#DC2626"];
const FLOW_NEAR_ZERO_NEGATIVE_COLOR = "#EFF6FF";
const FLOW_NEAR_ZERO_POSITIVE_COLOR = "#FFF1F2";
const BREADTH_COLORS = ["#2563EB", "#93C5FD", "#FDC698", "#FCA5A5", "#DC2626"];
const CACHE_TTL = 60_000;
const flowTrendCache = new Map<string, { expires: number; value: MarketThemeFlowTrendResponse }>();
export const invalidateMarketThemeFlowTrendFrontendCache = () => flowTrendCache.clear();

const amount = (value: number | null, suffix = true) => {
  if (value == null) return "-";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000_000) return `${sign}${(absolute / 1_000_000_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조${suffix ? "원" : ""}`;
  return `${sign}${(absolute / 100_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억${suffix ? "원" : ""}`;
};
const pct = (value: number | null) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
const qualityLabel = (value: string) => value === "ENOUGH" ? "충분" : value === "PARTIAL" ? "일부 부족" : value === "INSUFFICIENT" ? "부족" : "수급 없음";
const streak = (value: number) => value > 0 ? `${value}일 연속 순매수` : value < 0 ? `${Math.abs(value)}일 연속 순매도` : "연속 흐름 없음";

function strengthColor(value: number | null) {
  if (value == null) return "#f8fafc";
  if (value <= -20) return FLOW_COLORS[0]; if (value <= -15) return FLOW_COLORS[1];
  if (value <= -10) return FLOW_COLORS[2]; if (value <= -5) return FLOW_COLORS[3];
  if (value < 0) return FLOW_NEAR_ZERO_NEGATIVE_COLOR;
  if (value === 0) return FLOW_COLORS[4]; if (value < 5) return FLOW_NEAR_ZERO_POSITIVE_COLOR;
  if (value < 10) return FLOW_COLORS[5]; if (value < 15) return FLOW_COLORS[6];
  if (value < 20) return FLOW_COLORS[7]; return FLOW_COLORS[8];
}
function breadthColor(value: number | null) {
  if (value == null) return "#f8fafc";
  if (value < 30) return BREADTH_COLORS[0]; if (value < 40) return BREADTH_COLORS[1];
  if (value <= 60) return BREADTH_COLORS[2]; if (value <= 70) return BREADTH_COLORS[3]; return BREADTH_COLORS[4];
}
function amountColor(value: number | null, cap: number) {
  if (value == null) return "#f8fafc";
  if (value === 0) return FLOW_COLORS[4];
  const opacity = Math.min(.88, .14 + Math.abs(value) / Math.max(cap, 1) * .74);
  return value > 0 ? `rgba(220,38,38,${opacity})` : `rgba(37,99,235,${opacity})`;
}

function Segmented<T extends string>({ label, value, items, onChange }: { label: string; value: T; items: Array<{ value: T; label: string }>; onChange: (value: T) => void }) {
  return <div className="theme-flow-filter-group"><span>{label}</span><div className="theme-flow-segmented">{items.map((item) => <button type="button" key={item.value} className={value === item.value ? "active" : ""} onClick={() => onChange(item.value)}>{item.label}</button>)}</div></div>;
}

type Props = {
  endDate: string; onEndDateChange: (value: string) => void;
  themeGroupId: string; onThemeGroupChange: (value: string) => void;
  keyword: string; onKeywordChange: (value: string) => void;
  limit: string; onLimitChange: (value: string) => void;
  themeGroups: Array<{ id: number; theme_name: string }>;
  onCellClick: (theme: MarketThemeFlowTrendTheme, date: string, actor: MarketThemeFlowTrendActor, metric: MarketThemeFlowTrendMetric, attribution: MarketThemeFlowTrendAttribution) => void;
};

export default function MarketThemeFlowTrendPanel(props: Props) {
  const [actor, setActor] = useState<MarketThemeFlowTrendActor>("FOREIGN");
  const [metric, setMetric] = useState<MarketThemeFlowTrendMetric>("FLOW_STRENGTH");
  const [attribution, setAttribution] = useState<MarketThemeFlowTrendAttribution>("FRACTIONAL");
  const [data, setData] = useState<MarketThemeFlowTrendResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [highlightedThemeId, setHighlightedThemeId] = useState<number | null>(null);
  const requestSequence = useRef(0);
  const handledRefreshKey = useRef(0);
  const rowRefs = useRef(new Map<number, HTMLDivElement>());
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const paramsKey = [props.endDate, props.themeGroupId, props.keyword.trim(), props.limit, actor, metric, attribution].join("|");
  useEffect(() => {
    const sequence = ++requestSequence.current;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const forceRefresh = refreshKey > handledRefreshKey.current;
      if (forceRefresh) handledRefreshKey.current = refreshKey;
      const cached = flowTrendCache.get(paramsKey);
      if (!forceRefresh && cached && cached.expires > Date.now()) {
        setData(cached.value); setError(""); setLoading(false); return;
      }
      setLoading(true); setError("");
      repositories.marketThemes.getThemeFlowTrend({
        end_date: props.endDate, recent_days: 30, actor, metric, attribution,
        theme_group_id: props.themeGroupId === "all" ? undefined : Number(props.themeGroupId),
        search: props.keyword.trim() || undefined, limit: props.limit === "all" ? 100 : Number(props.limit),
        refresh: forceRefresh, signal: controller.signal,
      }).then((response) => {
        if (sequence !== requestSequence.current || controller.signal.aborted) return;
        flowTrendCache.set(paramsKey, { expires: Date.now() + CACHE_TTL, value: response });
        setData(response);
      }).catch((reason: unknown) => {
        if (controller.signal.aborted || sequence !== requestSequence.current) return;
        setData(null); setError(reason instanceof Error ? reason.message : "테마 수급 데이터를 불러오지 못했습니다.");
      }).finally(() => { if (sequence === requestSequence.current && !controller.signal.aborted) setLoading(false); });
    }, 180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [paramsKey, refreshKey]);
  useEffect(() => () => { if (highlightTimer.current) clearTimeout(highlightTimer.current); }, []);

  const validAmounts = useMemo(() => (data?.themes ?? []).flatMap((theme) => theme.cells.map((cell) => Math.abs(cell.net_buy_amount ?? 0))).filter((value) => value > 0).sort((a, b) => a - b), [data]);
  const amountCap = validAmounts.length ? validAmounts[Math.min(validAmounts.length - 1, Math.floor(validAmounts.length * .95))] : 1;
  const cellValue = (cell: MarketThemeFlowTrendCell) => metric === "FLOW_STRENGTH" ? (cell.flow_strength == null ? "-" : `${cell.flow_strength > 0 ? "+" : ""}${cell.flow_strength.toFixed(1)}`) : metric === "NET_AMOUNT" ? amount(cell.net_buy_amount, false) : cell.breadth_ratio == null ? "-" : `${Math.round(cell.breadth_ratio)}`;
  const cellColor = (cell: MarketThemeFlowTrendCell) => metric === "FLOW_STRENGTH" ? strengthColor(cell.flow_strength) : metric === "NET_AMOUNT" ? amountColor(cell.net_buy_amount, amountCap) : breadthColor(cell.breadth_ratio);
  const cellTone = (cell: MarketThemeFlowTrendCell) => {
    const value = metric === "FLOW_STRENGTH" ? cell.flow_strength : metric === "NET_AMOUNT" ? cell.net_buy_amount : cell.breadth_ratio == null ? null : cell.breadth_ratio - 50;
    return value == null || value === 0 ? "is-neutral" : value > 0 ? "is-positive" : "is-negative";
  };
  const tooltip = (theme: MarketThemeFlowTrendTheme, cell: MarketThemeFlowTrendCell) => [
    theme.theme_name, cell.trade_date, "", `${ACTOR_LABEL[actor]} 순매수: ${amount(cell.net_buy_amount)}`,
    `수급 강도: ${pct(cell.flow_strength)}`, `연결종목 확산도: ${cell.actor_data_stock_count ? `${cell.positive_stock_count}/${cell.actor_data_stock_count}종목 · ${cell.breadth_ratio?.toFixed(1)}%` : "-"}`,
    `테마 등락률: ${pct(cell.theme_return_pct)}`, `테마 거래대금: ${amount(cell.trading_value)}`,
    "", "상위 수급 기여 종목", ...cell.top_contributors.map((item, index) => `${index + 1}. ${item.stock_name} ${amount(item.net_buy_amount)}`),
    "", `수급 데이터: ${cell.actor_data_stock_count}/${cell.connected_stock_count}종목 · ${cell.data_quality}`,
    `종목 반영 기준: ${attribution === "FRACTIONAL" ? "중복테마별 1/n" : "중복테마별 1"}`,
    ...(actor === "PROGRAM" ? ["프로그램 수급은 외국인·기관 수급과 중복될 수 있습니다."] : []),
  ].join("\n");

  const scrollToTheme = (themeId: number) => {
    rowRefs.current.get(themeId)?.scrollIntoView({ behavior: "smooth", block: "center" });
    setHighlightedThemeId(themeId);
    if (highlightTimer.current) clearTimeout(highlightTimer.current);
    highlightTimer.current = setTimeout(() => setHighlightedThemeId(null), 1400);
  };
  const topCards = data ? [
    { label: `오늘 ${ACTOR_LABEL[actor]} 유입 1위`, item: data.summary.top_today, value: pct(data.summary.top_today?.flow_strength ?? null) },
    { label: `5일 ${ACTOR_LABEL[actor]} 누적 1위`, item: data.summary.top_five_day, value: amount(data.summary.top_five_day?.net_buy_amount ?? null) },
    { label: `${ACTOR_LABEL[actor]} 연결종목 확산도 1위`, item: data.summary.top_breadth, value: data.summary.top_breadth?.breadth_ratio == null ? "-" : `${data.summary.top_breadth.positive_stock_count}/${data.summary.top_breadth.actor_data_stock_count}종목 · ${Math.round(data.summary.top_breadth.breadth_ratio)}%` },
    { label: `${ACTOR_LABEL[actor]} 순매수 지속 1위`, item: data.summary.top_streak, value: data.summary.top_streak ? streak(data.summary.top_streak.current_streak) : "-" },
  ] : [];

  return <div className="theme-flow-trend-panel">
    <div className="theme-return-trend-toolbar">
      <input className="input-control" type="date" value={props.endDate} onChange={(event) => props.onEndDateChange(event.target.value)} />
      <select className="select-control" value={props.themeGroupId} onChange={(event) => props.onThemeGroupChange(event.target.value)}><option value="all">테마그룹 전체</option>{props.themeGroups.map((group) => <option key={group.id} value={group.id}>{group.theme_name}</option>)}</select>
      <input className="input-control" placeholder="테마명 검색" value={props.keyword} onChange={(event) => props.onKeywordChange(event.target.value)} />
      <select className="select-control" value={props.limit} onChange={(event) => props.onLimitChange(event.target.value)}><option value="10">상위 10개</option><option value="20">상위 20개</option><option value="30">상위 30개</option><option value="all">전체</option></select>
      <button type="button" className="btn btn-secondary market-theme-refresh-button" title="저장된 테마 수급 데이터를 다시 조회합니다. 외부 수급 수집은 실행하지 않습니다." onClick={() => { flowTrendCache.clear(); setRefreshKey((value) => value + 1); }} disabled={loading}>{loading ? "조회 중..." : "새로고침"}</button>
    </div>
    <div className="theme-flow-filter-row">
      <Segmented label="투자주체" value={actor} items={ACTORS} onChange={setActor} />
      <Segmented label="표시 지표" value={metric} items={METRICS} onChange={setMetric} />
      <Segmented label="종목 반영 기준" value={attribution} items={ATTRIBUTIONS} onChange={setAttribution} />
    </div>
    {actor === "PROGRAM" ? <p className="theme-flow-program-notice">프로그램은 독립 투자주체가 아닌 매매 방식 수급이며 외국인·기관 거래와 일부 중복될 수 있습니다.</p> : null}
    <p className="theme-flow-basis">집계 기준: 현재 활성 연결 종목 · {attribution === "FRACTIONAL" ? "중복테마별 1/n" : "중복테마별 1"} <span>과거 수급은 현재 활성 연결 종목 기준으로 계산됩니다.</span></p>
    {error ? <div className="theme-flow-state is-error"><strong>테마 수급 데이터를 불러오지 못했습니다.</strong><span>{error}</span><button type="button" onClick={() => setRefreshKey((value) => value + 1)}><RefreshCw size={13} /> 다시 시도</button></div> : null}
    {!error && topCards.length ? <div className="theme-flow-top-grid">{topCards.map((card) => <button type="button" key={card.label} disabled={!card.item} onClick={() => card.item && scrollToTheme(card.item.theme_id)}><span>{card.label}</span><strong>{card.item?.theme_name ?? "-"}</strong><em>{card.value}</em></button>)}</div> : null}
    {!error && metric === "FLOW_STRENGTH" ? <div className="theme-return-legend">{["-20% 이하", "-15%", "-10%", "-5%", "0%", "+5%", "+10%", "+15%", "+20% 이상"].map((label, index) => <span key={label} className="theme-return-legend__item"><i className="theme-return-legend__chip" style={{ background: FLOW_COLORS[index] }} />{label}</span>)}</div> : null}
    {!error && metric === "BREADTH" ? <div className="theme-return-legend">{["0~30%", "30~40%", "40~60%", "60~70%", "70~100%"].map((label, index) => <span key={label} className="theme-return-legend__item"><i className="theme-return-legend__chip" style={{ background: BREADTH_COLORS[index] }} />{label}</span>)}</div> : null}
    {!error && metric === "NET_AMOUNT" ? <p className="theme-flow-amount-legend">순매수 금액 색상은 현재 응답의 절대값 95 percentile을 상한으로 사용하며 실제 표시 금액은 변경하지 않습니다.</p> : null}
    {!error ? <div className="theme-return-heatmap-wrap theme-flow-heatmap-wrap">
      <div className="theme-return-heatmap theme-flow-heatmap" style={{ gridTemplateColumns: `minmax(240px, 270px) repeat(${Math.max(data?.dates.length ?? 0, 1)}, minmax(34px, 1fr))` }}>
        <div className="theme-return-heatmap__theme-cell theme-return-heatmap__header-cell">테마</div>
        {(data?.dates ?? []).map((day) => <div key={day} className="theme-return-heatmap__date-cell" title={day}>{day.slice(8)}</div>)}
        {loading ? <div className="theme-return-heatmap__empty-row">테마수급추이를 조회 중입니다.</div> : null}
        {!loading && (!data || !data.themes.length) ? <div className="theme-flow-state"><strong>수집된 테마 수급 데이터가 없습니다.</strong><span>‘테마 등락률&수급 갱신’을 실행하면 현재 활성 연결 종목의 수급 데이터를 수집할 수 있습니다.</span></div> : null}
        {!loading && data?.themes.map((theme) => <Fragment key={theme.theme_id}>
          <div ref={(node) => { if (node) rowRefs.current.set(theme.theme_id, node); else rowRefs.current.delete(theme.theme_id); }} className={`theme-return-heatmap__theme-cell theme-flow-theme-cell ${highlightedThemeId === theme.theme_id ? "is-highlighted" : ""}`}>
            <strong>{theme.theme_name}</strong><span>20일 {amount(theme.twenty_day_summary.cumulative_net_buy_amount, false)} · 강도 {pct(theme.twenty_day_summary.flow_strength)} · 연결종목 확산 {theme.twenty_day_summary.positive_stock_count}/{theme.twenty_day_summary.actor_data_stock_count} · {streak(theme.twenty_day_summary.current_streak)}</span><small>수급 {theme.twenty_day_summary.actor_data_stock_count}/{theme.connected_stock_count}종목 · {qualityLabel(theme.twenty_day_summary.data_quality)}</small>
          </div>
          {theme.cells.map((cell) => <button type="button" key={`${theme.theme_id}-${cell.trade_date}`} className={`theme-return-heatmap__value-cell theme-flow-value-cell ${cellTone(cell)} ${cell.actor_data_stock_count ? "" : "theme-return-heatmap__value-cell--empty"}`} style={{ background: cellColor(cell) }} title={tooltip(theme, cell)} onClick={() => cell.actor_data_stock_count && props.onCellClick(theme, cell.trade_date, actor, metric, attribution)}><span>{cellValue(cell)}</span></button>)}
        </Fragment>)}
      </div>
    </div> : null}
  </div>;
}
