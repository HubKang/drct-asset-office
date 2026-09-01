import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Sparkles, X } from "lucide-react";

import { repositories } from "@/services";
import type { DrctHtsImportPreview, DrctSignalSearchDetail } from "@/types/drctStockSignal";

type Props = { detail: DrctSignalSearchDetail; onVersionCreated: () => Promise<void> | void; onError: (message: string | null) => void };
const messageOf = (reason: unknown) => reason instanceof Error ? reason.message : "요청을 처리하지 못했습니다.";
const tone = (status: string) => status === "AUTO_CONVERTED" ? "ready" : status === "NEEDS_CONFIRMATION" ? "review" : "invalid";

function HtsRuleImportPanel({ detail, onVersionCreated, onError }: Props) {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState(detail.current_version.hts_reference_conditions);
  const [preview, setPreview] = useState<DrctHtsImportPreview | null>(null);
  const [resolutions, setResolutions] = useState<Record<string, Record<string, string | number>>>({});
  const [note, setNote] = useState("HTS 참조식 DrCT 자동 변환");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSource(detail.current_version.hts_reference_conditions);
    setPreview(null); setResolutions({});
  }, [detail.id, detail.current_version.id, detail.current_version.hts_reference_conditions]);

  const canDetect = detail.current_version.structured_rule?.validation_status === "VALID";
  const conditionCount = detail.current_version.structured_rule?.rule.conditions.length ?? 0;
  const analyze = async (next = resolutions) => {
    setBusy(true); onError(null);
    try { setPreview(await repositories.drctStockSignals.importHtsRule(source, detail.current_version.hts_condition_expression, next)); }
    catch (reason) { onError(messageOf(reason)); } finally { setBusy(false); }
  };
  const resolve = (code: string, key: string, value: string | number) => {
    const next = { ...resolutions, [code]: { ...(resolutions[code] ?? {}), [key]: value } };
    setResolutions(next); void analyze(next);
  };
  const save = async () => {
    if (!preview?.rule || preview.status !== "READY") return;
    setBusy(true); onError(null);
    try {
      const checked = await repositories.drctStockSignals.validateRule(preview.rule);
      if (checked.status !== "VALID") throw new Error(checked.errors[0]?.message || "완성된 조건을 다시 확인해 주세요.");
      await repositories.drctStockSignals.createRuleVersion(detail.id, preview.rule, note.trim() || "HTS 참조식 DrCT 자동 변환", source, preview.normalized_expression);
      setOpen(false); setPreview(null); setResolutions({}); await onVersionCreated();
    } catch (reason) { onError(messageOf(reason)); } finally { setBusy(false); }
  };

  return <article className="drct-rule-import-panel">
    <header><div><h4>DrCT 실행 조건</h4><p>HTS 참조식을 자동 변환하고 사람이 최종 확인합니다.</p></div><span className={canDetect ? "is-ready" : "is-draft"}>{canDetect ? "실행 가능" : "변환 필요"}</span></header>
    {canDetect ? <div className="drct-rule-human-summary"><CheckCircle2 size={19} /><div><strong>현재 v{detail.current_version.version_no} 실행 조건이 준비되었습니다.</strong><p>조건 {conditionCount}개 · 사용자 확인 완료 {conditionCount}개 · 미지원 0개</p></div><details><summary>기술 상세 보기</summary><pre>{JSON.stringify(detail.current_version.structured_rule?.rule, null, 2)}</pre></details></div> : <div className="drct-rule-human-summary muted"><AlertTriangle size={19} /><div><strong>아직 실행 조건이 없습니다.</strong><p>불완전한 항목만 직접 확인해 완성하세요.</p></div></div>}
    <button type="button" className="btn btn-primary drct-rule-import-button" onClick={() => { setOpen(true); void analyze(); }}><Sparkles size={16} /> {canDetect ? "조건 검토 · 다시 변환" : "HTS 참조식 자동 변환"}</button>

    {open ? <div className="drct-signal-modal-backdrop" role="presentation"><section className="drct-signal-modal is-wide drct-rule-import-modal" role="dialog" aria-modal="true" aria-label="HTS 검색식 자동 변환"><header><div><h3>HTS 검색식 자동 변환</h3><p>한국어로 검토하고 불완전한 항목만 직접 완성합니다.</p></div><button type="button" aria-label="닫기" disabled={busy} onClick={() => setOpen(false)}><X size={19} /></button></header><div className="drct-rule-import-body">
      <label className="drct-rule-source-input">HTS 참조 조건<textarea rows={10} value={source} onChange={(event) => { setSource(event.target.value); setPreview(null); }} /></label>
      <div className="drct-rule-expression"><strong>조건 조합</strong><span>{preview?.expression_korean || detail.current_version.hts_condition_expression.replace(/and/gi, "그리고").replace(/or/gi, "또는")}</span></div>
      <button type="button" className="btn btn-secondary" disabled={busy || !source.trim()} onClick={() => void analyze()}>{busy ? "분석 중" : "자동 변환 결과 새로고침"}</button>
      {preview ? <><div className={`drct-rule-import-status status-${preview.status.toLowerCase()}`}><strong>{preview.status_label}</strong><span>전체 {preview.summary.total} · 자동 완료 {preview.summary.auto_converted} · 확인 필요 {preview.summary.needs_confirmation} · 미지원 {preview.summary.unsupported}</span></div><div className="drct-rule-review-list">{preview.conditions.map((condition) => <article key={condition.code} className={`tone-${tone(condition.status)} ${condition.required ? "" : "is-unused"}`}><header><b>{condition.code}</b><div><strong>{condition.title}</strong><small>{condition.used_label}</small></div><span>{condition.status_label}</span></header><p>{condition.human_description}</p><details><summary>HTS 원문 보기</summary><pre>{condition.source_text || "원문 없음"}</pre></details>
        {condition.required && condition.resolution_kind === "RELATION" ? <label>관계 선택<select value={String(resolutions[condition.code]?.relation ?? "")} onChange={(event) => resolve(condition.code, "relation", event.target.value)}><option value="">선택해 주세요</option>{condition.resolution_options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label> : null}
        {condition.required && condition.resolution_kind === "PRICE_FIELD" ? <label>가격 종류 선택<select value={String(resolutions[condition.code]?.price_field ?? "")} onChange={(event) => resolve(condition.code, "price_field", event.target.value)}><option value="">선택해 주세요</option>{condition.resolution_options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label> : null}
        {condition.required && condition.resolution_kind === "THRESHOLD" ? <label>거래대금 기준(원)<input type="number" min={1} placeholder="예: 10000000000" value={String(resolutions[condition.code]?.threshold ?? "")} onBlur={(event) => event.target.value && resolve(condition.code, "threshold", Number(event.target.value))} onChange={(event) => setResolutions({ ...resolutions, [condition.code]: { ...(resolutions[condition.code] ?? {}), threshold: event.target.value } })} /></label> : null}
        {condition.issue ? <small className="drct-rule-issue">{condition.issue}</small> : null}</article>)}</div>{preview.rule ? <details className="drct-rule-tech"><summary>기술 상세 보기</summary><pre>{JSON.stringify(preview.rule, null, 2)}</pre></details> : null}</> : null}
    </div><footer><label>변경 메모<input value={note} onChange={(event) => setNote(event.target.value)} /></label><button type="button" className="btn btn-secondary" onClick={() => setOpen(false)}>취소</button><button type="button" className="btn btn-primary" disabled={busy || preview?.status !== "READY" || !preview.rule} onClick={() => void save()}>새 Version으로 저장</button></footer></section></div> : null}

  </article>;
}

export default HtsRuleImportPanel;
