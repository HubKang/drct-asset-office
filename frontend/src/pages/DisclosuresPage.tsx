import { Search } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import codes from "@/data/json/codes.json";
import { repositories } from "@/services";
import type { AiSummarizeResponse } from "@/types/analysis";
import type { Disclosure, DisclosureCollectResponse } from "@/types/disclosure";
import type { Stock } from "@/types/stock";

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
  if (!eventType || eventType === "unknown") return "기타";
  return eventType;
}

function DisclosuresPage() {
  const navigate = useNavigate();

  const [items, setItems] = useState<Disclosure[]>([]);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [selectedDisclosure, setSelectedDisclosure] = useState<Disclosure | null>(null);
  const [selectedDisclosureIds, setSelectedDisclosureIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [stockId, setStockId] = useState("");
  const [keyword, setKeyword] = useState("");
  const [disclosureType, setDisclosureType] = useState("");
  const [limit, setLimit] = useState("50");
  const [offset, setOffset] = useState("0");

  const [collectStockId, setCollectStockId] = useState("");
  const [collectDays, setCollectDays] = useState("30");
  const [collectPageCount, setCollectPageCount] = useState("100");
  const [collectLoading, setCollectLoading] = useState(false);
  const [collectError, setCollectError] = useState("");
  const [collectResult, setCollectResult] = useState<DisclosureCollectResponse | null>(null);

  const [summarizeLoading, setSummarizeLoading] = useState(false);
  const [summarizeError, setSummarizeError] = useState("");
  const [summarizeResult, setSummarizeResult] = useState<AiSummarizeResponse | null>(null);

  const stockNameMap = useMemo(() => {
    const map = new Map<number, string>();
    stocks.forEach((stock) => map.set(stock.id, `${stock.stock_name} (${stock.stock_code})`));
    return map;
  }, [stocks]);

  const renderStockLabel = (item: Disclosure) => {
    if (item.stock_name && item.stock_code) return `${item.stock_name} (${item.stock_code})`;
    if (item.stock_name) return item.stock_name;
    if (item.stock_code) return item.stock_code;
    if (item.stock_id && stockNameMap.get(item.stock_id)) return stockNameMap.get(item.stock_id) as string;
    return "-";
  };

  const renderStockCell = (item: Disclosure) => {
    if (item.stock_name && item.stock_code) {
      return (
        <div className="stock-cell">
          <strong>{item.stock_name}</strong>
          <span>{item.stock_code}</span>
        </div>
      );
    }
    if (item.stock_name) return <div className="stock-cell"><strong>{item.stock_name}</strong></div>;
    if (item.stock_code) return <div className="stock-cell"><span>{item.stock_code}</span></div>;
    if (item.stock_id && stockNameMap.get(item.stock_id)) {
      return <div className="stock-cell"><strong>{stockNameMap.get(item.stock_id) as string}</strong></div>;
    }
    return "-";
  };

  const loadDisclosures = async (overrides?: { stock_id?: number; offset?: number }) => {
    setLoading(true);
    setError("");
    try {
      const data = await repositories.disclosures.listDisclosures({
        stock_id: overrides?.stock_id ?? (stockId ? Number(stockId) : undefined),
        keyword: keyword || undefined,
        disclosure_type: disclosureType || undefined,
        limit: Number(limit) || 50,
        offset: overrides?.offset ?? (Number(offset) || 0),
      });
      setItems(data);
      setSelectedDisclosure((prev) => {
        if (data.length === 0) return null;
        if (!prev) return data[0];
        const found = data.find((item) => item.id === prev.id);
        return found ?? data[0];
      });
    } catch {
      setError("공시 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const loadStocks = async () => {
    try {
      const data = await repositories.stocks.list();
      setStocks(data);
      if (data.length > 0 && !collectStockId) setCollectStockId(String(data[0].id));
    } catch {
      // ignore stock load errors here
    }
  };

  useEffect(() => {
    loadDisclosures();
    loadStocks();
  }, []);

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    setOffset("0");
    setSelectedDisclosure(null);
    setSelectedDisclosureIds([]);
    await loadDisclosures({ offset: 0 });
  };

  const onReset = async () => {
    setStockId("");
    setKeyword("");
    setDisclosureType("");
    setLimit("50");
    setOffset("0");
    setSelectedDisclosure(null);
    setSelectedDisclosureIds([]);
    setSummarizeError("");
    setSummarizeResult(null);
    setTimeout(() => {
      loadDisclosures({ stock_id: undefined, offset: 0 });
    }, 0);
  };

  const onCollectForStock = async () => {
    if (!collectStockId) {
      setCollectError("종목을 선택해주세요.");
      return;
    }
    setCollectLoading(true);
    setCollectError("");
    setCollectResult(null);
    try {
      const result = await repositories.disclosures.collectDisclosuresForStock({
        stock_id: Number(collectStockId),
        days: Number(collectDays),
        page_count: Number(collectPageCount),
      });
      setCollectResult(result);
      setStockId(String(collectStockId));
      setOffset("0");
      setSelectedDisclosure(null);
      setSelectedDisclosureIds([]);
      await loadDisclosures({ stock_id: Number(collectStockId), offset: 0 });
    } catch (e) {
      const message = e instanceof Error ? e.message : "공시 수집 실행 중 오류가 발생했습니다.";
      setCollectError(message);
    } finally {
      setCollectLoading(false);
    }
  };

  const onCollectForWatchlist = async () => {
    setCollectLoading(true);
    setCollectError("");
    setCollectResult(null);
    try {
      const result = await repositories.disclosures.collectDisclosuresForWatchlist({
        days: Number(collectDays),
        page_count: Number(collectPageCount),
      });
      setCollectResult(result);
      setOffset("0");
      setSelectedDisclosure(null);
      setSelectedDisclosureIds([]);
      await loadDisclosures({ offset: 0 });
    } catch (e) {
      const message = e instanceof Error ? e.message : "관심종목 공시 수집 실행 중 오류가 발생했습니다.";
      setCollectError(message);
    } finally {
      setCollectLoading(false);
    }
  };

  const onSummarizeSelected = async () => {
    if (selectedDisclosureIds.length === 0) return;
    setSummarizeLoading(true);
    setSummarizeError("");
    setSummarizeResult(null);
    try {
      const result = await repositories.disclosures.summarizeSelectedDisclosures(selectedDisclosureIds);
      setSummarizeResult(result);
      setSelectedDisclosureIds([]);
      await loadDisclosures();
    } catch (e) {
      setSummarizeError(e instanceof Error ? e.message : "선택 공시 AI 요약 실행 중 오류가 발생했습니다.");
    } finally {
      setSummarizeLoading(false);
    }
  };

  const unknownRiskCount = useMemo(
    () => items.filter((d) => !d.ai_risk_level || d.ai_risk_level.toLowerCase() === "unknown").length,
    [items],
  );

  const numericOffset = Number(offset) || 0;
  const numericLimit = Number(limit) || 50;
  const canGoPrev = numericOffset > 0;
  const canGoNext = items.length >= numericLimit;

  const currentPageDisclosureIds = useMemo(() => items.map((item) => item.id), [items]);
  const allCurrentPageDisclosuresSelected =
    currentPageDisclosureIds.length > 0 && currentPageDisclosureIds.every((id) => selectedDisclosureIds.includes(id));

  const onToggleSelectAllCurrentPage = () => {
    if (allCurrentPageDisclosuresSelected) {
      setSelectedDisclosureIds((prev) => prev.filter((id) => !currentPageDisclosureIds.includes(id)));
      return;
    }
    setSelectedDisclosureIds((prev) => Array.from(new Set([...prev, ...currentPageDisclosureIds])));
  };

  const onPrevPage = async () => {
    const nextOffset = Math.max(0, numericOffset - numericLimit);
    setOffset(String(nextOffset));
    setSelectedDisclosure(null);
    setSelectedDisclosureIds([]);
    await loadDisclosures({ offset: nextOffset });
  };

  const onNextPage = async () => {
    const nextOffset = numericOffset + numericLimit;
    setOffset(String(nextOffset));
    setSelectedDisclosure(null);
    setSelectedDisclosureIds([]);
    await loadDisclosures({ offset: nextOffset });
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="공시 분석"
        description="공시 이벤트 유형과 리스크 수준을 우선 확인하고, 투자 근거를 정리합니다."
        action={<StatusBadge label={`미분류 리스크 ${unknownRiskCount}건`} tone={unknownRiskCount > 0 ? "amber" : "emerald"} />}
      />

      <SectionCard title="공시 수집 실행">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-6">
          <select className="select-control md:col-span-2" value={collectStockId} onChange={(e) => setCollectStockId(e.target.value)}>
            <option value="">종목 선택</option>
            {stocks.map((s) => (
              <option key={s.id} value={s.id}>{`${s.stock_name} (${s.stock_code})`}</option>
            ))}
          </select>

          <select className="select-control" value={collectDays} onChange={(e) => setCollectDays(e.target.value)}>
            {(codes as any).disclosureCollectDays?.map((d: { value: number; label: string }) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>

          <select className="select-control" value={collectPageCount} onChange={(e) => setCollectPageCount(e.target.value)}>
            {(codes as any).disclosurePageCount?.map((d: { value: number; label: string }) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>

          <button className="btn btn-primary" onClick={onCollectForStock} disabled={collectLoading}>
            {collectLoading ? "수집 중..." : "공시 수집 실행"}
          </button>
          <button className="btn btn-secondary" onClick={onCollectForWatchlist} disabled={collectLoading}>
            관심종목 전체 수집
          </button>
        </div>

        {collectError ? <p className="mt-3 text-sm text-rose-600">{collectError}</p> : null}

        {collectResult ? (
          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
              <div><p className="text-xs text-muted">상태</p><p className="font-semibold">{collectResult.status}</p></div>
              <div><p className="text-xs text-muted">대상</p><p className="font-semibold">{collectResult.target}</p></div>
              <div><p className="text-xs text-muted">수집 건수</p><p className="font-semibold">{collectResult.collected_count}</p></div>
              <div><p className="text-xs text-muted">저장 건수</p><p className="font-semibold">{collectResult.saved_count}</p></div>
              <div><p className="text-xs text-muted">중복 제외 건수</p><p className="font-semibold">{collectResult.skipped_count}</p></div>
              <div className="col-span-2 md:col-span-1"><p className="text-xs text-muted">메시지</p><p className="font-semibold">{collectResult.message}</p></div>
            </div>
            <div className="mt-3">
              <button type="button" className="btn btn-secondary" onClick={() => navigate("/collection-runs")}>수집 이력 확인</button>
            </div>
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="검색">
        <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-7">
          <input className="input-control" placeholder="종목 ID" value={stockId} onChange={(e) => setStockId(e.target.value)} />
          <div className="relative md:col-span-2">
            <Search size={16} className="absolute left-3 top-3.5 text-slate-400" />
            <input className="input-control pl-9" placeholder="keyword" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
          </div>
          <input className="input-control" placeholder="disclosure_type" value={disclosureType} onChange={(e) => setDisclosureType(e.target.value)} />
          <select className="select-control" value={limit} onChange={(e) => setLimit(e.target.value)}>
            <option value="20">20</option>
            <option value="50">50</option>
            <option value="100">100</option>
          </select>
          <input className="input-control" placeholder="offset" value={offset} onChange={(e) => setOffset(e.target.value)} />
          <div className="flex gap-2">
            <button type="submit" className="btn btn-primary">검색</button>
            <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
          </div>
        </form>
      </SectionCard>

      <div className="content-split">
        <SectionCard title="공시 목록" className="list-panel">
          {loading ? <p className="text-sm text-muted">조회 중입니다.</p> : null}
          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          {!loading && !error && items.length === 0 ? <EmptyState message="공시 데이터가 없습니다." /> : null}

          {!loading && !error && items.length > 0 ? (
            <>
              <div className="action-row">
                <div className="action-row-left">
                  <button type="button" className="btn btn-secondary" onClick={onSummarizeSelected} disabled={summarizeLoading || selectedDisclosureIds.length === 0}>
                    {summarizeLoading ? "AI 요약 중..." : `선택 ${selectedDisclosureIds.length}건 AI 요약`}
                  </button>
                </div>
                <div className="action-row-right">
                  <button type="button" className="btn btn-secondary" onClick={() => navigate("/collection-runs")}>수집 이력 확인</button>
                </div>
              </div>

              {summarizeResult ? (
                <div className="inline-result">
                  {summarizeResult.message || "선택 공시 AI 요약이 완료되었습니다."} (처리 {summarizeResult.processed_count ?? 0} / 성공 {summarizeResult.success_count ?? 0} / 실패 {summarizeResult.failed_count ?? 0})
                </div>
              ) : null}
              {summarizeError ? <div className="inline-result inline-error">{summarizeError}</div> : null}

              <div className="table-shell">
                <table className="data-table compact-table min-w-[980px]">
                  <thead>
                    <tr>
                      <th className="selection-cell">
                        <input
                          className="selection-checkbox"
                          type="checkbox"
                          checked={allCurrentPageDisclosuresSelected}
                          onChange={onToggleSelectAllCurrentPage}
                        />
                      </th>
                      <th>ID</th>
                      <th>종목</th>
                      <th>공시 제목</th>
                      <th>공시일</th>
                      <th>이벤트</th>
                      <th>리스크</th>
                      <th>중요도</th>
                      <th>AI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((disclosure) => {
                      const event = eventLabel(disclosure.ai_event_type);
                      const risk = riskMeta(disclosure.ai_risk_level);
                      const importance = importanceMeta(disclosure.ai_importance_score ?? disclosure.importance_score);
                      const selected = selectedDisclosure?.id === disclosure.id || selectedDisclosureIds.includes(disclosure.id);
                      return (
                        <tr
                          key={disclosure.id}
                          className={selected ? "selected-row row-clickable" : "row-clickable"}
                          onClick={() => setSelectedDisclosure(disclosure)}
                        >
                          <td className="selection-cell">
                            <input
                              className="selection-checkbox"
                              type="checkbox"
                              checked={selectedDisclosureIds.includes(disclosure.id)}
                              onClick={(e) => e.stopPropagation()}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedDisclosureIds((prev) => Array.from(new Set([...prev, disclosure.id])));
                                  return;
                                }
                                setSelectedDisclosureIds((prev) => prev.filter((id) => id !== disclosure.id));
                              }}
                            />
                          </td>
                          <td className="cell-nowrap">{disclosure.id}</td>
                          <td>{renderStockCell(disclosure)}</td>
                          <td className="min-w-[320px] cell-title cell-clamp-2">{disclosure.disclosure_title}</td>
                          <td className="cell-nowrap cell-muted">{disclosure.disclosed_at ?? "-"}</td>
                          <td><StatusBadge label={event} variant="event" /></td>
                          <td><StatusBadge label={risk.label} variant={risk.variant} /></td>
                          <td><StatusBadge label={importance.label} variant={importance.variant} /></td>
                          <td>
                            {disclosure.ai_summary ? (
                              <StatusBadge label="완료" tone="emerald" />
                            ) : disclosure.ai_summary_error ? (
                              <StatusBadge label="오류" tone="rose" />
                            ) : (
                              <StatusBadge label="미처리" tone="slate" />
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="pagination-bar">
                <div className="pagination-info">offset {offset} / {items.length}건 조회</div>
                <div className="flex gap-2">
                  <button type="button" className="btn btn-secondary" onClick={onPrevPage} disabled={!canGoPrev}>이전</button>
                  <button type="button" className="btn btn-secondary" onClick={onNextPage} disabled={!canGoNext}>다음</button>
                </div>
              </div>
            </>
          ) : null}
        </SectionCard>

        <SectionCard title="상세 분석" className="detail-panel">
          {!selectedDisclosure ? (
            <EmptyState message="공시를 선택하세요." />
          ) : (
            <>
              <h3 className="detail-title">{selectedDisclosure.disclosure_title}</h3>
              <div className="detail-meta">
                <StatusBadge label={`종목 ${renderStockLabel(selectedDisclosure)}`} tone="blue" />
                <StatusBadge label={eventLabel(selectedDisclosure.ai_event_type)} variant="event" />
                <StatusBadge label={riskMeta(selectedDisclosure.ai_risk_level).label} variant={riskMeta(selectedDisclosure.ai_risk_level).variant} />
                <StatusBadge label={importanceMeta(selectedDisclosure.ai_importance_score ?? selectedDisclosure.importance_score).label} variant={importanceMeta(selectedDisclosure.ai_importance_score ?? selectedDisclosure.importance_score).variant} />
              </div>

              <div className="detail-section">
                <p className="detail-label">기본 정보</p>
                <div className="detail-body">
                  <p>공시 유형: {selectedDisclosure.disclosure_type ?? "-"}</p>
                  <p>공시일: {selectedDisclosure.disclosed_at ?? "-"}</p>
                  <p>수집일: {selectedDisclosure.created_at ?? "-"}</p>
                  <p>AI 처리일시: {selectedDisclosure.ai_processed_at ?? "-"}</p>
                </div>
              </div>

              <div className="detail-section">
                <p className="detail-label">태그</p>
                <div className="flex flex-wrap gap-1">
                  {(selectedDisclosure.ai_tags || "").split(",").map((tag) => tag.trim()).filter(Boolean).map((tag) => (
                    <StatusBadge key={`${selectedDisclosure.id}-${tag}`} label={tag} tone="slate" />
                  ))}
                  {!(selectedDisclosure.ai_tags || "").trim() ? <StatusBadge label="미분류" tone="slate" /> : null}
                </div>
              </div>

              <div className="detail-section">
                <p className="detail-label">AI 요약</p>
                <p className="detail-body">{selectedDisclosure.ai_summary ?? "AI 요약이 없습니다."}</p>
              </div>

              {selectedDisclosure.ai_summary_error ? (
                <div className="detail-section">
                  <p className="detail-label">요약 오류</p>
                  <p className="detail-body text-rose-700">{selectedDisclosure.ai_summary_error}</p>
                </div>
              ) : null}

              <div className="detail-section">
                <p className="detail-label">원문 링크</p>
                {selectedDisclosure.url ? (
                  <a className="btn btn-secondary" href={selectedDisclosure.url} target="_blank" rel="noreferrer">원문 열기</a>
                ) : (
                  <p className="detail-body">원문 링크가 없습니다.</p>
                )}
              </div>
            </>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

export default DisclosuresPage;
