import { useEffect, useMemo, useState } from "react";
import { ClipboardList, Copy, FileQuestion, HelpCircle, ListCollapse, ListTree, Play, RefreshCw, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { WatchlistEvaluationFactor, WatchlistEvaluationHistoryItem, WatchlistEvaluationListItem, WatchlistEvaluationSummary } from "@/types/watchlistEvaluation";

type ActiveFilter = "all" | "active" | "inactive";
type SijeTab = "overall" | "market" | "material" | "supply" | "chart" | "financial" | "gpt" | "history";
type ReasonModal = { title: string; body: string; missing?: string[] } | null;

const TABS: { key: SijeTab; label: string }[] = [
  { key: "overall", label: "종합" },
  { key: "market", label: "시장" },
  { key: "material", label: "재료" },
  { key: "supply", label: "수급" },
  { key: "chart", label: "차트" },
  { key: "financial", label: "재무" },
  { key: "gpt", label: "GPT 판단" },
  { key: "history", label: "평가 이력" },
];

const MISSING_LABELS: Record<string, string> = {
  price: "가격정보",
  chart: "차트",
  market: "시장지표",
  financial: "재무정보",
  supply: "수급",
  "market:DOMESTIC_INDEX_TREND": "국내 지수 흐름",
  "market:MARKET_BREADTH": "시장 체감/폭",
  "market:MARKET_LIQUIDITY": "시장 유동성",
  "market:US_MARKET_TREND": "미국 시장 흐름",
  "market:EXTERNAL_RISK": "외부 위험",
};

const MARKET_STATUS_LABELS: Record<string, string> = {
  EVALUATED: "평가 완료",
  PARTIAL: "일부 데이터 평가",
  DATA_MISSING: "데이터 부족",
  NOT_EVALUATED: "미평가",
  ERROR: "평가 실패",
};

function safeMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "string") return error;
  return fallback;
}

function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return "미평가";
  return `${Math.round(value)}점`;
}

function formatPreciseScore(value: number | null | undefined, suffix = "점"): string {
  if (value === null || value === undefined) return "미수집";
  return `${new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 }).format(value)}${suffix}`;
}

function formatMissing(items: string[]): string {
  if (!items.length) return "없음";
  return items.map((item) => MISSING_LABELS[item] || item).join(", ");
}

function confidenceTone(value: string): "blue" | "emerald" | "slate" | "amber" | "rose" {
  if (value === "ENOUGH") return "emerald";
  if (value === "PARTIAL") return "blue";
  if (value === "LIMITED") return "amber";
  return "slate";
}

function statusTone(value?: string | null): "blue" | "emerald" | "slate" | "amber" | "rose" {
  if (value === "EVALUATED") return "emerald";
  if (value === "PARTIAL") return "blue";
  if (value === "DATA_MISSING") return "amber";
  if (value === "ERROR") return "rose";
  return "slate";
}

function gradeTone(value?: string | null): "blue" | "emerald" | "slate" | "amber" | "rose" {
  if (value === "강한 우호" || value === "우호") return "emerald";
  if (value === "중립") return "blue";
  if (value === "경계") return "amber";
  if (value === "위험") return "rose";
  return "slate";
}

function marketStatusLabel(value?: string | null): string {
  return MARKET_STATUS_LABELS[value || ""] || value || "미평가";
}

function ScoreBlock({
  title,
  score,
  status,
  dataList,
  onReason,
}: {
  title: string;
  score: number | null | undefined;
  status?: string | null;
  dataList: string[];
  onReason: () => void;
}) {
  const empty = score === null || score === undefined;
  return (
    <div className="sije-score-block">
      <div>
        <span className="sije-score-title">{title}</span>
        <strong className={empty ? "muted" : ""}>{formatScore(score)}</strong>
      </div>
      <p>{status || (empty ? "평가 산식 준비중" : "평가 완료")}</p>
      <div className="sije-score-meta">
        <span>사용 데이터: {dataList.length ? dataList.join(", ") : "준비중"}</span>
        <button type="button" className="sije-icon-link" onClick={onReason} title={`${title} 점수 근거`}>
          <FileQuestion size={15} />
          <span>근거</span>
        </button>
      </div>
    </div>
  );
}

function MarketFactorCard({ factor }: { factor: WatchlistEvaluationFactor }) {
  const reflected = factor.contribution_score !== null && factor.contribution_score !== undefined;
  return (
    <div className={`sije-market-factor ${reflected ? "" : "missing"}`}>
      <div className="sije-market-factor-head">
        <strong>{factor.factor_name}</strong>
        <span>{reflected ? `${formatPreciseScore(factor.contribution_score)} / ${formatPreciseScore(factor.weight)}` : "미수집 / 점수 미반영"}</span>
      </div>
      <p>{factor.reason || "해석 문구가 없습니다."}</p>
      <div className="sije-market-factor-meta">
        <span>{factor.raw_value || "사용 가능한 원천 데이터가 없습니다."}</span>
        <small>기준일: {factor.source_date || "-"}</small>
      </div>
    </div>
  );
}

function MarketPanel({ item, onHelp }: { item: WatchlistEvaluationListItem; onHelp: () => void }) {
  const factors = item.market_factors || [];
  return (
    <section className="sije-tab-panel">
      <div className="sije-market-head-card">
        <div>
          <div className="sije-market-title-row">
            <span>시장 평가</span>
            <button type="button" className="sije-icon-link" onClick={onHelp} title="시장 점수 산정 기준">
              <HelpCircle size={15} />
              <span>기준</span>
            </button>
          </div>
          <strong className={item.market_score == null ? "muted" : ""}>{formatScore(item.market_score)}</strong>
          <p>{item.market_summary || "시장 평가 전입니다."}</p>
        </div>
        <div className="sije-market-badge-stack">
          <StatusBadge label={item.market_grade || "미평가"} tone={gradeTone(item.market_grade)} />
          <StatusBadge label={marketStatusLabel(item.market_status)} tone={statusTone(item.market_status)} />
          <StatusBadge label={`신뢰도 ${item.data_confidence}`} tone={confidenceTone(item.data_confidence)} />
          <span>평가 기준일: {item.last_evaluated_at?.slice(0, 10) || "-"}</span>
          <span>미수집: {(item.missing_market_data || []).length.toLocaleString("ko-KR")}개</span>
        </div>
      </div>

      <div className="sije-market-factor-grid">
        {factors.length > 0 ? factors.map((factor) => <MarketFactorCard key={`${factor.factor_code}-${factor.id || factor.factor_name}`} factor={factor} />) : <EmptyState message="시장 평가 factor가 없습니다. 평가를 먼저 실행해 주세요." />}
      </div>
    </section>
  );
}

function WatchlistSijeSuchaJaePage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<WatchlistEvaluationListItem[]>([]);
  const [summary, setSummary] = useState<WatchlistEvaluationSummary | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [keyword, setKeyword] = useState("");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("all");
  const [tab, setTab] = useState<SijeTab>("overall");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [history, setHistory] = useState<WatchlistEvaluationHistoryItem[]>([]);
  const [gptPrompt, setGptPrompt] = useState("");
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [reasonModal, setReasonModal] = useState<ReasonModal>(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const result = await repositories.watchlistEvaluation.list();
      setItems(result.items);
      setSummary(result.summary);
      setSelectedId((prev) => prev ?? result.items[0]?.watchlist_id ?? null);
    } catch (loadError) {
      setError(safeMessage(loadError, "시재수차재 평가 목록을 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const filteredItems = useMemo(() => {
    const needle = keyword.trim().toLowerCase();
    return items.filter((item) => {
      if (activeFilter === "active" && !item.is_active) return false;
      if (activeFilter === "inactive" && item.is_active) return false;
      if (!needle) return true;
      return item.stock_name.toLowerCase().includes(needle) || item.stock_code.toLowerCase().includes(needle);
    });
  }, [activeFilter, items, keyword]);

  const selected = items.find((item) => item.watchlist_id === selectedId) || filteredItems[0] || null;

  useEffect(() => {
    if (!selected) return;
    setHistory([]);
    if (tab !== "history") return;
    void loadHistory(selected.watchlist_id);
  }, [selected?.watchlist_id, tab]);

  const runAction = async (key: string, action: () => Promise<void>) => {
    setActionLoading(key);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (actionError) {
      setError(safeMessage(actionError, "작업 실행 중 오류가 발생했습니다."));
    } finally {
      setActionLoading("");
    }
  };

  const loadHistory = async (watchlistId: number) => {
    try {
      setHistory(await repositories.watchlistEvaluation.history(watchlistId));
    } catch (historyError) {
      setError(safeMessage(historyError, "평가 이력을 불러오지 못했습니다."));
    }
  };

  const evaluateSelected = async () => {
    if (!selected) {
      setError("평가할 관심종목을 선택해 주세요.");
      return;
    }
    await runAction("evaluate-selected", async () => {
      const result = await repositories.watchlistEvaluation.evaluate([selected.watchlist_id]);
      setMessage(`선택 종목 시장 평가 완료: run #${result.run_id}, ${result.evaluated_count}건`);
      await load();
      await loadHistory(selected.watchlist_id);
    });
  };

  const evaluateAll = async () => {
    await runAction("evaluate-all", async () => {
      const result = await repositories.watchlistEvaluation.evaluateAll(true);
      setMessage(`전체 관심종목 시장 평가 완료: run #${result.run_id}, ${result.evaluated_count}건`);
      await load();
      if (selected) await loadHistory(selected.watchlist_id);
    });
  };

  const createPrompt = async () => {
    if (!selected) return;
    await runAction("gpt-prompt", async () => {
      const result = await repositories.watchlistEvaluation.createGptPrompt(selected.watchlist_id);
      setGptPrompt(result.prompt);
      setTab("gpt");
      setMessage("GPT 요청문을 생성했습니다.");
    });
  };

  const copyPrompt = async () => {
    if (!gptPrompt) return;
    await navigator.clipboard.writeText(gptPrompt);
    setMessage("GPT 요청문을 복사했습니다.");
  };

  const openReason = (title: string) => {
    if (title === "시장" && selected) {
      setReasonModal({
        title: "시장 점수 산정 기준",
        missing: selected.missing_market_data || [],
        body:
          "시장 점수는 관심종목을 평가하는 시점의 전체 시장 환경을 100점 만점으로 계산합니다.\n\n반영 영역:\n1. 국내 지수 흐름: 30점\n2. 시장 체감/폭: 20점\n3. 시장 유동성: 15점\n4. 미국 시장 흐름: 20점\n5. 외부 위험: 15점\n\n국내 지수 흐름은 KOSPI/KOSDAQ의 20일선, 60일선 위치와 최근 등락률을 반영합니다. 시장 체감/폭은 상승·하락 종목 수가 없으면 KOSPI/KOSDAQ 등락률 평균을 대체 지표로 사용합니다. 아직 수집되지 않은 데이터는 0점 처리하지 않고 점수 계산에서 제외합니다.",
      });
      return;
    }
    setReasonModal({
      title: `${title} 점수 근거`,
      body: "이번 단계에서는 시장 탭만 실제 산식과 연결했습니다. 재료·수급·차트·재무 점수는 다음 단계까지 미평가 상태로 유지합니다.",
    });
  };

  return (
    <div className="sije-page">
      <PageHeader title="관심 종목 시재수차재" description="관심종목의 시장·재료·수급·차트·재무 상태를 평가하고 평가 이력을 관리합니다." />

      {summary ? (
        <div className="sije-summary-grid">
          <div><span>관심종목</span><strong>{summary.watchlist_count.toLocaleString("ko-KR")}</strong></div>
          <div><span>활성</span><strong>{summary.active_count.toLocaleString("ko-KR")}</strong></div>
          <div><span>비활성</span><strong>{summary.inactive_count.toLocaleString("ko-KR")}</strong></div>
          <div><span>평가 완료</span><strong>{summary.evaluated_count.toLocaleString("ko-KR")}</strong></div>
          <div><span>미평가</span><strong>{summary.not_evaluated_count.toLocaleString("ko-KR")}</strong></div>
          <div><span>데이터 부족</span><strong>{summary.missing_data_count.toLocaleString("ko-KR")}</strong></div>
        </div>
      ) : null}

      <div className="sije-action-bar">
        <button className="btn btn-primary" type="button" onClick={() => void evaluateSelected()} disabled={!selected || Boolean(actionLoading)}><Play size={16} /> 선택 종목 평가</button>
        <button className="btn btn-secondary" type="button" onClick={() => void evaluateAll()} disabled={Boolean(actionLoading)}><RefreshCw size={16} /> 전체 관심종목 평가</button>
        <button className="btn btn-secondary" type="button" onClick={() => void createPrompt()} disabled={!selected || Boolean(actionLoading)}><ClipboardList size={16} /> GPT 요청문 생성</button>
        <button className="btn btn-secondary" type="button" onClick={() => navigate("/watchlist")}>관심종목 화면으로 이동</button>
      </div>

      {message ? <div className="inline-result inline-success">{message}</div> : null}
      {error ? <div className="inline-result inline-error">{error}</div> : null}

      <div className={`sije-layout ${panelCollapsed ? "collapsed" : ""}`}>
        <aside className="sije-stock-list-panel">
          <div className="sije-panel-head">
            <strong>관심종목</strong>
            <button type="button" className="sije-icon-button" onClick={() => setPanelCollapsed((value) => !value)} title={panelCollapsed ? "목록 펼치기" : "목록 접기"}>{panelCollapsed ? <ListTree size={17} /> : <ListCollapse size={17} />}</button>
          </div>
          {!panelCollapsed ? (
            <>
              <div className="sije-search-row"><Search size={16} /><input className="input-control" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="종목명 또는 코드" /></div>
              <div className="sije-filter-row">
                {(["all", "active", "inactive"] as ActiveFilter[]).map((value) => <button key={value} type="button" className={activeFilter === value ? "active" : ""} onClick={() => setActiveFilter(value)}>{value === "all" ? "전체" : value === "active" ? "활성" : "비활성"}</button>)}
              </div>
              {loading ? <p className="text-sm text-muted">목록 로딩 중입니다.</p> : null}
              {!loading && filteredItems.length === 0 ? <EmptyState message="조회된 관심종목이 없습니다." /> : null}
              <div className="sije-stock-list">
                {filteredItems.map((item) => (
                  <button key={item.watchlist_id} type="button" className={`sije-stock-card ${selected?.watchlist_id === item.watchlist_id ? "selected" : ""}`} onClick={() => { setSelectedId(item.watchlist_id); setGptPrompt(""); }}>
                    <strong>{item.stock_name}</strong>
                    <span>{item.stock_code} · {item.market || "-"}</span>
                    <small>{item.total_score === null ? "종합: 미평가" : `종합 ${item.total_score}점`}</small>
                    <small>시장: {formatScore(item.market_score)}{item.market_grade ? ` · ${item.market_grade}` : ""}</small>
                    <em>{(item.missing_market_data || []).length ? "시장 데이터 일부 누락" : item.missing_data.length ? "데이터 일부 누락" : "데이터 준비"}</em>
                  </button>
                ))}
              </div>
            </>
          ) : null}
        </aside>

        <main className="sije-main-panel">
          {!selected ? <EmptyState message="평가할 관심종목을 선택해 주세요." /> : null}
          {selected ? (
            <>
              <section className="sije-stock-header">
                <div>
                  <h2>{selected.stock_name} 분석</h2>
                  <p>{selected.stock_code} · {selected.market || "-"} · 관심종목 {selected.is_active ? "활성" : "비활성"}</p>
                  <div className="sije-header-badges">
                    <StatusBadge label={selected.last_evaluated_at ? `최근 평가 ${selected.last_evaluated_at}` : "최근 평가 미평가"} tone="slate" />
                    <StatusBadge label={`시장 ${formatScore(selected.market_score)}`} tone={gradeTone(selected.market_grade)} />
                    <StatusBadge label={`데이터 상태: ${formatMissing(selected.missing_data)}`} tone={selected.missing_data.length ? "amber" : "emerald"} />
                    <StatusBadge label={selected.data_confidence} tone={confidenceTone(selected.data_confidence)} />
                  </div>
                </div>
                <div className="sije-total-score"><span>종합점수</span><strong className={selected.total_score === null ? "muted" : ""}>{formatScore(selected.total_score)}</strong></div>
              </section>

              <div className="sije-tabs">{TABS.map((item) => <button key={item.key} type="button" className={tab === item.key ? "active" : ""} onClick={() => setTab(item.key)}>{item.label}</button>)}</div>

              {tab === "overall" ? (
                <section className="sije-tab-panel">
                  <div className="sije-score-grid">
                    <ScoreBlock title="시장" score={selected.market_score} status={`${selected.market_grade || "미평가"} · ${marketStatusLabel(selected.market_status)}`} dataList={["KOSPI/KOSDAQ", "시장지표", "미국지수", "환율/금리"]} onReason={() => openReason("시장")} />
                    <ScoreBlock title="재료" score={selected.material_score} dataList={["뉴스", "공시", "테마"]} onReason={() => openReason("재료")} />
                    <ScoreBlock title="수급" score={selected.supply_score} status="기관·외국인 수급 미수집" dataList={["거래대금", "테마 흐름"]} onReason={() => openReason("수급")} />
                    <ScoreBlock title="차트" score={selected.chart_score} dataList={["일봉", "이동평균", "거래대금"]} onReason={() => openReason("차트")} />
                    <ScoreBlock title="재무" score={selected.financial_score} status="재무정보 준비중" dataList={[]} onReason={() => openReason("재무")} />
                  </div>
                  <div className="sije-note">{selected.market_summary || "시장 평가를 실행하면 종합 탭에 시장 요약이 반영됩니다."}</div>
                </section>
              ) : null}

              {tab === "market" ? <MarketPanel item={selected} onHelp={() => openReason("시장")} /> : null}

              {["material", "supply", "chart", "financial"].includes(tab) ? (
                <section className="sije-tab-panel">
                  <ScoreBlock title={TABS.find((item) => item.key === tab)?.label || ""} score={selected[`${tab}_score` as keyof WatchlistEvaluationListItem] as number | null} status={tab === "financial" ? "재무정보 준비중" : tab === "supply" ? "기관·외국인 수급 미수집" : "다음 단계에서 연결 예정"} dataList={tab === "financial" ? [] : ["기존 수집 데이터"]} onReason={() => openReason(TABS.find((item) => item.key === tab)?.label || "")} />
                </section>
              ) : null}

              {tab === "gpt" ? (
                <section className="sije-tab-panel"><div className="sije-gpt-panel"><textarea className="textarea-control" value={gptPrompt} readOnly placeholder="GPT 요청문 생성 버튼을 누르면 현재 선택 종목의 평가 패키지가 생성됩니다." /><button className="btn btn-secondary" type="button" disabled={!gptPrompt} onClick={() => void copyPrompt()}><Copy size={16} /> 복사</button></div></section>
              ) : null}

              {tab === "history" ? (
                <section className="sije-tab-panel">
                  {history.length === 0 ? <EmptyState message="평가 이력이 없습니다." /> : null}
                  {history.length > 0 ? (
                    <div className="table-shell"><table className="data-table compact-table"><thead><tr><th>평가일</th><th>Run</th><th>시장</th><th>재료</th><th>수급</th><th>차트</th><th>재무</th><th>종합</th><th>데이터 상태</th></tr></thead><tbody>{history.map((item) => <tr key={item.score_id}><td>{item.evaluated_at}</td><td>{item.run_type} #{item.run_id}</td><td>{formatScore(item.market_score)}{item.market_grade ? ` · ${item.market_grade}` : ""}</td><td>{formatScore(item.material_score)}</td><td>{formatScore(item.supply_score)}</td><td>{formatScore(item.chart_score)}</td><td>{formatScore(item.financial_score)}</td><td>{formatScore(item.total_score)}</td><td>{marketStatusLabel(item.market_status)} · {item.data_confidence}</td></tr>)}</tbody></table></div>
                  ) : null}
                </section>
              ) : null}
            </>
          ) : null}
        </main>
      </div>

      {reasonModal ? (
        <div className="modal-backdrop" onClick={() => setReasonModal(null)}>
          <div className="modal-card sije-reason-modal" onClick={(event) => event.stopPropagation()}>
            <div className="trade-journal-detail-header"><h3>{reasonModal.title}</h3><button className="btn btn-secondary btn-table-sm" type="button" onClick={() => setReasonModal(null)}>닫기</button></div>
            <p>{reasonModal.body}</p>
            {reasonModal.missing ? <div className="sije-modal-missing"><strong>현재 미수집/미반영 항목</strong>{reasonModal.missing.length ? <ul>{reasonModal.missing.map((item) => <li key={item}>{item}</li>)}</ul> : <span>없음</span>}</div> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default WatchlistSijeSuchaJaePage;