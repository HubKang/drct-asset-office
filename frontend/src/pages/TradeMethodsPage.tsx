import { type KeyboardEvent, useEffect, useMemo, useState } from "react";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import { appConfig } from "@/services/config/appConfig";
import type {
  TradeJournal,
  TradeMethod,
  TradeMethodGptGuidePackage,
  TradeMethodImage,
  TradeMethodImageType,
} from "@/types/tradeJournal";

type ActiveFilter = "all" | "active" | "inactive";
type DetailMode = "view" | "create" | "edit";

type MethodDetailForm = {
  method_name: string;
  core_concept: string;
  description: string;
  buy_condition: string;
  sell_condition: string;
  position_sizing_rule: string;
  take_profit_rule: string;
  stop_loss_rule: string;
  checklist: string;
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

const METHOD_IMAGE_TYPE_OPTIONS: Array<{ value: TradeMethodImageType; label: string }> = [
  { value: "example_chart", label: "예시 차트" },
  { value: "entry_example", label: "진입 예시" },
  { value: "exit_example", label: "청산 예시" },
  { value: "failure_example", label: "실패 예시" },
  { value: "checklist_reference", label: "체크리스트 참고" },
  { value: "other", label: "기타" },
];

const defaultForm = (): MethodDetailForm => ({
  method_name: "",
  core_concept: "",
  description: "",
  buy_condition: "",
  sell_condition: "",
  position_sizing_rule: "",
  take_profit_rule: "",
  stop_loss_rule: "",
  checklist: "",
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

const normalizeText = (value: string): string | undefined => value.trim() || undefined;

const methodValue = (method: TradeMethod, ...fields: Array<keyof TradeMethod>): string => {
  for (const field of fields) {
    const value = method[field];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
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

const RuleList = ({ value, emptyText }: { value?: string | null; emptyText: string }) => {
  const lines = parseLines(value);
  return (
    <ul className="trade-method-rule-list">
      {lines.length > 0 ? lines.map((line, idx) => <li key={`${line}-${idx}`}>{line}</li>) : <li>{emptyText}</li>}
    </ul>
  );
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
  const [guidePackage, setGuidePackage] = useState<TradeMethodGptGuidePackage | null>(null);
  const [guideLoading, setGuideLoading] = useState(false);
  const [methodImages, setMethodImages] = useState<TradeMethodImage[]>([]);
  const [methodImageType, setMethodImageType] = useState<TradeMethodImageType>("example_chart");
  const [methodImageMemo, setMethodImageMemo] = useState("");
  const [methodImageFile, setMethodImageFile] = useState<File | null>(null);
  const [methodImageUploading, setMethodImageUploading] = useState(false);
  const [methodImageEditingId, setMethodImageEditingId] = useState<number | null>(null);
  const [methodImageEditDraft, setMethodImageEditDraft] = useState<{
    image_type: TradeMethodImageType;
    image_memo: string;
    sort_order: number;
  }>({
    image_type: "example_chart",
    image_memo: "",
    sort_order: 0,
  });
  const [methodImageSavingEdit, setMethodImageSavingEdit] = useState(false);
  const [methodImageDeletingId, setMethodImageDeletingId] = useState<number | null>(null);
  const [methodImagePreview, setMethodImagePreview] = useState<TradeMethodImage | null>(null);

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

  const setFormField = <K extends keyof MethodDetailForm>(key: K, value: MethodDetailForm[K]) => {
    setDetailForm((prev) => ({ ...prev, [key]: value }));
  };

  const resetMethodImageForm = () => {
    setMethodImageType("example_chart");
    setMethodImageMemo("");
    setMethodImageFile(null);
    setMethodImageEditingId(null);
    setMethodImagePreview(null);
    setMethodImageEditDraft({ image_type: "example_chart", image_memo: "", sort_order: 0 });
  };

  const loadMethodImages = async (methodId: number) => {
    const rows = await repositories.tradeJournals.fetchTradeMethodImages(methodId);
    setMethodImages(Array.isArray(rows) ? rows : []);
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
    setMethodImages([]);
    resetMethodImageForm();
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
      core_concept: methodValue(item, "core_concept") || parsed.coreConcept,
      description: methodValue(item, "description"),
      buy_condition: methodValue(item, "buy_condition", "entry_rule"),
      sell_condition: methodValue(item, "sell_condition", "exit_rule"),
      position_sizing_rule: methodValue(item, "position_sizing_rule"),
      take_profit_rule: methodValue(item, "take_profit_rule"),
      stop_loss_rule: methodValue(item, "stop_loss_rule"),
      checklist: methodValue(item, "checklist", "take_profit_rule"),
      sort_order: item.sort_order || 0,
      is_active: item.is_active === 1,
    });
    setGuidePackage(null);
    resetMethodImageForm();
    void loadMethodImages(item.id);
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
    setMethodImages([]);
    resetMethodImageForm();
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
        core_concept: normalizeText(detailForm.core_concept),
        description: normalizeText(detailForm.description),
        buy_condition: normalizeText(detailForm.buy_condition),
        sell_condition: normalizeText(detailForm.sell_condition),
        position_sizing_rule: normalizeText(detailForm.position_sizing_rule),
        take_profit_rule: normalizeText(detailForm.take_profit_rule),
        stop_loss_rule: normalizeText(detailForm.stop_loss_rule),
        checklist: normalizeText(detailForm.checklist),
        entry_rule: normalizeText(detailForm.buy_condition),
        exit_rule: normalizeText(detailForm.sell_condition),
        sort_order: Number(detailForm.sort_order) || 0,
        is_active: detailForm.is_active,
      };
      if (detailMode === "create") {
        const created = await repositories.tradeJournals.createTradeMethod(payload);
        setMessage("매매기법을 등록했습니다.");
        setSelectedMethodId(created.id);
        setDetailMode("edit");
        await loadMethodImages(created.id);
        await load();
      } else if (selectedMethodId) {
        await repositories.tradeJournals.updateTradeMethod(selectedMethodId, payload);
        setMessage("매매기법을 수정했습니다.");
        await loadMethodImages(selectedMethodId);
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

  const uploadMethodImage = async () => {
    if (!selectedMethodId || !methodImageFile) return;
    setMethodImageUploading(true);
    setError("");
    try {
      await repositories.tradeJournals.uploadTradeMethodImage(selectedMethodId, {
        image_type: methodImageType,
        image_memo: methodImageMemo,
        file: methodImageFile,
      });
      setMessage("기법 이미지를 등록했습니다.");
      resetMethodImageForm();
      await loadMethodImages(selectedMethodId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "기법 이미지 등록에 실패했습니다.");
    } finally {
      setMethodImageUploading(false);
    }
  };

  const startEditMethodImage = (image: TradeMethodImage) => {
    setMethodImageEditingId(image.id);
    setMethodImageEditDraft({
      image_type: image.image_type,
      image_memo: image.image_memo || "",
      sort_order: image.sort_order || 0,
    });
  };

  const saveMethodImageEdit = async (imageId: number) => {
    if (!selectedMethodId) return;
    setMethodImageSavingEdit(true);
    setError("");
    try {
      await repositories.tradeJournals.updateTradeMethodImage(selectedMethodId, imageId, {
        image_type: methodImageEditDraft.image_type,
        image_memo: methodImageEditDraft.image_memo,
        sort_order: methodImageEditDraft.sort_order,
      });
      setMessage("기법 이미지를 수정했습니다.");
      setMethodImageEditingId(null);
      await loadMethodImages(selectedMethodId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "기법 이미지 수정에 실패했습니다.");
    } finally {
      setMethodImageSavingEdit(false);
    }
  };

  const deleteMethodImage = async (imageId: number) => {
    if (!selectedMethodId) return;
    const ok = window.confirm("이 기법 이미지를 삭제하시겠습니까?");
    if (!ok) return;
    setMethodImageDeletingId(imageId);
    setError("");
    try {
      await repositories.tradeJournals.deleteTradeMethodImage(selectedMethodId, imageId);
      setMessage("기법 이미지를 삭제했습니다.");
      setMethodImageEditingId((prev) => (prev === imageId ? null : prev));
      await loadMethodImages(selectedMethodId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "기법 이미지 삭제에 실패했습니다.");
    } finally {
      setMethodImageDeletingId(null);
    }
  };

  const handleSearchKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    void load();
  };

  return (
    <div className="space-y-4">
      <div className="journal-hero-row">
        <section className="journal-hero-panel">
          <h1>매매기법</h1>
          <p>주력 매매기법을 정리하고 반복 훈련을 위한 가이드를 준비합니다.</p>
        </section>

        <section className="journal-summary-compact" aria-label="매매기법 요약">
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">활성 기법</span>
            <strong className="journal-summary-value">{summaryStats.activeMethodCount}개</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">총 거래</span>
            <strong className="journal-summary-value">{summaryStats.totalTrades}건</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">평균 승률</span>
            <strong className="journal-summary-value">{formatRate(summaryStats.avgWinRate)}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">누적 손익</span>
            <strong className="journal-summary-value journal-summary-value-money" title={formatWon(summaryStats.totalRealizedProfit)}>{formatWon(summaryStats.totalRealizedProfit)}</strong>
          </div>
        </section>
      </div>

      <SectionCard title="검색">
        <div className="trade-method-search-row">
          <input
            className="input-control trade-method-search-input"
            placeholder="매매기법명/핵심개념/매수조건 검색"
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
              const coreConcept = methodValue(item, "core_concept") || parsed.coreConcept;
              const buyCondition = methodValue(item, "buy_condition", "entry_rule");
              const sellCondition = methodValue(item, "sell_condition", "exit_rule");
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
                  <p className="trade-method-card-concept">{coreConcept || "핵심 개념이 없습니다."}</p>
                  <div className="trade-method-card-lines">
                    <p><b>매수</b>{buyCondition || "매수조건이 없습니다."}</p>
                    <p><b>매도</b>{sellCondition || "매도조건이 없습니다."}</p>
                  </div>
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
                      <div className="trade-method-info-block">
                        <div>
                          <span>기법명</span>
                          <strong>{selectedMethod.method_name || "-"}</strong>
                        </div>
                        <div>
                          <span>핵심개념</span>
                          <p>{methodValue(selectedMethod, "core_concept") || parseMethodMeta(selectedMethod.description).coreConcept || "등록된 핵심개념이 없습니다."}</p>
                        </div>
                        <div>
                          <span>설명</span>
                          <p>{methodValue(selectedMethod, "description") || "등록된 설명이 없습니다."}</p>
                        </div>
                      </div>
                    </div>
                    <div className="detail-section">
                      <h4 className="detail-label mb-2">성과 요약</h4>
                      <div className="trade-method-stats-grid">
                        <div className="trade-method-stat-card"><span>거래 수</span><strong>{selectedStats?.trade_count ?? 0}건</strong></div>
                        <div className="trade-method-stat-card"><span>승률</span><strong>{formatRate(selectedStats?.win_rate)}</strong></div>
                        <div className="trade-method-stat-card"><span>평균 수익률</span><strong>{formatRate(selectedStats?.avg_profit_rate)}</strong></div>
                        <div className="trade-method-stat-card"><span>누적 손익</span><strong>{formatWon(selectedStats?.realized_profit_sum)}</strong></div>
                      </div>
                    </div>
                    <div className="detail-section">
                      <h4 className="detail-label mb-2">매매 원칙서</h4>
                      <div className="trade-method-principle-grid">
                        <div className="trade-method-rule-card">
                          <h5>매수조건</h5>
                          <RuleList value={methodValue(selectedMethod, "buy_condition", "entry_rule")} emptyText="등록된 매수조건이 없습니다." />
                        </div>
                        <div className="trade-method-rule-card">
                          <h5>매도조건</h5>
                          <RuleList value={methodValue(selectedMethod, "sell_condition", "exit_rule")} emptyText="등록된 매도조건이 없습니다." />
                        </div>
                        <div className="trade-method-rule-card">
                          <h5>익절기준</h5>
                          <RuleList value={methodValue(selectedMethod, "take_profit_rule")} emptyText="등록된 익절기준이 없습니다." />
                        </div>
                        <div className="trade-method-rule-card">
                          <h5>손절기준</h5>
                          <RuleList value={methodValue(selectedMethod, "stop_loss_rule")} emptyText="등록된 손절기준이 없습니다." />
                        </div>
                        <div className="trade-method-rule-card">
                          <h5>진입&비중 방식</h5>
                          <RuleList value={methodValue(selectedMethod, "position_sizing_rule")} emptyText="등록된 비중 방식이 없습니다." />
                        </div>
                        <div className="trade-method-rule-card">
                          <h5>체크리스트</h5>
                          <RuleList value={methodValue(selectedMethod, "checklist", "take_profit_rule")} emptyText="등록된 체크리스트가 없습니다." />
                        </div>
                      </div>
                    </div>
                  </>
                ) : null}

                <div className="detail-section method-image-section">
                  <div className="method-image-section-header">
                    <div>
                      <h4 className="detail-label mb-1">기법 이미지</h4>
                      <p>차트 예시, 진입·청산·실패 사례 이미지를 매매기법 훈련 자료로 관리합니다.</p>
                    </div>
                  </div>

                  {detailMode === "create" || !selectedMethodId ? (
                    <div className="method-image-empty">
                      이미지는 매매기법 저장 후 수정 화면에서 등록할 수 있습니다.
                    </div>
                  ) : (
                    <>
                      {detailMode === "edit" ? (
                        <div className="method-image-upload-row">
                          <select
                            className="select-control method-image-type-select"
                            value={methodImageType}
                            onChange={(e) => setMethodImageType(e.target.value as TradeMethodImageType)}
                          >
                            {METHOD_IMAGE_TYPE_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                          <input
                            className="input-control method-image-file-input"
                            type="file"
                            accept="image/png,image/jpeg,image/webp"
                            onChange={(e) => setMethodImageFile(e.target.files?.[0] ?? null)}
                          />
                          <button
                            type="button"
                            className="btn btn-secondary method-image-upload-button"
                            onClick={() => void uploadMethodImage()}
                            disabled={!methodImageFile || methodImageUploading}
                          >
                            {methodImageUploading ? "업로드 중" : "이미지 업로드"}
                          </button>
                          <textarea
                            className="textarea-control method-image-memo"
                            rows={3}
                            value={methodImageMemo}
                            onChange={(e) => setMethodImageMemo(e.target.value)}
                            placeholder="이미지 메모"
                          />
                        </div>
                      ) : null}

                      <div className="method-image-list">
                        {methodImages.map((image) => (
                          <article key={image.id} className="method-image-card">
                            <div className="method-image-thumb-wrap">
                              {image.image_url ? (
                                <button
                                  type="button"
                                  className="method-image-thumb-button"
                                  onClick={() => setMethodImagePreview(image)}
                                  aria-label={`${image.original_filename || image.image_type_label || "기법 이미지"} 원본 보기`}
                                >
                                  <img
                                    className="method-image-thumb"
                                    src={`${appConfig.apiBaseUrl}${image.image_url}`}
                                    alt={image.original_filename || image.image_type_label || "기법 이미지"}
                                  />
                                </button>
                              ) : (
                                <div className="method-image-thumb method-image-thumb-fallback">이미지를 불러올 수 없습니다.</div>
                              )}
                            </div>
                            <div className="method-image-meta">
                              <div className="method-image-meta-header">
                                <span className="badge badge-blue method-image-badge">{image.image_type_label || image.image_type}</span>
                                <span className="method-image-filename">{image.original_filename || image.image_path}</span>
                              </div>
                              {methodImageEditingId === image.id ? (
                                <div className="method-image-edit-form">
                                  <div className="method-image-edit-grid">
                                    <select
                                      className="select-control"
                                      value={methodImageEditDraft.image_type}
                                      onChange={(e) =>
                                        setMethodImageEditDraft((prev) => ({
                                          ...prev,
                                          image_type: e.target.value as TradeMethodImageType,
                                        }))
                                      }
                                    >
                                      {METHOD_IMAGE_TYPE_OPTIONS.map((option) => (
                                        <option key={option.value} value={option.value}>
                                          {option.label}
                                        </option>
                                      ))}
                                    </select>
                                    <input
                                      className="input-control"
                                      type="number"
                                      value={methodImageEditDraft.sort_order}
                                      onChange={(e) =>
                                        setMethodImageEditDraft((prev) => ({
                                          ...prev,
                                          sort_order: Number(e.target.value) || 0,
                                        }))
                                      }
                                      placeholder="정렬"
                                    />
                                  </div>
                                  <textarea
                                    className="textarea-control"
                                    rows={3}
                                    value={methodImageEditDraft.image_memo}
                                    onChange={(e) =>
                                      setMethodImageEditDraft((prev) => ({
                                        ...prev,
                                        image_memo: e.target.value,
                                      }))
                                    }
                                    placeholder="이미지 메모"
                                  />
                                  <div className="method-image-actions">
                                    <button
                                      type="button"
                                      className="btn btn-primary btn-table-sm"
                                      onClick={() => void saveMethodImageEdit(image.id)}
                                      disabled={methodImageSavingEdit}
                                    >
                                      {methodImageSavingEdit ? "저장중" : "저장"}
                                    </button>
                                    <button
                                      type="button"
                                      className="btn btn-secondary btn-table-sm"
                                      onClick={() => setMethodImageEditingId(null)}
                                    >
                                      취소
                                    </button>
                                  </div>
                                </div>
                              ) : (
                                <>
                                  <p className="method-image-memo-text">{image.image_memo || "메모 없음"}</p>
                                  {detailMode === "edit" ? (
                                    <div className="method-image-actions">
                                      <button
                                        type="button"
                                        className="btn btn-secondary btn-table-sm"
                                        onClick={() => startEditMethodImage(image)}
                                      >
                                        수정
                                      </button>
                                      <button
                                        type="button"
                                        className="btn btn-danger btn-table-sm"
                                        onClick={() => void deleteMethodImage(image.id)}
                                        disabled={methodImageDeletingId === image.id}
                                      >
                                        {methodImageDeletingId === image.id ? "삭제중" : "삭제"}
                                      </button>
                                    </div>
                                  ) : null}
                                </>
                              )}
                            </div>
                          </article>
                        ))}
                        {methodImages.length === 0 ? (
                          <div className="method-image-empty">등록된 기법 이미지가 없습니다.</div>
                        ) : null}
                      </div>
                    </>
                  )}
                </div>

                {detailMode !== "view" ? (
                <>
                <div className="detail-section">
                  <h4 className="detail-label mb-2">기본 정보</h4>
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
                      <label className="detail-label">핵심개념</label>
                      <textarea
                        className="textarea-control"
                        rows={2}
                        value={detailForm.core_concept}
                        onChange={(e) => setFormField("core_concept", e.target.value)}
                        placeholder="예: 주도 테마가 살아 있고 첫 눌림에서 수급이 재유입되는 구간만 공략"
                      />
                    </div>
                    <div className="trade-detail-field md:col-span-2">
                      <label className="detail-label">설명</label>
                      <textarea
                        className="textarea-control"
                        rows={3}
                        value={detailForm.description}
                        onChange={(e) => setFormField("description", e.target.value)}
                        placeholder="이 기법을 어떤 시장과 종목 상황에서 쓰는지, 훈련자가 기억해야 할 맥락을 적어주세요."
                      />
                    </div>
                  </div>
                </div>

                <div className="detail-section">
                  <h4 className="detail-label mb-2">매매 기준</h4>
                  <div className="space-y-3">
                    <div>
                      <label className="detail-label">매수조건</label>
                      <textarea
                        className="textarea-control"
                        rows={4}
                        value={detailForm.buy_condition}
                        onChange={(e) => setFormField("buy_condition", e.target.value)}
                        placeholder="예: 거래대금 500억 이상, 주도 테마 1~2등주, 첫 눌림, 기준선 지지 확인 후 매수"
                      />
                    </div>
                    <div>
                      <label className="detail-label">매도조건</label>
                      <textarea
                        className="textarea-control"
                        rows={4}
                        value={detailForm.sell_condition}
                        onChange={(e) => setFormField("sell_condition", e.target.value)}
                        placeholder="예: 매수 논리 훼손, 주도 테마 약화, 기준선 이탈, 목표 구간 도달 시 분할 매도"
                      />
                    </div>
                    <div>
                      <label className="detail-label">진입&비중 방식</label>
                      <textarea
                        className="textarea-control"
                        rows={4}
                        value={detailForm.position_sizing_rule}
                        onChange={(e) => setFormField("position_sizing_rule", e.target.value)}
                        placeholder="예: 1차 50%, 지지 재확인 시 30%, 돌파 확인 시 20%. 손절선 멀면 진입 비중 축소"
                      />
                    </div>
                    <div>
                      <label className="detail-label">익절기준</label>
                      <textarea
                        className="textarea-control"
                        rows={3}
                        value={detailForm.take_profit_rule}
                        onChange={(e) => setFormField("take_profit_rule", e.target.value)}
                        placeholder="예: 1차 목표가에서 30% 익절, 전고점 저항에서 추가 익절, 거래량 둔화 시 잔량 축소"
                      />
                    </div>
                    <div>
                      <label className="detail-label">손절기준</label>
                      <textarea
                        className="textarea-control"
                        rows={3}
                        value={detailForm.stop_loss_rule}
                        onChange={(e) => setFormField("stop_loss_rule", e.target.value)}
                        placeholder="예: 기준봉 저가 이탈, 매수 근거 훼손, 시장 급락 전환 시 즉시 손절"
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
                  </div>
                </div>
                </>
                ) : null}

                {detailMode === "edit" && selectedMethodId ? (
                  <div className="detail-section">
                    <h4 className="detail-label mb-2">성과 요약</h4>
                    <div className="trade-method-stats-grid">
                      <div className="trade-method-stat-card"><span>거래 수</span><strong>{statsByMethod[selectedMethodId]?.trade_count ?? 0}건</strong></div>
                      <div className="trade-method-stat-card"><span>승률</span><strong>{formatRate(statsByMethod[selectedMethodId]?.win_rate)}</strong></div>
                      <div className="trade-method-stat-card"><span>평균 수익률</span><strong>{formatRate(statsByMethod[selectedMethodId]?.avg_profit_rate)}</strong></div>
                      <div className="trade-method-stat-card"><span>누적 손익</span><strong>{formatWon(statsByMethod[selectedMethodId]?.realized_profit_sum)}</strong></div>
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
            {methodImagePreview?.image_url ? (
              <div className="method-image-preview-modal" onClick={() => setMethodImagePreview(null)}>
                <div className="method-image-preview-frame" onClick={(event) => event.stopPropagation()}>
                  <img
                    className="method-image-preview-original"
                    src={`${appConfig.apiBaseUrl}${methodImagePreview.image_url}`}
                    alt={methodImagePreview.original_filename || methodImagePreview.image_type_label || "기법 이미지 원본"}
                  />
                  <div className="method-image-preview-caption">
                    <span className="badge badge-blue">{methodImagePreview.image_type_label || methodImagePreview.image_type}</span>
                    <span>{methodImagePreview.original_filename || methodImagePreview.image_path}</span>
                  </div>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

export default TradeMethodsPage;
