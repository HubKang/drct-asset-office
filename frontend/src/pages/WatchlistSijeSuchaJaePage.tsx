import { useEffect, useMemo, useRef, useState } from "react";
import { ClipboardList, Copy, FileQuestion, HelpCircle, ListCollapse, ListTree, Play, RefreshCw, Search } from "lucide-react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { InvestorFlowChartItem, InvestorFlowChartResponse, InvestorFlowMetricMode, WatchlistEvaluationFactor, WatchlistEvaluationHistoryItem, WatchlistEvaluationListItem } from "@/types/watchlistEvaluation";

type ActiveFilter = "all" | "active" | "inactive";
type SijeTab = "overall" | "market" | "material" | "supply" | "chart" | "financial" | "gpt" | "history";
type ReasonModal = { title: string; body: string; missing?: string[] } | null;

const TABS: { key: SijeTab; label: string }[] = [
  { key: "overall", label: "종합" },
  { key: "market", label: "시장" },
  { key: "material", label: "재료" },
  { key: "supply", label: "수급" },
  { key: "chart", label: "차트" },
  { key: "financial", label: "재무" },
  { key: "gpt", label: "GPT 판단" },
  { key: "history", label: "평가 이력" },
];

const MISSING_LABELS: Record<string, string> = {
  price: "가격정보",
  chart: "차트",
  market: "시장지표",
  financial: "재무정보",
  supply: "수급",
  "market:DOMESTIC_INDEX_TREND": "국내 지수 흐름",
  "market:MARKET_BREADTH": "시장 체감/폭",
  "market:MARKET_LIQUIDITY": "시장 유동성",
  "market:US_MARKET_TREND": "미국 시장 흐름",
  "market:EXTERNAL_RISK": "외부 위험",
  "supply:SUPPLY_TRADING_VALUE_INTENSITY": "거래대금 강도",
  "supply:SUPPLY_CONTINUITY": "수급 연속성",
  "supply:SUPPLY_THEME_ALIGNMENT": "테마 동조",
  "supply:SUPPLY_THEME_RELATIVE_POSITION": "테마 내 상대 위치",
};

const MARKET_STATUS_LABELS: Record<string, string> = {
  EVALUATED: "평가 완료",
  PARTIAL: "일부 데이터 평가",
  DATA_MISSING: "데이터 부족",
  NOT_EVALUATED: "미평가",
  ERROR: "평가 실패",
};

function safeMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "string") return error;
  return fallback;
}

function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return "미평가";
  return `${Math.round(value)}점`;
}

function formatPreciseScore(value: number | null | undefined, suffix = "점"): string {
  if (value === null || value === undefined) return "미수집";
  return `${new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 }).format(value)}${suffix}`;
}

function formatCompactNumber(value: number | null | undefined, suffix = ""): string {
  if (value === null || value === undefined) return "-";
  return `${new Intl.NumberFormat("ko-KR", { notation: "compact", maximumFractionDigits: 1 }).format(value)}${suffix}`;
}

function formatFlowDate(value: string): string {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  return match ? `${Number(match[2])}/${Number(match[3])}` : value.slice(5) || value;
}

function formatMissing(items: string[]): string {
  if (!items.length) return "없음";
  return items.map((item) => MISSING_LABELS[item] || item).join(", ");
}

function confidenceTone(value: string): "blue" | "emerald" | "slate" | "amber" | "rose" {
  if (value === "ENOUGH") return "emerald";
  if (value === "PARTIAL") return "blue";
  if (value === "LIMITED") return "amber";
  return "slate";
}

function statusTone(value?: string | null): "blue" | "emerald" | "slate" | "amber" | "rose" {
  if (value === "EVALUATED") return "emerald";
  if (value === "PARTIAL") return "blue";
  if (value === "DATA_MISSING") return "amber";
  if (value === "ERROR") return "rose";
  return "slate";
}

function gradeTone(value?: string | null): "blue" | "emerald" | "slate" | "amber" | "rose" {
  if (value === "강한 우호" || value === "우호" || value === "강한 수급" || value === "수급 양호") return "emerald";
  if (value === "중립" || value === "보통") return "blue";
  if (value === "경계" || value === "약한 수급") return "amber";
  if (value === "위험" || value === "수급 부족") return "rose";
  return "slate";
}

function marketStatusLabel(value?: string | null): string {
  return MARKET_STATUS_LABELS[value || ""] || value || "미평가";
}

function watchCardStatusLabel(item: WatchlistEvaluationListItem): string {
  if (item.last_evaluated_at && !(item.missing_market_data || []).length && !(item.missing_supply_data || []).length && !item.missing_data.length) return "평가 완료";
  if ((item.missing_market_data || []).length || (item.missing_supply_data || []).length) return "평가 데이터 일부 누락";
  if (item.missing_data.length) return "데이터 부족";
  return item.last_evaluated_at ? "평가 완료" : "미평가";
}

function watchCardStatusClass(item: WatchlistEvaluationListItem): string {
  const label = watchCardStatusLabel(item);
  if (label === "평가 완료") return "sije-watch-card-status--complete";
  if (label === "데이터 부족") return "sije-watch-card-status--danger";
  if (label === "평가 데이터 일부 누락") return "sije-watch-card-status--warning";
  return "sije-watch-card-status--muted";
}

function ScoreBlock({
  title,
  score,
  status,
  dataList,
  onReason,
}: {
  title: string;
  score: number | null | undefined;
  status?: string | null;
  dataList: string[];
  onReason: () => void;
}) {
  const empty = score === null || score === undefined;
  return (
    <div className="sije-score-block">
      <div>
        <span className="sije-score-title">{title}</span>
        <strong className={empty ? "muted" : ""}>{formatScore(score)}</strong>
      </div>
      <p>{status || (empty ? "평가 산식 준비중" : "평가 완료")}</p>
      <div className="sije-score-meta">
        <span>사용 데이터: {dataList.length ? dataList.join(", ") : "준비중"}</span>
        <button type="button" className="sije-icon-link" onClick={onReason} title={`${title} 점수 근거`}>
          <FileQuestion size={15} />
          <span>근거</span>
        </button>
      </div>
    </div>
  );
}

type SijeEvalSummaryBadge = { label: string; tone?: "blue" | "emerald" | "slate" | "amber" | "rose" };

function EvaluationSummaryPanel({
  title,
  score,
  onHelp,
  helpTitle,
  summary,
  subSummary,
  badges,
  metaLines,
}: {
  title: string;
  score: number | null | undefined;
  onHelp?: () => void;
  helpTitle?: string;
  summary: string;
  subSummary?: string | null;
  badges: SijeEvalSummaryBadge[];
  metaLines: string[];
}) {
  return (
    <div className="sije-eval-summary-panel">
      <div className="sije-eval-summary-score">
        <div className="sije-eval-summary-title-row">
          <span className="sije-eval-summary-title">{title}</span>
          {onHelp ? (
            <button type="button" className="sije-eval-criteria-button" onClick={onHelp} title={helpTitle || `${title} 기준`}>
              <HelpCircle size={14} />
              <span>기준</span>
            </button>
          ) : null}
        </div>
        <strong className={`sije-eval-summary-score-value ${score === null || score === undefined ? "muted" : ""}`}>{formatScore(score)}</strong>
      </div>

      <div className="sije-eval-summary-body">
        <p className="sije-eval-summary-text">{summary}</p>
        {subSummary ? <p className="sije-eval-summary-subtext">{subSummary}</p> : null}
      </div>

      <aside className="sije-eval-summary-meta">
        <div className="sije-eval-badge-wrap">
          {badges.map((badge, index) => <StatusBadge key={`${badge.label}-${index}`} label={badge.label} tone={badge.tone || "slate"} />)}
        </div>
        <div className="sije-eval-meta-lines">
          {metaLines.map((line, index) => <span key={`${line}-${index}`} className="sije-eval-meta-line">{line}</span>)}
        </div>
      </aside>
    </div>
  );
}

function GenericEvaluationPanel({ item, tab, onHelp }: { item: WatchlistEvaluationListItem; tab: "material" | "chart" | "financial"; onHelp: () => void }) {
  const config = {
    material: {
      title: "재료 평가",
      score: item.material_score,
      summary: "재료 평가는 뉴스·공시·테마 데이터 연결 후 표시됩니다.",
      subSummary: "현재는 다음 단계에서 산식과 근거를 연결할 예정입니다.",
      status: "다음 단계",
    },
    chart: {
      title: "차트 평가",
      score: item.chart_score,
      summary: "차트 평가는 일봉·이동평균·거래대금 근거를 연결한 뒤 표시됩니다.",
      subSummary: "현재는 기존 수집 데이터만 표시합니다.",
      status: "다음 단계",
    },
    financial: {
      title: "재무 평가",
      score: item.financial_score,
      summary: "재무 평가는 매출·이익·부채·현금흐름 데이터 연결 후 표시됩니다.",
      subSummary: "재무정보는 준비 중입니다.",
      status: "준비 중",
    },
  }[tab];
  return (
    <section className="sije-tab-panel">
      <EvaluationSummaryPanel
        title={config.title}
        score={config.score}
        onHelp={onHelp}
        summary={config.summary}
        subSummary={config.subSummary}
        badges={[{ label: "미평가", tone: "slate" }, { label: config.status, tone: "blue" }, { label: `신뢰도 ${item.data_confidence}`, tone: confidenceTone(item.data_confidence) }]}
        metaLines={[`평가 기준일: ${item.last_evaluated_at?.slice(0, 10) || "-"}`, `미수집: ${item.missing_data.length.toLocaleString("ko-KR")}개`]}
      />
    </section>
  );
}

function MarketFactorCard({ factor }: { factor: WatchlistEvaluationFactor }) {
  const reflected = factor.contribution_score !== null && factor.contribution_score !== undefined;
  return (
    <div className={`sije-market-factor ${reflected ? "" : "missing"}`}>
      <div className="sije-market-factor-head">
        <strong>{factor.factor_name}</strong>
        <span>{reflected ? `${formatPreciseScore(factor.contribution_score)} / ${formatPreciseScore(factor.weight)}` : "미수집 / 점수 미반영"}</span>
      </div>
      <p>{factor.reason || "해석 문구가 없습니다."}</p>
      <div className="sije-market-factor-meta">
        <span>{factor.raw_value || "사용 가능한 원천 데이터가 없습니다."}</span>
        <small>기준일: {factor.source_date || "-"}</small>
      </div>
    </div>
  );
}

function MarketPanel({ item, onHelp }: { item: WatchlistEvaluationListItem; onHelp: () => void }) {
  const factors = item.market_factors || [];
  return (
    <section className="sije-tab-panel">
      <EvaluationSummaryPanel
        title="시장 평가"
        score={item.market_score}
        onHelp={onHelp}
        helpTitle="시장 점수 산정 기준"
        summary={item.market_summary || "시장 평가 전입니다."}
        subSummary="KOSPI/KOSDAQ·시장지표·미국지수·환율/금리 데이터를 기준으로 판단합니다."
        badges={[
          { label: item.market_grade || "미평가", tone: gradeTone(item.market_grade) },
          { label: marketStatusLabel(item.market_status), tone: statusTone(item.market_status) },
          { label: `신뢰도 ${item.data_confidence}`, tone: confidenceTone(item.data_confidence) },
        ]}
        metaLines={[`평가 기준일: ${item.last_evaluated_at?.slice(0, 10) || "-"}`, `미수집: ${(item.missing_market_data || []).length.toLocaleString("ko-KR")}개`]}
      />

      <div className="sije-market-factor-grid">
        {factors.length > 0 ? factors.map((factor) => <MarketFactorCard key={`${factor.factor_code}-${factor.id || factor.factor_name}`} factor={factor} />) : <EmptyState message="시장 평가 factor가 없습니다. 평가를 먼저 실행해 주세요." />}
      </div>
    </section>
  );
}

type InvestorFlowSubject = {
  key: "foreign" | "institution" | "program";
  statusKey: "foreign" | "institution" | "program";
  label: string;
  className: string;
};

const FLOW_TEXT = {
  foreign: "외국인 순매매",
  institution: "기관 순매매",
  program: "프로그램 순매매",
  won: "원",
  share: "주",
  eok: "억",
  man: "만",
  sourceUnknown: "데이터 원천 확인 중",
  sourceDerived: "가격흐름 추정 · derived_price_flow",
  sourceMock: "Mock 데이터",
  sourceReal: "실데이터 · KIWOOM_REAL · ka10059/ka90013/ka10008",
  sourcePartial: "일부 실데이터 · KIWOOM_REAL/PARTIAL",
  buyStreak: "일 연속 순매수",
  sellStreak: "일 연속 순매도",
  noStreak: "연속 흐름 없음",
  fiveDaySum: "5일 누적",
  noData: "데이터 없음",
  derivedNote: "관심종목 수집으로 저장된 일봉 가격·거래량 기반 추정 수급입니다. 실제 투자주체별 순매매 원천은 아직 연결되지 않았습니다.",
  realNote: "ka10059/ka90013/ka10008 데이터 기준 수급입니다.",
  partialNote: "일부 투자주체만 Kiwoom 실데이터로 수집되었습니다. 미수집 항목은 점수에 반영하지 않습니다.",
  collected: "수집됨",
  derived: "추정",
  missing: "미수집",
  empty: "표시할 순매매 데이터가 없습니다.",
  emptyAction: "관심종목 화면에서 최근7일수집 또는 전체수집을 실행해 주세요.",
  allZero: "선택한 기간의 순매매 값이 모두 0입니다.",
  supplyEval: "수급 평가",
  supplyHelp: "수급 점수 산정 기준",
  standard: "기준",
  beforeSupply: "수급 평가 전입니다.",
  notEvaluated: "미평가",
  confidence: "신뢰도",
  theme: "대표 테마",
  day: "일",
  count: "개",
  factorEmpty: "수급 평가 factor가 없습니다. 평가를 먼저 실행해 주세요.",
  investorFlow: "투자주체별 수급",
  baseDate: "기준일",
  noStatus: "실제 투자주체별 수급 데이터 미연결",
  realOnlyNotice: "실제 Kiwoom 외국인·기관·프로그램 순매매 원천 데이터가 없어 그래프를 표시하지 않습니다. derived_price_flow 추정 데이터는 투자주체 수급처럼 표시하지 않고 점수에도 반영하지 않습니다.",
  qty: "수량",
  amount: "금액",
  amountMissing: "금액 기준 수급 데이터가 아직 수집되지 않았습니다.",
  amountView: "금액 기준으로 보기",
  loading: "그래프 로딩 중",
} as const;

const FLOW_SUBJECTS: InvestorFlowSubject[] = [
  { key: "foreign", statusKey: "foreign", label: FLOW_TEXT.foreign, className: "foreign" },
  { key: "institution", statusKey: "institution", label: FLOW_TEXT.institution, className: "institution" },
  { key: "program", statusKey: "program", label: FLOW_TEXT.program, className: "program" },
];

function flowValue(row: InvestorFlowChartItem, subject: InvestorFlowSubject, metric: InvestorFlowMetricMode): number | null {
  const key = `${subject.key}_net_${metric}` as keyof InvestorFlowChartItem;
  const value = row[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatHoldingRatio(value: number | null | undefined): string | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  const formatted = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(value);
  return `${formatted}%`;
}

function formatFlowDateLabel(row: InvestorFlowChartItem, subject: InvestorFlowSubject): string {
  const dateLabel = formatFlowDate(row.date);
  if (subject.key !== "foreign") return dateLabel;
  const ratioLabel = formatHoldingRatio(row.foreign_holding_ratio);
  return ratioLabel ? `${dateLabel}(${ratioLabel})` : dateLabel;
}

function formatFlowValue(value: number | null | undefined, metric: InvestorFlowMetricMode): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  const abs = Math.abs(value);
  if (metric === "amount") {
    if (abs >= 100000000) return `${sign}${new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 }).format(abs / 100000000)}${FLOW_TEXT.eok}`;
    if (abs >= 10000) return `${sign}${new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 }).format(abs / 10000)}${FLOW_TEXT.man}`;
    return `${sign}${new Intl.NumberFormat("ko-KR").format(abs)}${FLOW_TEXT.won}`;
  }
  return `${sign}${new Intl.NumberFormat("ko-KR").format(abs)}${FLOW_TEXT.share}`;
}

function sourceLabel(source?: string | null): string {
  if (!source) return FLOW_TEXT.sourceUnknown;
  if (source === "kiwoom_rest_multi_investor_flow" || source === "kiwoom_rest_ka10059" || source === "kiwoom_rest_ka90013" || source === "kiwoom_rest_ka10008") return FLOW_TEXT.sourceReal;
  if (source === "KIWOOM_REAL" || source === "kiwoom") return FLOW_TEXT.sourceReal;
  if (source === "KIWOOM_PARTIAL") return FLOW_TEXT.sourcePartial;
  if (source === "DERIVED_PRICE_FLOW" || source === "derived_price_flow") return FLOW_TEXT.sourceDerived;
  if (source === "mock") return FLOW_TEXT.sourceMock;
  return `${FLOW_TEXT.sourceReal} ${source}`;
}

function sourceClass(source?: string | null): string {
  if (source === "DERIVED_PRICE_FLOW" || source === "derived_price_flow") return "derived";
  if (source === "mock") return "mock";
  if (source === "KIWOOM_REAL" || source === "KIWOOM_PARTIAL" || source === "kiwoom") return "real";
  return source ? "real" : "unknown";
}

function sourceNotice(source?: string | null): string | null {
  if (source === "kiwoom_rest_multi_investor_flow" || source === "kiwoom_rest_ka10059" || source === "kiwoom_rest_ka90013" || source === "kiwoom_rest_ka10008") return FLOW_TEXT.realNote;
  if (source === "KIWOOM_REAL" || source === "kiwoom") return FLOW_TEXT.realNote;
  if (source === "KIWOOM_PARTIAL") return FLOW_TEXT.partialNote;
  if (source === "DERIVED_PRICE_FLOW" || source === "derived_price_flow") return FLOW_TEXT.derivedNote;
  return null;
}

function flowStreak(values: number[]): number {
  if (!values.length) return 0;
  const latest = values[values.length - 1];
  const sign = latest > 0 ? 1 : latest < 0 ? -1 : 0;
  if (!sign) return 0;
  let count = 0;
  for (let i = values.length - 1; i >= 0; i -= 1) {
    const value = values[i];
    if ((sign > 0 && value > 0) || (sign < 0 && value < 0)) count += 1;
    else break;
  }
  return count * sign;
}

function streakLabel(streak: number): string {
  if (streak > 0) return `${streak}${FLOW_TEXT.buyStreak}`;
  if (streak < 0) return `${Math.abs(streak)}${FLOW_TEXT.sellStreak}`;
  return FLOW_TEXT.noStreak;
}

function InvestorFlowChartCard({ subject, rows, metric, status, scrollRef, onScroll }: { subject: InvestorFlowSubject; rows: InvestorFlowChartItem[]; metric: InvestorFlowMetricMode; status?: string; scrollRef: (node: HTMLDivElement | null) => void; onScroll: () => void }) {
  const values = rows.map((row) => flowValue(row, subject, metric)).filter((value): value is number => value !== null);
  const hasData = values.length > 0;
  const allZero = hasData && values.every((value) => value === 0);
  const maxAbs = Math.max(0, ...values.map((value) => Math.abs(value)));
  const last5Sum = values.slice(-5).reduce((sum, value) => sum + value, 0);
  const streak = flowStreak(values);
  const statusLabel = status === "COLLECTED" ? FLOW_TEXT.collected : FLOW_TEXT.missing;

  return (
    <div className={`sije-flow-chart-card ${subject.className}`}>
      <div className="sije-flow-card-head">
        <div className="sije-flow-card-title-row">
          <strong className="sije-flow-card-title">{subject.label}</strong>
          <StatusBadge label={statusLabel} tone={status === "COLLECTED" ? "emerald" : "slate"} />
        </div>
        <span className="sije-flow-card-summary">{FLOW_TEXT.fiveDaySum} {hasData ? formatFlowValue(last5Sum, metric) : "-"} {"·"} {hasData ? streakLabel(streak) : FLOW_TEXT.noData}</span>
      </div>
      <div className="sije-flow-chart-scroll" ref={scrollRef} onScroll={onScroll}>
        {!hasData ? (
          <div className="sije-flow-empty">{FLOW_TEXT.empty}<br />{FLOW_TEXT.emptyAction}</div>
        ) : allZero ? (
          <div className="sije-flow-empty">{FLOW_TEXT.allZero}</div>
        ) : rows.map((row) => {
          const value = flowValue(row, subject, metric);
          const percent = value && maxAbs > 0 ? Math.max(2, Math.abs(value) / maxAbs * 100) : 0;
          return (
            <div className={`sije-flow-row ${metric === "amount" ? "sije-flow-row--amount" : ""}`} key={`${subject.key}-${row.date}`} title={`${row.date} ${formatFlowValue(value, metric)}`}>
              <span className="sije-flow-date">{formatFlowDateLabel(row, subject)}</span>
              <div className="sije-flow-bar-zone">
                <div className="sije-flow-half negative-side">{value && value < 0 ? <span className="sije-flow-bar negative" style={{ width: `${percent}%` }} /> : null}</div>
                <span className="sije-flow-zero" />
                <div className="sije-flow-half positive-side">{value && value > 0 ? <span className="sije-flow-bar positive" style={{ width: `${percent}%` }} /> : null}</div>
              </div>
              <span className={`sije-flow-value ${value && value < 0 ? "negative" : value && value > 0 ? "positive" : ""}`}>{formatFlowValue(value, metric)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}


function MaterialMiniList({
  title,
  items,
  emptyMessage,
}: {
  title: string;
  items: Array<{ id?: number; title?: string; date?: string | null; importance?: number | null; summary?: string | null; meta?: string | null }>;
  emptyMessage: string;
}) {
  return (
    <div className="sije-material-list-card">
      <h4>{title}</h4>
      {items.length === 0 ? <p className="sije-material-empty">{emptyMessage}</p> : null}
      {items.length > 0 ? (
        <ul className="sije-material-list">
          {items.slice(0, 5).map((item, index) => (
            <li key={`${title}-${item.id || index}`}>
              <div className="sije-material-list-head">
                <strong>{item.title || "-"}</strong>
                <span>{item.date?.slice(0, 10) || "-"}</span>
              </div>
              <div className="sije-material-list-meta">
                <span>{item.meta || "-"}</span>
                <span>중요도 {formatPreciseScore(item.importance)}</span>
              </div>
              {item.summary ? <p>{item.summary}</p> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function MaterialThemeList({ item }: { item: WatchlistEvaluationListItem }) {
  const themes = item.material_themes || [];
  return (
    <div className="sije-material-list-card">
      <h4>연결 테마</h4>
      {themes.length === 0 ? <p className="sije-material-empty">연결된 활성 테마가 없습니다.</p> : null}
      {themes.length > 0 ? (
        <ul className="sije-material-list">
          {themes.slice(0, 5).map((theme, index) => (
            <li key={`${theme.theme_id || index}-${theme.theme_name}`}>
              <div className="sije-material-list-head">
                <strong>{theme.theme_name}</strong>
                <span>{theme.is_primary ? "대표" : "연결"}</span>
              </div>
              <div className="sije-material-list-meta">
                <span>30일 {formatPreciseScore(theme.return_30d, "%")}</span>
                <span>5일 {formatPreciseScore(theme.return_5d, "%")}</span>
              </div>
              <p>기준일 {theme.source_date || "-"}</p>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function FinancialPerformanceChart({ title, rows }: { title: string; rows: Array<{ period_label?: string | null; revenue?: number | null; operating_profit?: number | null; net_income?: number | null }> }) {
  const maxValue = Math.max(1, ...rows.flatMap((row) => [row.revenue || 0, Math.abs(row.operating_profit || 0), Math.abs(row.net_income || 0)]));
  return (
    <div className="sije-financial-chart">
      <h4>{title}</h4>
      {rows.length === 0 ? <div className="sije-material-empty">수집된 실적 데이터가 없습니다.</div> : (
        <div className="sije-financial-bars">
          {rows.map((row, index) => (
            <div className="sije-financial-period" key={`${row.period_label}-${index}`}>
              <div className="sije-financial-bar-set">
                {(["revenue", "operating_profit", "net_income"] as const).map((key) => <span key={key} className={`sije-financial-bar ${key}`} style={{ height: `${Math.max(2, Math.abs(row[key] || 0) / maxValue * 100)}%` }} title={`${key}: ${formatCompactNumber(row[key])}`} />)}
              </div>
              <span>{row.period_label || "-"}</span>
            </div>
          ))}
        </div>
      )}
      <div className="sije-financial-legend"><span>매출액</span><span>영업이익</span><span>당기순이익</span></div>
    </div>
  );
}

function FinancialPanel({ item, onHelp }: { item: WatchlistEvaluationListItem; onHelp: () => void }) {
  const snapshot = item.financial_snapshot || {};
  const shareholder = item.shareholder_snapshot || {};
  const metrics: Array<[string, string, string]> = [
    ["PER", snapshot.per == null ? "미수집" : `${snapshot.per}배`, ""],
    ["PBR", snapshot.pbr == null ? "미수집" : `${snapshot.pbr}배`, ""],
    ["EPS", snapshot.eps == null ? "미수집" : formatCompactNumber(Number(snapshot.eps), "원"), ""],
    ["BPS", snapshot.bps == null ? "미수집" : formatCompactNumber(Number(snapshot.bps), "원"), ""],
    ["ROE", snapshot.roe == null ? "미수집" : `${snapshot.roe}%`, ""],
    ["부채비율", snapshot.debt_ratio == null ? "미수집" : `${snapshot.debt_ratio}%`, ""],
  ];
  return (
    <section className="sije-tab-panel">
      <EvaluationSummaryPanel title="재무 평가" score={item.financial_score} onHelp={onHelp} helpTitle="재무 점수 산정 기준" summary={item.financial_summary || "재무 평가 전입니다."} subSummary="실제 수집된 재무 데이터만 사용하며 매수·매도 추천이 아닌 관찰용 리스크 평가입니다." badges={[{ label: item.financial_grade || "미평가", tone: gradeTone(item.financial_grade) }, { label: marketStatusLabel(item.financial_status), tone: statusTone(item.financial_status) }, { label: item.financial_model_version || "FINANCIAL_V1", tone: "blue" }]} metaLines={[`최근 결산 기준: ${String(snapshot.snapshot_date || "-")}`, `미수집 항목: ${(item.missing_financial_data || []).length}개`]} />
      <div className="sije-financial-metric-grid">{metrics.map(([label,value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <div className="sije-market-factor-grid">{(item.financial_factors || []).length ? (item.financial_factors || []).map((factor) => <MarketFactorCard key={factor.factor_code} factor={factor} />) : <EmptyState message="재무 평가 factor가 없습니다. 관심종목 화면에서 수집 후 평가를 실행해 주세요." />}</div>
      <div className="sije-financial-chart-grid"><FinancialPerformanceChart title="연도별 실적" rows={item.financial_annual_statements || []} /><FinancialPerformanceChart title="분기별 실적" rows={item.financial_quarterly_statements || []} /></div>
      <div className="sije-chart-metrics"><h4>주주·지분 요약</h4><div className="sije-chart-metric-grid"><div><span>최대주주명</span><strong>미수집</strong></div><div><span>최대주주 지분율</span><strong>미수집</strong></div><div><span>외국인 보유율</span><strong>{shareholder.foreign_holding_ratio == null ? "미수집" : `${shareholder.foreign_holding_ratio}%`}</strong></div><div><span>기준일</span><strong>{String(shareholder.snapshot_date || "-")}</strong></div></div></div>
    </section>
  );
}

function ChartPanel({ item, onHelp }: { item: WatchlistEvaluationListItem; onHelp: () => void }) {
  const factors = item.chart_factors || [];
  const metrics = item.chart_metrics || {};
  const metricItems = [
    ["기준일", metrics.trade_date || "-"],
    ["종가", formatCompactNumber(metrics.close_price)],
    ["MA5", formatCompactNumber(metrics.ma5)],
    ["MA10", formatCompactNumber(metrics.ma10)],
    ["MA20", formatCompactNumber(metrics.ma20)],
    ["MA60", formatCompactNumber(metrics.ma60)],
    ["MA120", formatCompactNumber(metrics.ma120)],
    ["20일선 이격률", formatPreciseScore(metrics.close_vs_ma20_pct, "%")],
    ["60일선 이격률", formatPreciseScore(metrics.close_vs_ma60_pct, "%")],
    ["60일선 5일 기울기", formatPreciseScore(metrics.ma60_slope_5d, "%")],
    ["최근 5일 상승률", formatPreciseScore(metrics.recent_5d_return, "%")],
    ["거래대금 20일 평균 대비", metrics.trading_value_ratio_20 == null ? "미수집" : `${metrics.trading_value_ratio_20.toFixed(2)}배`],
  ];
  return (
    <section className="sije-tab-panel">
      <EvaluationSummaryPanel
        title="차트 평가"
        score={item.chart_score}
        onHelp={onHelp}
        helpTitle="차트 점수 산정 기준"
        summary={item.chart_summary || "차트 평가 전입니다."}
        subSummary="20일선 눌림, 60일선 추세, 과열 이격, 최근 상승률과 거래대금 동반 여부를 관찰용으로 평가합니다."
        badges={[
          { label: item.chart_grade || "미평가", tone: gradeTone(item.chart_grade) },
          { label: marketStatusLabel(item.chart_status), tone: statusTone(item.chart_status) },
          { label: item.chart_model_version || "CHART_V1", tone: "blue" },
        ]}
        metaLines={[`평가 기준일: ${metrics.trade_date || item.last_evaluated_at?.slice(0, 10) || "-"}`, `미수집 항목: ${(item.missing_chart_data || []).length.toLocaleString("ko-KR")}개`]}
      />
      <div className="sije-market-factor-grid sije-chart-factor-grid">
        {factors.length ? factors.map((factor) => <MarketFactorCard key={`${factor.factor_code}-${factor.id || factor.factor_name}`} factor={factor} />) : <EmptyState message="차트 평가 factor가 없습니다. 평가를 먼저 실행해 주세요." />}
      </div>
      <div className="sije-chart-metrics">
        <h4>핵심 차트 지표</h4>
        <div className="sije-chart-metric-grid">
          {metricItems.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}
        </div>
      </div>
    </section>
  );
}

function MaterialPanel({ item, onHelp }: { item: WatchlistEvaluationListItem; onHelp: () => void }) {
  const factors = item.material_factors || [];
  const newsItems = (item.material_recent_news || []).map((row) => ({
    id: row.id,
    title: row.title,
    date: row.published_at,
    importance: row.importance_score,
    summary: row.summary,
    meta: row.source || row.sentiment || "뉴스",
  }));
  const disclosureItems = (item.material_recent_disclosures || []).map((row) => ({
    id: row.id,
    title: row.title,
    date: row.disclosed_at,
    importance: row.importance_score,
    summary: row.summary,
    meta: row.disclosure_type || row.risk_level || "공시",
  }));
  return (
    <section className="sije-tab-panel">
      <EvaluationSummaryPanel
        title="재료 평가"
        score={item.material_score}
        onHelp={onHelp}
        helpTitle="재료 점수 산정 기준"
        summary={item.material_summary || "재료 평가 전입니다."}
        subSummary="뉴스·공시·테마 데이터만 기준으로 재료의 존재 여부와 강도를 평가합니다. 매수/매도 추천은 포함하지 않습니다."
        badges={[
          { label: item.material_grade || "미평가", tone: gradeTone(item.material_grade) },
          { label: marketStatusLabel(item.material_status), tone: statusTone(item.material_status) },
          { label: `신뢰도 ${item.data_confidence}`, tone: confidenceTone(item.data_confidence) },
        ]}
        metaLines={[`최신 재료일: ${item.latest_material_date || "-"}`, `뉴스: ${(item.material_news_count || 0).toLocaleString("ko-KR")}건`, `공시: ${(item.material_disclosure_count || 0).toLocaleString("ko-KR")}건`, `미수집: ${(item.missing_material_data || []).length.toLocaleString("ko-KR")}개`]}
      />

      <div className="sije-market-factor-grid">
        {factors.length > 0 ? factors.map((factor) => <MarketFactorCard key={`${factor.factor_code}-${factor.id || factor.factor_name}`} factor={factor} />) : <EmptyState message="재료 평가 factor가 없습니다. 평가를 먼저 실행해 주세요." />}
      </div>

      <div className="sije-material-detail-grid">
        <MaterialMiniList title="최근 뉴스" items={newsItems} emptyMessage="최근 뉴스 데이터가 없습니다." />
        <MaterialMiniList title="최근 공시" items={disclosureItems} emptyMessage="최근 공시 데이터가 없습니다." />
        <MaterialThemeList item={item} />
      </div>
    </section>
  );
}

function SupplyPanel({ item, onHelp, flowChart, flowDays, onFlowDaysChange, flowMetric, onFlowMetricChange, flowLoading }: { item: WatchlistEvaluationListItem; onHelp: () => void; flowChart: InvestorFlowChartResponse | null; flowDays: 7 | 30 | 90; onFlowDaysChange: (days: 7 | 30 | 90) => void; flowMetric: InvestorFlowMetricMode; onFlowMetricChange: (mode: InvestorFlowMetricMode) => void; flowLoading: boolean }) {
  const factors = item.supply_factors || [];
  const investorStatus = item.supply_investor_flow_status || {};
  const hasRealInvestorFlow = Boolean(flowChart?.has_real_data && flowChart?.is_real_investor_flow && flowChart.selected_source_type === "KIWOOM_REAL");
  const flowRows = useMemo(() => (hasRealInvestorFlow ? [...(flowChart?.items || [])].sort((a, b) => a.date.localeCompare(b.date)) : []), [flowChart?.items, hasRealInvestorFlow]);
  const source = hasRealInvestorFlow ? flowChart?.source_method || "KIWOOM_REAL" : null;
  const hasAmount = flowRows.some((row) => [row.foreign_net_amount, row.institution_net_amount, row.program_net_amount].some((value) => value !== null && value !== undefined && value !== 0));
  const latestDate = typeof item.investor_flow_summary?.latest_date === "string" ? item.investor_flow_summary.latest_date : null;
  const flowScrollRefs = useRef<Record<InvestorFlowSubject["key"], HTMLDivElement | null>>({ foreign: null, institution: null, program: null });
  const syncingScrollRef = useRef(false);

  const handleFlowScroll = (sourceKey: InvestorFlowSubject["key"]) => {
    const sourceEl = flowScrollRefs.current[sourceKey];
    if (!sourceEl || syncingScrollRef.current) return;
    const sourceMax = sourceEl.scrollHeight - sourceEl.clientHeight;
    const ratio = sourceMax > 0 ? sourceEl.scrollTop / sourceMax : 0;
    syncingScrollRef.current = true;
    FLOW_SUBJECTS.forEach((subject) => {
      if (subject.key === sourceKey) return;
      const targetEl = flowScrollRefs.current[subject.key];
      if (!targetEl) return;
      const targetMax = targetEl.scrollHeight - targetEl.clientHeight;
      targetEl.scrollTop = targetMax > 0 ? targetMax * ratio : 0;
    });
    window.requestAnimationFrame(() => {
      syncingScrollRef.current = false;
    });
  };

  useEffect(() => {
    const scrollToLatest = () => {
      Object.values(flowScrollRefs.current).forEach((node) => {
        if (node) node.scrollTop = node.scrollHeight - node.clientHeight;
      });
    };
    scrollToLatest();
    const frame = window.requestAnimationFrame(scrollToLatest);
    const timer = window.setTimeout(scrollToLatest, 80);
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [flowRows, flowDays, flowMetric]);

  return (
    <section className="sije-tab-panel">
      <EvaluationSummaryPanel
        title={FLOW_TEXT.supplyEval}
        score={item.supply_score}
        onHelp={onHelp}
        helpTitle={FLOW_TEXT.supplyHelp}
        summary={item.supply_summary || FLOW_TEXT.beforeSupply}
        subSummary="거래대금·테마 흐름·투자주체별 수급 데이터를 기준으로 판단합니다."
        badges={[
          { label: item.supply_grade || FLOW_TEXT.notEvaluated, tone: gradeTone(item.supply_grade) },
          { label: marketStatusLabel(item.supply_status), tone: statusTone(item.supply_status) },
          { label: item.supply_model_version || "V1", tone: item.supply_model_version === "V2" ? "emerald" : item.supply_model_version === "V2_PARTIAL" ? "blue" : "slate" },
          { label: `${FLOW_TEXT.confidence} ${item.data_confidence}`, tone: confidenceTone(item.data_confidence) },
        ]}
        metaLines={[`${FLOW_TEXT.theme}: ${item.representative_theme_name || "-"}`, `30${FLOW_TEXT.day}: ${formatPreciseScore(item.representative_theme_return_30d, "%")}`, `${FLOW_TEXT.missing}: ${(item.missing_supply_data || []).length.toLocaleString("ko-KR")}${FLOW_TEXT.count}`]}
      />

      <div className="sije-market-factor-grid">
        {factors.length > 0 ? factors.map((factor) => <MarketFactorCard key={`${factor.factor_code}-${factor.id || factor.factor_name}`} factor={factor} />) : <EmptyState message={FLOW_TEXT.factorEmpty} />}
      </div>

      <div className="sije-investor-flow-box">
        <div className="sije-investor-flow-head">
          <div>
            <strong>{FLOW_TEXT.investorFlow}</strong>
            <span>{FLOW_TEXT.baseDate}: {flowChart?.latest_date || latestDate || "-"}</span>
          </div>
          {hasRealInvestorFlow ? <span className={`sije-flow-source-badge ${sourceClass(source)}`}>{sourceLabel(source)}</span> : null}
        </div>
        {!hasRealInvestorFlow ? <p className="sije-flow-derived-note">{FLOW_TEXT.realOnlyNotice}</p> : null}
        <div className="sije-investor-flow-toolbar">
          <div className="sije-segmented-control">
            {([7, 30, 90] as const).map((days) => <button key={days} type="button" className={flowDays === days ? "active" : ""} onClick={() => onFlowDaysChange(days)}>{days}{FLOW_TEXT.day}</button>)}
          </div>
          <div className="sije-segmented-control">
            <button type="button" className={flowMetric === "qty" ? "active" : ""} onClick={() => onFlowMetricChange("qty")}>{FLOW_TEXT.qty}</button>
            <button type="button" className={flowMetric === "amount" ? "active" : ""} disabled={!hasAmount} onClick={() => onFlowMetricChange("amount")} title={!hasAmount ? FLOW_TEXT.amountMissing : FLOW_TEXT.amountView}>{FLOW_TEXT.amount}</button>
          </div>
          {!hasAmount ? <span className="sije-flow-toolbar-note">{FLOW_TEXT.amountMissing}</span> : null}
          {flowLoading ? <span className="text-sm text-muted">{FLOW_TEXT.loading}</span> : null}
        </div>
        {flowLoading ? <EmptyState message={FLOW_TEXT.loading} /> : null}
        {!flowLoading && !hasRealInvestorFlow ? <EmptyState message={FLOW_TEXT.noStatus} /> : null}
        {!flowLoading && hasRealInvestorFlow && flowRows.length === 0 ? <EmptyState message={FLOW_TEXT.noStatus} /> : null}
        {!flowLoading && hasRealInvestorFlow && flowRows.length > 0 ? (
          <div className="sije-flow-chart-wrap">
            <div className="sije-flow-chart-grid">
              {FLOW_SUBJECTS.map((subject) => (
                <InvestorFlowChartCard
                  key={subject.key}
                  subject={subject}
                  rows={flowRows}
                  metric={flowMetric}
                  status={investorStatus[subject.statusKey]}
                  scrollRef={(node) => {
                    flowScrollRefs.current[subject.key] = node;
                  }}
                  onScroll={() => handleFlowScroll(subject.key)}
                />
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
function WatchlistSijeSuchaJaePage() {
  const [items, setItems] = useState<WatchlistEvaluationListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [keyword, setKeyword] = useState("");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("active");
  const [tab, setTab] = useState<SijeTab>("overall");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [history, setHistory] = useState<WatchlistEvaluationHistoryItem[]>([]);
  const [gptPrompt, setGptPrompt] = useState("");
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [reasonModal, setReasonModal] = useState<ReasonModal>(null);
  const [flowDays, setFlowDays] = useState<7 | 30 | 90>(30);
  const [flowMetric, setFlowMetric] = useState<InvestorFlowMetricMode>("qty");
  const [flowChart, setFlowChart] = useState<InvestorFlowChartResponse | null>(null);
  const [flowLoading, setFlowLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const result = await repositories.watchlistEvaluation.list();
      setItems(result.items);
      setSelectedId((prev) => prev ?? result.items[0]?.watchlist_id ?? null);
    } catch (loadError) {
      setError(safeMessage(loadError, "시재수차재 평가 목록을 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const filteredItems = useMemo(() => {
    const needle = keyword.trim().toLowerCase();
    return items.filter((item) => {
      if (activeFilter === "active" && !item.is_active) return false;
      if (activeFilter === "inactive" && item.is_active) return false;
      if (!needle) return true;
      return item.stock_name.toLowerCase().includes(needle) || item.stock_code.toLowerCase().includes(needle);
    });
  }, [activeFilter, items, keyword]);

  const selected = items.find((item) => item.watchlist_id === selectedId) || filteredItems[0] || null;

  useEffect(() => {
    if (!selected) return;
    setHistory([]);
    if (tab === "history") void loadHistory(selected.watchlist_id);
    if (tab === "supply") void loadInvestorFlows(selected.watchlist_id, flowDays);
  }, [selected?.watchlist_id, tab, flowDays]);

  const runAction = async (key: string, action: () => Promise<void>) => {
    setActionLoading(key);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (actionError) {
      setError(safeMessage(actionError, "작업 실행 중 오류가 발생했습니다."));
    } finally {
      setActionLoading("");
    }
  };

  const loadHistory = async (watchlistId: number) => {
    try {
      setHistory(await repositories.watchlistEvaluation.history(watchlistId));
    } catch (historyError) {
      setError(safeMessage(historyError, "평가 이력을 불러오지 못했습니다."));
    }
  };

  const loadInvestorFlows = async (watchlistId: number, days: 7 | 30 | 90) => {
    setFlowLoading(true);
    try {
      const result = await repositories.watchlistEvaluation.investorFlows(watchlistId, days);
      setFlowChart(result);
      const hasAmount = result.items.some((row) => [row.foreign_net_amount, row.institution_net_amount, row.program_net_amount].some((value) => value !== null && value !== undefined));
      if (!hasAmount) setFlowMetric("qty");
    } catch (flowError) {
      setFlowChart(null);
      setError(safeMessage(flowError, "투자주체별 수급 그래프를 불러오지 못했습니다."));
    } finally {
      setFlowLoading(false);
    }
  };

  const evaluateSelected = async () => {
    if (!selected) {
      setError("평가할 관심종목을 선택해 주세요.");
      return;
    }
    await runAction("evaluate-selected", async () => {
      const result = await repositories.watchlistEvaluation.evaluate([selected.watchlist_id]);
      setMessage(`선택 종목 평가 완료: run #${result.run_id}, ${result.evaluated_count}건`);
      await load();
      await loadHistory(selected.watchlist_id);
    });
  };

  const evaluateAll = async () => {
    await runAction("evaluate-all", async () => {
      const result = await repositories.watchlistEvaluation.evaluateAll(true);
      setMessage(`전체 관심종목 평가 완료: run #${result.run_id}, ${result.evaluated_count}건`);
      await load();
      if (selected) await loadHistory(selected.watchlist_id);
    });
  };

  const createPrompt = async () => {
    if (!selected) return;
    await runAction("gpt-prompt", async () => {
      const result = await repositories.watchlistEvaluation.createGptPrompt(selected.watchlist_id);
      setGptPrompt(result.prompt);
      setTab("gpt");
      setMessage("GPT 요청문을 생성했습니다.");
    });
  };

  const copyPrompt = async () => {
    if (!gptPrompt) return;
    await navigator.clipboard.writeText(gptPrompt);
    setMessage("GPT 요청문을 복사했습니다.");
  };

  const openReason = (title: string) => {
    if (title === "시장" && selected) {
      setReasonModal({
        title: "시장 점수 산정 기준",
        missing: selected.missing_market_data || [],
        body:
          "시장 점수는 관심종목을 평가하는 시점의 전체 시장 환경을 100점 만점으로 계산합니다.\n\n반영 영역:\n1. 국내 지수 흐름: 30점\n2. 시장 체감/폭: 20점\n3. 시장 유동성: 15점\n4. 미국 시장 흐름: 20점\n5. 외부 위험: 15점\n\n국내 지수 흐름은 KOSPI/KOSDAQ의 20일선, 60일선 위치와 최근 등락률을 반영합니다. 시장 체감/폭은 상승·하락 종목 수가 없으면 KOSPI/KOSDAQ 등락률 평균을 대체 지표로 사용합니다. 아직 수집되지 않은 데이터는 0점 처리하지 않고 점수 계산에서 제외합니다.",
      });
      return;
    }
    if (title === "수급" && selected) {
      setReasonModal({
        title: "수급 점수 산정 기준",
        missing: selected.missing_supply_data || [],
        body:
          "수급 점수는 현재 수집된 일봉 거래대금과 테마 연결 데이터를 기준으로 100점 만점 환산합니다.\n\n반영 영역:\n1. 거래대금 강도: 30점\n2. 수급 연속성: 25점\n3. 테마 동조: 25점\n4. 테마 내 상대 위치: 20점\n\n최신 거래대금이 20일 평균 대비 얼마나 강한지, 최근 5일 동안 평균 이상 거래대금이 유지됐는지, 대표 테마의 30일 흐름과 테마 내 순위를 반영합니다. 기관·외국인·프로그램·신용·공매도·대차 수급은 2차 예정이며 현재 점수와 상태를 낮추지 않습니다.",
      });
      return;
    }
    if (title === "재료" && selected) {
      setReasonModal({
        title: "재료 점수 산정 기준",
        missing: selected.missing_material_data || [],
        body:
          "재료 점수는 실제 수집된 뉴스·공시·테마 연결 데이터를 기준으로 100점 만점으로 계산합니다.\n\n반영 영역:\n1. 뉴스 재료 강도: 30점\n2. 공시 재료 강도: 25점\n3. 테마 연결도: 20점\n4. 재료 최근성: 15점\n5. 재료 지속성: 10점\n\n수집된 데이터가 없는 factor는 0점이 아니라 평가에서 제외합니다. 이 평가는 관찰용 재료 평가이며 매수/매도 추천을 포함하지 않습니다.",
      });
      return;
    }
    if (title === "재무" && selected) {
      setReasonModal({ title: "재무 점수 산정 기준", missing: selected.missing_financial_data || [], body: "재무 점수는 실제 수집된 데이터로 계산합니다.\n\n1. 성장성 25점\n2. 수익성 20점\n3. 안정성 20점\n4. 밸류에이션 부담 20점\n5. 주주·지분 안정성 15점\n\n데이터가 없는 항목은 0점이 아니라 평가에서 제외합니다. 업종 평균 비교는 1차 MVP에 반영하지 않으며 매수·매도 추천이 아닙니다." });
      return;
    }
    if (title === "차트" && selected) {
      setReasonModal({
        title: "차트 점수 산정 기준",
        missing: selected.missing_chart_data || [],
        body: "차트 점수는 실제 일봉 가격과 거래대금으로 계산한 관찰용 평가입니다.\n\n반영 영역:\n1. 60일선 추세와 위치: 25점\n2. 20일선 눌림/근접도: 25점\n3. 과열 이격 위험: 20점\n4. 최근 5일 상승률 위험: 15점\n5. 거래대금 동반 여부: 15점\n\n데이터가 없는 항목은 0점이 아니라 평가에서 제외합니다. 이 평가는 매수·매도 추천이 아닙니다.",
      });
      return;
    }
    setReasonModal({
      title: `${title} 점수 근거`,
      body: "이번 단계에서는 시장·수급 탭을 실제 산식과 연결했습니다. 재료·차트·재무 점수는 다음 단계까지 미평가 상태로 유지합니다.",
    });
  };
  return (
    <div className="sije-page">
      <PageHeader title="관심 종목 시재수차재" description="관심종목의 시장·재료·수급·차트·재무 상태를 평가하고 평가 이력을 관리합니다." />


      <div className="sije-action-bar">
        <button className="btn btn-primary" type="button" onClick={() => void evaluateSelected()} disabled={!selected || Boolean(actionLoading)}><Play size={16} /> 선택 종목 평가</button>
        <button className="btn btn-secondary" type="button" onClick={() => void evaluateAll()} disabled={Boolean(actionLoading)}><RefreshCw size={16} /> 전체 관심종목 평가</button>
        <button className="btn btn-secondary" type="button" onClick={() => void createPrompt()} disabled={!selected || Boolean(actionLoading)}><ClipboardList size={16} /> GPT 요청문 생성</button>
      </div>

      {message ? <div className="inline-result inline-success">{message}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}

      <div className={`sije-layout ${panelCollapsed ? "collapsed" : ""}`}>
        <aside className="sije-stock-list-panel">
          <div className="sije-panel-head">
            <strong>관심종목</strong>
            <button type="button" className="sije-icon-button" onClick={() => setPanelCollapsed((value) => !value)} title={panelCollapsed ? "목록 펼치기" : "목록 접기"}>{panelCollapsed ? <ListTree size={17} /> : <ListCollapse size={17} />}</button>
          </div>
          {!panelCollapsed ? (
            <>
              <div className="sije-search-row"><Search size={16} /><input className="input-control" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="종목명 또는 코드" /></div>
              <div className="sije-filter-row">
                {(["all", "active", "inactive"] as ActiveFilter[]).map((value) => <button key={value} type="button" className={activeFilter === value ? "active" : ""} onClick={() => setActiveFilter(value)}>{value === "all" ? "전체" : value === "active" ? "활성" : "비활성"}</button>)}
              </div>
              {loading ? <p className="text-sm text-muted">목록 로딩 중입니다.</p> : null}
              {!loading && filteredItems.length === 0 ? <EmptyState message="조회된 관심종목이 없습니다." /> : null}
              <div className="sije-stock-list">
                {filteredItems.map((item) => (
                  <button key={item.watchlist_id} type="button" className={`sije-stock-card ${selected?.watchlist_id === item.watchlist_id ? "selected" : ""}`} onClick={() => { setSelectedId(item.watchlist_id); setGptPrompt(""); }}>
                    <div className="sije-watch-card-main">
                      <div className="sije-watch-card-left">
                        <strong className="sije-watch-card-name">{item.stock_name}</strong>
                        <span className="sije-watch-card-meta">{item.stock_code} {"·"} {item.market || "-"}</span>
                        <span className="sije-watch-card-line">{item.total_score === null ? "종합: 미평가" : `종합: ${item.total_score}점`}</span>
                      </div>
                      <div className="sije-watch-card-right">
                        <em className={`sije-watch-card-status ${watchCardStatusClass(item)}`}>{watchCardStatusLabel(item)}</em>
                        <span className="sije-watch-card-line">시장: {formatScore(item.market_score)}{item.market_grade ? ` · ${item.market_grade}` : ""}</span>
                        <span className="sije-watch-card-line">수급: {formatScore(item.supply_score)}{item.supply_grade ? ` · ${item.supply_grade}` : ""}</span>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </>
          ) : null}
        </aside>

        <main className="sije-main-panel">
          {!selected ? <EmptyState message="평가할 관심종목을 선택해 주세요." /> : null}
          {selected ? (
            <>
              <section className="sije-stock-header">
                <div>
                  <h2>{selected.stock_name} 분석</h2>
                  <p>{selected.stock_code} · {selected.market || "-"} · 관심종목 {selected.is_active ? "활성" : "비활성"}</p>
                  <div className="sije-header-badges">
                    <StatusBadge label={selected.last_evaluated_at ? `최근 평가 ${selected.last_evaluated_at}` : "최근 평가 미평가"} tone="slate" />
                    <StatusBadge label={`시장 ${formatScore(selected.market_score)}`} tone={gradeTone(selected.market_grade)} />
                    <StatusBadge label={`수급 ${formatScore(selected.supply_score)}`} tone={gradeTone(selected.supply_grade)} />
                    <StatusBadge label={`데이터 상태: ${formatMissing(selected.missing_data)}`} tone={selected.missing_data.length ? "amber" : "emerald"} />
                    <StatusBadge label={selected.data_confidence} tone={confidenceTone(selected.data_confidence)} />
                  </div>
                </div>
                <div className="sije-total-score"><span>종합점수</span><strong className={selected.total_score === null ? "muted" : ""}>{formatScore(selected.total_score)}</strong></div>
              </section>

              <div className="sije-tabs">{TABS.map((item) => <button key={item.key} type="button" className={tab === item.key ? "active" : ""} onClick={() => setTab(item.key)}>{item.label}</button>)}</div>

              {tab === "overall" ? (
                <section className="sije-tab-panel">
                  <div className="sije-score-grid">
                    <ScoreBlock title="시장" score={selected.market_score} status={`${selected.market_grade || "미평가"} · ${marketStatusLabel(selected.market_status)}`} dataList={["KOSPI/KOSDAQ", "시장지표", "미국지수", "환율/금리"]} onReason={() => openReason("시장")} />
                    <ScoreBlock title="재료" score={selected.material_score} dataList={["뉴스", "공시", "테마"]} onReason={() => openReason("재료")} />
                    <ScoreBlock title="수급" score={selected.supply_score} status={`${selected.supply_grade || "미평가"} · ${marketStatusLabel(selected.supply_status)}`} dataList={["거래대금", "테마 흐름", "테마 내 순위", "투자주체별 수급"]} onReason={() => openReason("수급")} />
                    <ScoreBlock title="차트" score={selected.chart_score} dataList={["일봉", "이동평균", "거래대금"]} onReason={() => openReason("차트")} />
                    <ScoreBlock title="재무" score={selected.financial_score} status="재무정보 준비중" dataList={[]} onReason={() => openReason("재무")} />
                  </div>
                  <div className="sije-note">{[selected.market_summary, selected.supply_summary].filter(Boolean).join(" ") || "평가를 실행하면 종합 탭에 시장·수급 요약이 반영됩니다."}</div>
                </section>
              ) : null}

              {tab === "market" ? <MarketPanel item={selected} onHelp={() => openReason("시장")} /> : null}

              {tab === "supply" ? <SupplyPanel item={selected} onHelp={() => openReason("수급")} flowChart={flowChart} flowDays={flowDays} onFlowDaysChange={setFlowDays} flowMetric={flowMetric} onFlowMetricChange={setFlowMetric} flowLoading={flowLoading} /> : null}

              {tab === "material" ? <MaterialPanel item={selected} onHelp={() => openReason("재료")} /> : null}

              {tab === "chart" ? <ChartPanel item={selected} onHelp={() => openReason("차트")} /> : null}

              {tab === "financial" ? <FinancialPanel item={selected} onHelp={() => openReason("재무")} /> : null}


              {tab === "gpt" ? (
                <section className="sije-tab-panel"><div className="sije-gpt-panel"><textarea className="textarea-control" value={gptPrompt} readOnly placeholder="GPT 요청문 생성 버튼을 누르면 현재 선택 종목의 평가 패키지가 생성됩니다." /><button className="btn btn-secondary" type="button" disabled={!gptPrompt} onClick={() => void copyPrompt()}><Copy size={16} /> 복사</button></div></section>
              ) : null}

              {tab === "history" ? (
                <section className="sije-tab-panel">
                  {history.length === 0 ? <EmptyState message="평가 이력이 없습니다." /> : null}
                  {history.length > 0 ? (
                    <div className="table-shell"><table className="data-table compact-table"><thead><tr><th>평가일</th><th>Run</th><th>시장</th><th>재료</th><th>수급</th><th>차트</th><th>재무</th><th>종합</th><th>데이터 상태</th></tr></thead><tbody>{history.map((item) => <tr key={item.score_id}><td>{item.evaluated_at}</td><td>{item.run_type} #{item.run_id}</td><td>{formatScore(item.market_score)}{item.market_grade ? ` · ${item.market_grade}` : ""}</td><td>{formatScore(item.material_score)}</td><td>{formatScore(item.supply_score)}{item.supply_grade ? ` · ${item.supply_grade}` : ""}</td><td>{formatScore(item.chart_score)}</td><td>{formatScore(item.financial_score)}</td><td>{formatScore(item.total_score)}</td><td>{marketStatusLabel(item.market_status)} · {item.data_confidence}</td></tr>)}</tbody></table></div>
                  ) : null}
                </section>
              ) : null}
            </>
          ) : null}
        </main>
      </div>

      {reasonModal ? (
        <div className="modal-backdrop" onClick={() => setReasonModal(null)}>
          <div className="modal-card sije-reason-modal" onClick={(event) => event.stopPropagation()}>
            <div className="trade-journal-detail-header"><h3>{reasonModal.title}</h3><button className="btn btn-secondary btn-table-sm" type="button" onClick={() => setReasonModal(null)}>닫기</button></div>
            <p>{reasonModal.body}</p>
            {reasonModal.missing ? <div className="sije-modal-missing"><strong>현재 미수집/미반영 항목</strong>{reasonModal.missing.length ? <ul>{reasonModal.missing.map((item) => <li key={item}>{item}</li>)}</ul> : <span>없음</span>}</div> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default WatchlistSijeSuchaJaePage;
