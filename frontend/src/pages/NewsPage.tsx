import { X } from "lucide-react";
import { useEffect, useMemo, useState, type MouseEvent } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { AiSummarizeResponse } from "@/types/analysis";
import type { NewsCollectResponse, NewsCollectSelectedResponse, NewsCollectionTarget, NewsItem } from "@/types/news";

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
  if (news.ai_summary) return { label: "완료", tone: "emerald" };
  if (news.ai_summary_error) return { label: "실패", tone: "rose" };
  if (news.ai_processed_at) return { label: "처리중", tone: "blue" };
  return { label: "미처리", tone: "slate" };
}

function formatDate(value?: string | null): string {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function NewsPage() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [collectionTargets, setCollectionTargets] = useState<NewsCollectionTarget[]>([]);
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const [currentStockId, setCurrentStockId] = useState<number | null>(null);
  const [checkedStockIds, setCheckedStockIds] = useState<number[]>([]);
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

  const loadNewsByCurrentStock = async (stockId: number | null) => {
    if (!stockId) {
      setItems([]);
      setSelectedNews(null);
      return;
    }

    setLoading(true);
    setError("");
    try {
      const data = await repositories.news.listNews({ stock_id: stockId, limit: 100 });
      setItems(data);
      setSelectedNews(data[0] ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "뉴스 조회 중 오류가 발생했습니다.");
      setItems([]);
      setSelectedNews(null);
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
    void loadNewsByCurrentStock(currentStockId);
  }, [currentStockId]);

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
      setCollectError("작업할 관심종목을 선택해 주세요.");
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
      await loadNewsByCurrentStock(currentStockId);
      return true;
    } catch (e) {
      setCollectError(e instanceof Error ? e.message : "선택 뉴스 수집 중 오류가 발생했습니다.");
      return false;
    } finally {
      setCollectLoading(false);
    }
  };

  const onSummarizeSelectedStocksNews = async (): Promise<boolean> => {
    const targets = resolveTargetStockIds();
    if (targets.length === 0) {
      setSummarizeError("작업할 관심종목을 선택해 주세요.");
      return false;
    }

    const targetSet = new Set(targets);
    const ids = items.filter((item) => item.stock_id !== null && targetSet.has(item.stock_id) && !item.ai_summary).map((item) => item.id);
    if (ids.length === 0) {
      setSummarizeError("처리할 미처리 뉴스가 없습니다.");
      return false;
    }

    setSummarizeLoading(true);
    setSummarizeError("");
    setSummarizeResult(null);
    try {
      const result = await repositories.news.summarizeSelectedNews(ids);
      setSummarizeResult(result);
      await loadCollectionTargets();
      await loadNewsByCurrentStock(currentStockId);
      return true;
    } catch (e) {
      setSummarizeError(e instanceof Error ? e.message : "선택 AI 처리 중 오류가 발생했습니다.");
      return false;
    } finally {
      setSummarizeLoading(false);
    }
  };

  const onCollectAndSummarize = async () => {
    const collected = await onCollectSelected();
    if (!collected) return;
    await onSummarizeSelectedStocksNews();
  };

  const onSearchTargets = () => setWatchlistFilter(watchlistKeyword);
  const onOpenDetail = (news: NewsItem) => {
    setSelectedNews(news);
    setIsDrawerOpen(true);
  };
  const onClickDetailButton = (event: MouseEvent<HTMLButtonElement>, news: NewsItem) => {
    event.preventDefault();
    event.stopPropagation();
    onOpenDetail(news);
  };
  const onCloseDrawer = () => {
    setIsDrawerOpen(false);
    setSelectedNews(null);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="뉴스 관리"
        description="관심종목을 선택하면 해당 종목의 뉴스가 자동 조회됩니다."
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
        <button type="button" className="btn btn-primary !min-h-[34px] w-[116px] shrink-0 px-2 text-[12px]" disabled={collectLoading} onClick={() => void onCollectSelected()}>
          {collectLoading ? "수집 중..." : "선택 뉴스 수집"}
        </button>
        <button type="button" className="btn btn-secondary !min-h-[34px] w-[110px] shrink-0 px-2 text-[12px]" disabled={summarizeLoading} onClick={() => void onSummarizeSelectedStocksNews()}>
          {summarizeLoading ? "AI 처리 중..." : "선택 AI 처리"}
        </button>
        <button type="button" className="btn btn-secondary !min-h-[34px] w-[132px] shrink-0 px-2 text-[12px]" disabled={collectLoading || summarizeLoading} onClick={() => void onCollectAndSummarize()}>
          선택 수집+AI 처리
        </button>
        <select className="select-control !min-h-[34px] w-[110px] max-w-[110px] shrink-0 px-2 py-1 text-[12px]" value={collectDisplay} onChange={(e) => setCollectDisplay(e.target.value)}>
          <option value="10">수집 10건</option>
          <option value="20">수집 20건</option>
          <option value="50">수집 50건</option>
        </select>
        <select className="select-control !min-h-[34px] w-[100px] max-w-[100px] shrink-0 px-2 py-1 text-[12px]" value={collectSort} onChange={(e) => setCollectSort(e.target.value)}>
          <option value="date">최신순</option>
          <option value="sim">정확도순</option>
        </select>
      </div>

      {collectError ? <p className="text-xs text-rose-600">{collectError}</p> : null}
      {collectResult ? <div className="inline-result">{"requested_count" in collectResult ? `선택 뉴스 수집 완료: 성공 ${collectResult.success_count}건 / 실패 ${collectResult.failed_count}건` : collectResult.message}</div> : null}
      {summarizeResult ? <div className="inline-result">{`선택 AI 처리 완료: 성공 ${summarizeResult.success_count ?? 0}건 / 실패 ${summarizeResult.failed_count ?? 0}건`}</div> : null}
      {summarizeError ? <div className="inline-result inline-error">{summarizeError}</div> : null}

      <div className="grid w-full min-w-0 grid-cols-[3fr_7fr] items-stretch gap-4">
        <div className="min-w-0">
          <SectionCard title="관심종목 목록">
            <div className="table-shell max-h-[620px] overflow-auto">
              <table className="data-table compact-table min-w-[560px]">
                <thead>
                  <tr>
                    <th>선택</th>
                    <th>종목명</th>
                    <th>뉴스수</th>
                    <th>AI처리</th>
                    <th>최근수집</th>
                  </tr>
                </thead>
                <tbody>
                  {watchlistLoading ? (
                    <tr><td colSpan={5} className="py-4 text-center text-muted">관심종목을 불러오는 중입니다.</td></tr>
                  ) : filteredTargets.length === 0 ? (
                    <tr><td colSpan={5} className="py-4 text-center text-muted">관심종목이 없습니다.</td></tr>
                  ) : (
                    filteredTargets.map((target) => {
                      const isChecked = checkedStockIds.includes(target.stock_id);
                      const isCurrent = currentStockId === target.stock_id;
                      return (
                        <tr key={target.stock_id} className={isCurrent ? "selected-row row-clickable" : "row-clickable"} onClick={() => setCurrentStockId(target.stock_id)}>
                          <td onClick={(e) => e.stopPropagation()}>
                            <input type="checkbox" checked={isChecked} onClick={(event) => event.stopPropagation()} onChange={() => toggleStockCheck(target.stock_id)} />
                          </td>
                          <td>{`${target.stock_name} (${target.stock_code})`}</td>
                          <td>{target.news_count}</td>
                          <td>{`${target.ai_processed_count}/${target.news_count}`}</td>
                          <td className="cell-nowrap">{formatDate(target.latest_collected_at)}</td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>

        <div className="min-w-0">
          <SectionCard title={`뉴스 목록${activeStockLabel ? ` - ${activeStockLabel.stock_name}` : ""}`}>
            {currentStockId === null ? <p className="text-sm text-muted">좌측 관심종목을 선택하면 해당 종목의 뉴스 목록이 표시됩니다.</p> : null}
            {loading ? <p className="text-sm text-muted">뉴스를 불러오는 중입니다.</p> : null}
            {error ? <p className="text-sm text-rose-600">{error}</p> : null}
            {!loading && !error && currentStockId !== null && sortedItems.length === 0 ? (
              <p className="text-sm text-muted">선택한 종목의 수집된 뉴스가 없습니다. 상단의 "선택 뉴스 수집" 버튼으로 뉴스를 수집해 주세요.</p>
            ) : null}

            {!loading && !error && sortedItems.length > 0 ? (
              <div className="table-shell max-h-[620px] overflow-auto">
                <table className="data-table compact-table min-w-[1040px]">
                  <thead>
                    <tr>
                      <th>AI처리</th>
                      <th>종목명</th>
                      <th className="min-w-[380px]">제목</th>
                      <th>중요도</th>
                      <th>감성</th>
                      <th>출처</th>
                      <th>발행일</th>
                      <th>상세</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedItems.map((news) => {
                      const sentiment = sentimentMeta(news.ai_sentiment ?? news.sentiment);
                      const importance = importanceMeta(news.ai_importance_score ?? news.importance_score);
                      const aiStatus = aiStatusMeta(news);
                      return (
                        <tr key={news.id} className="row-clickable" onClick={() => onOpenDetail(news)}>
                          <td><StatusBadge label={aiStatus.label} tone={aiStatus.tone} /></td>
                          <td className="cell-nowrap">{news.stock_name ?? news.stock_code ?? "-"}</td>
                          <td className="cell-title cell-clamp-2" title={news.title}>{news.title}</td>
                          <td><StatusBadge label={importance.label} variant={importance.variant} /></td>
                          <td><StatusBadge label={sentiment.label} variant={sentiment.variant} /></td>
                          <td className="cell-nowrap">{news.source ?? "-"}</td>
                          <td className="cell-nowrap cell-muted">{formatDate(news.published_at)}</td>
                          <td>
                            <button type="button" className="btn btn-secondary !min-h-[30px] px-2 text-[12px]" onClick={(event) => onClickDetailButton(event, news)}>
                              상세
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
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
                      <p>Risk: -</p>
                      <p>{`출처: ${selectedNews.source ?? "-"}`}</p>
                      <p>{`발행일: ${formatDate(selectedNews.published_at)}`}</p>
                      <p>{`수집일: ${formatDate(selectedNews.collected_at)}`}</p>
                      <p>{`AI 처리일: ${formatDate(selectedNews.ai_processed_at)}`}</p>
                    </div>
                  </div>
                  <div className="detail-section">
                    <p className="detail-label">분석 필드</p>
                    <div className="detail-body">
                      <p>{`tag: ${selectedNews.ai_tags ?? "-"}`}</p>
                      <p>{`score: ${selectedNews.ai_importance_score ?? selectedNews.importance_score ?? "-"}`}</p>
                      <p>{`sentiment: ${selectedNews.ai_sentiment ?? selectedNews.sentiment ?? "-"}`}</p>
                      <p>risk_level: -</p>
                      <p>event_type: -</p>
                    </div>
                  </div>
                  <div className="detail-section">
                    <p className="detail-label">AI 요약</p>
                    <p className="detail-body">{selectedNews.ai_summary ?? "아직 AI 처리가 완료되지 않은 뉴스입니다."}</p>
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
