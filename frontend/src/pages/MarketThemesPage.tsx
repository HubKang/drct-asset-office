import { Fragment, useEffect, useMemo, useState } from "react";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type {
  MarketTheme,
  MarketThemeCandidate,
  MarketThemeCandidateStatus,
  MarketThemeLevel,
  MarketThemeStock,
  MarketThemeType,
} from "@/types/marketTheme";
import type { Stock } from "@/types/stock";

type ActiveTab = "themes" | "mapping" | "candidates";
type ThemeViewMode = "group" | "theme";
const THEME_PAGE_SIZE = 20;

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

function parseKeywordsInput(value: string): string[] {
  return value
    .split(/\r?\n|,/g)
    .map((x) => x.trim())
    .filter(Boolean);
}

function sourceLabel(source: string): string {
  if (source === "news") return "\uB274\uC2A4";
  if (source === "disclosure") return "\uACF5\uC2DC";
  if (source === "supply_event" || source === "kiwoom_supply_event") return "\uC218\uAE09\uC774\uBCA4\uD2B8";
  if (source === "manual") return "manual";
  return source;
}

function statusLabel(status: MarketThemeCandidateStatus): string {
  if (status === "pending") return "승인 대기";
  if (status === "approved") return "승인 완료";
  if (status === "rejected") return "거절";
  return "보류";
}

function themeTypeLabel(type: MarketThemeType): string {
  if (type === "theme") return "테마";
  if (type === "industry") return "산업";
  if (type === "custom") return "커스텀";
  return "텔레그램";
}

function themeLevelLabel(level?: MarketThemeLevel): string {
  return level === "THEME_GROUP" ? "테마그룹" : "테마";
}

function themeGroupSortName(theme: MarketTheme): string {
  if (theme.theme_level === "THEME_GROUP") return theme.theme_name || "";
  return theme.parent_theme_name || "미지정";
}

function MarketThemesPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("themes");

  const [themes, setThemes] = useState<MarketTheme[]>([]);
  const [selectedThemeId, setSelectedThemeId] = useState<number | null>(null);
  const [themeStocks, setThemeStocks] = useState<MarketThemeStock[]>([]);
  const [candidates, setCandidates] = useState<MarketThemeCandidate[]>([]);

  const [themeFilterType, setThemeFilterType] = useState<"all" | MarketThemeType>("all");
  const [themeFilterActive, setThemeFilterActive] = useState<"all" | "1" | "0">("all");
  const [themeFilterSupply, setThemeFilterSupply] = useState<"all" | "1" | "0">("all");
  const [themeFilterKeyword, setThemeFilterKeyword] = useState("");
  const [themeViewMode, setThemeViewMode] = useState<ThemeViewMode>("group");
  const [themeFilterGroupId, setThemeFilterGroupId] = useState<"all" | string>("all");
  const [expandedThemeGroupIds, setExpandedThemeGroupIds] = useState<Set<number>>(() => new Set());
  const [mappingThemeGroupId, setMappingThemeGroupId] = useState<"all" | string>("all");
  const [themePage, setThemePage] = useState(1);

  const [candidateStatusFilter, setCandidateStatusFilter] = useState<"all" | MarketThemeCandidateStatus>("pending");
  const [candidateSourceFilter, setCandidateSourceFilter] = useState<"all" | "news" | "disclosure">("all");
  const [lookbackDays, setLookbackDays] = useState(7);

  const [stockSearchKeyword, setStockSearchKeyword] = useState("");
  const [stockSearchResults, setStockSearchResults] = useState<Stock[]>([]);

  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [generatingCandidates, setGeneratingCandidates] = useState(false);
  const [updatingPrimaryMappingId, setUpdatingPrimaryMappingId] = useState<number | null>(null);

  const [themeModalOpen, setThemeModalOpen] = useState(false);
  const [formThemeId, setFormThemeId] = useState<number | null>(null);
  const [themeLevel, setThemeLevel] = useState<MarketThemeLevel>("THEME");
  const [parentThemeId, setParentThemeId] = useState<string>("");
  const [themeName, setThemeName] = useState("");
  const [themeType, setThemeType] = useState<MarketThemeType>("theme");
  const [description, setDescription] = useState("");
  const [keywordsText, setKeywordsText] = useState("");
  const [sortOrder, setSortOrder] = useState(100);
  const [isSupplyTheme, setIsSupplyTheme] = useState(0);
  const [isActive, setIsActive] = useState(1);

  const sortedThemes = useMemo(
    () =>
      [...themes].sort((a, b) => {
        const groupCompare = themeGroupSortName(a).localeCompare(themeGroupSortName(b), "ko-KR");
        if (groupCompare !== 0) return groupCompare;
        if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
        return a.theme_name.localeCompare(b.theme_name, "ko-KR");
      }),
    [themes],
  );
  const themeGroups = useMemo(
    () => sortedThemes.filter((row) => row.theme_level === "THEME_GROUP"),
    [sortedThemes],
  );

  const manageableThemes = useMemo(
    () => sortedThemes.filter((row) => row.theme_level !== "THEME_GROUP"),
    [sortedThemes],
  );

  const filteredThemes = useMemo(() => {
    const keyword = themeFilterKeyword.trim().toLowerCase();
    return sortedThemes.filter((row) => {
      if (themeViewMode === "group" && row.theme_level !== "THEME_GROUP") return false;
      if (themeViewMode === "theme" && row.theme_level === "THEME_GROUP") return false;
      if (themeViewMode === "theme" && themeFilterGroupId !== "all" && String(row.parent_theme_id ?? "") !== themeFilterGroupId) return false;
      if (themeFilterType !== "all" && row.theme_type !== themeFilterType) return false;
      if (themeFilterActive !== "all" && String(row.is_active) !== themeFilterActive) return false;
      if (themeFilterSupply !== "all" && String(row.is_supply_theme) !== themeFilterSupply) return false;
      if (!keyword) return true;
      return row.theme_name.toLowerCase().includes(keyword) || row.keywords.join(" ").toLowerCase().includes(keyword);
    });
  }, [sortedThemes, themeFilterActive, themeFilterGroupId, themeFilterKeyword, themeFilterSupply, themeFilterType, themeViewMode]);

  const themeTotalPages = Math.max(1, Math.ceil(filteredThemes.length / THEME_PAGE_SIZE));
  const safeThemePage = Math.min(themePage, themeTotalPages);
  const themePageStart = filteredThemes.length === 0 ? 0 : (safeThemePage - 1) * THEME_PAGE_SIZE + 1;
  const themePageEnd = Math.min(filteredThemes.length, safeThemePage * THEME_PAGE_SIZE);
  const pagedThemes = filteredThemes.slice((safeThemePage - 1) * THEME_PAGE_SIZE, safeThemePage * THEME_PAGE_SIZE);

  const selectedTheme = useMemo(() => sortedThemes.find((x) => x.id === selectedThemeId) ?? null, [sortedThemes, selectedThemeId]);
  const mappingSelectableThemes = useMemo(
    () =>
      manageableThemes.filter((row) => {
        if (row.is_active !== 1) return false;
        if (mappingThemeGroupId !== "all" && String(row.parent_theme_id ?? "") !== mappingThemeGroupId) return false;
        return true;
      }),
    [manageableThemes, mappingThemeGroupId],
  );
  const selectedThemeGroup = useMemo(
    () => themeGroups.find((row) => String(row.id) === mappingThemeGroupId) ?? null,
    [mappingThemeGroupId, themeGroups],
  );
  const activeThemeStocks = useMemo(() => themeStocks.filter((x) => x.is_active === 1), [themeStocks]);
  const connectedStockIdSet = useMemo(() => new Set(activeThemeStocks.map((x) => x.stock_id)), [activeThemeStocks]);
  const primaryCount = useMemo(() => activeThemeStocks.filter((x) => x.is_primary === 1).length, [activeThemeStocks]);

  const pendingCandidatesCount = useMemo(() => candidates.filter((x) => x.status === "pending").length, [candidates]);
  const activeThemesCount = useMemo(() => manageableThemes.filter((x) => x.is_active === 1).length, [manageableThemes]);
  const supplyThemesCount = useMemo(() => manageableThemes.filter((x) => x.is_supply_theme === 1).length, [manageableThemes]);
  const linkedThemesCount = useMemo(() => manageableThemes.filter((x) => x.stock_count > 0).length, [manageableThemes]);
  const themeGroupCount = useMemo(() => themes.filter((x) => x.theme_level === "THEME_GROUP").length, [themes]);

  const resetForm = () => {
    setFormThemeId(null);
    setThemeLevel("THEME");
    setParentThemeId("");
    setThemeName("");
    setThemeType("theme");
    setDescription("");
    setKeywordsText("");
    setSortOrder(100);
    setIsSupplyTheme(0);
    setIsActive(1);
  };

  const loadThemes = async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await repositories.marketThemes.list({ limit: 500 });
      setThemes(rows);
      setSelectedThemeId((prev) => {
        if (prev && rows.some((row) => row.id === prev && row.theme_level !== "THEME_GROUP")) return prev;
        return rows.find((row) => row.theme_level !== "THEME_GROUP")?.id ?? null;
      });
    } catch (e) {
      setError(toErrorMessage(e, "테마 목록을 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  };

  const loadThemeStocks = async (themeId: number | null) => {
    if (!themeId) {
      setThemeStocks([]);
      return;
    }
    try {
      const rows = await repositories.marketThemes.listThemeStocks(themeId);
      setThemeStocks(rows);
    } catch (e) {
      setError(toErrorMessage(e, "테마 연결 종목을 불러오지 못했습니다."));
      setThemeStocks([]);
    }
  };

  const loadCandidates = async () => {
    try {
      const rows = await repositories.marketThemes.listCandidates({
        status: candidateStatusFilter === "all" ? undefined : candidateStatusFilter,
        candidate_source: candidateSourceFilter === "all" ? undefined : candidateSourceFilter,
        limit: 200,
      });
      setCandidates(rows);
    } catch (e) {
      setError(toErrorMessage(e, "추천 후보 목록을 불러오지 못했습니다."));
    }
  };

  useEffect(() => {
    void Promise.all([loadThemes(), loadCandidates()]);
  }, []);

  useEffect(() => {
    void loadThemeStocks(selectedThemeId);
  }, [selectedThemeId]);

  useEffect(() => {
    setThemePage(1);
  }, [themeFilterActive, themeFilterGroupId, themeFilterKeyword, themeFilterSupply, themeFilterType, themeViewMode]);

  useEffect(() => {
    if (themePage > themeTotalPages) {
      setThemePage(themeTotalPages);
    }
  }, [themePage, themeTotalPages]);
  useEffect(() => {
    if (mappingSelectableThemes.length === 0) {
      setSelectedThemeId(null);
      return;
    }
    if (!selectedThemeId || !mappingSelectableThemes.some((row) => row.id === selectedThemeId)) {
      setSelectedThemeId(mappingSelectableThemes[0].id);
    }
  }, [mappingSelectableThemes, selectedThemeId]);

  useEffect(() => {
    void loadCandidates();
  }, [candidateSourceFilter, candidateStatusFilter]);

  const openCreateThemeModal = () => {
    resetForm();
    setThemeModalOpen(true);
  };

  const openCreateThemeInGroupModal = (themeGroupId: number) => {
    resetForm();
    setThemeLevel("THEME");
    setParentThemeId(String(themeGroupId));
    setThemeModalOpen(true);
  };

  const openEditThemeModal = (theme: MarketTheme) => {
    setFormThemeId(theme.id);
    setThemeLevel(theme.theme_level ?? "THEME");
    setParentThemeId(theme.parent_theme_id ? String(theme.parent_theme_id) : "");
    setThemeName(theme.theme_name);
    setThemeType(theme.theme_type);
    setDescription(theme.description ?? "");
    setKeywordsText(theme.keywords.join("\n"));
    setSortOrder(theme.sort_order);
    setIsSupplyTheme(theme.is_supply_theme ?? 0);
    setIsActive(theme.is_active);
    setThemeModalOpen(true);
  };

  const onSubmitTheme = async () => {
    setMessage("");
    setError("");
    if (!themeName.trim()) {
      setError("테마명은 필수입니다.");
      return;
    }
    const keywords = parseKeywordsInput(keywordsText);
    const nextThemeLevel = themeLevel;
    const nextParentThemeId = nextThemeLevel === "THEME" && parentThemeId ? Number(parentThemeId) : null;
    const nextIsSupplyTheme = nextThemeLevel === "THEME" ? isSupplyTheme : 0;
    try {
      if (formThemeId) {
        await repositories.marketThemes.update(formThemeId, {
          theme_name: themeName.trim(),
          theme_type: themeType,
          theme_level: nextThemeLevel,
          description: description.trim() || null,
          keywords,
          parent_theme_id: nextParentThemeId,
          sort_order: sortOrder,
          is_supply_theme: nextIsSupplyTheme,
          is_active: isActive,
        });
      } else {
        await repositories.marketThemes.create({
          theme_name: themeName.trim(),
          theme_type: themeType,
          theme_level: nextThemeLevel,
          description: description.trim() || null,
          keywords,
          parent_theme_id: nextParentThemeId,
          sort_order: sortOrder,
          is_supply_theme: nextIsSupplyTheme,
          is_active: isActive,
        });
      }
      await loadThemes();
      setThemeModalOpen(false);
      resetForm();
      setMessage("테마가 저장되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "테마 저장 중 오류가 발생했습니다."));
    }
  };

  const onDeactivateTheme = async (themeId: number) => {
    const ok = window.confirm("선택한 테마를 비활성화하시겠습니까?");
    if (!ok) return;
    try {
      await repositories.marketThemes.deactivate(themeId);
      await loadThemes();
      setMessage("테마가 비활성화되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "테마 비활성화 중 오류가 발생했습니다."));
    }
  };

  const onActivateTheme = async (theme: MarketTheme) => {
    const ok = window.confirm("선택한 테마를 다시 활성화하시겠습니까?");
    if (!ok) return;
    try {
      await repositories.marketThemes.update(theme.id, {
        theme_name: theme.theme_name,
        theme_type: theme.theme_type,
        theme_level: theme.theme_level,
        description: theme.description,
        keywords: theme.keywords,
        parent_theme_id: theme.parent_theme_id,
        is_supply_theme: theme.is_supply_theme,
        sort_order: theme.sort_order,
        is_active: 1,
      });
      await loadThemes();
      setMessage("테마가 활성화되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "테마 활성화 중 오류가 발생했습니다."));
    }
  };

  const toggleThemeGroupExpanded = (themeGroupId: number) => {
    setExpandedThemeGroupIds((prev) => {
      const next = new Set(prev);
      if (next.has(themeGroupId)) next.delete(themeGroupId);
      else next.add(themeGroupId);
      return next;
    });
  };

  const openThemeStockMappings = (theme: MarketTheme) => {
    if (theme.theme_level === "THEME_GROUP") {
      const firstChildTheme = sortedThemes.find((row) => row.parent_theme_id === theme.id && row.theme_level !== "THEME_GROUP" && row.is_active === 1);
      setMappingThemeGroupId(String(theme.id));
      if (firstChildTheme) setSelectedThemeId(firstChildTheme.id);
    } else {
      setMappingThemeGroupId(theme.parent_theme_id ? String(theme.parent_theme_id) : "all");
      setSelectedThemeId(theme.id);
    }
    setStockSearchResults([]);
    setActiveTab("mapping");
  };

  const onSearchStocks = async () => {
    if (!selectedThemeId) {
      setError("종목을 연결할 테마를 선택해 주세요.");
      return;
    }
    if (selectedTheme?.theme_level === "THEME_GROUP") {
      setError("종목 연결은 테마를 선택해 주세요.");
      return;
    }
    setSearching(true);
    setError("");
    try {
      const rows = await repositories.stocks.list({ keyword: stockSearchKeyword.trim(), is_active: 1, limit: 30 });
      setStockSearchResults(rows);
    } catch (e) {
      setError(toErrorMessage(e, "종목 검색 중 오류가 발생했습니다."));
    } finally {
      setSearching(false);
    }
  };

  const onAddThemeStock = async (stockId: number) => {
    if (!selectedThemeId) return;
    if (selectedTheme?.theme_level === "THEME_GROUP") {
      setError("종목은 테마에만 연결할 수 있습니다.");
      return;
    }
    try {
      await repositories.marketThemes.createThemeStock(selectedThemeId, { stock_id: stockId, is_primary: false });
      await Promise.all([loadThemeStocks(selectedThemeId), loadThemes()]);
      setMessage("테마에 종목이 연결되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "종목 연결 중 오류가 발생했습니다."));
    }
  };

  const onDeactivateMapping = async (mappingId: number) => {
    if (!selectedThemeId) return;
    const ok = window.confirm("선택한 종목을 테마에서 연결 해제하시겠습니까?");
    if (!ok) return;
    try {
      await repositories.marketThemes.deactivateThemeStock(mappingId);
      await Promise.all([loadThemeStocks(selectedThemeId), loadThemes()]);
      setMessage("테마 연결이 해제되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "연결 해제 중 오류가 발생했습니다."));
    }
  };

  const onTogglePrimary = async (mappingId: number, checked: boolean) => {
    setUpdatingPrimaryMappingId(mappingId);
    try {
      await repositories.marketThemes.updateThemeStock(mappingId, { is_primary: checked });
      await loadThemeStocks(selectedThemeId);
      setMessage("대표 여부가 변경되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "대표 변경 중 오류가 발생했습니다."));
    } finally {
      setUpdatingPrimaryMappingId(null);
    }
  };

  const onGenerateCandidates = async () => {
    setGeneratingCandidates(true);
    try {
      const result = await repositories.marketThemes.generateCandidates({
        lookback_days: lookbackDays,
        source: candidateSourceFilter,
        limit: 500,
        force: false,
      });
      await loadCandidates();
      setMessage(`추천 후보 생성 완료: ${result.generated_count}건`);
    } catch (e) {
      setError(toErrorMessage(e, "추천 후보 생성 중 오류가 발생했습니다."));
    } finally {
      setGeneratingCandidates(false);
    }
  };

  const onApproveCandidate = async (candidateId: number) => {
    await repositories.marketThemes.approveCandidate(candidateId);
    await Promise.all([loadCandidates(), loadThemes(), loadThemeStocks(selectedThemeId)]);
  };

  const onRejectCandidate = async (candidateId: number) => {
    await repositories.marketThemes.rejectCandidate(candidateId, { review_memo: "관련성 낮음" });
    await loadCandidates();
  };

  const onIgnoreCandidate = async (candidateId: number) => {
    await repositories.marketThemes.ignoreCandidate(candidateId, { review_memo: "추가 확인" });
    await loadCandidates();
  };

  return (
    <div className="space-y-4">
      <div className="journal-hero-row market-theme-hero-row">
        <section className="journal-hero-panel">
          <h1>시장 테마 관리</h1>
          <p>이슈·수급 흐름, 뉴스·공시 키워드 기반으로 테마와 연결 종목을 관리합니다.</p>
        </section>

        <section className="journal-summary-compact market-theme-hero-summary" aria-label="시장 테마 요약">
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">테마그룹</span>
            <strong className="journal-summary-value">{themeGroupCount}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">전체 테마</span>
            <strong className="journal-summary-value">{manageableThemes.length}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">활성 테마</span>
            <strong className="journal-summary-value">{activeThemesCount}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">수급 테마</span>
            <strong className="journal-summary-value">{supplyThemesCount}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">연결 종목 있음</span>
            <strong className="journal-summary-value">{linkedThemesCount}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">추천 후보</span>
            <strong className="journal-summary-value">{pendingCandidatesCount}</strong>
          </div>
        </section>
      </div>

      {message ? <div className="inline-result inline-success">{message}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}

      <SectionCard title="">
        <div className="gpt-domain-tabs">
          <button type="button" className={`gpt-domain-tab ${activeTab === "themes" ? "active" : ""}`} onClick={() => setActiveTab("themes")}>테마 목록</button>
          <button type="button" className={`gpt-domain-tab ${activeTab === "mapping" ? "active" : ""}`} onClick={() => setActiveTab("mapping")}>종목 연결</button>
          <button type="button" className={`gpt-domain-tab ${activeTab === "candidates" ? "active" : ""}`} onClick={() => setActiveTab("candidates")}>추천 후보</button>
        </div>
      </SectionCard>

      {activeTab === "themes" ? (
        <SectionCard title="테마 목록">
          <div className="theme-view-mode-tabs">
            <button type="button" className={`theme-view-mode-tab ${themeViewMode === "group" ? "active" : ""}`} onClick={() => setThemeViewMode("group")}>
              테마그룹 기준 보기
            </button>
            <button type="button" className={`theme-view-mode-tab ${themeViewMode === "theme" ? "active" : ""}`} onClick={() => setThemeViewMode("theme")}>
              테마 기준 보기
            </button>
          </div>
          <div className="market-theme-filter-toolbar">
            {themeViewMode === "theme" ? (
              <select className="select-control" value={themeFilterGroupId} onChange={(e) => setThemeFilterGroupId(e.target.value)}>
                <option value="all">테마그룹 전체</option>
                {themeGroups.map((row) => (
                  <option key={row.id} value={row.id}>{row.theme_name}</option>
                ))}
              </select>
            ) : null}
            <select className="select-control" value={themeFilterType} onChange={(e) => setThemeFilterType(e.target.value as "all" | MarketThemeType)}>
              <option value="all">유형 전체</option><option value="theme">테마</option><option value="industry">산업</option><option value="custom">커스텀</option><option value="telegram">텔레그램</option>
            </select>
            <select className="select-control" value={themeFilterActive} onChange={(e) => setThemeFilterActive(e.target.value as "all" | "1" | "0")}> 
              <option value="all">활성 전체</option><option value="1">활성</option><option value="0">비활성</option>
            </select>
            <select className="select-control" value={themeFilterSupply} onChange={(e) => setThemeFilterSupply(e.target.value as "all" | "1" | "0")}> 
              <option value="all">수급 전체</option><option value="1">수급 테마</option><option value="0">일반 테마</option>
            </select>
            <input className="input-control" placeholder="테마그룹명, 테마명 또는 키워드 검색" value={themeFilterKeyword} onChange={(e) => setThemeFilterKeyword(e.target.value)} />
            <button type="button" className="btn btn-secondary" onClick={openCreateThemeModal}>+ 테마 등록</button>
          </div>
          <div className="table-shell">
            <table className="data-table compact-table">
              {themeViewMode === "group" ? (
                <thead><tr><th>상태</th><th>테마그룹명</th><th>하위 테마</th><th>수급 테마</th><th>키워드</th><th>연결 종목</th><th>정렬</th><th>작업</th></tr></thead>
              ) : (
                <thead><tr><th>상태</th><th>테마그룹</th><th>테마명</th><th>유형</th><th>수급</th><th>키워드</th><th>연결 종목</th><th>정렬</th><th>작업</th></tr></thead>
              )}
              <tbody>
                {filteredThemes.length === 0 ? (
                  <tr><td colSpan={themeViewMode === "group" ? 8 : 9} className="text-center text-muted">조회 결과가 없습니다.</td></tr>
                ) : null}
                {themeViewMode === "group" ? pagedThemes.map((row) => {
                  const isExpanded = expandedThemeGroupIds.has(row.id);
                  const childThemes = sortedThemes.filter((theme) => theme.parent_theme_id === row.id && theme.theme_level !== "THEME_GROUP");
                  return (
                    <Fragment key={row.id}>
                      <tr className="theme-group-row" onClick={() => toggleThemeGroupExpanded(row.id)}>
                        <td>{row.is_active === 1 ? <StatusBadge label="활성" tone="emerald" /> : <StatusBadge label="비활성" tone="slate" />}</td>
                        <td><button type="button" className="theme-expand-button" onClick={(e) => { e.stopPropagation(); toggleThemeGroupExpanded(row.id); }}>{isExpanded ? "접기" : "펼치기"}</button> {row.theme_name}</td>
                        <td><span className="badge badge-slate">{row.child_theme_count ?? childThemes.length}개</span></td>
                        <td><span className="badge badge-blue">{row.supply_child_theme_count ?? childThemes.filter((x) => x.is_supply_theme === 1).length}개</span></td>
                        <td><span className="badge badge-slate">{row.keyword_count ?? row.keywords.length}개</span></td>
                        <td>
                          <button
                            type="button"
                            className="theme-stock-count-link"
                            onClick={(e) => { e.stopPropagation(); openThemeStockMappings(row); }}
                          >
                            {row.linked_stock_count ?? row.stock_count}개
                          </button>
                        </td>
                        <td>{row.sort_order}</td>
                        <td>
                          <div className="theme-group-actions">
                            <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); openEditThemeModal(row); }}>수정</button>
                            <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); openCreateThemeInGroupModal(row.id); }}>테마 추가</button>
                            {row.is_active === 1 ? (
                              <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onDeactivateTheme(row.id); }}>비활성화</button>
                            ) : (
                              <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onActivateTheme(row); }}>활성화</button>
                            )}
                          </div>
                        </td>
                      </tr>
                      {isExpanded ? childThemes.map((child) => (
                        <tr key={`${row.id}-${child.id}`} className="theme-child-row" onClick={() => setSelectedThemeId(child.id)}>
                          <td>{child.is_active === 1 ? <StatusBadge label="활성" tone="emerald" /> : <StatusBadge label="비활성" tone="slate" />}</td>
                          <td colSpan={2}>{child.theme_name}</td>
                          <td>{child.is_supply_theme === 1 ? <span className="badge badge-blue">수급</span> : "-"}</td>
                          <td><span className="badge badge-slate">{child.keywords.length}개</span></td>
                          <td>
                            <button
                              type="button"
                              className="theme-stock-count-link"
                              onClick={(e) => { e.stopPropagation(); openThemeStockMappings(child); }}
                            >
                              {child.stock_count}개
                            </button>
                          </td>
                          <td>{child.sort_order}</td>
                          <td>
                            <div className="theme-group-actions">
                              <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); openEditThemeModal(child); }}>수정</button>
                              {child.is_active === 1 ? (
                                <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onDeactivateTheme(child.id); }}>비활성화</button>
                              ) : (
                                <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onActivateTheme(child); }}>활성화</button>
                              )}
                            </div>
                          </td>
                        </tr>
                      )) : null}
                    </Fragment>
                  );
                }) : pagedThemes.map((row) => (
                  <tr key={row.id} onClick={() => setSelectedThemeId(row.id)}>
                    <td>{row.is_active === 1 ? <StatusBadge label="활성" tone="emerald" /> : <StatusBadge label="비활성" tone="slate" />}</td>
                    <td>{row.parent_theme_name ?? <span className="text-muted">미지정</span>}</td>
                    <td>{row.theme_name}</td><td>{themeTypeLabel(row.theme_type)}</td><td>{row.is_supply_theme === 1 ? <span className="badge badge-blue">수급</span> : "-"}</td>
                    <td><span className="badge badge-slate">{row.keywords.length}개</span></td>
                    <td>
                      <button
                        type="button"
                        className="theme-stock-count-link"
                        onClick={(e) => { e.stopPropagation(); openThemeStockMappings(row); }}
                      >
                        {row.stock_count}개
                      </button>
                    </td>
                    <td>{row.sort_order}</td>
                    <td>
                      <div className="theme-group-actions">
                        <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); openEditThemeModal(row); }}>수정</button>
                        {row.is_active === 1 ? (
                          <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onDeactivateTheme(row.id); }}>비활성화</button>
                        ) : (
                          <button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onActivateTheme(row); }}>활성화</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination-bar">
            <span className="pagination-info">              {`이번 페이지 ${themePageStart}-${themePageEnd} / 전체 ${filteredThemes.length}건 - 20개씩 표시`}
            </span>
            <div className="pagination-actions">
              <button
                type="button"
                className="btn btn-secondary btn-table-sm"
                disabled={safeThemePage <= 1}
                onClick={() => setThemePage((prev) => Math.max(1, prev - 1))}
              >
                이전
              </button>
              <span className="pagination-info">{`${safeThemePage} / ${themeTotalPages}`}</span>
              <button
                type="button"
                className="btn btn-secondary btn-table-sm"
                disabled={safeThemePage >= themeTotalPages}
                onClick={() => setThemePage((prev) => Math.min(themeTotalPages, prev + 1))}
              >
                다음
              </button>
            </div>
          </div>
        </SectionCard>
      ) : null}

      {activeTab === "mapping" ? (
        <div className="space-y-4">
          <SectionCard title="종목 연결">
            <div className="market-theme-mapping-toolbar">
              <select className="select-control" value={mappingThemeGroupId} onChange={(e) => setMappingThemeGroupId(e.target.value)}>
                <option value="all">테마그룹 전체</option>
                {themeGroups.filter((x) => x.is_active === 1).map((row) => <option key={row.id} value={row.id}>{row.theme_name}</option>)}
              </select>
              <select className="select-control" value={selectedThemeId ?? ""} onChange={(e) => setSelectedThemeId(e.target.value ? Number(e.target.value) : null)}>
                {mappingSelectableThemes.map((row) => (
                  <option key={row.id} value={row.id}>{row.is_supply_theme === 1 ? `[수급] ${row.theme_name}` : row.theme_name}</option>
                ))}
              </select>
              <input className="input-control" placeholder="종목명 또는 종목코드 검색" value={stockSearchKeyword} onChange={(e) => setStockSearchKeyword(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void onSearchStocks(); } }} />
              <button type="button" className="btn btn-secondary" onClick={() => void onSearchStocks()} disabled={searching || !selectedThemeId}>{searching ? "검색 중..." : "검색"}</button>
            </div>

            <div className="table-shell max-h-[300px] overflow-auto mt-3">
              <table className="data-table compact-table">
                <thead><tr><th>종목</th><th>시장</th><th>추가</th></tr></thead>
                <tbody>
                  {!selectedThemeId ? <tr><td colSpan={3} className="text-center text-muted">테마를 선택해 주세요.</td></tr> : null}
                  {selectedThemeId && stockSearchResults.length === 0 ? <tr><td colSpan={3} className="text-center text-muted">종목을 검색해 주세요.</td></tr> : null}
                  {stockSearchResults.map((row) => {
                    const alreadyLinked = connectedStockIdSet.has(row.id);
                    return (
                      <tr key={row.id}>
                        <td><div className="stock-cell"><strong>{row.stock_name}</strong><span>{row.stock_code}</span></div></td>
                        <td>{row.market ?? "-"}</td>
                        <td>{alreadyLinked ? <button type="button" className="btn btn-secondary btn-table-sm" disabled>연결됨</button> : <button type="button" className="btn btn-primary btn-table-sm" onClick={() => void onAddThemeStock(row.id)}>추가</button>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </SectionCard>

          <SectionCard title={`연결 종목 목록${selectedTheme ? ` - ${selectedThemeGroup ? `${selectedThemeGroup.theme_name} / ` : ""}${selectedTheme.theme_name}` : ""} (${activeThemeStocks.length}종목 · 대표 ${primaryCount})`}>
            <div className="table-shell">
              <table className="data-table compact-table">
                <thead><tr><th>종목</th><th>시장</th><th>대표</th><th>출처</th><th>신뢰도</th><th>상태</th><th>작업</th></tr></thead>
                <tbody>
                  {activeThemeStocks.map((row) => (
                    <tr key={row.mapping_id}>
                      <td><div className="stock-cell"><strong>{row.stock_name}</strong><span>{row.stock_code}</span></div></td>
                      <td>{row.market ?? "-"}</td>
                      <td><label className="inline-flex items-center gap-2"><input type="checkbox" checked={row.is_primary === 1} disabled={updatingPrimaryMappingId === row.mapping_id} onChange={(e) => void onTogglePrimary(row.mapping_id, e.target.checked)} /><span>{row.is_primary === 1 ? "대표" : "일반"}</span></label></td>
                      <td>{sourceLabel(row.mapping_source)}</td><td>{row.confidence_score ?? "-"}</td><td>{row.is_active === 1 ? "활성" : "비활성"}</td>
                      <td><button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void onDeactivateMapping(row.mapping_id)}>해제</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "candidates" ? (
        <SectionCard title="추천 후보">
          <div className="theme-candidate-toolbar">
            <div className="theme-candidate-lookback-group">
              <span className="theme-candidate-lookback-label">최근 기간(일)</span>
              <input className="input-control theme-candidate-lookback-input" type="number" min={1} max={30} value={lookbackDays} onChange={(e) => setLookbackDays(Number(e.target.value) || 7)} />
            </div>
            <select className="select-control theme-candidate-select" value={candidateSourceFilter} onChange={(e) => setCandidateSourceFilter(e.target.value as "all" | "news" | "disclosure")}>
              <option value="all">출처 전체</option>
              <option value="news">뉴스</option>
              <option value="disclosure">공시</option>
            </select>
            <select className="select-control theme-candidate-select" value={candidateStatusFilter} onChange={(e) => setCandidateStatusFilter(e.target.value as "all" | MarketThemeCandidateStatus)}>
              <option value="all">상태 전체</option>
              <option value="pending">승인 대기</option>
              <option value="approved">승인 완료</option>
              <option value="rejected">거절</option>
              <option value="ignored">보류</option>
            </select>
            <button type="button" className="btn btn-primary" onClick={() => void onGenerateCandidates()} disabled={generatingCandidates}>{generatingCandidates ? "생성 중..." : "뉴스·공시 후보 생성"}</button>
            <button type="button" className="btn btn-secondary" onClick={() => void loadCandidates()}>새로고침</button>
          </div>

          <div className="table-shell max-h-[420px] overflow-auto mt-3">
            <table className="data-table compact-table">
              <thead><tr><th>추천 테마</th><th>추천 종목</th><th>출처</th><th>신뢰도</th><th>매칭 키워드</th><th>근거</th><th>상태</th><th>작업</th></tr></thead>
              <tbody>
                {candidates.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="text-center text-muted">추천 후보가 없습니다.</td>
                  </tr>
                ) : null}
                {candidates.map((row) => (
                  <tr key={row.id}>
                    <td><span className="badge badge-slate">{row.theme_name}</span></td>
                    <td><div className="stock-cell"><strong>{row.stock_name}</strong><span>{row.stock_code}</span></div></td>
                    <td><span className={`badge ${row.candidate_source === "news" ? "badge-blue" : "badge-slate"}`}>{sourceLabel(row.candidate_source)}</span></td>
                    <td>{row.confidence_score == null ? "-" : <span className="badge badge-neutral">{row.confidence_score}</span>}</td>
                    <td>
                      <div className="candidate-keyword-chips">
                        {row.matched_keywords.length > 0 ? row.matched_keywords.map((keyword) => (
                          <span key={`${row.id}-${keyword}`} className="badge badge-slate">{keyword}</span>
                        )) : <span>-</span>}
                      </div>
                    </td>
                    <td><span className="badge badge-slate">{row.evidence_count}건</span></td>
                    <td>
                      <span className={`badge ${row.status === "approved" ? "badge-emerald" : row.status === "rejected" ? "badge-rose" : row.status === "ignored" ? "badge-neutral" : "badge-amber"}`}>
                        {statusLabel(row.status)}
                      </span>
                    </td>
                    <td><div className="theme-group-actions"><button type="button" className="btn btn-primary btn-table-sm" onClick={() => void onApproveCandidate(row.id)}>승인</button><button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void onRejectCandidate(row.id)}>거절</button><button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void onIgnoreCandidate(row.id)}>보류</button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}

      {themeModalOpen ? (
        <div className="modal-backdrop">
          <div className="modal-card watchlist-theme-modal">
            <div className="trade-journal-detail-header">
              <h3>{formThemeId ? `${themeLevelLabel(themeLevel)} 수정` : `${themeLevelLabel(themeLevel)} 등록`}</h3>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setThemeModalOpen(false)}>닫기</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="space-y-1">
                <span>구분</span>
                <select className="select-control" value={themeLevel} onChange={(e) => {
                  const nextLevel = e.target.value as MarketThemeLevel;
                  setThemeLevel(nextLevel);
                  if (nextLevel === "THEME_GROUP") setParentThemeId("");
                }}>
                  <option value="THEME_GROUP">테마그룹</option>
                  <option value="THEME">테마</option>
                </select>
              </label>
              {themeLevel === "THEME" ? (
                <label className="space-y-1">
                  <span>상위 테마그룹</span>
                  <select className="select-control" value={parentThemeId} onChange={(e) => setParentThemeId(e.target.value)}>
                    <option value="">미지정</option>
                    {themeGroups.filter((row) => row.id !== formThemeId).map((row) => (
                      <option key={row.id} value={row.id}>{row.theme_name}</option>
                    ))}
                  </select>
                </label>
              ) : null}
              <label className="space-y-1"><span>{themeLevel === "THEME_GROUP" ? "테마그룹명" : "테마명"}</span><input className="input-control" value={themeName} onChange={(e) => setThemeName(e.target.value)} /></label>
              <label className="space-y-1"><span>유형</span><select className="select-control" value={themeType} onChange={(e) => setThemeType(e.target.value as MarketThemeType)}><option value="theme">테마</option><option value="industry">산업</option><option value="custom">커스텀</option><option value="telegram">텔레그램</option></select></label>
              <label className="space-y-1"><span>정렬 순서</span><input className="input-control" type="number" value={sortOrder} onChange={(e) => setSortOrder(Number(e.target.value) || 0)} /></label>
              <label className="space-y-1"><span>활성 여부</span><select className="select-control" value={isActive} onChange={(e) => setIsActive(Number(e.target.value))}><option value={1}>활성</option><option value={0}>비활성</option></select></label>
              <label className="space-y-1 md:col-span-2"><span>설명</span><input className="input-control" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
              {themeLevel === "THEME" ? (
                <label className="space-y-1"><span>수급테마 여부</span><select className="select-control" value={isSupplyTheme} onChange={(e) => setIsSupplyTheme(Number(e.target.value))}><option value={0}>일반 테마</option><option value={1}>수급 테마</option></select></label>
              ) : null}
              <label className="space-y-1 md:col-span-2"><span>키워드(줄바꿈/쉼표 구분)</span><textarea className="input-control min-h-[120px]" value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)} /></label>
            </div>
            <div className="watchlist-theme-modal-actions">
              <button type="button" className="btn btn-primary" onClick={() => void onSubmitTheme()}>저장</button>
              <button type="button" className="btn btn-secondary" onClick={resetForm}>초기화</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default MarketThemesPage;
