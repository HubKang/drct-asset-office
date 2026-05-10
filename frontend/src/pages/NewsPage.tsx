import { Search } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { AiSummarizeResponse } from "@/types/analysis";
import type { NewsCollectResponse, NewsItem } from "@/types/news";
import type { Stock } from "@/types/stock";

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

function NewsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<NewsItem[]>([]);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const [selectedNewsIds, setSelectedNewsIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [stockId, setStockId] = useState("");
  const [keyword, setKeyword] = useState("");
  const [source, setSource] = useState("");
  const [limit, setLimit] = useState("50");
  const [offset, setOffset] = useState("0");

  const [collectStockId, setCollectStockId] = useState("");
  const [collectDisplay, setCollectDisplay] = useState("20");
  const [collectSort, setCollectSort] = useState("date");
  const [collectLoading, setCollectLoading] = useState(false);
  const [collectError, setCollectError] = useState("");
  const [collectResult, setCollectResult] = useState<NewsCollectResponse | null>(null);

  const [summarizeLoading, setSummarizeLoading] = useState(false);
  const [summarizeError, setSummarizeError] = useState("");
  const [summarizeResult, setSummarizeResult] = useState<AiSummarizeResponse | null>(null);

  const stockNameMap = useMemo(() => {
    const map = new Map<number, string>();
    stocks.forEach((stock) => map.set(stock.id, `${stock.stock_name} (${stock.stock_code})`));
    return map;
  }, [stocks]);

  const loadNews = async (overrides?: { stock_id?: number; offset?: number }) => {
    setLoading(true);
    setError("");
    try {
      const data = await repositories.news.listNews({
        stock_id: overrides?.stock_id ?? (stockId ? Number(stockId) : undefined),
        keyword: keyword || undefined,
        source: source || undefined,
        limit: Number(limit) || 50,
        offset: overrides?.offset ?? (Number(offset) || 0),
      });
      setItems(data);
      setSelectedNews((prev) => {
        if (data.length === 0) return null;
        if (!prev) return data[0];
        const found = data.find((item) => item.id === prev.id);
        return found ?? data[0];
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "뉴스 조회 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const loadStocks = async () => {
    try {
      const data = await repositories.stocks.list();
      setStocks(data);
      if (data.length > 0 && !collectStockId) setCollectStockId(String(data[0].id));
    } catch {
      // keep silent on stock list failure for now
    }
  };

  useEffect(() => {
    loadNews();
    loadStocks();
  }, []);

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    setOffset("0");
    setSelectedNews(null);
    setSelectedNewsIds([]);
    await loadNews({ offset: 0 });
  };

  const onReset = async () => {
    setStockId("");
    setKeyword("");
    setSource("");
    setLimit("50");
    setOffset("0");
    setSelectedNews(null);
    setSelectedNewsIds([]);
    setSummarizeError("");
    setSummarizeResult(null);
    setTimeout(() => {
      loadNews({ stock_id: undefined, offset: 0 });
    }, 0);
  };

  const onCollect = async () => {
    if (!collectStockId) {
      setCollectError("종목을 선택해주세요.");
      return;
    }
    setCollectLoading(true);
    setCollectError("");
    setCollectResult(null);
    try {
      const result = await repositories.news.collectNewsForStock({
        stock_id: Number(collectStockId),
        providers: ["naver"],
        display: Number(collectDisplay),
        sort: collectSort,
      });
      setCollectResult(result);
      setStockId(String(collectStockId));
      setOffset("0");
      setSelectedNews(null);
      setSelectedNewsIds([]);
      await loadNews({ stock_id: Number(collectStockId), offset: 0 });
    } catch (e) {
      console.error(e);
      setCollectError(e instanceof Error ? e.message : "뉴스 수집 실행 중 오류가 발생했습니다.");
    } finally {
      setCollectLoading(false);
    }
  };

  const onSummarizeSelected = async () => {
    if (selectedNewsIds.length === 0) return;
    setSummarizeLoading(true);
    setSummarizeError("");
    setSummarizeResult(null);
    try {
      const result = await repositories.news.summarizeSelectedNews(selectedNewsIds);
      setSummarizeResult(result);
      setSelectedNewsIds([]);
      await loadNews();
    } catch (e) {
      setSummarizeError(e instanceof Error ? e.message : "선택 뉴스 AI 요약 실행 중 오류가 발생했습니다.");
    } finally {
      setSummarizeLoading(false);
    }
  };

  const processedCount = useMemo(() => items.filter((item) => Boolean(item.ai_processed_at)).length, [items]);
  const numericOffset = Number(offset) || 0;
  const numericLimit = Number(limit) || 50;
  const canGoPrev = numericOffset > 0;
  const canGoNext = items.length >= numericLimit;

  const currentPageNewsIds = useMemo(() => items.map((item) => item.id), [items]);
  const allCurrentPageNewsSelected = currentPageNewsIds.length > 0 && currentPageNewsIds.every((id) => selectedNewsIds.includes(id));

  const onToggleSelectAllCurrentPage = () => {
    if (allCurrentPageNewsSelected) {
      setSelectedNewsIds((prev) => prev.filter((id) => !currentPageNewsIds.includes(id)));
      return;
    }
    setSelectedNewsIds((prev) => Array.from(new Set([...prev, ...currentPageNewsIds])));
  };

  const onPrevPage = async () => {
    const nextOffset = Math.max(0, numericOffset - numericLimit);
    setOffset(String(nextOffset));
    setSelectedNews(null);
    setSelectedNewsIds([]);
    await loadNews({ offset: nextOffset });
  };

  const onNextPage = async () => {
    const nextOffset = numericOffset + numericLimit;
    setOffset(String(nextOffset));
    setSelectedNews(null);
    setSelectedNewsIds([]);
    await loadNews({ offset: nextOffset });
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="뉴스 분석"
        description="수집된 뉴스를 투자 관점으로 점검하고 AI 요약·감성·중요도 신호를 확인합니다."
        action={<StatusBadge label={`AI 처리 ${processedCount}/${items.length}`} tone="blue" />}
      />

      <SectionCard title="뉴스 수집 실행">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
          <select className="select-control md:col-span-2" value={collectStockId} onChange={(e) => setCollectStockId(e.target.value)}>
            <option value="">종목 선택</option>
            {stocks.map((s) => (
              <option key={s.id} value={s.id}>{`${s.stock_name} (${s.stock_code})`}</option>
            ))}
          </select>
          <select className="select-control" value={collectDisplay} onChange={(e) => setCollectDisplay(e.target.value)}>
            <option value="10">10건</option>
            <option value="20">20건</option>
            <option value="50">50건</option>
          </select>
          <select className="select-control" value={collectSort} onChange={(e) => setCollectSort(e.target.value)}>
            <option value="date">최신순(date)</option>
            <option value="sim">정확도순(sim)</option>
          </select>
          <button className="btn btn-primary" onClick={onCollect} disabled={collectLoading}>
            {collectLoading ? "수집 중..." : "뉴스 수집 실행"}
          </button>
        </div>
        <p className="mt-2 text-xs text-muted">수집처: 네이버 뉴스 (providers: ["naver"])</p>

        {collectError ? <p className="mt-3 text-sm text-rose-600">{collectError}</p> : null}

        {collectResult ? (
          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
              <div><p className="text-xs text-muted">상태</p><p className="font-semibold">{collectResult.status}</p></div>
              <div><p className="text-xs text-muted">대상</p><p className="font-semibold">{collectResult.target}</p></div>
              <div><p className="text-xs text-muted">수집</p><p className="font-semibold">{collectResult.collected_count}</p></div>
              <div><p className="text-xs text-muted">저장</p><p className="font-semibold">{collectResult.saved_count}</p></div>
              <div><p className="text-xs text-muted">중복제외</p><p className="font-semibold">{collectResult.skipped_count}</p></div>
              <div className="col-span-2 md:col-span-1"><p className="text-xs text-muted">메시지</p><p className="font-semibold">{collectResult.message}</p></div>
            </div>
            <div className="mt-3">
              <button type="button" className="btn btn-secondary" onClick={() => navigate("/collection-runs")}>수집 이력 확인</button>
            </div>
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="검색">
        <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-7">
          <input className="input-control" placeholder="stock_id" value={stockId} onChange={(e) => setStockId(e.target.value)} />
          <div className="relative md:col-span-2">
            <Search size={16} className="absolute left-3 top-3.5 text-slate-400" />
            <input className="input-control pl-9" placeholder="keyword" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
          </div>
          <input className="input-control" placeholder="source (ex. naver_news)" value={source} onChange={(e) => setSource(e.target.value)} />
          <select className="select-control" value={limit} onChange={(e) => setLimit(e.target.value)}>
            <option value="20">20</option>
            <option value="50">50</option>
            <option value="100">100</option>
          </select>
          <input className="input-control" placeholder="offset" value={offset} onChange={(e) => setOffset(e.target.value)} />
          <div className="flex gap-2">
            <button type="submit" className="btn btn-primary">검색</button>
            <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
          </div>
        </form>
      </SectionCard>

      <div className="content-split">
        <SectionCard title="뉴스 목록" className="list-panel">
          {loading ? <p className="text-sm text-muted">로딩 중...</p> : null}
          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          {!loading && !error && items.length === 0 ? <EmptyState message="수집된 뉴스가 없습니다." /> : null}

          {!loading && !error && items.length > 0 ? (
            <>
              <div className="action-row">
                <div className="action-row-left">
                  <button type="button" className="btn btn-secondary" onClick={onSummarizeSelected} disabled={summarizeLoading || selectedNewsIds.length === 0}>
                    {summarizeLoading ? "AI 요약 중..." : `선택 ${selectedNewsIds.length}건 AI 요약`}
                  </button>
                </div>
                <div className="action-row-right">
                  <button type="button" className="btn btn-secondary" onClick={() => navigate("/collection-runs")}>수집 이력 확인</button>
                </div>
              </div>

              {summarizeResult ? (
                <div className="inline-result">
                  {summarizeResult.message || "선택 뉴스 AI 요약이 완료되었습니다."} (처리 {summarizeResult.processed_count ?? 0} / 성공 {summarizeResult.success_count ?? 0} / 실패 {summarizeResult.failed_count ?? 0})
                </div>
              ) : null}
              {summarizeError ? <div className="inline-result inline-error">{summarizeError}</div> : null}

              <div className="table-shell">
                <table className="data-table compact-table min-w-[920px]">
                  <thead>
                    <tr>
                      <th className="selection-cell">
                        <input
                          className="selection-checkbox"
                          type="checkbox"
                          checked={allCurrentPageNewsSelected}
                          onChange={onToggleSelectAllCurrentPage}
                        />
                      </th>
                      <th>ID</th>
                      <th>종목</th>
                      <th>제목</th>
                      <th>출처</th>
                      <th>발행일</th>
                      <th>중요도</th>
                      <th>감성</th>
                      <th>AI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((news) => {
                      const sentiment = sentimentMeta(news.ai_sentiment ?? news.sentiment);
                      const importance = importanceMeta(news.ai_importance_score ?? news.importance_score);
                      const selected = selectedNews?.id === news.id || selectedNewsIds.includes(news.id);
                      return (
                        <tr
                          key={news.id}
                          className={selected ? "selected-row row-clickable" : "row-clickable"}
                          onClick={() => setSelectedNews(news)}
                        >
                          <td className="selection-cell">
                            <input
                              className="selection-checkbox"
                              type="checkbox"
                              checked={selectedNewsIds.includes(news.id)}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedNewsIds((prev) => Array.from(new Set([...prev, news.id])));
                                  return;
                                }
                                setSelectedNewsIds((prev) => prev.filter((id) => id !== news.id));
                              }}
                            />
                          </td>
                          <td className="cell-nowrap">{news.id}</td>
                          <td className="cell-nowrap">{news.stock_id ?? "-"}</td>
                          <td className="min-w-[280px] cell-title cell-clamp-2">{news.title}</td>
                          <td className="min-w-[100px] cell-nowrap">{news.source ?? "-"}</td>
                          <td className="min-w-[140px] cell-nowrap cell-muted">{news.published_at ?? "-"}</td>
                          <td><StatusBadge label={importance.label} variant={importance.variant} /></td>
                          <td><StatusBadge label={sentiment.label} variant={sentiment.variant} /></td>
                          <td>
                            {news.ai_summary ? (
                              <StatusBadge label="완료" tone="emerald" />
                            ) : news.ai_summary_error ? (
                              <StatusBadge label="오류" tone="rose" />
                            ) : (
                              <StatusBadge label="미처리" tone="slate" />
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="pagination-bar">
                <div className="pagination-info">offset {offset} / {items.length}건 조회</div>
                <div className="flex gap-2">
                  <button type="button" className="btn btn-secondary" onClick={onPrevPage} disabled={!canGoPrev}>이전</button>
                  <button type="button" className="btn btn-secondary" onClick={onNextPage} disabled={!canGoNext}>다음</button>
                </div>
              </div>
            </>
          ) : null}
        </SectionCard>

        <SectionCard title="상세 분석" className="detail-panel">
          {!selectedNews ? (
            <EmptyState message="뉴스를 선택하세요." />
          ) : (
            <>
              <h3 className="detail-title">{selectedNews.title}</h3>
              <div className="detail-meta">
                <StatusBadge label={`종목 ${selectedNews.stock_id ?? "-"}`} tone="blue" />
                {selectedNews.stock_id && stockNameMap.get(selectedNews.stock_id) ? (
                  <StatusBadge label={stockNameMap.get(selectedNews.stock_id) as string} tone="slate" />
                ) : null}
                <StatusBadge label={importanceMeta(selectedNews.ai_importance_score ?? selectedNews.importance_score).label} variant={importanceMeta(selectedNews.ai_importance_score ?? selectedNews.importance_score).variant} />
                <StatusBadge label={sentimentMeta(selectedNews.ai_sentiment ?? selectedNews.sentiment).label} variant={sentimentMeta(selectedNews.ai_sentiment ?? selectedNews.sentiment).variant} />
              </div>

              <div className="detail-section">
                <p className="detail-label">기본 정보</p>
                <div className="detail-body">
                  <p>출처: {selectedNews.source ?? "-"}</p>
                  <p>발행일: {selectedNews.published_at ?? "-"}</p>
                  <p>AI 처리일시: {selectedNews.ai_processed_at ?? "-"}</p>
                </div>
              </div>

              <div className="detail-section">
                <p className="detail-label">태그</p>
                <div className="flex flex-wrap gap-1">
                  {(selectedNews.ai_tags || "").split(",").map((tag) => tag.trim()).filter(Boolean).map((tag) => (
                    <StatusBadge key={`${selectedNews.id}-${tag}`} label={tag} tone="slate" />
                  ))}
                  {!(selectedNews.ai_tags || "").trim() ? <StatusBadge label="미분류" tone="slate" /> : null}
                </div>
              </div>

              <div className="detail-section">
                <p className="detail-label">AI 요약</p>
                <p className="detail-body">{selectedNews.ai_summary ?? "AI 요약이 없습니다."}</p>
              </div>

              {selectedNews.ai_summary_error ? (
                <div className="detail-section">
                  <p className="detail-label">요약 오류</p>
                  <p className="detail-body text-rose-700">{selectedNews.ai_summary_error}</p>
                </div>
              ) : null}

              <div className="detail-section">
                <p className="detail-label">원문 링크</p>
                {selectedNews.url ? (
                  <a className="btn btn-secondary" href={selectedNews.url} target="_blank" rel="noreferrer">원문 열기</a>
                ) : (
                  <p className="detail-body">원문 링크가 없습니다.</p>
                )}
              </div>
            </>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

export default NewsPage;
