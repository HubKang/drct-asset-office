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
import type { Stock } from "@/types/stock";

type ActiveTab = "kiwoom" | "flow" | "monthly";
type SortOrder = "asc" | "desc";
type ConditionOrderMode = "number" | "name";
type ResultSortKey = "stock_code" | "stock_name" | "current_price" | "change_rate" | "volume" | "estimated_trading_value";
type ManualCandidateForm = {
  trade_date: string;
  change_rate: string;
  trading_value: string;
  volume: string;
  theme_id: string;
  memo: string;
};

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

const getNaverMarketChartImageUrl = (market: "KOSPI" | "KOSDAQ", sidcode: number) =>
  `https://ssl.pstatic.net/imgstock/chart3/day90/${market}.png?sidcode=${sidcode}`;

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
const shiftDate = (dateText: string, diffDays: number) => {
  const d = new Date(dateText);
  if (Number.isNaN(d.getTime())) return dateText;
  d.setDate(d.getDate() + diffDays);
  return d.toISOString().slice(0, 10);
};

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
  const [resultPanelStatus, setResultPanelStatus] = useState("");
  const [conditionsRefreshing, setConditionsRefreshing] = useState(false);

  const [conditionOrderMode, setConditionOrderMode] = useState<ConditionOrderMode>("number");
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
  const [eventNameSortOrder, setEventNameSortOrder] = useState<SortOrder>("asc");
  const [manualModalOpen, setManualModalOpen] = useState(false);
  const [manualStockKeyword, setManualStockKeyword] = useState("");
  const [manualStockResults, setManualStockResults] = useState<Stock[]>([]);
  const [manualSelectedStock, setManualSelectedStock] = useState<Stock | null>(null);
  const [manualStockLoading, setManualStockLoading] = useState(false);
  const [manualSaving, setManualSaving] = useState(false);
  const [manualForm, setManualForm] = useState<ManualCandidateForm>({
    trade_date: tradeDate,
    change_rate: "",
    trading_value: "",
    volume: "",
    theme_id: "",
    memo: "",
  });

  const toggleSort = <T extends string,>(prev: { key: T; order: SortOrder }, key: T): { key: T; order: SortOrder } => {
    if (prev.key === key) {
      return { key, order: prev.order === "asc" ? "desc" : "asc" };
    }
    return { key, order: "asc" };
  };

  const sortedConditions = useMemo(() => {
    const arr = [...conditions];
    arr.sort((a, b) => {
      if (conditionOrderMode === "name") {
        return a.condition_name.localeCompare(b.condition_name, "ko");
      }
      const aNum = Number(a.condition_seq);
      const bNum = Number(b.condition_seq);
      const aNumOk = Number.isFinite(aNum);
      const bNumOk = Number.isFinite(bNum);
      if (aNumOk && bNumOk) return aNum - bNum;
      return a.condition_seq.localeCompare(b.condition_seq, "ko");
    });
    return arr;
  }, [conditions, conditionOrderMode]);

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
  const allResultChecked = useMemo(
    () => sortedResults.length > 0 && sortedResults.every((r) => Boolean(checkedMap[getResultRowKey(r)])),
    [sortedResults, checkedMap],
  );
  const sortedEvents = useMemo(() => {
    const arr = [...events];
    arr.sort((a, b) => {
      const cmp = (a.stock_name || "").localeCompare(b.stock_name || "", "ko");
      return eventNameSortOrder === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [events, eventNameSortOrder]);
  const flowSummaryStats = useMemo(() => {
    const top = flowSummaries[0];
    const maxChange = flowSummaries.reduce((max, item) => {
      const value = item.max_change_rate ?? Number.NEGATIVE_INFINITY;
      return value > max ? value : max;
    }, Number.NEGATIVE_INFINITY);
    return {
      savedCandidates: flowSummaries.reduce((sum, item) => sum + (item.event_count ?? 0), 0),
      themeCount: flowSummaries.length,
      topTheme: top?.theme_name ?? "없음",
      maxChangeRate: Number.isFinite(maxChange) ? maxChange : null,
      unclassified: "-",
    };
  }, [flowSummaries]);
  const selectedThemeMeta = useMemo(() => {
    if (!selectedFlowTheme) return null;
    const summary = flowSummaries.find((x) => x.market_theme_id === selectedFlowTheme.id);
    const stockCount = flowStocks.length;
    const rep = summary?.representative_stocks?.[0] ?? "-";
    return { stockCount, representative: rep };
  }, [selectedFlowTheme, flowSummaries, flowStocks]);
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
    setResultPanelStatus("조건검색 결과 조회 중...");
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
        setResultPanelStatus("");
        setError("조건검색 응답은 수신했지만 결과 종목을 해석하지 못했습니다.");
      } else if ((res.item_count ?? 0) === 0) setResultPanelStatus("조회 결과 0건 · 선택 0건");
      else setResultPanelStatus(`조회 결과 ${res.item_count}건 · 선택 0건`);
    } catch (e) {
      setResultPanelStatus("");
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
        detected_date: tradeDate,
        source: "kiwoom_rest",
        items: selectedItems,
      });
      setMessage("수급 이벤트 후보로 저장되었습니다.");
      await loadEvents();
    } catch (e) {
      setError(toErr(e, "수급 이벤트 후보 저장에 실패했습니다."));
    }
  };

  const loadEvents = async (targetDate?: string) => {
    setError("");
    try {
      const baseDate = targetDate || tradeDate;
      const res = await repositories.marketTrends.getKiwoomMarketEvents(baseDate, 200);
      const fetchedEvents = [...(res.items ?? [])];
      setEvents(fetchedEvents);
      const draftMap: Record<number, { theme_status: string; user_memo: string; selected_theme_id: string }> = {};
      for (const item of fetchedEvents) {
        draftMap[item.event_id] = {
          theme_status: item.theme_status || "unassigned",
          user_memo: item.user_memo || "",
          selected_theme_id: "",
        };
      }
      setEventDrafts(draftMap);

      const linkEntries = await Promise.all(
        fetchedEvents.map(async (item) => {
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

  const openManualCandidateModal = () => {
    setManualModalOpen(true);
    setManualStockKeyword("");
    setManualStockResults([]);
    setManualSelectedStock(null);
    setManualForm({
      trade_date: tradeDate,
      change_rate: "",
      trading_value: "",
      volume: "",
      theme_id: "",
      memo: "",
    });
  };

  const searchManualCandidateStocks = async () => {
    const keyword = manualStockKeyword.trim();
    if (!keyword) {
      setError("종목명 또는 종목코드를 입력해 주세요.");
      return;
    }
    setError("");
    setManualStockLoading(true);
    try {
      const rows = await repositories.stocks.list({ keyword, is_active: 1, limit: 20, offset: 0 });
      setManualStockResults(rows);
      if (rows.length === 0) setError("검색 결과가 없습니다. 종목명 또는 종목코드를 다시 확인해 주세요.");
    } catch (e) {
      setError(toErr(e, "종목 검색에 실패했습니다."));
      setManualStockResults([]);
    } finally {
      setManualStockLoading(false);
    }
  };

  const saveManualCandidate = async () => {
    if (!manualSelectedStock) {
      setError("직접등록할 종목을 선택해 주세요.");
      return;
    }
    if (!manualForm.trade_date) {
      setError("감지일을 선택해 주세요.");
      return;
    }
    if (!manualForm.memo.trim()) {
      setError("직접등록 사유 또는 메모를 입력해 주세요.");
      return;
    }
    const toOptionalNumber = (value: string) => {
      const trimmed = value.trim();
      if (!trimmed) return null;
      const parsed = Number(trimmed);
      return Number.isFinite(parsed) ? parsed : Number.NaN;
    };
    const changeRate = toOptionalNumber(manualForm.change_rate);
    const tradingValue = toOptionalNumber(manualForm.trading_value);
    const volume = toOptionalNumber(manualForm.volume);
    if (Number.isNaN(changeRate) || Number.isNaN(tradingValue) || Number.isNaN(volume)) {
      setError("등락률, 거래대금, 거래량은 숫자로 입력해 주세요.");
      return;
    }
    setError("");
    setMessage("");
    setManualSaving(true);
    try {
      const res = await repositories.marketTrends.createManualSupplyEventCandidate({
        trade_date: manualForm.trade_date,
        stock_id: manualSelectedStock.id,
        stock_code: manualSelectedStock.stock_code,
        change_rate: changeRate,
        trading_value: tradingValue == null ? null : Math.round(tradingValue),
        volume: volume == null ? null : Math.round(volume),
        theme_id: manualForm.theme_id ? Number(manualForm.theme_id) : null,
        memo: manualForm.memo.trim(),
      });
      setMessage(res.message || "수급 이벤트 후보를 직접 등록했습니다.");
      setManualModalOpen(false);
      setTradeDate(manualForm.trade_date);
      await Promise.all([loadEvents(manualForm.trade_date), loadFlow(manualForm.trade_date)]);
    } catch (e) {
      setError(toErr(e, "수급 이벤트 후보 직접등록에 실패했습니다."));
    } finally {
      setManualSaving(false);
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

  const loadFlow = async (targetDate?: string) => {
    setError("");
    setMessage("");
    setFlowLoading(true);
    setSelectedFlowTheme(null);
    setFlowStocks([]);
    try {
      const baseDate = targetDate || tradeDate;
      const res = await repositories.marketTrends.getExternalDailyThemeFlow(baseDate);
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
  const applyFlowDate = async (nextDate: string) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(nextDate)) return;
    const parsed = new Date(nextDate);
    if (Number.isNaN(parsed.getTime())) return;
    setTradeDate(nextDate);
    await Promise.all([loadEvents(nextDate), loadFlow(nextDate)]);
  };

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

  useEffect(() => {
    if (activeTab === "kiwoom") {
      void loadEvents(tradeDate);
    }
  }, [tradeDate, activeTab]);

  const monthlyCells = useMemo(() => buildCalendarCells(monthlyBaseMonth, monthlyCalendarDays), [monthlyBaseMonth, monthlyCalendarDays]);
  const monthlyTopThemes = useMemo(() => monthlyTrendThemes.slice(0, 5), [monthlyTrendThemes]);
  const monthlyMaxDayScore = useMemo(
    () => Math.max(1, ...monthlyCalendarDays.map((d) => d.themes.reduce((sum, t) => sum + (t.rank_score ?? 0), 0))),
    [monthlyCalendarDays],
  );
  const selectedMonthlyDay = useMemo(
    () => monthlyCalendarDays.find((d) => d.trade_date === selectedMonthlyDate) ?? null,
    [monthlyCalendarDays, selectedMonthlyDate],
  );
  const monthlySummary = useMemo(() => {
    const uniqueThemes = new Set<number>();
    let totalEvents = 0;
    let maxScore = -1;
    let bestDate = "-";
    for (const day of monthlyCalendarDays) {
      let dayScore = 0;
      for (const theme of day.themes) {
        uniqueThemes.add(theme.market_theme_id);
        totalEvents += theme.stock_count ?? 0;
        dayScore += theme.rank_score ?? 0;
      }
      if (dayScore > maxScore) {
        maxScore = dayScore;
        bestDate = day.trade_date.slice(5);
      }
    }
    return {
      totalEvents,
      themeCount: uniqueThemes.size,
      topTheme: monthlyTopThemes[0]?.theme_name ?? "없음",
      bestDate,
      unclassified: "-",
    };
  }, [monthlyCalendarDays, monthlyTopThemes]);
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
      <PageHeader
        title="시장 트랜드 분석"
        description="조건검색 결과를 수급 이벤트 후보로 저장하고 분석 우선순위를 관리합니다."
        action={(
          <button
            type="button"
            className="btn btn-secondary"
            title="핀업 테마로그를 새 창으로 엽니다."
            onClick={() => {
              window.open(
                "https://finance.finup.co.kr/lab/themelog/popup?Fullscreen=true",
                "_blank",
                "noopener,noreferrer",
              );
            }}
          >
            핀업 테마 열기
          </button>
        )}
      />
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
            <SectionCard title="">
              <div className="watchlist-card-title-wrap">
                <h3 className="section-title m-0">키움 조건식 목록</h3>
                <span className="hint-icon" title="키움 REST API에서 조건검색식을 조회합니다. 새로고침 시 최신 조건식 목록을 다시 불러옵니다.">i</span>
              </div>
              <div className="flex gap-2 mb-2">
                <button type="button" className="btn btn-secondary" onClick={() => void refreshConditions()} disabled={conditionsRefreshing}>
                  {conditionsRefreshing ? "새로고침 중..." : "조건식 새로고침"}
                </button>
                <select
                  className="select-control market-trend-condition-order"
                  aria-label="조건식 정렬"
                  title="조건식 정렬"
                  value={conditionOrderMode}
                  onChange={(e) => setConditionOrderMode(e.target.value as ConditionOrderMode)}
                >
                  <option value="number">번호순</option>
                  <option value="name">조건식명순</option>
                </select>
              </div>
              <div className="market-trend-condition-list">
                {sortedConditions.map((c) => {
                  const selected = selectedConditionSeq === c.condition_seq;
                  return (
                    <button
                      key={c.id}
                      type="button"
                      className={`market-trend-condition-item ${selected ? "selected" : ""}`}
                      onClick={() => { setSelectedConditionSeq(c.condition_seq); setSelectedConditionName(c.condition_name); }}
                      title={c.condition_name}
                    >
                      <strong>[{c.condition_seq.padStart(2, "0")}]</strong>
                      <span>{c.condition_name}</span>
                    </button>
                  );
                })}
              </div>
            </SectionCard>

            <SectionCard title="">
              <div className="watchlist-card-title-wrap">
                <h3 className="section-title m-0">조건검색 결과</h3>
                <span className="hint-icon" title="선택한 조건식의 현재 검색 결과입니다. 체크한 종목만 수급 이벤트 후보로 저장됩니다.">i</span>
              </div>
              <div className="space-y-2 mb-3">
                <div className="text-sm text-muted">
                  {selectedConditionSeq
                    ? `${selectedConditionSeq} · ${selectedConditionName} · 조회 결과 ${sortedResults.length}건 · 선택 ${selectedItems.length}건`
                    : "조건식을 선택해 주세요."}
                </div>
                {resultPanelStatus ? <div className="text-xs text-muted">{resultPanelStatus}</div> : null}
                <div className="flex gap-2 flex-wrap">
                  <button type="button" className="btn btn-secondary" onClick={() => void loadConditionResults()} disabled={!selectedConditionSeq}>결과 조회</button>
                  <button type="button" className="btn btn-primary" onClick={() => void saveSelectedAsEvents()} disabled={selectedItems.length === 0}>선택 후보 저장</button>
                </div>
              </div>
              <div className="table-shell max-h-[420px] overflow-auto">
                <table className="data-table compact-table">
                  <thead>
                    <tr>
                      <th>
                        <label className="inline-flex items-center gap-1">
                          <input
                            type="checkbox"
                            checked={allResultChecked}
                            onChange={(e) => {
                              const next: Record<string, boolean> = {};
                              for (const row of sortedResults) next[getResultRowKey(row)] = e.target.checked;
                              setCheckedMap(next);
                            }}
                          />
                          <span>체크</span>
                        </label>
                      </th>
                      <th className="cursor-pointer" onClick={() => setResultSort((p) => toggleSort(p, "stock_name"))}>종목{sortMark(resultSort.key === "stock_name", resultSort.order)}</th>
                      <th className="cursor-pointer" style={{ textAlign: "right" }} onClick={() => setResultSort((p) => toggleSort(p, "current_price"))}>현재가{sortMark(resultSort.key === "current_price", resultSort.order)}</th>
                      <th className="cursor-pointer text-right" onClick={() => setResultSort((p) => toggleSort(p, "change_rate"))}>등락률{sortMark(resultSort.key === "change_rate", resultSort.order)}</th>
                      <th className="cursor-pointer" style={{ textAlign: "right" }} onClick={() => setResultSort((p) => toggleSort(p, "volume"))}>거래량{sortMark(resultSort.key === "volume", resultSort.order)}</th>
                      <th className="cursor-pointer" style={{ textAlign: "right" }} onClick={() => setResultSort((p) => toggleSort(p, "estimated_trading_value"))}>거래대금(억){sortMark(resultSort.key === "estimated_trading_value", resultSort.order)}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedResults.length === 0 ? (
                      <tr><td colSpan={6} className="text-center text-muted">조회 결과가 없습니다.</td></tr>
                    ) : null}
                    {sortedResults.map((r) => {
                      const key = getResultRowKey(r);
                      return (
                        <tr key={key}>
                          <td><input type="checkbox" checked={Boolean(checkedMap[key])} onChange={(e) => setCheckedMap((prev) => ({ ...prev, [key]: e.target.checked }))} /></td>
                          <td>
                            <div className="stock-cell">
                              <strong>{r.stock_name || "-"}</strong>
                              <span>{r.stock_code || "-"}</span>
                            </div>
                          </td>
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

          <SectionCard title="">
            <div className="watchlist-card-title-wrap">
              <h3 className="section-title m-0">저장된 수급 이벤트 후보</h3>
              <span className="hint-icon" title="저장된 후보는 일별·월별 테마 수급 흐름 분석의 기초 데이터로 활용됩니다.">i</span>
            </div>
            <div className="flex gap-2 items-end mb-2 flex-wrap">
              <input className="input-control" style={{ width: "160px", minWidth: "160px" }} type="date" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} />
              <button type="button" className="btn btn-secondary" onClick={() => void loadEvents()}>조회</button>
              <button type="button" className="btn btn-primary" onClick={openManualCandidateModal}>+ 후보 직접등록</button>
            </div>
            <div className="table-shell">
              <table className="data-table compact-table">
                <thead>
                  <tr>
                    <th>감지일</th><th className="cursor-pointer" onClick={() => setEventNameSortOrder((p) => (p === "asc" ? "desc" : "asc"))}>종목{sortMark(true, eventNameSortOrder)}</th><th>시장</th><th className="text-right">등락률</th><th>연결 테마</th><th>메모</th><th>관리</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedEvents.length === 0 ? (
                    <tr><td colSpan={7} className="text-center text-muted">저장된 후보가 없습니다.</td></tr>
                  ) : null}
                  {sortedEvents.map((e) => {
                    const draft = eventDrafts[e.event_id] ?? { theme_status: "unassigned", user_memo: "", selected_theme_id: "" };
                    const links = eventThemeLinksMap[e.event_id] ?? [];
                    return (
                      <tr key={e.event_id}>
                        <td>{formatDate(e.detected_at)}</td>
                        <td>
                          <div className="stock-cell">
                            <strong>{e.stock_name || "-"}</strong>
                            <span>{e.stock_code || "-"}</span>
                            {e.detection_source === "manual" ? <span className="manual-candidate-badge">직접등록</span> : null}
                          </div>
                        </td>
                        <td>{e.market_type || "-"}</td><td className="text-right">{fmtPct(e.change_rate)}</td>
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

      {manualModalOpen ? (
        <div className="modal-backdrop" onClick={() => setManualModalOpen(false)}>
          <div className="modal-card manual-candidate-modal" onClick={(e) => e.stopPropagation()}>
            <div className="trade-journal-detail-header">
              <h3>수급 이벤트 후보 직접등록</h3>
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setManualModalOpen(false)}>
                닫기
              </button>
            </div>
            <p className="text-sm text-muted mb-3">
              직접등록 후보는 관심종목 Pool에 추가하지 않고, 현재 수급 이벤트 후보 데이터에만 저장됩니다.
            </p>

            <div className="manual-candidate-grid">
              <label className="manual-candidate-field">
                <span>감지일</span>
                <input
                  className="input-control"
                  type="date"
                  value={manualForm.trade_date}
                  onChange={(e) => setManualForm((prev) => ({ ...prev, trade_date: e.target.value }))}
                />
              </label>
              <label className="manual-candidate-field">
                <span>테마 선택</span>
                <select
                  className="input-control"
                  value={manualForm.theme_id}
                  onChange={(e) => setManualForm((prev) => ({ ...prev, theme_id: e.target.value }))}
                >
                  <option value="">테마 미지정</option>
                  {marketThemes.map((theme) => (
                    <option key={theme.id} value={theme.id}>{theme.theme_name}</option>
                  ))}
                </select>
              </label>
            </div>

            <form
              className="manual-candidate-search"
              onSubmit={(e) => {
                e.preventDefault();
                void searchManualCandidateStocks();
              }}
            >
              <input
                className="input-control"
                placeholder="종목명 또는 종목코드 입력"
                value={manualStockKeyword}
                onChange={(e) => setManualStockKeyword(e.target.value)}
              />
              <button type="submit" className="btn btn-primary" disabled={manualStockLoading}>
                {manualStockLoading ? "검색 중..." : "검색"}
              </button>
            </form>

            {manualSelectedStock ? (
              <div className="manual-candidate-selected">
                <strong>{manualSelectedStock.stock_name}</strong>
                <span>{normalizeStockCode(manualSelectedStock.stock_code)} · {manualSelectedStock.market || "-"}</span>
              </div>
            ) : null}

            {manualStockResults.length > 0 ? (
              <div className="manual-candidate-stock-list">
                {manualStockResults.map((stock) => {
                  const selected = manualSelectedStock?.id === stock.id;
                  return (
                    <button
                      key={stock.id}
                      type="button"
                      className={`manual-candidate-stock-item ${selected ? "selected" : ""}`}
                      onClick={() => setManualSelectedStock(stock)}
                    >
                      <strong>{stock.stock_name}</strong>
                      <span>{normalizeStockCode(stock.stock_code)} · {stock.market || "-"}</span>
                    </button>
                  );
                })}
              </div>
            ) : null}

            <div className="manual-candidate-grid mt-3">
              <label className="manual-candidate-field">
                <span>등락률(%)</span>
                <input
                  className="input-control"
                  inputMode="decimal"
                  placeholder="예: 12.5"
                  value={manualForm.change_rate}
                  onChange={(e) => setManualForm((prev) => ({ ...prev, change_rate: e.target.value }))}
                />
              </label>
              <label className="manual-candidate-field">
                <span>거래대금(원)</span>
                <input
                  className="input-control"
                  inputMode="numeric"
                  placeholder="예: 50000000000"
                  value={manualForm.trading_value}
                  onChange={(e) => setManualForm((prev) => ({ ...prev, trading_value: e.target.value }))}
                />
              </label>
              <label className="manual-candidate-field">
                <span>거래량</span>
                <input
                  className="input-control"
                  inputMode="numeric"
                  placeholder="선택 입력"
                  value={manualForm.volume}
                  onChange={(e) => setManualForm((prev) => ({ ...prev, volume: e.target.value }))}
                />
              </label>
            </div>

            <label className="manual-candidate-field mt-3">
              <span>메모</span>
              <textarea
                className="input-control manual-candidate-memo"
                placeholder="직접등록 사유를 입력해 주세요."
                value={manualForm.memo}
                onChange={(e) => setManualForm((prev) => ({ ...prev, memo: e.target.value }))}
              />
            </label>

            <div className="manual-candidate-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setManualModalOpen(false)}>
                취소
              </button>
              <button type="button" className="btn btn-primary" disabled={manualSaving} onClick={() => void saveManualCandidate()}>
                {manualSaving ? "저장 중..." : "직접등록 저장"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {activeTab === "flow" ? (
        <div className="space-y-4">
          <SectionCard title="">
            <div className="watchlist-card-title-wrap">
              <h3 className="section-title m-0">일별 테마 수급 흐름</h3>
              <span className="hint-icon" title="선택한 날짜의 저장된 수급 이벤트 후보를 테마별로 집계합니다. 날짜를 선택하면 즉시 조회됩니다.">i</span>
            </div>
            <div className="flex gap-2 items-end mb-3 flex-wrap">
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void applyFlowDate(shiftDate(tradeDate, -1))}>◀</button>
              <input
                className="input-control"
                style={{ width: "160px", minWidth: "160px" }}
                type="date"
                value={tradeDate}
                onChange={(e) => void applyFlowDate(e.target.value)}
                onBlur={(e) => void applyFlowDate(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void applyFlowDate((e.target as HTMLInputElement).value);
                  }
                }}
              />
              <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void applyFlowDate(shiftDate(tradeDate, 1))}>▶</button>
              <button type="button" className="btn btn-secondary" onClick={() => void applyFlowDate(new Date().toISOString().slice(0, 10))}>오늘</button>
              <button type="button" className="btn btn-secondary" title="자동 순위와 다르게 체감 주도 테마를 직접 조정할 수 있습니다." onClick={() => setRankEditMode((p) => !p)}>{rankEditMode ? "편집 취소" : "순위 편집"}</button>
              {rankEditMode ? <button type="button" className="btn btn-primary" onClick={() => void saveDailyRanks()}>순위 저장</button> : null}
              {rankEditMode ? <button type="button" className="btn btn-secondary" onClick={() => void resetDailyRanks()}>수동 순위 초기화</button> : null}
            </div>

            <div className="watchlist-top-stats mb-3">
              <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">저장 후보</p><strong className="watchlist-top-stat-value">{flowSummaryStats.savedCandidates}건</strong></div>
              <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">등장 테마</p><strong className="watchlist-top-stat-value">{flowSummaryStats.themeCount}개</strong></div>
              <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">1위 테마</p><strong className="watchlist-top-stat-value">{flowSummaryStats.topTheme}</strong></div>
              <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">최고 등락률</p><strong className="watchlist-top-stat-value">{fmtPct(flowSummaryStats.maxChangeRate)}</strong></div>
              <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">미분류</p><strong className="watchlist-top-stat-value">{flowSummaryStats.unclassified}</strong></div>
            </div>

            {flowLoading ? <p className="text-sm text-muted">테마 요약을 조회 중입니다.</p> : null}
            {!flowLoading && flowSummaries.length === 0 ? <p className="text-sm text-muted">이 날짜에 저장된 수급 이벤트 후보가 없습니다.</p> : null}

            {flowSummaries.length > 0 ? (
              <div className="daily-theme-rank-grid">
                {flowSummaries.map((item) => {
                  const selected = selectedFlowTheme?.id === item.market_theme_id;
                  return (
                    <button
                      key={item.market_theme_id}
                      type="button"
                      className={`daily-theme-rank-card ${selected ? "selected" : ""}`}
                      onClick={() => void loadFlowStocks(item)}
                    >
                      <div className="daily-theme-rank-title">{item.final_rank ?? "-"}위 {item.theme_name}</div>
                      <div className="daily-theme-rank-meta">점수 {item.rank_score} · {item.stock_count}종목 · 이벤트 {item.event_count}</div>
                      <div className="daily-theme-rank-meta">평균 {fmtPct(item.avg_change_rate)} · 최고 {fmtPct(item.max_change_rate)}</div>
                      <div className="daily-theme-rank-meta truncate">대표 {item.representative_stocks.length > 0 ? item.representative_stocks[0] : "-"} · 거래대금 {fmtEokShort(item.estimated_trading_value_sum)}</div>
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

          <SectionCard title="">
            <div className="theme-detail-header">
              <div className="theme-detail-title-block">
                <div className="watchlist-card-title-wrap">
                  <h3 className="section-title m-0">선택 테마 상세 종목{selectedFlowTheme ? ` - ${selectedFlowTheme.name}` : ""}</h3>
                </div>
                {selectedFlowTheme && selectedThemeMeta ? <p className="text-sm text-muted mb-2">{selectedThemeMeta.stockCount}종목 · 대표 {selectedThemeMeta.representative}</p> : null}
              </div>
              <div className="market-mini-charts">
                <div className="market-mini-chart-card">
                  <p className="market-mini-chart-label">KOSPI 3개월</p>
                  {brokenCharts["market-kospi-month3"] ? (
                    <div className="market-mini-chart-fallback">차트 이미지 없음</div>
                  ) : (
                    <button
                      type="button"
                      className="market-mini-chart-button"
                      onClick={() => setZoomedChart({ url: getNaverMarketChartImageUrl("KOSPI", chartSidcode), alt: "KOSPI 3개월 차트" })}
                    >
                      <img
                        src={getNaverMarketChartImageUrl("KOSPI", chartSidcode)}
                        alt="KOSPI 3개월 차트"
                        loading="lazy"
                        className="market-mini-chart-image"
                        onError={() => onChartError("market-kospi-month3")}
                      />
                    </button>
                  )}
                </div>
                <div className="market-mini-chart-card">
                  <p className="market-mini-chart-label">KOSDAQ 3개월</p>
                  {brokenCharts["market-kosdaq-month3"] ? (
                    <div className="market-mini-chart-fallback">차트 이미지 없음</div>
                  ) : (
                    <button
                      type="button"
                      className="market-mini-chart-button"
                      onClick={() => setZoomedChart({ url: getNaverMarketChartImageUrl("KOSDAQ", chartSidcode), alt: "KOSDAQ 3개월 차트" })}
                    >
                      <img
                        src={getNaverMarketChartImageUrl("KOSDAQ", chartSidcode)}
                        alt="KOSDAQ 3개월 차트"
                        loading="lazy"
                        className="market-mini-chart-image"
                        onError={() => onChartError("market-kosdaq-month3")}
                      />
                    </button>
                  )}
                </div>
              </div>
            </div>
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
                            {row.user_memo ? (
                              <div className="text-[11px] text-slate-500 truncate max-w-[220px]" title={row.user_memo}>
                                메모: {row.user_memo}
                              </div>
                            ) : null}
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
          <SectionCard title="">
            <div className="watchlist-card-title-wrap">
              <h3 className="section-title m-0">월별 테마 수급 흐름</h3>
              <span className="hint-icon" title="저장된 수급 이벤트 후보를 월 단위로 집계하여 날짜별·테마별 수급 흐름을 보여줍니다.">i</span>
            </div>
            <div className="flex gap-2 items-end mb-3 flex-wrap">
              <input className="input-control" style={{ width: "140px", minWidth: "140px" }} type="month" value={monthlyBaseMonth} onChange={(e) => setMonthlyBaseMonth(e.target.value)} />
              <button type="button" className="btn btn-primary" onClick={() => void loadMonthlyFlow()}>조회</button>
              <button type="button" className="btn btn-secondary" onClick={() => { const currentMonth = getMonthInput(); setMonthlyBaseMonth(currentMonth); void loadMonthlyFlow(); }}>이번 달</button>
              {monthlyStartDate && monthlyEndDate ? <span className="text-xs text-muted">조회 구간: {monthlyStartDate} ~ {monthlyEndDate}</span> : null}
            </div>

            <div className="watchlist-top-stats mb-3">
              <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">전체 이벤트</p><strong className="watchlist-top-stat-value">{monthlySummary.totalEvents}건</strong></div>
              <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">등장 테마</p><strong className="watchlist-top-stat-value">{monthlySummary.themeCount}개</strong></div>
              <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">TOP 테마</p><strong className="watchlist-top-stat-value">{monthlySummary.topTheme}</strong></div>
              <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">최고 수급일</p><strong className="watchlist-top-stat-value">{monthlySummary.bestDate}</strong></div>
              <div className="watchlist-top-stat-card"><p className="watchlist-top-stat-label">미분류 <span className="hint-icon" title="테마가 연결되지 않은 수급 이벤트 후보 수입니다.">i</span></p><strong className="watchlist-top-stat-value">{monthlySummary.unclassified}</strong></div>
            </div>

            {monthlyLoading ? <p className="text-sm text-muted">월별 테마 수급 흐름을 조회 중입니다.</p> : null}
            {!monthlyLoading && monthlyCalendarDays.length === 0 ? <p className="text-sm text-muted">저장된 수급 이벤트 후보가 없습니다.</p> : null}

            {monthlyCalendarDays.length > 0 ? (
              <div className="market-trend-monthly-grid">
                <div className="border rounded-lg p-3">
                  <div className="watchlist-card-title-wrap">
                    <h4 className="section-title m-0">월간 수급 달력</h4>
                    <span className="hint-icon" title="날짜별로 저장된 수급 이벤트 후보의 테마 점수를 표시합니다. 강한 수급일은 더 강조되어 표시됩니다.">i</span>
                  </div>
                  <div className="grid grid-cols-7 gap-2 mb-2 text-xs font-medium text-slate-600">
                    {["일", "월", "화", "수", "목", "금", "토"].map((w) => <div key={w}>{w}</div>)}
                  </div>
                  <div className="grid grid-cols-7 gap-2">
                    {monthlyCells.map((cell, idx) => {
                      const isToday = cell.date === todayDate;
                      const isSelected = cell.date && selectedMonthlyDate === cell.date;
                      const score = cell.day?.themes?.reduce((sum, t) => sum + (t.rank_score ?? 0), 0) ?? 0;
                      const intensity = score / monthlyMaxDayScore;
                      const heatClass = intensity >= 0.75 ? "heat-strong" : intensity >= 0.4 ? "heat-mid" : intensity > 0 ? "heat-light" : "";
                      return (
                        <button
                          key={`${cell.date ?? "blank"}-${idx}`}
                          type="button"
                          disabled={!cell.date}
                          onClick={() => cell.date && setSelectedMonthlyDate(cell.date)}
                          className={`market-trend-calendar-cell ${!cell.date ? "blank" : ""} ${isSelected ? "selected" : ""} ${isToday ? "today" : ""} ${heatClass}`}
                        >
                          <div className="text-xs font-semibold mb-1">{cell.date ? Number(cell.date.slice(8, 10)) : ""}</div>
                          {cell.day?.themes?.slice(0, 3).map((theme) => (
                            <div key={`${cell.date}-${theme.market_theme_id}`} className="text-[11px] text-slate-700 truncate">
                              {theme.theme_name} +{theme.rank_score}
                            </div>
                          ))}
                          {cell.day && cell.day.themes.length > 3 ? <div className="text-[11px] text-slate-500">+{cell.day.themes.length - 3}개</div> : null}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="border rounded-lg p-3">
                  <h4 className="section-title m-0">선택일 상세</h4>
                  {selectedMonthlyDay ? (
                    <div className="space-y-2">
                      <p className="text-sm text-muted">{selectedMonthlyDay.trade_date}</p>
                      {selectedMonthlyDay.themes.length === 0 ? <p className="text-sm text-muted">선택일 데이터가 없습니다.</p> : null}
                      {selectedMonthlyDay.themes.slice(0, 5).map((theme) => (
                        <div key={`selected-${theme.market_theme_id}`} className="flex items-center justify-between text-sm gap-2">
                          <span className="font-semibold text-slate-800">{theme.theme_name}</span>
                          <span className="text-slate-600">+{theme.rank_score} · {theme.stock_count}종목</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-sm text-muted">월간 TOP 테마</p>
                      {monthlyTopThemes.slice(0, 3).map((theme) => (
                        <div key={`month-top-${theme.market_theme_id}`} className="flex items-center justify-between text-sm gap-2">
                          <span className="font-semibold text-slate-800">{theme.theme_name}</span>
                          <span className="text-slate-600">+{theme.series[theme.series.length - 1]?.value ?? 0}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </SectionCard>

          <SectionCard title="">
            <div className="watchlist-card-title-wrap">
              <h3 className="section-title m-0">월간 테마 누적 흐름 그래프</h3>
              <span className="hint-icon" title="일별 테마 점수를 누적해 월간 흐름을 보여줍니다. 반복적으로 수급 이벤트가 발생한 테마일수록 상승합니다.">i</span>
            </div>
            {monthlyLineData.length === 0 ? <p className="text-sm text-muted">그래프 데이터가 없습니다.</p> : null}
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
                      <tr><th>날짜</th><th>1위 테마</th><th>2위 테마</th><th>3위 테마</th><th>이벤트 수</th><th>주요 종목</th><th>상세</th></tr>
                    </thead>
                    <tbody>
                      {monthlyCalendarDays.filter((d) => d.themes.length > 0).map((d) => (
                        <tr key={d.trade_date}>
                          <td>{d.trade_date}</td>
                          <td>{d.themes[0] ? `${d.themes[0].theme_name} +${d.themes[0].rank_score}` : "-"}</td>
                          <td>{d.themes[1] ? `${d.themes[1].theme_name} +${d.themes[1].rank_score}` : "-"}</td>
                          <td>{d.themes[2] ? `${d.themes[2].theme_name} +${d.themes[2].rank_score}` : "-"}</td>
                          <td>{d.themes.reduce((sum, t) => sum + (t.stock_count ?? 0), 0)}건</td>
                          <td>{d.themes[0] ? `${d.themes[0].theme_name} 외 ${Math.max(0, d.themes.reduce((sum, t) => sum + (t.stock_count ?? 0), 0) - 1)}` : "-"}</td>
                          <td><button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setSelectedMonthlyDate(d.trade_date)}>보기</button></td>
                        </tr>
                      ))}
                      {monthlyCalendarDays.filter((d) => d.themes.length > 0).length === 0 ? (
                        <tr><td colSpan={7} className="text-center text-muted">월간 상세 데이터가 없습니다.</td></tr>
                      ) : null}
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
