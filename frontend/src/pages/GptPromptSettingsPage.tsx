import { useEffect, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { GptPromptTemplate } from "@/types/gptPromptTemplate";

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "string" && error.trim()) return error;
  return fallback;
}

function GptPromptSettingsPage() {
  const [items, setItems] = useState<GptPromptTemplate[]>([]);
  const [selectedKey, setSelectedKey] = useState("stock_advisory_analysis");
  const [promptName, setPromptName] = useState("");
  const [description, setDescription] = useState("");
  const [templateText, setTemplateText] = useState("");
  const [isActive, setIsActive] = useState(1);
  const [updatedAt, setUpdatedAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadDetail = async (promptKey: string) => {
    setLoading(true);
    setError("");
    try {
      const row = await repositories.gptPromptTemplates.get(promptKey);
      setPromptName(row.prompt_name);
      setDescription(row.description ?? "");
      setTemplateText(row.template_text);
      setIsActive(row.is_active);
      setUpdatedAt(row.updated_at);
    } catch (e) {
      setError(toErrorMessage(e, "프롬프트를 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  };

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await repositories.gptPromptTemplates.list();
      setItems(rows);
      const initialKey = rows.find((row) => row.prompt_key === selectedKey)?.prompt_key ?? rows[0]?.prompt_key ?? selectedKey;
      setSelectedKey(initialKey);
      await loadDetail(initialKey);
    } catch (e) {
      setError(toErrorMessage(e, "프롬프트 목록을 불러오지 못했습니다."));
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const onSave = async () => {
    setMessage("");
    setError("");
    if (!templateText.trim()) {
      setError("프롬프트 본문은 비워둘 수 없습니다.");
      return;
    }
    setSaving(true);
    try {
      const row = await repositories.gptPromptTemplates.update(selectedKey, {
        prompt_name: promptName.trim() || "GPT 주식 분석 프롬프트",
        description: description.trim() || null,
        template_text: templateText,
        is_active: isActive,
      });
      setUpdatedAt(row.updated_at);
      setMessage("GPT 분석 프롬프트가 저장되었습니다.");
      setItems((prev) => prev.map((item) => (item.prompt_key === row.prompt_key ? row : item)));
    } catch (e) {
      setError(toErrorMessage(e, "저장 중 오류가 발생했습니다."));
    } finally {
      setSaving(false);
    }
  };

  const onRestoreDefault = async () => {
    const confirmed = window.confirm("기본 프롬프트로 복원하시겠습니까? 현재 수정 내용은 덮어쓰기 됩니다.");
    if (!confirmed) return;
    setMessage("");
    setError("");
    setSaving(true);
    try {
      const result = await repositories.gptPromptTemplates.restoreDefault(selectedKey);
      setPromptName(result.template.prompt_name);
      setDescription(result.template.description ?? "");
      setTemplateText(result.template.template_text);
      setIsActive(result.template.is_active);
      setUpdatedAt(result.template.updated_at);
      setMessage("기본 프롬프트로 복원되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "복원 중 오류가 발생했습니다."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="GPT 분석 프롬프트 설정" description="가격·캔들관리 화면에서 GPT 분석 요청문+JSON 복사 시 사용되는 기본 프롬프트를 관리합니다." />
      <SectionCard title="운영 안내">
        <p className="text-sm text-slate-600">매수·매도 단정, 목표가, 상승 확률 문구는 사용하지 않는 것을 권장합니다.</p>
      </SectionCard>
      <SectionCard title="프롬프트 편집">
        {loading ? <p className="text-sm text-muted">불러오는 중입니다.</p> : null}
        {error ? <p className="text-sm text-rose-600">{error}</p> : null}
        {message ? <p className="text-sm text-emerald-600">{message}</p> : null}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="space-y-1">
            <span className="text-sm text-slate-600">프롬프트 선택</span>
            <select
              className="select-control"
              value={selectedKey}
              onChange={(e) => {
                const nextKey = e.target.value;
                setSelectedKey(nextKey);
                void loadDetail(nextKey);
              }}
            >
              {items.map((item) => (
                <option key={item.prompt_key} value={item.prompt_key}>
                  {item.prompt_name} ({item.prompt_key})
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-sm text-slate-600">마지막 수정일</span>
            <input className="input-control" value={updatedAt} readOnly />
          </label>
          <label className="space-y-1">
            <span className="text-sm text-slate-600">프롬프트 이름</span>
            <input className="input-control" value={promptName} onChange={(e) => setPromptName(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span className="text-sm text-slate-600">활성 여부</span>
            <select className="select-control" value={isActive} onChange={(e) => setIsActive(Number(e.target.value))}>
              <option value={1}>활성</option>
              <option value={0}>비활성</option>
            </select>
          </label>
        </div>
        <label className="mt-3 block space-y-1">
          <span className="text-sm text-slate-600">설명</span>
          <input className="input-control" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label className="mt-3 block space-y-1">
          <span className="text-sm text-slate-600">프롬프트 본문</span>
          <textarea
            className="textarea-control w-full"
            style={{ minHeight: "500px", fontFamily: "Consolas, Monaco, monospace" }}
            value={templateText}
            onChange={(e) => setTemplateText(e.target.value)}
          />
        </label>
        <div className="mt-3 flex gap-2">
          <button type="button" className="btn btn-primary" disabled={saving} onClick={() => void onSave()}>
            저장
          </button>
          <button type="button" className="btn btn-secondary" disabled={saving} onClick={() => void onRestoreDefault()}>
            기본값 복원
          </button>
        </div>
      </SectionCard>
    </div>
  );
}

export default GptPromptSettingsPage;
