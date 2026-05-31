import { X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { AiSummarizeResponse } from "@/types/analysis";
import type { NewsBulkDeleteResponse, NewsCollectResponse, NewsCollectSelectedResponse, NewsCollectionTarget, NewsItem } from "@/types/news";

function sentimentMeta(sentiment?: string | null): { label: string; variant: "positive" | "neutral" | "negative" } {
  const value = (sentiment || "").toLowerCase();
  if (value === "positive") return { label: "긍정", variant: "positive" };
  if (value === "negative") return { label: "부정", variant: "negative" };
  return { label: "중립", variant: "neutral" };
}

function importanceMeta(score?: number | null): { label: string; variant: "importance-high" | "importance-medium" | "importance-low" } {
  const value = Number.isFinite(score) ? Number(score) : 0;
  if (value >= 70) return { label: `${value} / 중요`, variant: "importance-high" };
  if (value >= 40) return { label: `${value} / 보통`, variant: "importance-medium" };
  return { label: `${value} / 낮음`, variant: "importance-low" };
}

function aiStatusMeta(news: NewsItem): { label: string; tone: "emerald" | "rose" | "blue" | "slate" } {
  const err = (news.ai_summary_error || "").toLowerCase();
  if (err.startsWith("fallback:")) return { label: "보완 필요", tone: "rose" };
  if (err.startsWith("partial:")) return { label: "일부 보완", tone: "blue" };
  if (news.ai_summary) return { label: "완료", tone: "emerald" };
  if (news.ai_summary_error) return { label: "실패", tone: "rose" };
  if (news.ai_processed_at) return { label: "처리중", tone: "blue" };
  return { label: "미처리", tone: "slate" };
}

function formatDate(value?: string | null): string {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function parseAiMetaFromTags(tags?: string | null): { riskLevel: string; eventType: string } {
  const raw = (tags || "").split(",").map((v) => v.trim()).filter(Boolean);
  const risk = raw.find((v) => v.startsWith("risk:"))?.slice(5) || "unknown";
  const event = raw.find((v) => v.startsWith("event:"))?.slice(6) || "other";
  return { riskLevel: risk, eventType: event };
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

function NewsPage() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [collectionTargets, setCollectionTargets] = useState<NewsCollectionTarget[]>([]);
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const [currentStockId, setCurrentStockId] = useState<number | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [watchlistLoading, setWatchlistLoading] = useState(false);

  const [watchlistKeyword, setWatchlistKeyword] = useState("");
  const [watchlistFilter, setWatchlistFilter] = useState("");
  const [collectDisplay, setCollectDisplay] = useState("10");
  const [collectSort, setCollectSort] = useState("date");
  const [collectLoading, setCollectLoading] = useState(false);
  const [collectError, setCollectError] = useState("");
  const [collectResult, setCollectResult] = useState<NewsCollectResponse | NewsCollectSelectedResponse | null>(null);

  const [summarizeLoading, setSummarizeLoading] = useState(false);
  const [summarizeError, setSummarizeError] = useState("");
  const [summarizeResult, setSummarizeResult] = useState<AiSummarizeResponse | null>(null);

  const [checkedNewsIds, setCheckedNewsIds] = useState<number[]>([]);
  const [checkedStockIds, setCheckedStockIds] = useState<number[]>([]);
  const [newsPage, setNewsPage] = useState(1);
  const [newsTotalCount, setNewsTotalCount] = useState(0);
  const pageSize = 20;

  const filteredTargets = useMemo(() => {
    const q = watchlistFilter.trim().toLowerCase();
    if (!q) return collectionTargets;
    return collectionTargets.filter((item) => item.stock_name.toLowerCase().includes(q) || item.stock_code.toLowerCase().includes(q));
  }, [collectionTargets, watchlistFilter]);

  const sortedItems = useMemo(() => {
    const copied = [...items];
    if (collectSort === "sim") {
      return copied.sort((a, b) => (b.ai_importance_score ?? b.importance_score ?? 0) - (a.ai_importance_score ?? a.importance_score ?? 0));
    }
    return copied.sort((a, b) => String(b.published_at ?? "").localeCompare(String(a.published_at ?? "")));
  }, [items, collectSort]);

  const processedCount = sortedItems.filter((item) => Boolean(item.ai_summary)).length;
  const activeStockLabel = useMemo(() => collectionTargets.find((it) => it.stock_id === currentStockId), [collectionTargets, currentStockId]);
  const selectedNewsCount = checkedNewsIds.length;
  const allNewsChecked = sortedItems.length > 0 && sortedItems.every((item) => checkedNewsIds.includes(item.id));
  const totalPages = Math.max(1, Math.ceil(newsTotalCount / pageSize));
  const pageStart = newsTotalCount === 0 ? 0 : (newsPage - 1) * pageSize + 1;
  const pageEnd = Math.min(newsTotalCount, newsPage * pageSize);

  const loadCollectionTargets = async () => {
    setWatchlistLoading(true);
    try {
      const data = await repositories.news.listCollectionTargets();
      setCollectionTargets(data);
      setCurrentStockId((prev) => prev ?? data[0]?.stock_id ?? null);
    } finally {
      setWatchlistLoading(false);
    }
  };

  const loadNewsByCurrentStock = async (stockId: number | null, page: number = 1) => {
    if (!stockId) {
      setItems([]);
      setSelectedNews(null);
      setCheckedNewsIds([]);
      setNewsTotalCount(0);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const offset = (page - 1) * pageSize;
      const data = await repositories.news.listNewsPage({ stock_id: stockId, limit: pageSize, offset });
      setItems(data.items);
      setNewsTotalCount(data.total_count);
      setSelectedNews(data.items[0] ?? null);
      setCheckedNewsIds((prev) => prev.filter((id) => data.items.some((x) => x.id === id)));
    } catch (e) {
      setError(toUserError(e, "뉴스 목록 조회에 실패했습니다."));
      // Keep the last successful list to avoid empty screen on temporary network issues.
      setCheckedNewsIds([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCollectionTargets();
  }, []);

  useEffect(() => {
    setCollectResult(null);
    setSummarizeResult(null);
    setNewsPage(1);
    void loadNewsByCurrentStock(currentStockId, 1);
  }, [currentStockId]);

  useEffect(() => {
    if (currentStockId === null) return;
    void loadNewsByCurrentStock(currentStockId, newsPage);
  }, [newsPage]);

  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsDrawerOpen(false);
    };
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, []);

  const resolveTargetStockIds = (): number[] => {
    if (checkedStockIds.length > 0) return checkedStockIds;
    if (currentStockId) return [currentStockId];
    return [];
  };

  const toggleStockCheck = (stockId: number) => {
    setCheckedStockIds((prev) => (prev.includes(stockId) ? prev.filter((id) => id !== stockId) : [...prev, stockId]));
  };

  const onCollectSelected = async (): Promise<boolean> => {
    const targets = resolveTargetStockIds();
    if (targets.length === 0) {
      setCollectError("관심종목 목록에서 수집할 종목을 선택해 주세요.");
      return false;
    }

    setCollectLoading(true);
    setCollectError("");
    setCollectResult(null);
    try {
      const result = await repositories.news.collectNewsForSelectedWatchlist({
        stock_ids: targets,
        providers: ["naver"],
        display: Number(collectDisplay),
        sort: collectSort,
      });
      setCollectResult(result);
      await loadCollectionTargets();
      await loadNewsByCurrentStock(currentStockId, newsPage);
      setCollectError("");
      return true;
    } catch (e) {
      setCollectError(toUserError(e, "선택한 관심종목의 뉴스 수집에 실패했습니다."));
      return false;
    } finally {
      setCollectLoading(false);
    }
  };

  const onSummarizeSelectedNews = async (): Promise<boolean> => {
    if (checkedNewsIds.length === 0) {
      setSummarizeError("뉴스 목록에서 처리할 뉴스를 선택해 주세요.");
      return false;
    }
    const checkedSet = new Set(checkedNewsIds);
    const ids = items.filter((item) => checkedSet.has(item.id)).map((item) => item.id);
    if (ids.length === 0) {
      setSummarizeError("선택한 뉴스가 없습니다.");
      return false;
    }

    setSummarizeLoading(true);
    setSummarizeError("");
    setSummarizeResult(null);
    try {
      const result = await repositories.news.summarizeSelectedNews(ids);
      setSummarizeResult(result);
      await loadCollectionTargets();
      await loadNewsByCurrentStock(currentStockId, newsPage);
      setCheckedNewsIds([]);
      return true;
    } catch (e) {
      setSummarizeError(toUserError(e, "선택 AI 처리 중 오류가 발생했습니다."));
      return false;
    } finally {
      setSummarizeLoading(false);
    }
  };

  const onCollectAndSummarize = async () => {
    const targets = resolveTargetStockIds();
    if (targets.length === 0) {
      setSummarizeError("관심종목 목록에서 처리할 종목을 선택해 주세요.");
      return;
    }
    const collected = await onCollectSelected();
    if (!collected) return;
    const targetSet = new Set(targets);
    const ids = items.filter((item) => item.stock_id !== null && targetSet.has(item.stock_id) && !item.ai_summary).map((item) => item.id);
    if (ids.length === 0) {
      setSummarizeError("수집 후 AI 미처리 뉴스가 없습니다.");
      return;
    }
    setSummarizeLoading(true);
    setSummarizeError("");
    setSummarizeResult(null);
    try {
      const result = await repositories.news.summarizeSelectedNews(ids);
      setSummarizeResult(result);
      await loadCollectionTargets();
      await loadNewsByCurrentStock(currentStockId, newsPage);
      setCheckedNewsIds([]);
    } catch (e) {
      setSummarizeError(toUserError(e, "선택 수집+AI 처리에 실패했습니다."));
    } finally {
      setSummarizeLoading(false);
    }
  };

  const onSearchTargets = () => setWatchlistFilter(watchlistKeyword);
  const onOpenDetail = (news: NewsItem) => {
    setSelectedNews(news);
    setIsDrawerOpen(true);
  };
  const onDeleteSelectedNews = async () => {
    if (checkedNewsIds.length === 0) return;
    const ok = window.confirm(
      `선택한 뉴스 ${checkedNewsIds.length}건을 삭제하시겠습니까?\n수집 기사와 AI 요약 정보가 DB에서 삭제됩니다.`,
    );
    if (!ok) return;
    try {
      const result: NewsBulkDeleteResponse = await repositories.news.deleteNewsBulk(checkedNewsIds);
      const targetPage = checkedNewsIds.length >= items.length && newsPage > 1 ? newsPage - 1 : newsPage;
      setNewsPage(targetPage);
      await loadCollectionTargets();
      await loadNewsByCurrentStock(currentStockId, targetPage);
      setCheckedNewsIds([]);
      window.alert(result.deleted > 0 ? "선택한 뉴스가 삭제되었습니다." : "삭제된 뉴스가 없습니다.");
    } catch (e) {
      setSummarizeError(toUserError(e, "선택 뉴스 삭제 중 오류가 발생했습니다."));
    }
  };
  const onCloseDrawer = () => {
    setIsDrawerOpen(false);
    setSelectedNews(null);
  };
  const selectedMeta = useMemo(() => parseAiMetaFromTags(selectedNews?.ai_tags), [selectedNews?.ai_tags]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="뉴스 관리"
        description="관심종목을 선택하면 해당 종목의 뉴스가 자동 조회됩니다."
        action={(
          <div className="flex flex-wrap gap-2">
            <StatusBadge label="데이터 소스: API" tone="slate" />
            <StatusBadge label="API 정상" tone="emerald" />
            <StatusBadge label={`AI ${processedCount}/${sortedItems.length || 0}`} tone="blue" />
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
        <select className="select-control !min-h-[34px] w-[110px] max-w-[110px] shrink-0 px-2 py-1 text-[12px]" value={collectDisplay} onChange={(e) => setCollectDisplay(e.target.value)}>
          <option value="10">수집 10건</option>
          <option value="20">수집 20건</option>
          <option value="50">수집 50건</option>
        </select>
        <select className="select-control !min-h-[34px] w-[100px] max-w-[100px] shrink-0 px-2 py-1 text-[12px]" value={collectSort} onChange={(e) => setCollectSort(e.target.value)}>
          <option value="date">최신순</option>
          <option value="sim">중요도순</option>
        </select>
        <button
          type="button"
          className="btn btn-primary !min-h-[34px] w-[116px] shrink-0 px-2 text-[12px]"
          title="왼쪽 관심종목 목록에서 선택한 종목의 뉴스를 수집합니다."
          disabled={checkedStockIds.length === 0 || collectLoading}
          onClick={() => void onCollectSelected()}
        >
          {collectLoading ? "수집 중..." : "선택 뉴스 수집"}
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
      {collectResult ? <div className="inline-result">{"requested_count" in collectResult ? `선택한 뉴스 수집이 완료되었습니다. (성공 ${collectResult.success_count}건 / 실패 ${collectResult.failed_count}건)` : collectResult.message}</div> : null}
      {summarizeResult ? <div className="inline-result">{`선택한 뉴스의 AI 처리가 완료되었습니다. (성공 ${summarizeResult.success_count ?? 0}건 / 실패 ${summarizeResult.failed_count ?? 0}건)`}</div> : null}
      {summarizeError ? <div className="inline-result inline-error">{summarizeError}</div> : null}

      <div className="grid w-full min-w-0 grid-cols-[360px_minmax(0,1fr)] items-stretch gap-4 news-page-layout">
        <div className="min-w-0">
          <SectionCard title="관심종목 목록">
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
                      <span>{target.stock_code} · 뉴스 {target.news_count} · AI {target.ai_processed_count}/{target.news_count}</span>
                      <span>최종수집 {target.latest_collected_at ? formatDate(target.latest_collected_at).slice(0, 10) : "-"}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </SectionCard>
        </div>

        <div className="min-w-0">
          <SectionCard title="">
            <div className="news-list-header">
              <h3 className="section-title m-0">{`뉴스 목록${activeStockLabel ? ` - ${activeStockLabel.stock_name}` : ""}`}</h3>
              <div className="flex items-center gap-2">
                <button type="button" className="btn btn-secondary" disabled={selectedNewsCount === 0 || summarizeLoading} onClick={() => void onSummarizeSelectedNews()}>
                  {summarizeLoading ? "선택 AI 처리 중..." : `선택 AI 처리 ${selectedNewsCount}건`}
                </button>
                <button type="button" className="btn btn-secondary" disabled={selectedNewsCount === 0 || loading} onClick={() => void onDeleteSelectedNews()}>
                  {`선택 삭제 ${selectedNewsCount}건`}
                </button>
              </div>
            </div>

            {currentStockId === null ? <p className="text-sm text-muted">관심종목을 선택하세요.</p> : null}
            {loading ? <p className="text-sm text-muted">뉴스를 불러오는 중입니다.</p> : null}
            {error ? <p className="text-sm text-rose-600">{error}</p> : null}
            {!loading && !error && currentStockId !== null && sortedItems.length === 0 ? (
              <p className="text-sm text-muted">조회된 뉴스가 없습니다.</p>
            ) : null}

            {!loading && !error && sortedItems.length > 0 ? (
              <>
                <div className="table-shell max-h-[620px] overflow-auto">
                  <table className="data-table compact-table w-full table-fixed news-row-table">
                    <thead>
                      <tr>
                        <th className="news-col-check">
                          <input
                            type="checkbox"
                            checked={allNewsChecked}
                            onChange={(e) => {
                              setCheckedNewsIds(e.target.checked ? sortedItems.map((item) => item.id) : []);
                            }}
                          />
                        </th>
                        <th className="news-col-status">AI상태</th>
                        <th className="news-col-stock">종목명</th>
                        <th className="news-col-title">제목</th>
                        <th className="news-col-importance">중요도</th>
                        <th className="news-col-sentiment">감성</th>
                        <th className="news-col-source">출처</th>
                        <th className="news-col-date">발행일</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedItems.map((news) => {
                        const sentiment = sentimentMeta(news.ai_sentiment ?? news.sentiment);
                        const importance = importanceMeta(news.ai_importance_score ?? news.importance_score);
                        const aiStatus = aiStatusMeta(news);
                        const checked = checkedNewsIds.includes(news.id);
                        return (
                          <tr key={news.id} className="row-clickable" onClick={() => onOpenDetail(news)}>
                            <td onClick={(e) => e.stopPropagation()}>
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={(e) => {
                                  const next = e.target.checked;
                                  setCheckedNewsIds((prev) => (next ? [...prev, news.id] : prev.filter((id) => id !== news.id)));
                                }}
                              />
                            </td>
                            <td><StatusBadge label={aiStatus.label} tone={aiStatus.tone} /></td>
                            <td className="cell-nowrap">{news.stock_name ?? news.stock_code ?? "-"}</td>
                            <td
                              className="cell-title news-title-cell news-title-link"
                              title={news.title}
                              onClick={(e) => {
                                e.stopPropagation();
                                onOpenDetail(news);
                              }}
                            >
                              {news.title}
                            </td>
                            <td><StatusBadge label={importance.label} variant={importance.variant} /></td>
                            <td><StatusBadge label={sentiment.label} variant={sentiment.variant} /></td>
                            <td className="cell-nowrap">{news.source ?? "-"}</td>
                            <td className="cell-nowrap cell-muted">{formatDate(news.published_at)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="pagination-bar">
                  <span className="pagination-info">{`이번 페이지 ${sortedItems.length}건 / 전체 ${newsTotalCount}건 (${pageStart}-${pageEnd})`}</span>
                  <div className="pagination-actions">
                    <button
                      type="button"
                      className="btn btn-secondary !min-h-[32px] px-3 text-[12px]"
                      disabled={newsPage <= 1 || loading}
                      onClick={() => {
                        setNewsPage((prev) => Math.max(1, prev - 1));
                        setCheckedNewsIds([]);
                      }}
                    >
                      이전
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary !min-h-[32px] px-3 text-[12px]"
                      disabled={newsPage >= totalPages || loading}
                      onClick={() => {
                        setNewsPage((prev) => Math.min(totalPages, prev + 1));
                        setCheckedNewsIds([]);
                      }}
                    >
                      다음
                    </button>
                  </div>
                </div>
              </>
            ) : null}
          </SectionCard>
        </div>
      </div>

      {isDrawerOpen && selectedNews ? (
        <div className="fixed inset-0 z-[999] bg-slate-900/30" onClick={onCloseDrawer}>
          <aside className="absolute right-0 top-0 h-full w-full max-w-[520px] overflow-auto border-l bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 flex items-center justify-between border-b bg-white p-4">
              <h3 className="text-lg font-semibold">뉴스 상세</h3>
              <button type="button" className="btn btn-secondary !min-h-[30px] px-2" onClick={onCloseDrawer}><X size={16} /></button>
            </div>
            <div className="p-4">
              <div className="space-y-3">
                <h4 className="detail-title">{selectedNews.title}</h4>
                <div className="detail-section">
                  <p className="detail-label">기본 정보</p>
                  <div className="detail-body">
                    <p>{`종목명: ${selectedNews.stock_name ?? "-"}`}</p>
                    <p>{`종목코드: ${selectedNews.stock_code ?? "-"}`}</p>
                    <p>{`중요도: ${selectedNews.ai_importance_score ?? selectedNews.importance_score ?? "-"}`}</p>
                    <p>{`감성: ${selectedNews.ai_sentiment ?? selectedNews.sentiment ?? "-"}`}</p>
                    <p>Risk: 미분류</p>
                    <p>{`출처: ${selectedNews.source ?? "-"}`}</p>
                    <p>{`발행일: ${formatDate(selectedNews.published_at)}`}</p>
                    <p>{`수집일: ${formatDate(selectedNews.collected_at)}`}</p>
                    <p>{`AI 처리일: ${formatDate(selectedNews.ai_processed_at)}`}</p>
                  </div>
                </div>
                <div className="detail-section">
                  <p className="detail-label">분석 필드</p>
                  <div className="detail-body">
                    <p>{`tag: ${selectedNews.ai_tags ?? "미분류"}`}</p>
                    <p>{`score: ${selectedNews.ai_importance_score ?? selectedNews.importance_score ?? "-"}`}</p>
                    <p>{`sentiment: ${selectedNews.ai_sentiment ?? selectedNews.sentiment ?? "미분류"}`}</p>
                    <p>{`risk_level: ${selectedMeta.riskLevel}`}</p>
                    <p>{`event_type: ${selectedMeta.eventType}`}</p>
                  </div>
                </div>
                <div className="detail-section">
                  <p className="detail-label">AI 요약</p>
                  {(selectedNews.ai_summary_error || "").toLowerCase().startsWith("fallback:") ? (
                    <p className="text-xs text-amber-700 mb-2">AI 요약 상태: 보완 필요</p>
                  ) : null}
                  {(selectedNews.ai_summary_error || "").toLowerCase().startsWith("partial:") ? (
                    <p className="text-xs text-blue-700 mb-2">AI 요약 상태: 일부 보완</p>
                  ) : null}
                  <p className="detail-body news-ai-summary">{selectedNews.ai_summary ?? "아직 AI 처리가 완료되지 않은 뉴스입니다."}</p>
                </div>
                <div className="detail-section">
                  <p className="detail-label">원문 링크</p>
                  {selectedNews.url ? (
                    <a className="btn btn-secondary !min-h-[34px] px-3 text-[13px]" href={selectedNews.url} target="_blank" rel="noreferrer">원문 열기</a>
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

export default NewsPage;
