import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import { repositories } from "@/services";
import type {
  KmsCategory,
  KmsCategoryPayload,
  KmsCategorySortOrderItem,
  KmsSettingGroup,
  KmsSettingItem,
  KmsSettingItemPayload,
} from "@/types/kms";

type SettingsTab = "settings" | "categories";

const emptyCategoryForm: KmsCategoryPayload = {
  parent_id: null,
  name: "",
  description: "",
  sort_order: 100,
  is_active: true,
};

const emptySettingForm: KmsSettingItemPayload = {
  group_code: "PARA_TYPE",
  item_code: "",
  item_name: "",
  description: "",
  color: "#dbeafe",
  icon: "",
  sort_order: 100,
  is_default: false,
  is_active: true,
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

const nextSortOrder = (rows: Array<{ sort_order: number }>) => {
  const maxOrder = rows.reduce((max, item) => Math.max(max, item.sort_order || 0), 0);
  return maxOrder ? maxOrder + 10 : 100;
};

function KmsSettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("settings");
  const [settingGroups, setSettingGroups] = useState<KmsSettingGroup[]>([]);
  const [selectedGroupCode, setSelectedGroupCode] = useState("PARA_TYPE");
  const [selectedSettingId, setSelectedSettingId] = useState<number | null>(null);
  const [settingForm, setSettingForm] = useState<KmsSettingItemPayload>(emptySettingForm);

  const [categories, setCategories] = useState<KmsCategory[]>([]);
  const [rankCategories, setRankCategories] = useState<KmsCategory[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [categoryFormOpen, setCategoryFormOpen] = useState(false);
  const [categoryForm, setCategoryForm] = useState<KmsCategoryPayload>(emptyCategoryForm);
  const [rankEditing, setRankEditing] = useState(false);
  const [draggedId, setDraggedId] = useState<number | null>(null);

  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const orderedCategories = useMemo(() => sortCategories(categories), [categories]);
  const selectedGroup = useMemo(
    () => settingGroups.find((group) => group.group_code === selectedGroupCode) ?? settingGroups[0] ?? null,
    [settingGroups, selectedGroupCode],
  );
  const settingItems = selectedGroup?.items ?? [];
  const categoryCards = rankEditing ? rankCategories : orderedCategories;

  const loadSettings = async () => {
    const groups = await repositories.kms.listSettingGroups(true, true);
    setSettingGroups(groups);
    if (!groups.some((group) => group.group_code === selectedGroupCode)) {
      setSelectedGroupCode(groups[0]?.group_code ?? "PARA_TYPE");
    }
  };

  const loadCategories = async () => {
    const rows = sortCategories(await repositories.kms.listCategories(true));
    setCategories(rows);
    setRankCategories(rows);
  };

  const load = async () => {
    setMessage("");
    try {
      await Promise.all([loadSettings(), loadCategories()]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "KMS 설정을 불러오지 못했습니다.");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const resetSettingForm = (groupCode = selectedGroupCode) => {
    setSelectedSettingId(null);
    setSettingForm({
      ...emptySettingForm,
      group_code: groupCode,
      sort_order: nextSortOrder(settingGroups.find((group) => group.group_code === groupCode)?.items ?? []),
    });
  };

  const selectGroup = (groupCode: string) => {
    setSelectedGroupCode(groupCode);
    resetSettingForm(groupCode);
  };

  const editSettingItem = (item: KmsSettingItem) => {
    setSelectedSettingId(item.id);
    setSettingForm({
      group_code: item.group_code || selectedGroupCode,
      item_code: item.item_code,
      item_name: item.item_name,
      description: item.description || "",
      color: item.color || "#dbeafe",
      icon: item.icon || "",
      sort_order: item.sort_order,
      is_default: item.is_default,
      is_active: item.is_active,
    });
  };

  const saveSettingItem = async () => {
    if (!settingForm.item_code.trim() || !settingForm.item_name.trim()) {
      setMessage("설정 코드와 표시명은 필수입니다.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      if (selectedSettingId) {
        await repositories.kms.updateSettingItem(selectedSettingId, {
          item_code: settingForm.item_code.trim().toUpperCase(),
          item_name: settingForm.item_name.trim(),
          description: settingForm.description || null,
          color: settingForm.color || null,
          icon: settingForm.icon || null,
          sort_order: Number(settingForm.sort_order || 100),
          is_default: !!settingForm.is_default,
          is_active: !!settingForm.is_active,
        });
        setMessage("설정 항목을 수정했습니다.");
      } else {
        await repositories.kms.createSettingItem({
          ...settingForm,
          item_code: settingForm.item_code.trim().toUpperCase(),
          item_name: settingForm.item_name.trim(),
          sort_order: Number(settingForm.sort_order || 100),
        });
        setMessage("설정 항목을 추가했습니다.");
      }
      await loadSettings();
      resetSettingForm(settingForm.group_code);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "설정 항목 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const toggleSettingActive = async (item: KmsSettingItem) => {
    setSaving(true);
    setMessage("");
    try {
      await repositories.kms.updateSettingItemActive(item.id, !item.is_active);
      await loadSettings();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "설정 항목 상태 변경에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const setDefaultSetting = async (item: KmsSettingItem) => {
    setSaving(true);
    setMessage("");
    try {
      await repositories.kms.updateSettingItemDefault(item.id);
      await loadSettings();
      setMessage("기본값을 변경했습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "기본값 변경에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const saveSettingOrder = async () => {
    setSaving(true);
    setMessage("");
    try {
      const items = settingItems.map((item, index) => ({ id: item.id, sort_order: (index + 1) * 10 }));
      const result = await repositories.kms.reorderSettingItems(items);
      await loadSettings();
      setMessage(`정렬 순서를 저장했습니다. (${result.updated_count}개)`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "정렬 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const openCreateCategory = () => {
    setSelectedCategoryId(null);
    setCategoryForm({ ...emptyCategoryForm, sort_order: nextSortOrder(categories) });
    setCategoryFormOpen(true);
  };

  const selectCategory = (category: KmsCategory) => {
    setSelectedCategoryId(category.id);
    setCategoryForm({
      parent_id: category.parent_id,
      name: category.name,
      description: category.description || "",
      sort_order: category.sort_order,
      is_active: category.is_active,
    });
    setCategoryFormOpen(true);
  };

  const closeCategoryForm = () => {
    setSelectedCategoryId(null);
    setCategoryForm(emptyCategoryForm);
    setCategoryFormOpen(false);
  };

  const saveCategory = async () => {
    if (!categoryForm.name.trim()) {
      setMessage("카테고리명은 필수입니다.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      if (selectedCategoryId) {
        await repositories.kms.updateCategory(selectedCategoryId, { ...categoryForm, name: categoryForm.name.trim() });
        setMessage("카테고리를 수정했습니다.");
      } else {
        await repositories.kms.createCategory({ ...categoryForm, name: categoryForm.name.trim() });
        setMessage("카테고리를 추가했습니다.");
      }
      closeCategoryForm();
      await loadCategories();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const toggleCategoryActive = async (category: KmsCategory) => {
    setSaving(true);
    setMessage("");
    try {
      await repositories.kms.updateCategoryActive(category.id, !category.is_active);
      await loadCategories();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 상태 변경에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const deleteCategory = async (category: KmsCategory) => {
    if ((category.total_post_count ?? 0) > 0 || (category.child_count ?? 0) > 0) {
      setMessage("연결된 지식글 또는 하위 카테고리가 있어 삭제할 수 없습니다. 비활성화를 사용해 주세요.");
      return;
    }
    if (!window.confirm("이 카테고리를 삭제할까요?")) return;
    setSaving(true);
    setMessage("");
    try {
      await repositories.kms.deleteCategory(category.id);
      await loadCategories();
      setMessage("카테고리를 삭제했습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 삭제에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const startRankEditing = () => {
    setRankCategories(orderedCategories);
    setRankEditing(true);
    closeCategoryForm();
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

  const saveCategoryRank = async () => {
    const items: KmsCategorySortOrderItem[] = rankCategories.map((category, index) => ({
      id: category.id,
      sort_order: (index + 1) * 10,
    }));
    setSaving(true);
    setMessage("");
    try {
      const result = await repositories.kms.updateCategorySortOrders(items);
      await loadCategories();
      setRankEditing(false);
      setDraggedId(null);
      setMessage(`카테고리 순서를 저장했습니다. (${result.updated_count}개)`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "카테고리 순서 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="KMS 설정" description="PARA, 카테고리, 상태, 중요도, 태그 유형, 사용처, 출처 유형을 DB 설정값으로 관리합니다." />

      {message ? <div className="alert alert-warning">{message}</div> : null}

      <div className="kms-tabs" role="tablist" aria-label="KMS 설정 탭">
        <button type="button" role="tab" aria-selected={activeTab === "settings"} className={`kms-tab ${activeTab === "settings" ? "active" : ""}`} onClick={() => setActiveTab("settings")}>설정값</button>
        <button type="button" role="tab" aria-selected={activeTab === "categories"} className={`kms-tab ${activeTab === "categories" ? "active" : ""}`} onClick={() => setActiveTab("categories")}>기존 카테고리</button>
      </div>

      {activeTab === "settings" ? (
        <section className="kms-panel kms-settings-panel">
          <div className="kms-panel-header">
            <div>
              <h2 className="kms-panel-title">KMS 설정값 관리</h2>
              <p className="kms-panel-description">시스템 기본 항목은 삭제 대신 비활성화 정책으로 보호됩니다. 그룹별 기본값은 하나만 유지됩니다.</p>
            </div>
            <button type="button" className="btn btn-secondary" onClick={() => void saveSettingOrder()} disabled={saving || settingItems.length < 2}>현재 순서 저장</button>
          </div>

          <div className="kms-setting-group-tabs">
            {settingGroups.map((group) => (
              <button
                key={group.group_code}
                type="button"
                className={group.group_code === selectedGroupCode ? "active" : ""}
                onClick={() => selectGroup(group.group_code)}
              >
                {group.group_name}
              </button>
            ))}
          </div>

          <div className="kms-settings-layout">
            <div className="kms-setting-item-list">
              {settingItems.map((item) => (
                <article key={item.id} className={`kms-setting-item-card ${!item.is_active ? "inactive" : ""} ${selectedSettingId === item.id ? "selected" : ""}`}>
                  <div className="kms-setting-item-main">
                    <span className="kms-setting-color-dot" style={{ backgroundColor: item.color || "#dbeafe" }} />
                    <div>
                      <strong>{item.item_name}</strong>
                      <small>{item.item_code} · 순서 {item.sort_order}</small>
                    </div>
                  </div>
                  <p>{item.description || "설명 없음"}</p>
                  <div className="kms-setting-item-badges">
                    {item.is_default ? <span>기본값</span> : null}
                    {item.is_system ? <span>시스템</span> : null}
                    <span>{item.is_active ? "활성" : "비활성"}</span>
                  </div>
                  <div className="kms-category-card-actions">
                    <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => editSettingItem(item)} disabled={saving}>수정</button>
                    <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void setDefaultSetting(item)} disabled={saving || item.is_default}>기본값</button>
                    <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void toggleSettingActive(item)} disabled={saving || (item.is_system && item.is_active)}>
                      {item.is_active ? "비활성" : "활성"}
                    </button>
                  </div>
                </article>
              ))}
            </div>

            <div className="kms-category-editor-card kms-setting-editor-card">
              <div className="kms-panel-subtitle-row">
                <strong>{selectedSettingId ? "설정 항목 수정" : "설정 항목 추가"}</strong>
                <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => resetSettingForm()}>초기화</button>
              </div>
              <div className="kms-form-grid kms-category-editor-grid">
                <label className="kms-form-field">
                  <span className="kms-form-label">그룹</span>
                  <select className="select kms-form-control" value={settingForm.group_code} disabled={!!selectedSettingId} onChange={(event) => setSettingForm((prev) => ({ ...prev, group_code: event.target.value }))}>
                    {settingGroups.map((group) => <option key={group.group_code} value={group.group_code}>{group.group_name}</option>)}
                  </select>
                </label>
                <label className="kms-form-field">
                  <span className="kms-form-label">코드 *</span>
                  <input className="input kms-form-control" value={settingForm.item_code} onChange={(event) => setSettingForm((prev) => ({ ...prev, item_code: event.target.value }))} />
                </label>
                <label className="kms-form-field">
                  <span className="kms-form-label">표시명 *</span>
                  <input className="input kms-form-control" value={settingForm.item_name} onChange={(event) => setSettingForm((prev) => ({ ...prev, item_name: event.target.value }))} />
                </label>
                <label className="kms-form-field">
                  <span className="kms-form-label">색상</span>
                  <input className="input kms-form-control" type="color" value={settingForm.color || "#dbeafe"} onChange={(event) => setSettingForm((prev) => ({ ...prev, color: event.target.value }))} />
                </label>
                <label className="kms-form-field">
                  <span className="kms-form-label">아이콘/약어</span>
                  <input className="input kms-form-control" value={settingForm.icon || ""} onChange={(event) => setSettingForm((prev) => ({ ...prev, icon: event.target.value }))} />
                </label>
                <label className="kms-form-field">
                  <span className="kms-form-label">표시 순서</span>
                  <input className="input kms-form-control" type="number" value={settingForm.sort_order ?? 100} onChange={(event) => setSettingForm((prev) => ({ ...prev, sort_order: Number(event.target.value) }))} />
                </label>
                <label className="kms-form-field kms-form-wide">
                  <span className="kms-form-label">설명</span>
                  <textarea className="textarea kms-form-control kms-category-description-input" value={settingForm.description || ""} onChange={(event) => setSettingForm((prev) => ({ ...prev, description: event.target.value }))} />
                </label>
                <label className="kms-check-field">
                  <input type="checkbox" checked={!!settingForm.is_default} onChange={(event) => setSettingForm((prev) => ({ ...prev, is_default: event.target.checked }))} />
                  <span>기본값</span>
                </label>
                <label className="kms-check-field">
                  <input type="checkbox" checked={!!settingForm.is_active} onChange={(event) => setSettingForm((prev) => ({ ...prev, is_active: event.target.checked }))} />
                  <span>활성</span>
                </label>
              </div>
              <div className="kms-action-row">
                <button type="button" className="btn btn-primary" onClick={() => void saveSettingItem()} disabled={saving}>{saving ? "저장 중..." : "저장"}</button>
                <button type="button" className="btn btn-secondary" onClick={() => resetSettingForm()} disabled={saving}>취소</button>
              </div>
            </div>
          </div>
        </section>
      ) : (
        <section className="kms-panel kms-settings-panel">
          <div className="kms-panel-header">
            <div>
              <h2 className="kms-panel-title">기존 카테고리 관리</h2>
              <p className="kms-panel-description">기존 KMS 게시글 호환을 위한 카테고리입니다. 새 지식 카테고리는 설정값 탭에서 관리합니다.</p>
            </div>
          </div>

          <div className="kms-category-toolbar">
            <button type="button" className="btn btn-primary" onClick={openCreateCategory} disabled={saving || rankEditing}>카테고리 추가</button>
            {!rankEditing ? (
              <button type="button" className="btn btn-secondary" onClick={startRankEditing} disabled={saving || categories.length < 2}>순서 편집</button>
            ) : (
              <>
                <button type="button" className="btn btn-primary" onClick={() => void saveCategoryRank()} disabled={saving}>순서 저장</button>
                <button type="button" className="btn btn-secondary" onClick={() => { setRankEditing(false); setDraggedId(null); }} disabled={saving}>취소</button>
              </>
            )}
            <span className="kms-category-toolbar-count">총 {categories.length.toLocaleString("ko-KR")}개</span>
          </div>

          {categoryFormOpen ? (
            <div className="kms-category-editor-card">
              <div className="kms-panel-subtitle-row">
                <strong>{selectedCategoryId ? "카테고리 수정" : "카테고리 추가"}</strong>
                <button type="button" className="btn btn-secondary btn-table-sm" onClick={closeCategoryForm} disabled={saving}>닫기</button>
              </div>
              <div className="kms-form-grid kms-category-editor-grid">
                <label className="kms-form-field">
                  <span className="kms-form-label">카테고리명 *</span>
                  <input className="input kms-form-control" value={categoryForm.name} onChange={(event) => setCategoryForm((prev) => ({ ...prev, name: event.target.value }))} />
                </label>
                <label className="kms-form-field">
                  <span className="kms-form-label">상위 카테고리</span>
                  <select className="select kms-form-control" value={categoryForm.parent_id ?? ""} onChange={(event) => setCategoryForm((prev) => ({ ...prev, parent_id: event.target.value ? Number(event.target.value) : null }))}>
                    <option value="">없음</option>
                    {categories.filter((category) => category.id !== selectedCategoryId && category.is_active).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                  </select>
                </label>
                <label className="kms-form-field">
                  <span className="kms-form-label">표시 순서</span>
                  <input className="input kms-form-control" type="number" value={categoryForm.sort_order ?? 100} onChange={(event) => setCategoryForm((prev) => ({ ...prev, sort_order: Number(event.target.value) }))} />
                </label>
                <label className="kms-form-field kms-form-wide">
                  <span className="kms-form-label">설명</span>
                  <textarea className="textarea kms-form-control kms-category-description-input" value={categoryForm.description || ""} onChange={(event) => setCategoryForm((prev) => ({ ...prev, description: event.target.value }))} />
                </label>
                <label className="kms-check-field">
                  <input type="checkbox" checked={!!categoryForm.is_active} onChange={(event) => setCategoryForm((prev) => ({ ...prev, is_active: event.target.checked }))} />
                  <span>활성</span>
                </label>
              </div>
              <div className="kms-action-row">
                <button type="button" className="btn btn-primary" onClick={() => void saveCategory()} disabled={saving}>{saving ? "저장 중..." : "저장"}</button>
                <button type="button" className="btn btn-secondary" onClick={closeCategoryForm} disabled={saving}>취소</button>
              </div>
            </div>
          ) : null}

          <div className={rankEditing ? "kms-category-card-grid rank-editing" : "kms-category-card-grid"}>
            {categoryCards.map((category, index) => {
              const postCount = countOf(category.post_count);
              const totalPostCount = countOf(category.total_post_count);
              const childCount = countOf(category.child_count);
              const deleteBlocked = totalPostCount > 0 || childCount > 0;
              return (
                <article
                  key={category.id}
                  className={`kms-category-admin-card ${selectedCategoryId === category.id ? "selected" : ""} ${!category.is_active ? "inactive" : ""} ${rankEditing ? "draggable" : ""}`}
                  draggable={rankEditing}
                  onDragStart={() => setDraggedId(category.id)}
                  onDragOver={(event) => {
                    event.preventDefault();
                    moveDraggedCard(category.id);
                  }}
                  onDragEnd={() => setDraggedId(null)}
                >
                  <div className="kms-category-card-topline">
                    <span className="kms-category-rank">{rankEditing ? `${index + 1}위` : `순서 ${category.sort_order}`}</span>
                    <span className={`kms-mini-badge ${category.is_active ? "active" : "inactive"}`}>{category.is_active ? "활성" : "비활성"}</span>
                  </div>
                  <div className="kms-category-card-title-row">
                    {rankEditing ? <span className="kms-drag-handle" aria-hidden="true">↕</span> : null}
                    <strong>{category.name}</strong>
                  </div>
                  <p>{category.description || "설명 없음"}</p>
                  <div className="kms-category-card-meta">
                    <span>{category.parent_id ? "하위분류" : "대분류"}</span>
                    <span>지식글 {postCount.toLocaleString("ko-KR")}개</span>
                    <span>하위 {childCount.toLocaleString("ko-KR")}개</span>
                    <span>수정 {category.updated_at || "-"}</span>
                  </div>
                  <div className="kms-category-card-actions">
                    <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => selectCategory(category)} disabled={saving || rankEditing}>수정</button>
                    <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void toggleCategoryActive(category)} disabled={saving || rankEditing}>{category.is_active ? "비활성" : "활성"}</button>
                    <button type="button" className="btn btn-danger btn-table-sm" onClick={() => void deleteCategory(category)} disabled={saving || rankEditing || deleteBlocked}>삭제</button>
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
