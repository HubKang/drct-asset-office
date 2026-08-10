import { useEffect, useMemo, useRef, useState } from "react";
import { repositories } from "@/services";
import type { MarketTheme, MarketThemeObservationDiagnosticsResponse, MarketThemeObservationItem, MarketThemeObservationMLTrainResponse, MarketThemeObservationResponse } from "@/types/marketTheme";
import ObservationGapChart from "@/components/marketThemes/ObservationGapChart";
import ObservationRadarGrid from "@/components/marketThemes/ObservationRadarGrid";

const nextBusinessDay = () => {
  const value = new Date(); value.setDate(value.getDate() + 1);
  while (value.getDay() === 0 || value.getDay() === 6) value.setDate(value.getDate() + 1);
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
};
const n = (value: number | null | undefined, digits = 1) => value == null ? "-" : value.toFixed(digits);
const percent = (value: number | null | undefined) => value == null ? "-" : `${(value * 100).toFixed(1)}%`;
const dateTime = (value: string | null | undefined) => value ? value.replace("T", " ").slice(0, 16) : "-";
const stateName: Record<string, string> = {
  FLOW_LEADING: "수급 선도", STRONG_CONTINUATION: "강세 지속", REVERSAL_WATCH: "반전 관찰",
  NEUTRAL: "중립", OVERHEAT_RISK: "과열 위험", FLOW_EXIT: "수급 이탈",
};

export default function MarketThemeReturnPredictionPanel(props: {
  themeGroups: MarketTheme[];
  onThemeClick: (themeId: number) => void;
}) {
  const [data, setData] = useState<MarketThemeObservationResponse | null>(null);
  const [targetDate, setTargetDate] = useState(nextBusinessDay);
  const [groupId, setGroupId] = useState("all");
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(false); const [action, setAction] = useState(""); const [error, setError] = useState("");
  const [calculateDateError, setCalculateDateError] = useState("");
  const [mlResult, setMLResult] = useState<MarketThemeObservationMLTrainResponse | null>(null);
  const [diagnostics, setDiagnostics] = useState<MarketThemeObservationDiagnosticsResponse | null>(null);
  const [marketChoiceOpen, setMarketChoiceOpen] = useState(false);
  const [progressMessage, setProgressMessage] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  const request = async (work: (signal: AbortSignal) => Promise<MarketThemeObservationResponse>, options?: { preserveTargetDate?: boolean }) => {
    abortRef.current?.abort(); const controller = new AbortController(); abortRef.current = controller;
    setLoading(true); setError("");
    try {
      const result = await work(controller.signal); setData(result);
      if (!options?.preserveTargetDate) {
        const responseTargetDate = result.run?.target_date ?? result.default_target_date;
        if (responseTargetDate) setTargetDate(responseTargetDate);
      }
      return result;
    }
    catch (reason) { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "관찰 우선순위 요청에 실패했습니다."); return null; }
    finally { if (!controller.signal.aborted) setLoading(false); }
  };

  const loadDiagnostics = async () => { try { setDiagnostics(await repositories.marketThemes.getObservationDiagnostics()); } catch { /* 관찰 결과 조회는 진단 실패와 독립적으로 유지한다. */ } };
  useEffect(() => { void request((signal) => repositories.marketThemes.getLatestObservationPriority(signal)).then(() => loadDiagnostics()); return () => abortRef.current?.abort(); }, []);
  useEffect(() => {
    if (!marketChoiceOpen || action) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setMarketChoiceOpen(false); };
    window.addEventListener("keydown", close); return () => window.removeEventListener("keydown", close);
  }, [action, marketChoiceOpen]);
  const filteredRows = useMemo(() => {
    const term = keyword.trim().toLocaleLowerCase("ko-KR");
    const filtered = (data?.items ?? []).filter((item) => (groupId === "all" || String(item.theme_group_id ?? "") === groupId) &&
      (!term || item.theme_name.toLocaleLowerCase("ko-KR").includes(term) || (item.theme_group_name ?? "").toLocaleLowerCase("ko-KR").includes(term)));
    return filtered.sort((a, b) => (a.observation_rank ?? 999) - (b.observation_rank ?? 999));
  }, [data?.items, groupId, keyword]);
  const chartRows = useMemo(() => filteredRows.slice(0, 10), [filteredRows]);
  const displayValue = (item: MarketThemeObservationItem) => data?.run?.display_mode === "PROBABILITY" ? item.relative_strength_probability : item.relative_strength_score;
  const valueLabel = (item: MarketThemeObservationItem) => {
    const value = displayValue(item); return value == null ? "-" : data?.run?.display_mode === "PROBABILITY" ? `${n(value)}%` : `${n(value)}점`;
  };
  const summary = useMemo(() => ({ top: data?.items.find((item) => item.observation_rank === 1),
    top5: data?.items.filter((item) => (item.observation_rank ?? 999) <= 5).length ?? 0,
    leading: data?.items.filter((item) => item.status_code === "FLOW_LEADING" || item.status_code === "STRONG_CONTINUATION").length ?? 0,
    coverage: data?.items.length ? data.items.reduce((sum, item) => sum + item.data_coverage_rate, 0) / data.items.length : null }), [data?.items]);
  const calculationDateError = () => {
    if (!targetDate) return "관찰 대상일을 선택해 주세요.";
    const day = new Date(`${targetDate}T00:00:00`).getDay();
    if ([0, 6].includes(day)) return "신규 관찰순위의 관찰 대상일은 평일이어야 합니다.";
    const cutoff = data?.calculation_data_cutoff_date;
    if (cutoff && targetDate <= cutoff) return "과거 대상일은 신규 관찰순위를 계산할 수 없습니다.";
    return "";
  };
  const queryExisting = async () => {
    setCalculateDateError("");
    setProgressMessage("");
    await request((signal) => repositories.marketThemes.getObservationPriority(targetDate, signal), { preserveTargetDate: true });
  };
  const prepareCalculation = () => {
    const validationError = calculationDateError();
    setCalculateDateError(validationError);
    if (!validationError) setMarketChoiceOpen(true);
  };
  const calculate = async (refreshMarketIndicators: boolean) => {
    const validationError = calculationDateError();
    if (validationError || action) { setCalculateDateError(validationError); return; }
    setCalculateDateError("");
    setAction(refreshMarketIndicators ? "refresh-calculate" : "calculate");
    setProgressMessage(refreshMarketIndicators
      ? "1/3 최근 관찰결과를 실측 데이터로 검증하고 있습니다...\n2/3 시장지표를 갱신하고 있습니다...\n3/3 최신 시장환경으로 D+1 관찰순위를 계산하고 있습니다..."
      : "1/2 최근 관찰결과를 실측 데이터로 검증하고 있습니다...\n2/2 D+1 관찰순위를 계산하고 있습니다...");
    const result = await request((signal) => repositories.marketThemes.calculateObservationPriority(targetDate, refreshMarketIndicators, signal));
    setProgressMessage(result
      ? `${result.pre_validation_message ?? "이전 관찰결과 자동검증 확인 완료"}\n${refreshMarketIndicators ? "실측 검증 및 시장지표 보정관찰 계산 완료" : "실측 검증 및 D+1 관찰순위 계산 완료"}`
      : refreshMarketIndicators ? "시장지표 갱신 또는 보정관찰 계산에 실패했습니다. 현재 저장 지표로 다시 계산할 수 있습니다." : "관찰순위 계산에 실패했습니다.");
    setAction(""); if (result) { setMarketChoiceOpen(false); await loadDiagnostics(); }
  };
  const validate = async () => { if (!data?.run) return; setAction("validate"); await request((signal) => repositories.marketThemes.validateObservationPriority(data.run!.target_date, signal)); await loadDiagnostics(); setAction(""); };
  const train = async () => { setAction("train"); setError(""); try { setMLResult(await repositories.marketThemes.trainObservationML()); } catch (reason) { setError(reason instanceof Error ? reason.message : "ML 학습에 실패했습니다."); } finally { setAction(""); } };

  return <div className="theme-prediction-panel observation-priority-panel">
    <div className="theme-prediction-toolbar">
      <label><span>데이터 기준일</span><strong>{data?.data_cutoff_date ?? "-"}</strong></label>
      <label><span>관찰 대상일</span><input className="input-control" type="date" value={targetDate} onChange={(event) => { setTargetDate(event.target.value); setCalculateDateError(""); }} /></label>
      <label><span>테마그룹</span><select className="select-control" value={groupId} onChange={(event) => setGroupId(event.target.value)}><option value="all">전체</option>{props.themeGroups.map((group) => <option key={group.id} value={group.id}>{group.theme_name}</option>)}</select></label>
      <label><span>검색</span><input className="input-control" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="테마명" /></label>
      <label><span>표시</span><select className="select-control" value="10" disabled aria-label="표시"><option value="10">상위 10</option></select></label>
      <button className="btn btn-secondary" type="button" disabled={loading || !targetDate} onClick={() => void queryExisting()}>조회</button>
      <button className="btn btn-primary" type="button" disabled={!targetDate || Boolean(action)} onClick={prepareCalculation}>{action.includes("calculate") ? "계산 중..." : "관찰순위 계산"}</button>
      {data?.run ? <button className="btn btn-secondary" type="button" disabled={Boolean(action)} title="저장된 실측 데이터를 기준으로 선택일의 관찰결과를 다시 검증합니다." onClick={() => void validate()}>{action === "validate" ? "재검증 중..." : "재검증"}</button> : null}
    </div>
    <p className="theme-observation-date-help">관찰 대상일은 해당 날짜의 저장 결과를 조회합니다. 데이터 기준일은 관찰순위 계산에 사용된 마지막 실측일입니다.</p>
    {calculateDateError ? <p className="form-error">{calculateDateError}</p> : null}
    {error ? <div className="inline-result inline-error">{error}</div> : null}{data?.message ? <div className="inline-result">{data.message}</div> : null}
    {progressMessage ? <div className="inline-result theme-observation-progress">{progressMessage}</div> : null}
    <div className="theme-prediction-meta"><span className={`theme-prediction-status status-${(data?.status ?? "draft").toLowerCase()}`}>{data?.status ?? "DRAFT"}</span>
      <span>방법 {data?.run?.method ?? "OBSERVATION_RULE"}</span><span>{data?.run?.feature_version ?? "THEME_OBSERVATION_FEATURE_V1"}</span>
      <span>{data?.run?.display_mode === "PROBABILITY" ? "보정 확률" : "관찰 점수(확률 아님)"}</span>
      <span>{data?.run?.calculation_mode === "REFRESHED_MARKET_DATA" ? "시장지표 보정관찰" : "기존 시장지표 기준"}</span>
      <span>시장지표 {dateTime(data?.run?.market_indicator_refreshed_at ?? data?.market_indicator_latest_refreshed_at)}</span>
      <button className="btn btn-secondary btn-table-sm" type="button" disabled={Boolean(action)} onClick={() => void train()}>{action === "train" ? "ML 학습 중..." : "ML 후보 연구"}</button>
    </div>
    <p className="theme-observation-disclaimer">관찰 우선순위는 다음 거래일 상대강도 관찰을 위한 연구 지표이며 매수 추천이 아닙니다.</p>
    {data?.pre_validation_status ? <div className="theme-observation-auto-validation">
      <span>최근 자동검증 <b>{data.pre_validation_target_date ?? "대상 없음"}</b></span>
      <span>상태 <b>{data.pre_validation_quality_status ?? data.pre_validation_status}</b></span>
      <span>D+1 대상 <b>{data.run?.target_date ?? targetDate}</b></span>
      <span>시장보정 <b>{data.run?.calculation_mode === "REFRESHED_MARKET_DATA" ? "적용" : "미적용"}</b></span>
    </div> : null}
    {diagnostics ? <section className={`theme-observation-diagnostics status-${diagnostics.diagnostic_status.toLowerCase()}`}>
      <header><h3>실전검증 진단</h3><span className="theme-observation-diagnostic-badge">{diagnostics.messages[0]?.title ?? "관찰 로직 상태"}</span><strong>{diagnostics.quality_evaluated_days} / 20일</strong></header>
      <div className="theme-observation-diagnostic-grid">
        <article><span>최근 CURRENT</span><p>Top20 <b>{percent(diagnostics.recent_20.current.precision_top20)}</b><i>·</i>NDCG@5 <b>{n(diagnostics.recent_20.current.ndcg_at_5, 3)}</b></p></article>
        <article><span>시장보정</span><p>paired <b>{diagnostics.paired_correction.paired_days}일</b><i>·</i>효과 <b>{n(diagnostics.paired_correction.mean_refresh_effect)}</b></p></article>
        <article><span>ML 재학습</span><p>학습 후 <b>{diagnostics.ml_quality_days_since_training}일</b><i>·</i>자동학습 안 함</p></article>
      </div>
      <footer>{diagnostics.messages[0]?.message ?? "현재 진단 상태를 유지합니다."}</footer>
    </section> : null}
    <div className="theme-prediction-summary theme-observation-summary">
      <article><span>관찰 1위</span><div><strong>{summary.top?.theme_name ?? "-"}</strong><em>{summary.top ? valueLabel(summary.top) : "-"}</em></div></article>
      <article><span>시장보정</span><div><strong>{data?.run?.calculation_mode === "REFRESHED_MARKET_DATA" ? "적용" : "미적용"}</strong><em>{data?.run?.market_refresh_status === "PARTIAL" ? "일부 갱신 실패 · 기존값 포함" : dateTime(data?.run?.market_indicator_refreshed_at ?? data?.market_indicator_latest_refreshed_at)}</em></div></article>
      <article><span>집중 관찰</span><div><strong>{summary.top5}개</strong><em>상위 5개 테마</em></div></article>
      <article><span>수급·강세 상태</span><div><strong>{summary.leading}개</strong><em>선도·지속 상태</em></div></article>
      <article><span>평균 데이터 완전성</span><div><strong>{summary.coverage == null ? "-" : percent(summary.coverage)}</strong><em>{data?.items.length ?? 0}개 테마 기준</em></div></article>
    </div>
    {data?.metrics ? <div className="theme-prediction-summary validation"><article><span>Top20 정밀도</span><strong>{percent(data.metrics.precision_top20)}</strong></article>
      <article><span>Top20 재현율 / F1</span><strong>{percent(data.metrics.recall_top20)}</strong><em>{percent(data.metrics.f1_top20)}</em></article>
      <article><span>P@5 / NDCG@5</span><strong>{percent(data.metrics.precision_at_5)}</strong><em>{n(data.metrics.ndcg_at_5, 3)}</em></article>
      <article><span>평균 순위 오차</span><strong>{n(data.metrics.mean_rank_error)}</strong></article></div> : null}
    {mlResult ? <section className="theme-prediction-model-metrics"><h3>Phase4 ML 후보 검증</h3><p>{mlResult.message} · {mlResult.qualified_date_count}개 유니버스 날짜 · {mlResult.validation_fold_count} folds</p>
      <div className="table-shell"><table className="data-table compact-table"><thead><tr><th>모델</th><th>Top20</th><th>P@5</th><th>NDCG@5</th><th>Brier raw→보정</th><th>ECE raw→보정</th><th>Gate</th></tr></thead><tbody>{mlResult.candidates.map((item) => <tr key={item.model_version ?? item.model_type}><td>{item.model_type}<small>{item.probability_display_mode}</small></td><td>{percent(item.metrics.precision_top20)}</td><td>{percent(item.metrics.precision_at_5)}</td><td>{n(item.metrics.ndcg_at_5, 3)}</td><td>{n(item.metrics.raw_brier, 3)} → {n(item.metrics.brier, 3)}</td><td>{n(item.metrics.raw_calibration_error, 3)} → {n(item.metrics.calibration_error, 3)}</td><td>{item.selection_gate_status}<small>보정 {item.calibration_status}</small></td></tr>)}</tbody></table></div></section> : null}
    <ObservationGapChart items={chartRows} onThemeClick={props.onThemeClick} />
    <ObservationRadarGrid items={chartRows} statusNames={stateName} onThemeClick={props.onThemeClick} />
    {marketChoiceOpen ? <div className="theme-observation-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target && !action) setMarketChoiceOpen(false); }}><section className="theme-observation-modal" role="dialog" aria-modal="true" aria-labelledby="market-refresh-choice-title">
      <header><div><small>관찰순위 계산</small><h3 id="market-refresh-choice-title">시장지표를 갱신한 후 계산할까요?</h3></div><button type="button" aria-label="닫기" disabled={Boolean(action)} onClick={() => setMarketChoiceOpen(false)}>×</button></header>
      <p>직전 관찰결과를 최신 실측으로 먼저 검증한 후 D+1 관찰순위를 계산합니다. 최신 시장환경 반영 여부를 선택해 주세요.</p>
      <dl><dt>현재 시장지표 최근 갱신</dt><dd>{dateTime(data?.market_indicator_latest_refreshed_at)}</dd><dt>테마·종목 기준일</dt><dd>{data?.calculation_data_cutoff_date ?? data?.data_cutoff_date ?? "-"}</dd><dt>관찰 대상일</dt><dd>{targetDate}</dd></dl>
      {progressMessage && action ? <div className="theme-observation-modal-progress" role="status">{progressMessage}</div> : null}
      <div className="theme-observation-modal-actions"><button className="btn btn-secondary" type="button" disabled={Boolean(action)} onClick={() => void calculate(false)}>현재 지표로 계산</button><button className="btn btn-primary" type="button" disabled={Boolean(action)} onClick={() => void calculate(true)}>전체지표 갱신 후 계산<small>시장지표 전체갱신 후 관찰순위를 계산합니다.</small></button></div>
    </section></div> : null}
  </div>;
}
