import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { MarketCalendarEvent, MarketCalendarEventInput, MarketCalendarEventType, MarketCalendarImportance } from "@/types/marketCalendar";
import type { MarketTheme } from "@/types/marketTheme";
import type { Stock } from "@/types/stock";

const EVENT_TYPE_LABELS: Record<MarketCalendarEventType, string> = {
  news: "뉴스",
  policy: "정책",
  issue: "이슈",
  earnings: "실적",
  disclosure: "공시",
  supply: "수급",
  other: "기타",
};

const IMPORTANCE_LABELS: Record<MarketCalendarImportance, string> = {
  high: "높음",
  medium: "보통",
  low: "낮음",
};

const THEME_COLORS = ["#16a34a", "#db2777", "#2563eb", "#f97316", "#7c3aed", "#0891b2", "#dc2626", "#65a30d", "#9333ea", "#0f766e", "#ca8a04", "#4f46e5", "#be123c", "#15803d", "#0369a1", "#a21caf"];

const emptyForm = (dateValue: string): MarketCalendarEventInput => ({
  start_date: dateValue,
  end_date: dateValue,
  theme_id: 0,
  title: "",
  summary: "",
  news_url: "",
  event_type: "news",
  importance: "medium",
  memo: "",
  stock_ids: [],
});

function todayKst() {
  return new Date(Date.now() + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

function toMonth(value: Date) {
  return value.getFullYear() + "-" + String(value.getMonth() + 1).padStart(2, "0");
}

function shiftMonth(month: string, offset: number) {
  const [year, monthNumber] = month.split("-").map(Number);
  return toMonth(new Date(year, monthNumber - 1 + offset, 1));
}

function formatMonthLabel(month: string) {
  const [year, monthNumber] = month.split("-");
  return year + "년 " + Number(monthNumber) + "월";
}

function buildCalendarDays(month: string) {
  const [year, monthNumber] = month.split("-").map(Number);
  const first = new Date(year, monthNumber - 1, 1);
  const lastDate = new Date(year, monthNumber, 0).getDate();
  const days: Array<{ date: string; day: number; inMonth: boolean }> = [];
  for (let i = 0; i < first.getDay(); i += 1) {
    const date = new Date(year, monthNumber - 1, 1 - first.getDay() + i);
    days.push({ date: toMonth(date) + "-" + String(date.getDate()).padStart(2, "0"), day: date.getDate(), inMonth: false });
  }
  for (let day = 1; day <= lastDate; day += 1) {
    days.push({ date: month + "-" + String(day).padStart(2, "0"), day, inMonth: true });
  }
  while (days.length % 7 !== 0) {
    const date = new Date(year, monthNumber - 1, lastDate + (days.length % 7));
    days.push({ date: toMonth(date) + "-" + String(date.getDate()).padStart(2, "0"), day: date.getDate(), inMonth: false });
  }
  return days;
}

function occursOn(event: MarketCalendarEvent, dateValue: string) {
  return event.start_date <= dateValue && event.end_date >= dateValue;
}

function themeColor(themeId: number, themeName = "") {
  const seed = String(themeId) + themeName;
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) hash = (hash * 31 + seed.charCodeAt(index)) >>> 0;
  return THEME_COLORS[hash % THEME_COLORS.length];
}

function hexToRgba(hex: string, alpha: number) {
  const value = hex.replace("#", "");
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return "rgba(" + r + ", " + g + ", " + b + ", " + alpha + ")";
}

function eventDateLabel(event: MarketCalendarEvent) {
  return event.start_date === event.end_date ? event.start_date : event.start_date + " ~ " + event.end_date;
}

function getThemeInitial(event: MarketCalendarEvent) {
  const source = (event.theme_name || event.title || EVENT_TYPE_LABELS[event.event_type] || "?").trim();
  return Array.from(source)[0] ?? "?";
}

function getThemeColor(event: MarketCalendarEvent) {
  return themeColor(event.theme_id, event.theme_name || event.title);
}

function getShortEventTitle(event: MarketCalendarEvent) {
  return event.title.trim() || EVENT_TYPE_LABELS[event.event_type];
}

function getEventUrl(event: MarketCalendarEvent) {
  return event.news_url || (event as MarketCalendarEvent & { url?: string | null }).url || null;
}

function stockFromCalendar(stock: MarketCalendarEvent["stocks"][number]): Stock {
  return {
    id: stock.stock_id,
    stock_code: stock.stock_code ?? "",
    stock_name: stock.stock_name ?? "",
    market: null,
    sector: null,
    industry: null,
    isin_code: null,
    corp_name: null,
    corp_reg_no: null,
    last_synced_at: null,
    source: null,
    security_type: null,
    is_active: 1,
    created_at: "",
    updated_at: "",
  };
}

function MarketCalendarPage() {
  const today = todayKst();
  const [month, setMonth] = useState(toMonth(new Date(today + "T00:00:00")));
  const [events, setEvents] = useState<MarketCalendarEvent[]>([]);
  const [dailyEvents, setDailyEvents] = useState<MarketCalendarEvent[]>([]);
  const [themes, setThemes] = useState<MarketTheme[]>([]);
  const [themeGroupId, setThemeGroupId] = useState<number | "">("");
  const [keyword, setKeyword] = useState("");
  const [eventType, setEventType] = useState<MarketCalendarEventType | "">("");
  const [selectedDate, setSelectedDate] = useState(today);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<MarketCalendarEvent | null>(null);
  const [form, setForm] = useState<MarketCalendarEventInput>(emptyForm(today));
  const [selectedStocks, setSelectedStocks] = useState<Stock[]>([]);
  const [stockKeyword, setStockKeyword] = useState("");
  const [stockResults, setStockResults] = useState<Stock[]>([]);
  const [themeSearchText, setThemeSearchText] = useState("");
  const [themeDropdownOpen, setThemeDropdownOpen] = useState(false);
  const [, setMessage] = useState("");
  const [formError, setFormError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const themePickerRef = useRef<HTMLDivElement | null>(null);

  const themeGroups = useMemo(() => themes.filter((theme) => theme.theme_level === "THEME_GROUP"), [themes]);
  const themeItems = useMemo(() => themes.filter((theme) => theme.theme_level === "THEME" && theme.is_active === 1), [themes]);
  const selectedTheme = useMemo(() => themeItems.find((theme) => theme.id === form.theme_id) ?? null, [form.theme_id, themeItems]);
  const calendarDays = useMemo(() => buildCalendarDays(month), [month]);
  const themeOptions = useMemo(() => {
    const query = themeSearchText.trim().toLowerCase();
    return themeItems
      .filter((theme) => {
        if (themeGroupId && theme.parent_theme_id !== themeGroupId) return false;
        if (!query) return true;
        return [theme.theme_name, theme.parent_theme_name ?? "", ...(theme.keywords ?? [])].join(" ").toLowerCase().includes(query);
      })
      .sort((a, b) => {
        const aReturn = a.latest_return?.avg_change_rate ?? -999;
        const bReturn = b.latest_return?.avg_change_rate ?? -999;
        if (bReturn !== aReturn) return bReturn - aReturn;
        return (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.theme_name.localeCompare(b.theme_name, "ko");
      })
      .slice(0, 10);
  }, [themeGroupId, themeItems, themeSearchText]);

  const loadThemes = async () => {
    const rows = await repositories.marketThemes.list({ is_active: 1, limit: 500 });
    setThemes(rows);
  };

  const loadMonthly = async () => {
    const response = await repositories.marketCalendar.listMonthly({
      month,
      theme_group_id: themeGroupId || undefined,
      keyword: keyword.trim() || undefined,
      event_type: eventType || undefined,
    });
    setEvents(response.events);
  };

  const loadDaily = async (dateValue: string) => {
    const response = await repositories.marketCalendar.listDaily(dateValue);
    setDailyEvents(response.events);
  };

  const closeModal = () => {
    if (isSaving) return;
    setModalOpen(false);
    setFormError("");
    setThemeDropdownOpen(false);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
  };

  useEffect(() => {
    loadThemes().catch((error) => setMessage(error instanceof Error ? error.message : String(error)));
  }, []);

  useEffect(() => {
    loadMonthly().catch((error) => setMessage(error instanceof Error ? error.message : String(error)));
  }, [month, themeGroupId, eventType]);

  useEffect(() => {
    const onClick = (event: MouseEvent) => {
      if (themePickerRef.current && !themePickerRef.current.contains(event.target as Node)) setThemeDropdownOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (modalOpen) return;
      if (drawerOpen) closeDrawer();
      else setThemeDropdownOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [drawerOpen, modalOpen, isSaving]);

  const openDrawer = async (dateValue: string) => {
    setSelectedDate(dateValue);
    setDrawerOpen(true);
    await loadDaily(dateValue);
  };

  const openCreateModal = (dateValue = selectedDate) => {
    setEditingEvent(null);
    setSelectedStocks([]);
    setStockKeyword("");
    setStockResults([]);
    setThemeSearchText("");
    setForm(emptyForm(dateValue));
    setFormError("");
    setModalOpen(true);
  };

  const openEditModal = (event: MarketCalendarEvent) => {
    setEditingEvent(event);
    setSelectedStocks(event.stocks.map(stockFromCalendar));
    setThemeSearchText(event.theme_name);
    setForm({
      start_date: event.start_date,
      end_date: event.end_date,
      theme_id: event.theme_id,
      title: event.title,
      summary: event.summary ?? "",
      news_url: event.news_url ?? "",
      event_type: event.event_type,
      importance: event.importance,
      memo: event.memo ?? "",
      stock_ids: event.stocks.map((stock) => stock.stock_id),
    });
    setFormError("");
    setModalOpen(true);
  };

  const searchStocks = async () => {
    const query = stockKeyword.trim();
    if (!query) {
      setStockResults([]);
      return;
    }
    const rows = await repositories.stocks.list({ keyword: query, is_active: 1, limit: 10 });
    setStockResults(rows);
  };

  const addStock = (stock: Stock) => {
    if (selectedStocks.some((item) => item.id === stock.id)) return;
    const next = [...selectedStocks, stock];
    setSelectedStocks(next);
    setForm((prev) => ({ ...prev, stock_ids: next.map((item) => item.id) }));
    setStockKeyword("");
    setStockResults([]);
  };

  const removeStock = (stockId: number) => {
    const next = selectedStocks.filter((stock) => stock.id !== stockId);
    setSelectedStocks(next);
    setForm((prev) => ({ ...prev, stock_ids: next.map((item) => item.id) }));
  };

  const validateForm = () => {
    if (!form.start_date) return "시작일을 선택해 주세요.";
    if (!form.end_date) return "종료일을 선택해 주세요.";
    if (form.end_date < form.start_date) return "종료일은 시작일보다 빠를 수 없습니다.";
    if (!form.theme_id) return "테마를 선택해 주세요.";
    if (!form.title.trim()) return "뉴스명을 입력해 주세요.";
    if (form.news_url && form.news_url.trim() && !/^https?:\/\//i.test(form.news_url.trim())) return "뉴스 URL은 http:// 또는 https://로 시작해야 합니다.";
    return "";
  };

  const saveEvent = async () => {
    const error = validateForm();
    if (error) {
      setFormError(error);
      return;
    }
    setIsSaving(true);
    setFormError("");
    try {
      const payload: MarketCalendarEventInput = {
        start_date: form.start_date,
        end_date: form.end_date,
        theme_id: Number(form.theme_id),
        title: form.title.trim(),
        summary: form.summary?.trim() || null,
        news_url: form.news_url?.trim() || null,
        event_type: form.event_type || "news",
        importance: form.importance || "medium",
        memo: form.memo?.trim() || null,
        stock_ids: selectedStocks.map((stock) => stock.id),
      };
      if (editingEvent) await repositories.marketCalendar.update(editingEvent.id, payload);
      else await repositories.marketCalendar.create(payload);
      setModalOpen(false);
      setForm(emptyForm(selectedDate));
      setSelectedStocks([]);
      await loadMonthly();
      if (drawerOpen) await loadDaily(selectedDate);
    } catch (error) {
      console.error(error);
      setFormError("뉴스 등록에 실패했습니다. 입력값과 서버 상태를 확인해 주세요.");
    } finally {
      setIsSaving(false);
    }
  };

  const deleteEvent = async (event: MarketCalendarEvent) => {
    if (!window.confirm("이 캘린더 뉴스를 삭제할까요?")) return;
    await repositories.marketCalendar.delete(event.id);
    setMessage("");
    await loadMonthly();
    if (drawerOpen) await loadDaily(selectedDate);
  };

  return (
    <div className="market-calendar-page">
      <PageHeader
        title="증시 캘린더"
        description="테마별 주요 뉴스와 일정 흐름을 월간 캘린더로 관리합니다."
        action={<button className="btn-primary" type="button" onClick={() => openCreateModal(today)}>+ 뉴스 등록</button>}
      />
      <SectionCard className="market-calendar-card">
        <div className="market-calendar-toolbar">
          <div className="market-calendar-month-nav calendar-period-nav">
            <button type="button" className="btn-secondary calendar-nav-button" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="이전 월">◀</button>
            <input className="input-control calendar-period-input" type="month" value={month} onChange={(event) => setMonth(event.target.value)} aria-label="증시 캘린더 월" />
            <button type="button" className="btn-secondary calendar-nav-button" onClick={() => setMonth(shiftMonth(month, 1))} aria-label="다음 월">▶</button>
            <button type="button" className="btn-primary calendar-today-button" onClick={() => setMonth(toMonth(new Date(today + "T00:00:00")))}>이번달</button>
          </div>
          <div className="market-calendar-filters">
            <select value={themeGroupId} onChange={(event) => setThemeGroupId(event.target.value ? Number(event.target.value) : "")}> 
              <option value="">테마그룹 전체</option>
              {themeGroups.map((theme) => <option key={theme.id} value={theme.id}>{theme.theme_name}</option>)}
            </select>
            <select value={eventType} onChange={(event) => setEventType(event.target.value as MarketCalendarEventType | "")}> 
              <option value="">유형 전체</option>
              {Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <input value={keyword} onChange={(event) => setKeyword(event.target.value)} onKeyDown={(event) => event.key === "Enter" && loadMonthly()} placeholder="테마명, 뉴스 제목, 키워드 검색" />
            <button type="button" className="btn-secondary" onClick={() => loadMonthly()}>조회</button>
          </div>
        </div>
        <div className="market-calendar-weekdays">
          {["일", "월", "화", "수", "목", "금", "토"].map((day) => <span key={day}>{day}</span>)}
        </div>
        <div className="market-calendar-grid">
          {calendarDays.map((day) => {
            const dayEvents = events.filter((event) => occursOn(event, day.date));
            const visible = dayEvents.slice(0, 4);
            return (
              <button key={day.date} type="button" className={clsx("market-calendar-day", !day.inMonth && "market-calendar-day--muted", day.date === today && "market-calendar-day--today", day.date === selectedDate && drawerOpen && "market-calendar-day--selected")} onClick={() => openDrawer(day.date)}>
                <div className="market-calendar-day__number">{day.day}</div>
                <div className="market-calendar-day__events">
                  {visible.map((event) => {
                    const color = getThemeColor(event);
                    return (
                      <div key={event.id} className="market-calendar-event-chip" title={eventDateLabel(event) + " · " + event.title}>
                        <span className="market-calendar-event-initial" style={{ backgroundColor: color }}>{getThemeInitial(event)}</span>
                        <strong>{getShortEventTitle(event)}</strong>
                      </div>
                    );
                  })}
                  {dayEvents.length > 4 ? <div className="market-calendar-more">+ {dayEvents.length - 4}개 더</div> : null}
                </div>
              </button>
            );
          })}
        </div>
      </SectionCard>
      {drawerOpen ? (
        <div className="market-calendar-drawer-overlay" role="presentation" onClick={closeDrawer}>
          <aside className="market-calendar-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="market-calendar-drawer__header">
              <div><h3>{selectedDate}</h3><p>{dailyEvents.length}개 일정</p></div>
              <button type="button" className="btn-secondary" onClick={closeDrawer}>닫기</button>
            </div>
            <button type="button" className="btn-primary market-calendar-drawer__add" onClick={() => openCreateModal(selectedDate)}>+ 이 날짜에 뉴스 등록</button>
            <div className="market-calendar-drawer__list">
              {dailyEvents.length === 0 ? <div className="empty-state">등록된 뉴스가 없습니다.</div> : null}
              {dailyEvents.map((event) => {
                const color = getThemeColor(event);
                const eventUrl = getEventUrl(event);
                return (
                  <article key={event.id} className="market-calendar-detail-card">
                    <div className="market-calendar-detail-card__top">
                      <span className="badge-soft market-calendar-theme-badge" style={{ color, backgroundColor: hexToRgba(color, 0.12) }}>
                        <i style={{ backgroundColor: color }} aria-hidden="true" />
                        {event.theme_name}
                      </span>
                      <span className="badge-soft market-calendar-type-badge">{EVENT_TYPE_LABELS[event.event_type]}</span>
                      <span className={clsx("badge-soft", "market-calendar-importance-badge", "market-calendar-importance-badge--" + event.importance)}>{IMPORTANCE_LABELS[event.importance]}</span>
                    </div>
                    <h4>{event.title}</h4>
                    <p className="market-calendar-event-summary">{event.summary || "요약 없음"}</p>
                    {event.memo ? <div className="market-calendar-event-memo"><span>메모</span><p>{event.memo}</p></div> : null}
                    {event.stocks.length ? <div className="chip-row">{event.stocks.map((stock) => <span key={stock.stock_id} className="chip-light">{stock.stock_name} {stock.stock_code}</span>)}</div> : null}
                    <div className="market-calendar-detail-card__meta">{eventDateLabel(event)}</div>
                    <div className="market-calendar-detail-card__actions">
                      {eventUrl ? <a className="btn-secondary" href={eventUrl} target="_blank" rel="noreferrer" onClick={(clickEvent) => clickEvent.stopPropagation()}>원문보기</a> : null}
                      <button type="button" className="btn-secondary" onClick={() => openEditModal(event)}>수정</button>
                      <button type="button" className="btn-danger" onClick={() => deleteEvent(event)}>삭제</button>
                    </div>
                  </article>
                );
              })}
            </div>
          </aside>
        </div>
      ) : null}
      {modalOpen ? (
        <div className="market-calendar-modal-backdrop" role="presentation">
          <div className="market-calendar-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="market-calendar-modal__header">
              <h3>{editingEvent ? "뉴스 수정" : "뉴스 등록"}</h3>
              <button type="button" className="btn-secondary" onClick={closeModal}>닫기</button>
            </div>
            <div className="market-calendar-modal__body">
              {formError ? <div className="alert-error market-calendar-form-alert">{formError}</div> : null}
              <div className="market-calendar-date-grid">
                <label>시작일<input type="date" value={form.start_date} onChange={(event) => setForm((prev) => ({ ...prev, start_date: event.target.value }))} /></label>
                <label>종료일<input type="date" value={form.end_date} onChange={(event) => setForm((prev) => ({ ...prev, end_date: event.target.value }))} /></label>
              </div>
              <div className="market-calendar-meta-grid">
                <label className="market-calendar-field market-calendar-theme-field">테마
                  <div className="theme-search-combobox market-calendar-theme-picker" ref={themePickerRef}>
                    <input className="theme-search-combobox__input" value={themeDropdownOpen ? themeSearchText : selectedTheme?.theme_name ?? themeSearchText} placeholder="테마명 검색" onFocus={() => setThemeDropdownOpen(true)} onChange={(event) => { setThemeSearchText(event.target.value); setThemeDropdownOpen(true); setForm((prev) => ({ ...prev, theme_id: 0 })); }} />
                    <button type="button" className="theme-search-combobox__arrow" onClick={() => setThemeDropdownOpen((open) => !open)}>▾</button>
                    {themeDropdownOpen ? (
                      <div className="theme-search-combobox__menu">
                        {themeOptions.length === 0 ? <div className="theme-search-combobox__empty">검색된 테마가 없습니다.</div> : null}
                        {themeOptions.map((theme) => (
                          <button key={theme.id} type="button" className={clsx("theme-search-combobox__item", form.theme_id === theme.id && "theme-search-combobox__item--active")} onMouseDown={(event) => event.preventDefault()} onClick={() => { setForm((prev) => ({ ...prev, theme_id: theme.id })); setThemeSearchText(theme.theme_name); setThemeDropdownOpen(false); }}>
                            <span className="theme-search-combobox__item-title">{theme.theme_name}</span>
                            <span className="theme-search-combobox__item-meta">{theme.parent_theme_name || "미지정"} · 연결 {theme.linked_stock_count ?? theme.stock_count ?? 0}종목</span>
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </label>
                <label>유형<select value={form.event_type} onChange={(event) => setForm((prev) => ({ ...prev, event_type: event.target.value as MarketCalendarEventType }))}>{Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                <label>중요도<select value={form.importance} onChange={(event) => setForm((prev) => ({ ...prev, importance: event.target.value as MarketCalendarImportance }))}>{Object.entries(IMPORTANCE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
              </div>
              <label className="market-calendar-field">제목<input value={form.title} onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))} placeholder="뉴스 또는 일정 제목" /></label>
              <label className="market-calendar-field">요약<textarea value={form.summary ?? ""} onChange={(event) => setForm((prev) => ({ ...prev, summary: event.target.value }))} rows={3} /></label>
              <label className="market-calendar-field">뉴스 URL<input value={form.news_url ?? ""} onChange={(event) => setForm((prev) => ({ ...prev, news_url: event.target.value }))} placeholder="https://" /></label>
              <label className="market-calendar-field">관련 종목</label>
              <div className="market-calendar-stock-search">
                <input value={stockKeyword} onChange={(event) => setStockKeyword(event.target.value)} onKeyDown={(event) => event.key === "Enter" && searchStocks()} placeholder="종목명 또는 종목코드 검색" />
                <button type="button" className="btn-secondary" onClick={searchStocks}>검색</button>
              </div>
              {stockResults.length ? <div className="market-calendar-stock-results">{stockResults.map((stock) => <button key={stock.id} type="button" onClick={() => addStock(stock)}>{stock.stock_name} <span>{stock.stock_code}</span></button>)}</div> : null}
              <div className="chip-row">{selectedStocks.map((stock) => <button key={stock.id} type="button" className="chip-light" onClick={() => removeStock(stock.id)}>{stock.stock_name} {stock.stock_code} ×</button>)}</div>
              <label className="market-calendar-field">메모<textarea value={form.memo ?? ""} onChange={(event) => setForm((prev) => ({ ...prev, memo: event.target.value }))} rows={3} /></label>
            </div>
            <div className="market-calendar-modal__footer">
              <p>시작일, 종료일, 테마, 제목은 필수입니다.</p>
              <div className="market-calendar-modal__footer-actions">
                <button type="button" className="btn-secondary" disabled={isSaving} onClick={() => { setForm(emptyForm(selectedDate)); setSelectedStocks([]); setFormError(""); }}>초기화</button>
                <button type="button" className="btn-secondary" disabled={isSaving} onClick={closeModal}>취소</button>
                <button type="button" className="btn-primary" disabled={isSaving} onClick={() => saveEvent()}>{isSaving ? "저장 중..." : "저장"}</button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default MarketCalendarPage;





