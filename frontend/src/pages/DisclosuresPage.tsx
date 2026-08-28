import { ExternalLink, Info, ListCollapse, ListTree, Search, Sparkles, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { AiSummarizeResponse } from "@/types/analysis";
import type { Disclosure, DisclosureCollectSelectedResponse } from "@/types/disclosure";
import type { Watchlist } from "@/types/watchlist";

const PANEL_KEY = "drct.disclosures.leftPanelCollapsed";
type SummaryFilter = "all" | "unsummarized" | "summarized";
type DisclosureTarget = { stock_id: number; stock_code: string; stock_name: string; disclosure_count: number; summarized_count: number; latest_collected_at: string | null };
type SimpleSummary = { summary: string; keywords: string[] };

function formatDate(value?: string | null): string {
  return value ? value.replace("T", " ").slice(0, 16) : "-";
}
function formatShortDate(value?: string | null): { date: string; time: string } {
  const formatted = formatDate(value);
  if (formatted === "-") return { date: "-", time: "" };
  const [date, time = ""] = formatted.split(" ");
  return { date: date.slice(5).replace("-", "."), time };
}
function timestamp(item: Disclosure): number {
  const value = item.disclosed_at || item.created_at;
  const parsed = Date.parse(value.includes("T") ? value : value.replace(" ", "T"));
  return Number.isFinite(parsed) ? parsed : 0;
}
function hasSummary(item: Disclosure): boolean { return Boolean(item.ai_summary?.trim() || item.summary?.trim()); }
function splitKeywords(value?: string | null): string[] {
  if (!value) return [];
  return value.split(/[,|\n]/).map((keyword) => keyword.replace(/^[-•]\s*/, "").trim()).filter(Boolean)
    .filter((keyword, index, values) => values.indexOf(keyword) === index).slice(0, 8);
}
function extractSection(text: string, title: string): string {
  return new RegExp(`\\[${title}\\]\\s*([\\s\\S]*?)(?=\\n\\s*\\[[^\\]]+\\]|$)`).exec(text)?.[1]?.trim() ?? "";
}
function parseSummary(item: Disclosure): SimpleSummary {
  const raw = item.ai_summary?.trim() || item.summary?.trim() || "";
  let summary = "";
  let keywords: string[] = [];
  if (raw.startsWith("{")) {
    try {
      const parsed = JSON.parse(raw) as { summary?: unknown; keywords?: unknown };
      summary = typeof parsed.summary === "string" ? parsed.summary.trim() : "";
      keywords = Array.isArray(parsed.keywords) ? parsed.keywords.map(String).map((value) => value.trim()).filter(Boolean) : [];
    } catch { summary = ""; }
  }
  if (!summary && raw) summary = (extractSection(raw, "공시 요약") || extractSection(raw, "핵심 요약") || raw).trim();
  if (!keywords.length && raw) keywords = splitKeywords(extractSection(raw, "관련 키워드"));
  if (!keywords.length) keywords = splitKeywords(item.ai_tags);
  return { summary, keywords };
}
function toUserError(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) return fallback;
  const message = error.message?.trim() || "";
  if (/failed to fetch|networkerror/i.test(message)) return `${fallback} API 상태 또는 서버 연결을 확인해 주세요.`;
  if (/http 5/i.test(message)) return `${fallback} 서버 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.`;
  return message || fallback;
}
function summarizeResultText(result: AiSummarizeResponse): string {
  return `요약 완료 ${result.success_count ?? 0}건 · 처리 실패 ${result.failed_count ?? 0}건`;
}

function DisclosuresPage() {
  const [targets, setTargets] = useState<DisclosureTarget[]>([]);
  const [items, setItems] = useState<Disclosure[]>([]);
  const [currentStockId, setCurrentStockId] = useState<number | null>(null);
  const [checkedStockIds, setCheckedStockIds] = useState<number[]>([]);
  const [checkedIds, setCheckedIds] = useState<number[]>([]);
  const [selected, setSelected] = useState<Disclosure | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [panelCollapsed, setPanelCollapsed] = useState(() => typeof window !== "undefined" && window.localStorage.getItem(PANEL_KEY) === "true");
  const [targetKeyword, setTargetKeyword] = useState("");
  const [targetFilter, setTargetFilter] = useState("");
  const [sortOrder, setSortOrder] = useState("latest");
  const [summaryFilter, setSummaryFilter] = useState<SummaryFilter>("all");
  const [targetLoading, setTargetLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [collectLoading, setCollectLoading] = useState(false);
  const [summarizeLoading, setSummarizeLoading] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [feedbackError, setFeedbackError] = useState("");
  const [policyOpen, setPolicyOpen] = useState(false);
  const policyRef = useRef<HTMLDivElement | null>(null);

  const filteredTargets = useMemo(() => {
    const query = targetFilter.trim().toLowerCase();
    return query ? targets.filter((target) => target.stock_name.toLowerCase().includes(query) || target.stock_code.toLowerCase().includes(query)) : targets;
  }, [targets, targetFilter]);
  const activeTarget = useMemo(() => targets.find((target) => target.stock_id === currentStockId) ?? null, [targets, currentStockId]);
  const visibleItems = useMemo(() => {
    const filtered = items.filter((item) => summaryFilter === "all" || (summaryFilter === "summarized" ? hasSummary(item) : !hasSummary(item)));
    return [...filtered].sort((left, right) => sortOrder === "oldest" ? timestamp(left) - timestamp(right) || left.id - right.id : timestamp(right) - timestamp(left) || right.id - left.id);
  }, [items, sortOrder, summaryFilter]);
  const allChecked = visibleItems.length > 0 && visibleItems.every((item) => checkedIds.includes(item.id));

  const buildTargets = (watchlist: Watchlist[], disclosures: Disclosure[]): DisclosureTarget[] => watchlist.map((watch) => {
    const stockItems = disclosures.filter((item) => item.stock_id === watch.stock_id);
    return {
      stock_id: watch.stock_id, stock_code: watch.stock_code, stock_name: watch.stock_name,
      disclosure_count: stockItems.length, summarized_count: stockItems.filter(hasSummary).length,
      latest_collected_at: stockItems.map((item) => item.created_at).filter(Boolean).sort((a, b) => b.localeCompare(a))[0] ?? null,
    };
  });
  const loadTargets = async () => {
    setTargetLoading(true);
    try {
      const [watchlist, disclosures] = await Promise.all([
        repositories.watchlist.list({ is_active: 1, limit: 200, offset: 0 }),
        repositories.disclosures.listDisclosures({ limit: 500, offset: 0 }),
      ]);
      const next = buildTargets(watchlist, disclosures);
      setTargets(next); setCurrentStockId((previous) => previous ?? next[0]?.stock_id ?? null);
    } finally { setTargetLoading(false); }
  };
  const loadItems = async (stockId: number | null): Promise<Disclosure[]> => {
    if (!stockId) { setItems([]); setCheckedIds([]); return []; }
    setLoading(true); setError("");
    try {
      const data = await repositories.disclosures.listDisclosures({ stock_id: stockId, limit: 100, offset: 0 });
      setItems(data); setCheckedIds((previous) => previous.filter((id) => data.some((item) => item.id === id)));
      setSelected((previous) => previous ? data.find((item) => item.id === previous.id) ?? previous : null);
      return data;
    } catch (cause) { setError(toUserError(cause, "공시 목록 조회에 실패했습니다.")); return []; }
    finally { setLoading(false); }
  };

  useEffect(() => { void loadTargets(); }, []);
  useEffect(() => { window.localStorage.setItem(PANEL_KEY, String(panelCollapsed)); }, [panelCollapsed]);
  useEffect(() => { setCheckedIds([]); setSelected(null); setDrawerOpen(false); setFeedback(""); setFeedbackError(""); void loadItems(currentStockId); }, [currentStockId]);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") { setDrawerOpen(false); setPolicyOpen(false); } };
    const onPointerDown = (event: MouseEvent) => { if (policyRef.current && !policyRef.current.contains(event.target as Node)) setPolicyOpen(false); };
    window.addEventListener("keydown", onKeyDown); window.addEventListener("mousedown", onPointerDown);
    return () => { window.removeEventListener("keydown", onKeyDown); window.removeEventListener("mousedown", onPointerDown); };
  }, []);

  const toggleStock = (stockId: number) => setCheckedStockIds((previous) => previous.includes(stockId) ? previous.filter((id) => id !== stockId) : [...previous, stockId]);
  const collectSelected = async () => {
    const stockIds = checkedStockIds.length ? checkedStockIds : currentStockId ? [currentStockId] : [];
    if (!stockIds.length) { setFeedbackError("관심종목 목록에서 수집할 종목을 선택해 주세요."); return; }
    setCollectLoading(true); setFeedback(""); setFeedbackError("");
    try {
      const result: DisclosureCollectSelectedResponse = await repositories.disclosures.collectDisclosuresForSelectedWatchlist({ stock_ids: stockIds, days: 30, page_count: 10 });
      const saved = result.results.reduce((sum, item) => sum + item.saved_count, 0);
      const skipped = result.results.reduce((sum, item) => sum + item.skipped_count, 0);
      setFeedback(`수집 완료 · 신규 ${saved} · 중복/제외 ${skipped} · 실패 ${result.failed_count}`);
      await loadTargets(); await loadItems(currentStockId);
    } catch (cause) { setFeedbackError(toUserError(cause, "선택한 관심종목의 공시 수집에 실패했습니다.")); }
    finally { setCollectLoading(false); }
  };
  const summarize = async (ids: number[]) => {
    if (!ids.length) { setFeedbackError("요약할 공시를 선택해 주세요."); return; }
    setSummarizeLoading(true); setFeedback(""); setFeedbackError("");
    try {
      const result = await repositories.disclosures.summarizeSelectedDisclosures(ids);
      setFeedback(summarizeResultText(result)); setCheckedIds([]); await loadTargets();
      const refreshed = await loadItems(currentStockId);
      if (ids.length === 1) setSelected(refreshed.find((item) => item.id === ids[0]) ?? null);
    } catch (cause) { setFeedbackError(toUserError(cause, "선택 요약 중 오류가 발생했습니다.")); }
    finally { setSummarizeLoading(false); }
  };
  const deleteItems = async (ids: number[]) => {
    if (!ids.length || !window.confirm(`선택한 공시 ${ids.length}건을 삭제하시겠습니까?`)) return;
    setFeedback(""); setFeedbackError("");
    try {
      const result = await repositories.disclosures.deleteDisclosuresBulk(ids);
      setFeedback(`삭제 완료 ${result.deleted}건${result.failed ? ` · 실패 ${result.failed}건` : ""}`); setCheckedIds([]);
      if (selected && ids.includes(selected.id)) { setSelected(null); setDrawerOpen(false); }
      await loadTargets(); await loadItems(currentStockId);
    } catch (cause) { setFeedbackError(toUserError(cause, "공시 삭제 중 오류가 발생했습니다.")); }
  };

  const selectedSummary = selected ? parseSummary(selected) : null;
  return <div className="space-y-4 news-inbox-page disclosure-inbox-page">
    <PageHeader title="공시 관리" description="관심종목 공시를 수집하고 필요한 공시만 선별해 요약합니다." action={<div className="flex flex-wrap gap-2"><StatusBadge label="데이터 소스 API" tone="slate" /><StatusBadge label="API 정상" tone="emerald" /></div>} />
    <SectionCard className="news-inbox-toolbar-card"><div className="news-inbox-toolbar">
      <label className="news-inbox-search"><Search size={16} /><input value={targetKeyword} placeholder="종목명 또는 종목코드 검색" onChange={(e) => setTargetKeyword(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") setTargetFilter(targetKeyword); }} /></label>
      <select className="select-control" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} aria-label="공시 정렬"><option value="latest">최신순</option><option value="oldest">오래된순</option></select>
      <div className="news-collect-action" ref={policyRef}><button type="button" className="btn btn-primary" disabled={collectLoading || (!currentStockId && !checkedStockIds.length)} onClick={() => void collectSelected()}>{collectLoading ? "수집 중…" : "선택 공시 수집"}</button>
        <button type="button" className="news-policy-info" aria-label="공시 수집 정책 보기" aria-expanded={policyOpen} onClick={() => setPolicyOpen((open) => !open)}><Info size={16} /></button>
        {policyOpen ? <div className="news-policy-popover" role="dialog"><strong>공시 수집 정책</strong><ul><li><b>수집 범위</b><span>선택한 관심종목의 최근 30일 DART 공시를 확인합니다.</span></li><li><b>중복 방지</b><span>접수번호가 같은 공시는 다시 저장하지 않습니다.</span></li><li><b>선택 요약</b><span>수집할 때는 요약하지 않고, 필요한 공시를 선택한 뒤 요약합니다.</span></li></ul></div> : null}
      </div>
    </div></SectionCard>
    {feedback ? <div className="news-inbox-feedback" role="status">{feedback}</div> : null}
    {feedbackError ? <div className="news-inbox-feedback error" role="alert">{feedbackError}</div> : null}
    <div className={`drct-split-layout news-page-layout ${panelCollapsed ? "drct-split-layout--collapsed" : ""}`}>
      <aside className="drct-left-panel"><div className="drct-left-panel-rail"><button type="button" className="sije-icon-button" onClick={() => setPanelCollapsed(false)} aria-label="관심종목 목록 펼치기"><ListTree size={17} /></button><span className="drct-left-panel-rail-label">관심종목</span></div>
        {!panelCollapsed ? <SectionCard title={<span className="drct-left-panel-title"><span>관심종목 Inbox</span><button type="button" className="sije-icon-button" onClick={() => setPanelCollapsed(true)} aria-label="관심종목 목록 접기"><ListCollapse size={17} /></button></span>}><div className="watchlist-selection-count mb-2">수집 선택 {checkedStockIds.length}종목</div><div className="news-target-list">
          {targetLoading ? <p className="text-sm text-muted py-3">관심종목을 불러오는 중입니다.</p> : null}{!targetLoading && !filteredTargets.length ? <p className="text-sm text-muted py-3">관심종목이 없습니다.</p> : null}
          {filteredTargets.map((target) => <button key={target.stock_id} type="button" className={`news-target-item ${currentStockId === target.stock_id ? "selected" : ""}`} onClick={() => setCurrentStockId(target.stock_id)}><input type="checkbox" aria-label={`${target.stock_name} 수집 선택`} checked={checkedStockIds.includes(target.stock_id)} onClick={(e) => e.stopPropagation()} onChange={() => toggleStock(target.stock_id)} /><span className="stock-cell min-w-0"><strong>{target.stock_name}</strong><span className="news-target-metrics"><span>공시 <b>{target.disclosure_count}</b></span><i>·</i><span>요약 <b>{target.summarized_count}</b></span><i>·</i><span>최종수집 <b>{target.latest_collected_at ? formatDate(target.latest_collected_at).slice(5, 10).replace("-", ".") : "-"}</b></span></span></span></button>)}
        </div></SectionCard> : null}
      </aside>
      <main className="drct-main-panel"><SectionCard className="news-inbox-list-card"><div className="news-list-header"><h3 className="section-title m-0">{activeTarget ? `${activeTarget.stock_name} 공시 Inbox` : "공시 Inbox"}</h3><div className="news-inbox-actions"><button type="button" className="btn btn-secondary" disabled={!checkedIds.length || summarizeLoading} onClick={() => void summarize(checkedIds)}><Sparkles size={15} />{summarizeLoading ? "요약 중…" : `선택 요약 ${checkedIds.length || ""}`}</button><button type="button" className="btn btn-secondary danger" disabled={!checkedIds.length || loading} onClick={() => void deleteItems(checkedIds)}><Trash2 size={15} />{`선택 삭제 ${checkedIds.length || ""}`}</button></div></div>
        <div className="news-inbox-filter" role="group" aria-label="요약 상태 필터">{(["all", "unsummarized", "summarized"] as SummaryFilter[]).map((filter) => <button key={filter} type="button" className={summaryFilter === filter ? "active" : ""} onClick={() => setSummaryFilter(filter)}>{filter === "all" ? "전체" : filter === "unsummarized" ? "미요약" : "요약"}</button>)}</div>
        {!currentStockId ? <p className="news-inbox-empty">관심종목을 선택하세요.</p> : null}{loading ? <p className="news-inbox-empty">공시를 불러오는 중입니다.</p> : null}{error ? <p className="news-inbox-empty error">{error}</p> : null}{!loading && !error && currentStockId && !visibleItems.length ? <p className="news-inbox-empty">조건에 맞는 공시가 없습니다.</p> : null}
        {!loading && !error && visibleItems.length ? <div className="news-inbox-table-shell"><table className="news-inbox-table"><thead><tr><th><input type="checkbox" aria-label="현재 목록 전체 선택" checked={allChecked} onChange={(e) => setCheckedIds(e.target.checked ? visibleItems.map((item) => item.id) : [])} /></th><th>일시</th><th>공시</th><th>원문</th><th>작업</th></tr></thead><tbody>
          {visibleItems.map((item) => { const date = formatShortDate(item.disclosed_at || item.created_at); const summary = parseSummary(item); return <tr key={item.id} tabIndex={0} onClick={() => { setSelected(item); setDrawerOpen(true); }} onKeyDown={(e) => { if (e.key === "Enter") { setSelected(item); setDrawerOpen(true); } }}><td onClick={(e) => e.stopPropagation()}><input type="checkbox" aria-label={`${item.disclosure_title} 선택`} checked={checkedIds.includes(item.id)} onChange={(e) => setCheckedIds((previous) => e.target.checked ? [...previous, item.id] : previous.filter((id) => id !== item.id))} /></td><td><strong>{date.date}</strong><small>{date.time}</small></td><td><strong className="news-inbox-title">{item.disclosure_title}</strong>{summary.summary ? <p className="news-inbox-summary">{summary.summary}</p> : <span className="news-inbox-unsummarized">미요약</span>}</td><td onClick={(e) => e.stopPropagation()}>{item.url ? <a className="news-inbox-link" href={item.url} target="_blank" rel="noreferrer">공시 열기 <ExternalLink size={13} /></a> : <span className="cell-muted">URL 없음</span>}</td><td onClick={(e) => e.stopPropagation()}><button type="button" className="news-row-delete" aria-label={`${item.disclosure_title} 삭제`} onClick={() => void deleteItems([item.id])}><Trash2 size={15} /></button></td></tr>; })}
        </tbody></table></div> : null}<div className="disclosure-inbox-count">전체 {visibleItems.length}건</div>
      </SectionCard></main>
    </div>
    {drawerOpen && selected ? <div className="news-detail-overlay" onClick={() => setDrawerOpen(false)}><aside className="news-detail-drawer" role="dialog" aria-modal="true" aria-label="공시 상세" onClick={(e) => e.stopPropagation()}><header><div><span>DISCLOSURE DETAIL</span><h3>공시 상세</h3></div><button type="button" aria-label="닫기" onClick={() => setDrawerOpen(false)}><X size={19} /></button></header><div className="news-detail-content"><div className="news-detail-meta"><span>{selected.stock_name ?? "관심종목"}</span><span>공시 {formatDate(selected.disclosed_at)}</span>{selected.dart_receipt_no ? <span>접수번호 {selected.dart_receipt_no}</span> : null}</div><h4>{selected.disclosure_title}</h4><section className={`news-detail-summary ${selectedSummary?.summary ? "" : "empty"}`}><div><span>공시 요약</span><b>{selectedSummary?.summary ? "요약 완료" : "미요약"}</b></div>{selectedSummary?.summary ? <p>{selectedSummary.summary}</p> : <><p>아직 요약하지 않은 공시입니다. 원문을 확인한 뒤 필요할 때만 요약하세요.</p><button type="button" className="btn btn-primary" disabled={summarizeLoading} onClick={() => void summarize([selected.id])}><Sparkles size={15} />이 공시 요약</button></>}</section>{selectedSummary?.keywords.length ? <div className="disclosure-detail-keywords"><strong>관련 키워드</strong><div className="news-keyword-chip-list">{selectedSummary.keywords.map((keyword) => <span key={keyword} className="news-keyword-chip">{keyword}</span>)}</div></div> : null}{selected.url ? <a className="btn btn-secondary news-detail-source-link" href={selected.url} target="_blank" rel="noreferrer">DART 원문 열기 <ExternalLink size={15} /></a> : <p className="news-detail-no-url">원문 링크가 없습니다.</p>}</div><footer><button type="button" className="btn btn-secondary danger" onClick={() => void deleteItems([selected.id])}><Trash2 size={15} />삭제</button></footer></aside></div> : null}
  </div>;
}
export default DisclosuresPage;
