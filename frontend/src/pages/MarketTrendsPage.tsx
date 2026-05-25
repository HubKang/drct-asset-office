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
  MonthlyThemeFlowCalendarDay,
  MonthlyThemeFlowTrendTheme,
} from "@/types/marketTrend";

type ActiveTab = "kiwoom" | "flow" | "monthly";
type SortOrder = "asc" | "desc";
type ConditionSortKey = "condition_seq" | "condition_name";
type ResultSortKey = "stock_code" | "stock_name" | "current_price" | "change_rate" | "volume" | "estimated_trading_value";

const fmtNumber = (value: number | null | undefined) => (value == null ? "-" : value.toLocaleString("ko-KR"));
const fmtPct = (value: number | null | undefined) => (value == null ? "-" : `${value.toFixed(2)}%`);
const fmtEokShort = (value: number | null | undefined) => (value == null ? "-" : `${(value / 100000000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`);
const fmtEok2 = (value: number | null | undefined) => (value == null ? "-" : (value / 100000000).toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const toErr = (e: unknown, fallback: string) => {
  if (e instanceof Error) {
    const msg = e.message || "";
    if (msg.toLowerCase().includes("failed to fetch")) {
      return "백엔드 API 서버 연결에 실패했습니다. 백엔드 실행 상태와 VITE_API_BASE_URL 설정을 확인해 주세요.";
    }
    return msg || fallback;
  }
  return fallback;
};

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
const getMonthInput = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
const toMonthDateLabel = (value: string) => value.slice(5);
const colorPalette = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0f766e", "#be123c", "#334155", "#0891b2", "#84cc16"];

const buildCalendarCells = (month: string, days: MonthlyThemeFlowCalendarDay[]) => {
  const [y, m] = month.split("-").map(Number);
  const first = new Date(y, m - 1, 1);
  const last = new Date(y, m, 0);
  const offset = first.getDay();
  const cells: Array<{ date: string | null; day: MonthlyThemeFlowCalendarDay | null }> = [];
  for (let i = 0; i < offset; i += 1) cells.push({ date: null, day: null });
  const map = Object.fromEntries(days.map((d) => [d.trade_date, d] as const));
  for (let d = 1; d <= last.getDate(); d += 1) {
    const key = `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    cells.push({ date: key, day: map[key] ?? null });
  }
  while (cells.length % 7 !== 0) cells.push({ date: null, day: null });
  return cells;
};

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
  const [conditionsRefreshing, setConditionsRefreshing] = useState(false);

  const [conditionSort, setConditionSort] = useState<{ key: ConditionSortKey; order: SortOrder }>({ key: "condition_seq", order: "asc" });
  const [resultSort, setResultSort] = useState<{ key: ResultSortKey; order: SortOrder }>({ key: "change_rate", order: "desc" });

  const [flowSummaries, setFlowSummaries] = useState<DailyThemeFlowSummary[]>([]);
  const [flowStocks, setFlowStocks] = useState<DailyThemeFlowStock[]>([]);
  const [selectedFlowTheme, setSelectedFlowTheme] = useState<{ id: number; name: string } | null>(null);
  const [flowLoading, setFlowLoading] = useState(false);
  const [flowStocksLoading, setFlowStocksLoading] = useState(false);
  const [rankEditMode, setRankEditMode] = useState(false);
  const [rankDraftMap, setRankDraftMap] = useState<Record<number, string>>({});
  const [chartSidcode, setChartSidcode] = useState<number>(Date.now());
  const [brokenCharts, setBrokenCharts] = useState<Record<string, boolean>>({});
  const [zoomedChart, setZoomedChart] = useState<{ url: string; alt: string } | null>(null);
  const [monthlyBaseMonth, setMonthlyBaseMonth] = useState<string>(getMonthInput());
  const [monthlyCalendarDays, setMonthlyCalendarDays] = useState<MonthlyThemeFlowCalendarDay[]>([]);
  const [monthlyTrendThemes, setMonthlyTrendThemes] = useState<MonthlyThemeFlowTrendTheme[]>([]);
  const [monthlyStartDate, setMonthlyStartDate] = useState<string>("");
  const [monthlyEndDate, setMonthlyEndDate] = useState<string>("");
  const [selectedMonthlyDate, setSelectedMonthlyDate] = useState<string>("");
  const [monthlyLoading, setMonthlyLoading] = useState<boolean>(false);

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
      const fresh = Array.isArray(res.items) ? [...res.items] : [];
      setConditions(fresh);
      if (fresh.length === 0) {
        setSelectedConditionSeq("");
        setSelectedConditionName("");
        return;
      }
      const keep = fresh.find((x) => x.condition_seq === selectedConditionSeq);
      if (keep) {
        setSelectedConditionName(keep.condition_name);
        return;
      }
      setSelectedConditionSeq(fresh[0].condition_seq);
      setSelectedConditionName(fresh[0].condition_name);
    } catch (e) {
      setError(toErr(e, "조건검색 목록을 불러오지 못했습니다."));
    }
  };

  const refreshConditions = async () => {
    setError("");
    setMessage("");
    setConditionsRefreshing(true);
    try {
      const sync = await repositories.marketTrends.refreshKiwoomConditions();
      await loadConditions();
      if (!sync.success || sync.condition_count <= 0) {
        setError(
          sync.message || "조건검색 목록 응답은 받았지만 조건식 목록을 파싱하지 못했습니다.",
        );
        return;
      }
      setMessage(
        `조건검색 목록 갱신 완료: condition_count ${sync.condition_count}, inserted ${sync.inserted}, updated ${sync.updated}, total ${sync.total}`,
      );
    } catch (e) {
      setError(toErr(e, "조건검색 목록 새로고침에 실패했습니다. Kiwoom REST 토큰/연결 상태를 확인해 주세요."));
    } finally {
      setConditionsRefreshing(false);
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
      if (res.parsing_error) {
        setMessage("");
        setError("조건검색 응답은 수신했지만 결과 종목을 해석하지 못했습니다.");
      } else if ((res.item_count ?? 0) === 0) setMessage("현재 조건검색 결과가 없습니다.");
      else setMessage(`조건검색 결과 ${res.item_count}건을 조회했습니다. 저장할 종목을 선택하세요.`);
    } catch (e) {
      setMessage("");
      setError(toErr(e, "조건검색 결과 조회에 실패했습니다. Kiwoom REST 연결 상태를 확인해 주세요."));
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
      const items = res.items ?? [];
      setFlowSummaries(items);
      setRankDraftMap(
        Object.fromEntries(items.map((x) => [x.market_theme_id, x.manual_rank != null ? String(x.manual_rank) : ""])),
      );
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

  const loadMonthlyFlow = async () => {
    if (!monthlyBaseMonth) {
      setError("기준월(YYYY-MM)을 선택해 주세요.");
      return;
    }
    setError("");
    setMessage("");
    setMonthlyLoading(true);
    try {
      const [calendarRes, trendRes] = await Promise.all([
        repositories.marketTrends.getExternalMonthlyThemeFlowCalendar(monthlyBaseMonth),
        repositories.marketTrends.getExternalMonthlyThemeFlowTrend(monthlyBaseMonth),
      ]);
      setMonthlyCalendarDays(calendarRes.days ?? []);
      setMonthlyTrendThemes(trendRes.themes ?? []);
      setMonthlyStartDate(calendarRes.start_date);
      setMonthlyEndDate(calendarRes.end_date);
      setSelectedMonthlyDate(calendarRes.end_date);
    } catch (e) {
      setMonthlyCalendarDays([]);
      setMonthlyTrendThemes([]);
      setError(toErr(e, "월별 테마 수급 흐름 조회에 실패했습니다."));
    } finally {
      setMonthlyLoading(false);
    }
  };

  const saveDailyRanks = async () => {
    if (flowSummaries.length === 0) return;
    const used = new Set<number>();
    for (const item of flowSummaries) {
      const raw = rankDraftMap[item.market_theme_id];
      if (!raw) continue;
      const n = Number(raw);
      if (!Number.isInteger(n) || n <= 0) {
        setError("순위는 1 이상의 정수만 입력할 수 있습니다.");
        return;
      }
      if (used.has(n)) {
        setError("수동 순위가 중복되었습니다. 각 테마 순위를 다르게 지정해 주세요.");
        return;
      }
      used.add(n);
    }
    setError("");
    try {
      const res = await repositories.marketTrends.updateDailyThemeRanks({
        trade_date: tradeDate,
        items: flowSummaries.map((x) => ({
          market_theme_id: x.market_theme_id,
          manual_rank: rankDraftMap[x.market_theme_id] ? Number(rankDraftMap[x.market_theme_id]) : null,
        })),
      });
      setFlowSummaries(res.items ?? []);
      setMessage(`일별 테마 순위를 저장했습니다. (${res.updated_count}건)`);
      setRankEditMode(false);
    } catch (e) {
      setError(toErr(e, "일별 테마 순위 저장에 실패했습니다."));
    }
  };

  const resetDailyRanks = async () => {
    if (flowSummaries.length === 0) return;
    setError("");
    try {
      const res = await repositories.marketTrends.updateDailyThemeRanks({
        trade_date: tradeDate,
        items: flowSummaries.map((x) => ({ market_theme_id: x.market_theme_id, manual_rank: null })),
      });
      setFlowSummaries(res.items ?? []);
      setRankDraftMap(Object.fromEntries((res.items ?? []).map((x) => [x.market_theme_id, ""])));
      setMessage("수동 순위를 초기화했습니다. 자동 순위(평균등락률 기준)로 복원되었습니다.");
      setRankEditMode(false);
    } catch (e) {
      setError(toErr(e, "수동 순위 초기화에 실패했습니다."));
    }
  };

  useEffect(() => {
    void loadConditions();
    void loadMarketThemes();
    void loadEvents();
  }, []);

  useEffect(() => {
    if (activeTab === "monthly" && monthlyCalendarDays.length === 0 && !monthlyLoading) {
      void loadMonthlyFlow();
    }
  }, [activeTab]);

  const monthlyCells = useMemo(() => buildCalendarCells(monthlyBaseMonth, monthlyCalendarDays), [monthlyBaseMonth, monthlyCalendarDays]);
  const monthlyTopThemes = useMemo(() => monthlyTrendThemes.slice(0, 5), [monthlyTrendThemes]);
  const todayDate = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const monthlyLineData = useMemo(() => {
    if (monthlyTopThemes.length === 0) return [];
    const labels = monthlyTopThemes[0].series.map((p) => p.trade_date);
    return labels.map((dateValue, idx) => {
      const row: Record<string, unknown> = { trade_date: dateValue, label: toMonthDateLabel(dateValue) };
      for (const theme of monthlyTopThemes) {
        const point = theme.series[idx];
        row[`v_${theme.market_theme_id}`] = point?.value ?? 0;
        row[`meta_${theme.market_theme_id}`] = point ?? null;
      }
      return row;
    });
  }, [monthlyTopThemes]);

  return (
    <div className="space-y-4">
      <PageHeader title="시장 트랜드 분석" description="조건검색 결과를 수급 이벤트 후보로 저장하고 분석 우선순위를 관리합니다." />
      {message ? <div className="inline-result">{message}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}

      <SectionCard title="">
        <div className="border-b border-slate-200">
          <nav className="flex flex-wrap items-center gap-6">
            <button
              type="button"
              className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                activeTab === "kiwoom"
                  ? "border-slate-900 font-semibold text-slate-900"
                  : "border-transparent font-medium text-slate-500 hover:text-slate-900"
              }`}
              onClick={() => setActiveTab("kiwoom")}
            >
              키움 조건검색 수급 이벤트
            </button>
            <button
              type="button"
              className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                activeTab === "flow"
                  ? "border-slate-900 font-semibold text-slate-900"
                  : "border-transparent font-medium text-slate-500 hover:text-slate-900"
              }`}
              onClick={() => setActiveTab("flow")}
            >
              일별 테마 수급 흐름
            </button>
            <button
              type="button"
              className={`border-b-2 bg-transparent pb-3 text-sm transition-colors duration-150 ${
                activeTab === "monthly"
                  ? "border-slate-900 font-semibold text-slate-900"
                  : "border-transparent font-medium text-slate-500 hover:text-slate-900"
              }`}
              onClick={() => setActiveTab("monthly")}
            >
              월별 테마 수급 흐름
            </button>
          </nav>
        </div>
      </SectionCard>

      {activeTab === "kiwoom" ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 xl:grid-cols-[380px_1fr] gap-4">
            <SectionCard title="키움 조건검색 목록">
              <div className="flex gap-2 mb-2">
                <button type="button" className="btn btn-secondary" onClick={() => void refreshConditions()} disabled={conditionsRefreshing}>
                  {conditionsRefreshing ? "새로고침 중..." : "조건검색 목록 새로고침"}
                </button>
              </div>
              <p className="text-xs text-muted mb-2">조건검색 목록은 Kiwoom REST API에서 직접 조회하며, 새로고침 시 최신 조건식 목록을 반영합니다.</p>
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
              <button type="button" className="btn btn-secondary" onClick={() => setRankEditMode((p) => !p)}>{rankEditMode ? "편집 취소" : "순위 편집"}</button>
              {rankEditMode ? <button type="button" className="btn btn-primary" onClick={() => void saveDailyRanks()}>순위 저장</button> : null}
              {rankEditMode ? <button type="button" className="btn btn-secondary" onClick={() => void resetDailyRanks()}>수동 순위 초기화</button> : null}
            </div>
            <p className="text-xs text-muted mb-2">자동 순위는 평균등락률 기준이며, 필요 시 사용자가 해당일의 체감 1위 테마를 직접 지정할 수 있습니다.</p>

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
                      <div className="font-semibold text-slate-900">{item.final_rank ?? "-"}위 · {item.theme_name}</div>
                      <div className="text-xs text-muted mt-1">순위 기준: {item.rank_basis === "manual" ? "수동" : "자동"} · 점수 {item.rank_score}</div>
                      <div className="text-xs text-muted mt-1">연결 종목 {item.stock_count} · 이벤트 {item.event_count}</div>
                      <div className="text-xs text-muted">평균 등락률 {fmtPct(item.avg_change_rate)} · 최고 {fmtPct(item.max_change_rate)}</div>
                      <div className="text-xs text-muted">거래대금(추정) 합계 {fmtEokShort(item.estimated_trading_value_sum)}</div>
                      <div className="text-xs text-muted truncate mt-1">대표 종목: {item.representative_stocks.length > 0 ? item.representative_stocks.join(", ") : "-"}</div>
                      {rankEditMode ? (
                        <div className="mt-2">
                          <label className="text-xs text-slate-600 mr-1">수동 순위</label>
                          <select
                            className="input-control"
                            value={rankDraftMap[item.market_theme_id] ?? ""}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => setRankDraftMap((prev) => ({ ...prev, [item.market_theme_id]: e.target.value }))}
                          >
                            <option value="">자동</option>
                            {flowSummaries.map((_, i) => <option key={i + 1} value={String(i + 1)}>{i + 1}위</option>)}
                          </select>
                        </div>
                      ) : null}
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

      {activeTab === "monthly" ? (
        <div className="space-y-4">
          <SectionCard title="월별 테마 수급 흐름">
            <p className="text-sm text-muted mb-2">저장된 수급 이벤트 후보와 테마 연결 기록을 기준으로 월간 테마 흐름을 표시합니다.</p>
            <div className="flex gap-2 items-end mb-3 flex-wrap">
              <input className="input-control" style={{ width: "140px", minWidth: "140px" }} type="month" value={monthlyBaseMonth} onChange={(e) => setMonthlyBaseMonth(e.target.value)} />
              <button type="button" className="btn btn-primary" onClick={() => void loadMonthlyFlow()}>조회</button>
              {monthlyStartDate && monthlyEndDate ? <span className="text-xs text-muted">조회 구간: {monthlyStartDate} ~ {monthlyEndDate}</span> : null}
            </div>

            {monthlyLoading ? <p className="text-sm text-muted">월별 테마 수급 흐름을 조회 중입니다.</p> : null}
            {!monthlyLoading && monthlyCalendarDays.length === 0 ? <p className="text-sm text-muted">해당 월에 연결된 테마 수급 이벤트가 없습니다.</p> : null}

            {monthlyCalendarDays.length > 0 ? (
              <div className="border rounded-lg p-3">
                <div className="grid grid-cols-7 gap-2 mb-2 text-xs font-medium text-slate-600">
                  {["일", "월", "화", "수", "목", "금", "토"].map((w) => <div key={w}>{w}</div>)}
                </div>
                <div className="grid grid-cols-7 gap-2">
                  {monthlyCells.map((cell, idx) => {
                    const isToday = cell.date === todayDate;
                    const isSelected = cell.date && selectedMonthlyDate === cell.date;
                    return (
                      <button
                        key={`${cell.date ?? "blank"}-${idx}`}
                        type="button"
                        disabled={!cell.date}
                        onClick={() => cell.date && setSelectedMonthlyDate(cell.date)}
                        className={`min-h-[110px] rounded border p-2 text-left ${!cell.date ? "bg-slate-50 border-slate-100 cursor-default" : isSelected ? "border-blue-500 bg-blue-50" : "border-slate-200"} ${isToday ? "ring-1 ring-blue-300" : ""}`}
                      >
                        <div className="text-xs font-semibold mb-1">{cell.date ? Number(cell.date.slice(8, 10)) : ""}</div>
                        {cell.day?.themes?.slice(0, 3).map((theme) => (
                          <div key={`${cell.date}-${theme.market_theme_id}`} className="text-[11px] text-slate-700 truncate">
                            {theme.final_rank ?? theme.rank} {theme.theme_name} · +{theme.rank_score}점 · {theme.stock_count}종목 {theme.rank_basis === "manual" ? "· 수동" : ""}
                          </div>
                        ))}
                        {cell.date && (!cell.day || cell.day.themes.length === 0) ? <div className="text-[11px] text-slate-400">-</div> : null}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </SectionCard>

          <SectionCard title="월간 테마 흐름 라인 그래프 (순위 가중 누적 점수)">
            <p className="text-xs text-muted mb-3">일별 테마 순위에 가중치를 부여해 월초부터 누적한 값입니다. 반복적으로 상위권에 등장한 테마일수록 상승합니다.</p>
            {monthlyLineData.length === 0 ? <p className="text-sm text-muted">해당 월에 연결된 테마 수급 이벤트가 없습니다.</p> : null}
            {monthlyLineData.length > 0 ? (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-3 text-xs">
                  {monthlyTopThemes.map((t, idx) => <span key={t.market_theme_id} style={{ color: colorPalette[idx % colorPalette.length] }}>● {t.theme_name}</span>)}
                </div>
                <div className="overflow-x-auto border rounded-lg p-2 bg-white">
                  {(() => {
                    const width = Math.max(760, monthlyLineData.length * 28);
                    const height = 280;
                    const padL = 40;
                    const padR = 10;
                    const padT = 10;
                    const padB = 30;
                    const plotW = width - padL - padR;
                    const plotH = height - padT - padB;
                    const maxY = Math.max(1, ...monthlyTopThemes.flatMap((t) => t.series.map((p) => p.value)));
                    const xOf = (i: number) => padL + ((monthlyLineData.length <= 1 ? 0 : i / (monthlyLineData.length - 1)) * plotW);
                    const yOf = (v: number) => padT + ((maxY - v) / maxY) * plotH;
                    return (
                      <svg width={width} height={height} role="img" aria-label="월간 테마 흐름 그래프">
                        <line x1={padL} y1={padT} x2={padL} y2={padT + plotH} stroke="#cbd5e1" />
                        <line x1={padL} y1={padT + plotH} x2={padL + plotW} y2={padT + plotH} stroke="#cbd5e1" />
                        {[0, 0.25, 0.5, 0.75, 1].map((r) => {
                          const y = padT + plotH * r;
                          const label = Math.round(maxY * (1 - r));
                          return (
                            <g key={r}>
                              <line x1={padL} y1={y} x2={padL + plotW} y2={y} stroke="#f1f5f9" />
                              <text x={padL - 6} y={y + 4} textAnchor="end" fontSize="10" fill="#64748b">{label}</text>
                            </g>
                          );
                        })}
                        {monthlyTopThemes.map((theme, idx) => {
                          const points = theme.series.map((p, i) => `${xOf(i)},${yOf(p.value)}`).join(" ");
                          return (
                            <g key={theme.market_theme_id}>
                              <polyline fill="none" stroke={colorPalette[idx % colorPalette.length]} strokeWidth="2" points={points} />
                              {theme.series.map((p, i) => (
                                <circle key={`${theme.market_theme_id}-${p.trade_date}`} cx={xOf(i)} cy={yOf(p.value)} r="2.5" fill={colorPalette[idx % colorPalette.length]}>
                                  <title>{`${p.trade_date} | ${theme.theme_name} | 누적 ${p.value} | 당일 ${p.daily_score} | 순위 ${p.final_rank ?? "-"} | ${p.rank_basis === "manual" ? "수동" : "자동"} | 평균등락률 ${p.avg_change_rate ?? "-"} | 종목수 ${p.stock_count}`}</title>
                                </circle>
                              ))}
                            </g>
                          );
                        })}
                        {monthlyLineData.map((d, i) => {
                          if (i % Math.ceil(monthlyLineData.length / 8) !== 0 && i !== monthlyLineData.length - 1) return null;
                          return (
                            <text key={String(d.trade_date)} x={xOf(i)} y={height - 8} textAnchor="middle" fontSize="10" fill="#64748b">
                              {String(d.label)}
                            </text>
                          );
                        })}
                      </svg>
                    );
                  })()}
                </div>
                <div className="table-shell overflow-auto">
                  <table className="data-table compact-table">
                    <thead>
                      <tr><th>날짜</th><th>일별 테마 순위 (상위 3)</th></tr>
                    </thead>
                    <tbody>
                      {monthlyCalendarDays.filter((d) => d.themes.length > 0 && (!selectedMonthlyDate || d.trade_date === selectedMonthlyDate)).map((d) => (
                        <tr key={d.trade_date}>
                          <td>{d.trade_date}</td>
                          <td>{d.themes.slice(0, 3).map((t) => `${t.final_rank ?? t.rank}. ${t.theme_name} (+${t.rank_score}점, ${t.stock_count}종목, ${t.rank_basis === "manual" ? "수동" : "자동"})`).join(" / ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
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
