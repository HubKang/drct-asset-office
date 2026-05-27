import { type KeyboardEvent, useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { TradeJournal, TradeMethod } from "@/types/tradeJournal";

type ActiveFilter = "all" | "active" | "inactive";
type DetailMode = "create" | "edit";

type MethodDetailForm = {
  method_name: string;
  core_concept: string;
  checklist: string[];
  take_profit_rule: string;
  stop_loss_rule: string;
  failure_patterns: string;
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

const MARKET_TAG_OPTIONS = ["상승장", "횡보장", "하락장", "테마장", "반도체장", "AI장"];

const defaultForm = (): MethodDetailForm => ({
  method_name: "",
  core_concept: "",
  checklist: [""],
  take_profit_rule: "",
  stop_loss_rule: "",
  failure_patterns: "",
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

const toChecklist = (entryRule?: string | null): string[] =>
  (entryRule || "")
    .split("\n")
    .map((line) => line.replace(/^\s*[-*]\s*/, "").trim())
    .filter(Boolean);

const checklistToEntryRule = (items: string[]): string | undefined => {
  const normalized = items.map((item) => item.trim()).filter(Boolean);
  if (normalized.length === 0) return undefined;
  return normalized.map((item) => `- ${item}`).join("\n");
};

const formatRate = (value?: number | null): string => `${Number(value ?? 0).toFixed(1)}%`;
const formatWon = (value?: number | null): string => `${Number(value ?? 0).toLocaleString("ko-KR")}원`;
const formatResult = (value?: string | null): string => {
  if (value === "profit") return "익절";
  if (value === "loss") return "손절";
  if (value === "break_even") return "본전";
  return "보유중";
};

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

  const selectedMethod = useMemo(
    () => items.find((item) => item.id === selectedMethodId) ?? null,
    [items, selectedMethodId]
  );

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
    setIsDetailOpen(true);
    setMessage("");
    setError("");
  };

  const openEdit = (item: TradeMethod) => {
    if (selectedMethodId === item.id && isDetailOpen) {
      setSelectedMethodId(null);
      setIsDetailOpen(false);
      return;
    }
    const parsed = parseMethodMeta(item.description);
    const checklist = toChecklist(item.entry_rule);
    setSelectedMethodId(item.id);
    setDetailMode("edit");
    setDetailForm({
      method_name: item.method_name || "",
      core_concept: parsed.coreConcept,
      checklist: checklist.length > 0 ? checklist : [""],
      take_profit_rule: item.take_profit_rule || "",
      stop_loss_rule: item.stop_loss_rule || "",
      failure_patterns: item.exit_rule || "",
      market_conditions: parsed.marketConditions,
      sort_order: item.sort_order || 0,
      is_active: item.is_active === 1,
    });
    setIsDetailOpen(true);
    setMessage("");
    setError("");
  };

  const closeDetail = () => {
    setIsDetailOpen(false);
    setSelectedMethodId(null);
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
        entry_rule: checklistToEntryRule(detailForm.checklist),
        take_profit_rule: detailForm.take_profit_rule.trim() || undefined,
        stop_loss_rule: detailForm.stop_loss_rule.trim() || undefined,
        exit_rule: detailForm.failure_patterns.trim() || undefined,
        sort_order: Number(detailForm.sort_order) || 0,
        is_active: detailForm.is_active,
      };
      if (detailMode === "create") {
        const created = await repositories.tradeJournals.createTradeMethod(payload);
        setMessage("매매기법이 등록되었습니다.");
        await load();
        const createdRow = items.find((row) => row.id === created.id);
        if (createdRow) openEdit(createdRow);
      } else if (selectedMethodId) {
        await repositories.tradeJournals.updateTradeMethod(selectedMethodId, payload);
        setMessage("매매기법이 수정되었습니다.");
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

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    void load();
  };

  const updateChecklistItem = (index: number, value: string) => {
    setDetailForm((prev) => ({
      ...prev,
      checklist: prev.checklist.map((item, i) => (i === index ? value : item)),
    }));
  };

  const addChecklistItem = () => {
    setDetailForm((prev) => ({ ...prev, checklist: [...prev.checklist, ""] }));
  };

  const removeChecklistItem = (index: number) => {
    setDetailForm((prev) => {
      const next = prev.checklist.filter((_, i) => i !== index);
      return { ...prev, checklist: next.length > 0 ? next : [""] };
    });
  };

  const toggleMarketTag = (tag: string) => {
    setDetailForm((prev) => ({
      ...prev,
      market_conditions: prev.market_conditions.includes(tag)
        ? prev.market_conditions.filter((item) => item !== tag)
        : [...prev.market_conditions, tag],
    }));
  };

  return (
    <div className="space-y-4">
      <PageHeader title="매매기법" description="실전 매매 프레임을 카드 기반으로 관리하고 성과를 함께 확인합니다." />

      <SectionCard title="검색">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <input
            className="input-control"
            placeholder="매매기법명 / 핵심개념 검색"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={handleSearchKeyDown}
          />
          <select className="select-control" value={activeFilter} onChange={(e) => setActiveFilter(e.target.value as ActiveFilter)}>
            <option value="all">전체</option>
            <option value="active">활성</option>
            <option value="inactive">비활성</option>
          </select>
          <button type="button" className="btn btn-primary" onClick={() => void load()} disabled={loading}>
            {loading ? "조회 중..." : "조회"}
          </button>
          <button type="button" className="btn btn-secondary" onClick={openCreate}>
            + 새 매매기법
          </button>
        </div>
        {message ? <p className="mt-2 text-sm text-emerald-700">{message}</p> : null}
        {error ? <p className="mt-2 text-sm text-rose-700">{error}</p> : null}
      </SectionCard>

      <div className="trade-method-layout">
        <SectionCard title="매매기법 목록">
          <div className="trade-method-card-list">
            {items.map((item) => {
              const parsed = parseMethodMeta(item.description);
              const stats = statsByMethod[item.id];
              const selected = isDetailOpen && selectedMethodId === item.id && detailMode === "edit";
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`trade-method-card ${selected ? "selected" : ""}`}
                  onClick={() => openEdit(item)}
                >
                  <div className="trade-method-card-header">
                    <strong>{item.method_name}</strong>
                    <span className={`badge ${item.is_active === 1 ? "badge-emerald" : "badge-slate"}`}>
                      {item.is_active === 1 ? "활성" : "비활성"}
                    </span>
                  </div>
                  <p className="trade-method-card-concept">{parsed.coreConcept || "핵심 개념 미입력"}</p>
                  <div className="trade-method-card-stats">
                    <span>승률 {formatRate(stats?.win_rate)}</span>
                    <span>평균 {formatRate(stats?.avg_profit_rate)}</span>
                    <span>거래 {stats?.trade_count ?? 0}건</span>
                    <span>누적 {formatWon(stats?.realized_profit_sum)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </SectionCard>
      </div>

      {isDetailOpen ? (
        <>
          <div className="trade-journal-detail-dim" onClick={closeDetail} />
          <aside className="trade-journal-detail-drawer">
            <div className="trade-journal-detail-drawer-header">
              <h3>{detailMode === "create" ? "새 매매기법" : detailForm.method_name || "매매기법 상세"}</h3>
              <button type="button" className="btn btn-secondary" onClick={closeDetail}>
                닫기
              </button>
            </div>
            <div className="trade-journal-detail-drawer-body">
              <div className="trade-detail-form-grid">
                <div className="trade-detail-field">
                  <label>매매기법명</label>
                  <input
                    className="input-control"
                    value={detailForm.method_name}
                    onChange={(e) => setFormField("method_name", e.target.value)}
                  />
                </div>
                <div className="trade-detail-field">
                  <label>정렬순서</label>
                  <input
                    className="input-control"
                    type="number"
                    value={detailForm.sort_order}
                    onChange={(e) => setFormField("sort_order", Number(e.target.value) || 0)}
                  />
                </div>
                <div className="trade-detail-field">
                  <label>핵심 개념</label>
                  <input
                    className="input-control"
                    value={detailForm.core_concept}
                    onChange={(e) => setFormField("core_concept", e.target.value)}
                  />
                </div>
                <div className="trade-detail-field">
                  <label>활성 여부</label>
                  <select
                    className="select-control"
                    value={detailForm.is_active ? "1" : "0"}
                    onChange={(e) => setFormField("is_active", e.target.value === "1")}
                  >
                    <option value="1">활성</option>
                    <option value="0">비활성</option>
                  </select>
                </div>
                <div className="trade-detail-field">
                  <label>익절 기준</label>
                  <input
                    className="input-control"
                    value={detailForm.take_profit_rule}
                    onChange={(e) => setFormField("take_profit_rule", e.target.value)}
                  />
                </div>
                <div className="trade-detail-field">
                  <label>손절 기준</label>
                  <input
                    className="input-control"
                    value={detailForm.stop_loss_rule}
                    onChange={(e) => setFormField("stop_loss_rule", e.target.value)}
                  />
                </div>
              </div>

              <div className="detail-section">
                <div className="mb-2 flex items-center justify-between">
                  <strong>진입 체크리스트</strong>
                  <button type="button" className="btn btn-secondary btn-table-sm" onClick={addChecklistItem}>
                    + 항목
                  </button>
                </div>
                <div className="trade-method-checklist">
                  {detailForm.checklist.map((item, index) => (
                    <div key={`check-${index}`} className="trade-method-checklist-item">
                      <span>□</span>
                      <input
                        className="input-control"
                        value={item}
                        onChange={(e) => updateChecklistItem(index, e.target.value)}
                        placeholder="체크리스트 항목 입력"
                      />
                      <button
                        type="button"
                        className="btn btn-secondary btn-table-sm"
                        onClick={() => removeChecklistItem(index)}
                      >
                        삭제
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="detail-section">
                <label className="detail-label">실패 패턴</label>
                <textarea
                  className="textarea-control"
                  value={detailForm.failure_patterns}
                  onChange={(e) => setFormField("failure_patterns", e.target.value)}
                  placeholder="예: 시가 갭 과열 추격, 거래량 감소 구간 진입"
                />
              </div>

              <div className="detail-section">
                <label className="detail-label">시장 환경 태그</label>
                <div className="trade-method-tag-list">
                  {MARKET_TAG_OPTIONS.map((tag) => {
                    const active = detailForm.market_conditions.includes(tag);
                    return (
                      <button
                        key={tag}
                        type="button"
                        className={`trade-method-tag ${active ? "active" : ""}`}
                        onClick={() => toggleMarketTag(tag)}
                      >
                        {tag}
                      </button>
                    );
                  })}
                </div>
              </div>

              {detailMode === "edit" && selectedMethodId ? (
                <div className="detail-section">
                  <h4 className="section-title">성과 통계</h4>
                  <div className="trade-method-stats-grid">
                    <div className="price-meta-card">
                      <p className="price-meta-label">총 거래 수</p>
                      <strong>{statsByMethod[selectedMethodId]?.trade_count ?? 0}건</strong>
                    </div>
                    <div className="price-meta-card">
                      <p className="price-meta-label">승률</p>
                      <strong>{formatRate(statsByMethod[selectedMethodId]?.win_rate)}</strong>
                    </div>
                    <div className="price-meta-card">
                      <p className="price-meta-label">평균 수익률</p>
                      <strong>{formatRate(statsByMethod[selectedMethodId]?.avg_profit_rate)}</strong>
                    </div>
                    <div className="price-meta-card">
                      <p className="price-meta-label">누적 손익</p>
                      <strong>{formatWon(statsByMethod[selectedMethodId]?.realized_profit_sum)}</strong>
                    </div>
                  </div>
                </div>
              ) : null}

              {detailMode === "edit" && selectedMethodId ? (
                <div className="detail-section">
                  <h4 className="section-title">최근 매매일지</h4>
                  <div className="table-shell">
                    <table className="data-table compact-table">
                      <thead>
                        <tr>
                          <th>날짜</th>
                          <th>종목명</th>
                          <th>수익률</th>
                          <th>실현손익</th>
                          <th>결과</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(statsByMethod[selectedMethodId]?.recent_trades ?? []).map((trade) => (
                          <tr key={`recent-${trade.id}`}>
                            <td>{trade.buy_date}</td>
                            <td>{trade.stock_name}</td>
                            <td>{formatRate(trade.profit_rate)}</td>
                            <td>{formatWon(trade.realized_profit)}</td>
                            <td>{formatResult(trade.result_type)}</td>
                          </tr>
                        ))}
                        {(statsByMethod[selectedMethodId]?.recent_trades ?? []).length === 0 ? (
                          <tr>
                            <td colSpan={5} className="text-muted">
                              최근 매매일지가 없습니다.
                            </td>
                          </tr>
                        ) : null}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}
            </div>
            <div className="trade-journal-detail-drawer-footer">
              {detailMode === "edit" ? (
                <button type="button" className="btn btn-secondary" onClick={() => void toggleActive()}>
                  {detailForm.is_active ? "비활성화" : "활성화"}
                </button>
              ) : null}
              <button type="button" className="btn btn-primary" onClick={() => void onSubmit()} disabled={saving}>
                {saving ? "저장 중..." : "저장"}
              </button>
            </div>
          </aside>
        </>
      ) : null}
    </div>
  );
}

export default TradeMethodsPage;
