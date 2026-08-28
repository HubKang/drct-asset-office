import { useEffect, useRef, useState } from "react";
import { ChevronDown, DatabaseZap, Loader2, Plus, RefreshCw, Trash2, X } from "lucide-react";
import EmptyState from "@/components/common/EmptyState";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { UsStockCharts } from "@/types/usMarketTheme";
import type { UsExchange, UsHistoricalCollectionMode, UsHistoricalPriceStatus, UsPriceCollectionResponse, UsStock, UsStockDeleteImpact, UsStockDeleteResponse, UsStockInput, UsStockSummary, UsStockType } from "@/types/usStock";

const EXCHANGES: Array<{ value: UsExchange; label: string }> = [
  { value: "NASDAQ", label: "NASDAQ" }, { value: "NYSE", label: "NYSE" },
  { value: "NYSE_AMERICAN", label: "NYSE American" }, { value: "OTHER", label: "기타" },
];
const TYPES: Array<{ value: UsStockType; label: string }> = [
  { value: "COMMON", label: "보통주" }, { value: "ETF", label: "ETF" }, { value: "OTHER", label: "기타" },
];
const EMPTY_SUMMARY: UsStockSummary = { total: 0, active: 0, common: 0, etf: 0, price_complete: 0, price_not_collected: 0, price_partial: 0, price_error: 0, latest_price_date: null };
const EMPTY_FORM: UsStockInput = { symbol: "", name: "", name_ko: "", exchange: "NASDAQ", stock_type: "COMMON", naver_code: "", is_active: 1 };
type UsStockStatusFilter = "" | "ACTIVE" | "INACTIVE" | UsHistoricalPriceStatus;
const usStockChartCache = new Map<number, Promise<UsStockCharts>>();

function exchangeLabel(value: string) { return EXCHANGES.find((item) => item.value === value)?.label ?? value; }
function formatPriceDate(value: string | null) { return value ? value.slice(5).replace("-", ".") : "-"; }

function UsStockChartCells({ stock, onOpen }: { stock: UsStock; onOpen: (chart: { url: string; title: string }) => void }) {
  const rootRef = useRef<HTMLTableCellElement | null>(null);
  const [charts, setCharts] = useState<UsStockCharts | null>(null);
  const [requested, setRequested] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    setCharts(null); setRequested(false); setRetryCount(0);
    const element = rootRef.current;
    if (!element || !stock.naver_code) return;
    const request = () => setRequested(true);
    if (typeof IntersectionObserver === "undefined") { request(); return; }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) { request(); observer.disconnect(); }
    }, { rootMargin: "160px" });
    observer.observe(element);
    return () => observer.disconnect();
  }, [stock.id, stock.naver_code]);

  useEffect(() => {
    if (!requested) return;
    let active = true;
    let retryTimer: number | undefined;
    let promise = usStockChartCache.get(stock.id);
    if (!promise) {
      promise = repositories.usMarketThemes.charts(stock.id);
      usStockChartCache.set(stock.id, promise);
    }
    promise.then((value) => {
      if (!value.available) usStockChartCache.delete(stock.id);
      if (active) setCharts(value);
      if (active && !value.available && retryCount < 1) retryTimer = window.setTimeout(() => setRetryCount((count) => count + 1), 2500);
    }).catch(() => {
      usStockChartCache.delete(stock.id);
      if (active) setCharts({ stock_id: stock.id, naver_code: stock.naver_code, day: null, week: null, month: null, available: false });
      if (active && retryCount < 1) retryTimer = window.setTimeout(() => setRetryCount((count) => count + 1), 2500);
    });
    return () => { active = false; if (retryTimer !== undefined) window.clearTimeout(retryTimer); };
  }, [requested, retryCount, stock.id, stock.naver_code]);

  return <>
    {(["day", "week", "month"] as const).map((period) => {
      const label = period === "day" ? "일봉" : period === "week" ? "주봉" : "월봉";
      const url = charts?.[period];
      return <td key={period} ref={period === "day" ? rootRef : undefined} className="us-stock-chart-cell">{url ? <button type="button" className="theme-linked-stock-chart-button" onClick={() => onOpen({ url, title: `${stock.symbol} ${label}` })}><img className="theme-linked-stock-chart" src={url} alt={`${stock.symbol} ${label}`} loading="lazy" decoding="async" /></button>
        : <div className="theme-linked-stock-chart-fallback">{!stock.naver_code ? "차트없음" : !requested ? "차트 준비" : !charts ? "조회 중" : "조회불가"}</div>}</td>;
    })}
  </>;
}

function UsStockModal({ editing, onClose, onSaved, onDeleted }: { editing: UsStock | null; onClose: () => void; onSaved: (createdIds: number[]) => Promise<void>; onDeleted?: (result: UsStockDeleteResponse) => Promise<void> }) {
  const [form, setForm] = useState<UsStockInput>(() => editing ? { symbol: editing.symbol, name: editing.name, name_ko: editing.name_ko, exchange: editing.exchange, stock_type: editing.stock_type, naver_code: editing.naver_code, is_active: editing.is_active } : EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [deleteImpact, setDeleteImpact] = useState<UsStockDeleteImpact | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const update = <K extends keyof UsStockInput>(key: K, value: UsStockInput[K]) => setForm((prev) => ({ ...prev, [key]: value }));
  const save = async () => {
    setSaving(true); setError("");
    try {
      let createdIds: number[] = [];
      if (editing) {
        const { symbol: _symbol, ...payload } = form;
        await repositories.usStocks.update(editing.id, payload);
      } else {
        const created = await repositories.usStocks.create({ ...form, symbol: form.symbol.trim().toUpperCase() });
        createdIds = [created.id];
      }
      await onSaved(createdIds); onClose();
    } catch (e) { setError(e instanceof Error ? e.message : "저장하지 못했습니다."); }
    finally { setSaving(false); }
  };
  const prepareDelete = async () => {
    if (!editing) return;
    setSaving(true); setError("");
    try { setDeleteImpact(await repositories.usStocks.deleteImpact(editing.id)); }
    catch (e) { setError(e instanceof Error ? e.message : "삭제 영향을 확인하지 못했습니다."); }
    finally { setSaving(false); }
  };
  const remove = async () => {
    if (!editing || !deleteImpact || !onDeleted) return;
    setSaving(true); setError("");
    try { const result = await repositories.usStocks.delete(editing.id, deleteConfirm); await onDeleted(result); onClose(); }
    catch (e) { setError(e instanceof Error ? e.message : "종목을 삭제하지 못했습니다."); }
    finally { setSaving(false); }
  };
  return <div className="us-stock-modal-backdrop" role="presentation" onMouseDown={onClose}>
    <div className="us-stock-modal" role="dialog" aria-modal="true" aria-labelledby="us-stock-modal-title" onMouseDown={(e) => e.stopPropagation()}>
      <div className="us-stock-modal-head"><div><h3 id="us-stock-modal-title">{editing ? "미국 종목 수정" : "미국 종목 등록"}</h3><p>Ticker는 등록 후 변경할 수 없습니다.</p></div><button type="button" className="icon-button" onClick={onClose} aria-label="닫기"><X size={18} /></button></div>
      <div className="us-stock-form-grid">
        <label><span>Ticker *</span><input className="input-control" value={form.symbol} disabled={Boolean(editing)} onChange={(e) => update("symbol", e.target.value.toUpperCase())} placeholder="NVDA" /></label>
        <label><span>거래소 *</span><select className="select-control" value={form.exchange} onChange={(e) => update("exchange", e.target.value as UsExchange)}>{EXCHANGES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <label className="us-stock-form-wide"><span>종목명</span><input className="input-control" value={form.name ?? ""} onChange={(e) => update("name", e.target.value)} placeholder="NVIDIA Corporation" /></label>
        <label><span>한글명</span><input className="input-control" value={form.name_ko ?? ""} onChange={(e) => update("name_ko", e.target.value)} placeholder="엔비디아" /></label>
        <label><span>종목유형 *</span><select className="select-control" value={form.stock_type} onChange={(e) => update("stock_type", e.target.value as UsStockType)}>{TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        <label><span>Naver Code</span><input className="input-control" value={form.naver_code ?? ""} onChange={(e) => update("naver_code", e.target.value)} placeholder="검증된 코드만 입력" /></label>
        <label><span>상태</span><select className="select-control" value={form.is_active} onChange={(e) => update("is_active", Number(e.target.value))}><option value={1}>활성</option><option value={0}>비활성</option></select></label>
      </div>
      {deleteImpact ? <div className="us-stock-delete-confirm">
        <strong><Trash2 size={16} /> {deleteImpact.symbol} 물리 삭제</strong>
        <p>되돌릴 수 없습니다. 과거가격 <b>{deleteImpact.price_row_count.toLocaleString()}건</b>, 테마 연결 <b>{deleteImpact.theme_link_count.toLocaleString()}건</b>이 함께 삭제되고 영향받는 테마 {deleteImpact.affected_theme_count.toLocaleString()}개의 등락률이 재계산됩니다.</p>
        <label><span>확인을 위해 <b>{deleteImpact.symbol}</b> 입력</span><input className="input-control" value={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.value.toUpperCase())} autoFocus /></label>
      </div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}
      <div className={`us-stock-modal-actions ${editing ? "has-delete" : ""}`}>
        {editing && !deleteImpact ? <button type="button" className="btn btn-danger us-stock-delete-button" disabled={saving} onClick={() => void prepareDelete()}><Trash2 size={14} /> 물리 삭제</button> : null}
        {deleteImpact ? <><button type="button" className="btn btn-secondary" disabled={saving} onClick={() => { setDeleteImpact(null); setDeleteConfirm(""); }}>삭제 취소</button><button type="button" className="btn btn-danger" disabled={saving || deleteConfirm !== deleteImpact.symbol} onClick={() => void remove()}>{saving ? "삭제 중..." : "영구 삭제"}</button></> : <><button type="button" className="btn btn-secondary" onClick={onClose}>취소</button><button type="button" className="btn btn-primary" disabled={saving || !form.symbol.trim()} onClick={() => void save()}>{saving ? "저장 중..." : "저장"}</button></>}
      </div>
    </div>
  </div>;
}

export default function UsStocksPanel({ onCountChange }: { onCountChange: (count: number) => void }) {
  const [items, setItems] = useState<UsStock[]>([]); const [summary, setSummary] = useState(EMPTY_SUMMARY); const [page, setPage] = useState(1); const [total, setTotal] = useState(0); const pageSize = 20;
  const [keyword, setKeyword] = useState(""); const [draftKeyword, setDraftKeyword] = useState(""); const [exchange, setExchange] = useState(""); const [stockType, setStockType] = useState(""); const [statusFilter, setStatusFilter] = useState<UsStockStatusFilter>("");
  const [loading, setLoading] = useState(false); const [error, setError] = useState(""); const [editing, setEditing] = useState<UsStock | null>(null); const [showCreate, setShowCreate] = useState(false);
  const [deleteMessage, setDeleteMessage] = useState("");
  const [zoomedChart, setZoomedChart] = useState<{ url: string; title: string } | null>(null);
  const [collecting, setCollecting] = useState(false); const [collectionResult, setCollectionResult] = useState<UsPriceCollectionResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set()); const [historicalMode, setHistoricalMode] = useState<UsHistoricalCollectionMode>("MISSING"); const [showCollectionMenu, setShowCollectionMenu] = useState(false);
  const load = async (targetPage = page) => { setLoading(true); setError(""); try { const [list, nextSummary] = await Promise.all([repositories.usStocks.list({ keyword, exchange, stock_type: stockType, is_active: statusFilter === "ACTIVE" || ["NOT_COLLECTED", "COMPLETE", "PARTIAL", "ERROR"].includes(statusFilter) ? 1 : statusFilter === "INACTIVE" ? 0 : undefined, price_status: ["NOT_COLLECTED", "COMPLETE", "PARTIAL", "ERROR"].includes(statusFilter) ? statusFilter : undefined, page: targetPage, page_size: pageSize }), repositories.usStocks.summary()]); setItems(list.items); setTotal(list.total); setSummary(nextSummary); onCountChange(nextSummary.active); } catch (e) { setError(e instanceof Error ? e.message : "미국 종목을 불러오지 못했습니다."); } finally { setLoading(false); } };
  useEffect(() => { void load(page); }, [page, keyword, exchange, stockType, statusFilter]);
  const collectPrices = async (mode: "INCREMENTAL" | UsHistoricalCollectionMode, stockIds?: number[], requireConfirm = true) => {
    if (mode === "SELECTED" && !stockIds?.length) { setError("과거가격을 수집할 종목을 선택해 주세요."); return false; }
    const prompt = mode === "INCREMENTAL" ? stockIds?.length ? `선택한 ${stockIds.length}개 종목의 최신 종가를 수집할까요? 과거가격이 없는 종목은 등락률 계산을 위해 최근 2거래일을 수집합니다.` : "과거가격을 보유한 활성 미국 종목 전체의 최신 종가를 수집할까요?" : mode === "ALL_ACTIVE" ? "모든 활성 미국 종목의 최근 260거래일 과거가격을 수집할까요? 기존 가격은 안전하게 갱신됩니다." : mode === "SELECTED" ? `선택한 ${stockIds?.length ?? 0}개 종목의 최근 260거래일 과거가격을 수집할까요?` : "과거가격이 없는 활성 미국 종목만 최근 260거래일 가격을 수집할까요?";
    if (requireConfirm && !window.confirm(prompt)) return false;
    setCollecting(true); setCollectionResult(null); setError("");
    try { const result = await repositories.usStocks.collectPrices(mode, stockIds); setCollectionResult(result); await load(page); return true; }
    catch (e) { setError(e instanceof Error ? e.message : "미국 종가 수집에 실패했습니다."); }
    finally { setCollecting(false); }
    return false;
  };
  const runHistoricalCollection = async () => {
    const ids = historicalMode === "SELECTED" ? Array.from(selectedIds) : undefined;
    const completed = await collectPrices(historicalMode, ids);
    if (completed) { setShowCollectionMenu(false); setSelectedIds(new Set()); }
  };
  const runLatestCollection = async () => {
    const ids = selectedIds.size ? Array.from(selectedIds) : undefined;
    const completed = await collectPrices("INCREMENTAL", ids);
    if (completed && ids) setSelectedIds(new Set());
  };
  const afterSaved = async (createdIds: number[]) => {
    await load(page);
    if (createdIds.length && window.confirm(`신규 등록한 ${createdIds.length}개 종목의 260거래일 과거가격을 지금 수집할까요?`)) {
      await collectPrices("SELECTED", createdIds, false);
    }
  };
  const afterDeleted = async (result: UsStockDeleteResponse) => {
    setSelectedIds((current) => { const next = new Set(current); next.delete(result.stock_id); return next; });
    setDeleteMessage(`${result.message} 가격 ${result.deleted_price_count.toLocaleString()}건 · 테마 연결 ${result.deleted_theme_link_count.toLocaleString()}건 정리`);
    const targetPage = items.length === 1 && page > 1 ? page - 1 : page;
    if (targetPage !== page) setPage(targetPage); else await load(targetPage);
  };
  const toggleSelected = (stockId: number) => setSelectedIds((current) => { const next = new Set(current); if (next.has(stockId)) next.delete(stockId); else next.add(stockId); return next; });
  const selectablePageIds = items.filter((item) => item.is_active).map((item) => item.id);
  const pageSelected = selectablePageIds.length > 0 && selectablePageIds.every((id) => selectedIds.has(id));
  const togglePage = () => setSelectedIds((current) => { const next = new Set(current); selectablePageIds.forEach((id) => pageSelected ? next.delete(id) : next.add(id)); return next; });
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const reset = () => { setDraftKeyword(""); setKeyword(""); setExchange(""); setStockType(""); setStatusFilter(""); setPage(1); };
  const selectSummaryFilter = (nextStatus: "ACTIVE" | UsHistoricalPriceStatus) => {
    setPage(1);
    setStatusFilter((current) => current === nextStatus ? "" : nextStatus);
  };
  const summaryFilters = [
    { key: "ACTIVE" as const, label: "활성", count: summary.active, tone: "blue", title: "현재 활성 상태인 미국 종목" },
    { key: "COMPLETE" as const, label: "정상", count: summary.price_complete, tone: "green", title: "과거가격 수집이 정상 완료된 종목" },
    { key: "NOT_COLLECTED" as const, label: "미수집", count: summary.price_not_collected, tone: "slate", title: "과거가격 데이터가 없는 종목" },
    { key: "PARTIAL" as const, label: "부분수집", count: summary.price_partial, tone: "amber", title: "일부 가격은 있으나 수집이 정상 완료되지 않은 종목" },
    { key: "ERROR" as const, label: "오류", count: summary.price_error, tone: "rose", title: "최근 과거가격 수집이 실패한 종목" },
  ];
  return <>
    <SectionCard className="stock-work-card us-universe-card">
      <div className="us-universe-title-row"><h3 className="section-title">미국 종목 Universe 관리</h3></div>
      <div className="us-universe-command-row"><div className="us-stock-summary" aria-label="미국 종목 상태 필터">{summaryFilters.map((item) => { const selected = statusFilter === item.key; return <button key={item.key} type="button" className={`us-stock-summary-filter tone-${item.tone}${item.count === 0 ? " zero" : ""}${selected ? " selected" : ""}`} aria-pressed={selected} title={item.title} onClick={() => selectSummaryFilter(item.key)}><span>{item.label}</span><strong>{item.count.toLocaleString()}</strong></button>; })}</div><div className="us-price-collection-actions">
        <span className="us-latest-price-date" title={summary.latest_price_date ? `최신 가격일 ${summary.latest_price_date}` : "최신 가격일 없음"}>최신 <strong>{formatPriceDate(summary.latest_price_date)}</strong></span>
        <div className="us-historical-menu"><button type="button" className="btn btn-secondary" disabled={collecting} onClick={() => setShowCollectionMenu((value) => !value)}><DatabaseZap size={14} /> 260일 과거가격 수집 <ChevronDown size={14} /></button>{showCollectionMenu ? <div className="us-historical-menu-panel"><strong>수집 범위</strong>{([{ value: "MISSING", label: "미수집 종목만", note: `${summary.price_not_collected}개 대상` }, { value: "SELECTED", label: "선택 종목", note: `${selectedIds.size}개 선택` }, { value: "ALL_ACTIVE", label: "모든 활성 종목", note: `${summary.active}개 대상` }] as const).map((option) => <label key={option.value}><input type="radio" name="historical-mode" checked={historicalMode === option.value} onChange={() => setHistoricalMode(option.value)} /><span><b>{option.label}</b><small>{option.note}</small></span></label>)}<button type="button" className="btn btn-primary" disabled={collecting || (historicalMode === "SELECTED" && selectedIds.size === 0)} onClick={() => void runHistoricalCollection()}>과거가격 수집 실행</button></div> : null}</div>
        <button type="button" className="btn btn-primary" disabled={collecting} onClick={() => void runLatestCollection()}><RefreshCw size={14} className={collecting ? "animate-spin" : ""} /> {collecting ? "수집 중..." : selectedIds.size ? `선택 ${selectedIds.size}개 최신 종가 수집` : "최신 종가 수집"}</button>
        <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}><Plus size={15} /> 신규 종목 등록</button>
      </div></div>
      {collectionResult ? <div className={`inline-result ${collectionResult.failed_stock_count ? "inline-warning" : "inline-success"}`}><strong>{collectionResult.message}</strong><span>요청 {collectionResult.requested_stock_count} · 성공 {collectionResult.success_stock_count} · 실패 {collectionResult.failed_stock_count} · 추가 {collectionResult.inserted_count.toLocaleString()} · 갱신 {collectionResult.updated_count.toLocaleString()} · 동일 {collectionResult.unchanged_count.toLocaleString()} · 경계 정규화 {collectionResult.normalized_open_boundary_count.toLocaleString()} · 재계산 테마 {collectionResult.recalculated_theme_count}</span>{collectionResult.failures.length ? <small>{collectionResult.failures.slice(0, 5).map((item) => `${item.symbol}: ${item.reason}`).join(" / ")}</small> : null}</div> : null}
    </SectionCard>
    <SectionCard className="us-stock-search-card"><form className="stock-search-row us-stock-search-row" onSubmit={(e) => { e.preventDefault(); setPage(1); setKeyword(draftKeyword.trim()); }}><select className="select-control" value={exchange} onChange={(e) => { setPage(1); setExchange(e.target.value); }}><option value="">전체 거래소</option>{EXCHANGES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><select className="select-control" value={stockType} onChange={(e) => { setPage(1); setStockType(e.target.value); }}><option value="">전체 유형</option>{TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><select className="select-control" value={statusFilter} onChange={(e) => { setPage(1); setStatusFilter(e.target.value as UsStockStatusFilter); }}><option value="">전체 상태</option><option value="ACTIVE">활성</option><option value="INACTIVE">비활성</option><option value="COMPLETE">정상</option><option value="NOT_COLLECTED">미수집</option><option value="PARTIAL">부분수집</option><option value="ERROR">오류</option></select><input className="input-control" value={draftKeyword} onChange={(e) => setDraftKeyword(e.target.value)} placeholder="Ticker 또는 종목명" /><button className="btn btn-primary stock-search-btn" type="submit">검색</button><button className="btn btn-secondary stock-search-btn" type="button" onClick={reset}>초기화</button></form></SectionCard>
    <SectionCard title="미국 종목 목록">
      {deleteMessage ? <div className="inline-result inline-success">{deleteMessage}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}
      {loading ? <div className="us-stock-loading"><Loader2 size={18} className="animate-spin" /> 불러오는 중...</div> : items.length === 0 ? <EmptyState message="등록된 미국 종목이 없습니다." /> : <>
        <div className="table-shell us-stock-table-shell"><table className="data-table compact-table us-stock-table">
          <colgroup><col className="us-stock-col-ticker"/><col className="us-stock-col-name"/><col className="us-stock-col-exchange"/><col className="us-stock-col-price"/><col className="us-stock-col-change"/><col className="us-stock-col-chart"/><col className="us-stock-col-chart"/><col className="us-stock-col-chart"/><col className="us-stock-col-action"/></colgroup>
          <thead><tr><th>Ticker</th><th>종목명</th><th>거래소</th><th>최근 종가</th><th>등락률</th><th>일봉</th><th>주봉</th><th>월봉</th><th><span className="us-stock-action-heading">작업<input type="checkbox" aria-label="현재 페이지 활성 종목 전체 선택" title="현재 페이지 전체 선택" checked={pageSelected} onChange={togglePage}/></span></th></tr></thead>
          <tbody>{items.map((item) => <tr key={item.id}>
            <td><strong>{item.symbol}</strong></td>
            <td title={item.name ?? undefined}>{item.name_ko || item.name || "-"}</td>
            <td>{exchangeLabel(item.exchange)}</td>
            <td className="numeric-cell">{item.latest_close == null ? "-" : `$${item.latest_close.toLocaleString(undefined, { maximumFractionDigits: 4 })}`}</td>
            <td className={`numeric-cell ${item.latest_change_rate == null ? "" : item.latest_change_rate >= 0 ? "value-up" : "value-down"}`}>{item.latest_change_rate == null ? "-" : `${item.latest_change_rate >= 0 ? "+" : ""}${item.latest_change_rate.toFixed(2)}%`}</td>
            <UsStockChartCells stock={item} onOpen={setZoomedChart}/>
            <td><div className="us-stock-row-actions"><input className="us-stock-row-select" type="checkbox" aria-label={`${item.symbol} 가격 수집 대상으로 선택`} title="가격 수집 대상으로 선택" disabled={!item.is_active} checked={selectedIds.has(item.id)} onChange={() => toggleSelected(item.id)}/><button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setEditing(item)}>수정</button>{item.is_active && item.price_status !== "COMPLETE" ? <button type="button" className="btn btn-secondary btn-table-sm" disabled={collecting} onClick={() => void collectPrices("SELECTED", [item.id])}>과거가격 수집</button> : null}</div></td>
          </tr>)}</tbody>
        </table></div>
        <div className="pagination-bar"><div className="pagination-info">전체 {total.toLocaleString()}건 · {page} / {totalPages} 페이지 · 선택 {selectedIds.size}건</div><div className="pagination-actions"><button className="btn btn-secondary" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1}>이전</button><button className="btn btn-secondary" onClick={() => setPage((value) => Math.min(totalPages, value + 1))} disabled={page >= totalPages}>다음</button></div></div>
      </>}
    </SectionCard>
    {showCreate ? <UsStockModal editing={null} onClose={() => setShowCreate(false)} onSaved={afterSaved} /> : null}{editing ? <UsStockModal editing={editing} onClose={() => setEditing(null)} onSaved={afterSaved} onDeleted={afterDeleted} /> : null}
    {zoomedChart ? <div className="theme-linked-stock-chart-modal" onClick={() => setZoomedChart(null)}><div className="theme-linked-stock-chart-modal-panel" onClick={(event) => event.stopPropagation()}><div className="theme-linked-stock-chart-modal-header"><h3>{zoomedChart.title}</h3><button className="btn btn-secondary btn-table-sm" onClick={() => setZoomedChart(null)}>닫기</button></div><img src={zoomedChart.url} alt={zoomedChart.title} className="theme-linked-stock-chart-modal-image" /></div></div> : null}
  </>;
}
