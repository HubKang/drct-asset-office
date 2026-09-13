import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronRight, RefreshCw, Star, X } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import InsightPerformanceView from "@/components/drctInsight/InsightPerformanceView";
import MarketThemePriceFlowPanel from "@/components/marketThemes/MarketThemePriceFlowPanel";
import { repositories } from "@/services";
import type { DrctInsightReviewItem, DrctInsightStock, DrctInsightTheme, DrctInsightToday, DrctInsightWatchItem, InsightStatus, IntradayState, ReadinessStatus } from "@/types/drctInsight";
import { buildNaverStockCandleChartUrl, getNaverChartSessionSidcode, type NaverStockCandlePeriod } from "@/utils/naverChart";
import { candidateLabel, intradayLabel, nextCheck, patternInterpretation, patternLabel, readinessText, statusSymbol, todayJudgment } from "@/utils/drctInsightUx";
import "@/styles/drctInsightUx.css";

type ReviewFilter = "ALL" | "STRONG" | "WEAK" | "MISMATCH";
type InsightStatusFilter = "ALL" | Exclude<InsightStatus, "STABLE" | "WAITING">;
export type DrawerTab = "summary" | "pattern" | "flow";
type ThemeSnapshot = { changeRate: number | null; strength: number | null; up: number; valid: number; linked: number; rank: number | null; status: InsightStatus };
type InsightSnapshot = { themes: Record<number, ThemeSnapshot> };
export type IntradayView = { state: IntradayState; reasons: string[]; themeDelta: number | null; themeChangeDelta: number | null; initialThemeDelta: number | null; breadthDelta: number | null; executionAssist: "CONSIDER_READY" | "KEEP_WATCH" | "CAUTION" };

const insightChartPeriods: Array<[NaverStockCandlePeriod, string]> = [["day", "일"], ["week", "주"], ["month", "월"]];

const executionStatus: Record<string, string> = { WAIT: "관심", READY: "매수후보", TRIGGERED: "보유중", INVALID: "제외" };
const readinessSourceLabel: Record<string, string> = { theme: "테마", flow: "수급", us_kr: "미국 연계", pattern: "차트 패턴", realtime: "장중", outcome: "성과" };
const watchOrder: Record<string, number> = { TRIGGERED: 0, READY: 1, WATCH: 2, WAIT: 3, INVALID: 4 };

function number(value: number | null, digits = 0) { return value == null ? "-" : value.toFixed(digits); }
function pct(value: number | null, digits = 1) { return value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`; }
function point(value: number | null, digits = 1) { return value == null ? "-" : `${value > 0 ? "+" : ""}${value.toFixed(digits)}`; }
function delta(current: number | null, previous: number | null) { return current == null || previous == null ? null : current - previous; }
function movement(value: number | null, suffix = "") { return value == null ? "" : `${value > 0 ? "▲" : value < 0 ? "▼" : "→"} ${point(value)}${suffix}`; }
function compactMovement(value: number | null, suffix = "", flat = .05) { if (value == null) return ""; const direction = Math.abs(value) < flat ? "→" : value > 0 ? "▲" : "▼"; return `${direction} ${point(value)}${suffix}`; }
function snapshotOf(data: DrctInsightToday): InsightSnapshot { return { themes: Object.fromEntries(data.themes.map((row) => [row.theme_id, { changeRate: row.realtime_avg_change_rate, strength: row.theme_strength, up: row.up_count, valid: row.valid_stock_count, linked: row.linked_stock_count, rank: row.realtime_rank, status: row.insight_status }])) }; }

function intradayView(stock: DrctInsightStock, previous: InsightSnapshot | null, initial: InsightSnapshot | null, priorState: IntradayState = "STABLE"): IntradayView {
  const currentThemeValue = stock.theme_strength ?? stock.theme_change_rate;
  const previousTheme = stock.theme_id == null ? null : previous?.themes[stock.theme_id];
  const initialTheme = stock.theme_id == null ? null : initial?.themes[stock.theme_id];
  const themeDelta = delta(currentThemeValue, previousTheme?.strength ?? previousTheme?.changeRate ?? null);
  const themeChangeDelta = delta(stock.theme_change_rate, previousTheme?.changeRate ?? null);
  const initialThemeDelta = delta(currentThemeValue, initialTheme?.strength ?? initialTheme?.changeRate ?? null);
  const breadthDelta = previousTheme ? stock.theme_valid_stock_count - previousTheme.valid : null;
  const relative = stock.relative_strength;
  let proposed: IntradayState = "STABLE";
  if ((themeDelta != null && themeDelta <= -1) || (breadthDelta != null && breadthDelta <= -3) || (relative != null && relative <= -2)) proposed = "WARNING";
  else if ((themeDelta != null && themeDelta <= -.3) || (breadthDelta != null && breadthDelta <= -1) || (relative != null && relative <= -.5)) proposed = "WEAKENING";
  else if (themeDelta != null && themeDelta >= .3 && (breadthDelta == null || breadthDelta >= 0) && relative != null && relative >= .5) proposed = "STRENGTHENING";
  if (proposed === "STABLE" && priorState === "STRENGTHENING" && ((themeDelta ?? 0) >= .1 || (breadthDelta ?? 0) > 0)) proposed = priorState;
  if (proposed === "STABLE" && priorState === "WEAKENING" && ((themeDelta ?? 0) <= -.1 || (breadthDelta ?? 0) < 0)) proposed = priorState;
  const reasons = previous ? [themeDelta == null ? "테마 강도 비교 대기" : `테마 강도 ${movement(themeDelta, "%p")}`, themeChangeDelta == null ? "테마 등락 비교 대기" : `테마 등락 ${movement(themeChangeDelta, "%p")}`, breadthDelta == null ? "상승 확산 비교 대기" : `상승 확산 ${previousTheme?.valid}/${previousTheme?.linked} → ${stock.theme_valid_stock_count}/${stock.theme_linked_stock_count}`, stock.relative_strength == null ? "테마 대비 강도 데이터 대기" : `테마 대비 강도 ${point(relative)}%p`] : ["장중 변화 비교를 위한 첫 상태를 저장했습니다.", stock.relative_strength == null ? "테마 대비 강도 데이터 대기" : `테마 대비 강도 ${point(relative)}%p`];
  const executionAssist = proposed === "WARNING" ? "CAUTION" : proposed === "STRENGTHENING" ? "CONSIDER_READY" : "KEEP_WATCH";
  return { state: proposed, reasons, themeDelta, themeChangeDelta, initialThemeDelta, breadthDelta, executionAssist };
}

function Readiness({ data }: { data: DrctInsightToday }) {
  const sources = Object.entries(data.readiness).filter(([key]) => key !== "overall") as Array<[string, { status: ReadinessStatus; note: string }]>;
  return <details className="insight-ux-readiness"><summary><span>데이터</span><strong>{readinessText(data.readiness.overall)}</strong><span aria-hidden="true">ⓘ</span></summary><div><header><strong>판단 데이터 준비 상태</strong><small>아직 모이지 않은 값은 0이 아닌 ‘데이터 대기’로 표시합니다.</small></header>{sources.map(([key, source]) => <section key={key}><span>{readinessSourceLabel[key] || key}</span><b>{readinessText(source.status)}</b><small>{source.note}</small></section>)}</div></details>;
}

function themeCompactLead(theme: DrctInsightTheme) {
  const us = !theme.us_lead.linked || theme.us_lead.relation_status !== "AVAILABLE" ? "US 없음" : theme.us_lead.strength === "STRONG" ? "US 강" : theme.us_lead.strength === "MODERATE" ? "US 보통" : "US 약";
  const flow = theme.gates.flow === "PASS" ? "수급 양호" : theme.gates.flow === "WEAK" ? "수급 약함" : theme.gates.flow === "NO_DATA" ? "수급 데이터 대기" : "수급 관찰";
  return `${us} · ${flow}`;
}

function stockWhy(stock: DrctInsightStock) {
  const theme = stock.theme_name ? `${stock.theme_name} 관찰 #${stock.observation_rank ?? "-"}` : "독립 모멘텀 관찰";
  const lead = stock.us_lead.linked && stock.us_lead.relation_status === "AVAILABLE" && stock.us_lead.strength === "STRONG" ? `미국 ${stock.us_lead.us_theme_name || "연결 테마"} 강세` : theme;
  return `${lead} · 패턴 유사도 ${number(stock.success_similarity)}`;
}

function judgmentText(stock: DrctInsightStock, view: IntradayView) {
  if (stock.gates.execution === "READY" || view.executionAssist === "CONSIDER_READY") return "실행 검토";
  if (view.state === "WARNING") return "주의하며 관찰";
  return "관찰 유지";
}

function signalStateLabel(state: IntradayState) {
  if (state === "STRENGTHENING") return "▲ 강화";
  if (state === "WEAKENING") return "▼ 약화";
  if (state === "WARNING") return "! 주의";
  return "→ 유지";
}

function themeSignalReason(theme: DrctInsightTheme) {
  if (theme.signal_key_reason && !/호환 표시|기존 저장 결과/.test(theme.signal_key_reason)) return theme.signal_key_reason;
  const flow = theme.gates.flow === "PASS" ? "수급 양호" : theme.gates.flow === "WEAK" ? "수급 약함" : theme.gates.flow === "NO_DATA" ? "수급 대기" : "수급 관찰";
  return `D+1 관찰 #${theme.observation_rank ?? "-"} · ${theme.signal_stage_label || "가격·수급 신호"} · ${flow}`;
}

const insightStatusLabel: Record<InsightStatus, string> = { NEW: "신규", STRENGTHENING: "강화", STABLE: "유지", WEAKENING: "약화", MISMATCH: "판단 불일치", WAITING: "대기" };

function themeInsightStatus(theme: DrctInsightTheme, previous: ThemeSnapshot | null | undefined, realtimeReady: boolean): InsightStatus {
  if (!realtimeReady || theme.insight_status === "WAITING") return "WAITING";
  const strengthDelta = delta(theme.theme_strength, previous?.strength ?? null);
  const breadthDelta = previous ? theme.up_count - previous.up : null;
  const rankGain = previous?.rank != null && theme.realtime_rank != null ? previous.rank - theme.realtime_rank : null;
  if ((strengthDelta ?? 0) <= -.3 || (breadthDelta ?? 0) <= -1) return (theme.realtime_avg_change_rate ?? 0) > 0 && (breadthDelta ?? 0) < 0 ? "MISMATCH" : "WEAKENING";
  if (!theme.focus_candidate_count && ((strengthDelta ?? 0) >= .3 || (rankGain ?? 0) >= 3)) return "NEW";
  if ((strengthDelta ?? 0) >= .3 && (breadthDelta == null || breadthDelta >= 0)) return "STRENGTHENING";
  return theme.insight_status;
}

function themeJudgmentScore(theme: DrctInsightTheme) {
  const value = theme.d1_candidate_score ?? theme.theme_score ?? theme.theme_percentile ?? theme.flow_score;
  return value == null ? null : Math.max(0, Math.min(100, Math.round(value)));
}

function themeInsightLine(theme: DrctInsightTheme, status: InsightStatus, realtimeReady: boolean) {
  if (!realtimeReady || status === "WAITING") return "전일까지의 선행 신호를 유지하며 오늘 장중 테마 반응을 기다립니다.";
  if (status === theme.insight_status && theme.insight_interpretation) return theme.insight_interpretation;
  if (status === "MISMATCH") return "가격 흐름과 수급·확산 방향이 엇갈립니다.";
  if (status === "NEW") return "장중 강도 상승으로 새롭게 탐지됐습니다.";
  if (status === "STRENGTHENING") return "가격과 수급 신호가 함께 강화되고 있습니다.";
  if (status === "WEAKENING") return "기존 판단을 지지하던 장중 근거가 줄고 있습니다.";
  return "현재 반응을 유지하며 다음 Snapshot의 변화를 확인합니다.";
}

function patternQuality(stock: DrctInsightStock) {
  if (!stock.success_sample_count) return "유사 사례 부족";
  if (stock.pattern_status === "VERIFIED" || stock.success_similarity >= 70) return "패턴 양호";
  if (stock.pattern_status === "WEAK" || (stock.pattern_edge ?? 1) <= 0) return "패턴 확인 필요";
  return "패턴 보통";
}

function reviewCategories(item: DrctInsightReviewItem, view: IntradayView | undefined) {
  const categories = [...item.categories]; const d0 = item.outcome.d0_return;
  if (d0 != null && view && ((view.state === "STRENGTHENING" && d0 < 0) || (["WEAKENING", "WARNING"] as IntradayState[]).includes(view.state) && d0 >= 3)) categories.push("MISMATCH");
  return [...new Set(categories)];
}

function PostMarketPanel({ data, views, filter, onFilter, onOpen }: { data: DrctInsightToday; views: Record<number, IntradayView>; filter: ReviewFilter; onFilter: (value: ReviewFilter) => void; onOpen: (stockId: number) => void }) {
  const summary = data.outcome_summary;
  const reviews = data.review_queue
    .filter((item) => filter === "ALL" || reviewCategories(item, views[item.stock_id]).includes(filter))
    .sort((a, b) => (b.outcome.d0_return ?? Number.NEGATIVE_INFINITY) - (a.outcome.d0_return ?? Number.NEGATIVE_INFINITY))
    .slice(0, 10);
  const returnTone = (value: number | null) => value == null || value === 0 ? "is-flat" : value > 0 ? "is-positive" : "is-negative";
  return <section className="insight-ux-post"><header><div><small>장후 판단</small><h2>오늘 집중 후보 {summary.focus_count}개 중 {summary.positive_count}개가 상승했습니다.</h2><p>테마보다 강했던 종목 {summary.theme_outperform_count}개 · 복기 대상 {summary.review_count}개</p></div><dl><div><dt>평균 D0</dt><dd>{pct(summary.average_d0_return, 2)}</dd></div><div><dt>복기 추천</dt><dd>{summary.review_count}</dd></div></dl></header><nav aria-label="복기 필터">{([['ALL','전체'],['STRONG','강세'],['WEAK','약세'],['MISMATCH','판단 불일치']] as const).map(([key,label]) => <button type="button" key={key} className={filter === key ? "is-active" : ""} onClick={() => onFilter(key)}>{label}</button>)}</nav><div>{reviews.map((item) => <button type="button" className={returnTone(item.outcome.d0_return)} key={item.stock_id} onClick={() => onOpen(item.stock_id)}><span>{item.theme_name || "연결 테마 없음"}</span><strong>{item.stock_name}</strong><em>{item.outcome.status === "NOT_READY" ? "평가 대기" : pct(item.outcome.d0_return, 2)}</em></button>)}</div></section>;
}

function WatchDrawer({ watches, views, realtimeStatus, onOpen, onUpdate, onClose }: { watches: DrctInsightWatchItem[]; views: Record<number, IntradayView>; realtimeStatus: ReadinessStatus; onOpen: (stock: DrctInsightStock) => void; onUpdate: (row: DrctInsightWatchItem, value: string) => void; onClose: () => void }) {
  return <div className="insight-drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><aside className="insight-drawer insight-watch-drawer" role="dialog" aria-modal="true" aria-label="내 관찰 종목"><header><div><small>MY WATCH</small><h3>내 관찰 {watches.length}</h3><p>오늘 직접 확인할 종목입니다.</p></div><button type="button" aria-label="닫기" onClick={onClose}><X size={20}/></button></header><div className="insight-watch-drawer-body">{watches.map((row) => { const view = views[row.stock_id] || { state: "STABLE" as IntradayState }; return <article key={row.watchlist_id} role="button" tabIndex={0} onClick={() => onOpen(row)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onOpen(row); }}><header><h4>{row.stock_name}</h4><strong className={(row.change_rate ?? 0) >= 0 ? "is-up" : "is-down"}>{pct(row.change_rate,2)}</strong></header><dl><div><dt>장중 흐름</dt><dd>{statusSymbol(view.state)} {intradayLabel(view.state)}</dd></div><div><dt>내 상태</dt><dd><select aria-label={`${row.stock_name} 내 상태`} value={row.gates.execution || "WAIT"} onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()} onChange={(event) => onUpdate(row,event.target.value)}><option value="WAIT">대기 (WAIT)</option><option value="READY">실행 검토 (READY)</option><option value="TRIGGERED">실행 조건 도달 (TRIGGERED)</option><option value="INVALID">관찰 제외 (INVALID)</option></select></dd></div><div><dt>다음 확인</dt><dd>{nextCheck(row, view.state, realtimeStatus)}</dd></div></dl></article>; })}{!watches.length ? <div className="insight-ux-empty"><strong>내 관찰 종목이 없습니다.</strong><p>집중 후보의 별을 눌러 추가하세요.</p></div> : null}</div></aside></div>;
}

export function InsightDrawer({ stock, view, postMarket, analysisDate, realtimeStatus, loading, tab, onTab, onRefresh, onClose }: { stock: DrctInsightStock; view: IntradayView; postMarket: boolean; analysisDate: string | null; realtimeStatus: ReadinessStatus; loading: boolean; tab: DrawerTab; onTab: (tab: DrawerTab) => void; onRefresh: () => void; onClose: () => void }) {
  const [zoomedChart, setZoomedChart] = useState<{ url: string; alt: string } | null>(null);
  useEffect(() => { const handler = (event: KeyboardEvent) => { if (event.key !== "Escape") return; if (zoomedChart) setZoomedChart(null); else onClose(); }; window.addEventListener("keydown", handler); return () => window.removeEventListener("keydown", handler); }, [onClose, zoomedChart]);
  const decision = judgmentText(stock, view); const next = nextCheck(stock, view.state, realtimeStatus);
  const why = [stock.focus_candidate ? `오늘 집중 후보 #${stock.focus_rank}` : candidateLabel(stock), stock.observation_rank ? `${stock.theme_name || "연결 테마"} D+1 후보 #${stock.observation_rank}` : null, `패턴 유사도 ${number(stock.success_similarity)} · ${patternQuality(stock)}`, stock.gates.flow === "PASS" ? "테마 수급 양호" : null].filter(Boolean) as string[];
  const warnings = stock.warning_items.filter((item) => !/실패.*표본|Marker.*표본|Pattern Edge|구분력/.test(item));
  if (stock.failure_sample_count < stock.required_failure_sample_count) warnings.unshift("실패 사례 표본 부족");
  if (stock.pattern_edge == null) warnings.push("Pattern Edge 미확정 · 성공/실패 구분력 데이터 축적 중");
  const compactWarnings = [...new Set(warnings)].slice(0, 3);
  const nextItems = [next, stock.relative_strength == null ? "종목이 테마보다 강해지는지 확인" : stock.relative_strength < 0 ? "종목 상대강도가 회복되는지 확인" : "테마 대비 강도가 유지되는지 확인"];
  const candidateSummary = stock.focus_candidate && stock.focus_rank ? `집중 후보 #${stock.focus_rank}` : candidateLabel(stock);
  const d0 = stock.outcome?.analysis_date || analysisDate;
  const markerHref = `#/trading/chart-markers?stock_id=${stock.stock_id}&marker_date=${encodeURIComponent(d0 || "")}&stock_name=${encodeURIComponent(stock.stock_name)}${stock.theme_id ? `&theme_id=${stock.theme_id}` : ""}`;
  return <div className="insight-drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><aside className="insight-drawer insight-ux-drawer" role="dialog" aria-modal="true" aria-label={`${stock.stock_name} Insight 상세`}><header className={`insight-ux-drawer-hero is-${view.state.toLowerCase()}`}><div className="insight-ux-drawer-identity"><div className="insight-ux-drawer-title-line"><h3>{stock.stock_name}</h3><span>{candidateSummary}</span></div><p>{stock.stock_code} · {stock.theme_name || "연결 테마 없음"}</p></div><div className="insight-ux-drawer-current"><small>현재 흐름</small><strong>{signalStateLabel(view.state)}</strong><b aria-hidden="true">›</b><span>{decision}</span></div><div className="insight-ux-drawer-actions"><button type="button" disabled={loading} onClick={onRefresh}><RefreshCw size={15}/><span>{loading ? "갱신 중" : "새로고침"}</span></button><button type="button" aria-label="닫기" onClick={onClose}><X size={20}/></button></div></header><nav role="tablist" aria-label="종목 상세"><button role="tab" aria-selected={tab === "summary"} className={tab === "summary" ? "is-active" : ""} onClick={() => onTab("summary")}>판단 요약</button><button role="tab" aria-selected={tab === "pattern"} className={tab === "pattern" ? "is-active" : ""} onClick={() => onTab("pattern")}>차트 패턴</button><button role="tab" aria-selected={tab === "flow"} className={tab === "flow" ? "is-active" : ""} onClick={() => onTab("flow")}>수급 흐름</button></nav><div className="insight-drawer-body">
    {tab === "summary" ? <><div className={`insight-summary-workspace is-${view.state.toLowerCase()}`}><section className={`insight-decision-board is-${view.state.toLowerCase()}`}><header><div><span>판단 카드</span><strong>{stock.stock_name}</strong></div><p>현재 흐름과 대응 기준을 한눈에 확인합니다.</p></header><dl><div><dt>현재 흐름</dt><dd>{signalStateLabel(view.state)}</dd></div><div><dt>대응 판단</dt><dd>{decision}</dd></div><div><dt>테마</dt><dd>{stock.observation_rank ? `#${stock.observation_rank}` : "-"}</dd></div><div><dt>성공 유사</dt><dd>{number(stock.success_similarity)}</dd></div><div><dt>테마 대비</dt><dd>{stock.relative_strength == null ? "-" : `${point(stock.relative_strength)}%p`}</dd></div><div><dt>수급</dt><dd>{stock.gates.flow === "PASS" ? "양호" : stock.gates.flow === "WEAK" ? "약함" : stock.gates.flow === "NO_DATA" ? "대기" : "관찰"}</dd></div></dl></section><section className="insight-compact-list is-reason"><h4>왜 보는가</h4>{why.map((item) => <p key={item}><span className="insight-list-bullet" aria-hidden="true">▶</span>{item}</p>)}</section><section className="insight-compact-list is-next"><h4>다음 확인</h4>{[...new Set(nextItems)].map((item) => <p key={item}><span className="insight-list-bullet" aria-hidden="true">▶</span>{item}</p>)}</section><section className={`insight-compact-list is-warning${compactWarnings.length ? "" : " is-clear"}`}><h4>주의</h4>{compactWarnings.length ? compactWarnings.map((item) => <p key={item}><span className="insight-list-bullet" aria-hidden="true">▶</span>{item}</p>) : <p><span className="insight-list-bullet" aria-hidden="true">▶</span>현재 추가 주의 신호가 없습니다.</p>}</section></div><details className="insight-ux-system"><summary>판단 근거 상세</summary><dl><div><dt>THEME</dt><dd>{stock.gates.theme}</dd></div><div><dt>FLOW</dt><dd>{stock.gates.flow}</dd></div><div><dt>Pattern status</dt><dd>{stock.pattern_status}</dd></div><div><dt>Rule</dt><dd>{stock.candidate_band || "-"}</dd></div><div><dt>Percentile</dt><dd>{number(stock.convergence_level)}</dd></div><div><dt>S / F</dt><dd>{number(stock.success_similarity)} / {number(stock.failure_similarity)}</dd></div><div><dt>US Lead</dt><dd>{stock.us_lead.strength || stock.us_lead.relation_status}</dd></div></dl></details></> : null}
    {tab === "pattern" ? <><section className="insight-pattern-signal"><header><span>패턴 상태</span><strong>{patternLabel(stock.pattern_status)}</strong></header><div className="insight-pattern-matrix"><div className="is-success"><dt>성공 유사</dt><dd>{number(stock.success_similarity)} / 100</dd><i><b style={{width:`${Math.max(0, Math.min(100, stock.success_similarity || 0))}%`}}/></i></div><div><dt>실패 유사</dt><dd>{stock.failure_similarity == null ? "사례 부족" : `${number(stock.failure_similarity)} / 100`}</dd></div><div><dt>구분력</dt><dd>{stock.pattern_edge == null ? "데이터 축적 중" : point(stock.pattern_edge)}</dd></div><div><dt>비교 사례</dt><dd>성공 {stock.success_sample_count} · 실패 {stock.failure_sample_count}/{stock.required_failure_sample_count}</dd></div></div><p>ⓘ {patternInterpretation(stock)}</p></section><section className="insight-price-position is-compact"><header><strong>가격 위치</strong><small>현재 Insight 데이터 기준</small></header><dl><div><dt>현재</dt><dd className={(stock.change_rate ?? 0) >= 0 ? "is-up" : "is-down"}>{pct(stock.change_rate,2)}</dd></div><div><dt>테마</dt><dd>{pct(stock.theme_change_rate,2)}</dd></div><div><dt>테마 대비</dt><dd className={(stock.relative_strength ?? 0) >= 0 ? "is-up" : "is-down"}>{stock.relative_strength == null ? "대기" : `${point(stock.relative_strength)}%p`}</dd></div><div><dt>기준일</dt><dd>{d0?.slice(5).replace("-", "/") || "-"}</dd></div></dl><p>20일선·최근 고점 위치는 미연계</p></section><div className="insight-ux-chart-tools"><span>D0 분석 기준일 · {d0 || "-"}</span><a className="insight-marker-link" href={markerHref}>유사 차트 사례 보기 <ChevronRight size={14}/></a></div><div className="insight-ux-chart-grid">{insightChartPeriods.map(([period, label]) => { const url = buildNaverStockCandleChartUrl(stock.stock_code, period, getNaverChartSessionSidcode()); const alt = `${stock.stock_name} ${label}봉 가격 차트`; return <button type="button" key={period} className="insight-ux-chart-button" aria-label={`${alt} 크게 보기`} onClick={() => setZoomedChart({ url, alt })}><strong>{label}봉</strong><img className="insight-chart" src={url} alt={alt}/></button>; })}</div></> : null}
    {tab === "flow" ? <><section className={`insight-supply-theme-strip is-${stock.gates.flow.toLowerCase()}`}><header><span>테마 수급</span><strong>{stock.gates.flow === "PASS" ? "양호" : stock.gates.flow === "WEAK" ? "약함" : stock.gates.flow === "NO_DATA" ? "데이터 부족" : "관찰"}</strong></header><dl><div><dt>테마 강도</dt><dd>{stock.theme_strength == null ? "대기" : number(stock.theme_strength, 2)}</dd></div><div><dt>직전 대비</dt><dd>{movement(view.themeDelta, "%p") || "대기"}</dd></div><div><dt>상승 확산</dt><dd>{stock.theme_strength == null ? "대기" : `${stock.theme_valid_stock_count}/${stock.theme_linked_stock_count}`}</dd></div><div><dt>테마 대비</dt><dd>{stock.relative_strength == null ? "대기" : `${point(stock.relative_strength)}%p`}</dd></div></dl></section><div className="insight-ux-supply-board">{stock.theme_id ? <MarketThemePriceFlowPanel stockId={stock.stock_id} themeId={stock.theme_id} focusDate={d0}/> : <div className="insight-supply-empty">종목 투자주체 수급 데이터가 없습니다.</div>}</div></> : null}
    {postMarket && stock.outcome ? <section className="insight-ux-post-result"><strong>장후 결과</strong><span>D0 {pct(stock.outcome.d0_return, 2)} · 테마 대비 {point(stock.outcome.relative_return)}%p</span></section> : null}
  </div></aside>{zoomedChart ? <div className="stock-management-chart-modal" onClick={() => setZoomedChart(null)}><img src={zoomedChart.url} alt={zoomedChart.alt} className="stock-management-chart-modal-image" onClick={(event) => { event.stopPropagation(); setZoomedChart(null); }}/></div> : null}</div>;
}

function DrctInsightPage() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState<DrctInsightToday | null>(() => repositories.drctInsight.peekToday()); const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  const [workspace, setWorkspace] = useState<"today" | "performance">(() => searchParams.get("view") === "performance" ? "performance" : "today"); const [statusFilter, setStatusFilter] = useState<InsightStatusFilter>("ALL"); const [themeId, setThemeId] = useState<number | null>(() => Number(searchParams.get("theme")) || null); const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("ALL"); const [selected, setSelected] = useState<DrctInsightStock | null>(null); const [watchOpen, setWatchOpen] = useState(false); const [drawerTab, setDrawerTab] = useState<DrawerTab>("summary"); const [views, setViews] = useState<Record<number, IntradayView>>({});
  const requestRef = useRef(0); const abortRef = useRef<AbortController | null>(null); const initialSnapshotRef = useRef<InsightSnapshot | null>(null); const previousSnapshotRef = useRef<InsightSnapshot | null>(null); const currentSnapshotRef = useRef<InsightSnapshot | null>(null); const stateRef = useRef<Record<number, IntradayState>>({});

  const load = useCallback(async (force=true) => {
    const requestId = ++requestRef.current; abortRef.current?.abort(); const controller = new AbortController(); abortRef.current = controller; setLoading(true); setError("");
    try {
      let next = await repositories.drctInsight.today(controller.signal, force); if (requestId !== requestRef.current) return;
      if (next.market_mode === "POST_MARKET" && !next.evaluation_captured) next = await repositories.drctInsight.captureTodayEvaluation(controller.signal);
      const snapshot = snapshotOf(next); const previous = currentSnapshotRef.current; if (!initialSnapshotRef.current) initialSnapshotRef.current = snapshot;
      const nextViews = Object.fromEntries(next.stocks.map((row) => [row.stock_id, intradayView(row, previous, initialSnapshotRef.current, stateRef.current[row.stock_id])]));
      stateRef.current = Object.fromEntries(Object.entries(nextViews).map(([key, value]) => [Number(key), value.state])); previousSnapshotRef.current = previous; currentSnapshotRef.current = snapshot;
      const defaultTheme = [...next.themes].filter((row) => row.focus_candidate_count > 0).sort((a,b) => (a.observation_rank ?? 999) - (b.observation_rank ?? 999))[0] || [...next.themes].sort((a,b) => (a.observation_rank ?? 999) - (b.observation_rank ?? 999))[0];
      setViews(nextViews); setData(next); setThemeId((current) => current && next.themes.some((row) => row.theme_id === current) ? current : defaultTheme?.theme_id ?? null); setSelected((current) => { const queryStock = Number(searchParams.get("stock")); return current ? next.stocks.find((row) => row.stock_id === current.stock_id) || null : queryStock ? next.stocks.find((row) => row.stock_id === queryStock) || null : null; });
    } catch (cause) { if (requestId === requestRef.current && !controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Insight를 불러오지 못했습니다."); }
    finally { if (requestId === requestRef.current) setLoading(false); }
  }, [searchParams]);
  useEffect(() => { void load(false); return () => abortRef.current?.abort(); }, [load]);

  const realtimeReady = data?.readiness.realtime.status === "READY";
  const insightThemes = useMemo(() => [...(data?.themes || [])].map((theme) => { const previous = previousSnapshotRef.current?.themes[theme.theme_id]; const status = themeInsightStatus(theme, previous, Boolean(realtimeReady)); const change = delta(theme.theme_strength, previous?.strength ?? null); const breadthChange = previous ? theme.up_count - previous.up : null; const rankChange = previous?.rank != null && theme.realtime_rank != null ? previous.rank - theme.realtime_rank : null; return { theme, status, change, breadthChange, rankChange, score: themeJudgmentScore(theme) }; }).sort((a,b) => Number(b.status === "MISMATCH")-Number(a.status === "MISMATCH") || (b.score ?? -1)-(a.score ?? -1)), [data, realtimeReady]);
  const themes = useMemo(() => insightThemes.filter((row) => statusFilter === "ALL" || row.status === statusFilter), [insightThemes, statusFilter]);
  const selectedTheme = data?.themes.find((theme) => theme.theme_id === themeId) || null;
  const selectedInsight = insightThemes.find((row) => row.theme.theme_id === themeId) || null;
  const themeStocks = useMemo(() => (data?.stocks || []).filter((row) => row.theme_id === themeId).sort((a,b) => Number(b.final_candidate)-Number(a.final_candidate) || Number(b.focus_candidate)-Number(a.focus_candidate) || (a.focus_rank ?? 999)-(b.focus_rank ?? 999) || b.success_similarity-a.success_similarity), [data, themeId]);
  const watches = useMemo(() => [...(data?.my_watch || [])].sort((a,b) => (watchOrder[a.gates.execution || "WAIT"] ?? 9) - (watchOrder[b.gates.execution || "WAIT"] ?? 9)), [data]);
  const watchIds = useMemo(() => new Set(watches.map((row) => row.stock_id)), [watches]);
  const fallbackView: IntradayView = { state: "STABLE", reasons: ["변화 비교 대기"], themeDelta: null, themeChangeDelta: null, initialThemeDelta: null, breadthDelta: null, executionAssist: "KEEP_WATCH" };
  const postMarket = data?.market_mode === "POST_MARKET";
  const judgment = data ? todayJudgment(data, Object.values(views).map((view) => view.state)) : "오늘의 판단을 준비하고 있습니다.";
  const keyInsights = insightThemes.filter((row) => (statusFilter === "ALL" || row.status === statusFilter) && (row.theme.focus_candidate_count > 0 || row.status !== "STABLE")).slice(0, 4);
  const changes = insightThemes.filter((row) => (row.change != null && Math.abs(row.change) >= .3) || (row.breadthChange != null && Math.abs(row.breadthChange) >= 1) || (row.rankChange != null && Math.abs(row.rankChange) >= 3) || row.status === "MISMATCH" || row.status === "NEW").slice(0, 4);

  const toggleWatch = async (stock: DrctInsightStock) => { const watch = watches.find((row) => row.stock_id === stock.stock_id); if (watch) await repositories.watchlist.update(watch.watchlist_id, { is_active: 0 }); else await repositories.watchlist.bulkAdd({ stock_ids: [stock.stock_id], memo: "DrCT 실시간 인사이트" }); await load(true); };
  const updateWatch = async (row: DrctInsightWatchItem, value: string) => { await repositories.watchlist.update(row.watchlist_id, { status: executionStatus[value] || "관심" }); await load(true); };
  const openStock = (stock: DrctInsightStock) => { setWatchOpen(false); setSelected(stock); setDrawerTab("summary"); };

  if (workspace === "performance") return <div className="drct-insight-page"><PageHeader title="DrCT 실시간 인사이트" description="D+1 테마 후보를 포함한 집중·검증 후보의 실제 D+N 성과를 확인합니다."/><InsightPerformanceView onToday={() => setWorkspace("today")}/></div>;
  return <div className="drct-insight-page insight-ux-page">
    <header className="insight-ux-header insight-v2-header"><div className="insight-ux-title"><div><h1>DrCT 실시간 인사이트</h1><p className="insight-ux-title-description">DrCT 전체 데이터를 연결해 현재 의미 있는 시장 변화와 판단 근거를 보여줍니다.</p></div><div className="insight-ux-title-actions"><button type="button" className="insight-watch-button" onClick={() => setWatchOpen(true)}><Star size={16} fill={watches.length ? "currentColor" : "none"}/>내 관심종목 <b>{watches.length}</b></button><button type="button" className="btn btn-secondary" disabled={loading} onClick={() => void load()}><RefreshCw size={15}/>{loading ? "갱신 중" : "새로고침"}</button></div></div><div className="insight-v2-meta"><span>{judgment}</span><div>{data ? <Readiness data={data}/> : null}<small>{data?.market_mode === "POST_MARKET" ? "장후" : data?.market_mode === "PRE_MARKET" ? "장전" : "장중"} · {data?.summary.last_updated_at?.slice(11,16) || "-"}</small><button type="button" onClick={() => setWorkspace("performance")}>과거 판단 검증 →</button></div></div></header>
    {error ? <div className="insight-error">{error}<button type="button" onClick={() => void load()}>다시 시도</button></div> : null}
    <section className="insight-v2-key"><header><div><h2>현재 핵심 인사이트</h2><p>선행 가설과 오늘 실제 반응이 함께 만든 결론입니다.</p></div><nav aria-label="인사이트 상태 필터">{([['ALL','전체'],['NEW','신규'],['STRENGTHENING','강화'],['WEAKENING','약화'],['MISMATCH','판단 불일치']] as const).map(([key,label]) => <button type="button" key={key} className={statusFilter === key ? "is-active" : ""} onClick={() => setStatusFilter(key)}>{label}</button>)}</nav></header><div className="insight-v2-key-grid">{keyInsights.map(({theme,status,change,score}) => <button type="button" key={theme.theme_id} className={`is-${status.toLowerCase()}`} onClick={() => setThemeId(theme.theme_id)}><div><strong>{theme.theme_name}</strong><em>{insightStatusLabel[status]}</em></div><p>{themeInsightLine(theme,status,Boolean(realtimeReady))}</p><b>{score ?? "대기"} <small>{change == null ? "" : compactMovement(change,"%p",.1)}</small></b><ul>{[themeSignalReason(theme), theme.realtime_avg_change_rate == null ? "장중 반응 대기" : `실시간 ${pct(theme.realtime_avg_change_rate,2)}`, theme.valid_stock_count ? `상승 확산 ${theme.up_count}/${theme.valid_stock_count}` : null].filter(Boolean).slice(0,3).map((item) => <li key={String(item)}>{item}</li>)}</ul></button>)}{data && !keyInsights.length ? <div className="insight-ux-empty"><strong>핵심 인사이트를 준비하고 있습니다.</strong><p>확인된 데이터부터 순차적으로 반영합니다.</p></div> : null}</div></section>
    <section className="insight-v2-changes"><header><h2>주요 변화</h2><span>강도·순위·상승 확산의 의미 있는 Snapshot 변화</span></header><div>{changes.length ? changes.map(({theme,status,change,breadthChange,rankChange}) => <button type="button" key={theme.theme_id} onClick={() => setThemeId(theme.theme_id)}><time>{theme.realtime_snapshot_at?.slice(11,16) || "현재"}</time><strong>{theme.theme_name}</strong><span>{change != null && Math.abs(change) >= .3 ? `테마강도 ${compactMovement(change,"%p",.1)}` : breadthChange != null && Math.abs(breadthChange) >= 1 ? `상승 종목 ${breadthChange > 0 ? "+" : ""}${breadthChange}개` : rankChange != null ? `실시간 순위 ${rankChange > 0 ? `${rankChange}계단 상승` : `${Math.abs(rankChange)}계단 하락`}` : themeInsightLine(theme,status,Boolean(realtimeReady))}</span><em>{insightStatusLabel[status]}</em></button>) : <p>{realtimeReady ? "판단을 바꿀 만큼 큰 변화가 아직 없습니다." : "장중 데이터 대기 · 준비된 선행 신호는 0점으로 처리하지 않습니다."}</p>}</div></section>
    <main className="insight-v2-workspace">
      <section className="insight-v2-column insight-v2-flow"><header><h2>시장 흐름</h2><p>점수보다 변화와 상태를 먼저 봅니다.</p></header><div>{themes.map(({theme,status,change,score}) => <button type="button" className={`${theme.theme_id === themeId ? "is-selected " : ""}is-${status.toLowerCase()}`} key={theme.theme_id} onClick={() => setThemeId(theme.theme_id)}><span><strong>{theme.theme_name}</strong><em>{insightStatusLabel[status]}</em></span><b>{score ?? "대기"} <small>{change == null ? (realtimeReady ? "→" : "장중 대기") : compactMovement(change,"",.1)}</small></b><p>{theme.signal_stage_label || themeCompactLead(theme)}</p></button>)}{data && !themes.length ? <div className="insight-ux-empty"><strong>해당 상태의 테마가 없습니다.</strong></div> : null}</div></section>
      <section className="insight-v2-column insight-v2-evidence"><header><h2>판단 근거</h2><p>왜 이런 판단을 했는지 신호의 연결로 설명합니다.</p></header>{selectedTheme && selectedInsight ? <div className="insight-v2-evidence-body"><div className="insight-v2-decision"><span>{insightStatusLabel[selectedInsight.status]}</span><h3>{selectedTheme.theme_name}</h3><p>{themeInsightLine(selectedTheme,selectedInsight.status,Boolean(realtimeReady))}</p><strong>종합 판단 {selectedInsight.score ?? "대기"} {selectedInsight.change == null ? "" : compactMovement(selectedInsight.change,"",.1)}</strong></div><div className="insight-v2-reasons">{[
        ["시장 배경", selectedTheme.us_lead.linked ? `미국 ${selectedTheme.us_lead.us_theme_name || "연결 테마"} ${selectedTheme.us_lead.strength === "STRONG" ? "강세" : "연계 확인"}` : "미국 선행 연계 없음"],
        ["선행 신호", themeSignalReason(selectedTheme)],
        ["현재 테마 반응", selectedTheme.realtime_snapshot_at ? `실시간 등락 ${pct(selectedTheme.realtime_avg_change_rate,2)} · 테마강도 ${pct(selectedTheme.theme_strength,2)} · 상승 확산 ${selectedTheme.up_count}/${selectedTheme.valid_stock_count}` : "장중 데이터 대기 · 판단 보류"],
        ["종목 확인", themeStocks[0] ? `${themeStocks[0].stock_name} 테마 대비 ${themeStocks[0].relative_strength == null ? "확인 대기" : `${point(themeStocks[0].relative_strength)}%p`}` : "연결 종목 확인 대기"],
        ["과거 사례", themeStocks[0] ? `패턴 유사도 ${number(themeStocks[0].success_similarity)} · ${patternQuality(themeStocks[0])}` : "유사 사례 확인 대기"],
      ].map(([title,content]) => <article key={title}><strong>{title}</strong><p>{content}</p></article>)}</div><section className="insight-v2-chain"><h3>신호 연결</h3><div>{[selectedTheme.us_lead.linked ? `미국 ${selectedTheme.us_lead.us_theme_name || "테마"} 신호` : null, selectedTheme.us_lead.linked ? "한미 연계 확인" : null, selectedTheme.d1_candidate_score != null ? "D+1 가격·수급 상위" : null, selectedTheme.realtime_avg_change_rate != null ? `실시간 테마 ${pct(selectedTheme.realtime_avg_change_rate,2)}` : null, selectedTheme.valid_stock_count ? `상승 확산 ${selectedTheme.up_count}/${selectedTheme.valid_stock_count}` : null, themeStocks[0]?.relative_strength != null ? `${themeStocks[0].stock_name} 상대강도 ${themeStocks[0].relative_strength > 0 ? "+" : "-"}` : null].filter(Boolean).map((step,index) => <span key={String(step)}>{index ? <i>→</i> : null}{step}</span>)}</div></section></div> : <div className="insight-ux-empty"><strong>시장 흐름에서 테마를 선택하세요.</strong></div>}</section>
      <section className="insight-v2-column insight-v2-stocks"><header><h2>지금 볼 종목</h2><p>현재·변화·여유·다음 확인을 함께 봅니다.</p></header><div>{themeStocks.slice(0,6).map((stock) => { const view=views[stock.stock_id] || fallbackView; const watched=watchIds.has(stock.stock_id); const live=Boolean(selectedTheme?.realtime_snapshot_at); const status=view.state === "WARNING" ? "확인 필요" : view.state === "STRENGTHENING" || (stock.relative_strength ?? 0) > 0 ? "좋아지는 중" : "관찰 유지"; return <article key={stock.stock_id} role="button" tabIndex={0} onClick={() => openStock(stock)}><div><em>{status}</em><button type="button" aria-label={`${stock.stock_name} 관심종목 ${watched ? "해제" : "추가"}`} onClick={(event) => { event.stopPropagation(); void toggleWatch(stock); }}><Star size={15} fill={watched ? "currentColor" : "none"}/></button></div><div className="insight-v2-stock-identity"><h3>{stock.stock_name}</h3><span>{stock.theme_name || "테마 미지정"}</span><i aria-hidden="true">▶</i><b>{patternQuality(stock).replace("패턴 ", "패턴")}</b></div><dl><div><dt>현재</dt><dd className={(stock.change_rate ?? 0)>=0 ? "is-up" : "is-down"}>{live ? pct(stock.change_rate,2) : `전일 ${pct(stock.change_rate,2)}`}</dd></div><div><dt>변화</dt><dd>{live && stock.relative_strength != null ? `테마 대비 ${point(stock.relative_strength)}%p` : "장중 대기"}</dd></div><div><dt>여유</dt><dd>{selectedInsight?.status === "STRENGTHENING" ? `${selectedTheme?.theme_name} 강화 · ` : ""}수급 {stock.gates.flow === "PASS" ? "양호" : stock.gates.flow === "NO_DATA" ? "대기" : "관찰"} · 패턴 {number(stock.success_similarity)}</dd></div><div><dt>다음 확인</dt><dd>{live ? "테마 확산 / 상대강도 유지" : "실시간 테마 강도 / 테마 대비 상대강도"}</dd></div></dl></article>; })}{selectedTheme && !themeStocks.length ? <div className="insight-ux-empty"><strong>현재 연결된 종목이 없습니다.</strong></div> : null}</div></section>
    </main>
    {postMarket && data ? <PostMarketPanel data={data} views={views} filter={reviewFilter} onFilter={setReviewFilter} onOpen={(stockId) => { const stock = data.stocks.find((row) => row.stock_id === stockId); if (stock) openStock(stock); }}/> : null}
    {selected ? <InsightDrawer stock={selected} view={views[selected.stock_id] || fallbackView} postMarket={Boolean(postMarket)} analysisDate={data?.analysis_date || null} realtimeStatus={data?.readiness.realtime.status || "NOT_READY"} loading={loading} tab={drawerTab} onTab={setDrawerTab} onRefresh={() => void load()} onClose={() => setSelected(null)}/> : null}
    {watchOpen ? <WatchDrawer watches={watches} views={views} realtimeStatus={data?.readiness.realtime.status || "NOT_READY"} onOpen={openStock} onUpdate={(row,value) => void updateWatch(row,value)} onClose={() => setWatchOpen(false)}/> : null}
  </div>;
}

export default DrctInsightPage;
