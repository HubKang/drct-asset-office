import type { StockDailyFlowSummary, ThemeDailyFlowSummary } from "@/types/marketTheme";
import type { MouseEventHandler } from "react";

export type FlowActor = "individual" | "foreign" | "institution" | "program";
export const FLOW_ACTORS: Array<{ key: FlowActor; short: string; label: string; color: string }> = [
  { key: "individual", short: "개", label: "개인", color: "#2563eb" },
  { key: "foreign", short: "외", label: "외국인", color: "#dc2626" },
  { key: "institution", short: "기", label: "기관", color: "#f59e0b" },
  { key: "program", short: "P", label: "프로그램", color: "#16a34a" },
];

export const flowAmount = (value: number | null) => {
  if (value == null) return "없음";
  if (value === 0) return "0";
  const sign = value > 0 ? "+" : "-";
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000_000) return `${sign}${(absolute / 1_000_000_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조`;
  if (absolute >= 100_000_000) return `${sign}${(absolute / 100_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`;
  return `${sign}${absolute.toLocaleString("ko-KR")}`;
};

const tone = (value: number | null) => value == null || Math.abs(value) < 0.1 ? "is-neutral" : value > 0 ? "is-positive" : "is-negative";
const summaryLabel: Record<StockDailyFlowSummary["summary_code"], string> = {
  FOREIGN_INSTITUTION_BUY: "외국인·기관 동반",
  FOREIGN_LEAD: "외국인 우위",
  INSTITUTION_LEAD: "기관 우위",
  INDIVIDUAL_LEAD: "개인 우위",
  FOREIGN_INSTITUTION_SELL: "외국인·기관 매도",
  MIXED: "혼조",
  NO_DATA: "수급 없음",
};

export function StockFlowCompactCard({ summary, baseDate, onClick }: { summary?: StockDailyFlowSummary | null; baseDate?: string | null; onClick?: MouseEventHandler<HTMLButtonElement> }) {
  if (!summary || (!summary.has_investor_data && !summary.has_program_data)) {
    return <button type="button" className="stock-flow-compact is-empty" onClick={onClick} disabled={!onClick}>수급 없음</button>;
  }
  const tooltip = [
    `${baseDate ?? "-"} 수급`,
    ...FLOW_ACTORS.map(({ key, label }) => {
      const net = summary[`${key}_net_amount` as keyof StockDailyFlowSummary] as number | null;
      const strength = summary[`${key}_flow_strength` as keyof StockDailyFlowSummary] as number | null;
      return `${label}: 순매수 ${flowAmount(net)}원 · 거래대금 대비 ${strength == null ? "데이터 없음" : `${strength > 0 ? "+" : ""}${strength.toFixed(2)}%`}`;
    }),
    `요약: ${summaryLabel[summary.summary_code]}`,
  ].join("\n");
  return <button type="button" className="stock-flow-compact" title={tooltip} onClick={onClick} disabled={!onClick}>
    <span className="stock-flow-compact-main">
      {FLOW_ACTORS.slice(0, 3).map(({ key, short }) => {
        const value = summary[`${key}_flow_strength` as keyof StockDailyFlowSummary] as number | null;
        return <em key={key} className={tone(value)}>{short}{value == null ? "-" : value > 0 ? "+" : value < 0 ? "-" : "0"}</em>;
      })}
    </span>
    <small>{summaryLabel[summary.summary_code]}</small>
    <span className="stock-flow-program">P{summary.program_flow_strength == null ? " 없음" : summary.program_flow_strength > 0 ? "+" : summary.program_flow_strength < 0 ? "-" : "0"}</span>
  </button>;
}

export function ThemeFlowOverview({ summary, onActorClick, highlightedActors = [] }: { summary: ThemeDailyFlowSummary; onActorClick: (actor: FlowActor) => void; highlightedActors?: FlowActor[] }) {
  if (summary.quality_status === "EMPTY") return <div className="theme-flow-overview-empty"><strong>수집된 수급 데이터가 없습니다.</strong><span>테마 등락률·수급 갱신을 실행하면 활성 연결 종목의 수급 데이터가 수집됩니다.</span></div>;
  return <section className="theme-flow-overview">
    <div className="theme-flow-overview-head"><div><h4>테마 수급 현황</h4><p>{summary.base_date} · 현재 활성 연결 종목 · 전체 반영</p></div><span className={`price-flow-quality is-${summary.quality_status.toLowerCase()}`}>수급 데이터 {summary.complete_stock_count}/{summary.connected_stock_count}종목</span></div>
    <p className="theme-flow-daily-summary">{summary.summary_code === "FOREIGN_INSTITUTION_BUY" ? "외국인·기관 동반 순매수" : summary.summary_code === "FOREIGN_LEAD" ? "외국인 순매수 우위" : summary.summary_code === "INSTITUTION_LEAD" ? "기관 순매수 우위" : summary.summary_code === "INDIVIDUAL_LEAD" ? "개인 순매수 우위" : summary.summary_code === "FOREIGN_INSTITUTION_SELL" ? "외국인·기관 동반 순매도" : "수급 혼조"}{summary.program.net_amount != null ? ` · 프로그램 ${summary.program.net_amount > 0 ? "순매수" : summary.program.net_amount < 0 ? "순매도" : "중립"}` : " · 프로그램 데이터 없음"}</p>
    <div className="theme-flow-overview-grid">{FLOW_ACTORS.map(({ key, label, color }) => { const actor = summary[key]; return <button type="button" key={key} className={`${key === "program" ? "is-program" : ""} ${highlightedActors.includes(key) ? "is-highlighted" : ""}`} onClick={() => onActorClick(key)}><span>{label}{key === "program" ? " · 보조 수급" : ""}</span><strong style={{ color }}>{flowAmount(actor.net_amount)}원</strong><small>강도 {actor.flow_strength == null ? "-" : `${actor.flow_strength > 0 ? "+" : ""}${actor.flow_strength.toFixed(2)}%`} · {actor.positive_stock_count}/{actor.data_stock_count}종목 순매수</small></button>; })}</div>
  </section>;
}
