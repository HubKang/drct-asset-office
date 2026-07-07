import { ListCollapse, ListTree, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { AiSummarizeResponse } from "@/types/analysis";
import type { Disclosure, DisclosureCollectResponse, DisclosureCollectSelectedResponse } from "@/types/disclosure";
import type { Watchlist } from "@/types/watchlist";

const DISCLOSURES_LEFT_PANEL_STORAGE_KEY = "drct.disclosures.leftPanelCollapsed";

type WatchlistDisclosureTarget = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  disclosure_count: number;
  ai_processed_count: number;
  latest_disclosed_at: string | null;
};

function disclosureStatusMeta(item: Disclosure): { label: string; tone: "emerald" | "slate" | "rose" | "blue" } {
  const err = (item.ai_summary_error || "").toLowerCase();
  if (err.startsWith("fallback:")) return { label: "보완 필요", tone: "rose" };
  if (err.startsWith("partial:")) return { label: "일부 보완", tone: "blue" };
  if (item.ai_summary || item.ai_processed_at) return { label: "완료", tone: "emerald" };
  return { label: "미처리", tone: "slate" };
}

function riskMeta(risk?: string | null): { label: string; variant: "risk-high" | "risk-medium" | "risk-low" | "risk-unknown" } {
  const value = (risk || "").toLowerCase();
  if (value === "high") return { label: "고위험", variant: "risk-high" };
  if (value === "medium") return { label: "중위험", variant: "risk-medium" };
  if (value === "low") return { label: "저위험", variant: "risk-low" };
  return { label: "미분류", variant: "risk-unknown" };
}

function importanceMeta(score?: number | null): { label: string; variant: "importance-high" | "importance-medium" | "importance-low" } {
  const value = Number.isFinite(score) ? Number(score) : 0;
  if (value >= 70) return { label: `${value} / 중요`, variant: "importance-high" };
  if (value >= 40) return { label: `${value} / 보통`, variant: "importance-medium" };
  return { label: `${value} / 낮음`, variant: "importance-low" };
}

function eventLabel(eventType?: string | null): string {
  if (!eventType || eventType.toLowerCase() === "unknown") return "기타";
  return eventType;
}

function formatDate(value?: string | null): string {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

type SimpleDisclosureAiSummary = {
  summary: string;
  keywords: string[];
  importanceScore: number | null;
};

function splitKeywordText(value?: string | null): string[] {
  if (!value) return [];
  return value
    .split(/[,|\n]/)
    .map((keyword) => keyword.replace(/^[-•]\s*/, "").trim())
    .filter(Boolean)
    .filter((keyword, index, values) => values.indexOf(keyword) === index)
    .slice(0, 8);
}

function extractSection(text: string, title: string): string {
  const pattern = new RegExp(`\\[${title}\\]\\s*([\\s\\S]*?)(?=\\n\\s*\\[[^\\]]+\\]|$)`);
  return pattern.exec(text)?.[1]?.trim() ?? "";
}

function parseDisclosureAiSummary(item: Disclosure): SimpleDisclosureAiSummary {
  const raw = item.ai_summary?.trim() || "";
  let summary = "";
  let keywords: string[] = [];
  let importanceScore = item.ai_importance_score ?? item.importance_score ?? null;

  if (raw.startsWith("{")) {
    try {
      const parsed = JSON.parse(raw) as { summary?: unknown; keywords?: unknown; importance_score?: unknown };
      summary = typeof parsed.summary === "string" ? parsed.summary.trim() : "";
      keywords = Array.isArray(parsed.keywords) ? parsed.keywords.map((keyword) => String(keyword).trim()).filter(Boolean) : [];
      const parsedScore = Number(parsed.importance_score);
      if (Number.isFinite(parsedScore)) importanceScore = parsedScore;
    } catch {
      summary = "";
    }
  }

  if (!summary && raw) {
    summary = extractSection(raw, "공시 요약") || extractSection(raw, "핵심 요약") || raw;
    summary = summary.trim();
  }
  if (!keywords.length && raw) {
    keywords = splitKeywordText(extractSection(raw, "관련 키워드"));
  }
  if (!keywords.length) {
    keywords = splitKeywordText(item.ai_tags);
  }

  return {
    summary: summary || "아직 AI 처리가 완료되지 않은 공시입니다.",
    keywords,
    importanceScore,
  };
}

function toUserError(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    const message = error.message?.trim() || "";
    const lowered = message.toLowerCase();
    if (lowered.includes("failed to fetch") || lowered.includes("networkerror")) {
      return `${fallback} API 상태 또는 서버 연결을 확인해 주세요.`;
    }
    if (lowered.includes("http 5")) {
      return `${fallback} 서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.`;
    }
    return message || fallback;
  }
  return fallback;
}

function DisclosuresPage() {
  const [targets, setTargets] = useState<WatchlistDisclosureTarget[]>([]);
  const [items, setItems] = useState<Disclosure[]>([]);
  const [selectedDisclosure, setSelectedDisclosure] = useState<Disclosure | null>(null);
  const [isDisclosureDrawerOpen, setIsDisclosureDrawerOpen] = useState(false);
  const [panelCollapsed, setPanelCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(DISCLOSURES_LEFT_PANEL_STORAGE_KEY) === "true";
  });

  const [currentStockId, setCurrentStockId] = useState<number | null>(null);
  const [checkedStockIds, setCheckedStockIds] = useState<number[]>([]);
  const [checkedDisclosureIds, setCheckedDisclosureIds] = useState<number[]>([]);
  const [watchlistKeyword, setWatchlistKeyword] = useState("");
  const [watchlistFilter, setWatchlistFilter] = useState("");

  const [collectDays, setCollectDays] = useState("30");
  const [collectPageCount, setCollectPageCount] = useState("10");
  const [sortOrder, setSortOrder] = useState("latest");

  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [collectLoading, setCollectLoading] = useState(false);
  const [collectError, setCollectError] = useState("");
  const [collectResult, setCollectResult] = useState<DisclosureCollectResponse | DisclosureCollectSelectedResponse | null>(null);

  const [summarizeLoading, setSummarizeLoading] = useState(false);
  const [summarizeError, setSummarizeError] = useState("");
  const [summarizeResult, setSummarizeResult] = useState<AiSummarizeResponse | null>(null);

  const filteredTargets = useMemo(() => {
    const q = watchlistFilter.trim().toLowerCase();
    if (!q) return targets;
    return targets.filter((target) => target.stock_name.toLowerCase().includes(q) || target.stock_code.toLowerCase().includes(q));
  }, [targets, watchlistFilter]);

  const sortedItems = useMemo(() => {
    const copied = [...items];
    if (sortOrder === "oldest") {
      return copied.sort((a, b) => String(a.disclosed_at ?? "").localeCompare(String(b.disclosed_at ?? "")));
    }
    return copied.sort((a, b) => String(b.disclosed_at ?? "").localeCompare(String(a.disclosed_at ?? "")));
  }, [items, sortOrder]);

  const processedCount = sortedItems.filter((item) => Boolean(item.ai_summary || item.ai_processed_at)).length;
  const activeTarget = useMemo(() => targets.find((target) => target.stock_id === currentStockId), [targets, currentStockId]);
  const selectedDisclosureCount = checkedDisclosureIds.length;
  const allDisclosuresChecked = sortedItems.length > 0 && sortedItems.every((item) => checkedDisclosureIds.includes(item.id));

  const resolveTargetStockIds = (): number[] => {
    if (checkedStockIds.length > 0) return checkedStockIds;
    if (currentStockId) return [currentStockId];
    return [];
  };

  const buildTargets = (watchlist: Watchlist[], disclosures: Disclosure[]): WatchlistDisclosureTarget[] => {
    return watchlist.map((item) => {
      const stockDisclosures = disclosures.filter((disclosure) => disclosure.stock_id === item.stock_id);
      const latestDisclosedAt = stockDisclosures
        .map((disclosure) => disclosure.disclosed_at)
        .filter((value): value is string => Boolean(value))
        .sort((a, b) => b.localeCompare(a))[0] ?? null;
      return {
        stock_id: item.stock_id,
        stock_code: item.stock_code,
        stock_name: item.stock_name,
        disclosure_count: stockDisclosures.length,
        ai_processed_count: stockDisclosures.filter((disclosure) => Boolean(disclosure.ai_summary || disclosure.ai_processed_at)).length,
        latest_disclosed_at: latestDisclosedAt,
      };
    });
  };

  const loadTargets = async () => {
    setWatchlistLoading(true);
    try {
      const watchlist = await repositories.watchlist.list({ is_active: 1, limit: 200, offset: 0 });
      const disclosures = await repositories.disclosures.listDisclosures({ limit: 500, offset: 0 });
      const nextTargets = buildTargets(watchlist, disclosures);
      setTargets(nextTargets);
      setCurrentStockId((prev) => prev ?? nextTargets[0]?.stock_id ?? null);
    } finally {
      setWatchlistLoading(false);
    }
  };

  const loadDisclosuresByStock = async (stockId: number | null) => {
    if (!stockId) {
      setItems([]);
      setSelectedDisclosure(null);
      setCheckedDisclosureIds([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await repositories.disclosures.listDisclosures({ stock_id: stockId, limit: 100, offset: 0 });
      setItems(data);
      setSelectedDisclosure(data[0] ?? null);
      setCheckedDisclosureIds((prev) => prev.filter((id) => data.some((x) => x.id === id)));
    } catch (e) {
      setError(toUserError(e, "공시 목록 조회에 실패했습니다."));
      setCheckedDisclosureIds([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTargets();
  }, []);

  useEffect(() => {
    window.localStorage.setItem(DISCLOSURES_LEFT_PANEL_STORAGE_KEY, String(panelCollapsed));
  }, [panelCollapsed]);

  useEffect(() => {
    setCollectResult(null);
    setSummarizeResult(null);
    void loadDisclosuresByStock(currentStockId);
  }, [currentStockId]);

  useEffect(() => {
    const onEsc = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsDisclosureDrawerOpen(false);
    };
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, []);

  const toggleStockCheck = (stockId: number) => {
    setCheckedStockIds((prev) => (prev.includes(stockId) ? prev.filter((id) => id !== stockId) : [...prev, stockId]));
  };

  const handleOpenDisclosureDetail = (disclosure: Disclosure) => {
    setSelectedDisclosure(disclosure);
    setIsDisclosureDrawerOpen(true);
  };

  const handleCloseDisclosureDetail = () => {
    setIsDisclosureDrawerOpen(false);
  };

  const onCollectSelected = async (): Promise<boolean> => {
    const targetStockIds = resolveTargetStockIds();
    if (targetStockIds.length === 0) {
      setCollectError("관심종목 목록에서 작업 대상을 선택해 주세요.");
      return false;
    }

    setCollectLoading(true);
    setCollectError("");
    setCollectResult(null);
    try {
      const result = await repositories.disclosures.collectDisclosuresForSelectedWatchlist({
        stock_ids: targetStockIds,
        days: Number(collectDays),
        page_count: Number(collectPageCount),
      });
      setCollectResult(result);
      await loadTargets();
      await loadDisclosuresByStock(currentStockId);
      return true;
    } catch (e) {
      setCollectError(toUserError(e, "선택 공시 수집 중 오류가 발생했습니다."));
      return false;
    } finally {
      setCollectLoading(false);
    }
  };

  const onSummarizeSelected = async (): Promise<boolean> => {
    if (checkedDisclosureIds.length === 0) {
      setSummarizeError("공시 목록에서 AI 처리할 공시를 선택해 주세요.");
      return false;
    }

    setSummarizeLoading(true);
    setSummarizeError("");
    setSummarizeResult(null);
    try {
      const result = await repositories.disclosures.summarizeSelectedDisclosures(checkedDisclosureIds);
      setSummarizeResult(result);
      await loadTargets();
      await loadDisclosuresByStock(currentStockId);
      setCheckedDisclosureIds([]);
      return true;
    } catch (e) {
      setSummarizeError(toUserError(e, "선택 AI 처리 중 오류가 발생했습니다."));
      return false;
    } finally {
      setSummarizeLoading(false);
    }
  };

  const onDeleteSelectedDisclosures = async (): Promise<void> => {
    if (checkedDisclosureIds.length === 0) return;
    const ok = window.confirm(
      `선택한 공시 ${checkedDisclosureIds.length}건을 삭제하시겠습니까?\nAI 요약 포함 공시 데이터가 DB에서 삭제됩니다.`,
    );
    if (!ok) return;

    setSummarizeError("");
    try {
      const result = await repositories.disclosures.deleteDisclosuresBulk(checkedDisclosureIds);
      await loadTargets();
      await loadDisclosuresByStock(currentStockId);
      setCheckedDisclosureIds([]);
      window.alert(result.deleted > 0 ? "선택한 공시가 삭제되었습니다." : "삭제된 공시가 없습니다.");
    } catch (e) {
      setSummarizeError(toUserError(e, "선택 삭제 중 오류가 발생했습니다."));
    }
  };

  const onCollectAndSummarize = async () => {
    const collected = await onCollectSelected();
    if (!collected) return;

    const targetStockIds = resolveTargetStockIds();
    const results = await Promise.all(
      targetStockIds.map((stockId) => repositories.disclosures.listDisclosures({ stock_id: stockId, limit: 100, offset: 0 })),
    );
    const ids = results.flat().map((item) => item.id);
    const uniqueIds = Array.from(new Set(ids));
    if (uniqueIds.length === 0) {
      setSummarizeError("수집된 공시가 없어 AI 처리를 진행할 수 없습니다.");
      return;
    }

    setSummarizeLoading(true);
    setSummarizeError("");
    setSummarizeResult(null);
    try {
      const result = await repositories.disclosures.summarizeSelectedDisclosures(uniqueIds);
      setSummarizeResult(result);
      await loadTargets();
      await loadDisclosuresByStock(currentStockId);
      setCheckedDisclosureIds([]);
    } catch (e) {
      setSummarizeError(toUserError(e, "선택 수집+AI 처리 중 오류가 발생했습니다."));
    } finally {
      setSummarizeLoading(false);
    }
  };

  const onSearchTargets = () => setWatchlistFilter(watchlistKeyword);
  const selectedAiSummary = selectedDisclosure ? parseDisclosureAiSummary(selectedDisclosure) : null;

  return (
    <div className="space-y-4">
      <PageHeader
        title="공시 관리"
        description="관심종목을 선택하면 해당 종목의 공시가 자동 조회됩니다."
        action={(
          <div className="flex flex-wrap gap-2">
            <StatusBadge label="데이터 소스: API" tone="slate" />
            <StatusBadge label="API 정상" tone="emerald" />
            <StatusBadge label={`AI 처리 ${processedCount}/${sortedItems.length || 0}`} tone="blue" />
          </div>
        )}
      />

      <div className="flex w-full flex-nowrap items-center gap-1.5 overflow-hidden whitespace-nowrap">
        <input
          className="input-control !min-h-[34px] w-[170px] max-w-[170px] shrink-0 px-2 py-1 text-[12px]"
          placeholder="종목명/종목코드"
          value={watchlistKeyword}
          onChange={(e) => setWatchlistKeyword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key !== "Enter") return;
            e.preventDefault();
            onSearchTargets();
          }}
        />
        <button type="button" className="btn btn-secondary !min-h-[34px] w-[60px] shrink-0 px-2 text-[12px]" onClick={onSearchTargets}>검색</button>
        <select className="select-control !min-h-[34px] w-[110px] max-w-[110px] shrink-0 px-2 py-1 text-[12px]" value={collectDays} onChange={(e) => setCollectDays(e.target.value)}>
          <option value="30">최근 30일</option>
          <option value="7">최근 7일</option>
          <option value="90">최근 90일</option>
        </select>
        <select className="select-control !min-h-[34px] w-[110px] max-w-[110px] shrink-0 px-2 py-1 text-[12px]" value={collectPageCount} onChange={(e) => setCollectPageCount(e.target.value)}>
          <option value="100">수집 100건</option>
          <option value="10">수집 10건</option>
          <option value="30">수집 30건</option>
          <option value="50">수집 50건</option>
        </select>
        <select className="select-control !min-h-[34px] w-[110px] max-w-[110px] shrink-0 px-2 py-1 text-[12px]" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)}>
          <option value="latest">최신순</option>
          <option value="oldest">오래된순</option>
        </select>
        <button
          type="button"
          className="btn btn-primary !min-h-[34px] w-[116px] shrink-0 px-2 text-[12px]"
          disabled={checkedStockIds.length === 0 || collectLoading}
          onClick={() => void onCollectSelected()}
        >
          {collectLoading ? "수집 중..." : "선택 공시 수집"}
        </button>
        <button
          type="button"
          className="btn btn-secondary !min-h-[34px] w-[132px] shrink-0 px-2 text-[12px]"
          disabled={checkedStockIds.length === 0 || collectLoading || summarizeLoading}
          onClick={() => void onCollectAndSummarize()}
        >
          선택 수집+AI 처리
        </button>
      </div>

      {collectError ? <p className="text-xs text-rose-600">{collectError}</p> : null}
      {collectResult ? <div className="inline-result">{"requested_count" in collectResult ? `선택 공시 수집이 완료되었습니다. (성공 ${collectResult.success_count}건 / 실패 ${collectResult.failed_count}건)` : collectResult.message}</div> : null}
      {summarizeResult ? <div className="inline-result">{`선택 AI 처리 완료: 성공 ${summarizeResult.success_count ?? 0}건 / 실패 ${summarizeResult.failed_count ?? 0}건`}</div> : null}
      {summarizeError ? <div className="inline-result inline-error">{summarizeError}</div> : null}

      <div className={`drct-split-layout news-page-layout ${panelCollapsed ? "drct-split-layout--collapsed" : ""}`}>
        <aside className="drct-left-panel">
          <div className="drct-left-panel-rail" aria-label="관심종목 목록 펼치기">
            <button type="button" className="sije-icon-button" onClick={() => setPanelCollapsed(false)} title="관심종목 목록 펼치기" aria-label="관심종목 목록 펼치기">
              <ListTree size={17} />
            </button>
            <span className="drct-left-panel-rail-label">관심종목</span>
          </div>
          {!panelCollapsed ? (
          <SectionCard
            title={(
              <span className="drct-left-panel-title">
                <span>관심종목 목록</span>
                <button type="button" className="sije-icon-button" onClick={() => setPanelCollapsed(true)} title="관심종목 목록 접기" aria-label="관심종목 목록 접기">
                  <ListCollapse size={17} />
                </button>
              </span>
            )}
          >
            <div className="watchlist-selection-count mb-2">선택 종목 {checkedStockIds.length}건</div>
            <div className="news-target-list">
              {watchlistLoading ? <div className="text-sm text-muted py-3">관심종목을 불러오는 중입니다.</div> : null}
              {!watchlistLoading && filteredTargets.length === 0 ? <div className="text-sm text-muted py-3">관심종목이 없습니다.</div> : null}
              {!watchlistLoading && filteredTargets.map((target) => {
                const isChecked = checkedStockIds.includes(target.stock_id);
                const isCurrent = currentStockId === target.stock_id;
                return (
                  <button
                    key={target.stock_id}
                    type="button"
                    className={`news-target-item ${isCurrent ? "selected" : ""}`}
                    onClick={() => setCurrentStockId(target.stock_id)}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onClick={(event) => event.stopPropagation()}
                      onChange={(event) => {
                        event.stopPropagation();
                        toggleStockCheck(target.stock_id);
                      }}
                    />
                    <div className="stock-cell min-w-0">
                      <strong>{target.stock_name}</strong>
                      <span>{target.stock_code} · 공시 {target.disclosure_count} · AI {target.ai_processed_count}/{target.disclosure_count}</span>
                      <span>최종수집 {target.latest_disclosed_at ? formatDate(target.latest_disclosed_at).slice(0, 10) : "-"}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </SectionCard>
          ) : null}
        </aside>

        <main className="drct-main-panel">
          <SectionCard title="">
            <div className="news-list-header">
              <h3 className="section-title m-0">{`공시 목록${activeTarget ? ` - ${activeTarget.stock_name}` : ""}`}</h3>
              <div className="flex items-center gap-2">
                <button type="button" className="btn btn-secondary" disabled={selectedDisclosureCount === 0 || summarizeLoading} onClick={() => void onSummarizeSelected()}>
                  {summarizeLoading ? "선택 AI 처리 중..." : `선택 AI 처리 ${selectedDisclosureCount}건`}
                </button>
                <button type="button" className="btn btn-secondary" disabled={selectedDisclosureCount === 0 || loading} onClick={() => void onDeleteSelectedDisclosures()}>
                  {`선택 삭제 ${selectedDisclosureCount}건`}
                </button>
              </div>
            </div>

            {currentStockId === null ? <p className="text-sm text-muted">관심종목을 선택하세요.</p> : null}
            {loading ? <p className="text-sm text-muted">공시를 불러오는 중입니다.</p> : null}
            {error ? <p className="text-sm text-rose-600">{error}</p> : null}
            {!loading && !error && currentStockId !== null && sortedItems.length === 0 ? (
              <p className="text-sm text-muted">공시 목록이 없습니다.</p>
            ) : null}

            {!loading && !error && sortedItems.length > 0 ? (
              <div className="table-shell max-h-[620px] overflow-auto">
                <table className="data-table compact-table w-full table-fixed disclosure-row-table">
                  <thead>
                    <tr>
                      <th className="disclosure-col-check">
                        <input
                          type="checkbox"
                          checked={allDisclosuresChecked}
                          aria-label="전체 선택"
                          title="전체 선택"
                          onChange={(e) => {
                            setCheckedDisclosureIds(e.target.checked ? sortedItems.map((item) => item.id) : []);
                          }}
                        />
                      </th>
                      <th className="disclosure-col-status">AI상태</th>
                      <th className="disclosure-col-stock">종목명</th>
                      <th className="disclosure-col-title">공시제목</th>
                      <th className="disclosure-col-event">이벤트</th>
                      <th className="disclosure-col-risk">리스크</th>
                      <th className="disclosure-col-score">중요도</th>
                      <th className="disclosure-col-date">공시일</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedItems.map((item) => {
                      const aiStatus = disclosureStatusMeta(item);
                      const event = eventLabel(item.ai_event_type ?? item.disclosure_type);
                      const risk = riskMeta(item.ai_risk_level);
                      const importance = importanceMeta(item.ai_importance_score ?? item.importance_score);
                      const checked = checkedDisclosureIds.includes(item.id);

                      return (
                        <tr key={item.id} className="row-clickable" onClick={() => handleOpenDisclosureDetail(item)}>
                          <td onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={(e) => {
                                const next = e.target.checked;
                                setCheckedDisclosureIds((prev) => (next ? [...prev, item.id] : prev.filter((id) => id !== item.id)));
                              }}
                            />
                          </td>
                          <td><StatusBadge label={aiStatus.label} tone={aiStatus.tone} /></td>
                          <td className="cell-nowrap">{item.stock_name ?? item.stock_code ?? "-"}</td>
                          <td
                            className="cell-title disclosure-title-cell disclosure-title-link"
                            title={item.disclosure_title}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleOpenDisclosureDetail(item);
                            }}
                          >
                            {item.disclosure_title}
                          </td>
                          <td><StatusBadge label={event} variant="event" /></td>
                          <td><StatusBadge label={risk.label} variant={risk.variant} /></td>
                          <td><StatusBadge label={importance.label} variant={importance.variant} /></td>
                          <td className="cell-nowrap cell-muted">{formatDate(item.disclosed_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </SectionCard>
        </main>
      </div>

      {isDisclosureDrawerOpen && selectedDisclosure ? (
        <div className="fixed inset-0 z-[999] bg-slate-900/30" onClick={handleCloseDisclosureDetail}>
          <aside className="absolute right-0 top-0 h-full w-full max-w-[520px] overflow-auto border-l bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 flex items-center justify-between border-b bg-white p-4">
              <h3 className="text-lg font-semibold">공시 상세</h3>
              <button type="button" className="btn btn-secondary !min-h-[30px] px-2" onClick={handleCloseDisclosureDetail}>
                <X size={16} />
                <span className="ml-1">닫기</span>
              </button>
            </div>
            <div className="p-4">
              <div className="space-y-3">
                <h4 className="detail-title">{selectedDisclosure.disclosure_title}</h4>
                <div className="detail-section">
                  <p className="detail-label">기본 정보</p>
                  <div className="detail-body">
                    <p>{`종목명: ${selectedDisclosure.stock_name ?? "-"}`}</p>
                    <p>{`종목코드: ${selectedDisclosure.stock_code ?? "-"}`}</p>
                    <p>{`공시일: ${formatDate(selectedDisclosure.disclosed_at)}`}</p>
                    <p>{`접수일: ${formatDate(selectedDisclosure.disclosed_at)}`}</p>
                    <p>{`출처: DART`}</p>
                    <p>{`접수번호: ${selectedDisclosure.dart_receipt_no ?? "-"}`}</p>
                  </div>
                </div>
                <div className="detail-section">
                  <p className="detail-label">AI 요약</p>
                  {selectedDisclosure.ai_summary_error === "missing_disclosure_body" || selectedDisclosure.ai_summary_error === "dart_fetch_failed" ? (
                    <p className="text-xs text-amber-700 mb-2">AI 요약 상태: 원문 본문 확인 필요</p>
                  ) : null}
                  <div className="news-ai-simple-grid">
                    <div className="news-ai-simple-card summary">
                      <span className="news-ai-simple-label">공시 요약</span>
                      <p className="disclosure-ai-summary-text">{selectedAiSummary?.summary ?? "아직 AI 처리가 완료되지 않은 공시입니다."}</p>
                    </div>
                    <div className="news-ai-simple-card">
                      <span className="news-ai-simple-label">관련 키워드</span>
                      <div className="news-keyword-chip-list">
                        {selectedAiSummary?.keywords.length ? selectedAiSummary.keywords.map((keyword) => (
                          <span key={keyword} className="news-keyword-chip">{keyword}</span>
                        )) : <span className="cell-muted">-</span>}
                      </div>
                    </div>
                    <div className="news-ai-simple-card">
                      <span className="news-ai-simple-label">중요도</span>
                      <div className="news-ai-importance-line">
                        <StatusBadge
                          label={importanceMeta(selectedAiSummary?.importanceScore).label}
                          variant={importanceMeta(selectedAiSummary?.importanceScore).variant}
                        />
                      </div>
                    </div>
                  </div>
                </div>
                <details className="legacy-analysis-fields">
                  <summary>기존 분석 필드 보기</summary>
                  <div className="detail-body">
                    <p>{`AI 처리 여부: ${selectedDisclosure.ai_summary || selectedDisclosure.ai_processed_at ? "완료" : "미처리"}`}</p>
                    <p>{`AI 처리일: ${formatDate(selectedDisclosure.ai_processed_at)}`}</p>
                    <p>{`이벤트: ${eventLabel(selectedDisclosure.ai_event_type ?? selectedDisclosure.disclosure_type)}`}</p>
                    <p>{`리스크: ${riskMeta(selectedDisclosure.ai_risk_level).label}`}</p>
                    <p>{`중요도: ${selectedDisclosure.ai_importance_score ?? selectedDisclosure.importance_score ?? "-"}`}</p>
                    <p>{`tag: ${selectedDisclosure.ai_tags ?? "-"}`}</p>
                    <p>{`score: ${selectedDisclosure.ai_importance_score ?? selectedDisclosure.importance_score ?? "-"}`}</p>
                    <p>{`risk_level: ${selectedDisclosure.ai_risk_level ?? "-"}`}</p>
                    <p>{`event_type: ${selectedDisclosure.ai_event_type ?? selectedDisclosure.disclosure_type ?? "-"}`}</p>
                  </div>
                </details>
                <div className="detail-section">
                  <p className="detail-label">원문 링크</p>
                  {selectedDisclosure.url ? (
                    <a className="btn btn-secondary !min-h-[34px] px-3 text-[13px]" href={selectedDisclosure.url} target="_blank" rel="noreferrer">DART 원문 열기</a>
                  ) : (
                    <p className="detail-body">원문 링크가 없습니다.</p>
                  )}
                </div>
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

export default DisclosuresPage;
