import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Info } from "lucide-react";
import MarketThemeDetailDrawer from "@/components/marketThemes/MarketThemeDetailDrawer";
import ObservationGapChart from "@/components/marketThemes/ObservationGapChart";
import ObservationRadarGrid from "@/components/marketThemes/ObservationRadarGrid";
import { repositories } from "@/services";
import type { MarketTheme, MarketThemeObservationDiagnosticsResponse, MarketThemeObservationItem, MarketThemeObservationMLCandidate, MarketThemeObservationMLTrainResponse, MarketThemeObservationResponse } from "@/types/marketTheme";

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
const stateName: Record<string, string> = { FLOW_LEADING: "집중", STRONG_CONTINUATION: "집중", REVERSAL_WATCH: "관찰", NEUTRAL: "관찰", OVERHEAT_RISK: "주의", FLOW_EXIT: "주의" };
const factorDefinitions = [["가격", "price_score"], ["수급", "flow_score"], ["확산", "breadth_score"], ["유동성", "liquidity_score"], ["기술", "technical_score"], ["시장환경", "market_environment_score"]] as const;

function factorRows(item: MarketThemeObservationItem) {
  return factorDefinitions.flatMap(([label, key]) => {
    const value = item[key];
    return value == null ? [] : [{ label, value, direction: value >= 70 ? "강함" : value >= 50 ? "보통" : "약함" }];
  });
}

function ObservationFactorStrip({ item }: { item: MarketThemeObservationItem }) {
  const factors = [
    ...factorRows(item),
    { label: "과열/소진", value: item.penalty_score === 0 ? 0 : -Math.abs(item.penalty_score), direction: item.penalty_score === 0 ? "없음" : "감점" },
  ];
  return <section className="observation-linked-factor-strip" aria-label="Factor 상세">
    <header><h4>Factor 상세</h4><span>저장된 계산값 기준</span></header>
    <div>{factors.map((factor) => { const tone = factor.direction === "강함" ? "is-positive" : factor.direction === "약함" || factor.direction === "감점" ? "is-negative" : "is-neutral"; return <article key={factor.label} className={tone}><header><span>{factor.label}</span><i aria-hidden="true" /><em>{factor.direction}</em></header><strong>{n(factor.value)}</strong></article>; })}</div>
  </section>;
}

function whyMessages(item: MarketThemeObservationItem) {
  const messages: string[] = [];
  if (item.status_code === "FLOW_LEADING") messages.push("수급 흐름이 상대적으로 앞서고 있습니다.");
  if (item.status_code === "STRONG_CONTINUATION") messages.push("강한 흐름이 이어지는 상태입니다.");
  if (item.status_code === "REVERSAL_WATCH") messages.push("흐름 전환 가능성을 관찰할 구간입니다.");
  const factorCopy: Record<string, string> = {
    가격: "가격 강도가 비교 테마보다 높습니다.", 수급: "수급 강도가 관찰 우선순위를 높이고 있습니다.", 확산: "연결 종목으로 흐름이 비교적 넓게 확산되고 있습니다.",
    유동성: "거래 유동성이 관찰에 유리한 수준입니다.", 기술: "기술 흐름이 상대적으로 우호적입니다.", 시장환경: "시장 환경이 테마 흐름에 우호적입니다.",
  };
  factorRows(item).sort((a, b) => b.value - a.value).filter((row) => row.value >= 50).forEach((row) => messages.push(factorCopy[row.label]));
  const unique = [...new Set(messages)].slice(0, 3);
  return unique.length ? unique : ["현재 입력 지표의 종합점수가 비교 테마보다 높습니다."];
}

const scoreOf = (item: MarketThemeObservationItem) => item.relative_strength_score ?? item.relative_strength_probability;
const pointDelta = (value: number | null | undefined) => value == null ? "-" : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%p`;

function MLResearchResults({ result }: { result: MarketThemeObservationMLTrainResponse | null }) {
  if (!result) return <div className="observation-ml-empty"><strong>아직 이번 세션의 후보 모델 결과가 없습니다.</strong><p>기존 학습·Gate 계산을 실행해 Baseline과 Candidate를 비교할 수 있습니다.</p></div>;
  const rule = result.baseline_metrics.OBSERVATION_RULE;
  const diagnosticWarnings = result.feature_diagnostics.filter((item) => item.near_constant || item.missing_rate >= .2);
  return <div className="observation-research-results">
    <section className="observation-research-baseline"><header><div><span>운영 기준</span><strong>RULE V2 / Feature V2</strong></div><em>{result.recommendation}</em></header><div><article><span>P@5</span><strong>{percent(rule?.precision_at_5)}</strong></article><article><span>NDCG@5</span><strong>{n(rule?.ndcg_at_5, 3)}</strong></article><article><span>P@10</span><strong>{percent(rule?.precision_at_10)}</strong></article><article><span>Top20</span><strong>{percent(rule?.precision_top20)}</strong></article><article><span>최근 OOS</span><strong>{result.oos_sample_days}일</strong><small>{result.oos_start_date?.slice(5)} ~ {result.oos_end_date?.slice(5)}</small></article></div></section>
    <section className="observation-research-table"><header><div><h4>후보 비교</h4><p>P@5 우선, NDCG@5와 Fold 안정성으로 함께 비교합니다.</p></div><span>Gate: 최고 기준선 Top20 +{(result.gate_required_improvement * 100).toFixed(0)}%p</span></header><div className="table-shell"><table className="data-table compact-table"><thead><tr><th>후보명</th><th>유형</th><th>P@5</th><th>Δ P@5</th><th>NDCG@5</th><th>Δ NDCG</th><th>P@10</th><th>Top20</th><th>승리 Fold</th><th>최근 OOS P@5</th><th>Gate</th><th>상태</th></tr></thead><tbody>{result.candidates.map((candidate: MarketThemeObservationMLCandidate) => <tr key={candidate.model_type}><td><strong>{candidate.model_type}</strong><small>{candidate.feature_version.replace("THEME_OBSERVATION_", "")}</small></td><td>{candidate.candidate_type}</td><td>{percent(candidate.metrics.precision_at_5)}</td><td className={(candidate.delta_precision_at_5 ?? 0) > 0 ? "is-improved" : "is-weaker"}>{pointDelta(candidate.delta_precision_at_5)}</td><td>{n(candidate.metrics.ndcg_at_5, 3)}</td><td className={(candidate.delta_ndcg_at_5 ?? 0) > 0 ? "is-improved" : "is-weaker"}>{pointDelta(candidate.delta_ndcg_at_5)}</td><td>{percent(candidate.metrics.precision_at_10)}</td><td>{percent(candidate.metrics.precision_top20)}</td><td>{candidate.improving_fold_count}/{candidate.validation_fold_count}<small>최저 {percent(candidate.worst_fold_precision_at_5)}</small></td><td>{percent(candidate.oos_metrics?.precision_at_5)}</td><td>{candidate.selection_gate_status}</td><td>{candidate.candidate_status}</td></tr>)}</tbody></table></div></section>
    <section className="observation-research-table"><header><div><h4>Feature Group Ablation</h4><p>FULL HGBC에서 그룹 하나를 제거한 동일 Walk-forward 결과입니다.</p></div></header><div className="table-shell"><table className="data-table compact-table"><thead><tr><th>Feature Group</th><th>제거 후 P@5</th><th>Δ P@5</th><th>NDCG@5</th><th>Δ NDCG</th><th>판정</th></tr></thead><tbody>{result.ablation_results.map((item) => <tr key={item.feature_group}><td><strong>{item.feature_group === "FULL" ? "FULL" : `− ${item.feature_group}`}</strong></td><td>{percent(item.metrics.precision_at_5)}</td><td className={item.delta_precision_at_5 > 0 ? "is-improved" : item.delta_precision_at_5 < 0 ? "is-weaker" : ""}>{pointDelta(item.delta_precision_at_5)}</td><td>{n(item.metrics.ndcg_at_5, 3)}</td><td>{pointDelta(item.delta_ndcg_at_5)}</td><td>{item.verdict}</td></tr>)}</tbody></table></div></section>
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
  const [marketChoiceOpen, setMarketChoiceOpen] = useState(false);
  const [progressMessage, setProgressMessage] = useState("");
  const abortRef = useRef<AbortController | null>(null);
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
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "관찰 우선순위 요청에 실패했습니다.");
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
    if (!targetDate) return "관찰 대상일을 선택해 주세요.";
    const day = new Date(`${targetDate}T00:00:00`).getDay();
    if ([0, 6].includes(day)) return "신규 관찰순위의 관찰 대상일은 평일이어야 합니다.";
    const cutoff = data?.calculation_data_cutoff_date;
    if (cutoff && targetDate <= cutoff) return "과거 대상일은 신규 관찰순위를 계산할 수 없습니다.";
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
  const dateSetLabel = `${shortDate(data?.calculation_data_cutoff_date ?? data?.data_cutoff_date)} 데이터 → ${shortDate(data?.run?.target_date ?? targetDate)} 관찰`;

  return <div className="theme-prediction-panel observation-priority-panel observation-workspace">
    <header className="observation-workspace-header"><div><span>THEME OBSERVATION</span><h2>테마 관찰 우선순위</h2><p>다음 거래일에 상대적으로 먼저 관찰할 테마를 선별합니다.</p></div><div className="observation-header-actions"><button className="btn btn-primary" type="button" disabled={!targetDate || Boolean(action)} onClick={prepareCalculation}>{action.includes("calculate") ? "생성 중..." : "오늘 순위 생성"}</button><button className="btn btn-secondary" type="button" disabled={!data?.run || Boolean(action)} onClick={() => void validate()}>{action === "validate" ? "반영 중..." : "성과 반영"}</button><button className="btn btn-secondary" type="button" onClick={() => setActiveTab("ml")}>ML 연구</button></div></header>

    <nav className="observation-workspace-tabs" aria-label="테마 관찰 우선순위 보기">{([['today','오늘의 관찰','먼저 볼 테마'],['performance','성과·검증','예측과 실제'],['ml','ML 연구','후보 모델']] as const).map(([key, label, caption]) => <button key={key} type="button" className={activeTab === key ? "is-active" : ""} aria-current={activeTab === key ? "page" : undefined} onClick={() => setActiveTab(key)}><strong>{label}</strong><small>{caption}</small></button>)}</nav>

    <section className="observation-control-bar" aria-label="관찰순위 조회 조건"><div className="observation-date-set"><button type="button" aria-label="이전 관찰일" onClick={() => void navigateObservationDate(shiftBusinessDay(targetDate || today, -1))}><ChevronLeft size={18} /></button><label><span>관찰 세트</span><strong>{dateSetLabel}</strong><input type="date" value={targetDate} aria-label="관찰 대상일" onChange={(event) => { const value = event.target.value; setTargetDate(value); if (value) void queryExisting(value); }} /></label><button type="button" aria-label="다음 관찰일" onClick={() => void navigateObservationDate(shiftBusinessDay(targetDate || today, 1))}><ChevronRight size={18} /></button></div><div className="observation-filter-set"><label><span>테마그룹</span><select value={groupId} onChange={(event) => setGroupId(event.target.value)}><option value="all">전체</option>{props.themeGroups.map((group) => <option key={group.id} value={group.id}>{group.theme_name}</option>)}</select></label><label className="observation-keyword"><span>검색</span><input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="테마명" /></label><label><span>표시</span><select value={limit} onChange={(event) => setLimit(Number(event.target.value))}><option value={10}>Top 10</option><option value={20}>Top 20</option><option value={30}>Top 30</option><option value={50}>Top 50</option></select></label><button className="btn btn-secondary observation-query-button" type="button" disabled={loading || !targetDate} onClick={() => void queryExisting()}>{loading ? "조회 중" : "조회"}</button></div></section>

    {calculateDateError ? <p className="form-error">{calculateDateError}</p> : null}{error ? <div className="inline-result inline-error">{error}</div> : null}{progressMessage ? <div className="inline-result theme-observation-progress">{progressMessage}</div> : null}
    <section className="observation-operating-strip" aria-label="운영 상태"><span><small>운영 모델</small><strong>{operatingModel} · {featureVersionLabel(featureVersion)}</strong></span><span><small>시장보정</small><strong>{data?.run?.calculation_mode === "REFRESHED_MARKET_DATA" ? "적용" : "미적용"}</strong></span><span><small>최근 계산</small><strong>{shortDateTime(data?.run?.calculated_at)}</strong></span><span className={summary.coverage != null && summary.coverage < 1 ? "is-warning" : ""}><small>데이터 완전성</small><strong>{summary.coverage == null ? "-" : percent(summary.coverage)}</strong></span><span className="observation-score-info"><button type="button" aria-expanded={scoreInfoOpen} onClick={() => setScoreInfoOpen((open) => !open)}><Info size={15} /> 관찰점수란?</button>{scoreInfoOpen ? <span role="dialog"><b>관찰점수</b>는 가격·수급·확산·기술·시장환경 등의 상대적 상태를 종합한 0~100 관찰 우선순위 점수이며 상승확률을 의미하지 않습니다.</span> : null}</span></section>
    {summary.coverage != null && summary.coverage < 1 ? <p className="observation-data-warning"><Info size={15} /> 일부 테마의 가격·수급 데이터가 부족합니다. 순위는 제공하되 상세의 데이터 완전성을 함께 확인하세요.</p> : null}

    {activeTab === "today" ? <>{loading && !data ? <div className="observation-empty-state" role="status"><strong>관찰순위를 불러오는 중입니다.</strong><p>저장된 최신 결과를 확인하고 있습니다.</p></div> : null}{!loading && !data?.run ? <div className="observation-empty-state"><strong>{shortDate(targetDate)} 관찰순위가 아직 생성되지 않았습니다.</strong><p>마지막 실측 데이터를 기준으로 다음 거래일의 관찰 대상을 만듭니다.</p><button className="btn btn-primary" type="button" onClick={prepareCalculation}>오늘 순위 생성</button></div> : null}{data?.run ? <>
      <section className="observation-focus-section observation-focus-radar-section"><header><div><span>NEXT SESSION</span><h3>오늘의 집중 관찰</h3><p>{shortDate(data.run.target_date)}에 먼저 확인할 Top 5 테마입니다.</p></div><small>오각형 카드를 누르면 Factor와 연결 종목을 볼 수 있습니다.</small></header><div className="observation-focus-radar-body">{topRows.length ? <ObservationRadarGrid items={topRows} statusNames={stateName} hideHeader onThemeClick={(themeId) => { const item = topRows.find((row) => row.theme_id === themeId); if (item) setSelectedTheme(item); }} /> : <p className="observation-list-empty">현재 필터에 맞는 집중 관찰 테마가 없습니다.</p>}</div></section>
      {candidateRows.length ? <section className="observation-candidate-section"><header><div><h3>추가 관찰 후보</h3><p>Top 6 이후는 핵심 신호만 간결하게 표시합니다.</p></div><b>{candidateRows.length}개</b></header><div className="observation-candidate-table" role="table"><div className="is-head" role="row"><span>순위</span><span>테마</span><span>관찰점수</span><span>변화</span><span>핵심 이유</span><span>상태</span></div>{candidateRows.map((item) => <button key={item.theme_id} type="button" role="row" onClick={() => setSelectedTheme(item)}><b>{item.observation_rank ?? "-"}</b><strong>{item.theme_name}</strong><span>{n(scoreOf(item))}</span><span>—</span><span>{whyMessages(item)[0]}</span><em className={`theme-observation-state state-${item.status_code.toLowerCase()}`}>{stateName[item.status_code]}</em></button>)}</div></section> : null}
      <section className="observation-validation-compact"><div><strong>실전검증 {diagnosticDays}일</strong><span>P@5 {percent(diagnostics?.recent_20.current.precision_at_5)}</span><span>NDCG@5 {n(diagnostics?.recent_20.current.ndcg_at_5, 3)}</span><span>운영모델 {operatingModel}</span></div><button type="button" onClick={() => setActiveTab("performance")}>성과 보기 →</button></section><button className="observation-distribution-toggle" type="button" aria-expanded={scoreDistributionOpen} onClick={() => setScoreDistributionOpen((open) => !open)}>{scoreDistributionOpen ? "점수 분포 닫기" : "점수 분포 보기"}</button>{scoreDistributionOpen ? <ObservationGapChart items={filteredRows} onThemeClick={(themeId) => { const item = filteredRows.find((row) => row.theme_id === themeId); if (item) setSelectedTheme(item); }} /> : null}
    </> : null}</> : null}

    {activeTab === "performance" ? <section className="observation-performance-workspace"><header><div><span>PERFORMANCE</span><h3>성과·검증</h3><p>저장된 관찰순위와 D+1 실제 결과를 비교합니다.</p></div><div className="observation-period-tabs" aria-label="검증 기간">{(["20", "60", "120", "all"] as PeriodKey[]).map((key) => { const unavailable = key === "60" || key === "120"; return <button key={key} type="button" disabled={unavailable} className={period === key ? "is-active" : ""} title={unavailable ? "현재 제공되는 집계 구간이 없습니다." : undefined} onClick={() => setPeriod(key)}>{key === "all" ? "전체" : `최근 ${key}`}</button>; })}</div></header><div className="observation-performance-summary"><article><span>검증일수</span><strong>{period === "all" ? diagnostics?.all.quality_days ?? diagnosticDays : diagnostics?.recent_20.quality_days ?? diagnosticDays}일</strong></article><article><span>P@5</span><strong>{percent(period === "all" ? diagnostics?.all.current.precision_at_5 : diagnostics?.recent_20.current.precision_at_5)}</strong></article><article><span>NDCG@5</span><strong>{n(period === "all" ? diagnostics?.all.current.ndcg_at_5 : diagnostics?.recent_20.current.ndcg_at_5, 3)}</strong></article><article><span>Top20 적중</span><strong>{percent(period === "all" ? diagnostics?.all.current.precision_top20 : diagnostics?.recent_20.current.precision_top20)}</strong></article><article><span>시장보정 효과</span><strong>{n(diagnostics?.paired_correction.mean_refresh_effect)}</strong></article></div>{data?.run ? <div className="observation-result-table" role="table"><div className="is-head" role="row"><span>예측순위</span><span>테마</span><span>관찰점수</span><span>실제순위</span><span>실제 상대강도</span><span>결과</span></div>{filteredRows.map((item) => <button type="button" role="row" key={item.theme_id} onClick={() => setSelectedTheme(item)}><b>{item.observation_rank ?? "-"}</b><strong>{item.theme_name}</strong><span>{n(scoreOf(item))}</span><span>{item.actual_rank ?? "D+1 대기"}</span><span>{n(item.actual_relative_strength)}</span><em>{item.actual_rank == null ? "결과 대기" : `예측 ${item.observation_rank ?? "-"}위 → 실제 ${item.actual_rank}위`}</em></button>)}</div> : <div className="observation-empty-state"><strong>비교할 관찰 결과가 없습니다.</strong></div>}{data?.metrics ? <p className="observation-performance-note"><Info size={15} /> 선택일 기준 평균 순위 오차 {n(data.metrics.mean_rank_error)} · 검증 상태 {data.metrics.evaluation_status}</p> : null}</section> : null}

    {activeTab === "ml" ? <section className="observation-ml-workspace"><header><div><span>RESEARCH ONLY</span><h3>ML 후보 연구</h3><p>운영 순위와 분리된 후보 모델의 Gate·보정·Walk-forward 결과를 확인합니다.</p></div><button className="btn btn-primary" type="button" disabled={Boolean(action)} onClick={() => void train()}>{action === "train" ? "연구 실행 중..." : "후보 모델 검증"}</button></header><p className="observation-ml-boundary"><Info size={15} /> 후보 모델을 검증해도 운영 모델이나 확정 관찰순위는 자동으로 변경되지 않습니다.</p><MLResearchResults result={mlResult} /></section> : null}

    <p className="theme-observation-disclaimer"><Info size={14} /> 관찰우선순위는 다음 거래일 상대강도 관찰용 연구지표이며 매수·매도 추천이 아닙니다.</p>
    <MarketThemeDetailDrawer
      open={Boolean(selectedTheme)}
      themeId={selectedTheme?.theme_id ?? null}
      dataDate={data?.run?.data_cutoff_date ?? data?.calculation_data_cutoff_date}
      headerEyebrow={selectedTheme ? `관찰 ${selectedTheme.observation_rank ?? "-"}위` : undefined}
      headerTitle={selectedTheme?.theme_name}
      headerSubtitle={selectedTheme ? `${data?.run?.display_mode === "PROBABILITY" ? `상대강세 확률 ${n(selectedTheme.relative_strength_probability)}%` : `관찰점수 ${n(scoreOf(selectedTheme))}`} · ${stateName[selectedTheme.status_code]}` : undefined}
      summaryContent={selectedTheme ? <ObservationFactorStrip item={selectedTheme} /> : null}
      hideReturnKpis
      hideTitleBlock
      drawerClassName="observation-linked-detail-drawer"
      onClose={() => setSelectedTheme(null)}
    />

    {marketChoiceOpen ? <div className="theme-observation-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target && !action) setMarketChoiceOpen(false); }}><section className="theme-observation-modal is-organized" role="dialog" aria-modal="true" aria-labelledby="market-refresh-choice-title"><header><div><small>오늘 순위 생성</small><h3 id="market-refresh-choice-title">시장지표를 갱신한 후 생성할까요?</h3></div><button type="button" aria-label="닫기" disabled={Boolean(action)} onClick={() => setMarketChoiceOpen(false)}>×</button></header><p className="theme-observation-modal-intro">직전 관찰결과를 최신 실측으로 먼저 검증한 후 다음 거래일 관찰순위를 생성합니다.</p><section className="theme-observation-modal-basis" aria-label="계산 기준"><h4>계산 기준</h4><dl><div><dt>시장지표 최근 갱신</dt><dd>{dateTime(data?.market_indicator_latest_refreshed_at)}</dd></div><div><dt>테마·종목 기준일</dt><dd>{data?.calculation_data_cutoff_date ?? data?.data_cutoff_date ?? "-"}</dd></div><div><dt>관찰 대상일</dt><dd>{targetDate}</dd></div></dl></section>{progressMessage && action ? <div className="theme-observation-modal-progress" role="status">{progressMessage}</div> : null}<div className="theme-observation-modal-actions"><button className="btn btn-secondary" type="button" disabled={Boolean(action)} onClick={() => void calculate(false)}><span>현재 지표로 생성</span><small>저장된 최신 시장지표를 사용합니다.</small></button><button className="btn btn-primary" type="button" disabled={Boolean(action)} onClick={() => void calculate(true)}><span>전체지표 갱신 후 생성</span><small>시장지표를 갱신하고 관찰순위를 생성합니다.</small></button></div></section></div> : null}
  </div>;
}
