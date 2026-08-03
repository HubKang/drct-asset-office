import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { repositories } from "@/services";
import type { MarketThemeFlowChartResponse, MarketThemeFlowChartSeriesItem, MarketThemePriceFlowPeriod } from "@/types/marketTheme";

type Key = "theme" | "individual" | "foreign" | "institution" | "program";
const LINES: Array<{ key: Key; label: string; color: string; dashed?: boolean }> = [
  { key: "theme", label: "테마 수익률", color: "#111827" },
  { key: "individual", label: "개인", color: "#2563eb" },
  { key: "foreign", label: "외국인", color: "#dc2626" },
  { key: "institution", label: "기관", color: "#f59e0b" },
  { key: "program", label: "프로그램", color: "#16a34a", dashed: true },
];

const cumulativeField: Record<Key, keyof MarketThemeFlowChartSeriesItem> = {
  theme: "theme_cumulative_return_pct", individual: "individual_cumulative_amount",
  foreign: "foreign_cumulative_amount", institution: "institution_cumulative_amount",
  program: "program_cumulative_amount",
};

const dailyField: Record<Exclude<Key, "theme">, keyof MarketThemeFlowChartSeriesItem> = {
  individual: "individual_daily_amount", foreign: "foreign_daily_amount",
  institution: "institution_daily_amount", program: "program_daily_amount",
};

const numberOrNull = (value: unknown) => value == null || !Number.isFinite(Number(value)) ? null : Number(value);
const pct = (value: number | null) => value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
const amount = (value: number | null) => {
  if (value == null) return "데이터 없음";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000_000) return `${sign}${(absolute / 1_000_000_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}조원`;
  if (absolute >= 100_000_000) return `${sign}${(absolute / 100_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억원`;
  return `${sign}${absolute.toLocaleString("ko-KR")}원`;
};

function bounds(values: Array<number | null>): [number, number] {
  const valid = values.filter((value): value is number => value != null);
  valid.push(0);
  let min = Math.min(...valid), max = Math.max(...valid);
  if (min === max) return [min - 1, max + 1];
  const pad = (max - min) * 0.08;
  return [min - pad, max + pad];
}

function paths(values: Array<number | null>, x: (index: number) => number, y: (value: number) => number) {
  const result: string[] = [];
  let current: string[] = [];
  values.forEach((value, index) => {
    if (value == null) {
      if (current.length) result.push(current.join(" "));
      current = [];
    } else current.push(`${current.length ? "L" : "M"}${x(index).toFixed(2)},${y(value).toFixed(2)}`);
  });
  if (current.length) result.push(current.join(" "));
  return result;
}

export default function MarketThemeFlowChartPanel({ themeId, focusDate, initialActor }: { themeId: number; focusDate?: string | null; initialActor?: Exclude<Key, "theme"> | null }) {
  const [period, setPeriod] = useState<MarketThemePriceFlowPeriod>("3M");
  const [data, setData] = useState<MarketThemeFlowChartResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [hidden, setHidden] = useState<Set<Key>>(() => {
    if (!initialActor) return new Set();
    return new Set(LINES.map((line) => line.key).filter((key) => key !== "theme" && key !== initialActor));
  });

  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    repositories.marketThemes.getThemePriceFlowChart(themeId, { period, focus_date: focusDate ?? undefined })
      .then((response) => {
        if (!active) return;
        setData(response);
        const index = focusDate ? response.series.findIndex((row) => row.trade_date === focusDate) : -1;
        setSelected(index >= 0 ? index : null);
      })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : "테마 수급 차트를 불러오지 못했습니다."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [themeId, focusDate, period]);

  const chart = useMemo(() => {
    const rows = data?.series ?? [], width = 940, height = 400;
    const plot = { left: 66, top: 30, width: 804, height: 310 };
    const x = (index: number) => plot.left + (rows.length <= 1 ? plot.width / 2 : index / (rows.length - 1) * plot.width);
    const value = (row: MarketThemeFlowChartSeriesItem, key: Key) => numberOrNull(row[cumulativeField[key]]);
    const returnDomain = bounds(rows.map((row) => value(row, "theme")));
    const flowDomain = bounds(rows.flatMap((row) => LINES.slice(1).map((line) => value(row, line.key))));
    const y = (key: Key, valueToPlot: number) => {
      const [min, max] = key === "theme" ? returnDomain : flowDomain;
      return plot.top + (max - valueToPlot) / (max - min) * plot.height;
    };
    return { rows, width, height, plot, x, value, y };
  }, [data]);
  const selectedRow = selected == null ? null : data?.series[selected] ?? null;
  const toggleLine = (key: Key) => setHidden((before) => {
    const next = new Set(before);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  if (loading) return <div className="price-flow-loading">테마 가격·수급 데이터를 계산하는 중입니다.</div>;
  if (error) return <div className="price-flow-empty is-error"><strong>차트를 불러오지 못했습니다.</strong><span>{error}</span></div>;
  if (!data || !data.series.length) return <div className="price-flow-empty"><strong>수집된 테마 수급 데이터가 없습니다.</strong><span>테마 등락률·수급 갱신을 실행하면 활성 연결 종목의 데이터가 수집됩니다.</span></div>;

  return <div className="theme-flow-chart-panel">
    <div className="price-flow-controls"><div><span>기간</span><div className="price-flow-segmented">{(["1M", "3M", "6M"] as const).map((code) => <button type="button" key={code} className={period === code ? "is-active" : ""} onClick={() => setPeriod(code)}>{code}</button>)}</div></div></div>
    <div className="price-flow-data-status"><span>기간 {data.period.start_date} ~ {data.period.end_date}</span><span>테마등락률 {data.latest_theme_return_date ?? "-"}</span><span>수급 {data.latest_flow_date ?? "-"}</span><strong>공통 기준 {data.common_latest_date ?? "-"}</strong></div>
    <div className="price-flow-summary-grid">
      <div><span>테마 누적 수익률</span><strong>{pct(data.summary.theme_return_pct)}</strong><small>{data.period.actual_trading_days}/{data.period.requested_trading_days}거래일</small></div>
      {LINES.slice(1).map((line) => {
        const actor = data.summary[line.key as Exclude<Key, "theme">];
        const isHidden = hidden.has(line.key);
        return (
          <button
            type="button"
            key={line.key}
            className={`price-flow-summary-card is-series-toggle ${isHidden ? "is-hidden" : ""}`}
            style={{ "--price-flow-series-color": line.color } as CSSProperties}
            aria-pressed={!isHidden}
            aria-label={`${line.label} 그래프 ${isHidden ? "나타내기" : "숨기기"}`}
            title={`클릭하여 ${line.label} 그래프를 ${isHidden ? "나타냅니다" : "숨깁니다"}.`}
            onClick={() => toggleLine(line.key)}
          >
            <span>{line.label} 누적</span>
            <strong style={{ color: line.color }}>{amount(actor.cumulative_amount)}</strong>
            <small>순매수 {actor.positive_days}/{data.period.actual_trading_days}일 · 종목 {actor.positive_stock_count}/{actor.data_stock_count}</small>
          </button>
        );
      })}
    </div>
    <div className="price-flow-legend">{LINES.map((line) => <button type="button" key={line.key} className={hidden.has(line.key) ? "is-hidden" : ""} onClick={() => toggleLine(line.key)}><i style={{ borderColor: line.color, borderStyle: line.dashed ? "dashed" : "solid" }} />{line.label}</button>)}</div>
    <div className="price-flow-chart-wrap">
      <svg className="price-flow-chart" viewBox={`0 0 ${chart.width} ${chart.height}`} role="img" aria-label={`${data.theme_name} 가격·수급 추이`} onClick={(event) => { const rect = event.currentTarget.getBoundingClientRect(); const svgX = (event.clientX - rect.left) / rect.width * chart.width; const ratio = Math.max(0, Math.min(1, (svgX - chart.plot.left) / chart.plot.width)); const index = Math.round(ratio * (chart.rows.length - 1)); setSelected((before) => before === index ? null : index); }}>
        {[0, .25, .5, .75, 1].map((ratio) => <line key={ratio} x1={chart.plot.left} x2={chart.plot.left + chart.plot.width} y1={chart.plot.top + ratio * chart.plot.height} y2={chart.plot.top + ratio * chart.plot.height} className="price-flow-grid-line" />)}
        <line x1={chart.plot.left} x2={chart.plot.left + chart.plot.width} y1={chart.y("individual", 0)} y2={chart.y("individual", 0)} className="price-flow-zero-line" />
        {LINES.map((line) => hidden.has(line.key) ? null : <g key={line.key}>{paths(chart.rows.map((row) => chart.value(row, line.key)), chart.x, (value) => chart.y(line.key, value)).map((path, index) => <path key={index} d={path} fill="none" stroke={line.color} strokeWidth={line.key === "theme" ? 3 : 2.2} strokeDasharray={line.dashed ? "7 5" : undefined} />)}</g>)}
        {[0, Math.floor((chart.rows.length - 1) / 2), chart.rows.length - 1].map((index) => <text key={index} x={chart.x(index)} y={chart.height - 18} textAnchor={index === 0 ? "start" : index === chart.rows.length - 1 ? "end" : "middle"} className="price-flow-axis-label">{chart.rows[index]?.trade_date.slice(5)}</text>)}
        {selected != null ? <><line x1={chart.x(selected)} x2={chart.x(selected)} y1={chart.plot.top} y2={chart.plot.top + chart.plot.height} className="price-flow-crosshair" /><text x={chart.x(selected)} y={chart.plot.top + 14} textAnchor="middle" className="theme-flow-focus-label">선택일 {chart.rows[selected].trade_date.slice(5)}</text></> : null}
      </svg>
    </div>
    {selectedRow ? <div className="price-flow-selected-detail"><div><strong>{selectedRow.trade_date}</strong><span>테마 일간 {pct(selectedRow.theme_daily_return_pct)}</span><span>기간 누적 {pct(selectedRow.theme_cumulative_return_pct)}</span><span>완전성 {selectedRow.complete_stock_count}/{selectedRow.connected_stock_count}</span></div><div className="theme-flow-selected-values">{LINES.slice(1).map((line) => <span key={line.key} style={{ color: line.color }}>{line.label} {amount(numberOrNull(selectedRow[dailyField[line.key as Exclude<Key, "theme">]]))} · 누적 {amount(numberOrNull(selectedRow[cumulativeField[line.key]]))}</span>)}</div></div> : null}
    <p className="theme-flow-basis-note">집계 기준: 현재 활성 연결 종목 · 전체 반영(FULL). 프로그램은 투자주체 합계와 분리된 보조 수급입니다.</p>
  </div>;
}
