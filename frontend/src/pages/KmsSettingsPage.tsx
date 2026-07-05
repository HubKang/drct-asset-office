import { useEffect, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import { repositories } from "@/services";
import type { KmsCategory, KmsCategoryPayload } from "@/types/kms";

type SettingsTab = "categories" | "tags" | "templates" | "relations";

const emptyCategoryForm: KmsCategoryPayload = {
  parent_id: null,
  name: "",
  description: "",
  sort_order: 100,
  is_active: true,
};

const SETTINGS_TABS: Array<{ key: SettingsTab; label: string; help: string }> = [
  { key: "categories", label: "카테고리", help: "KMS 분류 트리와 표시 순서를 관리합니다." },
  { key: "tags", label: "태그관리", help: "태그 정리 기능은 다음 단계에서 제공됩니다." },
  { key: "templates", label: "템플릿", help: "지식 템플릿 기능은 다음 단계에서 제공됩니다." },
  { key: "relations", label: "관계설정", help: "관련 지식 연결 기능은 다음 단계에서 제공됩니다." },
];

function KmsSettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("categories");
  const [categories, setCategories] = useState<KmsCategory[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<KmsCategoryPayload>(emptyCategoryForm);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setMessage("");
    try {
      const rows = await repositories.kms.listCategories(true);
      setCategories(rows);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 목록을 불러오지 못했습니다.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const selectCategory = (category: KmsCategory) => {
    setSelectedId(category.id);
    setForm({
      parent_id: category.parent_id,
      name: category.name,
      description: category.description || "",
      sort_order: category.sort_order,
      is_active: category.is_active,
    });
  };

  const resetForm = () => {
    setSelectedId(null);
    setForm(emptyCategoryForm);
  };

  const save = async () => {
    if (!form.name.trim()) {
      setMessage("카테고리명은 필수입니다.");
      return;
    }
    if (!Number.isFinite(Number(form.sort_order))) {
      setMessage("표시 순서는 숫자로 입력해 주세요.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      if (selectedId) {
        await repositories.kms.updateCategory(selectedId, { ...form, name: form.name.trim() });
        setMessage("카테고리가 수정되었습니다.");
      } else {
        await repositories.kms.createCategory({ ...form, name: form.name.trim() });
        setMessage("카테고리가 등록되었습니다.");
      }
      resetForm();
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const deactivate = async (categoryId: number) => {
    if (!window.confirm("카테고리를 비활성화하시겠습니까? 실제 삭제는 수행하지 않습니다.")) return;
    setSaving(true);
    try {
      await repositories.kms.deactivateCategory(categoryId);
      if (selectedId === categoryId) resetForm();
      await load();
      setMessage("카테고리가 비활성화되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 비활성화에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const activeTabInfo = SETTINGS_TABS.find((tab) => tab.key === activeTab) ?? SETTINGS_TABS[0];

  return (
    <div className="space-y-4">
      <PageHeader title="KMS 설정" description="KMS 카테고리, 태그, 템플릿, 관계 설정을 단계적으로 관리합니다." />

      {message ? <div className="alert alert-warning">{message}</div> : null}

      <div className="kms-tabs" role="tablist" aria-label="KMS 설정 탭">
        {SETTINGS_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.key}
            className={`kms-tab ${activeTab === tab.key ? "active" : ""}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab !== "categories" ? (
        <section className="kms-panel">
          <div className="kms-empty-state">
            <strong>{activeTabInfo.label}</strong>
            <span>{activeTabInfo.help}</span>
          </div>
        </section>
      ) : (
        <section className="kms-panel kms-settings-panel">
          <div className="kms-panel-header">
            <div>
              <h2 className="kms-panel-title">카테고리 관리</h2>
              <p className="kms-panel-description">대분류와 하위분류를 관리하고 표시 순서를 조정합니다.</p>
            </div>
          </div>
          <div className="kms-settings-layout">
            <div className="kms-category-list-panel">
              <div className="kms-panel-subtitle-row">
                <strong>카테고리 목록</strong>
                <span>{categories.length.toLocaleString("ko-KR")}개</span>
              </div>
              <div className="kms-category-admin-list">
                {categories.map((category) => (
                  <button
                    key={category.id}
                    type="button"
                    className={`kms-category-list-item ${selectedId === category.id ? "active" : ""} ${!category.is_active ? "inactive" : ""}`}
                    onClick={() => selectCategory(category)}
                  >
                    <strong>{category.name}</strong>
                    <span>{category.parent_id ? "하위분류" : "대분류"} · 순서 {category.sort_order}</span>
                    <span className={`kms-mini-badge ${category.is_active ? "active" : "inactive"}`}>{category.is_active ? "활성" : "비활성"}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="kms-form-panel-inner">
              <div className="kms-panel-subtitle-row">
                <strong>{selectedId ? "카테고리 수정" : "카테고리 등록"}</strong>
                <button type="button" className="btn btn-secondary btn-table-sm" onClick={resetForm}>신규 입력</button>
              </div>
              {!selectedId ? (
                <div className="kms-form-guide">왼쪽에서 수정할 카테고리를 선택하거나 신규 입력 상태에서 새 카테고리를 등록하세요.</div>
              ) : null}
              <div className="kms-form-grid single">
                <label>
                  <span>카테고리명 *</span>
                  <input className="input" value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
                </label>
                <label>
                  <span>상위 카테고리</span>
                  <select
                    className="select"
                    value={form.parent_id ?? ""}
                    onChange={(event) => setForm((prev) => ({ ...prev, parent_id: event.target.value ? Number(event.target.value) : null }))}
                  >
                    <option value="">없음</option>
                    {categories
                      .filter((category) => category.id !== selectedId && category.is_active)
                      .map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                  </select>
                </label>
                <label>
                  <span>표시 순서</span>
                  <input className="input" type="number" value={form.sort_order ?? 100} onChange={(event) => setForm((prev) => ({ ...prev, sort_order: Number(event.target.value) }))} />
                </label>
                <label>
                  <span>설명</span>
                  <textarea className="textarea" value={form.description || ""} onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))} />
                </label>
                <label className="kms-check-field">
                  <input type="checkbox" checked={!!form.is_active} onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))} />
                  <span>사용</span>
                </label>
              </div>
              <div className="kms-action-row">
                <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={saving}>{saving ? "저장 중..." : "저장"}</button>
                {selectedId ? <button type="button" className="btn btn-danger" onClick={() => void deactivate(selectedId)} disabled={saving}>비활성화</button> : null}
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

export default KmsSettingsPage;
