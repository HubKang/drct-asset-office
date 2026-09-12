import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Info } from "lucide-react";
import MarketThemeDetailDrawer from "@/components/marketThemes/MarketThemeDetailDrawer";
import ObservationGapChart from "@/components/marketThemes/ObservationGapChart";
import ObservationRadarGrid from "@/components/marketThemes/ObservationRadarGrid";
import PriceFlowResearchCharts from "@/components/marketThemes/PriceFlowResearchCharts";
import { repositories } from "@/services";
import type { MarketTheme, MarketThemeObservationDiagnosticsResponse, MarketThemeObservationItem, MarketThemeObservationMLCandidate, MarketThemeObservationMLTrainResponse, MarketThemeObservationResponse, MarketThemePriceFlowResearchResponse } from "@/types/marketTheme";

type WorkspaceTab = "today" | "performance" | "ml";
type PeriodKey = "20" | "60" | "120" | "all";

const kstToday = () => new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(new Date());
const shiftBusinessDay = (dateValue: string, direction: -1 | 1) => {
  const value = new Date(`${dateValue}T00:00:00Z`);
  do value.setUTCDate(value.getUTCDate() + direction);
  while (value.getUTCDay() === 0 || value.getUTCDay() === 6);
  return value.toISOString().slice(0, 10);
};
const nextBusinessDay = () => shiftBusinessDay(kstToday(), 1);
const n = (value: number | null | undefined, digits = 1) => value == null ? "-" : value.toFixed(digits);
const percent = (value: number | null | undefined) => value == null ? "-" : `${(value * 100).toFixed(1)}%`;
const shortDate = (value: string | null | undefined) => value ? value.slice(5).replace("-", "/") : "-";
const dateTime = (value: string | null | undefined) => value ? value.replace("T", " ").slice(0, 16) : "-";
const shortDateTime = (value: string | null | undefined) => { const formatted = dateTime(value); return formatted === "-" ? formatted : formatted.slice(5); };
const featureVersionLabel = (value: string | null | undefined) => { const match = value?.match(/_V(\d+)$/i); return match ? `Feature V${match[1]}` : "Feature V1"; };
const modelVersionLabel = (value: string | null | undefined) => { const match = value?.match(/(?:RULE|OBSERVATION_RULE)[_-]?V?(\d+)/i); return match ? `RULE V${match[1]}` : "RULE V2"; };
const stageName: Record<string, string> = { EARLY: "수급 선행", CONFIRMED: "상승 확인", MATURE: "상승 진행", EXHAUSTED: "소진 주의" };
const factorDefinitions = [["가격 강도", "price_score"], ["수급 강도", "flow_score"], ["수급 가속", "flow_acceleration_score"], ["확산", "breadth_score"], ["지속 가능성", "sustainability_score"]] as const;
const legacyFactorDefinitions = [["가격", "price_score"], ["수급", "flow_score"], ["확산", "breadth_score"], ["기술", "technical_score"], ["완전성", "data_coverage_rate"]] as const;

function factorRows(item: MarketThemeObservationItem) {
  const signalRadarAvailable = item.flow_acceleration_score != null && item.sustainability_score != null;
  const definitions = signalRadarAvailable ? factorDefinitions : legacyFactorDefinitions;
  return definitions.flatMap(([label, key]) => {
    const raw = item[key];
    const value = raw == null ? null : key === "data_coverage_rate" ? raw * 100 : raw;
    return value == null ? [] : [{ label, value, direction: value >= 70 ? "강함" : value >= 50 ? "보통" : "약함" }];
  });
}

function ObservationFactorStrip({ item }: { item: MarketThemeObservationItem }) {
  const stage = item.stage_label ?? stageName[item.stage_code ?? ""] ?? "분석 대기";
  const factors = factorRows(item);
  const legacy = item.flow_acceleration_score == null || item.sustainability_score == null;
  return <section className="observation-linked-factor-strip signal-detail-strip" aria-label="가격 수급 신호 상세">
    <header><h4>가격·수급 신호</h4><span>{legacy ? "개편 전 저장 5축" : "동일 기준일 활성 테마 Percentile"}</span></header>
    <div><article className={`signal-stage-card stage-${item.stage_code?.toLowerCase() ?? "pending"}`}><header><span>현재 단계</span></header><strong>{stage}</strong></article>{factors.map((factor) => { const tone = factor.direction === "강함" ? "is-positive" : factor.direction === "약함" ? "is-negative" : "is-neutral"; return <article key={factor.label} className={tone}><header><span>{factor.label}</span><i aria-hidden="true" /><em>{factor.direction}</em></header><strong>{n(factor.value)}</strong></article>; })}<article className="is-neutral"><header><span>D+1 판단</span></header><strong>{n(scoreOf(item))}</strong></article></div>
    <p className="signal-detail-summary">{item.stage_summary ?? "가격과 수급의 진행 관계를 분석 중입니다."}</p>
  </section>;
}

function whyMessages(item: MarketThemeObservationItem) {
  const messages: string[] = item.stage_summary ? [item.stage_summary] : [];
  if ((item.flow_acceleration_score ?? 0) >= 70) messages.push("최근 3일 수급 가속이 강합니다.");
  if ((item.breadth_score ?? 0) >= 70) messages.push("가격·수급 흐름이 연결종목으로 확산되고 있습니다.");
  if ((item.sustainability_score ?? 0) >= 70) messages.push("현재 강세가 이어질 여지가 상대적으로 높습니다.");
  const unique = [...new Set(messages)].slice(0, 3);
  return unique.length ? unique : ["가격과 수급의 관계를 기준으로 D+1 후보를 선별했습니다."];
}

const factorTone = (value: number | null | undefined) => value == null ? "대기" : value >= 70 ? "강" : value >= 45 ? "보통" : "약";
const performanceReason = (item: MarketThemeObservationItem) => item.sustainability_score != null
  ? `수급 ${factorTone(item.flow_score)} · 지속성 ${factorTone(item.sustainability_score)}`
  : `수급 ${factorTone(item.flow_score)} · 확산 ${factorTone(item.breadth_score)}`;

const scoreOf = (item: MarketThemeObservationItem) => item.relative_strength_score ?? item.relative_strength_probability;
const pointDelta = (value: number | null | undefined) => value == null ? "-" : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%p`;
const score100 = (value: number | null | undefined) => value == null ? "-" : `${(value * 100).toFixed(1)} / 100`;
const signedPoint = (value: number | null | undefined) => value == null ? "-" : `${value >= 0 ? "+" : ""}${value.toFixed(1)}%p`;

function RankMovement({ predicted, actual, maxDelta }: { predicted: number | null | undefined; actual: number | null | undefined; maxDelta: number }) {
  if (predicted == null || actual == null) return <div className="rank-movement is-pending" title="실제 결과가 아직 반영되지 않았습니다."><span>예측 {predicted ?? "-"}위</span><i /><strong>결과 대기</strong></div>;
  const delta = predicted - actual;
  const tone = delta > 0 ? "is-improved" : delta < 0 ? "is-weaker" : "is-flat";
  const width = 26 + Math.min(1, Math.abs(delta) / Math.max(1, maxDelta)) * 64;
  const title = delta > 0 ? "실제 순위가 예상보다 높았습니다." : delta < 0 ? "실제 순위가 예상보다 낮았습니다." : "예상 순위와 실제 순위가 같았습니다.";
  return <div className={`rank-movement ${tone}`} title={title}><span>예측 {predicted}위</span><i style={{ width: `${width}%` }}><b /></i><strong>실제 {actual}위</strong><em>{delta > 0 ? `▲${delta}` : delta < 0 ? `▼${Math.abs(delta)}` : "변동 없음"}</em></div>;
}

function PerformanceResultList({ items, onSelect }: { items: MarketThemeObservationItem[]; onSelect: (item: MarketThemeObservationItem) => void }) {
  const maxDelta = Math.max(1, ...items.map((item) => item.actual_rank == null || item.observation_rank == null ? 0 : Math.abs(item.actual_rank - item.observation_rank)));
  return <section className="observation-performance-results"><header><div><h4>개별 테마 예측 결과</h4><p>예측 순위와 실제 다음날 순위가 얼마나 달랐는지 확인합니다.</p></div><span>화살표가 길수록 순위 차이가 큽니다.</span></header><div className="observation-performance-result-head"><span>예측순위 / 테마</span><span>단계</span><span>D+1 후보점수</span><span>순위 이동</span><span>실제 결과</span><span>핵심 이유</span></div>{items.map((item) => <button type="button" key={item.theme_id} onClick={() => onSelect(item)}><span className="performance-theme-cell"><b>#{item.observation_rank ?? "-"}</b><strong>{item.theme_name}</strong></span><em className={`theme-observation-state stage-${item.stage_code?.toLowerCase() ?? "pending"}`}>{item.stage_label ?? stageName[item.stage_code ?? ""] ?? "분석 대기"}</em><span><strong>{n(scoreOf(item))}</strong></span><RankMovement predicted={item.observation_rank} actual={item.actual_rank} maxDelta={maxDelta} /><span className="performance-actual-score">{n(item.actual_relative_strength)}</span><span className="performance-reason">{performanceReason(item)}</span></button>)}</section>;
}

function MLResearchResults({ result }: { result: MarketThemeObservationMLTrainResponse | null }) {
  if (!result) return <div className="observation-ml-empty"><strong>아직 이번 세션의 후보 모델 결과가 없습니다.</strong><p>기존 학습·Gate 계산을 실행해 Baseline과 Candidate를 비교할 수 있습니다.</p></div>;
  const rule = result.baseline_metrics.OBSERVATION_RULE;
  const ruleOos = result.baseline_metrics.OBSERVATION_RULE_OOS;
  const diagnosticWarnings = result.feature_diagnostics.filter((item) => item.near_constant || item.missing_rate >= .2);
  return <div className="observation-research-results">
    <section className="observation-research-baseline"><header><div><span>운영 기준</span><strong>RULE V2 / Feature V2</strong></div><em>{result.recommendation}</em></header><div><article><span>P@5</span><strong>{percent(rule?.precision_at_5)}</strong></article><article><span>NDCG@5</span><strong>{n(rule?.ndcg_at_5, 3)}</strong></article><article><span>P@10</span><strong>{percent(rule?.precision_at_10)}</strong></article><article><span>Top20</span><strong>{percent(rule?.precision_top20)}</strong></article><article><span>최근 OOS</span><strong>{result.oos_sample_days}일</strong><small>{result.oos_start_date?.slice(5)} ~ {result.oos_end_date?.slice(5)}</small></article></div></section>
    <section className="observation-research-table"><header><div><h4>후보 비교</h4><p>운영 RULE V2와 V2·V3 후보를 같은 Walk-forward 지표로 비교합니다.</p></div><span>Gate: 최고 기준선 Top20 +{(result.gate_required_improvement * 100).toFixed(0)}%p</span></header><div className="table-shell"><table className="data-table compact-table"><thead><tr><th>후보명</th><th>P@5</th><th>NDCG@5</th><th>P@10</th><th>Top20</th><th>Top5 하위50</th><th>승리 Fold</th><th>Holdout P@5</th><th>Holdout 실패</th><th>Gate</th><th>상태</th></tr></thead><tbody><tr><td><strong>RULE_V2</strong><small>운영 기준</small></td><td>{percent(rule?.precision_at_5)}</td><td>{n(rule?.ndcg_at_5, 3)}</td><td>{percent(rule?.precision_at_10)}</td><td>{percent(rule?.precision_top20)}</td><td>{percent(rule?.top5_bottom_half_rate)}</td><td>-</td><td>{percent(ruleOos?.precision_at_5)}</td><td>{percent(ruleOos?.top5_bottom_half_rate)}</td><td>운영 기준</td><td>PUBLISHED</td></tr>{result.candidates.map((candidate: MarketThemeObservationMLCandidate) => <tr key={candidate.model_type}><td><strong>{candidate.model_type}</strong><small>{candidate.feature_version.replace("THEME_OBSERVATION_", "")}</small></td><td>{percent(candidate.metrics.precision_at_5)}<small>{pointDelta(candidate.delta_precision_at_5)}</small></td><td>{n(candidate.metrics.ndcg_at_5, 3)}</td><td>{percent(candidate.metrics.precision_at_10)}</td><td>{percent(candidate.metrics.precision_top20)}</td><td>{percent(candidate.metrics.top5_bottom_half_rate)}</td><td>{candidate.improving_fold_count}/{candidate.validation_fold_count}<small>최저 {percent(candidate.worst_fold_precision_at_5)}</small></td><td>{percent(candidate.oos_metrics?.precision_at_5)}</td><td>{percent(candidate.oos_metrics?.top5_bottom_half_rate)}</td><td>{candidate.selection_gate_status}</td><td>{candidate.candidate_status}</td></tr>)}</tbody></table></div></section>
    <section className="observation-research-table"><header><div><h4>Feature Group Ablation</h4><p>FULL PRICE_FLOW_V3에서 그룹 하나를 제거한 동일 Walk-forward 결과입니다.</p></div></header><div className="table-shell"><table className="data-table compact-table"><thead><tr><th>Feature Group</th><th>제거 후 P@5</th><th>Δ P@5</th><th>NDCG@5</th><th>Δ NDCG</th><th>Δ Top20</th><th>Δ Top5 실패</th><th>판정</th></tr></thead><tbody>{result.ablation_results.map((item) => <tr key={item.feature_group}><td><strong>{item.feature_group === "FULL_V3" ? "FULL_V3" : `− ${item.feature_group}`}</strong></td><td>{percent(item.metrics.precision_at_5)}</td><td className={item.delta_precision_at_5 > 0 ? "is-improved" : item.delta_precision_at_5 < 0 ? "is-weaker" : ""}>{pointDelta(item.delta_precision_at_5)}</td><td>{n(item.metrics.ndcg_at_5, 3)}</td><td>{pointDelta(item.delta_ndcg_at_5)}</td><td>{pointDelta(item.delta_precision_top20)}</td><td>{pointDelta(item.delta_top5_bottom_half_rate)}</td><td>{item.verdict}</td></tr>)}</tbody></table></div></section>
    <section className="observation-research-foot"><div><strong>Feature 진단</strong><span>{result.feature_diagnostics.length}개 점검 · 경고 {diagnosticWarnings.length}개</span></div><div><strong>최근 OOS</strong><span>튜닝에 사용하지 않은 {result.oos_sample_days}일 · 소표본 해석 주의</span></div><div><strong>권고 후보</strong><span>{result.recommended_candidate ?? "없음"}</span></div></section>
  </div>;
}

export default function MarketThemeReturnPredictionPanel(props: {
  themeGroups: MarketTheme[];
  onThemeClick: (themeId: number) => void;
  onNavigateToThemeView?: (view: "trend" | "flowTrend" | "theme") => void;
  initialTargetDate?: string | null;
}) {
  const [data, setData] = useState<MarketThemeObservationResponse | null>(null);
  const [targetDate, setTargetDate] = useState(nextBusinessDay);
  const [groupId, setGroupId] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [limit, setLimit] = useState(10);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("today");
  const [period, setPeriod] = useState<PeriodKey>("20");
  const [selectedTheme, setSelectedTheme] = useState<MarketThemeObservationItem | null>(null);
  const [scoreInfoOpen, setScoreInfoOpen] = useState(false);
  const [scoreDistributionOpen, setScoreDistributionOpen] = useState(true);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState("");
  const [error, setError] = useState("");
  const [calculateDateError, setCalculateDateError] = useState("");
  const [mlResult, setMLResult] = useState<MarketThemeObservationMLTrainResponse | null>(null);
  const [diagnostics, setDiagnostics] = useState<MarketThemeObservationDiagnosticsResponse | null>(null);
  const [research, setResearch] = useState<MarketThemePriceFlowResearchResponse | null>(null);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchError, setResearchError] = useState("");
  const [marketChoiceOpen, setMarketChoiceOpen] = useState(false);
  const [progressMessage, setProgressMessage] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const researchAbortRef = useRef<AbortController | null>(null);
  const today = kstToday();

  const request = async (work: (signal: AbortSignal) => Promise<MarketThemeObservationResponse>, options?: { preserveTargetDate?: boolean }) => {
    abortRef.current?.abort();
    const controller = new AbortController(); abortRef.current = controller;
    setLoading(true); setError("");
    try {
      const result = await work(controller.signal); setData(result);
      if (!options?.preserveTargetDate) { const responseTargetDate = result.run?.target_date ?? result.default_target_date; if (responseTargetDate) setTargetDate(responseTargetDate); }
      return result;
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "D+1 테마 후보(가격·수급) 요청에 실패했습니다.");
      return null;
    } finally { if (!controller.signal.aborted) setLoading(false); }
  };
  const loadDiagnostics = async () => { try { setDiagnostics(await repositories.marketThemes.getObservationDiagnostics()); } catch { /* 순위 조회와 독립 */ } };

  useEffect(() => {
    const initialDate = props.initialTargetDate?.trim();
    void request((signal) => initialDate ? repositories.marketThemes.getObservationPriority(initialDate, signal) : repositories.marketThemes.getLatestObservationPriority(signal)).then(() => void loadDiagnostics());
    return () => abortRef.current?.abort();
  }, []);
  useEffect(() => {
    if (!marketChoiceOpen && !selectedTheme) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape" && !action) { setMarketChoiceOpen(false); setSelectedTheme(null); } };
    window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close);
  }, [action, marketChoiceOpen, selectedTheme]);
  useEffect(() => {
    if (activeTab === "today") setScoreDistributionOpen(true);
  }, [activeTab, data?.run?.id]);
  useEffect(() => {
    if (activeTab === "today" || research) return;
    const controller = new AbortController(); researchAbortRef.current = controller;
    setResearchLoading(true); setResearchError("");
    void repositories.marketThemes.getPriceFlowResearch(controller.signal)
      .then((result) => { if (!controller.signal.aborted) setResearch(result); })
      .catch((reason) => { if (!controller.signal.aborted) setResearchError(reason instanceof Error ? reason.message : "Stage·Radar 연구 결과를 불러오지 못했습니다."); })
      .finally(() => { if (!controller.signal.aborted) setResearchLoading(false); });
    return () => controller.abort();
  }, [activeTab, research]);

  const filteredRows = useMemo(() => {
    const term = keyword.trim().toLocaleLowerCase("ko-KR");
    return [...(data?.items ?? [])].filter((item) => (groupId === "all" || String(item.theme_group_id ?? "") === groupId)
      && (!term || item.theme_name.toLocaleLowerCase("ko-KR").includes(term) || (item.theme_group_name ?? "").toLocaleLowerCase("ko-KR").includes(term)))
      .sort((a, b) => (a.observation_rank ?? 999) - (b.observation_rank ?? 999)).slice(0, limit);
  }, [data?.items, groupId, keyword, limit]);
  const topRows = filteredRows.filter((item) => (item.observation_rank ?? 999) <= 5);
  const candidateRows = filteredRows.filter((item) => (item.observation_rank ?? 999) > 5);
  const summary = useMemo(() => ({ coverage: data?.items.length ? data.items.reduce((sum, item) => sum + item.data_coverage_rate, 0) / data.items.length : null }), [data?.items]);
  const featureVersion = data?.run?.feature_version ?? "THEME_OBSERVATION_FEATURE_V2";
  const operatingModel = modelVersionLabel(data?.run?.model_version ?? data?.run?.method);
  const diagnosticDays = diagnostics?.quality_evaluated_days ?? 0;

  const calculationDateError = () => {
    if (!targetDate) return "신호 대상일을 선택해 주세요.";
    const day = new Date(`${targetDate}T00:00:00`).getDay();
    if ([0, 6].includes(day)) return "신규 D+1 신호의 대상일은 평일이어야 합니다.";
    const cutoff = data?.calculation_data_cutoff_date;
    if (cutoff && targetDate <= cutoff) return "과거 대상일은 신규 D+1 신호를 계산할 수 없습니다.";
    return "";
  };
  const queryExisting = async (date = targetDate) => { if (!date) return; setCalculateDateError(""); setProgressMessage(""); setSelectedTheme(null); await request((signal) => repositories.marketThemes.getObservationPriority(date, signal), { preserveTargetDate: true }); };
  const navigateObservationDate = async (nextDate: string) => { setTargetDate(nextDate); setCalculateDateError(""); await queryExisting(nextDate); };
  const prepareCalculation = () => { const validationError = calculationDateError(); setCalculateDateError(validationError); if (!validationError) setMarketChoiceOpen(true); };
  const calculate = async (refreshMarketIndicators: boolean) => {
    const validationError = calculationDateError(); if (validationError || action) { setCalculateDateError(validationError); return; }
    setAction(refreshMarketIndicators ? "refresh-calculate" : "calculate");
    setProgressMessage(refreshMarketIndicators ? "1/3 이전 성과 확인 중\n2/3 시장지표 갱신 중\n3/3 오늘 순위 생성 중" : "1/2 이전 성과 확인 중\n2/2 오늘 순위 생성 중");
    const result = await request((signal) => repositories.marketThemes.calculateObservationPriority(targetDate, refreshMarketIndicators, signal));
    setProgressMessage(result ? "성과 확인과 오늘 순위 생성을 완료했습니다." : "오늘 순위 생성에 실패했습니다."); setAction("");
    if (result) { setMarketChoiceOpen(false); await loadDiagnostics(); }
  };
  const validate = async () => { if (!data?.run || action) return; setAction("validate"); await request((signal) => repositories.marketThemes.validateObservationPriority(data.run!.target_date, signal)); await loadDiagnostics(); setAction(""); };
  const train = async () => { if (action) return; setAction("train"); setError(""); try { setMLResult(await repositories.marketThemes.trainObservationML()); } catch (reason) { setError(reason instanceof Error ? reason.message : "ML 학습에 실패했습니다."); } finally { setAction(""); } };
  const dateSetLabel = `${shortDate(data?.calculation_data_cutoff_date ?? data?.data_cutoff_date)} 데이터 → ${shortDate(data?.run?.target_date ?? targetDate)} 신호`;

  return <div className="theme-prediction-panel observation-priority-panel observation-workspace">
    <header className="observation-workspace-header"><div><span>PRICE × FLOW SIGNAL</span><h2>D+1 테마 후보(가격·수급)</h2><p>오늘 확정된 가격·수급 데이터를 기반으로 다음 거래일 강세 가능성이 높은 테마 후보를 찾습니다.</p></div><div className="observation-header-actions"><button className="btn btn-primary" type="button" disabled={!targetDate || Boolean(action)} onClick={prepareCalculation}>{action.includes("calculate") ? "생성 중..." : "오늘 신호 생성"}</button><button className="btn btn-secondary" type="button" disabled={!data?.run || Boolean(action)} onClick={() => void validate()}>{action === "validate" ? "반영 중..." : "성과 반영"}</button><button className="btn btn-secondary" type="button" onClick={() => setActiveTab("ml")}>ML 연구</button></div></header>

    <nav className="observation-workspace-tabs" aria-label="D+1 테마 후보(가격·수급) 보기">{([['today','오늘의 신호','D+1 후보 테마'],['performance','성과·검증','예측과 실제'],['ml','ML 연구','후보 모델']] as const).map(([key, label, caption]) => <button key={key} type="button" className={activeTab === key ? "is-active" : ""} aria-current={activeTab === key ? "page" : undefined} onClick={() => setActiveTab(key)}><strong>{label}</strong><small>{caption}</small></button>)}</nav>

    <section className="observation-control-bar" aria-label="D+1 신호 조회 조건"><div className="observation-date-set"><button type="button" aria-label="이전 신호일" onClick={() => void navigateObservationDate(shiftBusinessDay(targetDate || today, -1))}><ChevronLeft size={18} /></button><label><span>신호 세트</span><strong>{dateSetLabel}</strong><input type="date" value={targetDate} aria-label="신호 대상일" onChange={(event) => { const value = event.target.value; setTargetDate(value); if (value) void queryExisting(value); }} /></label><button type="button" aria-label="다음 신호일" onClick={() => void navigateObservationDate(shiftBusinessDay(targetDate || today, 1))}><ChevronRight size={18} /></button></div><div className="observation-filter-set"><label><span>테마그룹</span><select value={groupId} onChange={(event) => setGroupId(event.target.value)}><option value="all">전체</option>{props.themeGroups.map((group) => <option key={group.id} value={group.id}>{group.theme_name}</option>)}</select></label><label className="observation-keyword"><span>검색</span><input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="테마명" /></label><label><span>표시</span><select value={limit} onChange={(event) => setLimit(Number(event.target.value))}><option value={10}>Top 10</option><option value={20}>Top 20</option><option value={30}>Top 30</option><option value={50}>Top 50</option></select></label><button className="btn btn-secondary observation-query-button" type="button" disabled={loading || !targetDate} onClick={() => void queryExisting()}>{loading ? "조회 중" : "조회"}</button></div></section>

    {calculateDateError ? <p className="form-error">{calculateDateError}</p> : null}{error ? <div className="inline-result inline-error">{error}</div> : null}{progressMessage ? <div className="inline-result theme-observation-progress">{progressMessage}</div> : null}
    <section className="observation-operating-strip" aria-label="운영 상태"><span><small>운영 모델</small><strong>{operatingModel} · {featureVersionLabel(featureVersion)}</strong></span><span><small>시장보정</small><strong>{data?.run?.calculation_mode === "REFRESHED_MARKET_DATA" ? "적용" : "미적용"}</strong></span><span><small>최근 계산</small><strong>{shortDateTime(data?.run?.calculated_at)}</strong></span><span className={summary.coverage != null && summary.coverage < 1 ? "is-warning" : ""}><small>데이터 완전성</small><strong>{summary.coverage == null ? "-" : percent(summary.coverage)}</strong></span><span className="observation-score-info"><button type="button" aria-expanded={scoreInfoOpen} onClick={() => setScoreInfoOpen((open) => !open)}><Info size={15} /> D+1 후보점수란?</button>{scoreInfoOpen ? <span role="dialog"><b>D+1 후보점수</b>는 기존 Rule V2가 가격·수급·확산 등 정형 Factor를 종합한 0~100 Ranking 점수입니다. 상승확률이 아니며, 단계의 순서로 점수를 정하지 않습니다.</span> : null}</span></section>
    {summary.coverage != null && summary.coverage < 1 ? <p className="observation-data-warning"><Info size={15} /> 일부 테마의 가격·수급 데이터가 부족합니다. 순위는 제공하되 상세의 데이터 완전성을 함께 확인하세요.</p> : null}

    {activeTab === "today" ? <>{loading && !data ? <div className="observation-empty-state" role="status"><strong>테마 신호를 불러오는 중입니다.</strong><p>저장된 최신 D+1 결과를 확인하고 있습니다.</p></div> : null}{!loading && !data?.run ? <div className="observation-empty-state"><strong>{shortDate(targetDate)} 신호가 아직 생성되지 않았습니다.</strong><p>마지막 실측 데이터를 기준으로 다음 거래일의 가격·수급 신호를 만듭니다.</p><button className="btn btn-primary" type="button" onClick={prepareCalculation}>오늘 신호 생성</button></div> : null}{data?.run ? <>
      <section className="observation-focus-section observation-focus-radar-section"><header><div><span>NEXT SESSION</span><h3>D+1 상승 후보 Top 5</h3><p>{shortDate(data.run.target_date)}에 상대적으로 먼저 확인할 테마입니다.</p></div><small>카드를 누르면 단계·가격·수급·D+1 판단 근거를 볼 수 있습니다.</small></header><div className="observation-focus-radar-body">{topRows.length ? <ObservationRadarGrid items={topRows} statusNames={stageName} hideHeader onThemeClick={(themeId) => { const item = topRows.find((row) => row.theme_id === themeId); if (item) setSelectedTheme(item); }} /> : <p className="observation-list-empty">현재 필터에 맞는 D+1 후보 테마가 없습니다.</p>}</div></section>
      {candidateRows.length ? <section className="observation-candidate-section"><header><div><h3>추가 D+1 후보</h3><p>Top 6 이후는 단계와 핵심 신호만 간결하게 표시합니다.</p></div><b>{candidateRows.length}개</b></header><div className="observation-candidate-table" role="table"><div className="is-head" role="row"><span>순위</span><span>테마</span><span>D+1 후보</span><span>가격×수급</span><span>핵심 이유</span><span>단계</span></div>{candidateRows.map((item) => <button key={item.theme_id} type="button" role="row" onClick={() => setSelectedTheme(item)}><b>{item.observation_rank ?? "-"}</b><strong>{item.theme_name}</strong><span>{n(scoreOf(item))}</span><span>{item.price_flow_gap == null ? "—" : `${item.price_flow_gap > 0 ? "수급 +" : "가격 +"}${n(Math.abs(item.price_flow_gap))}`}</span><span>{whyMessages(item)[0]}</span><em className={`theme-observation-state stage-${item.stage_code?.toLowerCase() ?? "pending"}`}>{item.stage_label ?? "분석 대기"}</em></button>)}</div></section> : null}
      <section className="observation-validation-compact"><div><strong>실전검증 {diagnosticDays}일</strong><span>P@5 {percent(diagnostics?.recent_20.current.precision_at_5)}</span><span>NDCG@5 {n(diagnostics?.recent_20.current.ndcg_at_5, 3)}</span><span>운영모델 {operatingModel}</span></div><button type="button" onClick={() => setActiveTab("performance")}>성과 보기 →</button></section><button className="observation-distribution-toggle" type="button" aria-expanded={scoreDistributionOpen} onClick={() => setScoreDistributionOpen((open) => !open)}>{scoreDistributionOpen ? "점수 분포 닫기" : "점수 분포 보기"}</button>{scoreDistributionOpen ? <ObservationGapChart items={filteredRows} onThemeClick={(themeId) => { const item = filteredRows.find((row) => row.theme_id === themeId); if (item) setSelectedTheme(item); }} /> : null}
    </> : null}</> : null}

    {activeTab === "performance" ? <section className="observation-performance-workspace">
      <header><div><span>PERFORMANCE</span><h3>성과·검증</h3><p>저장된 다음날 후보와 실제 결과를 비교합니다.</p></div><div className="observation-period-tabs" aria-label="검증 기간">{(["20", "60", "120", "all"] as PeriodKey[]).map((key) => { const unavailable = key === "60" || key === "120"; return <button key={key} type="button" disabled={unavailable} className={period === key ? "is-active" : ""} title={unavailable ? "현재 제공되는 집계 구간이 없습니다." : undefined} onClick={() => setPeriod(key)}>{key === "all" ? "전체" : `최근 ${key}`}</button>; })}</div></header>
      <div className="observation-performance-summary">
        <article><span>검증기간</span><strong>{period === "all" ? diagnostics?.all.quality_days ?? diagnosticDays : diagnostics?.recent_20.quality_days ?? diagnosticDays}일</strong></article>
        <article title="예측 상위 5개 중 실제 상위 20%에 들어간 비율입니다."><span>상위 5개 적중률</span><strong>{percent(period === "all" ? diagnostics?.all.current.precision_at_5 : diagnostics?.recent_20.current.precision_at_5)}</strong></article>
        <article title="예측한 상위권 순서와 실제 상위권 순서가 일치한 정도입니다."><span>상위권 순위 일치도</span><strong>{score100(period === "all" ? diagnostics?.all.current.ndcg_at_5 : diagnostics?.recent_20.current.ndcg_at_5)}</strong></article>
        <article title="예측 후보가 실제 전체 테마 상위 20%에 들어간 비율입니다."><span>상위 20% 적중률</span><strong>{percent(period === "all" ? diagnostics?.all.current.precision_top20 : diagnostics?.recent_20.current.precision_top20)}</strong></article>
        <article title="예측 상위 5개 중 실제 다음날 상대강도가 하위 50%로 내려간 비율입니다."><span>상위후보 실패율</span><strong>{percent(research?.rule_top5_bottom_half_rate)}</strong><small>낮을수록 좋음</small></article>
        <article title="시장지표 갱신 전후의 평균 성과 개선폭입니다."><span>시장보정 개선폭</span><strong>{signedPoint(diagnostics?.paired_correction.mean_refresh_effect)}</strong></article>
      </div>
      {researchLoading ? <div className="observation-research-loading" role="status">단계별 성과와 성공 요인을 불러오고 있습니다.</div> : null}
      {researchError ? <div className="inline-result inline-error">{researchError}</div> : null}
      {research ? <PriceFlowResearchCharts data={research} /> : null}
      {data?.run ? <PerformanceResultList items={filteredRows} onSelect={setSelectedTheme} /> : <div className="observation-empty-state"><strong>비교할 다음날 결과가 없습니다.</strong></div>}
      {data?.metrics ? <p className="observation-performance-note"><Info size={15} /> 예상 위치와 실제 결과는 100에 가까울수록 해당 날짜의 전체 테마 중 상위입니다. 평균 순위 차이 {n(data.metrics.mean_rank_error)} · 검증 상태 {data.metrics.evaluation_status}</p> : null}
    </section> : null}

    {activeTab === "ml" ? <section className="observation-ml-workspace"><header><div><span>RESEARCH ONLY</span><h3>ML 후보 연구</h3><p>운영 Ranking과 분리된 후보 모델의 Gate·보정·Walk-forward 결과를 확인합니다.</p></div><button className="btn btn-primary" type="button" disabled={Boolean(action)} onClick={() => void train()}>{action === "train" ? "연구 실행 중..." : "후보 모델 검증"}</button></header><p className="observation-ml-boundary"><Info size={15} /> PRICE_FLOW_FEATURE_V3 후보와 Stage 성과를 검증해도 운영 Rule V2의 D+1 후보점수와 Published Ranking은 자동으로 변경되지 않습니다.</p><MLResearchResults result={mlResult} /></section> : null}

    <p className="theme-observation-disclaimer"><Info size={14} /> D+1 후보점수와 가격·수급 단계는 다음 거래일 상대강도 관찰용 지표이며 매수·매도 추천이 아닙니다.</p>
    <MarketThemeDetailDrawer
      open={Boolean(selectedTheme)}
      themeId={selectedTheme?.theme_id ?? null}
      dataDate={data?.run?.data_cutoff_date ?? data?.calculation_data_cutoff_date}
      headerEyebrow={selectedTheme ? `D+1 후보 ${selectedTheme.observation_rank ?? "-"}위` : undefined}
      headerTitle={selectedTheme?.theme_name}
      headerSubtitle={selectedTheme ? `D+1 후보점수 ${n(scoreOf(selectedTheme))} · ${selectedTheme.stage_label ?? "단계 분석 대기"}` : undefined}
      summaryContent={selectedTheme ? <ObservationFactorStrip item={selectedTheme} /> : null}
      hideReturnKpis
      hideTitleBlock
      drawerClassName="observation-linked-detail-drawer"
      onClose={() => setSelectedTheme(null)}
    />

    {marketChoiceOpen ? <div className="theme-observation-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target && !action) setMarketChoiceOpen(false); }}><section className="theme-observation-modal is-organized" role="dialog" aria-modal="true" aria-labelledby="market-refresh-choice-title"><header><div><small>오늘 신호 생성</small><h3 id="market-refresh-choice-title">시장지표를 갱신한 후 생성할까요?</h3></div><button type="button" aria-label="닫기" disabled={Boolean(action)} onClick={() => setMarketChoiceOpen(false)}>×</button></header><p className="theme-observation-modal-intro">직전 신호를 최신 실측으로 먼저 검증한 후 다음 거래일의 가격·수급 신호를 생성합니다.</p><section className="theme-observation-modal-basis" aria-label="계산 기준"><h4>계산 기준</h4><dl><div><dt>시장지표 최근 갱신</dt><dd>{dateTime(data?.market_indicator_latest_refreshed_at)}</dd></div><div><dt>테마·종목 기준일</dt><dd>{data?.calculation_data_cutoff_date ?? data?.data_cutoff_date ?? "-"}</dd></div><div><dt>신호 대상일</dt><dd>{targetDate}</dd></div></dl></section>{progressMessage && action ? <div className="theme-observation-modal-progress" role="status">{progressMessage}</div> : null}<div className="theme-observation-modal-actions"><button className="btn btn-secondary" type="button" disabled={Boolean(action)} onClick={() => void calculate(false)}><span>현재 지표로 생성</span><small>저장된 최신 시장지표를 사용합니다.</small></button><button className="btn btn-primary" type="button" disabled={Boolean(action)} onClick={() => void calculate(true)}><span>전체지표 갱신 후 생성</span><small>시장지표를 갱신하고 D+1 신호를 생성합니다.</small></button></div></section></div> : null}
  </div>;
}
