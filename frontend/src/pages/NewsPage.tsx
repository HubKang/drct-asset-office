import { ExternalLink, Info, ListCollapse, ListTree, Search, Sparkles, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type {
  NewsBulkDeleteResponse, NewsCollectSelectedResponse, NewsCollectionTarget,
  NewsItem, NewsSummarizeResponse,
} from "@/types/news";

const NEWS_LEFT_PANEL_STORAGE_KEY = "drct.news.leftPanelCollapsed";
type SummaryFilter = "all" | "unsummarized" | "summarized";

function formatDate(value?: string | null): string {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function formatShortDate(value?: string | null): { date: string; time: string } {
  const formatted = formatDate(value);
  if (formatted === "-") return { date: "-", time: "" };
  const [date, time = ""] = formatted.split(" ");
  return { date: date.slice(5).replace("-", "."), time };
}

function newsTimestamp(news: NewsItem): number {
  const value = news.published_at || news.collected_at || news.created_at;
  const parsed = Date.parse(value.includes("T") ? value : value.replace(" ", "T"));
  return Number.isFinite(parsed) ? parsed : 0;
}

function sortNewsLatestFirst(newsItems: NewsItem[]): NewsItem[] {
  return [...newsItems].sort((left, right) =>
    newsTimestamp(right) - newsTimestamp(left) || right.id - left.id,
  );
}

function toUserError(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) return fallback;
  const message = error.message?.trim() || "";
  if (/failed to fetch|networkerror/i.test(message)) return `${fallback} API 상태 또는 서버 연결을 확인해 주세요.`;
  if (/http 5/i.test(message)) return `${fallback} 서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.`;
  return message || fallback;
}

function summarizeResultText(result: NewsSummarizeResponse): string {
  return [
    `요약 완료 ${result.summarized}`,
    `기존 요약 ${result.skipped_existing}`,
    `URL 없음 ${result.missing_url}`,
    `URL 조회 실패 ${result.fetch_failed}`,
    `본문 확인 실패 ${result.extraction_failed}`,
    `처리 실패 ${result.processing_failed}`,
  ].join(" · ");
}

function NewsPage() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [collectionTargets, setCollectionTargets] = useState<NewsCollectionTarget[]>([]);
  const [currentStockId, setCurrentStockId] = useState<number | null>(null);
  const [checkedStockIds, setCheckedStockIds] = useState<number[]>([]);
  const [checkedNewsIds, setCheckedNewsIds] = useState<number[]>([]);
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [panelCollapsed, setPanelCollapsed] = useState(() =>
    typeof window !== "undefined" && window.localStorage.getItem(NEWS_LEFT_PANEL_STORAGE_KEY) === "true",
  );
  const [targetKeyword, setTargetKeyword] = useState("");
  const [targetFilter, setTargetFilter] = useState("");
  const [collectSort, setCollectSort] = useState("date");
  const [summaryFilter, setSummaryFilter] = useState<SummaryFilter>("all");
  const [newsPage, setNewsPage] = useState(1);
  const [newsTotalCount, setNewsTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [targetLoading, setTargetLoading] = useState(false);
  const [collectLoading, setCollectLoading] = useState(false);
  const [summarizeLoading, setSummarizeLoading] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [feedbackError, setFeedbackError] = useState("");
  const [contentFailureIds, setContentFailureIds] = useState<number[]>([]);
  const [policyOpen, setPolicyOpen] = useState(false);
  const policyRef = useRef<HTMLDivElement | null>(null);
  const pageSize = 20;

  const filteredTargets = useMemo(() => {
    const query = targetFilter.trim().toLowerCase();
    return query ? collectionTargets.filter((item) =>
      item.stock_name.toLowerCase().includes(query) || item.stock_code.toLowerCase().includes(query),
    ) : collectionTargets;
  }, [collectionTargets, targetFilter]);
  const activeStock = useMemo(
    () => collectionTargets.find((item) => item.stock_id === currentStockId) ?? null,
    [collectionTargets, currentStockId],
  );
  const totalPages = Math.max(1, Math.ceil(newsTotalCount / pageSize));
  const allChecked = items.length > 0 && items.every((item) => checkedNewsIds.includes(item.id));

  const loadTargets = async () => {
    setTargetLoading(true);
    try {
      const data = await repositories.news.listCollectionTargets();
      setCollectionTargets(data);
      setCurrentStockId((previous) => previous ?? data[0]?.stock_id ?? null);
    } finally {
      setTargetLoading(false);
    }
  };

  const loadNews = async (stockId: number | null, page: number, filter: SummaryFilter) => {
    if (!stockId) {
      setItems([]); setNewsTotalCount(0); setCheckedNewsIds([]); return [];
    }
    setLoading(true); setError("");
    try {
      const data = await repositories.news.listNewsPage({
        stock_id: stockId,
        summary_status: filter === "all" ? undefined : filter,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      const sortedItems = sortNewsLatestFirst(data.items);
      setItems(sortedItems); setNewsTotalCount(data.total_count);
      setCheckedNewsIds((previous) => previous.filter((id) => sortedItems.some((item) => item.id === id)));
      setSelectedNews((previous) => previous ? sortedItems.find((item) => item.id === previous.id) ?? previous : null);
      return sortedItems;
    } catch (cause) {
      setError(toUserError(cause, "뉴스 목록 조회에 실패했습니다."));
      return [];
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadTargets(); }, []);
  useEffect(() => { window.localStorage.setItem(NEWS_LEFT_PANEL_STORAGE_KEY, String(panelCollapsed)); }, [panelCollapsed]);
  useEffect(() => {
    setNewsPage(1); setCheckedNewsIds([]); setSelectedNews(null); setIsDrawerOpen(false);
    setFeedback(""); setFeedbackError("");
  }, [currentStockId, summaryFilter]);
  useEffect(() => { void loadNews(currentStockId, newsPage, summaryFilter); }, [currentStockId, newsPage, summaryFilter]);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setIsDrawerOpen(false); setPolicyOpen(false); }
    };
    const onPointerDown = (event: MouseEvent) => {
      if (policyRef.current && !policyRef.current.contains(event.target as Node)) setPolicyOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("mousedown", onPointerDown);
    return () => { window.removeEventListener("keydown", onKeyDown); window.removeEventListener("mousedown", onPointerDown); };
  }, []);

  const toggleStock = (stockId: number) => setCheckedStockIds((previous) =>
    previous.includes(stockId) ? previous.filter((id) => id !== stockId) : [...previous, stockId],
  );
  const openDetail = (news: NewsItem) => { setSelectedNews(news); setIsDrawerOpen(true); };

  const collectSelected = async () => {
    const stockIds = checkedStockIds.length ? checkedStockIds : currentStockId ? [currentStockId] : [];
    if (!stockIds.length) { setFeedbackError("관심종목 목록에서 수집할 종목을 선택해 주세요."); return; }
    setCollectLoading(true); setFeedback(""); setFeedbackError("");
    try {
      const result: NewsCollectSelectedResponse = await repositories.news.collectNewsForSelectedWatchlist({
        stock_ids: stockIds, providers: ["naver"], display: 20, sort: collectSort,
      });
      const saved = result.results.reduce((sum, item) => sum + item.saved_count, 0);
      const duplicate = result.results.reduce((sum, item) => sum + (item.duplicate_skipped ?? 0), 0);
      const mismatch = result.results.reduce((sum, item) => sum + (item.name_mismatch_skipped ?? 0), 0);
      const excluded = result.results.reduce((sum, item) => sum + (item.excluded_skipped ?? 0), 0);
      const invalid = result.results.reduce((sum, item) => sum + (item.invalid_skipped ?? 0), 0);
      const ranges = result.results.filter((item) => item.from_date && item.to_date);
      const rangeText = ranges.length === 1 ? ` · 검색 ${ranges[0].from_date} ~ ${ranges[0].to_date}` : "";
      setFeedback(saved
        ? `수집 완료 · 신규 ${saved} · 중복 ${duplicate} · 종목명 미포함 ${mismatch} · 삭제 제외 ${excluded} · 유효하지 않음 ${invalid} · 실패 ${result.failed_count}${rangeText}`
        : `검색 완료 · 종목명이 포함된 신규 뉴스가 없습니다. · 중복 ${duplicate} · 종목명 미포함 ${mismatch} · 삭제 제외 ${excluded} · 유효하지 않음 ${invalid} · 실패 ${result.failed_count}${rangeText}`);
      await loadTargets(); await loadNews(currentStockId, newsPage, summaryFilter);
    } catch (cause) {
      setFeedbackError(toUserError(cause, "선택한 관심종목의 뉴스 수집에 실패했습니다."));
    } finally { setCollectLoading(false); }
  };

  const summarize = async (ids: number[]) => {
    if (!ids.length) { setFeedbackError("요약할 뉴스를 선택해 주세요."); return; }
    setSummarizeLoading(true); setFeedback(""); setFeedbackError("");
    try {
      const result = await repositories.news.summarizeSelectedNews(ids);
      if (ids.length === 1) {
        setContentFailureIds((previous) => result.extraction_failed
          ? Array.from(new Set([...previous, ids[0]]))
          : previous.filter((id) => id !== ids[0]));
      }
      setFeedback(summarizeResultText(result)); setCheckedNewsIds([]);
      await loadTargets();
      const refreshed = await loadNews(currentStockId, newsPage, summaryFilter);
      if (ids.length === 1) setSelectedNews(refreshed.find((item) => item.id === ids[0]) ?? null);
    } catch (cause) {
      setFeedbackError(toUserError(cause, "선택 요약 중 오류가 발생했습니다."));
    } finally { setSummarizeLoading(false); }
  };

  const deleteNews = async (ids: number[]) => {
    if (!ids.length || !window.confirm(`선택한 뉴스 ${ids.length}건을 삭제하시겠습니까?\n오늘 다시 수집해도 같은 기사는 제외됩니다.`)) return;
    setFeedback(""); setFeedbackError("");
    try {
      const result: NewsBulkDeleteResponse = await repositories.news.deleteNewsBulk(ids);
      setFeedback(`삭제 완료 ${result.deleted}건${result.failed ? ` · 실패 ${result.failed}건` : ""}`);
      setCheckedNewsIds([]);
      if (selectedNews && ids.includes(selectedNews.id)) { setSelectedNews(null); setIsDrawerOpen(false); }
      const targetPage = ids.length >= items.length && newsPage > 1 ? newsPage - 1 : newsPage;
      setNewsPage(targetPage); await loadTargets(); await loadNews(currentStockId, targetPage, summaryFilter);
    } catch (cause) { setFeedbackError(toUserError(cause, "뉴스 삭제 중 오류가 발생했습니다.")); }
  };

  return <div className="space-y-4 news-inbox-page">
    <PageHeader
      title="뉴스 관리"
      description="관심종목 뉴스를 수집하고 필요한 기사만 선별해 요약합니다."
      action={<div className="flex flex-wrap gap-2"><StatusBadge label="데이터 소스 API" tone="slate" /><StatusBadge label="API 정상" tone="emerald" /></div>}
    />

    <SectionCard className="news-inbox-toolbar-card">
      <div className="news-inbox-toolbar">
        <label className="news-inbox-search"><Search size={16} /><input value={targetKeyword} placeholder="종목명 또는 종목코드 검색" onChange={(e) => setTargetKeyword(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") setTargetFilter(targetKeyword); }} /></label>
        <select className="select-control" value={collectSort} onChange={(e) => setCollectSort(e.target.value)} aria-label="뉴스 수집 정렬"><option value="date">최신순</option><option value="sim">정확도순</option></select>
        <div className="news-collect-action" ref={policyRef}>
          <button type="button" className="btn btn-primary" disabled={collectLoading || (!currentStockId && !checkedStockIds.length)} onClick={() => void collectSelected()}>{collectLoading ? "수집 중…" : "선택 뉴스 수집"}</button>
          <button type="button" className="news-policy-info" aria-label="뉴스 수집 정책 보기" aria-expanded={policyOpen} aria-controls="news-collection-policy" onClick={() => setPolicyOpen((open) => !open)}><Info size={16} /></button>
          {policyOpen ? <div id="news-collection-policy" className="news-policy-popover" role="dialog" aria-labelledby="news-collection-policy-title">
            <strong id="news-collection-policy-title">뉴스 수집 정책</strong>
            <ul>
              <li><b>처음 수집</b><span>최근 90일에서 종목명이 제목에 포함된 기사를 최대 20건 수집합니다.</span></li>
              <li><b>이후 수집</b><span>마지막 검색 완료일 다음 날부터 오늘까지 새 기사만 확인합니다.</span></li>
              <li><b>오늘 재확인</b><span>오늘 이미 수집한 종목은 오늘 기사만 다시 확인합니다.</span></li>
              <li><b>기사 선별</b><span>DB의 공식 종목명이 기사 제목에 포함된 경우만 저장합니다.</span></li>
              <li><b>중복·삭제</b><span>중복 기사는 저장하지 않으며, 오늘 삭제한 기사는 같은 날 다시 수집하지 않습니다.</span></li>
              <li><b>다음 날</b><span>전날 삭제 제외 기록을 정리하고 새 날짜 기준으로 관리합니다.</span></li>
              <li><b>AI 요약</b><span>수집할 때는 요약하지 않습니다. 필요한 기사를 선택한 후 요약합니다.</span></li>
            </ul>
          </div> : null}
        </div>
      </div>
    </SectionCard>

    {feedback ? <div className="news-inbox-feedback" role="status">{feedback}</div> : null}
    {feedbackError ? <div className="news-inbox-feedback error" role="alert">{feedbackError}</div> : null}

    <div className={`drct-split-layout news-page-layout ${panelCollapsed ? "drct-split-layout--collapsed" : ""}`}>
      <aside className="drct-left-panel">
        <div className="drct-left-panel-rail"><button type="button" className="sije-icon-button" onClick={() => setPanelCollapsed(false)} aria-label="관심종목 목록 펼치기"><ListTree size={17} /></button><span className="drct-left-panel-rail-label">관심종목</span></div>
        {!panelCollapsed ? <SectionCard title={<span className="drct-left-panel-title"><span>관심종목 Inbox</span><button type="button" className="sije-icon-button" onClick={() => setPanelCollapsed(true)} aria-label="관심종목 목록 접기"><ListCollapse size={17} /></button></span>}>
          <div className="watchlist-selection-count mb-2">수집 선택 {checkedStockIds.length}종목</div>
          <div className="news-target-list">
            {targetLoading ? <p className="text-sm text-muted py-3">관심종목을 불러오는 중입니다.</p> : null}
            {!targetLoading && !filteredTargets.length ? <p className="text-sm text-muted py-3">관심종목이 없습니다.</p> : null}
            {filteredTargets.map((target) => <button key={target.stock_id} type="button" className={`news-target-item ${currentStockId === target.stock_id ? "selected" : ""}`} onClick={() => setCurrentStockId(target.stock_id)}>
              <input type="checkbox" aria-label={`${target.stock_name} 수집 선택`} checked={checkedStockIds.includes(target.stock_id)} onClick={(e) => e.stopPropagation()} onChange={() => toggleStock(target.stock_id)} />
              <span className="stock-cell min-w-0"><strong>{target.stock_name}</strong><span className="news-target-metrics"><span>뉴스 <b>{target.news_count}</b></span><i>·</i><span>요약 <b>{target.summarized_count}</b></span><i>·</i><span>최종수집 <b>{target.latest_collected_at ? formatDate(target.latest_collected_at).slice(5, 10).replace("-", ".") : "-"}</b></span></span></span>
            </button>)}
          </div>
        </SectionCard> : null}
      </aside>

      <main className="drct-main-panel">
        <SectionCard className="news-inbox-list-card">
          <div className="news-list-header">
            <h3 className="section-title m-0">{activeStock ? `${activeStock.stock_name} 뉴스 Inbox` : "뉴스 Inbox"}</h3>
            <div className="news-inbox-actions"><button type="button" className="btn btn-secondary" disabled={!checkedNewsIds.length || summarizeLoading} onClick={() => void summarize(checkedNewsIds)}><Sparkles size={15} />{summarizeLoading ? "요약 중…" : `선택 요약 ${checkedNewsIds.length || ""}`}</button><button type="button" className="btn btn-secondary danger" disabled={!checkedNewsIds.length || loading} onClick={() => void deleteNews(checkedNewsIds)}><Trash2 size={15} />{`선택 삭제 ${checkedNewsIds.length || ""}`}</button></div>
          </div>
          <div className="news-inbox-filter" role="group" aria-label="요약 상태 필터">{(["all", "unsummarized", "summarized"] as SummaryFilter[]).map((filter) => <button key={filter} type="button" className={summaryFilter === filter ? "active" : ""} onClick={() => setSummaryFilter(filter)}>{filter === "all" ? "전체" : filter === "unsummarized" ? "미요약" : "요약"}</button>)}</div>

          {!currentStockId ? <p className="news-inbox-empty">관심종목을 선택하세요.</p> : null}
          {loading ? <p className="news-inbox-empty">뉴스를 불러오는 중입니다.</p> : null}
          {error ? <p className="news-inbox-empty error">{error}</p> : null}
          {!loading && !error && currentStockId && !items.length ? <p className="news-inbox-empty">조건에 맞는 뉴스가 없습니다.</p> : null}
          {!loading && !error && items.length ? <>
            <div className="news-inbox-table-shell"><table className="news-inbox-table"><thead><tr><th><input type="checkbox" aria-label="현재 페이지 전체 선택" checked={allChecked} onChange={(e) => setCheckedNewsIds(e.target.checked ? items.map((item) => item.id) : [])} /></th><th>일시</th><th>뉴스</th><th>기사</th><th>작업</th></tr></thead><tbody>
              {items.map((news) => { const date = formatShortDate(news.published_at); const checked = checkedNewsIds.includes(news.id); return <tr key={news.id} tabIndex={0} onClick={() => openDetail(news)} onKeyDown={(e) => { if (e.key === "Enter") openDetail(news); }}>
                <td onClick={(e) => e.stopPropagation()}><input type="checkbox" aria-label={`${news.title} 선택`} checked={checked} onChange={(e) => setCheckedNewsIds((previous) => e.target.checked ? [...previous, news.id] : previous.filter((id) => id !== news.id))} /></td>
                <td><strong>{date.date}</strong><small>{date.time}</small></td>
                <td><strong className="news-inbox-title">{news.title}</strong>{news.summary ? <p className="news-inbox-summary">{news.summary}</p> : <span className="news-inbox-unsummarized">미요약</span>}</td>
                <td onClick={(e) => e.stopPropagation()}>{news.url ? <a className="news-inbox-link" href={news.url} target="_blank" rel="noreferrer">기사 열기 <ExternalLink size={13} /></a> : <span className="cell-muted">URL 없음</span>}</td>
                <td onClick={(e) => e.stopPropagation()}><button type="button" className="news-row-delete" aria-label={`${news.title} 삭제`} onClick={() => void deleteNews([news.id])}><Trash2 size={15} /></button></td>
              </tr>; })}
            </tbody></table></div>
            <div className="pagination-bar"><span className="pagination-info">전체 {newsTotalCount}건 · {newsPage}/{totalPages} 페이지</span><div className="pagination-actions"><button type="button" className="btn btn-secondary" disabled={newsPage <= 1 || loading} onClick={() => setNewsPage((page) => page - 1)}>이전</button><button type="button" className="btn btn-secondary" disabled={newsPage >= totalPages || loading} onClick={() => setNewsPage((page) => page + 1)}>다음</button></div></div>
          </> : null}
        </SectionCard>
      </main>
    </div>

    {isDrawerOpen && selectedNews ? <div className="news-detail-overlay" onClick={() => setIsDrawerOpen(false)}><aside className="news-detail-drawer" role="dialog" aria-modal="true" aria-label="뉴스 상세" onClick={(e) => e.stopPropagation()}>
      <header><div><span>NEWS DETAIL</span><h3>뉴스 상세</h3></div><button type="button" onClick={() => setIsDrawerOpen(false)} aria-label="닫기"><X size={19} /></button></header>
      <div className="news-detail-content"><div className="news-detail-meta"><span>{selectedNews.stock_name ?? "관심종목"}</span><span>{selectedNews.stock_code ?? "-"}</span><span>발행 {formatDate(selectedNews.published_at)}</span><span>수집 {formatDate(selectedNews.collected_at)}</span></div><h4>{selectedNews.title}</h4>
        <section className={`news-detail-summary ${selectedNews.summary ? "" : "empty"}`}><div><span>기사 요약</span>{selectedNews.summary ? <b>요약 완료</b> : contentFailureIds.includes(selectedNews.id) ? <b>본문 확인 실패</b> : <b>미요약</b>}</div>{selectedNews.summary ? <p>{selectedNews.summary}</p> : <>{contentFailureIds.includes(selectedNews.id) ? <p>원문 기사 본문을 정확히 확인하지 못해 요약하지 않았습니다.</p> : <p>아직 요약하지 않은 기사입니다. 원문을 확인한 뒤 필요할 때만 요약하세요.</p>}<button type="button" className="btn btn-primary" disabled={summarizeLoading || !selectedNews.url} onClick={() => void summarize([selectedNews.id])}><Sparkles size={15} />이 기사 요약</button></>}</section>
        {selectedNews.url ? <a className="btn btn-secondary news-detail-source-link" href={selectedNews.url} target="_blank" rel="noreferrer">원문 기사 열기 <ExternalLink size={15} /></a> : <p className="news-detail-no-url">원문 링크가 없습니다.</p>}
      </div>
      <footer><button type="button" className="btn btn-secondary danger" onClick={() => void deleteNews([selectedNews.id])}><Trash2 size={15} />삭제</button></footer>
    </aside></div> : null}
  </div>;
}

export default NewsPage;
