import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { MarketTheme } from "@/types/marketTheme";
import type {
  CollectMarketTrendEventsResponse,
  DailyThemeFlowResponse,
  MarketScope,
  MarketTrendEvent,
  ThemeStatus,
  TrendDetectionSetting,
} from "@/types/marketTrend";

type ActiveTab = "settings" | "events" | "flow";

const fmtEok = (value: number | null | undefined) => (value == null ? "-" : value.toLocaleString("ko-KR"));
const fmtPct = (value: number | null | undefined) => (value == null ? "-" : `${value.toFixed(2)}%`);
const toErr = (e: unknown, fallback: string) => (e instanceof Error && e.message ? e.message : fallback);

function MarketTrendsPage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("settings");
  const [setting, setSetting] = useState<TrendDetectionSetting | null>(null);
  const [themes, setThemes] = useState<MarketTheme[]>([]);
  const [events, setEvents] = useState<MarketTrendEvent[]>([]);
  const [flow, setFlow] = useState<DailyThemeFlowResponse | null>(null);
  const [collectResult, setCollectResult] = useState<CollectMarketTrendEventsResponse | null>(null);
  const [tradeDate, setTradeDate] = useState("");
  const [themeStatusFilter, setThemeStatusFilter] = useState<"all" | ThemeStatus>("all");
  const [marketScopeFilter, setMarketScopeFilter] = useState<MarketScope>("ALL");
  const [flowOnlySupplyTheme, setFlowOnlySupplyTheme] = useState(false);
  const [selectedThemeByEvent, setSelectedThemeByEvent] = useState<Record<number, number | "">>({});
  const [reasonByEvent, setReasonByEvent] = useState<Record<number, string>>({});
  const [memoByEvent, setMemoByEvent] = useState<Record<number, string>>({});
  const [addToMappingByEvent, setAddToMappingByEvent] = useState<Record<number, boolean>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const sortedThemes = useMemo(
    () =>
      [...themes].sort((a, b) => {
        if (b.is_supply_theme !== a.is_supply_theme) return b.is_supply_theme - a.is_supply_theme;
        if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
        return a.theme_name.localeCompare(b.theme_name, "ko-KR");
      }),
    [themes],
  );

  const loadInitial = async () => {
    setLoading(true);
    setError("");
    try {
      const [settingRes, themesRes] = await Promise.all([
        repositories.marketTrends.getTrendDetectionSettings(),
        repositories.marketThemes.list({ is_active: 1, limit: 500 }),
      ]);
      setSetting(settingRes);
      setThemes(themesRes);
      if (!tradeDate) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, "0");
        const dd = String(today.getDate()).padStart(2, "0");
        setTradeDate(`${yyyy}-${mm}-${dd}`);
      }
    } catch (e) {
      setError(toErr(e, "초기 데이터를 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  };

  const loadEvents = async () => {
    setError("");
    try {
      const rows = await repositories.marketTrends.getMarketTrendEvents({
        trade_date: tradeDate || undefined,
        theme_status: themeStatusFilter === "all" ? undefined : themeStatusFilter,
        market_scope: marketScopeFilter,
        limit: 200,
      });
      setEvents(rows);
    } catch (e) {
      setError(toErr(e, "수급 이벤트 목록을 불러오지 못했습니다."));
    }
  };

  const loadFlow = async () => {
    setError("");
    try {
      const res = await repositories.marketTrends.getDailyThemeFlow({
        trade_date: tradeDate || undefined,
        only_supply_theme: flowOnlySupplyTheme,
        market_scope: marketScopeFilter,
      });
      setFlow(res);
    } catch (e) {
      setError(toErr(e, "일별 테마 수급 흐름을 불러오지 못했습니다."));
    }
  };

  useEffect(() => {
    void loadInitial();
  }, []);

  const onSaveSettings = async () => {
    if (!setting) return;
    setMessage("");
    setError("");
    try {
      const updated = await repositories.marketTrends.updateTrendDetectionSettings({
        min_market_cap_krw_100m: Number(setting.min_market_cap_krw_100m) || 0,
        min_trading_value_krw_100m: Number(setting.min_trading_value_krw_100m) || 0,
        min_change_rate: Number(setting.min_change_rate) || 0,
        min_intraday_range_rate: setting.min_intraday_range_rate == null ? null : Number(setting.min_intraday_range_rate),
        use_intraday_range: setting.use_intraday_range,
        market_scope: setting.market_scope,
        is_active: setting.is_active,
      });
      setSetting(updated);
      setMessage("감지 조건이 저장되었습니다.");
    } catch (e) {
      setError(toErr(e, "감지 조건 저장에 실패했습니다."));
    }
  };

  const onCollectEvents = async () => {
    setMessage("");
    setError("");
    try {
      const res = await repositories.marketTrends.collectMarketTrendEvents({ trade_date: tradeDate || undefined });
      setCollectResult(res);
      setMessage(res.message);
      await loadEvents();
    } catch (e) {
      setError(toErr(e, "수급 이벤트 종목 수집에 실패했습니다."));
    }
  };

  const onAssignTheme = async (eventId: number) => {
    const themeId = selectedThemeByEvent[eventId];
    if (!themeId) {
      setError("테마를 선택해 주세요.");
      return;
    }
    setMessage("");
    setError("");
    try {
      await repositories.marketTrends.assignThemeToTrendEvent(eventId, {
        theme_id: Number(themeId),
        reason_summary: reasonByEvent[eventId] || null,
        user_memo: memoByEvent[eventId] || null,
        also_add_to_theme_stocks: Boolean(addToMappingByEvent[eventId]),
        is_primary_for_theme: false,
      });
      setMessage("테마 수동 부여가 저장되었습니다.");
      await Promise.all([loadEvents(), loadFlow()]);
    } catch (e) {
      setError(toErr(e, "테마 수동 부여 저장에 실패했습니다."));
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="시장 트렌드 분석" description="수급 이벤트 감지, 테마 수동 부여, 일별 테마 수급 흐름을 관리합니다." />
      {message ? <div className="inline-result">{message}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}

      <SectionCard title="작업 탭">
        <div className="flex gap-2 flex-wrap">
          <button type="button" className={`btn ${activeTab === "settings" ? "btn-primary" : "btn-secondary"}`} onClick={() => setActiveTab("settings")}>감지 조건 설정</button>
          <button type="button" className={`btn ${activeTab === "events" ? "btn-primary" : "btn-secondary"}`} onClick={() => setActiveTab("events")}>수급 이벤트 종목</button>
          <button type="button" className={`btn ${activeTab === "flow" ? "btn-primary" : "btn-secondary"}`} onClick={() => setActiveTab("flow")}>일별 테마 수급 흐름</button>
        </div>
      </SectionCard>

      {activeTab === "settings" && setting ? (
        <SectionCard title="감지 조건 설정">
          {loading ? <p className="text-sm text-muted">로딩 중...</p> : null}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="space-y-1"><span>최소 시가총액(억 원)</span><input className="input-control" type="number" min={0} value={setting.min_market_cap_krw_100m} onChange={(e) => setSetting({ ...setting, min_market_cap_krw_100m: Number(e.target.value) || 0 })} /></label>
            <label className="space-y-1"><span>최소 거래대금(억 원)</span><input className="input-control" type="number" min={0} value={setting.min_trading_value_krw_100m} onChange={(e) => setSetting({ ...setting, min_trading_value_krw_100m: Number(e.target.value) || 0 })} /></label>
            <label className="space-y-1"><span>최소 상승률(%)</span><input className="input-control" type="number" min={0} step="0.1" value={setting.min_change_rate} onChange={(e) => setSetting({ ...setting, min_change_rate: Number(e.target.value) || 0 })} /></label>
            <label className="space-y-1"><span>최소 당일 변동폭(%)</span><input className="input-control" type="number" min={0} step="0.1" value={setting.min_intraday_range_rate ?? 0} onChange={(e) => setSetting({ ...setting, min_intraday_range_rate: Number(e.target.value) || 0 })} disabled={!setting.use_intraday_range} /></label>
            <label className="space-y-1"><span>시장 구분</span><select className="select-control" value={setting.market_scope} onChange={(e) => setSetting({ ...setting, market_scope: e.target.value as MarketScope })}><option value="ALL">전체</option><option value="KOSPI">KOSPI</option><option value="KOSDAQ">KOSDAQ</option></select></label>
            <label className="inline-flex items-center gap-2 mt-7"><input type="checkbox" checked={setting.use_intraday_range} onChange={(e) => setSetting({ ...setting, use_intraday_range: e.target.checked })} /><span>당일 변동폭 조건 사용</span></label>
          </div>
          <p className="text-sm text-muted mt-3">현재 감지 조건: 시가총액 {fmtEok(setting.min_market_cap_krw_100m)}억 이상 · 거래대금 {fmtEok(setting.min_trading_value_krw_100m)}억 이상 · 상승률 {setting.min_change_rate}% 이상</p>
          <div className="flex gap-2 mt-3"><button type="button" className="btn btn-primary" onClick={() => void onSaveSettings()}>저장</button></div>
        </SectionCard>
      ) : null}

      {activeTab === "events" ? (
        <SectionCard title="수급 이벤트 종목">
          <div className="flex gap-2 flex-wrap items-end">
            <label className="space-y-1"><span>기준일</span><input className="input-control" type="date" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} /></label>
            <label className="space-y-1"><span>분류 상태</span><select className="select-control" value={themeStatusFilter} onChange={(e) => setThemeStatusFilter(e.target.value as "all" | ThemeStatus)}><option value="all">전체</option><option value="unassigned">미분류</option><option value="manual_assigned">분류완료</option></select></label>
            <label className="space-y-1"><span>시장</span><select className="select-control" value={marketScopeFilter} onChange={(e) => setMarketScopeFilter(e.target.value as MarketScope)}><option value="ALL">전체</option><option value="KOSPI">KOSPI</option><option value="KOSDAQ">KOSDAQ</option></select></label>
            <button type="button" className="btn btn-primary" onClick={() => void onCollectEvents()}>수집 실행</button>
            <button type="button" className="btn btn-secondary" onClick={() => void loadEvents()}>조회</button>
          </div>
          {collectResult ? <p className="text-sm text-muted mt-2">수집 결과: 전체 {collectResult.collected_count}건 / 신규 {collectResult.inserted_count}건 / 중복 {collectResult.duplicated_count}건</p> : null}
          <div className="table-shell max-h-[420px] overflow-auto mt-3">
            <table className="data-table compact-table">
              <thead><tr><th>종목</th><th>시장</th><th>등락률</th><th>거래대금(억)</th><th>시가총액(억)</th><th>변동폭</th><th>테마</th><th>사유/메모</th><th>작업</th></tr></thead>
              <tbody>
                {events.map((row) => (
                  <tr key={row.event_id}>
                    <td>{row.stock_name} ({row.stock_code})</td><td>{row.market_type ?? "-"}</td><td>{fmtPct(row.change_rate)}</td><td>{fmtEok(row.trading_value == null ? null : row.trading_value / 100000000)}</td><td>{fmtEok(row.market_cap == null ? null : row.market_cap / 100000000)}</td><td>{fmtPct(row.intraday_range_rate)}</td>
                    <td>
                      <select className="select-control min-w-[180px]" value={selectedThemeByEvent[row.event_id] ?? row.theme_id ?? ""} onChange={(e) => setSelectedThemeByEvent((prev) => ({ ...prev, [row.event_id]: e.target.value ? Number(e.target.value) : "" }))}>
                        <option value="">테마 미지정</option>
                        {sortedThemes.map((theme) => <option key={theme.id} value={theme.id}>{theme.is_supply_theme === 1 ? `[수급] ${theme.theme_name}` : theme.theme_name}</option>)}
                      </select>
                    </td>
                    <td>
                      <input className="input-control mb-1" placeholder="사유 요약" value={reasonByEvent[row.event_id] ?? row.reason_summary ?? ""} onChange={(e) => setReasonByEvent((prev) => ({ ...prev, [row.event_id]: e.target.value }))} />
                      <input className="input-control mb-1" placeholder="사용자 메모" value={memoByEvent[row.event_id] ?? row.user_memo ?? ""} onChange={(e) => setMemoByEvent((prev) => ({ ...prev, [row.event_id]: e.target.value }))} />
                      <label className="inline-flex items-center gap-1 text-xs"><input type="checkbox" checked={Boolean(addToMappingByEvent[row.event_id])} onChange={(e) => setAddToMappingByEvent((prev) => ({ ...prev, [row.event_id]: e.target.checked }))} /><span>정식 테마-종목 매핑 추가</span></label>
                    </td>
                    <td><button type="button" className="btn btn-primary" onClick={() => void onAssignTheme(row.event_id)}>저장</button></td>
                  </tr>
                ))}
                {events.length === 0 ? <tr><td colSpan={9} className="text-center text-muted">데이터가 없습니다.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}

      {activeTab === "flow" ? (
        <SectionCard title="일별 테마 수급 흐름">
          <div className="flex gap-2 flex-wrap items-end">
            <label className="space-y-1"><span>기준일</span><input className="input-control" type="date" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} /></label>
            <label className="space-y-1"><span>시장</span><select className="select-control" value={marketScopeFilter} onChange={(e) => setMarketScopeFilter(e.target.value as MarketScope)}><option value="ALL">전체</option><option value="KOSPI">KOSPI</option><option value="KOSDAQ">KOSDAQ</option></select></label>
            <label className="inline-flex items-center gap-2 mb-2"><input type="checkbox" checked={flowOnlySupplyTheme} onChange={(e) => setFlowOnlySupplyTheme(e.target.checked)} /><span>수급테마만 보기</span></label>
            <button type="button" className="btn btn-primary" onClick={() => void loadFlow()}>조회</button>
          </div>
          <p className="text-sm text-muted mt-2">본 집계는 사용자가 부여한 테마 기준의 내부 참고 지표입니다. 공식 업종/테마 분류가 아니며, 최종 투자 판단은 사용자가 수행합니다.</p>
          {flow ? <p className="text-sm text-muted mt-2">요약: 이벤트 {flow.summary.event_count}건 · 분류완료 {flow.summary.assigned_count}건 · 미분류 {flow.summary.unassigned_count}건</p> : null}
          <div className="table-shell max-h-[420px] overflow-auto mt-3">
            <table className="data-table compact-table">
              <thead><tr><th>순위</th><th>테마</th><th>수급</th><th>감지 종목 수</th><th>거래대금 합계(억)</th><th>평균 상승률</th><th>최고 상승률</th><th>최고 상승 종목</th><th>최대 거래대금 종목</th></tr></thead>
              <tbody>
                {(flow?.items ?? []).map((item) => (
                  <tr key={item.theme_id}>
                    <td>{item.trend_rank}</td><td>{item.theme_name}</td><td>{item.is_supply_theme ? "수급" : "-"}</td><td>{item.detected_stock_count}</td><td>{fmtEok(item.total_trading_value_krw_100m)}</td><td>{fmtPct(item.avg_change_rate)}</td><td>{fmtPct(item.max_change_rate)}</td><td>{item.top_change_stock_name ?? "-"}</td><td>{item.top_trading_value_stock_name ?? "-"}</td>
                  </tr>
                ))}
                {(flow?.items.length ?? 0) === 0 ? <tr><td colSpan={9} className="text-center text-muted">데이터가 없습니다.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}
    </div>
  );
}

export default MarketTrendsPage;

