import { type KeyboardEvent, useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { TradeJournal, TradeMethod, TradeMethodGptGuidePackage } from "@/types/tradeJournal";

type ActiveFilter = "all" | "active" | "inactive";
type DetailMode = "view" | "create" | "edit";

type MethodDetailForm = {
  method_name: string;
  core_concept: string;
  entry_conditions: string;
  exit_conditions: string;
  failure_patterns: string;
  checklist: string;
  market_conditions: string[];
  sort_order: number;
  is_active: boolean;
};

type MethodStats = {
  trade_count: number;
  profit_count: number;
  loss_count: number;
  win_rate: number;
  avg_profit_rate: number;
  realized_profit_sum: number;
  recent_trades: TradeJournal[];
};

const MARKET_TAG_OPTIONS = ["급등주", "눌림목", "하락반등", "테마주", "반도체", "장시작"];

const defaultForm = (): MethodDetailForm => ({
  method_name: "",
  core_concept: "",
  entry_conditions: "",
  exit_conditions: "",
  failure_patterns: "",
  checklist: "",
  market_conditions: [],
  sort_order: 0,
  is_active: true,
});

const parseMethodMeta = (description?: string | null): { coreConcept: string; marketConditions: string[] } => {
  const raw = (description || "").trim();
  if (!raw) return { coreConcept: "", marketConditions: [] };
  const match = raw.match(/\[시장환경\]\s*(.+)$/);
  if (!match) return { coreConcept: raw, marketConditions: [] };
  const tags = match[1]
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
  const coreConcept = raw.replace(match[0], "").trim();
  return { coreConcept, marketConditions: tags };
};

const buildDescription = (coreConcept: string, marketConditions: string[]): string | undefined => {
  const concept = coreConcept.trim();
  const tags = marketConditions.map((tag) => tag.trim()).filter(Boolean);
  if (!concept && tags.length === 0) return undefined;
  if (tags.length === 0) return concept || undefined;
  return `${concept}${concept ? "\n" : ""}[시장환경] ${tags.join(", ")}`;
};

const normalizeText = (value: string): string | undefined => value.trim() || undefined;

const normalizeTags = (tags: string[]): string[] => {
  const merged = tags.join(" ");
  return merged
    .split(/[\s,\n]+/)
    .map((tag) => tag.trim())
    .filter(Boolean);
};

const formatRate = (value?: number | null): string => `${Number(value ?? 0).toFixed(1)}%`;
const formatWon = (value?: number | null): string => `${Number(value ?? 0).toLocaleString("ko-KR")}원`;
const formatRateCell = (value?: number | null): string => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${Number(value).toFixed(1)}%`;
};
const formatWonCell = (value?: number | null): string => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${Number(value).toLocaleString("ko-KR")}원`;
};
const formatResult = (value?: string | null): string => {
  if (value === "profit") return "익절";
  if (value === "loss") return "손절";
  if (value === "break_even") return "본전";
  return "보유중";
};

const parseLines = (value?: string | null): string[] =>
  (value || "")
    .split("\n")
    .map((line) => line.replace(/^\s*[-*]\s*/, "").trim())
    .filter(Boolean);

function TradeMethodsPage() {
  const [items, setItems] = useState<TradeMethod[]>([]);
  const [keyword, setKeyword] = useState("");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("active");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [selectedMethodId, setSelectedMethodId] = useState<number | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailMode, setDetailMode] = useState<DetailMode>("create");
  const [detailForm, setDetailForm] = useState<MethodDetailForm>(defaultForm());
  const [statsByMethod, setStatsByMethod] = useState<Record<number, MethodStats>>({});
  const [guidePackage, setGuidePackage] = useState<TradeMethodGptGuidePackage | null>(null);
  const [guideLoading, setGuideLoading] = useState(false);

  const safeItems = useMemo(() => (Array.isArray(items) ? items : []), [items]);

  const selectedMethod = useMemo(
    () => items.find((item) => item.id === selectedMethodId) ?? null,
    [items, selectedMethodId]
  );
  const selectedStats = selectedMethodId ? statsByMethod[selectedMethodId] : undefined;

  const summaryStats = useMemo(() => {
    const activeMethodCount = safeItems.filter((item) => Number(item.is_active) === 1).length;
    const totalTrades = Object.values(statsByMethod).reduce((acc, stat) => acc + Number(stat.trade_count || 0), 0);
    const avgWinRate =
      safeItems.length > 0
        ? safeItems.reduce((acc, item) => acc + Number(statsByMethod[item.id]?.win_rate ?? 0), 0) / safeItems.length
        : 0;
    const totalRealizedProfit = Object.values(statsByMethod).reduce(
      (acc, stat) => acc + Number(stat.realized_profit_sum || 0),
      0
    );
    return { activeMethodCount, totalTrades, avgWinRate, totalRealizedProfit };
  }, [safeItems, statsByMethod]);

  const marketTags = normalizeTags(detailForm.market_conditions);

  const setFormField = <K extends keyof MethodDetailForm>(key: K, value: MethodDetailForm[K]) => {
    setDetailForm((prev) => ({ ...prev, [key]: value }));
  };

  const loadStatsForMethod = async (methodId: number): Promise<MethodStats> => {
    const result = await repositories.tradeJournals.fetchTradeJournals({
      start_date: "2000-01-01",
      end_date: "2099-12-31",
      trade_method_id: methodId,
    });
    const rows = result.items ?? [];
    const trade_count = rows.length;
    const profit_count = rows.filter((row) => row.result_type === "profit").length;
    const loss_count = rows.filter((row) => row.result_type === "loss").length;
    const win_rate = trade_count > 0 ? (profit_count / trade_count) * 100 : 0;
    const avg_profit_rate =
      trade_count > 0 ? rows.reduce((acc, row) => acc + Number(row.profit_rate ?? 0), 0) / trade_count : 0;
    const realized_profit_sum = rows.reduce((acc, row) => acc + Number(row.realized_profit ?? 0), 0);
    const recent_trades = [...rows]
      .sort((a, b) => `${b.buy_date}-${b.id}`.localeCompare(`${a.buy_date}-${a.id}`))
      .slice(0, 10);
    return {
      trade_count,
      profit_count,
      loss_count,
      win_rate,
      avg_profit_rate,
      realized_profit_sum,
      recent_trades,
    };
  };

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const isActive = activeFilter === "all" ? undefined : activeFilter === "active" ? 1 : 0;
      const rows = await repositories.tradeJournals.listTradeMethods({
        keyword: keyword.trim() || undefined,
        is_active: isActive,
      });
      setItems(rows);
      const statsEntries = await Promise.all(rows.map(async (item) => [item.id, await loadStatsForMethod(item.id)] as const));
      setStatsByMethod(Object.fromEntries(statsEntries));
    } catch (e) {
      setError(e instanceof Error ? e.message : "매매기법 목록 조회에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const openCreate = () => {
    setSelectedMethodId(null);
    setDetailMode("create");
    setDetailForm(defaultForm());
    setGuidePackage(null);
    setIsDetailOpen(true);
    setMessage("");
    setError("");
  };

  const openEdit = (item: TradeMethod) => {
    if (selectedMethodId === item.id && isDetailOpen) {
      setSelectedMethodId(null);
      setGuidePackage(null);
      setIsDetailOpen(false);
      return;
    }
    const parsed = parseMethodMeta(item.description);
    setSelectedMethodId(item.id);
    setDetailMode("view");
    setDetailForm({
      method_name: item.method_name || "",
      core_concept: parsed.coreConcept,
      entry_conditions: item.entry_rule || "",
      exit_conditions: item.exit_rule || "",
      failure_patterns: item.stop_loss_rule || "",
      checklist: item.take_profit_rule || "",
      market_conditions: parsed.marketConditions,
      sort_order: item.sort_order || 0,
      is_active: item.is_active === 1,
    });
    setGuidePackage(null);
    setIsDetailOpen(true);
    setMessage("");
    setError("");
  };

  const startEditMode = () => {
    if (!selectedMethod) return;
    setDetailMode("edit");
  };

  const closeDetail = () => {
    setIsDetailOpen(false);
    setSelectedMethodId(null);
    setGuidePackage(null);
  };

  const onSubmit = async () => {
    setMessage("");
    setError("");
    if (!detailForm.method_name.trim()) {
      setError("매매기법명을 입력해 주세요.");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        method_name: detailForm.method_name.trim(),
        description: buildDescription(detailForm.core_concept, detailForm.market_conditions),
        entry_rule: normalizeText(detailForm.entry_conditions),
        exit_rule: normalizeText(detailForm.exit_conditions),
        stop_loss_rule: normalizeText(detailForm.failure_patterns),
        take_profit_rule: normalizeText(detailForm.checklist),
        sort_order: Number(detailForm.sort_order) || 0,
        is_active: detailForm.is_active,
      };
      if (detailMode === "create") {
        await repositories.tradeJournals.createTradeMethod(payload);
        setMessage("매매기법을 등록했습니다.");
        await load();
      } else if (selectedMethodId) {
        await repositories.tradeJournals.updateTradeMethod(selectedMethodId, payload);
        setMessage("매매기법을 수정했습니다.");
        await load();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async () => {
    if (!selectedMethodId || detailMode !== "edit") return;
    try {
      await repositories.tradeJournals.updateTradeMethod(selectedMethodId, { is_active: !detailForm.is_active });
      setMessage("매매기법 상태가 변경되었습니다.");
      setDetailForm((prev) => ({ ...prev, is_active: !prev.is_active }));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "상태 변경에 실패했습니다.");
    }
  };

  const createGuidePackage = async () => {
    if (!selectedMethodId || detailMode !== "edit") return;
    setGuideLoading(true);
    setError("");
    try {
      const pkg = await repositories.tradeJournals.fetchTradeMethodGuidePackage(selectedMethodId);
      setGuidePackage(pkg);
      setMessage("GPT 기법 개선 가이드를 생성했습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "가이드 패키지 생성에 실패했습니다.");
    } finally {
      setGuideLoading(false);
    }
  };

  const copyGuidePackage = async () => {
    if (!guidePackage?.markdown) {
      setError("복사할 가이드 내용이 없습니다.");
      return;
    }
    try {
      await navigator.clipboard.writeText(guidePackage.markdown);
      setMessage("GPT 기법 개선 가이드가 복사되었습니다.");
    } catch {
      setError("클립보드 복사에 실패했습니다.");
    }
  };

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    void load();
  };

  return (
    <div className="space-y-4">
      <PageHeader title="매매기법" description="주력 매매기법을 정리하고 반복 훈련을 위한 가이드를 준비합니다." />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <SectionCard title="활성 기법">
          <p className="text-2xl font-semibold text-slate-900">{summaryStats.activeMethodCount}개</p>
        </SectionCard>
        <SectionCard title="총 거래">
          <p className="text-2xl font-semibold text-slate-900">{summaryStats.totalTrades}건</p>
        </SectionCard>
        <SectionCard title="평균 승률">
          <p className="text-2xl font-semibold text-slate-900">{formatRate(summaryStats.avgWinRate)}</p>
        </SectionCard>
        <SectionCard title="누적 손익">
          <p className="text-2xl font-semibold text-slate-900">{formatWon(summaryStats.totalRealizedProfit)}</p>
        </SectionCard>
      </div>

      <SectionCard title="검색">
        <div className="trade-method-search-row">
          <input
            className="input-control trade-method-search-input"
            placeholder="매매기법명/핵심개념 검색"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={handleSearchKeyDown}
          />
          <select className="select-control trade-method-status-select" value={activeFilter} onChange={(e) => setActiveFilter(e.target.value as ActiveFilter)}>
            <option value="all">전체</option>
            <option value="active">활성</option>
            <option value="inactive">비활성</option>
          </select>
          <button type="button" className="btn btn-primary trade-method-search-button" onClick={() => void load()} disabled={loading}>
            {loading ? "조회 중..." : "조회"}
          </button>
          <button type="button" className="btn btn-secondary trade-method-create-button" onClick={openCreate}>
            + 새 매매기법
          </button>
        </div>
        {message ? <p className="mt-2 text-sm text-emerald-700">{message}</p> : null}
        {error ? <p className="mt-2 text-sm text-rose-700">{error}</p> : null}
      </SectionCard>

      <div className="trade-method-layout">
        <SectionCard title="매매기법 목록">
          <div className="trade-method-card-list">
            {safeItems.map((item) => {
              const parsed = parseMethodMeta(item.description);
              const stats = statsByMethod[item.id];
              const selected = isDetailOpen && selectedMethodId === item.id && (detailMode === "view" || detailMode === "edit");
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`trade-method-card ${selected ? "selected" : ""}`}
                  onClick={() => openEdit(item)}
                >
                  <div className="trade-method-card-header">
                    <h3>{item.method_name}</h3>
                    <span className={`badge ${item.is_active ? "badge-emerald" : "badge-slate"}`}>
                      {item.is_active ? "활성" : "비활성"}
                    </span>
                  </div>
                  {parsed.marketConditions.length > 0 ? (
                    <div className="trade-method-tag-list">
                      {parsed.marketConditions.slice(0, 3).map((tag) => (
                        <span key={`${item.id}-${tag}`} className="trade-method-tag active">{tag}</span>
                      ))}
                    </div>
                  ) : null}
                  <p className="trade-method-card-concept">{parsed.coreConcept || "핵심 개념이 없습니다."}</p>
                  <div className="trade-method-card-stats">
                    <span>거래 {stats?.trade_count ?? 0}건</span>
                    <span>승률 {formatRate(stats?.win_rate)}</span>
                    <span>평균 {formatRate(stats?.avg_profit_rate)}</span>
                    <span>누적 {formatWon(stats?.realized_profit_sum)}</span>
                  </div>
                </button>
              );
            })}
            {safeItems.length === 0 ? <p className="text-sm text-slate-500">등록된 매매기법이 없습니다.</p> : null}
          </div>
        </SectionCard>

        {isDetailOpen ? (
          <>
            <div className="trade-journal-detail-dim" onClick={closeDetail} />
            <aside className="trade-journal-detail-drawer">
              <div className="trade-journal-detail-drawer-header">
                <div>
                  <h3>{detailMode === "create" ? "새 매매기법" : detailForm.method_name || "매매기법 상세"}</h3>
                  <span className={`badge mt-1 inline-flex ${detailForm.is_active ? "badge-emerald" : "badge-slate"}`}>
                    {detailForm.is_active ? "활성" : "비활성"}
                  </span>
                </div>
                <button type="button" className="btn btn-secondary" onClick={closeDetail}>
                  닫기
                </button>
              </div>

              <div className="trade-journal-detail-drawer-body space-y-4">
                {detailMode === "view" && selectedMethod ? (
                  <>
                    <div className="detail-section">
                      <h4 className="detail-label mb-2">기본 정보</h4>
                      <div className="space-y-2 text-sm text-slate-700">
                        <p><b>기법명:</b> {selectedMethod.method_name || "-"}</p>
                        <p><b>핵심 개념:</b> {parseMethodMeta(selectedMethod.description).coreConcept || "등록된 핵심 개념이 없습니다."}</p>
                        <p><b>시장 환경:</b> {parseMethodMeta(selectedMethod.description).marketConditions.join(", ") || "등록된 시장 환경 태그가 없습니다."}</p>
                      </div>
                    </div>
                    <div className="detail-section">
                      <h4 className="detail-label mb-2">성과 요약</h4>
                      <div className="trade-method-stats-grid">
                        <div className="rounded border border-slate-200 bg-white p-3"><p className="text-xs text-slate-500">거래 수</p><strong>{selectedStats?.trade_count ?? 0}건</strong></div>
                        <div className="rounded border border-slate-200 bg-white p-3"><p className="text-xs text-slate-500">승률</p><strong>{formatRate(selectedStats?.win_rate)}</strong></div>
                        <div className="rounded border border-slate-200 bg-white p-3"><p className="text-xs text-slate-500">평균 수익률</p><strong>{formatRate(selectedStats?.avg_profit_rate)}</strong></div>
                        <div className="rounded border border-slate-200 bg-white p-3"><p className="text-xs text-slate-500">누적 손익</p><strong>{formatWon(selectedStats?.realized_profit_sum)}</strong></div>
                      </div>
                    </div>
                    <div className="detail-section">
                      <h4 className="detail-label mb-2">진입 조건</h4>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                        {parseLines(selectedMethod.entry_rule).length > 0 ? parseLines(selectedMethod.entry_rule).map((line, idx) => <li key={`entry-${idx}`}>{line}</li>) : <li>등록된 진입 조건이 없습니다.</li>}
                      </ul>
                    </div>
                    <div className="detail-section">
                      <h4 className="detail-label mb-2">청산 조건</h4>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                        {parseLines(selectedMethod.exit_rule).length > 0 ? parseLines(selectedMethod.exit_rule).map((line, idx) => <li key={`exit-${idx}`}>{line}</li>) : <li>등록된 청산 조건이 없습니다.</li>}
                      </ul>
                    </div>
                    <div className="detail-section">
                      <h4 className="detail-label mb-2">실패 패턴</h4>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                        {parseLines(selectedMethod.stop_loss_rule).length > 0 ? parseLines(selectedMethod.stop_loss_rule).map((line, idx) => <li key={`failure-${idx}`}>{line}</li>) : <li>등록된 실패 패턴이 없습니다.</li>}
                      </ul>
                    </div>
                    <div className="detail-section">
                      <h4 className="detail-label mb-2">체크리스트</h4>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                        {parseLines(selectedMethod.take_profit_rule).length > 0 ? parseLines(selectedMethod.take_profit_rule).map((line, idx) => <li key={`check-${idx}`}>{line}</li>) : <li>등록된 체크리스트가 없습니다.</li>}
                      </ul>
                    </div>
                  </>
                ) : null}

                {detailMode !== "view" ? (
                <>
                <div className="detail-section">
                  <h4 className="detail-label mb-2">매매기법 정의</h4>
                  <div className="trade-detail-form-grid">
                    <div className="trade-detail-field">
                      <label className="detail-label">기법명</label>
                      <input className="input-control" value={detailForm.method_name} onChange={(e) => setFormField("method_name", e.target.value)} />
                    </div>
                    <div className="trade-detail-field">
                      <label className="detail-label">정렬순서</label>
                      <input
                        className="input-control"
                        type="number"
                        value={detailForm.sort_order}
                        onChange={(e) => setFormField("sort_order", Number(e.target.value) || 0)}
                      />
                    </div>
                    <div className="trade-detail-field md:col-span-2">
                      <label className="detail-label">핵심 개념</label>
                      <input className="input-control" value={detailForm.core_concept} onChange={(e) => setFormField("core_concept", e.target.value)} />
                    </div>
                    <div className="trade-detail-field md:col-span-2">
                      <label className="detail-label">설명</label>
                      <textarea
                        className="textarea-control"
                        rows={2}
                        value={buildDescription(detailForm.core_concept, detailForm.market_conditions) ?? ""}
                        readOnly
                      />
                    </div>
                  </div>
                </div>

                <div className="detail-section">
                  <h4 className="detail-label mb-2">조건 관리</h4>
                  <div className="space-y-3">
                    <div>
                      <label className="detail-label">진입 조건</label>
                      <textarea
                        className="textarea-control"
                        rows={4}
                        value={detailForm.entry_conditions}
                        onChange={(e) => setFormField("entry_conditions", e.target.value)}
                        placeholder="예: 거래대금 500억 이상, 주도 테마, 눌림목, 이평선 지지, 전고점 돌파"
                      />
                    </div>
                    <div>
                      <label className="detail-label">청산 조건</label>
                      <textarea
                        className="textarea-control"
                        rows={4}
                        value={detailForm.exit_conditions}
                        onChange={(e) => setFormField("exit_conditions", e.target.value)}
                        placeholder="예: 목표 수익률 도달, 기준선 이탈, 거래량 급감, 손절 기준 도달"
                      />
                    </div>
                    <div>
                      <label className="detail-label">실패 패턴</label>
                      <textarea
                        className="textarea-control"
                        rows={4}
                        value={detailForm.failure_patterns}
                        onChange={(e) => setFormField("failure_patterns", e.target.value)}
                        placeholder="예: 돌파 후 거래량 감소, 윗꼬리 출현, 시장 주도주 교체"
                      />
                    </div>
                    <div>
                      <label className="detail-label">체크리스트</label>
                      <textarea
                        className="textarea-control"
                        rows={4}
                        value={detailForm.checklist}
                        onChange={(e) => setFormField("checklist", e.target.value)}
                        placeholder="예: 시장 흐름 확인, 테마 강도 확인, 손절선 설정, 분할매수 여부 확인"
                      />
                    </div>
                    <div>
                      <label className="detail-label">시장 환경 태그</label>
                      <div className="mb-2 flex flex-wrap gap-2">
                        {MARKET_TAG_OPTIONS.map((tag) => {
                          const active = marketTags.includes(tag);
                          return (
                            <button
                              key={tag}
                              type="button"
                              className={`chip ${active ? "chip-active" : ""}`}
                              onClick={() => {
                                const next = active ? marketTags.filter((x) => x !== tag) : [...marketTags, tag];
                                setFormField("market_conditions", next);
                              }}
                            >
                              {tag}
                            </button>
                          );
                        })}
                      </div>
                      {marketTags.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {marketTags.map((tag) => (
                            <span key={`badge-${tag}`} className="badge badge-slate">
                              {tag}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-slate-500">선택된 시장 환경 태그가 없습니다.</p>
                      )}
                    </div>
                  </div>
                </div>
                </>
                ) : null}

                {detailMode === "edit" && selectedMethodId ? (
                  <div className="detail-section">
                    <h4 className="detail-label mb-2">성과 요약</h4>
                    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                      <div className="rounded border border-slate-200 bg-white p-3">
                        <p className="text-xs text-slate-500">거래 수</p>
                        <strong>{statsByMethod[selectedMethodId]?.trade_count ?? 0}건</strong>
                      </div>
                      <div className="rounded border border-slate-200 bg-white p-3">
                        <p className="text-xs text-slate-500">승률</p>
                        <strong>{formatRate(statsByMethod[selectedMethodId]?.win_rate)}</strong>
                      </div>
                      <div className="rounded border border-slate-200 bg-white p-3">
                        <p className="text-xs text-slate-500">평균 수익률</p>
                        <strong>{formatRate(statsByMethod[selectedMethodId]?.avg_profit_rate)}</strong>
                      </div>
                      <div className="rounded border border-slate-200 bg-white p-3">
                        <p className="text-xs text-slate-500">누적 손익</p>
                        <strong>{formatWon(statsByMethod[selectedMethodId]?.realized_profit_sum)}</strong>
                      </div>
                    </div>
                  </div>
                ) : null}

                {detailMode === "edit" && selectedMethodId ? (
                  <div className="detail-section">
                    <h4 className="detail-label mb-1">최근 매매일지 · 최신순 최대 10건</h4>
                    <p className="mb-2 text-xs text-slate-500">
                      현재 매매기법으로 기록된 매매일지를 최신순으로 최대 10건 표시합니다.
                    </p>
                    <div className="method-journal-grid-wrap">
                      <div className="method-journal-grid">
                        <div className="method-journal-grid-header">
                          <div className="method-journal-grid-cell">매수일</div>
                          <div className="method-journal-grid-cell">종목명</div>
                          <div className="method-journal-grid-cell method-journal-grid-cell--center">상태</div>
                          <div className="method-journal-grid-cell method-journal-grid-cell--right">수익률</div>
                          <div className="method-journal-grid-cell method-journal-grid-cell--right">실현손익</div>
                        </div>

                        {(statsByMethod[selectedMethodId]?.recent_trades ?? []).map((trade) => (
                          <div key={trade.id} className="method-journal-grid-row">
                            <div className="method-journal-grid-cell">{trade.buy_date || "-"}</div>
                            <div className="method-journal-grid-cell">{trade.stock_name || "-"}</div>
                            <div className="method-journal-grid-cell method-journal-grid-cell--center">
                              <span className={`badge ${trade.result_type === "profit" ? "badge-rose" : trade.result_type === "loss" ? "badge-blue" : "badge-slate"}`}>
                                {formatResult(trade.result_type)}
                              </span>
                            </div>
                            <div className="method-journal-grid-cell method-journal-grid-cell--right">{formatRateCell(trade.profit_rate)}</div>
                            <div className="method-journal-grid-cell method-journal-grid-cell--right">{formatWonCell(trade.realized_profit)}</div>
                          </div>
                        ))}
                      </div>
                      {(statsByMethod[selectedMethodId]?.recent_trades ?? []).length === 0 ? (
                        <div className="rounded border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
                          이 매매기법으로 기록된 매매일지가 없습니다.
                        </div>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                {detailMode === "edit" ? (
                  <div className="detail-section">
                    <h4 className="detail-label mb-2">GPT 기법 개선 가이드</h4>
                    <p className="mb-2 text-sm text-slate-600">
                      이 매매기법으로 기록된 매매일지를 바탕으로 성공 조건, 실패 조건, 진입/청산 기준 개선안을 생성합니다.
                    </p>
                    <div className="mb-2 flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => void createGuidePackage()}
                        disabled={guideLoading}
                      >
                        {guideLoading ? "생성 중..." : "GPT 기법 개선 가이드 생성"}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => void copyGuidePackage()}
                        disabled={!guidePackage?.markdown}
                      >
                        전체 복사
                      </button>
                    </div>
                    <div className="rounded border border-slate-200 bg-slate-50 p-3">
                      <p className="mb-2 text-sm font-medium text-slate-700">GPT 기법 개선 가이드 미리보기</p>
                      {guidePackage?.markdown ? (
                        <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-slate-700">{guidePackage.markdown}</pre>
                      ) : (
                        <p className="text-sm text-slate-500">가이드를 생성하면 이 영역에 Markdown 미리보기가 표시됩니다.</p>
                      )}
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="trade-journal-detail-drawer-footer">
                {detailMode === "view" ? (
                  <button type="button" className="btn btn-primary" onClick={startEditMode}>수정</button>
                ) : (
                  <button type="button" className="btn btn-primary" onClick={() => void onSubmit()} disabled={saving}>
                    {saving ? "저장 중..." : "저장"}
                  </button>
                )}
                {detailMode === "edit" ? (
                  <button type="button" className="btn btn-secondary" onClick={() => void toggleActive()}>
                    {detailForm.is_active ? "비활성화" : "활성화"}
                  </button>
                ) : null}
                <button type="button" className="btn btn-secondary" onClick={closeDetail}>
                  닫기
                </button>
              </div>
            </aside>
          </>
        ) : null}
      </div>
    </div>
  );
}

export default TradeMethodsPage;
