import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type {
  AddMarketEventThemeLinkRequest,
  DailyThemeFlowStock,
  DailyThemeFlowSummary,
  KiwoomConditionItem,
  KiwoomConditionResultItem,
  KiwoomMarketEventItem,
  MarketEventThemeLink,
} from "@/types/marketTrend";

type ActiveTab = "kiwoom" | "flow";
type SortOrder = "asc" | "desc";
type ConditionSortKey = "condition_seq" | "condition_name";
type ResultSortKey = "stock_code" | "stock_name" | "current_price" | "change_rate" | "volume" | "estimated_trading_value";

const fmtNumber = (value: number | null | undefined) => (value == null ? "-" : value.toLocaleString("ko-KR"));
const fmtPct = (value: number | null | undefined) => (value == null ? "-" : `${value.toFixed(2)}%`);
const fmtEokShort = (value: number | null | undefined) => (value == null ? "-" : `${(value / 100000000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`);
const fmtEok2 = (value: number | null | undefined) => (value == null ? "-" : (value / 100000000).toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const toErr = (e: unknown, fallback: string) => (e instanceof Error && e.message ? e.message : fallback);

const formatDate = (value: string | null | undefined) => {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).replace("T", " ").slice(0, 10);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

const normalizeStockCode = (value: string | null | undefined) => {
  if (!value) return "";
  const digits = String(value).replace(/[^0-9]/g, "");
  if (!digits) return "";
  return digits.slice(-6).padStart(6, "0");
};

const getNaverChartImageUrl = (stockCode: string, period: "week" | "month3" | "year", sidcode: number) => {
  const code = normalizeStockCode(stockCode);
  return `https://ssl.pstatic.net/imgfinance/chart/item/area/${period}/${code}.png?sidcode=${sidcode}`;
};

const estimatedTradingValue = (item: { estimated_trading_value?: number | null; current_price?: number | null; volume?: number | null; trading_value?: number | null }) => {
  if (item.estimated_trading_value != null) return item.estimated_trading_value;
  if (item.current_price != null && item.volume != null) return Math.max(0, item.current_price) * Math.max(0, item.volume);
  if (item.trading_value != null) return item.trading_value;
  return null;
};

const getResultRowKey = (row: KiwoomConditionResultItem) => `${row.stock_code || "NA"}|${row.stock_name || "NA"}|${row.detected_at || "NA"}|${row.source_api || "NA"}`;

function MarketTrendsPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("kiwoom");

  const [conditions, setConditions] = useState<KiwoomConditionItem[]>([]);
  const [selectedConditionSeq, setSelectedConditionSeq] = useState("");
  const [selectedConditionName, setSelectedConditionName] = useState("");
  const [results, setResults] = useState<KiwoomConditionResultItem[]>([]);
  const [checkedMap, setCheckedMap] = useState<Record<string, boolean>>({});

  const [events, setEvents] = useState<KiwoomMarketEventItem[]>([]);
  const [eventThemeLinksMap, setEventThemeLinksMap] = useState<Record<number, MarketEventThemeLink[]>>({});
  const [eventDrafts, setEventDrafts] = useState<Record<number, { theme_status: string; user_memo: string; selected_theme_id: string }>>({});
  const [marketThemes, setMarketThemes] = useState<Array<{ id: number; theme_name: string }>>([]);

  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10));
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [conditionSort, setConditionSort] = useState<{ key: ConditionSortKey; order: SortOrder }>({ key: "condition_seq", order: "asc" });
  const [resultSort, setResultSort] = useState<{ key: ResultSortKey; order: SortOrder }>({ key: "change_rate", order: "desc" });

  const [flowSummaries, setFlowSummaries] = useState<DailyThemeFlowSummary[]>([]);
  const [flowStocks, setFlowStocks] = useState<DailyThemeFlowStock[]>([]);
  const [selectedFlowTheme, setSelectedFlowTheme] = useState<{ id: number; name: string } | null>(null);
  const [flowLoading, setFlowLoading] = useState(false);
  const [flowStocksLoading, setFlowStocksLoading] = useState(false);
  const [chartSidcode, setChartSidcode] = useState<number>(Date.now());
  const [brokenCharts, setBrokenCharts] = useState<Record<string, boolean>>({});
  const [zoomedChart, setZoomedChart] = useState<{ url: string; alt: string } | null>(null);

  const toggleSort = <T extends string,>(prev: { key: T; order: SortOrder }, key: T): { key: T; order: SortOrder } => {
    if (prev.key === key) {
      return { key, order: prev.order === "asc" ? "desc" : "asc" };
    }
    return { key, order: "asc" };
  };

  const sortedConditions = useMemo(() => {
    const arr = [...conditions];
    arr.sort((a, b) => {
      let cmp = 0;
      if (conditionSort.key === "condition_seq") cmp = Number(a.condition_seq) - Number(b.condition_seq);
      else cmp = a.condition_name.localeCompare(b.condition_name, "ko");
      return conditionSort.order === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [conditions, conditionSort]);

  const sortedResults = useMemo(() => {
    const arr = [...results];
    arr.sort((a, b) => {
      const num = (v: number | null | undefined) => (v == null ? Number.NEGATIVE_INFINITY : v);
      let cmp = 0;
      switch (resultSort.key) {
        case "stock_code": cmp = (a.stock_code || "").localeCompare(b.stock_code || ""); break;
        case "stock_name": cmp = (a.stock_name || "").localeCompare(b.stock_name || "", "ko"); break;
        case "current_price": cmp = num(a.current_price) - num(b.current_price); break;
        case "change_rate": cmp = num(a.change_rate) - num(b.change_rate); break;
        case "volume": cmp = num(a.volume) - num(b.volume); break;
        case "estimated_trading_value": cmp = num(estimatedTradingValue(a)) - num(estimatedTradingValue(b)); break;
      }
      return resultSort.order === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [results, resultSort]);

  const selectedItems = useMemo(() => sortedResults.filter((r) => checkedMap[getResultRowKey(r)]), [checkedMap, sortedResults]);
  const sortMark = (active: boolean, order: SortOrder) => (active ? (order === "asc" ? " ▲" : " ▼") : "");

  const loadConditions = async () => {
    setError("");
    try {
      const res = await repositories.marketTrends.getKiwoomConditions();
      setConditions(res.items);
    } catch (e) {
      setError(toErr(e, "조건검색 목록을 불러오지 못했습니다."));
    }
  };

  const loadConditionResults = async () => {
    if (!selectedConditionSeq) {
      setError("조건식을 먼저 선택해 주세요.");
      return;
    }
    setError("");
    setMessage("키움 조건검색 결과를 조회 중입니다.");
    try {
      const res = await repositories.marketTrends.previewKiwoomConditionResults(selectedConditionSeq, {
        condition_name: selectedConditionName || null,
        header_mode: "auth-only",
        login_mode: "message-token",
        search_type: "0",
        stex_tp: "K",
      });
      setResults(res.items ?? []);
      setCheckedMap({});
      if ((res.item_count ?? 0) === 0) setMessage("현재 조건검색 결과가 없습니다.");
      else setMessage(`조건검색 결과 ${res.item_count}건을 조회했습니다. 저장할 종목을 선택하세요.`);
    } catch (e) {
      setMessage("");
      setError(toErr(e, "조건검색 결과 조회에 실패했습니다. Agent 실행 상태와 키움 연결을 확인해 주세요."));
    }
  };

  const saveSelectedAsEvents = async () => {
    if (!selectedConditionSeq) {
      setError("조건식을 먼저 선택해 주세요.");
      return;
    }
    if (selectedItems.length === 0) {
      setError("수급 이벤트 후보로 저장할 종목을 선택해 주세요.");
      return;
    }
    setError("");
    setMessage("");
    try {
      const res = await repositories.marketTrends.saveKiwoomMarketEvents({
        condition_seq: selectedConditionSeq,
        condition_name: selectedConditionName,
        source: "kiwoom_rest",
        items: selectedItems,
      });
      setMessage(`수급 이벤트 후보 저장 완료: saved ${res.saved_count}, updated ${res.updated_count}, unmatched ${res.unmatched_count}`);
      await loadEvents();
    } catch (e) {
      setError(toErr(e, "수급 이벤트 후보 저장에 실패했습니다."));
    }
  };

  const loadEvents = async () => {
    setError("");
    try {
      const res = await repositories.marketTrends.getKiwoomMarketEvents(tradeDate, 200);
      setEvents(res.items);
      const draftMap: Record<number, { theme_status: string; user_memo: string; selected_theme_id: string }> = {};
      for (const item of res.items) {
        draftMap[item.event_id] = {
          theme_status: item.theme_status || "unassigned",
          user_memo: item.user_memo || "",
          selected_theme_id: "",
        };
      }
      setEventDrafts(draftMap);

      const linkEntries = await Promise.all(
        res.items.map(async (item) => {
          const linkRes = await repositories.marketTrends.getKiwoomMarketEventThemes(item.event_id);
          return [item.event_id, linkRes.items] as const;
        }),
      );
      setEventThemeLinksMap(Object.fromEntries(linkEntries));
    } catch (e) {
      setError(toErr(e, "저장된 수급 이벤트 후보를 불러오지 못했습니다."));
    }
  };

  const loadMarketThemes = async () => {
    try {
      const items = await repositories.marketThemes.list({ is_active: 1, limit: 500 });
      setMarketThemes(items.map((x) => ({ id: x.id, theme_name: x.theme_name })));
    } catch {
      setMarketThemes([]);
    }
  };

  const saveEventNote = async (eventId: number) => {
    const draft = eventDrafts[eventId];
    if (!draft) return;
    setError("");
    setMessage("");
    try {
      const res = await repositories.marketTrends.updateKiwoomMarketEvent(eventId, {
        theme_status: draft.theme_status,
        user_memo: draft.user_memo,
      });
      setMessage(`메모 저장 완료: event_id=${res.item.event_id}`);
      await loadEvents();
    } catch (e) {
      setError(toErr(e, "메모 저장에 실패했습니다."));
    }
  };

  const addThemeLink = async (eventId: number) => {
    const draft = eventDrafts[eventId];
    if (!draft?.selected_theme_id) {
      setError("추가 연결할 테마를 선택해 주세요.");
      return;
    }
    setError("");
    setMessage("");
    try {
      const payload: AddMarketEventThemeLinkRequest = {
        market_theme_id: Number(draft.selected_theme_id),
        user_memo: draft.user_memo || null,
      };
      await repositories.marketTrends.addKiwoomMarketEventTheme(eventId, payload);
      const links = await repositories.marketTrends.getKiwoomMarketEventThemes(eventId);
      setEventThemeLinksMap((prev) => ({ ...prev, [eventId]: links.items }));
      setMessage("테마를 추가 연결했습니다.");
    } catch (e) {
      setError(toErr(e, "테마 추가 연결에 실패했습니다."));
    }
  };

  const removeThemeLink = async (eventId: number, linkId: number) => {
    setError("");
    setMessage("");
    try {
      await repositories.marketTrends.removeKiwoomMarketEventTheme(eventId, linkId);
      const links = await repositories.marketTrends.getKiwoomMarketEventThemes(eventId);
      setEventThemeLinksMap((prev) => ({ ...prev, [eventId]: links.items }));
      setMessage("테마 연결을 해제했습니다.");
    } catch (e) {
      setError(toErr(e, "테마 연결 해제에 실패했습니다."));
    }
  };

  const deleteEvent = async (eventId: number) => {
    const ok = window.confirm("이 수급 이벤트 후보를 삭제하시겠습니까? 연결된 테마 기록도 함께 해제될 수 있습니다.");
    if (!ok) return;
    setError("");
    setMessage("");
    try {
      await repositories.marketTrends.deleteKiwoomMarketEvent(eventId);
      setMessage(`삭제 완료: event_id=${eventId}`);
      await loadEvents();
    } catch (e) {
      setError(toErr(e, "수급 이벤트 후보 삭제에 실패했습니다."));
    }
  };

  const loadFlow = async () => {
    setError("");
    setMessage("");
    setFlowLoading(true);
    setSelectedFlowTheme(null);
    setFlowStocks([]);
    try {
      const res = await repositories.marketTrends.getExternalDailyThemeFlow(tradeDate);
      setFlowSummaries(res.items ?? []);
      if ((res.items ?? []).length === 0) setMessage("해당일에 테마가 연결된 수급 이벤트 후보가 없습니다.");
    } catch (e) {
      setError(toErr(e, "일별 테마 수급 흐름 조회에 실패했습니다."));
      setFlowSummaries([]);
    } finally {
      setFlowLoading(false);
    }
  };

  const loadFlowStocks = async (theme: DailyThemeFlowSummary) => {
    setSelectedFlowTheme({ id: theme.market_theme_id, name: theme.theme_name });
    setFlowStocksLoading(true);
    setChartSidcode(Date.now());
    setBrokenCharts({});
    try {
      const res = await repositories.marketTrends.getExternalDailyThemeFlowStocks(tradeDate, theme.market_theme_id);
      setFlowStocks(res.items ?? []);
    } catch (e) {
      setError(toErr(e, "선택 테마 상세 종목 조회에 실패했습니다."));
      setFlowStocks([]);
    } finally {
      setFlowStocksLoading(false);
    }
  };

  const onChartError = (key: string) => setBrokenCharts((prev) => ({ ...prev, [key]: true }));

  useEffect(() => {
    void loadConditions();
    void loadMarketThemes();
    void loadEvents();
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader title="시장 트랜드 분석" description="조건검색 결과를 수급 이벤트 후보로 저장하고 분석 우선순위를 관리합니다." />
      {message ? <div className="inline-result">{message}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}

      <SectionCard title="작업 탭">
        <div className="flex gap-2">
          <button type="button" className={`btn ${activeTab === "kiwoom" ? "btn-primary" : "btn-secondary"}`} onClick={() => setActiveTab("kiwoom")}>키움 조건검색 수급 이벤트</button>
          <button type="button" className={`btn ${activeTab === "flow" ? "btn-primary" : "btn-secondary"}`} onClick={() => setActiveTab("flow")}>일별 테마 수급 흐름</button>
        </div>
      </SectionCard>

      {activeTab === "kiwoom" ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 xl:grid-cols-[380px_1fr] gap-4">
            <SectionCard title="키움 조건검색 목록">
              <div className="flex gap-2 mb-2">
                <button type="button" className="btn btn-secondary" onClick={() => void loadConditions()}>조건검색 목록 새로고침</button>
              </div>
              <p className="text-xs text-muted mb-2">키움 원천 목록 갱신은 kiwoom-rest-agent 실행 후 반영됩니다.</p>
              <div className="table-shell max-h-[420px] overflow-auto">
                <table className="data-table compact-table">
                  <thead>
                    <tr>
                      <th className="cursor-pointer" onClick={() => setConditionSort((p) => toggleSort(p, "condition_seq"))}>조건식 번호{sortMark(conditionSort.key === "condition_seq", conditionSort.order)}</th>
                      <th className="cursor-pointer" onClick={() => setConditionSort((p) => toggleSort(p, "condition_name"))}>조건식명{sortMark(conditionSort.key === "condition_name", conditionSort.order)}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedConditions.map((c) => {
                      const selected = selectedConditionSeq === c.condition_seq;
                      return (
                        <tr key={c.id} className={`cursor-pointer ${selected ? "bg-blue-50" : ""}`} onClick={() => { setSelectedConditionSeq(c.condition_seq); setSelectedConditionName(c.condition_name); }}>
                          <td>{c.condition_seq}</td>
                          <td className="max-w-[220px] truncate" title={c.condition_name}>{c.condition_name}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </SectionCard>

            <SectionCard title="조건검색 결과 / 수급 이벤트 후보">
              <div className="space-y-2 mb-3">
                <div className="text-sm text-muted">선택 조건식: {selectedConditionSeq ? `${selectedConditionSeq} · ${selectedConditionName}` : "미선택"}</div>
                <div className="flex gap-2 flex-wrap">
                  <button type="button" className="btn btn-secondary" onClick={() => void loadConditionResults()}>조건검색 결과 조회</button>
                  <button type="button" className="btn btn-primary" onClick={() => void saveSelectedAsEvents()}>선택 종목 수급 이벤트 후보 저장</button>
                </div>
                <p className="text-xs text-muted">조건검색 결과는 조회 전용이며, 선택 저장 시에만 수급 이벤트 후보로 저장됩니다.</p>
              </div>
              <div className="table-shell max-h-[420px] overflow-auto">
                <table className="data-table compact-table">
                  <thead>
                    <tr>
                      <th>체크</th>
                      <th className="cursor-pointer" onClick={() => setResultSort((p) => toggleSort(p, "stock_code"))}>종목코드{sortMark(resultSort.key === "stock_code", resultSort.order)}</th>
                      <th className="cursor-pointer" onClick={() => setResultSort((p) => toggleSort(p, "stock_name"))}>종목명{sortMark(resultSort.key === "stock_name", resultSort.order)}</th>
                      <th className="cursor-pointer" style={{ textAlign: "right" }} onClick={() => setResultSort((p) => toggleSort(p, "current_price"))}>현재가{sortMark(resultSort.key === "current_price", resultSort.order)}</th>
                      <th className="cursor-pointer text-right" onClick={() => setResultSort((p) => toggleSort(p, "change_rate"))}>등락률{sortMark(resultSort.key === "change_rate", resultSort.order)}</th>
                      <th className="cursor-pointer" style={{ textAlign: "right" }} onClick={() => setResultSort((p) => toggleSort(p, "volume"))}>거래량{sortMark(resultSort.key === "volume", resultSort.order)}</th>
                      <th className="cursor-pointer" style={{ textAlign: "right" }} onClick={() => setResultSort((p) => toggleSort(p, "estimated_trading_value"))}>거래대금(추정, 억){sortMark(resultSort.key === "estimated_trading_value", resultSort.order)}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedResults.map((r) => {
                      const key = getResultRowKey(r);
                      return (
                        <tr key={key}>
                          <td><input type="checkbox" checked={Boolean(checkedMap[key])} onChange={(e) => setCheckedMap((prev) => ({ ...prev, [key]: e.target.checked }))} /></td>
                          <td>{r.stock_code || "-"}</td>
                          <td>{r.stock_name || "-"}</td>
                          <td style={{ textAlign: "right" }}>{fmtNumber(r.current_price)}</td>
                          <td className="text-right">{fmtPct(r.change_rate)}</td>
                          <td style={{ textAlign: "right" }}>{fmtNumber(r.volume)}</td>
                          <td style={{ textAlign: "right" }}>{fmtEok2(estimatedTradingValue(r))}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          </div>

          <SectionCard title="저장된 수급 이벤트 후보">
            <div className="flex gap-2 items-end mb-2 flex-wrap">
              <input className="input-control" style={{ width: "160px", minWidth: "160px" }} type="date" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} />
              <button type="button" className="btn btn-secondary" onClick={() => void loadEvents()}>조회</button>
            </div>
            <div className="table-shell max-h-[380px] overflow-auto">
              <table className="data-table compact-table">
                <thead>
                  <tr>
                    <th>감지일</th><th>종목코드</th><th>종목명</th><th>시장</th><th className="text-right">등락률</th><th>연결 테마</th><th>메모</th><th>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e) => {
                    const draft = eventDrafts[e.event_id] ?? { theme_status: "unassigned", user_memo: "", selected_theme_id: "" };
                    const links = eventThemeLinksMap[e.event_id] ?? [];
                    return (
                      <tr key={e.event_id}>
                        <td>{formatDate(e.detected_at)}</td><td>{e.stock_code || "-"}</td><td>{e.stock_name || "-"}</td><td>{e.market_type || "-"}</td><td className="text-right">{fmtPct(e.change_rate)}</td>
                        <td className="align-top">
                          <div className="min-w-[260px]">
                            <div className="flex gap-1 items-center">
                              <select className="input-control flex-1" value={draft.selected_theme_id} onChange={(ev) => setEventDrafts((prev) => ({ ...prev, [e.event_id]: { ...(prev[e.event_id] ?? draft), selected_theme_id: ev.target.value } }))}>
                                <option value="">테마 선택</option>
                                {marketThemes.map((t) => <option key={t.id} value={t.id}>{t.theme_name}</option>)}
                              </select>
                              <button type="button" className="btn btn-secondary whitespace-nowrap" onClick={() => void addThemeLink(e.event_id)}>테마 추가</button>
                            </div>
                            {links.length > 0 ? (
                              <div className="flex flex-wrap gap-1 mt-1">
                                {links.map((l) => <button key={l.link_id} type="button" className="btn btn-secondary" onClick={() => void removeThemeLink(e.event_id, l.link_id)} title="테마 연결 해제">{l.theme_name} ×</button>)}
                              </div>
                            ) : null}
                          </div>
                        </td>
                        <td className="align-top"><input className="input-control min-w-[220px]" value={draft.user_memo} onChange={(ev) => setEventDrafts((prev) => ({ ...prev, [e.event_id]: { ...(prev[e.event_id] ?? draft), user_memo: ev.target.value } }))} placeholder="메모" /></td>
                        <td className="align-top"><div className="flex gap-1"><button type="button" className="btn btn-secondary whitespace-nowrap" onClick={() => void saveEventNote(e.event_id)}>메모 저장</button><button type="button" className="btn btn-danger" onClick={() => void deleteEvent(e.event_id)}>삭제</button></div></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
      ) : null}

      {activeTab === "flow" ? (
        <div className="space-y-4">
          <SectionCard title="일별 테마 수급 흐름">
            <div className="flex gap-2 items-end mb-3 flex-wrap">
              <input className="input-control" style={{ width: "160px", minWidth: "160px" }} type="date" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} />
              <button type="button" className="btn btn-primary" onClick={() => void loadFlow()}>조회</button>
            </div>

            {flowLoading ? <p className="text-sm text-muted">테마 요약을 조회 중입니다.</p> : null}
            {!flowLoading && flowSummaries.length === 0 ? <p className="text-sm text-muted">해당일에 테마가 연결된 수급 이벤트 후보가 없습니다.</p> : null}

            {flowSummaries.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {flowSummaries.map((item) => {
                  const selected = selectedFlowTheme?.id === item.market_theme_id;
                  return (
                    <button
                      key={item.market_theme_id}
                      type="button"
                      className={`text-left rounded-lg border p-3 transition ${selected ? "border-blue-500 bg-blue-50" : "border-slate-200 hover:border-slate-300"}`}
                      onClick={() => void loadFlowStocks(item)}
                    >
                      <div className="font-semibold text-slate-900">{item.theme_name}</div>
                      <div className="text-xs text-muted mt-1">연결 종목 {item.stock_count} · 이벤트 {item.event_count}</div>
                      <div className="text-xs text-muted">평균 등락률 {fmtPct(item.avg_change_rate)} · 최고 {fmtPct(item.max_change_rate)}</div>
                      <div className="text-xs text-muted">거래대금(추정) 합계 {fmtEokShort(item.estimated_trading_value_sum)}</div>
                      <div className="text-xs text-muted truncate mt-1">대표 종목: {item.representative_stocks.length > 0 ? item.representative_stocks.join(", ") : "-"}</div>
                    </button>
                  );
                })}
              </div>
            ) : null}
          </SectionCard>

          <SectionCard title="선택 테마 상세 종목">
            {selectedFlowTheme ? <p className="text-sm text-muted mb-2">선택 테마: {selectedFlowTheme.name}</p> : null}
            {flowStocksLoading ? <p className="text-sm text-muted">상세 종목을 조회 중입니다.</p> : null}
            {!flowStocksLoading && selectedFlowTheme && flowStocks.length === 0 ? <p className="text-sm text-muted">선택한 테마에 연결된 종목이 없습니다.</p> : null}

            {flowStocks.length > 0 ? (
              <div className="table-shell overflow-auto">
                <table className="data-table compact-table min-w-[1320px]">
                  <thead>
                    <tr><th>테마명</th><th>종목명</th><th>1주일</th><th>3개월</th><th>1년</th></tr>
                  </thead>
                  <tbody>
                    {flowStocks.map((row) => {
                      const weekUrl = getNaverChartImageUrl(row.stock_code, "week", chartSidcode);
                      const month3Url = getNaverChartImageUrl(row.stock_code, "month3", chartSidcode);
                      const yearUrl = getNaverChartImageUrl(row.stock_code, "year", chartSidcode);

                      const chartCell = (url: string, key: string) => (
                        <div className="w-[280px]">
                          {brokenCharts[key] ? (
                            <div className="h-[120px] w-[280px] border rounded flex items-center justify-center text-xs text-muted">차트 이미지 없음</div>
                          ) : (
                            <button type="button" className="block" onClick={() => setZoomedChart({ url, alt: `차트-${row.stock_code}` })}>
                              <img
                                src={url}
                                alt={`차트-${row.stock_code}`}
                                loading="lazy"
                                className="h-auto w-[280px] border rounded"
                                onError={() => onChartError(key)}
                              />
                            </button>
                          )}
                        </div>
                      );

                      return (
                        <tr key={`${row.market_theme_id}-${row.stock_code}`}>
                          <td>{row.theme_name}</td>
                          <td>
                            <div>{row.stock_name}</div>
                            <div className="text-xs text-muted">{row.stock_code}</div>
                          </td>
                          <td>{chartCell(weekUrl, `${row.stock_code}-week`)}</td>
                          <td>{chartCell(month3Url, `${row.stock_code}-month3`)}</td>
                          <td>{chartCell(yearUrl, `${row.stock_code}-year`)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </SectionCard>
        </div>
      ) : null}

      {zoomedChart ? (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" onClick={() => setZoomedChart(null)}>
          <img
            src={zoomedChart.url}
            alt={zoomedChart.alt}
            className="h-auto w-[700px] max-w-[95vw] rounded border border-white/30"
            onClick={(e) => {
              e.stopPropagation();
              setZoomedChart(null);
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

export default MarketTrendsPage;
