import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, BarChart3, Check, ChevronRight, Database, Link2, Radar, RefreshCw, SearchX, X } from "lucide-react";

import { repositories } from "@/services";
import type { DrctRuleDiagnostic, DrctRuleMismatchSummary, DrctRulePreview, DrctSignalSearchDetail, DrctTrainingCase, DrctTrainingCaseDetail, DrctTrainingReadiness, DrctValidationOutcomeMetric, DrctValidationReport } from "@/types/drctStockSignal";

type WorkspaceTab = "detect" | "readiness" | "validation" | "cases";
type CaseCategory = "mismatch" | "incomplete" | "undecided" | "model";
type Props = { detail: DrctSignalSearchDetail; onManageMarkers: () => void; onError: (message: string | null) => void };
const errorText = (reason: unknown) => reason instanceof Error ? reason.message : "분석 데이터를 불러오지 못했습니다.";
const pct = (value: number | null) => value == null ? "-" : `${value.toFixed(1)}%`;
const valueText = (value: number | null) => value == null ? "-" : `${value.toFixed(2)}%`;
const koreanLabel = (value: string) => ({ SUCCESS: "성공", FAILURE: "실패", UNDECIDED: "미판정", CONFLICT: "판정 충돌" }[value] ?? value);
const resultLabel = (value: string) => value === "PASS" ? "충족" : value === "FAIL" ? "미충족" : "데이터 부족";

function SignalAnalysisWorkspace({ detail, onManageMarkers, onError }: Props) {
  const versionId = detail.current_version.id;
  const [tab, setTab] = useState<WorkspaceTab>("readiness");
  const [category, setCategory] = useState<CaseCategory>("mismatch");
  const [readiness, setReadiness] = useState<DrctTrainingReadiness | null>(null);
  const [report, setReport] = useState<DrctValidationReport | null>(null);
  const [mismatch, setMismatch] = useState<DrctRuleMismatchSummary | null>(null);
  const [selectedCondition, setSelectedCondition] = useState<string | null>(null);
  const [caseRows, setCaseRows] = useState<DrctTrainingCase[]>([]);
  const [caseDetail, setCaseDetail] = useState<DrctTrainingCaseDetail | null>(null);
  const [scan, setScan] = useState<DrctRulePreview | null>(null);
  const [diagnostic, setDiagnostic] = useState<DrctRuleDiagnostic | null>(null);
  const [busy, setBusy] = useState(false);
  const loadingKey = useRef<string | null>(null);

  const loadBase = useCallback(async (force = false) => {
    const requestKey = `${detail.id}:${versionId}`;
    if (!force && loadingKey.current === requestKey) return;
    loadingKey.current = requestKey;
    onError(null);
    try {
      const [ready, validation, mismatchResult] = await Promise.all([
        repositories.drctStockSignals.trainingReadiness(detail.id, versionId),
        repositories.drctStockSignals.validationReport(detail.id, versionId),
        repositories.drctStockSignals.ruleMismatchSummary(detail.id, versionId),
      ]);
      if (loadingKey.current === requestKey) { setReadiness(ready); setReport(validation); setMismatch(mismatchResult); }
    } catch (reason) { if (loadingKey.current === requestKey) onError(errorText(reason)); }
    finally { if (loadingKey.current === requestKey) loadingKey.current = null; }
  }, [detail.id, onError, versionId]);

  useEffect(() => { setTab("readiness"); setCategory("mismatch"); setSelectedCondition(null); setCaseRows([]); setScan(null); void loadBase(); }, [detail.id, versionId, loadBase]);
  const summary = readiness?.summary;
  const canDetect = detail.current_version.structured_rule?.validation_status === "VALID";
  const ruleMatch = summary?.rule_matched_count ?? 0;

  const refresh = async () => { setBusy(true); try { await repositories.drctStockSignals.previewTrainingDataset(detail.id, versionId); await loadBase(true); } catch (reason) { onError(errorText(reason)); } finally { setBusy(false); } };
  const detect = async () => { setBusy(true); onError(null); try { setScan(await repositories.drctStockSignals.previewRule(detail.id, null, false)); } catch (reason) { onError(errorText(reason)); } finally { setBusy(false); } };
  const diagnoseCurrent = async (stockId: number) => { if (!scan) return; setBusy(true); try { setDiagnostic(await repositories.drctStockSignals.diagnoseRule(detail.id, stockId, scan.analysis_date)); } catch (reason) { onError(errorText(reason)); } finally { setBusy(false); } };
  const openCase = async (item: DrctTrainingCase) => { setBusy(true); try { setCaseDetail(await repositories.drctStockSignals.trainingCaseDetail(detail.id, versionId, item.stock_id, item.d0)); } catch (reason) { onError(errorText(reason)); } finally { setBusy(false); } };
  const loadCases = useCallback(async (nextCategory: CaseCategory, conditionCode?: string | null) => {
    setBusy(true); onError(null);
    try {
      if (nextCategory === "mismatch") setCaseRows((await repositories.drctStockSignals.filteredTrainingCases(detail.id, versionId, "RULE_NO_MATCH", conditionCode || undefined)).items);
      else if (nextCategory === "incomplete") setCaseRows((await repositories.drctStockSignals.filteredTrainingCases(detail.id, versionId, "RULE_DATA_INCOMPLETE")).items);
      else if (nextCategory === "undecided") setCaseRows((await repositories.drctStockSignals.labeledTrainingCases(detail.id, versionId, "UNDECIDED")).items);
      else setCaseRows((report?.model_disagreement_cases ?? []).map((item) => ({ ...item, mfe_20: null, mae_20: null, failed_conditions: [] })));
    } catch (reason) { onError(errorText(reason)); } finally { setBusy(false); }
  }, [detail.id, onError, report?.model_disagreement_cases, versionId]);

  useEffect(() => { if (tab === "cases") void loadCases(category, selectedCondition); }, [tab, category, selectedCondition, loadCases]);
  const goMismatch = () => { setCategory("mismatch"); setSelectedCondition(null); setTab("cases"); };
  const outcome = (label: "success" | "failure", key: string) => report?.outcomes[label][key] as DrctValidationOutcomeMetric | undefined;

  return <section className="drct-analysis-workspace" aria-labelledby="drct-analysis-title">
    <header className="drct-analysis-header"><div><h3 id="drct-analysis-title">선택 검색식 분석 &amp; 학습</h3><p>현재 선택된 검색식의 탐지 결과와 성공패턴 학습 상태를 검증합니다.</p></div><button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void refresh()}><RefreshCw size={14} /> 데이터 새로고침</button></header>
    <nav className="drct-analysis-tabs" aria-label="선택 검색식 분석 메뉴">{([['detect','현재 탐지'],['readiness','학습 준비'],['validation','검증 결과'],['cases','사례 분석']] as const).map(([key,label]) => <button type="button" key={key} className={tab === key ? "is-active" : ""} onClick={() => setTab(key)}>{label}{key === "cases" && summary ? <span>{summary.rule_no_match_count + summary.rule_data_incomplete_count + summary.undecided_count}</span> : null}</button>)}</nav>

    {tab === "detect" ? <div className="drct-analysis-panel drct-detect-tab"><div className="drct-tab-title"><div><h4>현재 종목 탐지</h4><p>활성 국내 테마 연결 종목의 최신 공통 완료일을 기준으로 확인합니다.</p></div><button type="button" className="btn btn-primary" disabled={!canDetect || busy} onClick={() => void detect()}><Radar size={15} /> 현재 종목 탐지</button></div>
      {scan ? <><div className="drct-analysis-metrics">{[["기준일",scan.analysis_date],["테마 종목",scan.universe_count],["평가 가능",scan.evaluable_count],["검색식 포착",scan.matched_count],["데이터 부족",scan.data_incomplete_count]].map(([label,value]) => <article key={String(label)}><span>{label}</span><strong>{value}</strong></article>)}</div><p className="drct-analysis-note">검색식 포착 종목은 성공패턴 알고리즘 적용 전 1차 후보입니다.</p>{scan.items.length ? <div className="drct-detect-table"><table><thead><tr><th>종목</th><th>테마</th><th>기준일 종가</th><th>판정</th></tr></thead><tbody>{scan.items.map((item) => <tr key={item.stock_id} onClick={() => void diagnoseCurrent(item.stock_id)}><td><strong>{item.stock_name}</strong><small>{item.stock_code}</small></td><td>{item.theme_names.join(", ")}</td><td>{item.close?.toLocaleString() ?? "-"}</td><td>검색조건 충족</td></tr>)}</tbody></table></div> : <div className="drct-neutral-empty"><SearchX size={24} /><strong>현재 기준일에 이 검색조건을 만족한 종목이 없습니다.</strong><p>0건은 오류가 아니며 시장 상황에 따라 달라질 수 있습니다.</p></div>}</> : <div className="drct-neutral-empty"><Radar size={24} /><strong>현재 시장의 검색조건 충족 종목을 확인하세요.</strong><p>결과는 실행 시점에만 계산하며 저장하지 않습니다.</p></div>}
    </div> : null}

    {tab === "readiness" ? <div className="drct-analysis-panel"><div className="drct-learning-status"><div><span>학습 상태</span><strong>{ruleMatch === 0 && (summary?.rule_evaluable_count ?? 0) > 0 ? "검색조건 검토 필요" : summary?.blocking_reasons.length ? "준비 항목 확인 필요" : "학습 데이터 준비"}</strong><p>{ruleMatch === 0 && (summary?.rule_evaluable_count ?? 0) > 0 ? `과거 평가 가능 사례 ${summary?.rule_evaluable_count}건 중 현재 DrCT 검색조건과 일치한 사례가 없습니다.` : "학습 단계별 데이터 준비 상태를 확인합니다."}</p></div>{(summary?.rule_no_match_count ?? 0) > 0 ? <button type="button" className="btn btn-primary" onClick={goMismatch}><SearchX size={15} /> 불일치 원인 확인</button> : null}</div>
      <section className="drct-learning-markers"><div><h4>연결 차트마커 <span>{detail.marker_links.length}개</span></h4><p>성공패턴 학습 사례를 구성하는 차트마커입니다.</p></div><button type="button" className="btn btn-secondary" onClick={onManageMarkers}><Link2 size={14} /> 마커 연결 관리</button><div>{detail.marker_links.map((link) => <span key={link.id}>{link.marker_symbol} {link.marker_name}</span>)}</div></section>
      {report ? <div className="drct-simple-checklist">{[["검색식 준비",report.checklist.hts_reference_registered && report.checklist.rule_valid,"HTS · DrCT 검색조건"],["학습 사례",report.checklist.marker_linked && report.checklist.reviewed_case_exists,"마커 · 복기"],["데이터 검증",report.checklist.rule_match_exists && report.checklist.core_ready,"검색조건 일치 · Feature"]].map(([label,ready,desc]) => <article key={String(label)} className={ready ? "is-ready" : "is-pending"}><i>{ready ? <Check size={14} /> : <AlertCircle size={14} />}</i><div><strong>{label}</strong><span>{desc}</span></div></article>)}</div> : null}
      {summary ? <><div className="drct-simple-funnel">{[["마커",summary.marker_link_count],["연결 사례",summary.linked_event_count],["복기 완료",summary.reviewed_event_count],["평가 가능",summary.rule_evaluable_count],["검색조건 일치",summary.rule_matched_count],["Feature 준비",summary.core_ready_count]].map(([label,value],index) => <article key={String(label)}><span>{label}</span><strong>{value}</strong>{index < 5 ? <ChevronRight size={15} /> : null}</article>)}</div><div className="drct-progressive-coverage"><article><span>복기 Coverage</span><strong>{summary.linked_event_count ? pct(summary.reviewed_event_count / summary.linked_event_count * 100) : "-"}</strong><small>{summary.reviewed_event_count} / {summary.linked_event_count}</small></article><article className={ruleMatch === 0 ? "warning" : ""}><span>검색조건 일치</span><strong>{pct(summary.rule_match_rate)}</strong><small>{summary.rule_matched_count} / {summary.rule_evaluable_count}</small></article>{ruleMatch > 0 ? <><article><span>기본 Feature</span><strong>{summary.core_ready_count}</strong><small>준비 사례</small></article><article><span>확장 Feature</span><strong>{summary.enriched_ready_count}</strong><small>준비 사례</small></article></> : <p>검색조건 일치 사례가 생성되면 Feature 및 D+20 검증이 활성화됩니다.</p>}</div><div className="drct-learning-details"><span>검색조건 불일치 {summary.rule_no_match_count}</span><span>Rule 데이터 부족 {summary.rule_data_incomplete_count}</span><span>미판정 {summary.undecided_count}</span><span>Label 충돌 {summary.label_conflict_count}</span></div></> : <div className="drct-neutral-empty"><Database size={22} /><strong>학습 준비 상태를 계산하고 있습니다.</strong></div>}
    </div> : null}

    {tab === "validation" ? <div className="drct-analysis-panel">{ruleMatch === 0 ? <div className="drct-neutral-empty"><BarChart3 size={25} /><strong>검증 결과를 생성할 수 없습니다.</strong><p>검색조건과 일치한 학습 사례가 없습니다.</p><div><button type="button" className="btn btn-secondary" onClick={() => setTab("readiness")}>학습 준비로 이동</button><button type="button" className="btn btn-primary" onClick={goMismatch}>Rule 불일치 확인</button></div></div> : report ? <><div className="drct-tab-title"><div><h4>성과 검증 결과</h4><p>성공·실패 사례의 미래 성과와 기본모델 검증 상태입니다.</p></div></div><div className="drct-validation-summary"><span>성공 <strong>{report.labels.success_count}</strong></span><span>실패 <strong>{report.labels.failure_count}</strong></span><span>기본모델 <strong>{report.prototype.status === "READY" ? "검증 가능" : "사례 부족"}</strong></span><span>로지스틱 연구 <strong>{report.logistic.status === "READY" ? "검증 가능" : "사례 부족"}</strong></span></div><div className="drct-outcome-compact"><table><thead><tr><th>성과 구간</th><th>성공 사례</th><th>실패 사례</th><th>차이</th></tr></thead><tbody>{([['D+5','d5_return'],['D+10','d10_return'],['D+20','d20_return'],['MFE','mfe_20'],['MAE','mae_20']] as const).map(([label,key]) => <tr key={key}><th>{label}</th><td>{valueText(outcome("success",key)?.mean ?? null)}</td><td>{valueText(outcome("failure",key)?.mean ?? null)}</td><td>{valueText(report.outcomes.difference[key])}</td></tr>)}</tbody></table></div></> : null}</div> : null}

    {tab === "cases" ? <div className="drct-analysis-panel"><div className="drct-case-categories">{([['mismatch',`검색조건 불일치 ${summary?.rule_no_match_count ?? 0}`],['incomplete',`데이터 부족 ${summary?.rule_data_incomplete_count ?? 0}`],['undecided',`미판정 ${summary?.undecided_count ?? 0}`],['model',`모델 불일치 ${report?.model_disagreement_cases.length ?? 0}`]] as const).map(([key,label]) => <button type="button" key={key} disabled={key === "model" && !report?.model_disagreement_cases.length} className={category === key ? "is-active" : ""} onClick={() => { setCategory(key); setSelectedCondition(null); }}>{label}</button>)}</div>
      {category === "mismatch" && mismatch ? <><div className="drct-tab-title"><div><h4>검색조건 불일치 <span>{mismatch.case_count}건</span></h4><p>조건 실패 빈도이며, 단일 조건이 최종 실패의 유일한 원인이라는 의미는 아닙니다.</p></div></div><div className="drct-mismatch-grid"><section><h5>조건별 평가 현황</h5><div className="drct-mismatch-table"><table><thead><tr><th>조건</th><th>내용</th><th>충족</th><th>미충족</th><th>부족</th><th>실패율</th></tr></thead><tbody>{mismatch.conditions.map((item) => <tr key={item.code} className={selectedCondition === item.code ? "is-selected" : ""} onClick={() => setSelectedCondition(item.code)}><td><b>{item.code}</b></td><td>{item.label}</td><td>{item.pass_count}</td><td>{item.fail_count}</td><td>{item.incomplete_count}</td><td><strong>{pct(item.fail_rate)}</strong></td></tr>)}</tbody></table></div>{mismatch.branches.length ? <div className="drct-branch-summary"><h5>OR 조합 통과 현황</h5>{mismatch.branches.map((item) => <span key={item.expression}>{item.label} <strong>{item.pass_count} / {item.evaluated_count}</strong></span>)}</div> : null}</section><section><h5>{selectedCondition ? `${selectedCondition} 조건 실패 사례` : "전체 불일치 사례"} <span>{caseRows.length}건</span></h5><CaseTable rows={caseRows} onOpen={openCase} /></section></div></> : <><div className="drct-tab-title"><div><h4>{category === "incomplete" ? "Rule 데이터 부족" : category === "undecided" ? "미판정 사례" : "모델 불일치 사례"}</h4><p>{category === "incomplete" ? "실제 진단에 기록된 데이터 부족 사유를 확인합니다." : category === "undecided" ? "Marker D0가 명확한 추가 복기 대상입니다." : "기본모델이 준비된 경우에만 표시합니다."}</p></div></div><CaseTable rows={caseRows} onOpen={openCase} /></>}
    </div> : null}

    {diagnostic ? <DiagnosticModal title={`${diagnostic.stock_name} 현재 조건 진단`} subtitle={diagnostic.analysis_date} rows={diagnostic.conditions} onClose={() => setDiagnostic(null)} /> : null}
    {caseDetail ? <DiagnosticModal title={`${caseDetail.stock_name} · Marker D0 ${caseDetail.d0}`} subtitle={`${koreanLabel(caseDetail.label)} · ${caseDetail.matched_marker_names.join(", ")}`} rows={caseDetail.rule_diagnostics as Array<{code:string;label:string;status:string;actual_value:string;criteria:string}>} onClose={() => setCaseDetail(null)} /> : null}
  </section>;
}

function CaseTable({ rows, onOpen }: { rows: DrctTrainingCase[]; onOpen: (item: DrctTrainingCase) => void }) {
  if (!rows.length) return <div className="drct-neutral-empty compact"><Database size={20} /><strong>표시할 사례가 없습니다.</strong></div>;
  return <div className="drct-case-table"><table><thead><tr><th>종목</th><th>Marker D0</th><th>판정</th><th>마커</th><th>실패 조건</th><th></th></tr></thead><tbody>{rows.map((item) => <tr key={`${item.stock_id}-${item.d0}`} onClick={() => onOpen(item)}><td><strong>{item.stock_name}</strong><small>{item.stock_code}</small></td><td>{item.d0}</td><td>{koreanLabel(item.label)}</td><td>{item.matched_marker_names.join(", ")}</td><td>{item.failed_conditions?.map((row) => <span key={row.code} title={row.label}>{row.code}</span>)}</td><td>상세</td></tr>)}</tbody></table></div>;
}

function DiagnosticModal({ title, subtitle, rows, onClose }: { title: string; subtitle: string; rows: Array<{code:string;label:string;status:string;actual_value:string;criteria:string}>; onClose: () => void }) {
  return <div className="drct-signal-modal-backdrop" role="presentation"><section className="drct-signal-modal drct-rule-diagnostic-modal" role="dialog" aria-modal="true" aria-label="조건 진단"><header><div><h3>{title}</h3><p>{subtitle}</p></div><button type="button" aria-label="닫기" onClick={onClose}><X size={19} /></button></header><div className="drct-rule-diagnostic-list">{rows.map((row) => <article key={row.code}><span>{row.code}</span><div><strong>{row.label}</strong><small>실제 값 {row.actual_value || "-"}</small><small>기준 {row.criteria || "-"}</small></div><em className={`status-${row.status.toLowerCase()}`}>{resultLabel(row.status)}</em></article>)}</div><footer><p>Marker 사례는 표시된 D0 시점에서 재평가한 결과입니다.</p><button type="button" className="btn btn-primary" onClick={onClose}>확인</button></footer></section></div>;
}

export default SignalAnalysisWorkspace;
