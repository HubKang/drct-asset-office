import { useEffect, useMemo, useState } from "react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type {
  AnalysisConditionTemplate,
  AnalysisIndicator,
  AnalysisIndicatorAlias,
  AnalysisIndicatorCandidate,
  AnalysisLlmCatalog,
} from "@/types/analysisIndicator";

type TabKey = "indicators" | "aliases" | "templates" | "catalog" | "candidates";

const indicatorDefaults: Partial<AnalysisIndicator> = {
  indicator_key: "",
  indicator_name: "",
  source_type: "calculated",
  data_type: "number",
  category: "condition",
  allowed_operators_json: "[\">\", \">=\", \"<\", \"<=\", \"between\", \"=\", \"!=\"]",
  required_columns_json: "[]",
  is_available_for_rule: 1,
  is_available_for_llm: 1,
  is_entry_allowed: 1,
  is_success_allowed: 0,
  is_failure_allowed: 0,
  needs_review_default: 0,
  is_active: 1,
  sort_order: 0,
};

const aliasDefaults: Partial<AnalysisIndicatorAlias> = {
  alias_text: "",
  indicator_key: "",
  alias_type: "phrase",
  match_type: "contains",
  default_category: "entry_filter",
  apply_to_samples_default: 0,
  needs_review: 1,
  confidence: 0.8,
  is_active: 1,
  sort_order: 0,
};

const templateDefaults: Partial<AnalysisConditionTemplate> = {
  template_key: "",
  template_name: "",
  template_type: "entry_filter",
  condition_json: "{\n  \"conditions\": []\n}",
  default_apply_to_samples: 0,
  needs_review: 1,
  is_available_for_llm: 1,
  is_active: 1,
  sort_order: 0,
};

function boolText(value: unknown) {
  return Number(value || 0) ? "Y" : "N";
}

function compactText(value: unknown, maxLength = 60) {
  const text = value === null || value === undefined || value === "" ? "-" : String(value);
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function validateJson(value: string | null | undefined, label: string) {
  if (!value) return "";
  try {
    JSON.parse(value);
    return "";
  } catch {
    return `${label} JSON 형식을 확인해 주세요.`;
  }
}

function AnalysisIndicatorSettingsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("indicators");
  const [indicators, setIndicators] = useState<AnalysisIndicator[]>([]);
  const [aliases, setAliases] = useState<AnalysisIndicatorAlias[]>([]);
  const [templates, setTemplates] = useState<AnalysisConditionTemplate[]>([]);
  const [candidates, setCandidates] = useState<AnalysisIndicatorCandidate[]>([]);
  const [catalog, setCatalog] = useState<AnalysisLlmCatalog | null>(null);
  const [indicatorForm, setIndicatorForm] = useState<Partial<AnalysisIndicator>>(indicatorDefaults);
  const [aliasForm, setAliasForm] = useState<Partial<AnalysisIndicatorAlias>>(aliasDefaults);
  const [templateForm, setTemplateForm] = useState<Partial<AnalysisConditionTemplate>>(templateDefaults);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const catalogText = useMemo(() => JSON.stringify(catalog || {}, null, 2), [catalog]);

  const loadAll = async () => {
    setLoading(true);
    setError("");
    try {
      const [indicatorResult, aliasResult, templateResult, catalogResult, candidateResult] = await Promise.all([
        repositories.analysisIndicators.fetchIndicators({ active_only: false }),
        repositories.analysisIndicators.fetchAliases({ active_only: false }),
        repositories.analysisIndicators.fetchTemplates({ active_only: false }),
        repositories.analysisIndicators.fetchLlmCatalog(),
        repositories.analysisIndicators.fetchCandidates({ active_only: false }),
      ]);
      setIndicators(indicatorResult.items);
      setAliases(aliasResult.items);
      setTemplates(templateResult.items);
      setCatalog(catalogResult);
      setCandidates(candidateResult.items);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "매매연구 지표 설정을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAll();
  }, []);

  const saveEntity = async (
    id: number | undefined,
    createFn: () => Promise<unknown>,
    updateFn: (id: number) => Promise<unknown>,
    reset: () => void,
    successMessage: string,
  ) => {
    setLoading(true);
    setError("");
    try {
      if (id) await updateFn(id);
      else await createFn();
      reset();
      setMessage(successMessage);
      await loadAll();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const saveIndicator = async () => {
    const jsonError =
      validateJson(indicatorForm.required_columns_json, "required_columns_json") ||
      validateJson(indicatorForm.allowed_operators_json, "allowed_operators_json") ||
      validateJson(indicatorForm.default_value_json, "default_value_json");
    if (jsonError) {
      setError(jsonError);
      return;
    }
    await saveEntity(
      indicatorForm.id,
      () => repositories.analysisIndicators.createIndicator(indicatorForm),
      (id) => repositories.analysisIndicators.updateIndicator(id, indicatorForm),
      () => setIndicatorForm(indicatorDefaults),
      "지표 기준정보를 저장했습니다.",
    );
  };

  const saveAlias = async () => {
    const jsonError = validateJson(aliasForm.default_value_json, "default_value_json");
    if (jsonError) {
      setError(jsonError);
      return;
    }
    await saveEntity(
      aliasForm.id,
      () => repositories.analysisIndicators.createAlias(aliasForm),
      (id) => repositories.analysisIndicators.updateAlias(id, aliasForm),
      () => setAliasForm(aliasDefaults),
      "자연어 별칭을 저장했습니다.",
    );
  };

  const saveTemplate = async () => {
    const jsonError = validateJson(templateForm.condition_json, "condition_json");
    if (jsonError) {
      setError(jsonError);
      return;
    }
    await saveEntity(
      templateForm.id,
      () => repositories.analysisIndicators.createTemplate(templateForm),
      (id) => repositories.analysisIndicators.updateTemplate(id, templateForm),
      () => setTemplateForm(templateDefaults),
      "조건 템플릿을 저장했습니다.",
    );
  };

  const softDelete = async (kind: TabKey, id: number) => {
    setLoading(true);
    setError("");
    try {
      if (kind === "indicators") await repositories.analysisIndicators.deleteIndicator(id);
      if (kind === "aliases") await repositories.analysisIndicators.deleteAlias(id);
      if (kind === "templates") await repositories.analysisIndicators.deleteTemplate(id);
      setMessage("비활성화했습니다.");
      await loadAll();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "비활성화에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleCandidateAction = async (action: () => Promise<unknown>, successMessage: string) => {
    setLoading(true);
    setError("");
    try {
      await action();
      setMessage(successMessage);
      await loadAll();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "GPT 제안 후보 처리에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="analysis-indicator-page space-y-4">
      <PageHeader title="매매연구 지표 설정" description="매매목표 해석과 GPT/LLM catalog에 사용할 지표, 별칭, 템플릿, GPT 제안 후보를 관리합니다." />
      {message ? <div className="alert success">{message}</div> : null}
      {error ? <div className="alert danger">{error}</div> : null}
      <div className="analysis-indicator-tabs">
        {[
          ["indicators", "지표 기준정보"],
          ["aliases", "자연어 별칭"],
          ["templates", "조건 템플릿"],
          ["catalog", "LLM catalog 미리보기"],
          ["candidates", "GPT 제안 후보"],
        ].map(([key, label]) => (
          <button key={key} type="button" className={activeTab === key ? "active" : ""} onClick={() => setActiveTab(key as TabKey)}>{label}</button>
        ))}
        <button type="button" className="btn btn-secondary" disabled={loading} onClick={() => void loadAll()}>새로고침</button>
      </div>

      {activeTab === "indicators" ? (
        <SettingsLayout
          title="지표 기준정보"
          form={<IndicatorForm form={indicatorForm} setForm={setIndicatorForm} onSave={saveIndicator} onReset={() => setIndicatorForm(indicatorDefaults)} loading={loading} />}
          table={<IndicatorTable items={indicators} onEdit={setIndicatorForm} onDelete={(id) => void softDelete("indicators", id)} />}
        />
      ) : null}

      {activeTab === "aliases" ? (
        <SettingsLayout
          title="자연어 별칭"
          form={<AliasForm form={aliasForm} setForm={setAliasForm} onSave={saveAlias} onReset={() => setAliasForm(aliasDefaults)} loading={loading} />}
          table={<AliasTable items={aliases} onEdit={setAliasForm} onDelete={(id) => void softDelete("aliases", id)} />}
        />
      ) : null}

      {activeTab === "templates" ? (
        <SettingsLayout
          title="조건 템플릿"
          form={<TemplateForm form={templateForm} setForm={setTemplateForm} onSave={saveTemplate} onReset={() => setTemplateForm(templateDefaults)} loading={loading} />}
          table={<TemplateTable items={templates} onEdit={setTemplateForm} onDelete={(id) => void softDelete("templates", id)} />}
        />
      ) : null}

      {activeTab === "catalog" ? (
        <SectionCard title="LLM catalog 미리보기">
          <p className="analysis-indicator-help">LLM/GPT 목표 해석에서 참조할 active + LLM 사용 가능 지표/별칭/조건 템플릿입니다.</p>
          <textarea className="analysis-indicator-json-preview" readOnly value={catalogText} />
        </SectionCard>
      ) : null}

      {activeTab === "candidates" ? (
        <SectionCard title="GPT 제안 지표 후보">
          <CandidateTable
            items={candidates}
            loading={loading}
            onApprove={(id) => void handleCandidateAction(() => repositories.analysisIndicators.approveCandidateAsIndicator(id), "지표로 등록했습니다.")}
            onReference={(id) => void handleCandidateAction(() => repositories.analysisIndicators.approveCandidateReferenceOnly(id), "참고용으로 승인했습니다.")}
            onNeedsEngine={(id) => void handleCandidateAction(() => repositories.analysisIndicators.markCandidateNeedsEngine(id), "계산 엔진 필요로 표시했습니다.")}
            onReject={(id) => void handleCandidateAction(() => repositories.analysisIndicators.rejectCandidate(id), "제외 처리했습니다.")}
          />
        </SectionCard>
      ) : null}
    </div>
  );
}

function SettingsLayout({ title, form, table }: { title: string; form: JSX.Element; table: JSX.Element }) {
  return (
    <div className="analysis-indicator-layout">
      <SectionCard title={`${title} 등록/수정`}>{form}</SectionCard>
      <SectionCard title={`${title} 목록`}>{table}</SectionCard>
    </div>
  );
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: unknown; onChange: (value: any) => void; type?: string }) {
  return (
    <label className="analysis-indicator-field">
      <span>{label}</span>
      <input className="input-control" type={type} value={value === null || value === undefined ? "" : String(value)} onChange={(event) => onChange(type === "number" ? Number(event.target.value) : event.target.value)} />
    </label>
  );
}

function TextAreaField({ label, value, onChange }: { label: string; value: unknown; onChange: (value: string) => void }) {
  return (
    <label className="analysis-indicator-field wide">
      <span>{label}</span>
      <textarea value={value === null || value === undefined ? "" : String(value)} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function IndicatorForm({ form, setForm, onSave, onReset, loading }: { form: Partial<AnalysisIndicator>; setForm: (value: Partial<AnalysisIndicator>) => void; onSave: () => Promise<void>; onReset: () => void; loading: boolean }) {
  const set = (key: keyof AnalysisIndicator, value: any) => setForm({ ...form, [key]: value });
  return (
    <div className="analysis-indicator-form">
      <Field label="indicator_key" value={form.indicator_key} onChange={(value) => set("indicator_key", value)} />
      <Field label="indicator_name" value={form.indicator_name} onChange={(value) => set("indicator_name", value)} />
      <Field label="source_type" value={form.source_type} onChange={(value) => set("source_type", value)} />
      <Field label="category" value={form.category} onChange={(value) => set("category", value)} />
      <Field label="unit" value={form.unit} onChange={(value) => set("unit", value)} />
      <Field label="data_type" value={form.data_type} onChange={(value) => set("data_type", value)} />
      <Field label="default_operator" value={form.default_operator} onChange={(value) => set("default_operator", value)} />
      <Field label="sort_order" type="number" value={form.sort_order} onChange={(value) => set("sort_order", value)} />
      {(["is_available_for_rule", "is_available_for_llm", "is_entry_allowed", "is_success_allowed", "is_failure_allowed", "needs_review_default", "is_active"] as Array<keyof AnalysisIndicator>).map((key) => (
        <Field key={key} label={key} type="number" value={form[key]} onChange={(value) => set(key, value)} />
      ))}
      <TextAreaField label="description" value={form.description} onChange={(value) => set("description", value)} />
      <TextAreaField label="calculation_formula" value={form.calculation_formula} onChange={(value) => set("calculation_formula", value)} />
      <TextAreaField label="required_columns_json" value={form.required_columns_json} onChange={(value) => set("required_columns_json", value)} />
      <TextAreaField label="allowed_operators_json" value={form.allowed_operators_json} onChange={(value) => set("allowed_operators_json", value)} />
      <TextAreaField label="default_value_json" value={form.default_value_json} onChange={(value) => set("default_value_json", value)} />
      <TextAreaField label="example_expressions" value={form.example_expressions} onChange={(value) => set("example_expressions", value)} />
      <FormActions loading={loading} editing={Boolean(form.id)} onSave={onSave} onReset={onReset} />
    </div>
  );
}

function AliasForm({ form, setForm, onSave, onReset, loading }: { form: Partial<AnalysisIndicatorAlias>; setForm: (value: Partial<AnalysisIndicatorAlias>) => void; onSave: () => Promise<void>; onReset: () => void; loading: boolean }) {
  const set = (key: keyof AnalysisIndicatorAlias, value: any) => setForm({ ...form, [key]: value });
  return (
    <div className="analysis-indicator-form">
      <Field label="alias_text" value={form.alias_text} onChange={(value) => set("alias_text", value)} />
      <Field label="indicator_key" value={form.indicator_key} onChange={(value) => set("indicator_key", value)} />
      <Field label="default_category" value={form.default_category} onChange={(value) => set("default_category", value)} />
      <Field label="default_operator" value={form.default_operator} onChange={(value) => set("default_operator", value)} />
      <Field label="apply_to_samples_default" type="number" value={form.apply_to_samples_default} onChange={(value) => set("apply_to_samples_default", value)} />
      <Field label="needs_review" type="number" value={form.needs_review} onChange={(value) => set("needs_review", value)} />
      <Field label="confidence" type="number" value={form.confidence} onChange={(value) => set("confidence", value)} />
      <Field label="is_active" type="number" value={form.is_active} onChange={(value) => set("is_active", value)} />
      <TextAreaField label="default_value_json" value={form.default_value_json} onChange={(value) => set("default_value_json", value)} />
      <TextAreaField label="description" value={form.description} onChange={(value) => set("description", value)} />
      <FormActions loading={loading} editing={Boolean(form.id)} onSave={onSave} onReset={onReset} />
    </div>
  );
}

function TemplateForm({ form, setForm, onSave, onReset, loading }: { form: Partial<AnalysisConditionTemplate>; setForm: (value: Partial<AnalysisConditionTemplate>) => void; onSave: () => Promise<void>; onReset: () => void; loading: boolean }) {
  const set = (key: keyof AnalysisConditionTemplate, value: any) => setForm({ ...form, [key]: value });
  return (
    <div className="analysis-indicator-form">
      <Field label="template_key" value={form.template_key} onChange={(value) => set("template_key", value)} />
      <Field label="template_name" value={form.template_name} onChange={(value) => set("template_name", value)} />
      <Field label="template_type" value={form.template_type} onChange={(value) => set("template_type", value)} />
      <Field label="default_apply_to_samples" type="number" value={form.default_apply_to_samples} onChange={(value) => set("default_apply_to_samples", value)} />
      <Field label="needs_review" type="number" value={form.needs_review} onChange={(value) => set("needs_review", value)} />
      <Field label="is_available_for_llm" type="number" value={form.is_available_for_llm} onChange={(value) => set("is_available_for_llm", value)} />
      <Field label="is_active" type="number" value={form.is_active} onChange={(value) => set("is_active", value)} />
      <TextAreaField label="description" value={form.description} onChange={(value) => set("description", value)} />
      <TextAreaField label="condition_json" value={form.condition_json} onChange={(value) => set("condition_json", value)} />
      <FormActions loading={loading} editing={Boolean(form.id)} onSave={onSave} onReset={onReset} />
    </div>
  );
}

function FormActions({ loading, editing, onSave, onReset }: { loading: boolean; editing: boolean; onSave: () => Promise<void>; onReset: () => void }) {
  return (
    <div className="pattern-action-row">
      <button className="btn btn-primary" type="button" disabled={loading} onClick={() => void onSave()}>{editing ? "수정 저장" : "신규 등록"}</button>
      <button className="btn btn-secondary" type="button" disabled={loading} onClick={onReset}>입력 초기화</button>
    </div>
  );
}

function IndicatorTable({ items, onEdit, onDelete }: { items: AnalysisIndicator[]; onEdit: (item: AnalysisIndicator) => void; onDelete: (id: number) => void }) {
  if (!items.length) return <EmptyState message="등록된 지표 기준정보가 없습니다." />;
  return (
    <div className="table-shell analysis-indicator-table-shell">
      <table className="data-table compact-table">
        <thead><tr><th>지표키</th><th>지표명</th><th>유형</th><th>카테고리</th><th>Rule</th><th>LLM</th><th>진입</th><th>성공</th><th>실패</th><th>활성</th><th>처리</th></tr></thead>
        <tbody>{items.map((item) => (
          <tr key={item.id}>
            <td>{item.indicator_key}</td><td>{item.indicator_name}</td><td>{item.source_type}</td><td>{item.category}</td>
            <td>{boolText(item.is_available_for_rule)}</td><td>{boolText(item.is_available_for_llm)}</td><td>{boolText(item.is_entry_allowed)}</td><td>{boolText(item.is_success_allowed)}</td><td>{boolText(item.is_failure_allowed)}</td><td>{boolText(item.is_active)}</td>
            <td><RowActions onEdit={() => onEdit(item)} onDelete={() => onDelete(item.id)} /></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function AliasTable({ items, onEdit, onDelete }: { items: AnalysisIndicatorAlias[]; onEdit: (item: AnalysisIndicatorAlias) => void; onDelete: (id: number) => void }) {
  if (!items.length) return <EmptyState message="등록된 자연어 별칭이 없습니다." />;
  return (
    <div className="table-shell analysis-indicator-table-shell">
      <table className="data-table compact-table">
        <thead><tr><th>자연어 표현</th><th>연결 지표</th><th>기본 구분</th><th>기본 연산자</th><th>기본값</th><th>확인 필요</th><th>활성</th><th>처리</th></tr></thead>
        <tbody>{items.map((item) => (
          <tr key={item.id}>
            <td>{item.alias_text}</td><td>{item.indicator_key}</td><td>{item.default_category}</td><td>{item.default_operator || "-"}</td><td>{compactText(item.default_value_json)}</td><td>{boolText(item.needs_review)}</td><td>{boolText(item.is_active)}</td>
            <td><RowActions onEdit={() => onEdit(item)} onDelete={() => onDelete(item.id)} /></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function TemplateTable({ items, onEdit, onDelete }: { items: AnalysisConditionTemplate[]; onEdit: (item: AnalysisConditionTemplate) => void; onDelete: (id: number) => void }) {
  if (!items.length) return <EmptyState message="등록된 조건 템플릿이 없습니다." />;
  return (
    <div className="table-shell analysis-indicator-table-shell">
      <table className="data-table compact-table">
        <thead><tr><th>템플릿키</th><th>템플릿명</th><th>유형</th><th>샘플 기본 적용</th><th>확인 필요</th><th>LLM</th><th>활성</th><th>처리</th></tr></thead>
        <tbody>{items.map((item) => (
          <tr key={item.id}>
            <td>{item.template_key}</td><td>{item.template_name}</td><td>{item.template_type}</td><td>{boolText(item.default_apply_to_samples)}</td><td>{boolText(item.needs_review)}</td><td>{boolText(item.is_available_for_llm)}</td><td>{boolText(item.is_active)}</td>
            <td><RowActions onEdit={() => onEdit(item)} onDelete={() => onDelete(item.id)} /></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function CandidateTable({
  items,
  loading,
  onApprove,
  onReference,
  onNeedsEngine,
  onReject,
}: {
  items: AnalysisIndicatorCandidate[];
  loading: boolean;
  onApprove: (id: number) => void;
  onReference: (id: number) => void;
  onNeedsEngine: (id: number) => void;
  onReject: (id: number) => void;
}) {
  if (!items.length) return <EmptyState message="저장된 GPT 제안 지표 후보가 없습니다." />;
  return (
    <div className="table-shell analysis-indicator-table-shell">
      <table className="data-table compact-table">
        <thead><tr><th>원문</th><th>제안 지표키</th><th>제안 지표명</th><th>계산 유형</th><th>필요 지표</th><th>검증 상태</th><th>결정 상태</th><th>처리</th></tr></thead>
        <tbody>{items.map((item) => (
          <tr key={item.id}>
            <td>{compactText(item.source_text, 80)}</td>
            <td>{item.suggested_indicator_key}</td>
            <td>{item.suggested_indicator_name || "-"}</td>
            <td>{item.calculation_type || "-"}</td>
            <td>{compactText(item.required_indicators_json, 80)}</td>
            <td>{item.validation_status || "-"}<br /><small>{item.validation_message || ""}</small></td>
            <td>{item.decision_status || "pending"}</td>
            <td>
              <div className="analysis-indicator-row-actions">
                <button className="btn btn-secondary" type="button" disabled={loading} onClick={() => onApprove(item.id)}>지표 등록</button>
                <button className="btn btn-secondary" type="button" disabled={loading} onClick={() => onReference(item.id)}>참고 승인</button>
                <button className="btn btn-secondary" type="button" disabled={loading} onClick={() => onNeedsEngine(item.id)}>엔진 필요</button>
                <button className="btn btn-danger" type="button" disabled={loading} onClick={() => onReject(item.id)}>제외</button>
              </div>
            </td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function RowActions({ onEdit, onDelete }: { onEdit: () => void; onDelete: () => void }) {
  return (
    <div className="analysis-indicator-row-actions">
      <button type="button" className="btn btn-secondary" onClick={onEdit}>수정</button>
      <button type="button" className="btn btn-danger" onClick={onDelete}>비활성화</button>
    </div>
  );
}

export default AnalysisIndicatorSettingsPage;
