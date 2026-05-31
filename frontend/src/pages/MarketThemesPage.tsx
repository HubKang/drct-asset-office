import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type {
  MarketTheme,
  MarketThemeCandidate,
  MarketThemeCandidateStatus,
  MarketThemeStock,
  MarketThemeType,
} from "@/types/marketTheme";
import type { Stock } from "@/types/stock";

type ActiveTab = "themes" | "mapping" | "candidates";

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
  if (source === "news") return "뉴스";
  if (source === "disclosure") return "공시";
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
        if (b.is_supply_theme !== a.is_supply_theme) return b.is_supply_theme - a.is_supply_theme;
        if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
        return a.theme_name.localeCompare(b.theme_name, "ko-KR");
      }),
    [themes],
  );

  const filteredThemes = useMemo(() => {
    const keyword = themeFilterKeyword.trim().toLowerCase();
    return sortedThemes.filter((row) => {
      if (themeFilterType !== "all" && row.theme_type !== themeFilterType) return false;
      if (themeFilterActive !== "all" && String(row.is_active) !== themeFilterActive) return false;
      if (themeFilterSupply !== "all" && String(row.is_supply_theme) !== themeFilterSupply) return false;
      if (!keyword) return true;
      return row.theme_name.toLowerCase().includes(keyword) || row.keywords.join(" ").toLowerCase().includes(keyword);
    });
  }, [sortedThemes, themeFilterActive, themeFilterKeyword, themeFilterSupply, themeFilterType]);

  const selectedTheme = useMemo(() => sortedThemes.find((x) => x.id === selectedThemeId) ?? null, [sortedThemes, selectedThemeId]);
  const activeThemeStocks = useMemo(() => themeStocks.filter((x) => x.is_active === 1), [themeStocks]);
  const connectedStockIdSet = useMemo(() => new Set(activeThemeStocks.map((x) => x.stock_id)), [activeThemeStocks]);
  const primaryCount = useMemo(() => activeThemeStocks.filter((x) => x.is_primary === 1).length, [activeThemeStocks]);

  const pendingCandidatesCount = useMemo(() => candidates.filter((x) => x.status === "pending").length, [candidates]);
  const activeThemesCount = useMemo(() => themes.filter((x) => x.is_active === 1).length, [themes]);
  const supplyThemesCount = useMemo(() => themes.filter((x) => x.is_supply_theme === 1).length, [themes]);
  const linkedThemesCount = useMemo(() => themes.filter((x) => x.stock_count > 0).length, [themes]);

  const resetForm = () => {
    setFormThemeId(null);
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
      setSelectedThemeId((prev) => prev ?? rows[0]?.id ?? null);
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
    void loadCandidates();
  }, [candidateSourceFilter, candidateStatusFilter]);

  const openCreateThemeModal = () => {
    resetForm();
    setThemeModalOpen(true);
  };

  const openEditThemeModal = (theme: MarketTheme) => {
    setFormThemeId(theme.id);
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
    try {
      if (formThemeId) {
        await repositories.marketThemes.update(formThemeId, {
          theme_name: themeName.trim(),
          theme_type: themeType,
          description: description.trim() || null,
          keywords,
          sort_order: sortOrder,
          is_supply_theme: isSupplyTheme,
          is_active: isActive,
        });
      } else {
        await repositories.marketThemes.create({
          theme_name: themeName.trim(),
          theme_type: themeType,
          description: description.trim() || null,
          keywords,
          sort_order: sortOrder,
          is_supply_theme: isSupplyTheme,
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

  const onSearchStocks = async () => {
    if (!selectedThemeId) {
      setError("종목을 연결할 테마를 선택해 주세요.");
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
      <PageHeader title="시장 테마 관리" description="이슈·수급 흐름, 뉴스·공시 키워드 기반으로 테마와 연결 종목을 관리합니다." />

      <div className="watchlist-top-stats">
        <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">전체 테마</p><strong className="watchlist-top-stat-value">{themes.length}</strong></div>
        <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">활성 테마</p><strong className="watchlist-top-stat-value">{activeThemesCount}</strong></div>
        <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">수급 테마</p><strong className="watchlist-top-stat-value">{supplyThemesCount}</strong></div>
        <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">연결 종목 있음</p><strong className="watchlist-top-stat-value">{linkedThemesCount}</strong></div>
        <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">추천 후보</p><strong className="watchlist-top-stat-value">{pendingCandidatesCount}</strong></div>
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
          <div className="market-theme-filter-toolbar">
            <select className="select-control" value={themeFilterType} onChange={(e) => setThemeFilterType(e.target.value as "all" | MarketThemeType)}>
              <option value="all">유형 전체</option><option value="theme">테마</option><option value="industry">산업</option><option value="custom">커스텀</option><option value="telegram">텔레그램</option>
            </select>
            <select className="select-control" value={themeFilterActive} onChange={(e) => setThemeFilterActive(e.target.value as "all" | "1" | "0")}> 
              <option value="all">활성 전체</option><option value="1">활성</option><option value="0">비활성</option>
            </select>
            <select className="select-control" value={themeFilterSupply} onChange={(e) => setThemeFilterSupply(e.target.value as "all" | "1" | "0")}> 
              <option value="all">수급 전체</option><option value="1">수급 테마</option><option value="0">일반 테마</option>
            </select>
            <input className="input-control" placeholder="테마명 또는 키워드 검색" value={themeFilterKeyword} onChange={(e) => setThemeFilterKeyword(e.target.value)} />
            <button type="button" className="btn btn-secondary" onClick={openCreateThemeModal}>+ 테마 등록</button>
          </div>
          <div className="table-shell">
            <table className="data-table compact-table">
              <thead><tr><th>상태</th><th>테마명</th><th>유형</th><th>수급</th><th>키워드</th><th>연결 종목</th><th>정렬</th><th>작업</th></tr></thead>
              <tbody>
                {filteredThemes.map((row) => (
                  <tr key={row.id} onClick={() => setSelectedThemeId(row.id)}>
                    <td>{row.is_active === 1 ? <StatusBadge label="활성" tone="emerald" /> : <StatusBadge label="비활성" tone="slate" />}</td>
                    <td>{row.theme_name}</td><td>{themeTypeLabel(row.theme_type)}</td><td>{row.is_supply_theme === 1 ? <span className="badge badge-blue">수급</span> : "-"}</td>
                    <td><span className="badge badge-slate">{row.keywords.length}개</span></td><td><span className="badge badge-slate">{row.stock_count}개</span></td><td>{row.sort_order}</td>
                    <td><div className="theme-group-actions"><button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); openEditThemeModal(row); }}>수정</button><button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void onDeactivateTheme(row.id); }}>비활성화</button></div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}

      {activeTab === "mapping" ? (
        <div className="space-y-4">
          <SectionCard title="종목 연결">
            <div className="market-theme-mapping-toolbar">
              <select className="select-control" value={selectedThemeId ?? ""} onChange={(e) => setSelectedThemeId(e.target.value ? Number(e.target.value) : null)}>
                {sortedThemes.filter((x) => x.is_active === 1).map((row) => <option key={row.id} value={row.id}>{row.is_supply_theme === 1 ? `[수급] ${row.theme_name}` : row.theme_name}</option>)}
              </select>
              <input className="input-control" value={stockSearchKeyword} onChange={(e) => setStockSearchKeyword(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); void onSearchStocks(); } }} />
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

          <SectionCard title={`연결 종목 목록${selectedTheme ? ` - ${selectedTheme.theme_name}` : ""} (${activeThemeStocks.length}종목 · 대표 ${primaryCount})`}>
            <div className="table-shell">
              <table className="data-table compact-table">
                <thead><tr><th>종목</th><th>시장</th><th>대표</th><th>출처</th><th>신뢰도</th><th>상태</th><th>작업</th></tr></thead>
                <tbody>
                  {activeThemeStocks.map((row) => (
                    <tr key={row.mapping_id}>
                      <td><div className="stock-cell"><strong>{row.stock_name}</strong><span>{row.stock_code}</span></div></td>
                      <td>{row.market ?? "-"}</td>
                      <td><label className="inline-flex items-center gap-2"><input type="checkbox" checked={row.is_primary === 1} disabled={updatingPrimaryMappingId === row.mapping_id} onChange={(e) => void onTogglePrimary(row.mapping_id, e.target.checked)} /><span>{row.is_primary === 1 ? "대표" : "일반"}</span></label></td>
                      <td>{row.mapping_source}</td><td>{row.confidence_score ?? "-"}</td><td>{row.is_active === 1 ? "활성" : "비활성"}</td>
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
        <div className="modal-backdrop" onClick={() => setThemeModalOpen(false)}>
          <div className="modal-card watchlist-theme-modal" onClick={(e) => e.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <h3>{formThemeId ? "테마 수정" : "테마 등록"}</h3>
              <button className="btn btn-secondary btn-table-sm" onClick={() => setThemeModalOpen(false)}>닫기</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="space-y-1"><span>테마명</span><input className="input-control" value={themeName} onChange={(e) => setThemeName(e.target.value)} /></label>
              <label className="space-y-1"><span>유형</span><select className="select-control" value={themeType} onChange={(e) => setThemeType(e.target.value as MarketThemeType)}><option value="theme">테마</option><option value="industry">산업</option><option value="custom">커스텀</option><option value="telegram">텔레그램</option></select></label>
              <label className="space-y-1"><span>정렬 순서</span><input className="input-control" type="number" value={sortOrder} onChange={(e) => setSortOrder(Number(e.target.value) || 0)} /></label>
              <label className="space-y-1"><span>활성 여부</span><select className="select-control" value={isActive} onChange={(e) => setIsActive(Number(e.target.value))}><option value={1}>활성</option><option value={0}>비활성</option></select></label>
              <label className="space-y-1 md:col-span-2"><span>설명</span><input className="input-control" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
              <label className="space-y-1"><span>수급테마 여부</span><select className="select-control" value={isSupplyTheme} onChange={(e) => setIsSupplyTheme(Number(e.target.value))}><option value={0}>일반 테마</option><option value={1}>수급 테마</option></select></label>
              <label className="space-y-1 md:col-span-2"><span>키워드(줄바꿈/쉼표 구분)</span><textarea className="input-control min-h-[120px]" value={keywordsText} onChange={(e) => setKeywordsText(e.target.value)} /></label>
            </div>
            <div className="watchlist-theme-modal-actions">
              <button className="btn btn-primary" onClick={() => void onSubmitTheme()}>저장</button>
              <button className="btn btn-secondary" onClick={resetForm}>초기화</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default MarketThemesPage;
