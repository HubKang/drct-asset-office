import { useEffect, useMemo, useState, type CSSProperties } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Grid2X2, List } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import KmsRichEditor from "@/components/kms/KmsRichEditor";
import { repositories } from "@/services";
import type { KmsKnowledgeItem, KmsKnowledgeItemPayload, KmsSettingGroup, KmsSettingItem, KmsSettingItemSummary } from "@/types/kms";
import { extractKmsImageSources, sanitizeKmsHtml, toKmsDisplayHtml, toKmsEditableHtml, toKmsPlainText } from "@/utils/kmsRichContent";

const cardPageSize = 12;
const listPageSize = 20;

const emptyKnowledgeForm: KmsKnowledgeItemPayload = {
  title: "",
  content: "",
  content_format: "HTML",
  summary: "",
  para_type_id: null,
  category_id: null,
  status_id: null,
  importance_id: null,
  usage_context_id: null,
  source_type_id: null,
  source_url: "",
  tags: "",
  editor_uploaded_image_urls: [],
};

const statusLabel = (value: string | null | undefined) => {
  const map: Record<string, string> = {
    PENDING: "대기",
    READY: "준비",
    RUNNING: "진행 중",
    DONE: "완료",
    FAILED: "실패",
  };
  return map[String(value || "PENDING")] || String(value || "대기");
};
const statusToneClass = (value: string | null | undefined) => {
  const normalized = String(value || "PENDING").toUpperCase();
  if (normalized === "DONE" || normalized === "READY") return "is-success";
  if (normalized === "RUNNING") return "is-running";
  if (normalized === "FAILED") return "is-error";
  return "is-pending";
};

const plainSnippet = (value: string | null | undefined, max = 140) => {
  const text = String(value || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max)}...` : text;
};

const normalizeTagNames = (tags: string[] | string | null | undefined) => {
  const rawValues = Array.isArray(tags) ? tags : String(tags || "").split(",");
  const seen = new Set<string>();
  const result: string[] = [];
  rawValues.forEach((raw) => {
    const name = String(raw || "").trim().replace(/^#+/, "").replace(/\s+/g, " ");
    const key = name.toLocaleLowerCase("ko-KR");
    if (!name || seen.has(key)) return;
    seen.add(key);
    result.push(name);
  });
  return result;
};

const hexToRgba = (hex?: string | null, alpha = 1) => {
  const fallback = `rgba(148, 163, 184, ${alpha})`;
  if (!hex) return fallback;
  const normalized = hex.replace("#", "").trim();
  const expanded = normalized.length === 3 ? normalized.split("").map((char) => char + char).join("") : normalized;
  if (!/^[0-9a-fA-F]{6}$/.test(expanded)) return fallback;
  const r = parseInt(expanded.slice(0, 2), 16);
  const g = parseInt(expanded.slice(2, 4), 16);
  const b = parseInt(expanded.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

const knowledgeCardStyle = (item: KmsKnowledgeItem): CSSProperties => {
  const categoryColor = item.category?.color || "#94a3b8";
  return {
    "--kms-card-category-color": categoryColor,
    "--kms-card-category-bg": hexToRgba(categoryColor, 0.1),
    "--kms-card-category-border": hexToRgba(categoryColor, 0.3),
    "--kms-card-category-divider": hexToRgba(categoryColor, 0.22),
  } as CSSProperties;
};

const confirmedTags = (item: KmsKnowledgeItem) => item.tags.filter((tag) => tag.is_confirmed);
const toTagText = (item: KmsKnowledgeItem) => confirmedTags(item).map((tag) => tag.tag_name).join(", ");

function SettingBadge({ item, fallback }: { item?: KmsSettingItemSummary | null; fallback: string }) {
  return (
    <span className="kms-knowledge-badge" style={{ "--kms-badge-bg": item?.color || "#f1f5f9" } as CSSProperties} title={item?.item_code || fallback}>
      {item?.item_name || fallback}
    </span>
  );
}

function KmsPostsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [settingGroups, setSettingGroups] = useState<KmsSettingGroup[]>([]);
  const [items, setItems] = useState<KmsKnowledgeItem[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [categoryCounts, setCategoryCounts] = useState<Map<number, number>>(new Map());
  const [viewMode, setViewMode] = useState<"card" | "list">("card");
  const [keyword, setKeyword] = useState(searchParams.get("keyword") || "");
  const [filters, setFilters] = useState({
    para_type_id: Number(searchParams.get("para_type_id") || 0),
    category_id: Number(searchParams.get("category_id") || 0),
    status_id: 0,
    importance_id: 0,
    usage_context_id: 0,
    source_type_id: 0,
    tag: searchParams.get("tags") || searchParams.get("tag") || "",
  });
  const [tagMatchMode, setTagMatchMode] = useState<"AND" | "OR">((searchParams.get("match_mode") === "OR" ? "OR" : "AND"));
  const [currentPage, setCurrentPage] = useState(1);
  const [showForm, setShowForm] = useState(searchParams.get("new") === "1");
  const [form, setForm] = useState<KmsKnowledgeItemPayload>(emptyKnowledgeForm);
  const [selectedItem, setSelectedItem] = useState<KmsKnowledgeItem | null>(null);
  const [drawerEditing, setDrawerEditing] = useState(false);
  const [drawerForm, setDrawerForm] = useState<KmsKnowledgeItemPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [drawerRemovedImageUrls, setDrawerRemovedImageUrls] = useState<string[]>([]);
  const routeKnowledgeItemId = Number(searchParams.get("item_id") || 0);

  const optionMap = useMemo(() => {
    const map = new Map<string, KmsSettingItem[]>();
    settingGroups.forEach((group) => map.set(group.group_code, group.items || []));
    return map;
  }, [settingGroups]);

  const categoryOptions = optionMap.get("KNOWLEDGE_CATEGORY") ?? [];
  const pageSize = viewMode === "list" ? listPageSize : cardPageSize;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const pageStart = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const pageEnd = Math.min(currentPage * pageSize, totalItems);

  const defaultId = (groupCode: string) => optionMap.get(groupCode)?.find((item) => item.is_default)?.id ?? optionMap.get(groupCode)?.[0]?.id ?? null;
  const withDefaults = (base: KmsKnowledgeItemPayload = emptyKnowledgeForm): KmsKnowledgeItemPayload => ({
    ...base,
    para_type_id: base.para_type_id ?? defaultId("PARA_TYPE"),
    category_id: base.category_id ?? defaultId("KNOWLEDGE_CATEGORY"),
    status_id: base.status_id ?? defaultId("KNOWLEDGE_STATUS"),
    importance_id: base.importance_id ?? defaultId("IMPORTANCE_LEVEL"),
    usage_context_id: base.usage_context_id ?? defaultId("USAGE_CONTEXT"),
    source_type_id: base.source_type_id ?? defaultId("SOURCE_TYPE"),
  });

  const loadItems = async (options?: { keepPage?: boolean; selectedItemId?: number | null }) => {
    setLoading(true);
    setMessage("");
    try {
      const baseParams = {
        keyword: keyword || undefined,
        para_type_id: filters.para_type_id || undefined,
        status_id: filters.status_id || undefined,
        importance_id: filters.importance_id || undefined,
        usage_context_id: filters.usage_context_id || undefined,
        source_type_id: filters.source_type_id || undefined,
        recent_days: Number(searchParams.get("recent") || 0) || undefined,
        is_active: true,
      };
      const data = await repositories.kms.listKnowledgeItemsPage({
        ...baseParams,
        category_id: filters.category_id || undefined,
        tag_names: normalizeTagNames(filters.tag),
        tag_match_mode: tagMatchMode,
        limit: pageSize,
        offset: (currentPage - 1) * pageSize,
      });
      setItems(data.items);
      setTotalItems(data.total);
      setCategoryCounts(new Map(data.category_counts.map((entry) => [entry.category_id, entry.count])));
      setSelectedItem((prev) => {
        const routeTargetId = Number(searchParams.get("item_id") || 0);
        const targetId = options?.selectedItemId ?? (routeTargetId || prev?.id);
        if (!targetId) return null;
        return data.items.find((row) => row.id === targetId) ?? prev;
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "지식 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void repositories.kms.listSettingGroups(false, true).then(setSettingGroups).catch((error) => setMessage(error instanceof Error ? error.message : "KMS 설정을 불러오지 못했습니다."));
  }, []);

  useEffect(() => {
    if (settingGroups.length === 0) return;
    setForm((prev) => withDefaults(prev));
    const statusCode = searchParams.get("status_code");
    const importanceCode = searchParams.get("importance_code");
    if (statusCode || importanceCode) {
      setFilters((prev) => ({
        ...prev,
        status_id: statusCode ? (optionMap.get("KNOWLEDGE_STATUS")?.find((item) => item.item_code === statusCode)?.id || prev.status_id) : prev.status_id,
        importance_id: importanceCode ? (optionMap.get("IMPORTANCE_LEVEL")?.find((item) => item.item_code === importanceCode)?.id || prev.importance_id) : prev.importance_id,
      }));
    } else {
      void loadItems();
    }
  }, [settingGroups]);

  useEffect(() => {
    if (settingGroups.length === 0) return;
    void loadItems();
  }, [filters, currentPage, viewMode, tagMatchMode]);

  useEffect(() => {
    if (!routeKnowledgeItemId) return;
    let active = true;
    repositories.kms.getKnowledgeItem(routeKnowledgeItemId)
      .then((item) => { if (active) setSelectedItem(item); })
      .catch((error) => { if (active) setMessage(error instanceof Error ? error.message : "연결된 지식을 불러오지 못했습니다."); });
    return () => { active = false; };
  }, [routeKnowledgeItemId]);

  useEffect(() => {
    if (!selectedItem) {
      setDrawerEditing(false);
      setDrawerForm(null);
      return;
    }
    setDrawerEditing(false);
    setDrawerRemovedImageUrls([]);
    setDrawerForm({
      title: selectedItem.title,
      content: toKmsEditableHtml(selectedItem.content),
      content_format: "HTML",
      summary: selectedItem.summary || "",
      para_type_id: selectedItem.para_type_id,
      category_id: selectedItem.category_id,
      status_id: selectedItem.status_id,
      importance_id: selectedItem.importance_id,
      usage_context_id: selectedItem.usage_context_id,
      source_type_id: selectedItem.source_type_id,
      source_url: selectedItem.source_url || "",
      tags: toTagText(selectedItem),
      editor_uploaded_image_urls: [],
    });
  }, [selectedItem]);

  useEffect(() => {
    if (!selectedItem) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedItem(null);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [selectedItem]);

  const compactSettingSelect = (groupCode: string, value: number | null | undefined, onChange: (value: number | null) => void, label: string, allLabel = "전체") => (
    <label className="kms-compact-field">
      <span>{label}</span>
      <select value={value ?? ""} onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}>
        <option value="">{allLabel}</option>
        {(optionMap.get(groupCode) ?? []).map((option) => <option key={option.id} value={option.id}>{option.item_name}</option>)}
      </select>
    </label>
  );

  const savePayload = (next: KmsKnowledgeItemPayload, cleanContent: string) => ({
    ...next,
    title: next.title.trim(),
    content: cleanContent,
    content_format: "HTML",
    summary: next.summary || null,
    source_url: next.source_url || null,
    tags: normalizeTagNames(next.tags),
  });

  const saveNewItem = async () => {
    const next = withDefaults(form);
    const cleanContent = sanitizeKmsHtml(next.content);
    if (!next.title.trim() || !toKmsPlainText(cleanContent)) {
      setMessage("제목과 본문은 필수입니다.");
      return;
    }
    setSaving(true);
    try {
      const saved = await repositories.kms.createKnowledgeItem(savePayload(next, cleanContent));
      setForm(withDefaults({ ...emptyKnowledgeForm }));
      setShowForm(false);
      const nextParams = new URLSearchParams(searchParams);
      nextParams.delete("new");
      setSearchParams(nextParams);
      await loadItems({ selectedItemId: saved.id });
      setSelectedItem(await repositories.kms.getKnowledgeItem(saved.id));
      setMessage("지식을 저장했습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "지식 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const saveDrawerItem = async () => {
    if (!selectedItem || !drawerForm) return;
    const next = withDefaults(drawerForm);
    const cleanContent = sanitizeKmsHtml(next.content);
    if (!next.title.trim() || !toKmsPlainText(cleanContent)) {
      setMessage("제목과 본문은 필수입니다.");
      return;
    }
    const originalImageSources = extractKmsImageSources(selectedItem.content);
    const nextImageSources = new Set(extractKmsImageSources(cleanContent));
    const explicitlyRemoved = new Set(drawerRemovedImageUrls);
    const unexpectedlyMissing = originalImageSources.filter((source) => !nextImageSources.has(source) && !explicitlyRemoved.has(source));
    if (unexpectedlyMissing.length) {
      setMessage(`이미지 ${unexpectedlyMissing.length}개가 명시적인 삭제 없이 본문에서 누락되어 저장을 중단했습니다. 편집 화면을 다시 열어 확인해 주세요.`);
      return;
    }
    setSaving(true);
    try {
      const saved = await repositories.kms.updateKnowledgeItem(selectedItem.id, {
        ...savePayload(next, cleanContent),
        editor_removed_image_urls: drawerRemovedImageUrls,
      });
      setSelectedItem(saved);
      await loadItems({ keepPage: true, selectedItemId: saved.id });
      setSelectedItem(await repositories.kms.getKnowledgeItem(saved.id));
      setDrawerEditing(false);
      setDrawerRemovedImageUrls([]);
      setMessage("지식을 수정했습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "지식 수정에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const deleteItem = async (item: KmsKnowledgeItem) => {
    if (!window.confirm("이 지식을 DB에서 삭제할까요? 삭제 후 복구할 수 없습니다.")) return;
    setSaving(true);
    try {
      await repositories.kms.deleteKnowledgeItem(item.id);
      setSelectedItem(null);
      await loadItems();
      setMessage("지식을 삭제했습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "지식 삭제에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const removeTag = async (tagId: number) => {
    if (!selectedItem) return;
    const updated = await repositories.kms.removeKnowledgeItemTag(selectedItem.id, tagId);
    setSelectedItem(updated);
    await loadItems({ selectedItemId: updated.id });
  };

  const runSummaryHelp = async () => {
    if (!selectedItem || aiBusy) return;
    setAiBusy(true);
    setMessage("");
    try {
      const result = await repositories.kms.generateKnowledgeItemSummaryHelp(selectedItem.id);
      if (result.item) setSelectedItem(result.item);
      await loadItems({ selectedItemId: result.item?.id ?? selectedItem.id });
      setMessage(result.status === "FAILED" ? result.error_message || "요약 생성에 실패했습니다." : "요약 도움을 생성했습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "요약 생성에 실패했습니다.");
    } finally {
      setAiBusy(false);
    }
  };

  const applySummaryHelp = async (payload: { apply_summary?: boolean; summary?: string | null; add_keywords_as_tags?: boolean; keywords?: string[] }) => {
    if (!selectedItem || aiBusy) return;
    setAiBusy(true);
    try {
      const result = await repositories.kms.applyKnowledgeItemSummaryHelp(selectedItem.id, payload);
      if (result.item) setSelectedItem(result.item);
      await loadItems({ selectedItemId: result.item?.id ?? selectedItem.id });
      setMessage("요약 도움 결과를 적용했습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "요약 도움 결과 적용에 실패했습니다.");
    } finally {
      setAiBusy(false);
    }
  };

  const resetFilters = () => {
    setKeyword("");
    setFilters({ para_type_id: 0, category_id: 0, status_id: 0, importance_id: 0, usage_context_id: 0, source_type_id: 0, tag: "" });
    setCurrentPage(1);
    setTagMatchMode("AND");
  };

  const runSearch = () => {
    setCurrentPage(1);
    if (currentPage === 1) void loadItems({ keepPage: true });
  };

  const updateFilters = (updater: (current: typeof filters) => typeof filters) => {
    setFilters(updater);
    setCurrentPage(1);
  };

  const changeView = (next: "card" | "list") => {
    setViewMode(next);
    setCurrentPage(1);
  };

  const handleSearchKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") runSearch();
  };

  const openCreate = () => {
    setForm(withDefaults({ ...emptyKnowledgeForm }));
    setShowForm(true);
    const next = new URLSearchParams(searchParams);
    next.set("new", "1");
    setSearchParams(next);
  };

  const summaryHelpPayload = useMemo(() => {
    const raw = selectedItem?.extractions?.find((item) => item.extraction_type === "SUMMARY_HELP")?.extraction_text;
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
    } catch {
      return null;
    }
  }, [selectedItem]);

  const summaryHelpText = typeof summaryHelpPayload?.summary === "string" ? summaryHelpPayload.summary.trim() : "";
  const summaryHelpKeywords = Array.isArray(summaryHelpPayload?.keywords) ? summaryHelpPayload.keywords.map(String).filter(Boolean) : [];
  const isSummaryHelpApplied = Boolean(summaryHelpText && selectedItem?.summary?.trim() === summaryHelpText);
  const selectedConfirmedTags = selectedItem ? confirmedTags(selectedItem) : [];

  const renderKnowledgeForm = (target: KmsKnowledgeItemPayload, setTarget: (updater: (prev: KmsKnowledgeItemPayload) => KmsKnowledgeItemPayload) => void, ownerId: number | null) => (
    <>
      <div className="kms-form-grid single">
        <label className="kms-form-field">
          <span className="kms-form-label">제목 *</span>
          <input className="input kms-form-control" value={target.title} onChange={(event) => setTarget((prev) => ({ ...prev, title: event.target.value }))} />
        </label>
        <label className="kms-form-field">
          <span className="kms-form-label">요약</span>
          <textarea className="textarea kms-form-control kms-summary-input" value={target.summary || ""} onChange={(event) => setTarget((prev) => ({ ...prev, summary: event.target.value }))} />
        </label>
        <div className="kms-form-field">
          <span className="kms-form-label">본문 *</span>
          <KmsRichEditor
            resetKey={ownerId ? `knowledge-${ownerId}` : "knowledge-new"}
            value={target.content}
            selectLocalImage={() => repositories.kms.selectLocalImage()}
            imageUploadDomain="kms"
            ownerType="kms_knowledge_item"
            ownerId={ownerId}
            onChange={(content) => setTarget((prev) => ({ ...prev, content, content_format: "HTML" }))}
            onSessionUploadedImageUrlsChange={(urls) => setTarget((prev) => ({ ...prev, editor_uploaded_image_urls: urls }))}
            onRemovedImageUrlsChange={ownerId ? setDrawerRemovedImageUrls : undefined}
          />
        </div>
      </div>
      <div className="kms-knowledge-meta-grid">
        {compactSettingSelect("PARA_TYPE", target.para_type_id, (value) => setTarget((prev) => ({ ...prev, para_type_id: value })), "지식 유형")}
        {compactSettingSelect("KNOWLEDGE_CATEGORY", target.category_id, (value) => setTarget((prev) => ({ ...prev, category_id: value })), "카테고리")}
        {compactSettingSelect("KNOWLEDGE_STATUS", target.status_id, (value) => setTarget((prev) => ({ ...prev, status_id: value })), "상태")}
        {compactSettingSelect("IMPORTANCE_LEVEL", target.importance_id, (value) => setTarget((prev) => ({ ...prev, importance_id: value })), "중요도")}
        {compactSettingSelect("USAGE_CONTEXT", target.usage_context_id, (value) => setTarget((prev) => ({ ...prev, usage_context_id: value })), "사용처")}
        {compactSettingSelect("SOURCE_TYPE", target.source_type_id, (value) => setTarget((prev) => ({ ...prev, source_type_id: value })), "출처 유형")}
      </div>
      <div className="kms-form-grid single">
        <label className="kms-form-field">
          <span className="kms-form-label">출처 URL</span>
          <input className="input kms-form-control" value={target.source_url || ""} onChange={(event) => setTarget((prev) => ({ ...prev, source_url: event.target.value }))} />
        </label>
        <label className="kms-form-field kms-form-wide">
          <span className="kms-form-label">태그</span>
          <input className="input kms-form-control" value={String(target.tags || "")} onChange={(event) => setTarget((prev) => ({ ...prev, tags: event.target.value }))} placeholder="#금리, 반도체, 리스크" />
        </label>
      </div>
    </>
  );

  return (
    <div className="space-y-4">
      <PageHeader title="지식 보드" description="기사 요약, 공모 내용, 투자 판단 메모를 자유롭게 저장하고 태그와 설정값으로 연결합니다." action={<button type="button" className="btn btn-primary" onClick={openCreate}>지식 등록</button>} />
      {message ? <div className="alert alert-warning">{message}</div> : null}

      {showForm ? (
        <section className="kms-panel kms-post-form-panel">
          <div className="kms-panel-header">
            <div>
              <h2 className="kms-panel-title">새 지식 등록</h2>
              <p className="kms-panel-description">제목과 본문만 입력해도 기본값으로 저장됩니다.</p>
            </div>
            <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>닫기</button>
          </div>
          {renderKnowledgeForm(form, setForm, null)}
          <div className="kms-action-row">
            <button type="button" className="btn btn-primary" onClick={() => void saveNewItem()} disabled={saving}>{saving ? "저장 중..." : "저장"}</button>
            <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)} disabled={saving}>취소</button>
          </div>
        </section>
      ) : null}

      <section className="knowledge-board-filter-panel">
        <div className="knowledge-board-search-bar">
          {compactSettingSelect("PARA_TYPE", filters.para_type_id || null, (value) => updateFilters((prev) => ({ ...prev, para_type_id: value || 0 })), "지식 유형")}
          {compactSettingSelect("KNOWLEDGE_CATEGORY", filters.category_id || null, (value) => updateFilters((prev) => ({ ...prev, category_id: value || 0 })), "카테고리")}
          <label className="kms-compact-field"><span>태그</span><input value={filters.tag} onChange={(event) => updateFilters((prev) => ({ ...prev, tag: event.target.value }))} placeholder="#태그, #태그" /></label>
          <div className="kms-filter-match-mode" aria-label="태그 검색 조건">
            <button type="button" className={tagMatchMode === "AND" ? "active" : ""} onClick={() => { setTagMatchMode("AND"); setCurrentPage(1); }}>AND</button>
            <button type="button" className={tagMatchMode === "OR" ? "active" : ""} onClick={() => { setTagMatchMode("OR"); setCurrentPage(1); }}>OR</button>
          </div>
          <label className="kms-compact-field"><span>검색어</span><input className="kms-search-input" value={keyword} onChange={(event) => setKeyword(event.target.value)} onKeyDown={handleSearchKeyDown} placeholder="제목, 본문, 요약 검색" /></label>
          <button type="button" className="btn btn-primary" onClick={runSearch} disabled={loading}>검색</button>
          <button type="button" className="btn btn-secondary" onClick={resetFilters}>초기화</button>
        </div>
      </section>

      <section className="knowledge-board-category-summary">
        <div className="section-header"><div><h2>카테고리 현황</h2></div></div>
        <div className="kms-category-strip">
          {categoryOptions.map((category) => (
            <button key={category.id} type="button" className={`kms-category-pill ${filters.category_id === category.id ? "active" : ""}`} style={{ "--category-color": category.color || "#94a3b8" } as CSSProperties} onClick={() => updateFilters((prev) => ({ ...prev, category_id: prev.category_id === category.id ? 0 : category.id }))}>
              <span className="category-dot" />
              <span className="category-name">{category.item_name}</span>
              <strong className="category-count">{(categoryCounts.get(category.id) || 0).toLocaleString("ko-KR")}개</strong>
            </button>
          ))}
        </div>
      </section>

      <section className="kms-panel">
        <div className="kms-board-title-row">
          <div><h2 className="kms-panel-title">지식 목록</h2><p className="kms-panel-description">{loading ? "조회 중..." : `총 ${totalItems.toLocaleString("ko-KR")}개 중 ${pageStart.toLocaleString("ko-KR")}-${pageEnd.toLocaleString("ko-KR")}개 표시`}</p></div>
          <div className="kms-view-toggle" aria-label="지식 목록 보기 방식">
            <button type="button" className={viewMode === "card" ? "active" : ""} aria-pressed={viewMode === "card"} onClick={() => changeView("card")}><Grid2X2 size={15} aria-hidden="true" />카드</button>
            <button type="button" className={viewMode === "list" ? "active" : ""} aria-pressed={viewMode === "list"} onClick={() => changeView("list")}><List size={16} aria-hidden="true" />목록</button>
          </div>
        </div>
        {viewMode === "card" ? (
          <div className="kms-result-grid">
            {items.map((item) => (
              <button key={item.id} type="button" className="kms-post-card kms-knowledge-item-card" style={knowledgeCardStyle(item)} onClick={() => setSelectedItem(item)}>
                <div className="kms-card-badges"><SettingBadge item={item.para_type} fallback="유형" /><SettingBadge item={item.category} fallback="미분류" /><SettingBadge item={item.status} fallback="상태" /><SettingBadge item={item.importance} fallback="중요도" /></div>
                <strong>{item.title}</strong>
                <p>{item.summary || plainSnippet(item.content)}</p>
                <div className="kms-chip-row compact">{confirmedTags(item).slice(0, 6).map((tag) => <span key={tag.id} className="kms-chip static">#{tag.tag_name}</span>)}</div>
                <div className="kms-knowledge-state-row"><span>출처: {item.source_type?.item_name || "-"}</span><span>임베딩: {statusLabel(item.embedding_status)}</span></div>
                <small>{item.updated_at.replace("T", " ").slice(0, 16)}</small>
              </button>
            ))}
          </div>
        ) : (
          <div className="kms-knowledge-list" role="table" aria-label="지식 목록">
            <div className="kms-knowledge-list-head" role="row"><span>유형</span><span>카테고리</span><span>제목</span><span>태그</span><span>상태</span><span>출처</span><span>수정일</span></div>
            {items.map((item) => {
              const tags = confirmedTags(item);
              return (
                <button key={item.id} type="button" role="row" className="kms-knowledge-list-row" onClick={() => setSelectedItem(item)} title={item.title}>
                  <span role="cell"><SettingBadge item={item.para_type} fallback="유형" /></span>
                  <span role="cell"><SettingBadge item={item.category} fallback="미분류" /></span>
                  <strong role="cell">{item.title}</strong>
                  <span role="cell" className="kms-list-tags">{tags.slice(0, 2).map((tag) => <i key={tag.id}>#{tag.tag_name}</i>)}{tags.length > 2 ? <i>+{tags.length - 2}</i> : null}</span>
                  <span role="cell">{item.status?.item_name || "-"}</span>
                  <span role="cell">{item.source_type?.item_name || "-"}</span>
                  <time role="cell">{item.updated_at.replace("T", " ").slice(0, 16)}</time>
                </button>
              );
            })}
          </div>
        )}
        {!loading && items.length === 0 ? <div className="kms-empty-state">조건에 맞는 지식이 없습니다.</div> : null}
        {totalPages > 1 ? <div className="kms-pagination"><span>총 {totalItems.toLocaleString("ko-KR")}개</span><button type="button" className="kms-page-button" onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))} disabled={currentPage === 1}>이전</button>{Array.from({ length: totalPages }, (_, index) => index + 1).map((page) => <button key={page} type="button" className={page === currentPage ? "kms-page-button active" : "kms-page-button"} onClick={() => setCurrentPage(page)}>{page}</button>)}<button type="button" className="kms-page-button" onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))} disabled={currentPage === totalPages}>다음</button></div> : null}
      </section>

      {selectedItem && drawerForm ? (
        <div className="kms-detail-drawer-backdrop" onClick={() => setSelectedItem(null)}>
          <aside className="kms-detail-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="kms-detail-drawer-header"><div><h2>{selectedItem.title}</h2><p>{selectedItem.para_type?.item_name || "-"} · {selectedItem.category?.item_name || "-"} · {selectedItem.created_at}</p></div><div className="kms-detail-drawer-actions"><button type="button" className="btn btn-primary" onClick={() => setDrawerEditing((prev) => !prev)}>{drawerEditing ? "보기" : "수정"}</button><button type="button" className="btn btn-secondary" onClick={() => setSelectedItem(null)}>닫기</button></div></div>
            <div className="kms-detail-drawer-body">
              {drawerEditing ? (
                <div className="kms-detail-drawer-edit-form">
                  {renderKnowledgeForm(drawerForm, (updater) => setDrawerForm((prev) => prev && updater(prev)), selectedItem.id)}
                  <div className="kms-action-row"><button type="button" className="btn btn-primary" onClick={() => void saveDrawerItem()} disabled={saving}>저장</button><button type="button" className="btn btn-danger" onClick={() => void deleteItem(selectedItem)} disabled={saving}>삭제</button></div>
                </div>
              ) : (
                <>
                  <div className="kms-card-badges"><SettingBadge item={selectedItem.para_type} fallback="유형" /><SettingBadge item={selectedItem.category} fallback="미분류" /><SettingBadge item={selectedItem.status} fallback="상태" /><SettingBadge item={selectedItem.importance} fallback="중요도" /><SettingBadge item={selectedItem.usage_context} fallback="사용처" /><SettingBadge item={selectedItem.source_type} fallback="출처" /></div>
                  {selectedItem.summary ? <section className="kms-content-section"><h3>요약</h3><p className="kms-detail-summary">{selectedItem.summary}</p></section> : null}
                  <section className="kms-content-section"><h3>본문</h3><div className="kms-detail-content kms-rich-content" dangerouslySetInnerHTML={{ __html: toKmsDisplayHtml(selectedItem.content) }} /></section>
                  <div className="kms-detail-support">
                    <section className="kms-detail-group" aria-labelledby="kms-knowledge-info-title">
                      <div className="kms-detail-group-heading">
                        <div>
                          <h3 id="kms-knowledge-info-title">지식 정보</h3>
                          <p>분류에 활용하는 태그와 원문 출처를 확인합니다.</p>
                        </div>
                      </div>
                      <div className="kms-detail-info-grid">
                        <article className="kms-detail-info-card">
                          <div className="kms-detail-info-card-heading">
                            <h4>태그</h4>
                            {selectedConfirmedTags.length ? <span>{selectedConfirmedTags.length}개</span> : null}
                          </div>
                          {selectedConfirmedTags.length ? (
                            <div className="kms-chip-row">
                              {selectedConfirmedTags.map((tag) => <button key={tag.id} type="button" className="kms-chip selected" onClick={() => void removeTag(tag.tag_id)}>#{tag.tag_name}</button>)}
                            </div>
                          ) : <div className="kms-compact-empty">등록된 태그가 없습니다.</div>}
                        </article>
                        <article className="kms-detail-info-card">
                          <div className="kms-detail-info-card-heading"><h4>출처</h4></div>
                          {selectedItem.source_url ? (
                            <a className="kms-source-link kms-detail-source-link" href={selectedItem.source_url} target="_blank" rel="noreferrer">{selectedItem.source_url}</a>
                          ) : <div className="kms-compact-empty">출처 URL이 없습니다.</div>}
                        </article>
                      </div>
                    </section>

                    <section className="kms-detail-group" aria-labelledby="kms-ai-usage-title">
                      <div className="kms-detail-group-heading">
                        <div>
                          <h3 id="kms-ai-usage-title">AI 활용</h3>
                          <p>요약 제안을 생성하고 AI 처리 상태를 확인합니다.</p>
                        </div>
                      </div>
                      <article className="kms-ai-summary-panel">
                        <div className="kms-ai-summary-header">
                          <div>
                            <h4>요약 도움</h4>
                            <span className={`kms-processing-pill ${statusToneClass(selectedItem.ai_extract_status)}`}>AI 추출 {statusLabel(selectedItem.ai_extract_status)}</span>
                          </div>
                          <button type="button" className="btn btn-primary" onClick={() => void runSummaryHelp()} disabled={aiBusy || selectedItem.ai_extract_status === "RUNNING"}>{aiBusy || selectedItem.ai_extract_status === "RUNNING" ? "요약 생성 중..." : summaryHelpText ? "다시 생성" : "요약 생성"}</button>
                        </div>
                        {aiBusy || selectedItem.ai_extract_status === "RUNNING" ? <div className="kms-compact-message is-running">본문 앞부분을 기반으로 요약과 키워드를 생성하는 중입니다.</div> : null}
                        {selectedItem.ai_extract_status === "FAILED" && !summaryHelpText ? <div className="kms-compact-message is-error">요약 생성에 실패했습니다. LM Studio 상태를 확인한 뒤 다시 시도해 주세요.</div> : null}
                        {summaryHelpText ? (
                          <div className="kms-ai-result-grid">
                            <article className="kms-extraction-card"><strong>요약 제안</strong><p>{summaryHelpText}</p><button type="button" className="btn btn-secondary" onClick={() => void applySummaryHelp({ apply_summary: true, summary: summaryHelpText })} disabled={aiBusy || isSummaryHelpApplied}>{isSummaryHelpApplied ? "적용됨" : "요약에 적용"}</button></article>
                            <article className="kms-extraction-card"><strong>키워드 제안</strong>{summaryHelpKeywords.length ? <div className="kms-chip-row">{summaryHelpKeywords.map((keyword) => <span key={keyword} className="kms-chip static">#{keyword}</span>)}</div> : <div className="kms-compact-empty">키워드 제안이 없습니다.</div>}{summaryHelpKeywords.length ? <button type="button" className="btn btn-secondary" onClick={() => void applySummaryHelp({ add_keywords_as_tags: true, keywords: summaryHelpKeywords })} disabled={aiBusy}>키워드를 태그에 추가</button> : null}</article>
                          </div>
                        ) : selectedItem.ai_extract_status !== "FAILED" && selectedItem.ai_extract_status !== "RUNNING" && !aiBusy ? <div className="kms-compact-empty">요약 생성 버튼을 눌러 요약과 키워드 제안을 만드세요. 결과는 자동 적용되지 않습니다.</div> : null}
                      </article>

                      <div className="kms-processing-status">
                        <h4>처리 상태</h4>
                        <div className="kms-processing-pill-row">
                          <span className={`kms-processing-pill ${statusToneClass(selectedItem.ai_extract_status)}`}>AI 추출 {statusLabel(selectedItem.ai_extract_status)}</span>
                          <span className={`kms-processing-pill ${statusToneClass(selectedItem.embedding_status)}`}>임베딩 {statusLabel(selectedItem.embedding_status)}</span>
                        </div>
                        {selectedItem.legacy_source_type ? <p>기존 데이터: {selectedItem.legacy_source_type} #{selectedItem.legacy_source_id}</p> : null}
                      </div>
                    </section>
                  </div>
                </>
              )}
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

export default KmsPostsPage;
