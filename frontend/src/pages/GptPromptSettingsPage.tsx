import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { GptPromptTemplate } from "@/types/gptPromptTemplate";

const DOMAIN_TABS = [
  { key: "investment_advisory", label: "투자자문" },
  { key: "trade_review", label: "매매일지 복기" },
  { key: "economic_briefing", label: "경제브리핑" },
  { key: "news_disclosure", label: "뉴스/공시" },
  { key: "common", label: "공통 설정" },
] as const;

const DOMAIN_HELP_TEXT: Record<string, string> = {
  investment_advisory: "관심종목 Data분석과 GPT 자문 패키지에서 사용하는 분석 프롬프트를 관리합니다.",
  trade_review: "매매일지, 매매일지 캘린더, 매매기법 화면에서 사용하는 복기/실패패턴 분석 프롬프트를 관리합니다.",
  economic_briefing: "경제 유튜브 영상을 요약하고 시장 흐름을 정리하는 프롬프트를 관리합니다.",
  news_disclosure: "뉴스, 공시, 텔레그램 메시지를 요약/분류하는 프롬프트를 관리합니다.",
  common: "모든 GPT 분석에 공통으로 적용되는 지침과 금지 표현을 관리합니다.",
};

const PROMPT_SURFACE_MAP: Record<string, string> = {
  stock_advisory_analysis: "관심종목 Data분석",
  trade_single_review: "매매일지",
  trade_monthly_review: "매매일지 캘린더",
  strategy_performance_review: "매매기법",
  failure_pattern_review: "매매일지 실패패턴 분석",
  economic_video_summary: "경제브리핑",
  news_item_summary: "뉴스관리",
  disclosure_item_summary: "공시관리",
  telegram_message_summary: "텔레그램 브리핑",
  common_analysis_policy: "모든 GPT 분석",
  common_output_format: "모든 GPT 분석",
  common_prohibited_expressions: "모든 GPT 분석",
  common_risk_policy: "모든 GPT 분석",
};

function getSurfaceLabel(promptKey: string): string {
  return PROMPT_SURFACE_MAP[promptKey] ?? "-";
}

function isCommonPrompt(item: GptPromptTemplate): boolean {
  const domain = String(item.domain || "").toLowerCase().trim();
  const key = String(item.prompt_key || "").toLowerCase().trim();
  return domain === "common" || domain === "common_settings" || key.startsWith("common_");
}

function filterByDomain(items: GptPromptTemplate[], domain: string): GptPromptTemplate[] {
  if (domain === "common") {
    return items.filter(isCommonPrompt);
  }
  return items.filter((item) => String(item.domain || "").toLowerCase() === domain.toLowerCase());
}

function getDomainLabel(domain: string, promptKey: string): string {
  if (promptKey.startsWith("common_") || domain === "common" || domain === "common_settings") {
    return "공통 설정";
  }
  return DOMAIN_TABS.find((d) => d.key === domain)?.label ?? domain;
}

function GptPromptSettingsPage() {
  const [activeDomain, setActiveDomain] = useState("trade_review");
  const [items, setItems] = useState<GptPromptTemplate[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [form, setForm] = useState({
    prompt_name: "",
    description: "",
    prompt_text: "",
    is_active: 1,
    sort_order: 0,
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const safeItems = Array.isArray(items) ? items : [];
  const selected = useMemo(() => safeItems.find((x) => x.prompt_key === selectedKey) ?? null, [safeItems, selectedKey]);

  const isDirty = useMemo(() => {
    if (!selected) return false;
    return (
      form.prompt_name !== selected.prompt_name ||
      form.description !== (selected.description ?? "") ||
      form.prompt_text !== selected.prompt_text ||
      form.is_active !== selected.is_active ||
      form.sort_order !== selected.sort_order
    );
  }, [form, selected]);

  const promptTextLength = form.prompt_text.length;

  const load = async (domain: string) => {
    setLoading(true);
    setError("");
    try {
      const rows = await repositories.gptPromptTemplates.list(domain === "common" ? undefined : domain);
      const normalizedRows = filterByDomain(Array.isArray(rows) ? rows : [], domain);
      setItems(normalizedRows);
      const first = normalizedRows[0];
      const firstKey = first?.prompt_key ?? "";
      setSelectedKey(firstKey);

      if (first) {
        setForm({
          prompt_name: first.prompt_name,
          description: first.description ?? "",
          prompt_text: first.prompt_text,
          is_active: first.is_active,
          sort_order: first.sort_order,
        });
      } else {
        setForm({ prompt_name: "", description: "", prompt_text: "", is_active: 1, sort_order: 0 });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "프롬프트 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(activeDomain);
  }, [activeDomain]);

  const selectItem = (item: GptPromptTemplate) => {
    setSelectedKey(item.prompt_key);
    setForm({
      prompt_name: item.prompt_name,
      description: item.description ?? "",
      prompt_text: item.prompt_text,
      is_active: item.is_active,
      sort_order: item.sort_order,
    });
    setMessage("");
    setError("");
  };

  const save = async () => {
    if (!selectedKey) return;
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const updated = await repositories.gptPromptTemplates.update(selectedKey, {
        prompt_name: form.prompt_name,
        description: form.description || null,
        prompt_text: form.prompt_text,
        is_active: form.is_active,
        sort_order: form.sort_order,
      });
      setItems((prev) => prev.map((row) => (row.prompt_key === selectedKey ? updated : row)));
      setMessage("저장되었습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const restoreDefault = async () => {
    if (!selectedKey) return;

    const confirmed = window.confirm(
      "기본값으로 복원하시겠습니까?\n현재 입력 중인 프롬프트 내용은 기본 템플릿으로 교체됩니다.",
    );
    if (!confirmed) return;

    setSaving(true);
    setMessage("");
    setError("");
    try {
      const restored = await repositories.gptPromptTemplates.restoreDefault(selectedKey);
      const updated = restored.template;
      setItems((prev) => prev.map((row) => (row.prompt_key === selectedKey ? updated : row)));
      setForm({
        prompt_name: updated.prompt_name,
        description: updated.description ?? "",
        prompt_text: updated.prompt_text,
        is_active: updated.is_active,
        sort_order: updated.sort_order,
      });
      setMessage("기본 프롬프트로 복원되었습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "기본값 복원 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const emptyHelpByDomain: Record<string, string> = {
    economic_briefing: "경제 영상 요약에 사용할 프롬프트가 아직 등록되지 않았습니다. 경제브리핑 요약 일관성을 위해 기본 프롬프트를 확인해 주세요.",
    news_disclosure: "뉴스, 공시, 텔레그램 메시지 요약/분류에 사용할 프롬프트가 아직 등록되지 않았습니다.",
    common:
      "모든 GPT 분석에 공통 적용할 정책 프롬프트가 아직 등록되지 않았습니다. 공통 분석 지침/출력 형식/금지 표현 정책을 등록해 주세요.",
  };

  const emptyMessage = emptyHelpByDomain[activeDomain] ??
    "이 영역에서 사용할 GPT 분석 기준이 아직 등록되지 않았습니다. 공통 설정과 기본 seed를 확인한 뒤 필요한 프롬프트를 추가해 주세요.";

  return (
    <div className="space-y-4">
      <PageHeader
        title="GPT 분석 프롬프트 설정"
        description="업무 영역별 프롬프트를 조회/수정하고 기본값으로 복원할 수 있습니다."
      />

      <SectionCard title="업무 영역">
        <div className="space-y-3">
          <div className="gpt-domain-tabs">
            {DOMAIN_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={`gpt-domain-tab ${activeDomain === tab.key ? "active" : ""}`}
                onClick={() => setActiveDomain(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <p className="text-muted gpt-domain-help">{DOMAIN_HELP_TEXT[activeDomain] ?? ""}</p>
        </div>
      </SectionCard>

      <SectionCard title="프롬프트 관리">
        {loading ? <p className="text-muted">불러오는 중입니다.</p> : null}
        {error ? <p className="inline-result inline-error">{error}</p> : null}
        {message ? <p className="inline-result inline-success">{message}</p> : null}

        {safeItems.length === 0 ? (
          <div className="empty-state">
            <p>해당 업무 영역에 등록된 프롬프트가 없습니다.</p>
            <p className="text-muted gpt-empty-help">{emptyMessage}</p>
          </div>
        ) : (
          <div className="gpt-prompt-layout">
            <div className="gpt-prompt-list">
              {safeItems.map((item) => (
                <button
                  key={item.prompt_key}
                  type="button"
                  className={`gpt-prompt-item ${selectedKey === item.prompt_key ? "active" : ""}`}
                  onClick={() => selectItem(item)}
                >
                  <strong>{item.prompt_name}</strong>
                  <small>{item.prompt_key}</small>
                  <div className="gpt-prompt-item-meta">
                    <StatusBadge label={item.is_active === 1 ? "사용" : "미사용"} tone={item.is_active === 1 ? "blue" : "slate"} />
                    <span className="gpt-prompt-surface">{getSurfaceLabel(item.prompt_key)}</span>
                  </div>
                </button>
              ))}
            </div>

            {selected ? (
              <div className="gpt-prompt-editor">
                <div className="gpt-prompt-meta-grid">
                  <div><span>업무 영역</span><strong>{getDomainLabel(selected.domain, selected.prompt_key)}</strong></div>
                  <div><span>적용 화면</span><strong>{getSurfaceLabel(selected.prompt_key)}</strong></div>
                  <div><span>프롬프트 key</span><strong>{selected.prompt_key}</strong></div>
                  <div><span>상태</span><strong>{form.is_active === 1 ? "사용" : "미사용"}</strong></div>
                </div>

                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  <input
                    className="input-control"
                    value={form.prompt_name}
                    onChange={(e) => setForm((p) => ({ ...p, prompt_name: e.target.value }))}
                    placeholder="프롬프트명"
                  />
                  <input className="input-control" value={selected.prompt_key} readOnly />
                  <input
                    className="input-control"
                    value={form.description}
                    onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                    placeholder="설명"
                  />
                  <select
                    className="select-control"
                    value={form.is_active}
                    onChange={(e) => setForm((p) => ({ ...p, is_active: Number(e.target.value) }))}
                  >
                    <option value={1}>사용</option>
                    <option value={0}>미사용</option>
                  </select>
                </div>

                <textarea
                  className="textarea-control gpt-prompt-textarea"
                  value={form.prompt_text}
                  onChange={(e) => setForm((p) => ({ ...p, prompt_text: e.target.value }))}
                />

                <div className="gpt-prompt-editor-status">
                  <span>글자 수: {promptTextLength.toLocaleString()}자</span>
                  <StatusBadge label={isDirty ? "변경사항 있음" : "최신 상태"} tone={isDirty ? "amber" : "slate"} />
                </div>

                <div className="gpt-prompt-actions">
                  <button type="button" className="btn btn-secondary" onClick={() => void restoreDefault()} disabled={saving}>
                    기본값 복원
                  </button>
                  <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={saving}>
                    저장
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </SectionCard>
    </div>
  );
}

export default GptPromptSettingsPage;
