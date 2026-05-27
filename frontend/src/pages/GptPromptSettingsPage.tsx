import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { GptPromptTemplate } from "@/types/gptPromptTemplate";

const DOMAIN_TABS = [
  { key: "investment_advisory", label: "투자자문" },
  { key: "trade_review", label: "매매복기" },
  { key: "economic_briefing", label: "경제브리핑" },
  { key: "news_disclosure", label: "뉴스/공시" },
  { key: "common", label: "공통 설정" },
];

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

  const selected = useMemo(() => items.find((x) => x.prompt_key === selectedKey) ?? null, [items, selectedKey]);

  const load = async (domain: string) => {
    setLoading(true);
    setError("");
    try {
      const rows = await repositories.gptPromptTemplates.list(domain);
      setItems(rows);
      const firstKey = rows[0]?.prompt_key ?? "";
      setSelectedKey(firstKey);
      if (rows[0]) {
        setForm({
          prompt_name: rows[0].prompt_name,
          description: rows[0].description ?? "",
          prompt_text: rows[0].prompt_text,
          is_active: rows[0].is_active,
          sort_order: rows[0].sort_order,
        });
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
      setMessage(restored.message);
    } catch (e) {
      setError(e instanceof Error ? e.message : "기본값 복원 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="GPT 분석 프롬프트 설정" description="업무 영역별 프롬프트를 조회/수정하고 기본값으로 복원할 수 있습니다." />
      <SectionCard title="업무 영역">
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
      </SectionCard>
      <SectionCard title="프롬프트 관리">
        {loading ? <p className="text-muted">불러오는 중입니다.</p> : null}
        {error ? <p className="inline-result inline-error">{error}</p> : null}
        {message ? <p className="inline-result inline-success">{message}</p> : null}
        {items.length === 0 ? (
          <p className="empty-state">해당 업무 영역에 등록된 프롬프트가 없습니다.</p>
        ) : (
          <div className="gpt-prompt-layout">
            <div className="gpt-prompt-list">
              {items.map((item) => (
                <button key={item.prompt_key} type="button" className={`gpt-prompt-item ${selectedKey === item.prompt_key ? "active" : ""}`} onClick={() => selectItem(item)}>
                  <strong>{item.prompt_name}</strong>
                  <small>{item.prompt_key}</small>
                </button>
              ))}
            </div>
            {selected ? (
              <div className="gpt-prompt-editor">
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  <input className="input-control" value={form.prompt_name} onChange={(e) => setForm((p) => ({ ...p, prompt_name: e.target.value }))} placeholder="프롬프트명" />
                  <input className="input-control" value={selected.prompt_key} readOnly />
                  <input className="input-control" value={form.description} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} placeholder="설명" />
                  <select className="select-control" value={form.is_active} onChange={(e) => setForm((p) => ({ ...p, is_active: Number(e.target.value) }))}>
                    <option value={1}>사용</option>
                    <option value={0}>미사용</option>
                  </select>
                </div>
                <textarea className="textarea-control gpt-prompt-textarea" value={form.prompt_text} onChange={(e) => setForm((p) => ({ ...p, prompt_text: e.target.value }))} />
                <div className="gpt-prompt-actions">
                  <button type="button" className="btn btn-secondary" onClick={() => void restoreDefault()} disabled={saving}>기본값 복원</button>
                  <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={saving}>저장</button>
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
