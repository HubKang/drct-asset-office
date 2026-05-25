import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type {
  MarketTheme,
  MarketThemeCandidate,
  MarketThemeCandidateStatus,
  MarketThemeType,
  MarketThemeStock,
} from "@/types/marketTheme";
import type { Stock } from "@/types/stock";

type ActiveTab = "theme" | "mapping";

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
  if (status === "approved") return "승인됨";
  if (status === "rejected") return "거절됨";
  return "보류";
}

function MarketThemesPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("theme");

  const [themes, setThemes] = useState<MarketTheme[]>([]);
  const [selectedThemeId, setSelectedThemeId] = useState<number | null>(null);
  const [themeStocks, setThemeStocks] = useState<MarketThemeStock[]>([]);
  const [candidates, setCandidates] = useState<MarketThemeCandidate[]>([]);

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

  const [formThemeId, setFormThemeId] = useState<number | null>(null);
  const [themeName, setThemeName] = useState("");
  const [themeCode, setThemeCode] = useState("");
  const [themeType, setThemeType] = useState<MarketThemeType>("theme");
  const [description, setDescription] = useState("");
  const [keywordsText, setKeywordsText] = useState("");
  const [sortOrder, setSortOrder] = useState(0);
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

  const selectedTheme = useMemo(
    () => sortedThemes.find((x) => x.id === selectedThemeId) ?? null,
    [sortedThemes, selectedThemeId],
  );

  const activeThemeStocks = useMemo(
    () => themeStocks.filter((row) => row.is_active === 1),
    [themeStocks],
  );

  const resetForm = () => {
    setFormThemeId(null);
    setThemeName("");
    setThemeCode("");
    setThemeType("theme");
    setDescription("");
    setKeywordsText("");
    setSortOrder(0);
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
      setError(toErrorMessage(e, "후보 목록을 불러오지 못했습니다."));
    }
  };

  useEffect(() => {
    void loadThemes();
  }, []);

  useEffect(() => {
    void loadThemeStocks(selectedThemeId);
  }, [selectedThemeId]);

  useEffect(() => {
    void loadCandidates();
  }, [candidateStatusFilter, candidateSourceFilter]);

  const onEditTheme = (theme: MarketTheme) => {
    setFormThemeId(theme.id);
    setThemeName(theme.theme_name);
    setThemeCode(theme.theme_code);
    setThemeType(theme.theme_type);
    setDescription(theme.description ?? "");
    setKeywordsText(theme.keywords.join("\n"));
    setSortOrder(theme.sort_order);
    setIsSupplyTheme(theme.is_supply_theme ?? 0);
    setIsActive(theme.is_active);
    setMessage("");
    setError("");
  };

  const onSubmitTheme = async () => {
    setMessage("");
    setError("");

    if (!themeName.trim()) {
      setError("테마명은 필수입니다.");
      return;
    }
    if (!formThemeId && !themeCode.trim()) {
      setError("테마 코드는 필수입니다.");
      return;
    }

    const keywords = parseKeywordsInput(keywordsText);
    if (keywords.length === 0) {
      setError("키워드를 입력해 주세요.");
      return;
    }

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
          theme_code: themeCode.trim(),
          theme_type: themeType,
          description: description.trim() || null,
          keywords,
          sort_order: sortOrder,
          is_supply_theme: isSupplyTheme,
          is_active: isActive,
        });
      }
      await loadThemes();
      setMessage("테마가 저장되었습니다.");
      resetForm();
    } catch (e) {
      setError(toErrorMessage(e, "테마 저장 중 오류가 발생했습니다."));
    }
  };

  const onDeactivateTheme = async (themeId: number) => {
    setMessage("");
    setError("");
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
      const rows = await repositories.stocks.list({
        keyword: stockSearchKeyword.trim(),
        is_active: 1,
        limit: 30,
      });
      setStockSearchResults(rows);
    } catch (e) {
      setError(toErrorMessage(e, "종목 검색 중 오류가 발생했습니다."));
    } finally {
      setSearching(false);
    }
  };

  const onAddThemeStock = async (stockId: number) => {
    if (!selectedThemeId) {
      setError("테마를 먼저 선택해 주세요.");
      return;
    }

    setMessage("");
    setError("");
    try {
      await repositories.marketThemes.createThemeStock(selectedThemeId, {
        stock_id: stockId,
        is_primary: false,
      });
      await loadThemeStocks(selectedThemeId);
      await loadThemes();
      setMessage("종목이 테마에 추가되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "종목 추가 중 오류가 발생했습니다."));
    }
  };

  const onDeactivateMapping = async (mappingId: number) => {
    if (!selectedThemeId) return;

    const ok = window.confirm("이 종목을 해당 테마에서 연결 해제하시겠습니까?");
    if (!ok) return;

    const previousRows = themeStocks;
    setThemeStocks((prev) => prev.filter((row) => row.mapping_id !== mappingId));

    setMessage("");
    setError("");
    try {
      await repositories.marketThemes.deactivateThemeStock(mappingId);
      await loadThemeStocks(selectedThemeId);
      await loadThemes();
      setMessage("테마 연결이 삭제되었습니다.");
    } catch (e) {
      setThemeStocks(previousRows);
      setError(toErrorMessage(e, "종목 연결 해제 중 오류가 발생했습니다."));
    }
  };

  const onTogglePrimary = async (mappingId: number, checked: boolean) => {
    if (!selectedThemeId) return;

    const previousRows = themeStocks;
    setThemeStocks((prev) =>
      prev.map((row) =>
        row.mapping_id === mappingId
          ? {
              ...row,
              is_primary: checked ? 1 : 0,
            }
          : row,
      ),
    );
    setUpdatingPrimaryMappingId(mappingId);
    setMessage("");
    setError("");

    try {
      await repositories.marketThemes.updateThemeStock(mappingId, {
        is_primary: checked,
      });
      await loadThemeStocks(selectedThemeId);
      setMessage("대표 여부가 변경되었습니다.");
    } catch (e) {
      setThemeStocks(previousRows);
      setError(toErrorMessage(e, "대표 여부 변경에 실패했습니다."));
    } finally {
      setUpdatingPrimaryMappingId(null);
    }
  };

  const onGenerateCandidates = async () => {
    setGeneratingCandidates(true);
    setMessage("");
    setError("");
    try {
      const result = await repositories.marketThemes.generateCandidates({
        lookback_days: lookbackDays,
        source: candidateSourceFilter,
        limit: 500,
        force: false,
      });
      await loadCandidates();
      setMessage(
        `테마 후보 생성이 완료되었습니다. 생성: ${result.generated_count}건, 갱신: ${result.updated_count}건`,
      );
    } catch (e) {
      setError(toErrorMessage(e, "후보 생성 중 오류가 발생했습니다."));
    } finally {
      setGeneratingCandidates(false);
    }
  };

  const onApproveCandidate = async (candidateId: number) => {
    setMessage("");
    setError("");
    try {
      await repositories.marketThemes.approveCandidate(candidateId);
      await Promise.all([loadCandidates(), loadThemes(), loadThemeStocks(selectedThemeId)]);
      setMessage("후보가 정식 테마 매핑으로 승인되었습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "후보 승인 중 오류가 발생했습니다."));
    }
  };

  const onRejectCandidate = async (candidateId: number) => {
    setMessage("");
    setError("");
    try {
      await repositories.marketThemes.rejectCandidate(candidateId, {
        review_memo: "관련성이 낮음",
      });
      await loadCandidates();
      setMessage("후보를 거절했습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "후보 거절 중 오류가 발생했습니다."));
    }
  };

  const onIgnoreCandidate = async (candidateId: number) => {
    setMessage("");
    setError("");
    try {
      await repositories.marketThemes.ignoreCandidate(candidateId, {
        review_memo: "추가 확인 필요",
      });
      await loadCandidates();
      setMessage("후보를 보류했습니다.");
    } catch (e) {
      setError(toErrorMessage(e, "후보 보류 중 오류가 발생했습니다."));
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="시장 테마 관리"
        description="시장 테마 등록, 수동 매핑, 자동 추천 후보를 통합 관리합니다."
      />

      {message ? <div className="inline-result">{message}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}

      <SectionCard title="">
        <div className="border-b border-slate-200">
          <nav className="flex flex-wrap items-center gap-6">
          <button
            type="button"
              className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                activeTab === "theme"
                  ? "border-slate-900 font-semibold text-slate-900"
                  : "border-transparent font-medium text-slate-500 hover:text-slate-900"
              }`}
            onClick={() => setActiveTab("theme")}
          >
            테마 관리
          </button>
          <button
            type="button"
              className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                activeTab === "mapping"
                  ? "border-slate-900 font-semibold text-slate-900"
                  : "border-transparent font-medium text-slate-500 hover:text-slate-900"
              }`}
            onClick={() => setActiveTab("mapping")}
          >
            종목 연결 관리
          </button>
          </nav>
        </div>
      </SectionCard>

      {activeTab === "theme" ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 xl:grid-cols-[6fr_4fr] gap-4 items-stretch">
            <SectionCard title="테마 목록" className="h-full">
              {loading ? <p className="text-sm text-muted">로딩 중...</p> : null}
              <div className="table-shell h-[520px] overflow-auto">
                <table className="data-table compact-table">
                  <thead>
                    <tr>
                      <th>테마명</th>
                      <th>유형</th>
                      <th>수급</th>
                      <th>키워드 수</th>
                      <th>연결 종목 수</th>
                      <th>활성</th>
                      <th>작업</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedThemes.map((row) => (
                      <tr
                        key={row.id}
                        className={selectedThemeId === row.id ? "bg-blue-50" : ""}
                        onClick={() => setSelectedThemeId(row.id)}
                      >
                        <td>{row.theme_name}</td>
                        <td>{row.theme_type}</td>
                        <td>{row.is_supply_theme === 1 ? "수급" : "-"}</td>
                        <td>{row.keywords.length}</td>
                        <td>{row.stock_count}</td>
                        <td>{row.is_active === 1 ? "활성" : "비활성"}</td>
                        <td>
                          <div className="flex gap-1">
                            <button
                              type="button"
                              className="btn btn-secondary"
                              onClick={(e) => {
                                e.stopPropagation();
                                onEditTheme(row);
                              }}
                            >
                              수정
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary"
                              onClick={(e) => {
                                e.stopPropagation();
                                void onDeactivateTheme(row.id);
                              }}
                            >
                              비활성
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {themes.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="text-center text-muted">
                          데이터가 없습니다.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </SectionCard>

            <SectionCard title={formThemeId ? "테마 수정" : "테마 등록/수정"} className="h-full">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="space-y-1">
                  <span>테마명</span>
                  <input className="input-control" value={themeName} onChange={(e) => setThemeName(e.target.value)} />
                </label>
                <label className="space-y-1">
                  <span>테마 코드</span>
                  <input
                    className="input-control"
                    value={themeCode}
                    disabled={Boolean(formThemeId)}
                    onChange={(e) => setThemeCode(e.target.value)}
                  />
                </label>
                <label className="space-y-1">
                  <span>유형</span>
                  <select
                    className="select-control"
                    value={themeType}
                    onChange={(e) => setThemeType(e.target.value as MarketThemeType)}
                  >
                    <option value="industry">industry</option>
                    <option value="theme">theme</option>
                    <option value="custom">custom</option>
                    <option value="telegram">telegram</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span>정렬 순서</span>
                  <input
                    className="input-control"
                    type="number"
                    value={sortOrder}
                    onChange={(e) => setSortOrder(Number(e.target.value) || 0)}
                  />
                </label>
                <label className="space-y-1 md:col-span-2">
                  <span>설명</span>
                  <input
                    className="input-control"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </label>
                <label className="space-y-1 md:col-span-2">
                  <span>키워드(줄바꿈 또는 쉼표 구분)</span>
                  <textarea
                    className="input-control min-h-[120px]"
                    value={keywordsText}
                    onChange={(e) => setKeywordsText(e.target.value)}
                  />
                </label>
                <label className="space-y-1">
                  <span>활성 여부</span>
                  <select className="select-control" value={isActive} onChange={(e) => setIsActive(Number(e.target.value))}>
                    <option value={1}>활성</option>
                    <option value={0}>비활성</option>
                  </select>
                </label>
                <label className="space-y-1">
                  <span>수급테마 여부</span>
                  <select
                    className="select-control"
                    value={isSupplyTheme}
                    onChange={(e) => setIsSupplyTheme(Number(e.target.value))}
                  >
                    <option value={0}>일반 테마</option>
                    <option value={1}>수급테마</option>
                  </select>
                </label>
                <p className="text-xs text-muted md:col-span-2">
                  수급테마로 지정하면 테마 목록과 종목 연결 관리의 테마 선택 목록 상단에 표시됩니다.
                </p>
              </div>

              <div className="flex gap-2 mt-3">
                <button type="button" className="btn btn-primary" onClick={() => void onSubmitTheme()}>
                  저장
                </button>
                <button type="button" className="btn btn-secondary" onClick={resetForm}>
                  초기화
                </button>
              </div>
            </SectionCard>
          </div>

          <SectionCard title="자동 추천 후보">
            <p className="text-sm text-muted mb-3">
              자동 추천 후보는 뉴스·공시 키워드 기반으로 생성된 승인 대기 항목입니다. 승인한 후보만 정식 테마-종목 매핑에 반영됩니다.
            </p>

            <div className="flex flex-wrap gap-2 items-end">
              <label className="space-y-1">
                <span className="text-sm">최근 기간(일)</span>
                <input
                  className="input-control"
                  type="number"
                  min={1}
                  max={30}
                  value={lookbackDays}
                  onChange={(e) => setLookbackDays(Number(e.target.value) || 7)}
                />
              </label>
              <label className="space-y-1">
                <span className="text-sm">출처</span>
                <select
                  className="select-control"
                  value={candidateSourceFilter}
                  onChange={(e) => setCandidateSourceFilter(e.target.value as "all" | "news" | "disclosure")}
                >
                  <option value="all">전체</option>
                  <option value="news">뉴스</option>
                  <option value="disclosure">공시</option>
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-sm">상태 필터</span>
                <select
                  className="select-control"
                  value={candidateStatusFilter}
                  onChange={(e) => setCandidateStatusFilter(e.target.value as "all" | MarketThemeCandidateStatus)}
                >
                  <option value="all">전체</option>
                  <option value="pending">승인 대기</option>
                  <option value="approved">승인됨</option>
                  <option value="rejected">거절됨</option>
                  <option value="ignored">보류</option>
                </select>
              </label>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void onGenerateCandidates()}
                disabled={generatingCandidates}
              >
                {generatingCandidates ? "생성 중..." : "뉴스·공시 후보 생성"}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => void loadCandidates()}>
                목록 새로고침
              </button>
            </div>

            <div className="table-shell max-h-[380px] overflow-auto mt-3">
              <table className="data-table compact-table">
                <thead>
                  <tr>
                    <th>추천 테마</th>
                    <th>추천 종목</th>
                    <th>출처</th>
                    <th>신뢰도</th>
                    <th>매칭 키워드</th>
                    <th>근거 수</th>
                    <th>상태</th>
                    <th>작업</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((row) => (
                    <tr key={row.id}>
                      <td>{row.theme_name}</td>
                      <td>{`${row.stock_name} (${row.stock_code})`}</td>
                      <td>{sourceLabel(row.candidate_source)}</td>
                      <td>{row.confidence_score ?? "-"}</td>
                      <td>{row.matched_keywords.join(", ") || "-"}</td>
                      <td>{row.evidence_count}</td>
                      <td>{statusLabel(row.status)}</td>
                      <td>
                        <div className="flex gap-1">
                          <button type="button" className="btn btn-primary" onClick={() => void onApproveCandidate(row.id)}>
                            승인
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => void onRejectCandidate(row.id)}
                          >
                            거절
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => void onIgnoreCandidate(row.id)}
                          >
                            보류
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {candidates.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="text-center text-muted">
                        후보 데이터가 없습니다.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "mapping" ? (
        <div className="space-y-4">
          <SectionCard title="테마 선택 / 종목 검색 / 종목 추가">
            <p className="text-sm text-muted mb-3">
              선택한 테마에 종목을 직접 연결합니다. 연결된 종목은 테마별 집계와 시장 트렌드 분석의 기준으로 사용됩니다.
            </p>

            <div className="grid grid-cols-1 xl:grid-cols-[3fr_7fr] gap-3">
              <label className="space-y-1">
                <span>테마 선택</span>
                <select
                  className="select-control"
                  value={selectedThemeId ?? ""}
                  onChange={(e) => setSelectedThemeId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">테마를 선택해 주세요</option>
                  {sortedThemes
                    .filter((x) => x.is_active === 1)
                    .map((row) => (
                      <option key={row.id} value={row.id}>
                        {row.is_supply_theme === 1 ? `[수급] ${row.theme_name}` : row.theme_name}
                      </option>
                    ))}
                </select>
              </label>

              <div className="space-y-1">
                <span>종목명 또는 종목코드 검색</span>
                <div className="flex gap-2">
                  <input
                    className="input-control"
                    placeholder="예: HJ중공업 또는 097230"
                    value={stockSearchKeyword}
                    onChange={(e) => setStockSearchKeyword(e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => void onSearchStocks()}
                    disabled={searching || !selectedThemeId}
                  >
                    {searching ? "검색 중..." : "검색"}
                  </button>
                </div>
              </div>
            </div>

            {!selectedThemeId ? (
              <p className="text-sm text-muted mt-3">종목을 연결할 테마를 선택해 주세요.</p>
            ) : (
              <div className="table-shell max-h-[300px] overflow-auto mt-3">
                <table className="data-table compact-table">
                  <thead>
                    <tr>
                      <th>종목명</th>
                      <th>종목코드</th>
                      <th>시장</th>
                      <th>추가</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stockSearchResults.map((row) => (
                      <tr key={row.id}>
                        <td>{row.stock_name}</td>
                        <td>{row.stock_code}</td>
                        <td>{row.market ?? "-"}</td>
                        <td>
                          <button type="button" className="btn btn-primary" onClick={() => void onAddThemeStock(row.id)}>
                            추가
                          </button>
                        </td>
                      </tr>
                    ))}
                    {stockSearchResults.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="text-center text-muted">
                          검색 결과가 없습니다.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>

          <SectionCard title={`연결 종목 목록${selectedTheme ? ` - ${selectedTheme.theme_name}` : ""}`}>
            <div className="table-shell max-h-[360px] overflow-auto">
              <table className="data-table compact-table">
                <thead>
                  <tr>
                    <th>종목명</th>
                    <th>종목코드</th>
                    <th>대표</th>
                    <th>출처</th>
                    <th>신뢰도</th>
                    <th>상태</th>
                    <th>작업</th>
                  </tr>
                </thead>
                <tbody>
                  {activeThemeStocks.map((row) => (
                    <tr key={row.mapping_id}>
                      <td>{row.stock_name}</td>
                      <td>{row.stock_code}</td>
                      <td>
                        <label className="inline-flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={row.is_primary === 1}
                            title="대표 종목으로 표시"
                            disabled={updatingPrimaryMappingId === row.mapping_id}
                            onChange={(e) => void onTogglePrimary(row.mapping_id, e.target.checked)}
                          />
                          <span>{row.is_primary === 1 ? "대표" : "일반"}</span>
                        </label>
                      </td>
                      <td>{row.mapping_source}</td>
                      <td>{row.confidence_score ?? "-"}</td>
                      <td>{row.is_active === 1 ? "활성" : "비활성"}</td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() => void onDeactivateMapping(row.mapping_id)}
                        >
                          삭제
                        </button>
                      </td>
                    </tr>
                  ))}
                  {activeThemeStocks.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="text-center text-muted">
                        연결된 종목이 없습니다.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
      ) : null}
    </div>
  );
}

export default MarketThemesPage;
