import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import { repositories } from "@/services";
import type { KmsCategory, KmsCategoryPayload, KmsCategorySortOrderItem } from "@/types/kms";

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

const DEFAULT_CATEGORY_ORDER: Record<string, number> = {
  시장: 10,
  재료: 20,
  수급: 30,
  차트: 40,
  재무: 50,
  기법: 60,
  심리: 70,
  리스크: 80,
  복기: 90,
  자료: 100,
};

const countOf = (value: number | undefined) => value ?? 0;

const sortCategories = (rows: KmsCategory[]) =>
  [...rows].sort((a, b) => {
    const parentDiff = (a.parent_id ?? 0) - (b.parent_id ?? 0);
    if (parentDiff) return parentDiff;
    const orderDiff = a.sort_order - b.sort_order;
    if (orderDiff) return orderDiff;
    return a.name.localeCompare(b.name, "ko-KR");
  });

const nextSortOrder = (rows: KmsCategory[]) => {
  const maxOrder = rows.reduce((max, category) => Math.max(max, category.sort_order || 0), 0);
  return maxOrder ? maxOrder + 10 : 100;
};

function KmsSettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("categories");
  const [categories, setCategories] = useState<KmsCategory[]>([]);
  const [rankCategories, setRankCategories] = useState<KmsCategory[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState<KmsCategoryPayload>(emptyCategoryForm);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [rankEditing, setRankEditing] = useState(false);
  const [draggedId, setDraggedId] = useState<number | null>(null);

  const orderedCategories = useMemo(() => sortCategories(categories), [categories]);
  const cards = rankEditing ? rankCategories : orderedCategories;
  const activeTabInfo = SETTINGS_TABS.find((tab) => tab.key === activeTab) ?? SETTINGS_TABS[0];

  const load = async () => {
    setMessage("");
    try {
      const rows = await repositories.kms.listCategories(true);
      const sorted = sortCategories(rows);
      setCategories(sorted);
      setRankCategories(sorted);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 목록을 불러오지 못했습니다.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const openCreateForm = () => {
    setSelectedId(null);
    setForm({ ...emptyCategoryForm, sort_order: nextSortOrder(categories) });
    setFormOpen(true);
  };

  const selectCategory = (category: KmsCategory) => {
    setSelectedId(category.id);
    setForm({
      parent_id: category.parent_id,
      name: category.name,
      description: category.description || "",
      sort_order: category.sort_order,
      is_active: category.is_active,
    });
    setFormOpen(true);
  };

  const closeForm = () => {
    setSelectedId(null);
    setForm(emptyCategoryForm);
    setFormOpen(false);
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
      closeForm();
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (category: KmsCategory) => {
    setSaving(true);
    setMessage("");
    try {
      await repositories.kms.updateCategoryActive(category.id, !category.is_active);
      await load();
      setMessage(category.is_active ? "카테고리가 비활성화되었습니다." : "카테고리가 활성화되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 상태 변경에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const deleteCategory = async (category: KmsCategory) => {
    const postCount = countOf(category.post_count);
    const totalPostCount = countOf(category.total_post_count);
    const childCount = countOf(category.child_count);
    if (totalPostCount > 0) {
      setMessage("이 카테고리에 연결된 게시글이 있어 삭제할 수 없습니다. 비활성화를 사용해 주세요.");
      return;
    }
    if (childCount > 0) {
      setMessage("하위 카테고리가 있어 삭제할 수 없습니다. 하위 카테고리를 먼저 정리해 주세요.");
      return;
    }
    if (!window.confirm("게시글이 없는 카테고리만 실제 삭제됩니다. 이 카테고리를 삭제하시겠습니까?")) return;
    setSaving(true);
    setMessage("");
    try {
      await repositories.kms.deleteCategory(category.id);
      if (selectedId === category.id) closeForm();
      await load();
      setMessage("카테고리가 삭제되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 삭제에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const startRankEditing = () => {
    setRankCategories(orderedCategories);
    setRankEditing(true);
    closeForm();
    setMessage("카드를 드래그해서 순서를 바꾼 뒤 순위 저장을 눌러 주세요.");
  };

  const cancelRankEditing = () => {
    setRankCategories(orderedCategories);
    setRankEditing(false);
    setDraggedId(null);
    setMessage("순위 편집을 취소했습니다.");
  };

  const moveDraggedCard = (targetId: number) => {
    if (!rankEditing || draggedId === null || draggedId === targetId) return;
    setRankCategories((prev) => {
      const fromIndex = prev.findIndex((category) => category.id === draggedId);
      const toIndex = prev.findIndex((category) => category.id === targetId);
      if (fromIndex < 0 || toIndex < 0) return prev;
      const next = [...prev];
      const [moved] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, moved);
      return next;
    });
  };

  const resetAutoRank = () => {
    const next = [...rankCategories].sort((a, b) => {
      const aDefault = a.parent_id ? 1000 + a.sort_order : DEFAULT_CATEGORY_ORDER[a.name] ?? 900;
      const bDefault = b.parent_id ? 1000 + b.sort_order : DEFAULT_CATEGORY_ORDER[b.name] ?? 900;
      const defaultDiff = aDefault - bDefault;
      if (defaultDiff) return defaultDiff;
      return a.name.localeCompare(b.name, "ko-KR");
    });
    setRankCategories(next);
    setMessage("자동순위로 재정렬했습니다. 적용하려면 순위 저장을 눌러 주세요.");
  };

  const saveRank = async () => {
    const items: KmsCategorySortOrderItem[] = rankCategories.map((category, index) => ({
      id: category.id,
      sort_order: (index + 1) * 10,
    }));
    setSaving(true);
    setMessage("");
    try {
      const result = await repositories.kms.updateCategorySortOrders(items);
      await load();
      setRankEditing(false);
      setDraggedId(null);
      setMessage(`카테고리 순위가 저장되었습니다. (${result.updated_count.toLocaleString("ko-KR")}개)`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 순위 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

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
              <p className="kms-panel-description">카드에서 등록, 수정, 상태 변경, 삭제, 표시 순서를 관리합니다.</p>
            </div>
          </div>

          <div className="kms-category-toolbar">
            <button type="button" className="btn btn-primary" onClick={openCreateForm} disabled={saving || rankEditing}>카테고리 등록</button>
            {!rankEditing ? (
              <button type="button" className="btn btn-secondary" onClick={startRankEditing} disabled={saving || categories.length < 2}>순위 편집</button>
            ) : (
              <>
                <button type="button" className="btn btn-primary" onClick={() => void saveRank()} disabled={saving}>순위 저장</button>
                <button type="button" className="btn btn-secondary" onClick={cancelRankEditing} disabled={saving}>취소</button>
                <button type="button" className="btn btn-secondary" onClick={resetAutoRank} disabled={saving}>자동순위로 초기화</button>
              </>
            )}
            <span className="kms-category-toolbar-count">총 {categories.length.toLocaleString("ko-KR")}개</span>
          </div>

          {formOpen ? (
            <div className="kms-category-editor-card">
              <div className="kms-panel-subtitle-row">
                <strong>{selectedId ? "카테고리 수정" : "카테고리 등록"}</strong>
                <button type="button" className="btn btn-secondary btn-table-sm" onClick={closeForm} disabled={saving}>닫기</button>
              </div>
              <div className="kms-form-grid kms-category-editor-grid">
                <label className="kms-form-field">
                  <span className="kms-form-label">카테고리명 *</span>
                  <input className="input kms-form-control" value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />
                </label>
                <label className="kms-form-field">
                  <span className="kms-form-label">상위 카테고리</span>
                  <select
                    className="select kms-form-control"
                    value={form.parent_id ?? ""}
                    onChange={(event) => setForm((prev) => ({ ...prev, parent_id: event.target.value ? Number(event.target.value) : null }))}
                  >
                    <option value="">없음</option>
                    {categories
                      .filter((category) => category.id !== selectedId && category.is_active)
                      .map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                  </select>
                </label>
                <label className="kms-form-field">
                  <span className="kms-form-label">표시 순서</span>
                  <input className="input kms-form-control" type="number" value={form.sort_order ?? 100} onChange={(event) => setForm((prev) => ({ ...prev, sort_order: Number(event.target.value) }))} />
                </label>
                <label className="kms-form-field kms-form-wide">
                  <span className="kms-form-label">설명</span>
                  <textarea className="textarea kms-form-control kms-category-description-input" value={form.description || ""} onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))} />
                </label>
                <label className="kms-check-field">
                  <input type="checkbox" checked={!!form.is_active} onChange={(event) => setForm((prev) => ({ ...prev, is_active: event.target.checked }))} />
                  <span>사용</span>
                </label>
              </div>
              <div className="kms-action-row">
                <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={saving}>{saving ? "저장 중..." : "저장"}</button>
                <button type="button" className="btn btn-secondary" onClick={closeForm} disabled={saving}>취소</button>
              </div>
            </div>
          ) : null}

          <div className={rankEditing ? "kms-category-card-grid rank-editing" : "kms-category-card-grid"}>
            {cards.map((category, index) => {
              const postCount = countOf(category.post_count);
              const totalPostCount = countOf(category.total_post_count);
              const childCount = countOf(category.child_count);
              const deleteBlocked = totalPostCount > 0 || childCount > 0;
              const projectedOrder = rankEditing ? (index + 1) * 10 : category.sort_order;
              return (
                <article
                  key={category.id}
                  className={`kms-category-admin-card ${selectedId === category.id ? "selected" : ""} ${!category.is_active ? "inactive" : ""} ${rankEditing ? "draggable" : ""}`}
                  draggable={rankEditing}
                  onDragStart={() => setDraggedId(category.id)}
                  onDragOver={(event) => {
                    event.preventDefault();
                    moveDraggedCard(category.id);
                  }}
                  onDragEnd={() => setDraggedId(null)}
                >
                  <div className="kms-category-card-topline">
                    <span className="kms-category-rank">{rankEditing ? `${index + 1}위` : `순서 ${projectedOrder}`}</span>
                    <span className={`kms-mini-badge ${category.is_active ? "active" : "inactive"}`}>{category.is_active ? "활성" : "비활성"}</span>
                  </div>
                  <div className="kms-category-card-title-row">
                    {rankEditing ? <span className="kms-drag-handle" aria-hidden="true">↕</span> : null}
                    <strong>{category.name}</strong>
                  </div>
                  <p>{category.description || "설명 없음"}</p>
                  <div className="kms-category-card-meta">
                    <span>{category.parent_id ? "하위분류" : "대분류"}</span>
                    <span>게시글 {postCount.toLocaleString("ko-KR")}개</span>
                    <span>하위 {childCount.toLocaleString("ko-KR")}개</span>
                    <span>수정 {category.updated_at || "-"}</span>
                  </div>
                  <div className="kms-category-card-actions">
                    <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => selectCategory(category)} disabled={saving || rankEditing}>수정</button>
                    <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void toggleActive(category)} disabled={saving || rankEditing}>
                      {category.is_active ? "비활성화" : "활성화"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger btn-table-sm"
                      onClick={() => void deleteCategory(category)}
                      disabled={saving || rankEditing || deleteBlocked}
                      title={deleteBlocked ? "게시글 또는 하위 카테고리가 있어 삭제할 수 없습니다." : "게시글이 없는 카테고리를 실제 삭제합니다."}
                    >
                      삭제
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}

export default KmsSettingsPage;
