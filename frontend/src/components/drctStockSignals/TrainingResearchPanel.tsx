import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight, Database, RefreshCw, X } from "lucide-react";

import { repositories } from "@/services";
import type { DrctScoreBucket, DrctSignalSearchDetail, DrctTrainingCaseDetail, DrctTrainingCaseList, DrctTrainingReadiness, DrctValidationCase, DrctValidationOutcomeMetric, DrctValidationReport } from "@/types/drctStockSignal";

const message = (reason: unknown) => reason instanceof Error ? reason.message : "학습 데이터를 불러오지 못했습니다.";
const ratioPct = (value: number | null) => value == null ? "-" : `${(value * 100).toFixed(1)}%`;
const percent = (value: number | null) => value == null ? "-" : `${value.toFixed(1)}%`;
const num = (value: number | null, suffix = "") => value == null ? "-" : `${value.toFixed(2)}${suffix}`;
const blockerText: Record<string, string> = {
  RULE_NOT_CONFIGURED: "현재 검색식 Version에 실행 가능한 DrCT Rule이 없습니다. 학습 Dataset을 생성하려면 먼저 DrCT 실행식을 구성하십시오.",
  RULE_INVALID: "현재 Version의 실행 Rule이 유효하지 않습니다.",
  NO_MARKER_LINK: "이 검색식에 연결된 차트마커가 없습니다. 성공패턴 학습에 사용할 마커를 먼저 연결하십시오.",
};

function ScoreBucketTable({ rows }: { rows: DrctScoreBucket[] }) {
  if (!rows.length) return <p className="drct-training-small-state">Out-of-Sample 평가 사례가 부족합니다.</p>;
  return <div className="drct-score-buckets"><table><thead><tr><th>Score</th><th>n</th><th>관찰된 성공 비율</th><th>D+20</th><th>Median</th><th>MFE</th><th>MAE</th></tr></thead><tbody>{rows.map((row) => <tr key={row.bucket}><th>{row.bucket}</th><td>{row.n}</td><td>{percent(row.observed_success_ratio)}</td><td>{num(row.d20_return, "%")}</td><td>{num(row.d20_median, "%")}</td><td>{num(row.mfe_20, "%")}</td><td>{num(row.mae_20, "%")}</td></tr>)}</tbody></table></div>;
}

function ResearchCases({ title, rows, onSelect }: { title: string; rows: DrctValidationCase[]; onSelect: (item: DrctValidationCase) => void }) {
  return <section><h4>{title} <span>{rows.length}건</span></h4>{rows.length ? <div>{rows.slice(0, 30).map((item) => <button type="button" key={`${item.stock_id}-${item.d0}-${item.reason}`} onClick={() => onSelect(item)}><strong>{item.stock_name}</strong><span>{item.d0} · {item.label}</span><small>{item.reason}{item.prototype_score != null ? ` · Prototype ${item.prototype_score.toFixed(1)}` : ""}{item.shadow_score != null ? ` · SHADOW ${item.shadow_score.toFixed(1)}` : ""}</small></button>)}</div> : <p>해당 사례가 없습니다.</p>}</section>;
}

function TrainingResearchPanel({ detail }: { detail: DrctSignalSearchDetail }) {
  const versionId = detail.current_version.id;
  const [readiness, setReadiness] = useState<DrctTrainingReadiness | null>(null);
  const [cases, setCases] = useState<DrctTrainingCaseList | null>(null);
  const [caseDetail, setCaseDetail] = useState<DrctTrainingCaseDetail | null>(null);
  const [caseContext, setCaseContext] = useState<string | null>(null);
  const [report, setReport] = useState<DrctValidationReport | null>(null);
  const [includeAll, setIncludeAll] = useState(false);
  const [casesOpen, setCasesOpen] = useState(false);
  const [baselineOpen, setBaselineOpen] = useState(false);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [featureOpen, setFeatureOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedKeyRef = useRef("");

  const loadReadiness = useCallback(async () => {
    setError(null);
    try {
      const [readinessResult, reportResult] = await Promise.all([repositories.drctStockSignals.trainingReadiness(detail.id, versionId), repositories.drctStockSignals.validationReport(detail.id, versionId)]);
      setReadiness(readinessResult); setReport(reportResult); setError(null);
    }
    catch (reason) { setError(message(reason)); }
  }, [detail.id, versionId]);

  useEffect(() => { const key = `${detail.id}-${versionId}-${detail.marker_links.length}`; if (loadedKeyRef.current === key) return; loadedKeyRef.current = key; setCases(null); setReport(null); setCaseDetail(null); void loadReadiness(); }, [loadReadiness, detail.id, detail.marker_links.length, versionId]);

  const refreshDataset = async () => {
    setBusy(true); setError(null);
    try {
      const [readinessResult, reportResult] = await Promise.all([repositories.drctStockSignals.previewTrainingDataset(detail.id, versionId), repositories.drctStockSignals.validationReport(detail.id, versionId)]);
      setReadiness(readinessResult); setReport(reportResult);
    }
    catch (reason) { setError(message(reason)); } finally { setBusy(false); }
  };
  const loadCases = async (nextIncludeAll = includeAll) => {
    setBusy(true); setError(null);
    try { setCases(await repositories.drctStockSignals.trainingCases(detail.id, versionId, nextIncludeAll)); setCasesOpen(true); }
    catch (reason) { setError(message(reason)); } finally { setBusy(false); }
  };
  const loadCaseDetail = async (item: { stock_id: number; d0: string; reason?: string; prototype_score?: number; shadow_score?: number }) => {
    setBusy(true);
    try { setCaseContext(item.reason ? `${item.reason}${item.prototype_score != null ? ` · Prototype ${item.prototype_score.toFixed(1)}` : ""}${item.shadow_score != null ? ` · SHADOW ${item.shadow_score.toFixed(1)}` : ""}` : null); setCaseDetail(await repositories.drctStockSignals.trainingCaseDetail(detail.id, versionId, item.stock_id, item.d0)); }
    catch (reason) { setError(message(reason)); } finally { setBusy(false); }
  };
  const evaluate = async () => {
    setBusy(true); setError(null);
    try { setReport(await repositories.drctStockSignals.validationReport(detail.id, versionId)); setBaselineOpen(true); }
    catch (reason) { setError(message(reason)); } finally { setBusy(false); }
  };

  const summary = readiness?.summary;
  const blocked = Boolean(summary?.blocking_reasons.length);
  const checklist = report?.checklist;
  const outcome = (label: "success" | "failure", key: string) => report?.outcomes[label][key] as DrctValidationOutcomeMetric | undefined;
  return <section className="drct-signal-detail-section drct-training-research">
    <div className="drct-signal-detail-section-head"><div><h3>성공패턴 학습 <span>Feature Schema v{readiness?.feature_schema_version ?? 1}</span></h3><p>D0 시점 Rule을 재검증하고 과거 정보만으로 검색식 Version별 Dataset을 런타임 생성합니다.</p></div><div className="drct-training-actions"><span className={`drct-training-readiness ${blocked ? "blocked" : "ready"}`}>{report?.research_status ?? (!readiness ? "확인 중" : blocked ? "NOT_READY" : "검증 필요")}</span><button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void refreshDataset()}><RefreshCw size={13} /> 검증 새로고침</button></div></div>
    {error ? <p className="drct-signal-inline-error" role="alert">{error}</p> : null}
    {summary?.blocking_reasons.map((reason) => <div className="drct-training-blocker" key={reason}><strong>{reason}</strong><span>{blockerText[reason] ?? "학습 준비 조건을 확인하세요."}</span></div>)}
    {checklist ? <div className="drct-training-checklist"><strong>학습 준비 Checklist</strong><div>{[
      ["HTS 참조식 등록", checklist.hts_reference_registered, null], ["DrCT Rule VALID", checklist.rule_valid, "drct-rule-section"], ["Marker 연결", checklist.marker_linked, "drct-marker-section"], ["Reviewed Case", checklist.reviewed_case_exists, null], ["Rule Match Case", checklist.rule_match_exists, null], ["CORE Feature", checklist.core_ready, null], ["ENRICHED Feature", checklist.enriched_ready, null],
    ].map(([label, ready, target]) => <button type="button" key={String(label)} className={ready ? "is-ready" : "is-pending"} onClick={() => target && document.getElementById(String(target))?.scrollIntoView({ behavior: "smooth", block: "start" })}><span>{ready ? "✓" : "△"}</span>{label}</button>)}</div></div> : null}
    {summary ? <>
      <div className="drct-training-funnel" aria-label="학습 Dataset 퍼널">
        {[['마커 연결', summary.marker_link_count], ['연결 이벤트', summary.linked_event_count], ['중복 제거', summary.dedup_case_count], ['Rule 일치', summary.rule_matched_count], ['CORE 준비', summary.core_ready_count], ['성공', summary.success_count], ['실패', summary.failure_count]].map(([label, value], index) => <div key={String(label)}><span>{label}</span><strong>{value}</strong>{index < 6 ? <ChevronRight size={13} /> : null}</div>)}
      </div>
      <div className="drct-training-notes"><span>Rule 불일치 {summary.rule_no_match_count}</span><span>Rule 데이터 부족 {summary.rule_data_incomplete_count}</span><span>Label 충돌 {summary.label_conflict_count}</span><span>미판정 {summary.undecided_count}</span><span>Rule 일치율 {percent(summary.rule_match_rate)}</span><span>실행 {report?.elapsed_ms ?? readiness?.elapsed_ms ?? 0}ms</span></div>
      {report ? <><div className="drct-quality-gates">{([['복기 Coverage','reviewed_coverage'],['Rule Match','rule_match_rate'],['CORE','core_coverage'],['ENRICHED','enriched_coverage'],['D+20','d20_coverage']] as const).map(([label,key]) => { const gate=report.quality_gate[key]; const threshold=report.quality_gate.thresholds[key]; const warning=gate.value != null && threshold != null && gate.value < threshold; return <article key={key} className={warning ? "warning" : ""}><span>{label}</span><strong>{percent(gate.value)}</strong><small>{gate.numerator} / {gate.denominator}</small></article>; })}</div><div className="drct-label-distribution"><span>Dataset Label 분포</span><strong>SUCCESS {report.labels.success_count}</strong><strong>FAILURE {report.labels.failure_count}</strong><em>관찰된 SUCCESS 비율 {percent(report.labels.observed_success_ratio)}</em></div></> : null}
      {report ? <div className="drct-outcome-compare"><table><thead><tr><th>Market Outcome</th><th>SUCCESS</th><th>FAILURE</th><th>Δ</th></tr></thead><tbody>{([['D+5','d5_return'],['D+10','d10_return'],['D+20','d20_return'],['MFE','mfe_20'],['MAE','mae_20']] as const).map(([label,key]) => <tr key={key}><th>{label}</th><td>{num(outcome('success',key)?.mean ?? null,'%')}<small>median {num(outcome('success',key)?.median ?? null,'%')} · n={outcome('success',key)?.n ?? 0}</small></td><td>{num(outcome('failure',key)?.mean ?? null,'%')}<small>median {num(outcome('failure',key)?.median ?? null,'%')} · n={outcome('failure',key)?.n ?? 0}</small></td><td>{num(report.outcomes.difference[key],'%')}</td></tr>)}</tbody></table></div> : null}
      <p className="drct-training-leakage-note">Future Outcome은 평가용이며 Feature 입력에는 포함되지 않습니다. 원본 시세·지표·사례 Feature Matrix는 저장하지 않습니다.</p>
    </> : <div className="drct-signal-model-empty"><strong>학습 준비 상태를 계산하는 중입니다.</strong></div>}

    <div className="drct-training-accordion">
      <button type="button" onClick={() => casesOpen ? setCasesOpen(false) : void loadCases()}>{casesOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />} 사례 탐색 <span>{cases?.total ?? summary?.dedup_case_count ?? 0}건</span></button>
      {casesOpen ? <div className="drct-training-accordion-body"><label className="drct-training-toggle"><input type="checkbox" checked={includeAll} onChange={(event) => { setIncludeAll(event.target.checked); void loadCases(event.target.checked); }} /> 제외·미판정 사례 포함</label>{cases?.items.length ? <div className="drct-training-case-table"><table><thead><tr><th>D0</th><th>종목</th><th>Label</th><th>Marker</th><th>Rule</th><th>Feature</th><th>D+20</th><th>MFE</th><th>MAE</th></tr></thead><tbody>{cases.items.map((item) => <tr key={`${item.stock_id}-${item.d0}`} onClick={() => void loadCaseDetail(item)}><td>{item.d0}</td><td><strong>{item.stock_name}</strong><small>{item.stock_code}</small></td><td><span className={`label-${item.label.toLowerCase()}`}>{item.label}</span></td><td>{item.matched_marker_names.join(", ")}</td><td>{item.rule_status}</td><td>CORE {item.core_status}<small>ENRICHED {item.enriched_status}</small></td><td>{num(item.d20_return, "%")}</td><td>{num(item.mfe_20, "%")}</td><td>{num(item.mae_20, "%")}</td></tr>)}</tbody></table></div> : <div className="drct-training-empty"><Database size={18} /> 표시할 학습 사례가 없습니다.</div>}</div> : null}
    </div>
    <div className="drct-training-accordion">
      <button type="button" disabled={blocked || busy} onClick={() => baselineOpen ? setBaselineOpen(false) : report ? setBaselineOpen(true) : void evaluate()}>{baselineOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />} Baseline OOS 검증 <span>Prototype · Logistic SHADOW</span></button>
      {baselineOpen && report ? <div className="drct-baseline-validation"><article><header><div><strong>Success Prototype OOS</strong><small>과거 SUCCESS로 다음 날짜 Batch 평가</small></div><span>{report.prototype.status}</span></header><div className="drct-training-baseline-metrics"><span>Training <b>{report.prototype.training_case_count}</b></span><span>Evaluated <b>{report.prototype.evaluated_case_count}</b></span><span>초기 Window <b>{report.prototype.initial_training_window_count}</b></span></div><ScoreBucketTable rows={report.prototype.buckets} /></article><article><header><div><strong>L2 Logistic SHADOW</strong><small>Expanding Window · {report.metadata.feature_profile}</small></div><span>{report.logistic.status}</span></header><div className="drct-training-baseline-metrics"><span>Training <b>{report.logistic.training_case_count}</b></span><span>Evaluated <b>{report.logistic.evaluated_case_count}</b></span>{report.logistic.metrics ? <><span>Accuracy <b>{ratioPct(report.logistic.metrics.accuracy)}</b></span><span>Precision <b>{ratioPct(report.logistic.metrics.precision)}</b></span><span>Recall <b>{ratioPct(report.logistic.metrics.recall)}</b></span><span>ROC AUC <b>{num(report.logistic.metrics.roc_auc)}</b></span><span>Brier <b>{num(report.logistic.metrics.brier_score)}</b></span></> : null}</div><ScoreBucketTable rows={report.logistic.buckets} /><div className="drct-training-effects">{report.logistic.feature_effects?.slice(0, 5).map((effect) => <span key={effect.feature}>{effect.feature} <b>{effect.coefficient > 0 ? "+" : ""}{effect.coefficient.toFixed(3)}</b></span>)}</div></article><p className="drct-score-relationship">동일 OOS 사례 {report.score_relationship.matched_case_count}건 · Pearson {num(report.score_relationship.pearson)} · Spearman {num(report.score_relationship.spearman)}</p></div> : null}
    </div>
    <div className="drct-training-accordion">
      <button type="button" onClick={() => setAnalysisOpen((current) => !current)}>{analysisOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />} 사례 품질 분석 <span>Rule 불일치 · 데이터 부족 · 모델 불일치</span></button>
      {analysisOpen && report ? <div className="drct-research-case-groups"><ResearchCases title="Rule 불일치" rows={report.rule_mismatch_cases} onSelect={(item) => void loadCaseDetail(item)} /><ResearchCases title="Data Incomplete" rows={report.data_incomplete_cases} onSelect={(item) => void loadCaseDetail(item)} /><ResearchCases title="모델 불일치 사례" rows={report.model_disagreement_cases} onSelect={(item) => void loadCaseDetail(item)} /></div> : null}
    </div>
    <div className="drct-training-accordion">
      <button type="button" onClick={() => setFeatureOpen((current) => !current)}>{featureOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />} 성공/실패 Feature 연구 <span>분포 차이 · 고상관 후보</span></button>
      {featureOpen && report ? <div className="drct-feature-research"><section><h4>성공/실패 Feature 차이</h4>{report.feature_distribution.length ? <div className="drct-score-buckets"><table><thead><tr><th>Feature</th><th>SUCCESS Median</th><th>FAILURE Median</th><th>Difference</th><th>S IQR</th><th>F IQR</th></tr></thead><tbody>{report.feature_distribution.map((row) => <tr key={row.feature}><th>{row.feature}</th><td>{num(row.success_median)}</td><td>{num(row.failure_median)}</td><td>{num(row.difference)}</td><td>{num(row.success_iqr)}</td><td>{num(row.failure_iqr)}</td></tr>)}</tbody></table></div> : <p>SUCCESS와 FAILURE Feature Ready 사례가 모두 필요합니다.</p>}</section><section><h4>고상관 Feature 후보 · |r| ≥ 0.90</h4>{report.high_correlation_pairs.length ? <div className="drct-correlation-list">{report.high_correlation_pairs.map((row) => <span key={`${row.feature_a}-${row.feature_b}`}>{row.feature_a} ↔ {row.feature_b} <b>{row.correlation.toFixed(3)}</b></span>)}</div> : <p>표시할 후보가 없습니다.</p>}</section></div> : null}
    </div>
    {caseDetail ? <div className="drct-signal-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setCaseDetail(null); }}><section className="drct-signal-modal is-wide drct-training-case-modal" role="dialog" aria-modal="true" aria-label="학습 사례 상세"><header><div><h3>{caseDetail.stock_name} · {caseDetail.d0}</h3><p>{caseDetail.label} · {caseDetail.matched_marker_names.join(", ")} · Feature Schema v{caseDetail.feature_schema_version}</p></div><button type="button" aria-label="닫기" onClick={() => setCaseDetail(null)}><X size={19} /></button></header><div className="drct-training-case-detail">{caseContext ? <p className="drct-case-context">목록 포함 사유: {caseContext}</p> : null}<p>{caseDetail.outcome_notice}</p><section><h4>Rule 재검증 · {caseDetail.rule_status}</h4><pre>{JSON.stringify(caseDetail.rule_diagnostics, null, 2)}</pre></section><section><h4>CORE Feature · {caseDetail.core_status}</h4>{caseDetail.core_features ? <dl>{Object.entries(caseDetail.core_features).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value.toFixed(4)}</dd></div>)}</dl> : <p>부족: {caseDetail.core_missing.join(", ")}</p>}</section><section><h4>ENRICHED Feature · {caseDetail.enriched_status}</h4>{caseDetail.enriched_features ? <dl>{Object.entries(caseDetail.enriched_features).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value.toFixed(4)}</dd></div>)}</dl> : <p>부족: {caseDetail.enriched_missing.join(", ")}</p>}</section><section><h4>Future Outcome · 학습 입력에 사용하지 않음</h4><dl>{Object.entries(caseDetail.outcomes).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{num(value, "%")}</dd></div>)}</dl></section></div></section></div> : null}
  </section>;
}

export default TrainingResearchPanel;
