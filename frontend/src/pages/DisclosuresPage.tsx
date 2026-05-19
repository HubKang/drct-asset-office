import { X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { AiSummarizeResponse } from "@/types/analysis";
import type { Disclosure, DisclosureCollectResponse, DisclosureCollectSelectedResponse } from "@/types/disclosure";
import type { Watchlist } from "@/types/watchlist";

type WatchlistDisclosureTarget = {
  stock_id: number;
  stock_code: string;
  stock_name: string;
  disclosure_count: number;
  ai_processed_count: number;
  latest_disclosed_at: string | null;
};

function disclosureStatusMeta(item: Disclosure): { label: string; tone: "emerald" | "slate" } {
  if (item.ai_summary || item.ai_processed_at) return { label: "완료", tone: "emerald" };
  return { label: "미처리", tone: "slate" };
}

function riskMeta(risk?: string | null): { label: string; variant: "risk-high" | "risk-medium" | "risk-low" | "risk-unknown" } {
  const value = (risk || "").toLowerCase();
  if (value === "high") return { label: "고위험", variant: "risk-high" };
  if (value === "medium") return { label: "중위험", variant: "risk-medium" };
  if (value === "low") return { label: "저위험", variant: "risk-low" };
  return { label: "미분류", variant: "risk-unknown" };
}

function importanceMeta(score?: number | null): { label: string; variant: "importance-high" | "importance-medium" | "importance-low" } {
  const value = Number.isFinite(score) ? Number(score) : 0;
  if (value >= 70) return { label: `${value} / 중요`, variant: "importance-high" };
  if (value >= 40) return { label: `${value} / 보통`, variant: "importance-medium" };
  return { label: `${value} / 낮음`, variant: "importance-low" };
}

function eventLabel(eventType?: string | null): string {
  if (!eventType || eventType.toLowerCase() === "unknown") return "기타";
  return eventType;
}

function formatDate(value?: string | null): string {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function DisclosuresPage() {
  const [targets, setTargets] = useState<WatchlistDisclosureTarget[]>([]);
  const [items, setItems] = useState<Disclosure[]>([]);
  const [selectedDisclosure, setSelectedDisclosure] = useState<Disclosure | null>(null);
  const [isDisclosureDrawerOpen, setIsDisclosureDrawerOpen] = useState(false);

  const [currentStockId, setCurrentStockId] = useState<number | null>(null);
  const [checkedStockIds, setCheckedStockIds] = useState<number[]>([]);
  const [watchlistKeyword, setWatchlistKeyword] = useState("");
  const [watchlistFilter, setWatchlistFilter] = useState("");

  const [collectDays, setCollectDays] = useState("30");
  const [collectPageCount, setCollectPageCount] = useState("100");
  const [sortOrder, setSortOrder] = useState("date");

  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [collectLoading, setCollectLoading] = useState(false);
  const [collectError, setCollectError] = useState("");
  const [collectResult, setCollectResult] = useState<DisclosureCollectResponse | DisclosureCollectSelectedResponse | null>(null);

  const [summarizeLoading, setSummarizeLoading] = useState(false);
  const [summarizeError, setSummarizeError] = useState("");
  const [summarizeResult, setSummarizeResult] = useState<AiSummarizeResponse | null>(null);

  const filteredTargets = useMemo(() => {
    const q = watchlistFilter.trim().toLowerCase();
    if (!q) return targets;
    return targets.filter((target) => target.stock_name.toLowerCase().includes(q) || target.stock_code.toLowerCase().includes(q));
  }, [targets, watchlistFilter]);

  const sortedItems = useMemo(() => {
    const copied = [...items];
    if (sortOrder === "score") {
      return copied.sort((a, b) => (b.ai_importance_score ?? b.importance_score ?? 0) - (a.ai_importance_score ?? a.importance_score ?? 0));
    }
    return copied.sort((a, b) => String(b.disclosed_at ?? "").localeCompare(String(a.disclosed_at ?? "")));
  }, [items, sortOrder]);

  const processedCount = sortedItems.filter((item) => Boolean(item.ai_summary || item.ai_processed_at)).length;
  const activeTarget = useMemo(() => targets.find((target) => target.stock_id === currentStockId), [targets, currentStockId]);

  const resolveTargetStockIds = (): number[] => {
    if (checkedStockIds.length > 0) return checkedStockIds;
    if (currentStockId) return [currentStockId];
    return [];
  };

  const buildTargets = (watchlist: Watchlist[], disclosures: Disclosure[]): WatchlistDisclosureTarget[] => {
    return watchlist.map((item) => {
      const stockDisclosures = disclosures.filter((disclosure) => disclosure.stock_id === item.stock_id);
      const latestDisclosedAt = stockDisclosures
        .map((disclosure) => disclosure.disclosed_at)
        .filter((value): value is string => Boolean(value))
        .sort((a, b) => b.localeCompare(a))[0] ?? null;
      return {
        stock_id: item.stock_id,
        stock_code: item.stock_code,
        stock_name: item.stock_name,
        disclosure_count: stockDisclosures.length,
        ai_processed_count: stockDisclosures.filter((disclosure) => Boolean(disclosure.ai_summary || disclosure.ai_processed_at)).length,
        latest_disclosed_at: latestDisclosedAt,
      };
    });
  };

  const loadTargets = async () => {
    setWatchlistLoading(true);
    try {
      const watchlist = await repositories.watchlist.list({ is_active: 1, limit: 200, offset: 0 });
      const disclosures = await repositories.disclosures.listDisclosures({ limit: 500, offset: 0 });
      const nextTargets = buildTargets(watchlist, disclosures);
      setTargets(nextTargets);
      setCurrentStockId((prev) => prev ?? nextTargets[0]?.stock_id ?? null);
    } finally {
      setWatchlistLoading(false);
    }
  };

  const loadDisclosuresByStock = async (stockId: number | null) => {
    if (!stockId) {
      setItems([]);
      setSelectedDisclosure(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await repositories.disclosures.listDisclosures({ stock_id: stockId, limit: 100, offset: 0 });
      setItems(data);
      setSelectedDisclosure(data[0] ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "공시 목록 조회 중 오류가 발생했습니다.");
      setItems([]);
      setSelectedDisclosure(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTargets();
  }, []);

  useEffect(() => {
    setCollectResult(null);
    setSummarizeResult(null);
    void loadDisclosuresByStock(currentStockId);
  }, [currentStockId]);

  useEffect(() => {
    const onEsc = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsDisclosureDrawerOpen(false);
      }
    };
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, []);

  const toggleStockCheck = (stockId: number) => {
    setCheckedStockIds((prev) => (prev.includes(stockId) ? prev.filter((id) => id !== stockId) : [...prev, stockId]));
  };

  const handleOpenDisclosureDetail = (disclosure: Disclosure) => {
    setSelectedDisclosure(disclosure);
    setIsDisclosureDrawerOpen(true);
  };

  const handleCloseDisclosureDetail = () => {
    setIsDisclosureDrawerOpen(false);
    setSelectedDisclosure(null);
  };

  const onCollectSelected = async (): Promise<boolean> => {
    const targetStockIds = resolveTargetStockIds();
    if (targetStockIds.length === 0) {
      setCollectError("작업할 관심종목을 선택해 주세요.");
      return false;
    }

    setCollectLoading(true);
    setCollectError("");
    setCollectResult(null);
    try {
      const result = await repositories.disclosures.collectDisclosuresForSelectedWatchlist({
        stock_ids: targetStockIds,
        days: Number(collectDays),
        page_count: Number(collectPageCount),
      });
      setCollectResult(result);
      await loadTargets();
      await loadDisclosuresByStock(currentStockId);
      return true;
    } catch (e) {
      setCollectError(e instanceof Error ? e.message : "선택 공시 수집 중 오류가 발생했습니다.");
      return false;
    } finally {
      setCollectLoading(false);
    }
  };

  const onSummarizeSelected = async (): Promise<boolean> => {
    const targetStockIds = resolveTargetStockIds();
    if (targetStockIds.length === 0) {
      setSummarizeError("작업할 관심종목을 선택해 주세요.");
      return false;
    }

    const results = await Promise.all(
      targetStockIds.map((stockId) => repositories.disclosures.listDisclosures({ stock_id: stockId, limit: 100, offset: 0 })),
    );
    const ids = results.flat().filter((item) => !item.ai_summary && !item.ai_processed_at).map((item) => item.id);
    const uniqueIds = Array.from(new Set(ids));
    if (uniqueIds.length === 0) {
      setSummarizeError("처리할 미처리 공시가 없습니다.");
      return false;
    }

    setSummarizeLoading(true);
    setSummarizeError("");
    setSummarizeResult(null);
    try {
      const result = await repositories.disclosures.summarizeSelectedDisclosures(uniqueIds);
      setSummarizeResult(result);
      await loadTargets();
      await loadDisclosuresByStock(currentStockId);
      return true;
    } catch (e) {
      setSummarizeError(e instanceof Error ? e.message : "선택 AI 처리 중 오류가 발생했습니다.");
      return false;
    } finally {
      setSummarizeLoading(false);
    }
  };

  const onCollectAndSummarize = async () => {
    const collected = await onCollectSelected();
    if (!collected) return;
    await onSummarizeSelected();
  };

  const onSearchTargets = () => setWatchlistFilter(watchlistKeyword);

  return (
    <div className="space-y-4">
      <PageHeader
        title="공시 관리"
        description="관심종목을 선택하면 해당 종목의 공시가 자동 조회됩니다."
        action={(
          <div className="flex flex-wrap gap-2">
            <StatusBadge label="데이터 소스: API" tone="slate" />
            <StatusBadge label="API 정상" tone="emerald" />
            <StatusBadge label={`AI 처리 ${processedCount}/${sortedItems.length || 0}`} tone="blue" />
          </div>
        )}
      />

      <div className="flex w-full flex-nowrap items-center gap-1.5 overflow-hidden whitespace-nowrap">
        <input
          className="input-control !min-h-[34px] w-[170px] max-w-[170px] shrink-0 px-2 py-1 text-[12px]"
          placeholder="종목명/종목코드"
          value={watchlistKeyword}
          onChange={(e) => setWatchlistKeyword(e.target.value)}
        />
        <button type="button" className="btn btn-secondary !min-h-[34px] w-[60px] shrink-0 px-2 text-[12px]" onClick={onSearchTargets}>검색</button>
        <button type="button" className="btn btn-primary !min-h-[34px] w-[116px] shrink-0 px-2 text-[12px]" disabled={collectLoading} onClick={() => void onCollectSelected()}>
          {collectLoading ? "수집 중..." : "선택 공시 수집"}
        </button>
        <button type="button" className="btn btn-secondary !min-h-[34px] w-[110px] shrink-0 px-2 text-[12px]" disabled={summarizeLoading} onClick={() => void onSummarizeSelected()}>
          {summarizeLoading ? "AI 처리 중..." : "선택 AI 처리"}
        </button>
        <button type="button" className="btn btn-secondary !min-h-[34px] w-[132px] shrink-0 px-2 text-[12px]" disabled={collectLoading || summarizeLoading} onClick={() => void onCollectAndSummarize()}>
          선택 수집+AI 처리
        </button>
        <select className="select-control !min-h-[34px] w-[110px] max-w-[110px] shrink-0 px-2 py-1 text-[12px]" value={collectDays} onChange={(e) => setCollectDays(e.target.value)}>
          <option value="7">최근 7일</option>
          <option value="30">최근 30일</option>
          <option value="90">최근 90일</option>
        </select>
        <select className="select-control !min-h-[34px] w-[110px] max-w-[110px] shrink-0 px-2 py-1 text-[12px]" value={collectPageCount} onChange={(e) => setCollectPageCount(e.target.value)}>
          <option value="50">수집 50건</option>
          <option value="100">수집 100건</option>
          <option value="200">수집 200건</option>
        </select>
        <select className="select-control !min-h-[34px] w-[100px] max-w-[100px] shrink-0 px-2 py-1 text-[12px]" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)}>
          <option value="date">최신순</option>
          <option value="score">점수순</option>
        </select>
      </div>

      {collectError ? <p className="text-xs text-rose-600">{collectError}</p> : null}
      {collectResult ? <div className="inline-result">{"requested_count" in collectResult ? `선택 공시 수집 완료: 성공 ${collectResult.success_count}건 / 실패 ${collectResult.failed_count}건` : collectResult.message}</div> : null}
      {summarizeResult ? <div className="inline-result">{`선택 AI 처리 완료: 성공 ${summarizeResult.success_count ?? 0}건 / 실패 ${summarizeResult.failed_count ?? 0}건`}</div> : null}
      {summarizeError ? <div className="inline-result inline-error">{summarizeError}</div> : null}

      <div className="grid w-full min-w-0 grid-cols-[3fr_7fr] items-stretch gap-4">
        <div className="min-w-0">
          <SectionCard title="관심종목 목록">
            <div className="table-shell max-h-[620px] overflow-auto">
              <table className="data-table compact-table min-w-[560px]">
                <thead>
                  <tr>
                    <th>선택</th>
                    <th>종목명</th>
                    <th>공시수</th>
                    <th>AI처리</th>
                    <th>최근공시</th>
                  </tr>
                </thead>
                <tbody>
                  {watchlistLoading ? (
                    <tr><td colSpan={5} className="py-4 text-center text-muted">관심종목을 불러오는 중입니다.</td></tr>
                  ) : filteredTargets.length === 0 ? (
                    <tr><td colSpan={5} className="py-4 text-center text-muted">관심종목이 없습니다.</td></tr>
                  ) : (
                    filteredTargets.map((target) => {
                      const isChecked = checkedStockIds.includes(target.stock_id);
                      const isCurrent = currentStockId === target.stock_id;
                      return (
                        <tr key={target.stock_id} className={isCurrent ? "selected-row row-clickable" : "row-clickable"} onClick={() => setCurrentStockId(target.stock_id)}>
                          <td onClick={(e) => e.stopPropagation()}>
                            <input type="checkbox" checked={isChecked} onClick={(event) => event.stopPropagation()} onChange={() => toggleStockCheck(target.stock_id)} />
                          </td>
                          <td>{`${target.stock_name} (${target.stock_code})`}</td>
                          <td>{target.disclosure_count}</td>
                          <td>{`${target.ai_processed_count}/${target.disclosure_count}`}</td>
                          <td className="cell-nowrap">{formatDate(target.latest_disclosed_at)}</td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>

        <div className="min-w-0">
          <SectionCard title={`공시 목록${activeTarget ? ` - ${activeTarget.stock_name}` : ""}`}>
            {currentStockId === null ? <p className="text-sm text-muted">좌측 관심종목을 선택하면 해당 종목의 공시 목록이 표시됩니다.</p> : null}
            {loading ? <p className="text-sm text-muted">공시를 불러오는 중입니다.</p> : null}
            {error ? <p className="text-sm text-rose-600">{error}</p> : null}
            {!loading && !error && currentStockId !== null && sortedItems.length === 0 ? (
              <p className="text-sm text-muted">선택한 종목의 수집된 공시가 없습니다. 상단의 "선택 공시 수집" 버튼으로 공시를 수집해 주세요.</p>
            ) : null}

            {!loading && !error && sortedItems.length > 0 ? (
              <div className="table-shell max-h-[620px] overflow-auto">
                <table className="data-table compact-table min-w-[1020px]">
                  <thead>
                    <tr>
                      <th>AI처리</th>
                      <th>종목명</th>
                      <th className="min-w-[380px]">공시제목</th>
                      <th>이벤트</th>
                      <th>리스크</th>
                      <th>중요도</th>
                      <th>공시일</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedItems.map((item) => {
                      const aiStatus = disclosureStatusMeta(item);
                      const event = eventLabel(item.ai_event_type ?? item.disclosure_type);
                      const risk = riskMeta(item.ai_risk_level);
                      const importance = importanceMeta(item.ai_importance_score ?? item.importance_score);
                      return (
                        <tr key={item.id} className="row-clickable" onClick={() => handleOpenDisclosureDetail(item)}>
                          <td><StatusBadge label={aiStatus.label} tone={aiStatus.tone} /></td>
                          <td className="cell-nowrap">{item.stock_name ?? item.stock_code ?? "-"}</td>
                          <td className="cell-title cell-clamp-2" title={item.disclosure_title}>{item.disclosure_title}</td>
                          <td><StatusBadge label={event} variant="event" /></td>
                          <td><StatusBadge label={risk.label} variant={risk.variant} /></td>
                          <td><StatusBadge label={importance.label} variant={importance.variant} /></td>
                          <td className="cell-nowrap cell-muted">{formatDate(item.disclosed_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </SectionCard>
        </div>
      </div>

      {isDisclosureDrawerOpen && selectedDisclosure ? (
        <div className="fixed inset-0 z-[999] bg-slate-900/30" onClick={handleCloseDisclosureDetail}>
          <aside className="absolute right-0 top-0 h-full w-full max-w-[520px] overflow-auto border-l bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 flex items-center justify-between border-b bg-white p-4">
              <h3 className="text-lg font-semibold">공시 상세</h3>
              <button type="button" className="btn btn-secondary !min-h-[30px] px-2" onClick={handleCloseDisclosureDetail}><X size={16} /></button>
            </div>
            <div className="p-4">
              <div className="space-y-3">
                <h4 className="detail-title">{selectedDisclosure.disclosure_title}</h4>
                <div className="detail-section">
                  <p className="detail-label">기본 정보</p>
                  <div className="detail-body">
                    <p>{`종목명: ${selectedDisclosure.stock_name ?? "-"}`}</p>
                    <p>{`종목코드: ${selectedDisclosure.stock_code ?? "-"}`}</p>
                    <p>{`공시일: ${formatDate(selectedDisclosure.disclosed_at)}`}</p>
                    <p>{`접수일: ${formatDate(selectedDisclosure.disclosed_at)}`}</p>
                    <p>{`출처: DART`}</p>
                    <p>{`접수번호: ${selectedDisclosure.dart_receipt_no ?? "-"}`}</p>
                  </div>
                </div>
                <div className="detail-section">
                  <p className="detail-label">AI 분석 정보</p>
                  <div className="detail-body">
                    <p>{`AI 처리 여부: ${selectedDisclosure.ai_summary || selectedDisclosure.ai_processed_at ? "완료" : "미처리"}`}</p>
                    <p>{`AI 처리일: ${formatDate(selectedDisclosure.ai_processed_at)}`}</p>
                    <p>{`이벤트: ${eventLabel(selectedDisclosure.ai_event_type ?? selectedDisclosure.disclosure_type)}`}</p>
                    <p>{`리스크: ${riskMeta(selectedDisclosure.ai_risk_level).label}`}</p>
                    <p>{`중요도: ${selectedDisclosure.ai_importance_score ?? selectedDisclosure.importance_score ?? "-"}`}</p>
                    <p>{`tag: ${selectedDisclosure.ai_tags ?? "-"}`}</p>
                    <p>{`score: ${selectedDisclosure.ai_importance_score ?? selectedDisclosure.importance_score ?? "-"}`}</p>
                    <p>sentiment: -</p>
                    <p>{`risk_level: ${selectedDisclosure.ai_risk_level ?? "-"}`}</p>
                    <p>{`event_type: ${selectedDisclosure.ai_event_type ?? selectedDisclosure.disclosure_type ?? "-"}`}</p>
                  </div>
                </div>
                <div className="detail-section">
                  <p className="detail-label">AI 요약</p>
                  <p className="detail-body">{selectedDisclosure.ai_summary ?? "아직 AI 처리가 완료되지 않은 공시입니다."}</p>
                </div>
                <div className="detail-section">
                  <p className="detail-label">원문 링크</p>
                  {selectedDisclosure.url ? (
                    <a className="btn btn-secondary !min-h-[34px] px-3 text-[13px]" href={selectedDisclosure.url} target="_blank" rel="noreferrer">DART 원문 열기</a>
                  ) : (
                    <p className="detail-body">원문 링크가 없습니다.</p>
                  )}
                </div>
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

export default DisclosuresPage;
