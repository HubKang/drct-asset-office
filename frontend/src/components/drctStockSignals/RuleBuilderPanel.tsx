import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronRight, FlaskConical, Plus, Save, Settings2, X } from "lucide-react";

import { repositories } from "@/services";
import type { DrctRuleCondition, DrctRuleDiagnostic, DrctRulePreview, DrctRuleValidation, DrctSignalSearchDetail, DrctStructuredRule } from "@/types/drctStockSignal";

const TYPES = [
  "MARKET_CAP_COMPARE", "PRICE_COMPARE_VALUE", "PRICE_COMPARE_PRICE", "MA_COMPARE", "PRICE_MA_COMPARE", "MA_TREND",
  "CROSS_UP", "CROSS_DOWN", "PCT_CHANGE", "DISTANCE_PCT", "PERIOD_EXISTS_PRICE_CHANGE", "PERIOD_VALUE_COMPARE",
];
const OPS = ["GTE", "GT", "LTE", "LT", "EQ"];
const PRICE_FIELDS = ["OPEN", "HIGH", "LOW", "CLOSE"];
const MA_PERIODS = [5, 10, 20, 60, 120, 240];
const EMPTY_RULE: DrctStructuredRule = { schema_version: 1, conditions: [], expression: "" };

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "요청을 처리하지 못했습니다.";
}

function defaultParams(type: string): Record<string, unknown> {
  if (type === "MARKET_CAP_COMPARE") return { operator: "GTE", value: 200000000000 };
  if (type === "PRICE_COMPARE_VALUE") return { price_field: "CLOSE", offset: 0, operator: "GTE", value: 1000 };
  if (type === "MA_COMPARE") return { lhs_period: 20, lhs_offset: 0, rhs_period: 60, rhs_offset: 0, operator: "GT" };
  if (type === "PRICE_MA_COMPARE") return { price_field: "CLOSE", price_offset: 0, ma_period: 20, ma_offset: 0, operator: "GT" };
  if (type === "MA_TREND") return { ma_period: 60, direction: "UP", count: 2, offset: 0 };
  if (type === "PERIOD_EXISTS_PRICE_CHANGE") return { price_field: "CLOSE", lookback: 20, operator: "GTE", value: 10 };
  if (type === "PERIOD_VALUE_COMPARE") return { value_field: "TRADING_VALUE", lookback: 20, operator: "GTE", value: 1000000000 };
  return { lhs: { kind: "PRICE", field: "CLOSE", offset: 1 }, rhs: { kind: type === "PRICE_COMPARE_PRICE" || type === "PCT_CHANGE" ? "PRICE" : "MA", field: "CLOSE", period: 20, offset: 0 }, ...(type === "PCT_CHANGE" || type === "DISTANCE_PCT" ? { operator: "GTE", value: 5 } : type === "PRICE_COMPARE_PRICE" ? { operator: "GT" } : {}) };
}

function ParamFields({ condition, update }: { condition: DrctRuleCondition; update: (params: Record<string, unknown>) => void }) {
  const p = condition.params;
  const set = (key: string, value: unknown) => update({ ...p, [key]: value });
  const number = (key: string, label: string, min = 0) => <label>{label}<input type="number" min={min} value={Number(p[key] ?? 0)} onChange={(e) => set(key, Number(e.target.value))} /></label>;
  const operator = () => <label>연산자<select value={String(p.operator ?? "GTE")} onChange={(e) => set("operator", e.target.value)}>{OPS.map((item) => <option key={item}>{item}</option>)}</select></label>;
  const price = (key = "price_field") => <label>가격<select value={String(p[key] ?? "CLOSE")} onChange={(e) => set(key, e.target.value)}>{PRICE_FIELDS.map((item) => <option key={item}>{item}</option>)}</select></label>;
  const ma = (key: string, label: string) => <label>{label}<select value={Number(p[key] ?? 20)} onChange={(e) => set(key, Number(e.target.value))}>{MA_PERIODS.map((item) => <option key={item} value={item}>MA{item}</option>)}</select></label>;
  if (condition.type === "MARKET_CAP_COMPARE") return <>{operator()}{number("value", "시장가치(원)")}</>;
  if (condition.type === "PRICE_COMPARE_VALUE") return <>{price()}{number("offset", "봉전")}{operator()}{number("value", "기준값")}</>;
  if (condition.type === "MA_COMPARE") return <>{ma("lhs_period", "왼쪽 MA")}{number("lhs_offset", "왼쪽 봉전")}{operator()}{ma("rhs_period", "오른쪽 MA")}{number("rhs_offset", "오른쪽 봉전")}</>;
  if (condition.type === "PRICE_MA_COMPARE") return <>{price()}{number("price_offset", "가격 봉전")}{operator()}{ma("ma_period", "MA")}{number("ma_offset", "MA 봉전")}</>;
  if (condition.type === "MA_TREND") return <>{ma("ma_period", "MA")}<label>방향<select value={String(p.direction ?? "UP")} onChange={(e) => set("direction", e.target.value)}><option value="UP">상승</option><option value="DOWN">하락</option></select></label>{number("count", "지속 횟수", 1)}{number("offset", "시작 봉전")}</>;
  if (condition.type === "PERIOD_EXISTS_PRICE_CHANGE") return <>{price()}{number("lookback", "최근 N봉", 1)}{operator()}{number("value", "변화율(%)")}</>;
  if (condition.type === "PERIOD_VALUE_COMPARE") return <><label>값<select value={String(p.value_field ?? "TRADING_VALUE")} onChange={(e) => set("value_field", e.target.value)}><option value="TRADING_VALUE">거래대금</option><option value="VOLUME">거래량</option></select></label>{number("lookback", "최근 N봉", 1)}{operator()}{number("value", "기준값")}</>;
  const operand = (key: "lhs" | "rhs", label: string) => {
    const value = (p[key] as Record<string, unknown>) ?? {};
    const updateOperand = (field: string, next: unknown) => set(key, { ...value, [field]: next });
    return <fieldset><legend>{label}</legend><select value={String(value.kind ?? "PRICE")} onChange={(e) => updateOperand("kind", e.target.value)}><option value="PRICE">가격</option><option value="MA">이동평균</option></select>{value.kind === "MA" ? <select value={Number(value.period ?? 20)} onChange={(e) => updateOperand("period", Number(e.target.value))}>{MA_PERIODS.map((item) => <option key={item} value={item}>MA{item}</option>)}</select> : <select value={String(value.field ?? "CLOSE")} onChange={(e) => updateOperand("field", e.target.value)}>{PRICE_FIELDS.map((item) => <option key={item}>{item}</option>)}</select>}<input aria-label={`${label} 봉전`} type="number" min={0} value={Number(value.offset ?? 0)} onChange={(e) => updateOperand("offset", Number(e.target.value))} /></fieldset>;
  };
  return <>{operand("lhs", "왼쪽")}{condition.type === "PRICE_COMPARE_PRICE" ? operator() : null}{operand("rhs", "오른쪽")}{condition.type === "PCT_CHANGE" || condition.type === "DISTANCE_PCT" ? <>{operator()}{number("value", "기준(%)")}</> : null}</>;
}

export default function RuleBuilderPanel({ detail, onVersionCreated, onError }: { detail: DrctSignalSearchDetail; onVersionCreated: () => Promise<void>; onError: (message: string) => void }) {
  const existing = detail.current_version.structured_rule;
  const [editing, setEditing] = useState(false);
  const [rule, setRule] = useState<DrctStructuredRule>(existing?.rule ?? EMPTY_RULE);
  const [validation, setValidation] = useState<DrctRuleValidation | null>(existing ? { status: existing.validation_status, errors: existing.validation_errors, required_lookback: existing.required_lookback } : null);
  const [changeNote, setChangeNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [analysisDate, setAnalysisDate] = useState("");
  const [includeAll, setIncludeAll] = useState(false);
  const [preview, setPreview] = useState<DrctRulePreview | null>(null);
  const [diagnostic, setDiagnostic] = useState<DrctRuleDiagnostic | null>(null);

  useEffect(() => { setEditing(false); setRule(existing?.rule ?? EMPTY_RULE); setValidation(existing ? { status: existing.validation_status, errors: existing.validation_errors, required_lookback: existing.required_lookback } : null); setPreview(null); }, [detail.current_version.id]);
  useEffect(() => {
    if (!editing) return;
    const timer = window.setTimeout(() => repositories.drctStockSignals.validateRule(rule).then(setValidation).catch((reason) => onError(errorMessage(reason))), 250);
    return () => window.clearTimeout(timer);
  }, [rule, editing, onError]);

  const status = validation?.status ?? (existing ? existing.validation_status : "DRAFT");
  const nextCode = useMemo(() => {
    const used = new Set(rule.conditions.map((item) => item.code));
    for (let index = 0; index < 26; index += 1) { const code = String.fromCharCode(65 + index); if (!used.has(code)) return code; }
    return `C${rule.conditions.length + 1}`;
  }, [rule.conditions]);
  const addCondition = () => { const condition: DrctRuleCondition = { code: nextCode, type: "PRICE_COMPARE_VALUE", label: "종가 기준", configured: true, params: defaultParams("PRICE_COMPARE_VALUE") }; setRule((current) => ({ ...current, conditions: [...current.conditions, condition], expression: current.expression ? `${current.expression} AND ${nextCode}` : nextCode })); };
  const updateCondition = (index: number, next: DrctRuleCondition) => setRule((current) => ({ ...current, conditions: current.conditions.map((item, itemIndex) => itemIndex === index ? next : item) }));
  const removeCondition = (index: number) => { const code = rule.conditions[index].code; if (new RegExp(`\\b${code}\\b`, "i").test(rule.expression) && !window.confirm(`조건 ${code}가 조건 조합에서 사용 중입니다. 삭제할까요?`)) return; setRule((current) => ({ ...current, conditions: current.conditions.filter((_, itemIndex) => itemIndex !== index) })); };
  const save = async () => { if (!changeNote.trim()) { onError("변경 메모를 입력해 주세요."); return; } setSaving(true); try { await repositories.drctStockSignals.createRuleVersion(detail.id, rule, changeNote); setChangeNote(""); setEditing(false); await onVersionCreated(); } catch (reason) { onError(errorMessage(reason)); } finally { setSaving(false); } };
  const runPreview = async () => { setPreviewing(true); try { const result = await repositories.drctStockSignals.previewRule(detail.id, analysisDate || null, includeAll); setPreview(result); if (!analysisDate) setAnalysisDate(result.analysis_date); } catch (reason) { onError(errorMessage(reason)); } finally { setPreviewing(false); } };
  const diagnose = async (item: DrctRulePreview["items"][number]) => { if (!preview) return; try { setDiagnostic(await repositories.drctStockSignals.diagnoseRule(detail.id, item.stock_id, preview.analysis_date)); } catch (reason) { onError(errorMessage(reason)); } };

  return <section className="drct-rule-workspace">
    <header className="drct-rule-head"><div><h4>DrCT 실행식</h4><p>HTS 문자열을 자동 해석하지 않고 Structured Rule을 직접 구성합니다.</p></div><div><span className={`drct-rule-status ${status.toLowerCase()}`}>{status === "VALID" ? "검증완료" : status === "INVALID" ? "오류" : existing ? "작성중" : "미구성"}</span><button type="button" className="btn btn-secondary" onClick={() => setEditing(true)}><Settings2 size={14} /> {existing ? "새 Version으로 수정" : "실행식 구성"}</button></div></header>
    {!editing ? existing ? <div className="drct-rule-readonly"><div className="drct-rule-condition-list">{existing.rule.conditions.map((condition) => <article key={condition.code}><b>{condition.code}</b><div><strong>{condition.label || condition.type}</strong><small>{condition.type}</small></div></article>)}</div><pre>{existing.rule.expression}</pre></div> : <div className="drct-signal-unconfigured">현재 v{detail.current_version_no}에는 Structured Rule이 없습니다. 실행식 구성 시 새 Version이 생성됩니다.</div> : <div className="drct-rule-builder">
      <div className="drct-rule-condition-list">{rule.conditions.map((condition, index) => <article key={`${condition.code}-${index}`}><div className="drct-rule-code"><input aria-label="조건 코드" maxLength={20} value={condition.code} onChange={(e) => updateCondition(index, { ...condition, code: e.target.value.toUpperCase() })} /></div><div className="drct-rule-condition-body"><div className="drct-rule-condition-title"><input aria-label="조건 이름" placeholder="조건 이름" value={condition.label ?? ""} onChange={(e) => updateCondition(index, { ...condition, label: e.target.value })} /><select aria-label="조건 유형" value={condition.type} onChange={(e) => updateCondition(index, { ...condition, type: e.target.value, params: defaultParams(e.target.value) })}>{TYPES.map((type) => <option key={type}>{type}</option>)}</select><button type="button" onClick={() => removeCondition(index)}>삭제</button></div><div className="drct-rule-fields"><ParamFields condition={condition} update={(params) => updateCondition(index, { ...condition, params })} /></div></div></article>)}</div>
      <button type="button" className="btn btn-secondary" onClick={addCondition}><Plus size={14} /> 조건 추가</button>
      <label className="drct-rule-expression">조건 조합<textarea rows={4} placeholder="A AND B AND (C OR D)" value={rule.expression} onChange={(e) => setRule({ ...rule, expression: e.target.value.toUpperCase() })} /></label>
      <div className={`drct-rule-validation ${status.toLowerCase()}`}>{status === "VALID" ? <><CheckCircle2 size={18} /><div><strong>검증 완료</strong><p>필요 Lookback: {validation?.required_lookback ?? 0}거래봉</p></div></> : <><AlertTriangle size={18} /><div><strong>{status === "DRAFT" ? "Rule 작성 중" : "Rule 오류"}</strong>{validation?.errors.map((item, index) => <p key={`${item.code}-${index}`}>{item.message}</p>)}</div></>}</div>
      <label className="drct-rule-change-note">변경 메모 *<input value={changeNote} onChange={(e) => setChangeNote(e.target.value)} placeholder="Rule 구성 근거를 기록하세요." /></label><div className="drct-rule-builder-actions"><button type="button" className="btn btn-secondary" onClick={() => { setEditing(false); setRule(existing?.rule ?? EMPTY_RULE); }}>취소</button><button type="button" className="btn btn-primary" disabled={saving} onClick={() => void save()}><Save size={14} /> v{detail.current_version_no + 1} 저장</button></div>
    </div>}
    <section className="drct-rule-preview"><header><div><h4>Rule Preview</h4><p>활성 국내 테마 연결 종목을 Runtime으로 검사하며 결과는 저장하지 않습니다.</p></div><div><input aria-label="분석 기준일" type="date" value={analysisDate} onChange={(e) => setAnalysisDate(e.target.value)} /><label><input type="checkbox" checked={includeAll} onChange={(e) => setIncludeAll(e.target.checked)} /> 전체 판정 보기</label><button type="button" className="btn btn-primary" disabled={status !== "VALID" || editing || previewing} onClick={() => void runPreview()}><FlaskConical size={14} /> {previewing ? "검사 중" : "검색식 테스트"}</button></div></header>{status !== "VALID" ? <p className="drct-rule-preview-blocked">검증 완료된 현재 Version에서만 검색식 테스트를 실행할 수 있습니다.</p> : null}{preview ? <><div className="drct-rule-summary"><div><span>분석 기준일</span><strong>{preview.analysis_date}</strong></div><div><span>대상 종목</span><strong>{preview.universe_count}</strong></div><div><span>평가 가능</span><strong>{preview.evaluable_count}</strong></div><div className="incomplete"><span>데이터 부족</span><strong>{preview.data_incomplete_count}</strong></div><div className="match"><span>조건 만족</span><strong>{preview.matched_count}</strong></div></div><p className="drct-rule-runtime">Runtime {preview.elapsed_ms.toLocaleString()}ms · Preview 결과 비저장</p><div className="drct-rule-results"><table><thead><tr><th>종목</th><th>코드</th><th>연결 테마</th><th>종가</th><th>판정</th><th /></tr></thead><tbody>{preview.items.map((item) => <tr key={item.stock_id}><td>{item.stock_name}</td><td>{item.stock_code}</td><td>{item.theme_names.join(" · ")}</td><td>{item.close?.toLocaleString() ?? "-"}</td><td><span className={item.status.toLowerCase()}>{item.status}</span></td><td><button type="button" aria-label={`${item.stock_name} 진단`} onClick={() => void diagnose(item)}><ChevronRight size={15} /></button></td></tr>)}</tbody></table>{preview.items.length === 0 ? <p>표시할 판정 종목이 없습니다.</p> : null}</div></> : null}</section>
    {diagnostic ? <div className="drct-signal-modal-backdrop"><section className="drct-signal-modal is-wide drct-rule-diagnostic" role="dialog" aria-modal="true" aria-label="종목 Rule 진단"><header><div><h3>{diagnostic.stock_name} Rule 진단</h3><p>{diagnostic.stock_code} · {diagnostic.analysis_date} · {diagnostic.theme_names.join(" · ")}</p></div><button type="button" aria-label="닫기" onClick={() => setDiagnostic(null)}><X size={19} /></button></header><div className="drct-rule-diagnostic-list">{diagnostic.conditions.map((condition) => <article key={condition.code}><b>{condition.code}</b><div><strong>{condition.label}</strong><span>{condition.criteria}</span><small>실제값 {condition.actual_value}</small></div><em className={condition.status.toLowerCase()}>{condition.status}</em></article>)}</div></section></div> : null}
  </section>;
}
