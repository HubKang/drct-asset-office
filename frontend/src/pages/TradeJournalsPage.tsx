import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import { appConfig } from "@/services/config/appConfig";
import type {
  FailurePatternReviewPackage,
  TradeJournal,
  TradeJournalGptReviewPackage,
  TradeJournalImage,
  TradeJournalSaveRequest,
  TradeMethod,
} from "@/types/tradeJournal";

type DetailMode = "create" | "edit";

const RESULT_TYPE_OPTIONS = [
  { value: "", label: "전체" },
  { value: "holding", label: "보유중" },
  { value: "profit", label: "익절" },
  { value: "loss", label: "손절" },
  { value: "break_even", label: "본전" },
];

const IMAGE_TYPE_OPTIONS = [
  { value: "trade_time_chart", label: "매매 당시 차트" },
  { value: "after_trade_chart", label: "매매 이후 차트" },
];

const today = () => new Date().toISOString().slice(0, 10);
const threeMonthsAgo = () => {
  const d = new Date();
  d.setMonth(d.getMonth() - 3);
  return d.toISOString().slice(0, 10);
};
const formatWon = (value?: number | null) => `${Number(value ?? 0).toLocaleString("ko-KR")}원`;
const formatRate = (value?: number | null) => `${Number(value ?? 0).toFixed(1)}%`;

function TradeJournalsPage() {
  const [items, setItems] = useState<TradeJournal[]>([]);
  const [tradeMethods, setTradeMethods] = useState<TradeMethod[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [filters, setFilters] = useState({
    start_date: today(),
    end_date: today(),
    stock_name: "",
    result_type: "",
  });
  const [selectedJournalId, setSelectedJournalId] = useState<number | null>(null);
  const [detailMode, setDetailMode] = useState<DetailMode>("create");
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailImages, setDetailImages] = useState<TradeJournalImage[]>([]);
  const [gptPackage, setGptPackage] = useState<TradeJournalGptReviewPackage | null>(null);
  const [failurePatternPackage, setFailurePatternPackage] = useState<FailurePatternReviewPackage | null>(null);
  const [failureLoading, setFailureLoading] = useState(false);

  const [form, setForm] = useState<TradeJournalSaveRequest>({
    buy_date: today(),
    sell_date: today(),
    stock_name: "",
    result_type: "holding",
    profit_rate: 0,
    realized_profit: 0,
  });
  const [imageType, setImageType] = useState("trade_time_chart");
  const [imageMemo, setImageMemo] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);

  const totalRealized = useMemo(
    () => items.reduce((acc, row) => acc + Number(row.realized_profit ?? 0), 0),
    [items]
  );

  const loadTradeMethods = async () => {
    const rows = await repositories.tradeJournals.listTradeMethods({ is_active: 1 });
    setTradeMethods(rows);
  };

  const loadList = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await repositories.tradeJournals.fetchTradeJournals({
        start_date: filters.start_date,
        end_date: filters.end_date,
        stock_name: filters.stock_name || undefined,
        result_type: filters.result_type || undefined,
      });
      setItems(response.items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "목록 조회에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTradeMethods();
    void loadList();
  }, []);

  const loadDetail = async (id: number) => {
    const [detail, images] = await Promise.all([
      repositories.tradeJournals.fetchTradeJournalDetail(id),
      repositories.tradeJournals.fetchTradeJournalImages(id),
    ]);
    setForm({
      buy_date: detail.buy_date?.slice(0, 10) || today(),
      sell_date: detail.sell_date?.slice(0, 10) || null,
      stock_code: detail.stock_code || "",
      stock_name: detail.stock_name || "",
      stock_theme: detail.stock_theme || "",
      trade_method_id: detail.trade_method_id ?? null,
      result_type: detail.result_type || "holding",
      profit_rate: detail.profit_rate ?? 0,
      realized_profit: detail.realized_profit ?? 0,
      trade_reason: detail.trade_reason || "",
      success_reason: detail.success_reason || "",
      failure_reason: detail.failure_reason || "",
      review_memo: detail.review_memo || "",
      remark: detail.remark || "",
    });
    setDetailImages(images ?? []);
  };

  const openCreate = () => {
    setSelectedJournalId(null);
    setDetailMode("create");
    setIsDetailOpen(true);
    setGptPackage(null);
    setForm({
      buy_date: today(),
      sell_date: today(),
      stock_name: "",
      result_type: "holding",
      profit_rate: 0,
      realized_profit: 0,
    });
    setDetailImages([]);
  };

  const openEdit = async (id: number) => {
    setSelectedJournalId(id);
    setDetailMode("edit");
    setIsDetailOpen(true);
    setGptPackage(null);
    await loadDetail(id);
  };

  const save = async () => {
    if (!form.stock_name?.trim()) {
      setError("종목명은 필수입니다.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (detailMode === "create") {
        const created = await repositories.tradeJournals.createTradeJournal(form);
        setSelectedJournalId(created.id);
        setDetailMode("edit");
      } else if (selectedJournalId) {
        await repositories.tradeJournals.updateTradeJournal(selectedJournalId, form);
      }
      await loadList();
      if (selectedJournalId) await loadDetail(selectedJournalId);
      setMessage("저장되었습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const uploadImage = async () => {
    if (!selectedJournalId || !imageFile) return;
    await repositories.tradeJournals.uploadTradeJournalImage(selectedJournalId, {
      image_type: imageType,
      image_memo: imageMemo,
      file: imageFile,
    });
    setImageFile(null);
    setImageMemo("");
    await loadDetail(selectedJournalId);
    await loadList();
  };

  const generatePackage = async () => {
    if (!selectedJournalId) return;
    const pkg = await repositories.tradeJournals.fetchGptReviewPackage(selectedJournalId);
    setGptPackage(pkg);
  };

  const copyPackage = async () => {
    if (!gptPackage?.markdown) return;
    await navigator.clipboard.writeText(gptPackage.markdown);
    setMessage("GPT 복기 패키지가 복사되었습니다.");
  };

  const generateFailurePatternPackage = async () => {
    setFailureLoading(true);
    setError("");
    try {
      const fromDate = filters.start_date || threeMonthsAgo();
      const toDate = filters.end_date || today();
      const pkg = await repositories.tradeJournals.fetchFailurePatternReviewPackage({
        from_date: fromDate,
        to_date: toDate,
      });
      setFailurePatternPackage(pkg);
      setMessage("GPT 실패 패턴 분석 패키지를 생성했습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "실패 패턴 패키지 생성에 실패했습니다.");
    } finally {
      setFailureLoading(false);
    }
  };

  const copyFailurePatternPackage = async () => {
    if (!failurePatternPackage?.markdown) return;
    await navigator.clipboard.writeText(failurePatternPackage.markdown);
    setMessage("GPT 실패 패턴 분석 패키지가 복사되었습니다.");
  };

  return (
    <div className="space-y-4">
      <PageHeader title="매매일지" description="매매일지 관리 · GPT 매매복기" />

      <SectionCard title="조회 기간">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-6">
          <input
            className="input-control"
            type="date"
            value={filters.start_date}
            onChange={(e) => setFilters((p) => ({ ...p, start_date: e.target.value }))}
            aria-label="시작일"
          />
          <input
            className="input-control"
            type="date"
            value={filters.end_date}
            onChange={(e) => setFilters((p) => ({ ...p, end_date: e.target.value }))}
            aria-label="종료일"
          />
          <input
            className="input-control"
            value={filters.stock_name}
            onChange={(e) => setFilters((p) => ({ ...p, stock_name: e.target.value }))}
            placeholder="종목명"
          />
          <select
            className="select-control"
            value={filters.result_type}
            onChange={(e) => setFilters((p) => ({ ...p, result_type: e.target.value }))}
          >
            {RESULT_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn-primary" onClick={() => void loadList()}>
            {loading ? "조회 중" : "조회"}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() =>
              setFilters({
                start_date: today(),
                end_date: today(),
                stock_name: "",
                result_type: "",
              })
            }
          >
            초기화
          </button>
        </div>
      </SectionCard>

      <SectionCard title="GPT 실패 패턴 분석 패키지">
        <p className="mb-2 text-sm text-slate-600">
          기간/목록 단위로 손실 거래, 손절 거래, 실패 사유 기록 거래를 모아 실패 패턴을 분석합니다.
        </p>
        <div className="mb-2 flex flex-wrap gap-2">
          <button type="button" className="btn btn-secondary" onClick={() => void generateFailurePatternPackage()} disabled={failureLoading}>
            {failureLoading ? "생성 중..." : "GPT 실패 패턴 분석 패키지 생성"}
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => void copyFailurePatternPackage()} disabled={!failurePatternPackage?.markdown}>
            전체 복사
          </button>
        </div>
        <div className="rounded border border-slate-200 bg-slate-50 p-3">
          <p className="mb-2 text-sm font-medium text-slate-700">GPT 실패 패턴 분석 패키지 미리보기</p>
          {failurePatternPackage?.markdown ? (
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-slate-700">{failurePatternPackage.markdown}</pre>
          ) : (
            <p className="text-sm text-slate-500">패키지를 생성하면 이 영역에 Markdown 미리보기가 표시됩니다.</p>
          )}
        </div>
      </SectionCard>

      {message ? <p className="inline-result inline-success">{message}</p> : null}
      {error ? <p className="inline-result inline-error">{error}</p> : null}

      <SectionCard title="매매일지 목록">
        <div className="mb-2 flex justify-end">
          <button type="button" className="btn btn-primary" onClick={openCreate}>
            새 매매일지
          </button>
        </div>
        <div className="trade-journal-table-shell">
          <table className="data-table trade-journal-table">
            <thead>
              <tr>
                <th>매수일</th>
                <th>매도일</th>
                <th>종목명</th>
                <th>상태</th>
                <th>수익률</th>
                <th>실현손익</th>
                <th>이미지</th>
                <th>관리</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="trade-journal-row" onClick={() => void openEdit(item.id)}>
                  <td>{item.buy_date?.slice(0, 10)}</td>
                  <td>{item.sell_date?.slice(0, 10) || "-"}</td>
                  <td>{item.stock_name}</td>
                  <td>{RESULT_TYPE_OPTIONS.find((x) => x.value === (item.result_type || "holding"))?.label || "보유중"}</td>
                  <td>{formatRate(item.profit_rate)}</td>
                  <td>{formatWon(item.realized_profit)}</td>
                  <td>{item.image_count ?? 0}</td>
                  <td>상세</td>
                </tr>
              ))}
              <tr className="trade-journal-summary-row">
                <td colSpan={5}>실현손익 합계</td>
                <td>{formatWon(totalRealized)}</td>
                <td colSpan={2} />
              </tr>
            </tbody>
          </table>
        </div>
      </SectionCard>

      {isDetailOpen ? (
        <>
          <div className="trade-journal-detail-dim" onClick={() => setIsDetailOpen(false)} />
          <aside className="trade-journal-detail-drawer">
            <div className="trade-journal-detail-drawer-header">
              <h3>매매일지 상세</h3>
              <div className="trade-detail-header-actions">
                <button className="btn btn-secondary" onClick={() => void generatePackage()} type="button">
                  GPT 복기 패키지 생성
                </button>
                <button className="btn btn-secondary" onClick={() => void copyPackage()} type="button" disabled={!gptPackage}>
                  GPT 분석 요청문+JSON 복사
                </button>
                <button className="btn btn-secondary" onClick={() => setIsDetailOpen(false)} type="button">
                  닫기
                </button>
              </div>
            </div>
            <div className="trade-journal-detail-drawer-body">
              <div className="trade-detail-form-grid">
                <div className="trade-detail-field">
                  <label>매수일</label>
                  <input
                    className="input-control"
                    type="date"
                    value={(form.buy_date || "").slice(0, 10)}
                    onChange={(e) => setForm((p) => ({ ...p, buy_date: e.target.value }))}
                  />
                </div>
                <div className="trade-detail-field">
                  <label>매도일</label>
                  <input
                    className="input-control"
                    type="date"
                    value={(form.sell_date || "").slice(0, 10)}
                    onChange={(e) => setForm((p) => ({ ...p, sell_date: e.target.value }))}
                  />
                </div>
                <div className="trade-detail-field">
                  <label>종목명</label>
                  <input className="input-control" value={form.stock_name || ""} onChange={(e) => setForm((p) => ({ ...p, stock_name: e.target.value }))} />
                </div>
                <div className="trade-detail-field">
                  <label>테마</label>
                  <input className="input-control" value={form.stock_theme || ""} onChange={(e) => setForm((p) => ({ ...p, stock_theme: e.target.value }))} />
                </div>
                <div className="trade-detail-field">
                  <label>매매기법</label>
                  <select
                    className="select-control"
                    value={String(form.trade_method_id ?? "")}
                    onChange={(e) => setForm((p) => ({ ...p, trade_method_id: e.target.value ? Number(e.target.value) : null }))}
                  >
                    <option value="">선택</option>
                    {tradeMethods.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.method_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="trade-detail-field">
                  <label>상태</label>
                  <select className="select-control" value={form.result_type || "holding"} onChange={(e) => setForm((p) => ({ ...p, result_type: e.target.value }))}>
                    {RESULT_TYPE_OPTIONS.filter((x) => x.value).map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="detail-section">
                <label className="detail-label">매매 기록</label>
                <textarea className="textarea-control" placeholder="매매 기록" value={form.remark || ""} onChange={(e) => setForm((p) => ({ ...p, remark: e.target.value }))} />
              </div>

              <div className="trade-journal-detail-grid detail-section">
                <textarea className="textarea-control" placeholder="매매 이유" value={form.trade_reason || ""} onChange={(e) => setForm((p) => ({ ...p, trade_reason: e.target.value }))} />
                <textarea className="textarea-control" placeholder="성공 사유" value={form.success_reason || ""} onChange={(e) => setForm((p) => ({ ...p, success_reason: e.target.value }))} />
                <textarea className="textarea-control" placeholder="실패 사유" value={form.failure_reason || ""} onChange={(e) => setForm((p) => ({ ...p, failure_reason: e.target.value }))} />
                <textarea className="textarea-control" placeholder="복기 메모" value={form.review_memo || ""} onChange={(e) => setForm((p) => ({ ...p, review_memo: e.target.value }))} />
              </div>

              {gptPackage ? (
                <div className="detail-section">
                  <div className="rounded border border-slate-200 bg-slate-50 p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <strong>GPT 복기 패키지 미리보기</strong>
                      <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void copyPackage()}>
                        전체 복사
                      </button>
                    </div>
                    <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-slate-700">{gptPackage.markdown}</pre>
                  </div>
                </div>
              ) : null}

              <div className="detail-section">
                <div className="mb-2 flex items-center justify-between">
                  <strong>차트 이미지</strong>
                </div>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                  <select className="select-control" value={imageType} onChange={(e) => setImageType(e.target.value)}>
                    {IMAGE_TYPE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                  <input className="input-control" type="file" accept="image/*" onChange={(e) => setImageFile(e.target.files?.[0] ?? null)} />
                  <input className="input-control" value={imageMemo} onChange={(e) => setImageMemo(e.target.value)} placeholder="이미지 메모" />
                </div>
                <div className="mt-2">
                  <button type="button" className="btn btn-secondary" onClick={() => void uploadImage()} disabled={!selectedJournalId || !imageFile}>
                    이미지 업로드
                  </button>
                </div>
                <div className="trade-image-list mt-2">
                  {detailImages.map((img) => (
                    <article key={img.id} className="trade-journal-image-card">
                      <div>
                        <span className="badge badge-blue">{img.image_type}</span> <small>{img.original_filename || img.image_path}</small>
                      </div>
                      {img.image_url ? <img src={`${appConfig.apiBaseUrl}${img.image_url}`} className="trade-journal-image-preview" alt="trade" /> : null}
                      <p className="trade-image-memo">{img.image_memo || "메모 없음"}</p>
                    </article>
                  ))}
                </div>
              </div>
            </div>
            <div className="trade-journal-detail-drawer-footer">
              <button className="btn btn-primary" type="button" onClick={() => void save()} disabled={saving}>
                {saving ? "저장중" : detailMode === "create" ? "저장" : "수정"}
              </button>
              {detailMode === "edit" ? (
                <button className="btn btn-danger" type="button">
                  삭제
                </button>
              ) : null}
            </div>
          </aside>
        </>
      ) : null}
    </div>
  );
}

export default TradeJournalsPage;
