import { useEffect, useMemo, useState } from "react";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { TradeMethod } from "@/types/tradeJournal";
import type {
  TradeGrade,
  TradeReviewCheckItem,
  TradeReviewDetail,
  TradeReviewGptPackage,
  TradeReviewListItem,
  TradeReviewSaveRequest,
  TradeReviewSummary,
} from "@/types/tradeReview";

const REVIEW_STATUS_OPTIONS = ["전체", "미복기", "복기완료"];
const RESULT_TYPE_OPTIONS = [
  { value: "", label: "전체" },
  { value: "profit", label: "익절" },
  { value: "loss", label: "손절" },
  { value: "holding", label: "보유중" },
  { value: "break_even", label: "본전" },
];
const PRINCIPLE_OPTIONS = ["지킴", "일부 위반", "위반", "미확인"];
const QUALITY_OPTIONS = ["좋음", "보통", "나쁨", "미확인"];
const MISTAKE_OPTIONS = [
  "",
  "추격매수",
  "손절 지연",
  "근거 부족 진입",
  "조기 매도",
  "과도한 비중",
  "뉴스만 보고 진입",
  "원칙 없는 재진입",
  "수익 욕심",
  "공포 매도",
  "기타",
];
const GRADE_OPTIONS: Array<{ value: TradeGrade; title: string; description: string }> = [
  { value: "A", title: "A급", description: "원칙 준수 + 좋은 매매" },
  { value: "B", title: "B급", description: "원칙 준수 + 정상 손실" },
  { value: "C", title: "C급", description: "원칙 일부 위반" },
  { value: "D", title: "D급", description: "충동매매 / 원칙 위반" },
];
const CHECK_ITEM_GROUPS = [
  { type: "entry", title: "진입 조건 체크", help: "체크됨 = 진입 원칙을 지켰다" },
  { type: "exit", title: "청산 조건 체크", help: "체크됨 = 청산 원칙을 지켰다" },
  { type: "failure", title: "실패 패턴 해당 여부", help: "체크됨 = 해당 실패 패턴이 발생했다" },
  { type: "checklist", title: "체크리스트 확인", help: "체크됨 = 확인했다/지켰다" },
];

const today = () => new Date().toISOString().slice(0, 10);
const daysAgo = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
};
const formatWon = (value?: number | null) => `${Number(value ?? 0).toLocaleString("ko-KR")}원`;
const formatRate = (value?: number | null) => `${Number(value ?? 0).toFixed(1)}%`;
const resultLabel = (value?: string | null) => RESULT_TYPE_OPTIONS.find((item) => item.value === value)?.label || "보유중";
const parseLines = (value?: string | null) =>
  (value || "")
    .split("\n")
    .map((line) => line.replace(/^\s*[-*]\s*/, "").trim())
    .filter(Boolean);

const emptySummary: TradeReviewSummary = {
  total_trades: 0,
  reviewed_count: 0,
  unreviewed_count: 0,
  review_rate: 0,
  principle_followed_count: 0,
  principle_violation_count: 0,
  impulse_trade_count: 0,
  grade_counts: { A: 0, B: 0, C: 0, D: 0 },
  top_mistakes: [],
};

function toForm(detail?: TradeReviewDetail | null): TradeReviewSaveRequest {
  const review = detail?.review;
  return {
    review_status: review?.review_status || "복기완료",
    trade_grade: review?.trade_grade || "",
    principle_followed: review?.principle_followed || "미확인",
    entry_quality: review?.entry_quality || "미확인",
    exit_quality: review?.exit_quality || "미확인",
    risk_control_quality: review?.risk_control_quality || "미확인",
    emotion_control_quality: review?.emotion_control_quality || "미확인",
    impulse_trade: Number(review?.impulse_trade || 0) === 1,
    main_mistake: review?.main_mistake || "",
    good_point: review?.good_point || "",
    improvement_point: review?.improvement_point || "",
    next_action: review?.next_action || "",
    review_memo: review?.review_memo || "",
    gpt_review_text: review?.gpt_review_text || "",
  };
}

function TradeReviewsPage() {
  const [items, setItems] = useState<TradeReviewListItem[]>([]);
  const [summary, setSummary] = useState<TradeReviewSummary>(emptySummary);
  const [tradeMethods, setTradeMethods] = useState<TradeMethod[]>([]);
  const [selectedJournalId, setSelectedJournalId] = useState<number | null>(null);
  const [detail, setDetail] = useState<TradeReviewDetail | null>(null);
  const [form, setForm] = useState<TradeReviewSaveRequest>(toForm(null));
  const [checkItems, setCheckItems] = useState<TradeReviewCheckItem[]>([]);
  const [gptPackage, setGptPackage] = useState<TradeReviewGptPackage | null>(null);
  const [gptPackageLoading, setGptPackageLoading] = useState(false);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({
    period: "30",
    from_date: daysAgo(30),
    to_date: today(),
    review_status: "",
    result_type: "",
    method_id: "",
    main_mistake: "",
    impulse_trade: "",
    trade_grade: "",
    principle_followed: "",
    stock_name: "",
  });

  const safeItems = useMemo(() => {
    const rows = Array.isArray(items) ? items : [];
    if (!filters.principle_followed) return rows;
    return rows.filter((item) => (item.principle_followed || "") === filters.principle_followed);
  }, [items, filters.principle_followed]);
  const principleUnknownCount = useMemo(
    () => (Array.isArray(items) ? items.filter((item) => !item.principle_followed || item.principle_followed === "미확인").length : 0),
    [items]
  );
  const topMistake = summary.reviewed_count > 0 && summary.top_mistakes[0]?.name ? summary.top_mistakes[0].name : "데이터 부족";
  const selectedGradeOption = GRADE_OPTIONS.find((grade) => grade.value === form.trade_grade);
  const checkedItemCount = checkItems.filter((item) => Number(item.is_checked || 0) === 1).length;
  const failureHitCount = checkItems.filter((item) => item.item_type === "failure" && Number(item.is_checked || 0) === 1).length;

  const loadTradeMethods = async () => {
    const rows = await repositories.tradeJournals.listTradeMethods({ is_active: 1 });
    setTradeMethods(rows);
  };

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [listResponse, summaryResponse] = await Promise.all([
        repositories.tradeReviews.fetchTradeReviews({
          from_date: filters.from_date,
          to_date: filters.to_date,
          review_status: filters.review_status || undefined,
          trade_grade: filters.trade_grade || undefined,
          result_type: filters.result_type || undefined,
          method_id: filters.method_id ? Number(filters.method_id) : undefined,
          stock_name: filters.stock_name || undefined,
          main_mistake: filters.main_mistake || undefined,
          impulse_trade: filters.impulse_trade || undefined,
          limit: 100,
          offset: 0,
        }),
        repositories.tradeReviews.fetchTradeReviewSummary({
          from_date: filters.from_date,
          to_date: filters.to_date,
        }),
      ]);
      setItems(listResponse.items ?? []);
      setSummary(summaryResponse ?? emptySummary);
    } catch (e) {
      setError(e instanceof Error ? e.message : "매매일지 복기 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTradeMethods();
    void load();
  }, []);

  const applyPeriod = (period: string) => {
    const range = period === "7" ? 7 : period === "90" ? 90 : 30;
    setFilters((prev) => ({
      ...prev,
      period,
      from_date: period === "custom" ? prev.from_date : daysAgo(range),
      to_date: period === "custom" ? prev.to_date : today(),
    }));
  };

  const openDetail = async (journalId: number) => {
    setSelectedJournalId(journalId);
    setDetailLoading(true);
    setError("");
    try {
      const response = await repositories.tradeReviews.fetchTradeReviewDetail(journalId);
      setDetail(response);
      setForm(toForm(response));
      setCheckItems(response.check_items ?? []);
      setGptPackage(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "복기 상세 조회에 실패했습니다.");
    } finally {
      setDetailLoading(false);
    }
  };

  const save = async () => {
    if (!selectedJournalId) return;
    setSaving(true);
    setError("");
    try {
      const saved = await repositories.tradeReviews.saveTradeReview(selectedJournalId, {
        ...form,
        review_status: form.review_status || "복기완료",
        check_items: checkItems.map((item) => ({
          id: item.id,
          is_checked: Number(item.is_checked || 0) === 1,
          note: item.note || "",
        })),
      });
      setDetail(saved);
      setForm(toForm(saved));
      setCheckItems(saved.check_items ?? []);
      setMessage("매매일지 복기가 저장되었습니다.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "매매일지 복기 저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const closeDetail = () => {
    setSelectedJournalId(null);
    setDetail(null);
    setCheckItems([]);
    setGptPackage(null);
  };

  const updateForm = <K extends keyof TradeReviewSaveRequest>(key: K, value: TradeReviewSaveRequest[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const updateCheckItem = (itemId: number, patch: Partial<TradeReviewCheckItem>) => {
    setCheckItems((prev) => prev.map((item) => (item.id === itemId ? { ...item, ...patch } : item)));
  };

  const generateGptPackage = async () => {
    if (!selectedJournalId) return;
    setGptPackageLoading(true);
    setError("");
    try {
      const pkg = await repositories.tradeReviews.fetchTradeReviewGptPackage(selectedJournalId);
      setGptPackage(pkg);
      setMessage("GPT 복기 패키지를 생성했습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "GPT 복기 패키지 생성에 실패했습니다.");
    } finally {
      setGptPackageLoading(false);
    }
  };

  const copyGptPackage = async () => {
    if (!gptPackage?.generated_prompt) return;
    try {
      await navigator.clipboard.writeText(gptPackage.generated_prompt);
      setMessage("GPT 복기 패키지를 복사했습니다.");
    } catch {
      setError("클립보드 복사에 실패했습니다.");
    }
  };

  return (
    <div className="space-y-4">
      <div className="journal-hero-row review-hero-row">
        <section className="journal-hero-panel">
          <h1>매매일지 복기</h1>
          <p>매매일지 데이터를 기반으로 원칙 준수, 충동매매, 반복 실수를 점검합니다.</p>
        </section>

        <section className="review-kpi-bar review-kpi-hero" aria-label="매매일지 복기 요약">
          {[
            ["총 매매", `${summary.total_trades}건`, ""],
            ["복기완료", `${summary.reviewed_count}건`, "success"],
            ["미복기", `${summary.unreviewed_count}건`, "warning"],
            ["완료율", `${summary.review_rate.toFixed(1)}%`, ""],
            ["원칙위반", `${summary.principle_violation_count}건`, "danger"],
            ["원칙미확인", `${principleUnknownCount}건`, "warning"],
            ["충동매매", `${summary.impulse_trade_count}건`, "danger"],
            ["반복실수", topMistake, "muted"],
          ].map(([label, value, tone]) => (
            <div key={label} className={`review-kpi-pill ${tone ? `is-${tone}` : ""}`}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </section>
      </div>

      {(message || error) ? (
        <div className={`review-compact-alert ${error ? "is-error" : "is-success"}`}>
          {error || message}
        </div>
      ) : null}

      <SectionCard title="필터">
        <div className="review-filter-compact">
          <select className="select-control" value={filters.period} onChange={(e) => applyPeriod(e.target.value)}>
            <option value="7">최근 7일</option>
            <option value="30">최근 30일</option>
            <option value="90">최근 90일</option>
            <option value="custom">직접 선택</option>
          </select>
          <input
            className="input-control"
            type="date"
            value={filters.from_date}
            onChange={(e) => setFilters((p) => ({ ...p, period: "custom", from_date: e.target.value }))}
          />
          <input
            className="input-control"
            type="date"
            value={filters.to_date}
            onChange={(e) => setFilters((p) => ({ ...p, period: "custom", to_date: e.target.value }))}
          />
          <select className="select-control" value={filters.review_status} onChange={(e) => setFilters((p) => ({ ...p, review_status: e.target.value }))}>
            {REVIEW_STATUS_OPTIONS.map((status) => (
              <option key={status} value={status === "전체" ? "" : status}>
                {status}
              </option>
            ))}
          </select>
          <select className="select-control" value={filters.result_type} onChange={(e) => setFilters((p) => ({ ...p, result_type: e.target.value }))}>
            {RESULT_TYPE_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select className="select-control" value={filters.method_id} onChange={(e) => setFilters((p) => ({ ...p, method_id: e.target.value }))}>
            <option value="">매매기법 전체</option>
            {tradeMethods.map((method) => (
              <option key={method.id} value={method.id}>
                {method.method_name}
              </option>
            ))}
          </select>
          <input
            className="input-control"
            value={filters.stock_name}
            onChange={(e) => setFilters((p) => ({ ...p, stock_name: e.target.value }))}
            placeholder="종목명 검색"
          />
          <button type="button" className="btn btn-primary" onClick={() => void load()} disabled={loading}>
            {loading ? "조회 중..." : "조회"}
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => setShowAdvancedFilters((prev) => !prev)}>
            {showAdvancedFilters ? "고급 닫기" : "고급 필터"}
          </button>
        </div>
        {showAdvancedFilters ? (
          <div className="review-filter-advanced">
            <select className="select-control" value={filters.main_mistake} onChange={(e) => setFilters((p) => ({ ...p, main_mistake: e.target.value }))}>
              {MISTAKE_OPTIONS.map((mistake) => (
                <option key={mistake || "all"} value={mistake}>
                  {mistake || "실수 유형 전체"}
                </option>
              ))}
            </select>
            <select className="select-control" value={filters.impulse_trade} onChange={(e) => setFilters((p) => ({ ...p, impulse_trade: e.target.value }))}>
              <option value="">충동매매 전체</option>
              <option value="true">예</option>
              <option value="false">아니오</option>
            </select>
            <select className="select-control" value={filters.trade_grade} onChange={(e) => setFilters((p) => ({ ...p, trade_grade: e.target.value }))}>
              <option value="">등급 전체</option>
              <option value="A">A급</option>
              <option value="B">B급</option>
              <option value="C">C급</option>
              <option value="D">D급</option>
            </select>
            <select className="select-control" value={filters.principle_followed} onChange={(e) => setFilters((p) => ({ ...p, principle_followed: e.target.value }))}>
              <option value="">원칙 준수 전체</option>
              {PRINCIPLE_OPTIONS.map((option) => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="복기 대상 매매 목록">
        <div className="table-shell">
          <table className="data-table compact-table trade-review-table">
            <thead>
              <tr>
                <th>복기상태</th>
                <th>종목명</th>
                <th>매수/매도일</th>
                <th>매매기법</th>
                <th>결과</th>
                <th>수익률</th>
                <th>등급</th>
                <th>원칙준수</th>
                <th>주요실수</th>
                <th>이미지</th>
                <th>관리</th>
              </tr>
            </thead>
            <tbody>
              {safeItems.map((item) => (
                <tr
                  key={item.journal_id}
                  className={`row-clickable ${selectedJournalId === item.journal_id ? "selected-row" : ""}`}
                  onClick={() => void openDetail(item.journal_id)}
                >
                  <td>
                    <span className={`badge ${item.review_status === "복기완료" ? "badge-emerald" : "badge-amber"}`}>
                      {item.review_status}
                    </span>
                  </td>
                  <td>{item.stock_name}</td>
                  <td className="review-date-cell">
                    <span>{item.buy_date?.slice(0, 10)}</span>
                    <small>{item.sell_date?.slice(0, 10) || "미매도"}</small>
                  </td>
                  <td>{item.method_name || "-"}</td>
                  <td>{item.result_type === "holding" ? "보유중/중간점검" : resultLabel(item.result_type)}</td>
                  <td>{formatRate(item.profit_rate)}</td>
                  <td>{item.trade_grade || "-"}</td>
                  <td>{item.principle_followed || "-"}</td>
                  <td>{item.main_mistake || "-"}</td>
                  <td>{item.image_count}</td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-secondary btn-table-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        void openDetail(item.journal_id);
                      }}
                    >
                      {item.review_status === "복기완료" ? "복기수정" : "복기하기"}
                    </button>
                  </td>
                </tr>
              ))}
              {safeItems.length === 0 ? (
                <tr>
                  <td colSpan={11} className="py-6 text-center text-sm text-slate-500">
                    복기 대상 매매가 없습니다.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {selectedJournalId ? (
        <>
          <div className="trade-journal-detail-dim" onClick={closeDetail} />
          <aside className="trade-journal-detail-drawer">
            <div className="trade-journal-detail-drawer-header">
              <div>
                <h3>매매일지 복기</h3>
                <p className="mt-1 text-xs text-slate-500">손실이어도 원칙을 지켰다면 B급 매매일 수 있습니다.</p>
              </div>
              <button type="button" className="btn btn-secondary" onClick={closeDetail}>
                닫기
              </button>
            </div>
            {detail ? (
              <div className="review-detail-summary">
                <span>상태 <b>{form.review_status || "미복기"}</b></span>
                <span>등급 <b>{form.trade_grade || "-"}</b></span>
                <span>원칙 <b>{form.principle_followed || "미확인"}</b></span>
                <span className={form.impulse_trade ? "is-danger" : ""}>충동 <b>{form.impulse_trade ? "예" : "아니오"}</b></span>
              </div>
            ) : null}
            <div className="trade-journal-detail-drawer-body space-y-4">
              {detailLoading || !detail ? (
                <p className="text-sm text-slate-500">복기 상세를 불러오는 중입니다.</p>
              ) : (
                <>
                  <div className="detail-section">
                    <h4 className="detail-label mb-2">매매 기본정보</h4>
                    <div className="trade-review-info-grid">
                      <div><span>종목명</span><strong>{detail.journal.stock_name}</strong></div>
                      <div><span>매수/매도일</span><strong>{detail.journal.buy_date} / {detail.journal.sell_date || "-"}</strong></div>
                      <div><span>매수가/매도가</span><strong>{detail.journal.buy_price || "-"} / {detail.journal.sell_price || "-"}</strong></div>
                      <div><span>수익률</span><strong>{formatRate(detail.journal.profit_rate)}</strong></div>
                      <div><span>실현손익</span><strong>{formatWon(detail.journal.realized_profit)}</strong></div>
                      <div><span>매매기법</span><strong>{detail.method?.method_name || detail.journal.trade_method_name || "-"}</strong></div>
                      <div><span>이미지 수</span><strong>{detail.image_count}개</strong></div>
                    </div>
                  </div>

                  <details className="detail-section review-accordion">
                    <summary>
                      <span>원본 메모/이미지 정보</span>
                      <small>이미지 {detail.image_count}개</small>
                    </summary>
                    <div className="review-origin-notes">
                      <p><b>매수 이유:</b> {detail.journal.trade_reason || "-"}</p>
                      <p><b>매도 이유:</b> {detail.journal.success_reason || detail.journal.failure_reason || "-"}</p>
                      <p><b>기존 복기 메모:</b> {detail.journal.review_memo || "-"}</p>
                      <p><b>이미지:</b> {detail.image_count}개</p>
                    </div>
                  </details>

                  <details className="detail-section review-accordion">
                    <summary>
                      <span>매매기법 기준</span>
                      <small>진입/청산/실패/체크리스트</small>
                    </summary>
                    <div className="trade-review-rule-grid">
                      {[
                        ["진입 조건", detail.method?.entry_rule],
                        ["청산 조건", detail.method?.exit_rule],
                        ["실패 패턴", detail.method?.stop_loss_rule],
                        ["체크리스트", detail.method?.take_profit_rule],
                      ].map(([title, value]) => (
                        <div key={title} className="trade-review-rule-card">
                          <strong>{title}</strong>
                          <ul>
                            {parseLines(value).length > 0 ? parseLines(value).map((line) => <li key={line}>{line}</li>) : <li>등록된 내용이 없습니다.</li>}
                          </ul>
                        </div>
                      ))}
                    </div>
                  </details>

                  <details className="detail-section review-accordion">
                    <summary>
                      <span>매매기법 체크</span>
                      <small>{checkedItemCount}/{checkItems.length} · 실패패턴 {failureHitCount}개 해당</small>
                    </summary>
                    <p className="mb-3 text-xs text-slate-500">
                      이 매매가 등록된 매매기법 기준을 얼마나 지켰는지 확인합니다.
                    </p>
                    {!detail.method ? (
                      <div className="trade-review-empty-note">
                        연결된 매매기법이 없어 체크 항목을 자동 생성할 수 없습니다. 매매일지에서 매매기법을 선택하면 복기 체크리스트를 사용할 수 있습니다.
                      </div>
                    ) : checkItems.length === 0 ? (
                      <div className="trade-review-empty-note">
                        이 매매기법에 등록된 진입/청산/실패/체크리스트 기준이 없습니다. 매매기법 화면에서 기준을 입력하면 복기 체크 항목으로 사용할 수 있습니다.
                      </div>
                    ) : (
                      <div className="trade-review-checklist-groups">
                        {CHECK_ITEM_GROUPS.map((group) => {
                          const groupItems = checkItems.filter((item) => item.item_type === group.type);
                          if (groupItems.length === 0) return null;
                          return (
                            <section key={group.type} className={`trade-review-checklist-group ${group.type === "failure" ? "is-failure" : ""}`}>
                              <div className="trade-review-checklist-head">
                                <strong>{group.title}</strong>
                                <span>{group.help}</span>
                              </div>
                              <div className="trade-review-checklist-items">
                                {groupItems.map((item) => (
                                  <label key={item.id} className="trade-review-check-item">
                                    <input
                                      type="checkbox"
                                      checked={Number(item.is_checked || 0) === 1}
                                      onChange={(e) => updateCheckItem(item.id, { is_checked: e.target.checked ? 1 : 0 })}
                                    />
                                    <div className="trade-review-check-item-body">
                                      <span>{group.type === "failure" ? `${item.item_text}에 해당` : item.item_text}</span>
                                      <input
                                        className="input-control trade-review-check-note"
                                        value={item.note || ""}
                                        onChange={(e) => updateCheckItem(item.id, { note: e.target.value })}
                                        placeholder="메모"
                                      />
                                    </div>
                                  </label>
                                ))}
                              </div>
                            </section>
                          );
                        })}
                      </div>
                    )}
                  </details>

                  <div className="detail-section">
                    <h4 className="detail-label mb-2">복기 입력</h4>
                    <div className="review-compact-form">
                      <div className="trade-detail-field">
                        <label className="detail-label">복기 상태</label>
                        <select className="select-control" value={form.review_status || "복기완료"} onChange={(e) => updateForm("review_status", e.target.value as "미복기" | "복기완료")}>
                          <option value="미복기">미복기</option>
                          <option value="복기완료">복기완료</option>
                        </select>
                      </div>
                      <div className="trade-detail-field">
                        <label className="detail-label">원칙 준수 여부</label>
                        <select className="select-control" value={form.principle_followed || "미확인"} onChange={(e) => updateForm("principle_followed", e.target.value)}>
                          {PRINCIPLE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                        </select>
                      </div>
                      <div className="trade-detail-field">
                        <label className="detail-label">진입 품질</label>
                        <select className="select-control" value={form.entry_quality || "미확인"} onChange={(e) => updateForm("entry_quality", e.target.value)}>
                          {QUALITY_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                        </select>
                      </div>
                      <div className="trade-detail-field">
                        <label className="detail-label">청산 품질</label>
                        <select className="select-control" value={form.exit_quality || "미확인"} onChange={(e) => updateForm("exit_quality", e.target.value)}>
                          {QUALITY_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                        </select>
                      </div>
                      <div className="trade-detail-field">
                        <label className="detail-label">리스크 관리</label>
                        <select className="select-control" value={form.risk_control_quality || "미확인"} onChange={(e) => updateForm("risk_control_quality", e.target.value)}>
                          {QUALITY_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                        </select>
                      </div>
                      <div className="trade-detail-field">
                        <label className="detail-label">감정 통제</label>
                        <select className="select-control" value={form.emotion_control_quality || "미확인"} onChange={(e) => updateForm("emotion_control_quality", e.target.value)}>
                          {QUALITY_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                        </select>
                      </div>
                      <div className="trade-detail-field">
                        <label className="detail-label">주요 실수</label>
                        <select className="select-control" value={form.main_mistake || ""} onChange={(e) => updateForm("main_mistake", e.target.value)}>
                          {MISTAKE_OPTIONS.map((mistake) => <option key={mistake || "none"} value={mistake}>{mistake || "선택 안 함"}</option>)}
                        </select>
                      </div>
                      <label className={`review-impulse-check ${form.impulse_trade ? "is-checked" : ""}`}>
                        <input type="checkbox" checked={Boolean(form.impulse_trade)} onChange={(e) => updateForm("impulse_trade", e.target.checked)} />
                        충동매매였음
                      </label>
                    </div>
                  </div>

                  <div className="detail-section">
                    <h4 className="detail-label mb-1">매매 등급</h4>
                    <p className="mb-2 text-xs text-slate-500">손실이어도 원칙을 지켰다면 B급 매매일 수 있습니다.</p>
                    <div className="review-grade-segment">
                      {GRADE_OPTIONS.map((grade) => (
                        <button
                          key={grade.value}
                          type="button"
                          className={form.trade_grade === grade.value ? "selected" : ""}
                          onClick={() => updateForm("trade_grade", grade.value)}
                        >
                          <strong>{grade.title}</strong>
                          <span>{grade.description}</span>
                        </button>
                      ))}
                    </div>
                    {selectedGradeOption ? <p className="review-grade-help">{selectedGradeOption.title}: {selectedGradeOption.description}</p> : null}
                  </div>

                  <div className="detail-section">
                    <h4 className="detail-label mb-2">습관 교정 메모</h4>
                    <div className="review-memo-grid">
                      <textarea className="textarea-control" value={form.good_point || ""} onChange={(e) => updateForm("good_point", e.target.value)} placeholder="잘한 점을 적어 주세요." />
                      <textarea className="textarea-control" value={form.improvement_point || ""} onChange={(e) => updateForm("improvement_point", e.target.value)} placeholder="개선할 점을 적어 주세요." />
                      <textarea className="textarea-control" value={form.next_action || ""} onChange={(e) => updateForm("next_action", e.target.value)} placeholder="다음 매매 전 반드시 지킬 것을 적어 주세요." />
                    </div>
                  </div>

                  <details className="detail-section review-accordion">
                    <summary>
                      <span>상세 메모</span>
                      <small>복기 메모</small>
                    </summary>
                    <textarea className="textarea-control" value={form.review_memo || ""} onChange={(e) => updateForm("review_memo", e.target.value)} placeholder="복기 메모를 자유롭게 적어 주세요." />
                  </details>

                  <details className="detail-section review-accordion">
                    <summary>
                      <span>GPT 복기</span>
                      <small>패키지 생성 · 결과 저장</small>
                    </summary>
                    <div className="trade-review-gpt-head">
                      <div>
                        <p className="text-xs text-slate-500">
                          매매일지, 매매기법, 체크 결과를 묶어 GPT에 붙여넣을 복기 요청문을 생성합니다.
                        </p>
                      </div>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => void generateGptPackage()}
                        disabled={gptPackageLoading}
                      >
                        {gptPackageLoading ? "생성 중..." : "GPT 복기 패키지 생성"}
                      </button>
                    </div>
                    <p className="trade-review-gpt-help">
                      현재 화면에 입력한 복기 내용이 저장되지 않았다면 패키지에 반영되지 않을 수 있습니다. 먼저 복기 저장 후 패키지를 생성하는 것을 권장합니다.
                    </p>
                    {gptPackage ? (
                      <div className="trade-review-gpt-package">
                        <div className="trade-review-gpt-package-title">
                          <strong>{gptPackage.package_title}</strong>
                          <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void copyGptPackage()}>
                            복사
                          </button>
                        </div>
                        <textarea
                          className="textarea-control trade-review-gpt-prompt"
                          value={gptPackage.generated_prompt}
                          readOnly
                        />
                      </div>
                    ) : null}
                    <div className="trade-review-gpt-result">
                      <label className="detail-label">GPT 복기 결과</label>
                      <textarea
                        className="textarea-control"
                        value={form.gpt_review_text || ""}
                        onChange={(e) => updateForm("gpt_review_text", e.target.value)}
                        placeholder="GPT 분석 결과를 여기에 붙여넣고 복기 저장을 누르세요."
                      />
                    </div>
                  </details>
                </>
              )}
            </div>
            <div className="trade-journal-detail-drawer-footer">
              <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={saving || detailLoading}>
                {saving ? "저장 중..." : "복기 저장"}
              </button>
              <button type="button" className="btn btn-secondary" onClick={closeDetail}>
                닫기
              </button>
            </div>
          </aside>
        </>
      ) : null}
    </div>
  );
}

export default TradeReviewsPage;
