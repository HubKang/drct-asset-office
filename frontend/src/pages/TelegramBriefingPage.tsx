import { FormEvent, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, ExternalLink, LoaderCircle, Search, Sparkles, Trash2, X } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { TelegramItem, TelegramSource } from "@/types/telegram";

const PAGE_SIZE = 20;

function kstDate(offsetDays = 0) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date(Date.now() + offsetDays * 86_400_000));
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function TelegramBriefingPage() {
  const today = useMemo(() => kstDate(), []);
  const [tab, setTab] = useState<"inbox" | "sources">("inbox");
  const [sources, setSources] = useState<TelegramSource[]>([]);
  const [items, setItems] = useState<TelegramItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [detail, setDetail] = useState<TelegramItem | null>(null);
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [keyword, setKeyword] = useState("");
  const [targetDate, setTargetDate] = useState(today);
  const [sourceId, setSourceId] = useState("0");
  const [busy, setBusy] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [notice, setNotice] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [channel, setChannel] = useState("");

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const activeSources = useMemo(() => sources.filter((source) => source.is_active === 1), [sources]);
  const pageNumbers = useMemo(() => {
    const values = new Set([1, totalPages, page - 1, page, page + 1]);
    return [...values].filter((value) => value >= 1 && value <= totalPages).sort((a, b) => a - b);
  }, [page, totalPages]);

  async function loadSources() { setSources(await repositories.telegram.listSources(false)); }

  async function loadItems(nextPage = page) {
    const result = await repositories.telegram.listItems({
      date_from: dateFrom, date_to: dateTo, keyword: keyword || undefined,
      limit: PAGE_SIZE, offset: (nextPage - 1) * PAGE_SIZE,
    });
    setItems(result.items); setTotal(result.total_count); setSelected([]);
    setDetail((current) => current ? result.items.find((item) => item.id === current.id) ?? current : null);
  }

  useEffect(() => { void Promise.all([loadSources(), loadItems(1)]); }, []);

  async function collect() {
    setBusy(true); setNotice("");
    try {
      const options = { target_date: targetDate };
      const result = sourceId === "0"
        ? await repositories.telegram.collectAllByDate(options)
        : await repositories.telegram.collectByDate({ ...options, source_id: Number(sourceId) });
      setNotice(`수집 완료 · 신규 ${result.inserted} · 중복 ${result.duplicate_skipped} · 삭제 제외 ${result.excluded_skipped} · 처리 실패 ${result.processing_failed}`);
      setDateFrom(targetDate); setDateTo(targetDate); setPage(1);
      const next = await repositories.telegram.listItems({ date_from: targetDate, date_to: targetDate, limit: PAGE_SIZE, offset: 0 });
      setItems(next.items); setTotal(next.total_count); setSelected([]); await loadSources();
    } catch (error) { setNotice(error instanceof Error ? error.message : "수집에 실패했습니다."); }
    finally { setBusy(false); }
  }

  async function search(event?: FormEvent) {
    event?.preventDefault(); setBusy(true); setPage(1);
    try { await loadItems(1); } finally { setBusy(false); }
  }

  async function summarizeItems(ids: number[]) {
    if (!ids.length) return;
    setSummarizing(true); setNotice("");
    try {
      const result = await repositories.telegram.summarizeItems(ids);
      setNotice(`요약 완료 ${result.summarized} · 기존 요약 ${result.skipped_existing} · URL 없음 ${result.missing_url} · 본문 조회 실패 ${result.fetch_failed} · 처리 실패 ${result.processing_failed}`);
      await loadItems(page);
    } catch (error) { setNotice(error instanceof Error ? error.message : "기사 요약에 실패했습니다."); }
    finally { setSummarizing(false); }
  }

  async function removeItems(ids: number[], closeDrawer = false) {
    if (!ids.length) return;
    if (!window.confirm(`선택한 ${ids.length}건을 삭제하시겠습니까?\n\n오늘 같은 수집일에 다시 수집해도 해당 메시지는 재등록되지 않습니다.`)) return;
    setBusy(true);
    try {
      const result = await repositories.telegram.deleteItems(ids);
      setNotice(`${result.deleted_count}건을 삭제했습니다.`); if (closeDrawer) setDetail(null);
      await loadItems(page);
    } finally { setBusy(false); }
  }

  async function addSource(event: FormEvent) {
    event.preventDefault();
    await repositories.telegram.createSource({ source_name: sourceName, channel_username: channel, is_active: true });
    setSourceName(""); setChannel(""); await loadSources();
  }

  async function changePage(next: number) {
    setPage(next); setBusy(true);
    try { await loadItems(next); } finally { setBusy(false); }
  }

  const allSelected = items.length > 0 && items.every((item) => selected.includes(item.id));

  return <div className="telegram-briefing-page">
    <PageHeader title="텔레그램 브리핑" description="필요한 기사만 선별해 원문 기준 요약으로 보관합니다." />

    <section className="telegram-toolbar-surface">
      <div className="telegram-tabs" role="tablist" aria-label="텔레그램 브리핑 메뉴">
        <button role="tab" aria-selected={tab === "inbox"} className={tab === "inbox" ? "is-active" : ""} onClick={() => setTab("inbox")}>브리핑 Inbox</button>
        <button role="tab" aria-selected={tab === "sources"} className={tab === "sources" ? "is-active" : ""} onClick={() => setTab("sources")}>채널 관리</button>
      </div>
    </section>

    {tab === "inbox" ? <>
      <div className="telegram-operations-grid">
        <section className="telegram-collection-surface">
          <div className="telegram-collect-bar compact">
            <label><span>수집일</span><input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} /></label>
            <label className="telegram-channel-field"><span>수집 채널</span><select value={sourceId} onChange={(e) => setSourceId(e.target.value)}><option value="0">활성 채널 전체</option>{activeSources.map((source) => <option key={source.id} value={source.id}>{source.source_name}</option>)}</select></label>
            <button className="telegram-primary-action" disabled={busy || !activeSources.length} onClick={() => void collect()}>{busy ? <><LoaderCircle size={17} className="animate-spin" />수집 중...</> : "수집 실행"}</button>
          </div>
        </section>
        <section className="telegram-search-surface">
          <form className="telegram-search-bar compact" onSubmit={(event) => void search(event)}>
            <label><span>시작일</span><input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></label>
            <label><span>종료일</span><input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></label>
            <label className="telegram-keyword-field"><span>검색어</span><div><Search size={17} aria-hidden="true" /><input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="제목·요약·기사 URL 검색" /></div></label>
            <button className="telegram-search-action" disabled={busy}>조회</button>
          </form>
        </section>
      </div>
      {notice ? <div className="telegram-result-strip standalone" role="status">{notice}</div> : null}

      <section className="telegram-list-surface">
        <div className="telegram-list-section">
          <div className="telegram-list-heading"><div><h3>브리핑 목록</h3><p>총 {total}건 · {page}/{totalPages} 페이지 · 선택 {selected.length}건</p></div><div className="telegram-list-actions"><button className="telegram-summary-action" disabled={!selected.length || summarizing} onClick={() => void summarizeItems(selected)}>{summarizing ? <LoaderCircle size={16} className="animate-spin" /> : <Sparkles size={16} />}선택 요약{selected.length ? ` ${selected.length}` : ""}</button><button className="telegram-delete-action" disabled={!selected.length || busy} onClick={() => void removeItems(selected)}><Trash2 size={16} />선택 삭제{selected.length ? ` ${selected.length}` : ""}</button></div></div>
          <div className="telegram-inbox-list">
            <div className="telegram-list-columns"><input type="checkbox" checked={allSelected} onChange={(e) => setSelected(e.target.checked ? items.map((item) => item.id) : [])} aria-label="현재 페이지 전체 선택" /><span>일시</span><span>브리핑</span><span>기사</span><span>작업</span></div>
            {items.map((item) => {
              const date = item.message_at.replace("T", " ");
              return <article key={item.id} className="telegram-inbox-row">
                <input type="checkbox" checked={selected.includes(item.id)} onChange={(e) => setSelected((current) => e.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))} aria-label={`${item.title} 선택`} />
                <time dateTime={item.message_at}><b>{date.slice(5, 10).replace("-", ".")}</b><span>{date.slice(11, 16)}</span></time>
                <button className="telegram-briefing-content" onClick={() => setDetail(item)}><strong>{item.title}</strong>{item.summary ? <span>{item.summary}</span> : null}</button>
                <div className="telegram-article-cell">{item.source_url ? <a href={item.source_url} target="_blank" rel="noreferrer">기사 열기 <ExternalLink size={14} /></a> : <span>URL 없음</span>}</div>
                <button className="telegram-row-delete" aria-label={`${item.title} 삭제`} onClick={() => void removeItems([item.id])}><Trash2 size={16} /></button>
              </article>;
            })}
            {!items.length ? <div className="telegram-empty">조회된 브리핑이 없습니다.</div> : null}
          </div>
          <nav className="telegram-pagination" aria-label="브리핑 페이지"><button disabled={page <= 1} onClick={() => void changePage(page - 1)}><ChevronLeft size={16} />이전</button>{pageNumbers.map((value, index) => <span key={value}>{index > 0 && value - pageNumbers[index - 1] > 1 ? <i>…</i> : null}<button aria-current={value === page ? "page" : undefined} onClick={() => void changePage(value)}>{value}</button></span>)}<button disabled={page >= totalPages} onClick={() => void changePage(page + 1)}>다음<ChevronRight size={16} /></button></nav>
        </div>
      </section>
    </> : <SectionCard title="수집 채널 관리" className="telegram-source-card">
      <form className="telegram-source-form" onSubmit={addSource}><label><span>채널 표시명</span><input required value={sourceName} onChange={(e) => setSourceName(e.target.value)} placeholder="예: 시장 뉴스" /></label><label><span>Telegram 채널</span><input required value={channel} onChange={(e) => setChannel(e.target.value)} placeholder="@username 또는 t.me 링크" /></label><button className="btn btn-primary">채널 추가</button></form>
      <div className="telegram-source-list">{sources.map((source) => <div key={source.id}><div><strong>{source.source_name}</strong><p>{source.channel_username} · 최근 수집 {source.last_collected_at || "-"}</p></div><div><button className="btn btn-secondary" onClick={async () => { await repositories.telegram.updateSource(source.id, { is_active: source.is_active !== 1 }); await loadSources(); }}>{source.is_active === 1 ? "일시정지" : "활성화"}</button><button className="btn btn-danger" onClick={async () => { if (window.confirm("채널 설정을 삭제할까요?")) { await repositories.telegram.deleteSource(source.id); await loadSources(); } }}>삭제</button></div></div>)}</div>
    </SectionCard>}

    {detail ? <div className="telegram-drawer-backdrop" onClick={() => setDetail(null)}><aside className="telegram-detail-drawer" role="dialog" aria-modal="true" aria-labelledby="telegram-detail-title" onClick={(event) => event.stopPropagation()}><header><h3 id="telegram-detail-title">브리핑 상세</h3><button aria-label="상세 닫기" onClick={() => setDetail(null)}><X size={20} /></button></header><div className="telegram-drawer-body"><time>{detail.message_at.replace("T", " ")}</time><h4>{detail.title}</h4>{detail.summary ? <section><h5>요약</h5><p>{detail.summary}</p></section> : <section className="telegram-unsummarized"><p>{detail.source_url ? "아직 요약하지 않은 기사입니다." : "기사 URL이 없어 요약할 수 없습니다."}</p><button disabled={!detail.source_url || summarizing} onClick={() => void summarizeItems([detail.id])}>{summarizing ? <LoaderCircle size={16} className="animate-spin" /> : <Sparkles size={16} />}이 기사 요약</button></section>}{detail.source_url ? <section className="telegram-original-article"><h5>원문 기사</h5><a href={detail.source_url} target="_blank" rel="noreferrer">원문 기사 열기 <ExternalLink size={15} /></a></section> : null}</div><footer><button onClick={() => void removeItems([detail.id], true)}><Trash2 size={16} />삭제</button></footer></aside></div> : null}
  </div>;
}

export default TelegramBriefingPage;
