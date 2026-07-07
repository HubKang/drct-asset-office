import { useEffect, useMemo, useState } from "react";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import { appConfig } from "@/services/config/appConfig";
import type { AppImage } from "@/types/image";
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
const threeDaysAgo = () => {
  const d = new Date();
  d.setDate(d.getDate() - 3);
  return d.toISOString().slice(0, 10);
};
const threeMonthsAgo = () => {
  const d = new Date();
  d.setMonth(d.getMonth() - 3);
  return d.toISOString().slice(0, 10);
};
const formatWon = (value?: number | null) => `${Number(value ?? 0).toLocaleString("ko-KR")}원`;
const formatRate = (value?: number | null) => `${Number(value ?? 0).toFixed(1)}%`;
const safeNumber = (value?: number | null) => (Number.isFinite(Number(value)) ? Number(value) : 0);

function TradeJournalsPage() {
  const [items, setItems] = useState<TradeJournal[]>([]);
  const [tradeMethods, setTradeMethods] = useState<TradeMethod[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [filters, setFilters] = useState({
    start_date: threeDaysAgo(),
    end_date: today(),
    stock_name: "",
    result_type: "",
  });
  const [selectedJournalId, setSelectedJournalId] = useState<number | null>(null);
  const [detailMode, setDetailMode] = useState<DetailMode>("create");
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailImages, setDetailImages] = useState<TradeJournalImage[]>([]);
  const [detailAppImages, setDetailAppImages] = useState<AppImage[]>([]);
  const [gptPackage, setGptPackage] = useState<TradeJournalGptReviewPackage | null>(null);
  const [failurePatternPackage, setFailurePatternPackage] = useState<FailurePatternReviewPackage | null>(null);
  const [failureLoading, setFailureLoading] = useState(false);
  const [deletingJournal, setDeletingJournal] = useState(false);
  const [imageEditingId, setImageEditingId] = useState<number | null>(null);
  const [imageEditDraft, setImageEditDraft] = useState<{ image_type: string; image_memo: string }>({
    image_type: "trade_time_chart",
    image_memo: "",
  });
  const [savingImageEdit, setSavingImageEdit] = useState(false);
  const [deletingImageId, setDeletingImageId] = useState<number | null>(null);
  const [previewImage, setPreviewImage] = useState<{ src: string; title: string; caption?: string; badge?: string } | null>(null);

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

  const safeItems = useMemo(() => (Array.isArray(items) ? items : []), [items]);
  const safeMethods = useMemo(() => (Array.isArray(tradeMethods) ? tradeMethods : []), [tradeMethods]);

  const getImageTypeLabel = (value: string) => IMAGE_TYPE_OPTIONS.find((option) => option.value === value)?.label || value;
  const getImageUrl = (url?: string | null) => {
    if (!url) return "";
    if (/^https?:\/\//i.test(url) || url.startsWith("blob:")) return url;
    const normalized = url.startsWith("/") ? url : "/" + url;
    return appConfig.apiBaseUrl + normalized;
  };

  const summaryStats = useMemo(() => {
    const total = safeItems.length;
    const wins = safeItems.filter((row) => row.result_type === "profit").length;
    const losses = safeItems.filter((row) => row.result_type === "loss").length;
    const avgProfitRate = total > 0 ? safeItems.reduce((acc, row) => acc + safeNumber(row.profit_rate), 0) / total : 0;
    const realizedSum = safeItems.reduce((acc, row) => acc + safeNumber(row.realized_profit), 0);
    return { total, wins, losses, avgProfitRate, realizedSum };
  }, [safeItems]);

  const totalRealized = useMemo(
    () => safeItems.reduce((acc, row) => acc + safeNumber(row.realized_profit), 0),
    [safeItems]
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
      setItems(Array.isArray(response.items) ? response.items : []);
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

  useEffect(() => {
    if (!previewImage) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPreviewImage(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [previewImage]);

  const loadDetail = async (id: number) => {
    const [detail, images, appImages] = await Promise.all([
      repositories.tradeJournals.fetchTradeJournalDetail(id),
      repositories.tradeJournals.fetchTradeJournalImages(id),
      repositories.images.listImages({ domain: "trade_journal", owner_type: "trade_journal", owner_id: id }),
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
    setDetailAppImages(appImages.items);
  };

  const openCreate = () => {
    setSelectedJournalId(null);
    setDetailMode("create");
    setIsDetailOpen(true);
    setGptPackage(null);
    setImageEditingId(null);
    setForm({
      buy_date: today(),
      sell_date: today(),
      stock_name: "",
      result_type: "holding",
      profit_rate: 0,
      realized_profit: 0,
    });
    setDetailImages([]);
    setDetailAppImages([]);
    setPreviewImage(null);
  };

  const openEdit = async (id: number) => {
    setSelectedJournalId(id);
    setDetailMode("edit");
    setIsDetailOpen(true);
    setGptPackage(null);
    setImageEditingId(null);
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
        setMessage("매매일지가 저장되었습니다.");
        await loadDetail(created.id);
      } else if (selectedJournalId) {
        await repositories.tradeJournals.updateTradeJournal(selectedJournalId, form);
        setMessage("매매일지가 수정되었습니다.");
        await loadDetail(selectedJournalId);
      }
      await loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const uploadImage = async () => {
    if (!selectedJournalId || !imageFile) return;
    const imageTypeLabel = IMAGE_TYPE_OPTIONS.find((option) => option.value === imageType)?.label || imageType;
    const memo = imageMemo.trim();
    await repositories.images.uploadImage({
      domain: "trade_journal",
      owner_type: "trade_journal",
      owner_id: selectedJournalId,
      file: imageFile,
      description: memo ? imageTypeLabel + " - " + memo : imageTypeLabel,
    });
    setImageFile(null);
    setImageMemo("");
    setImageEditingId(null);
    await loadDetail(selectedJournalId);
    await loadList();
    setMessage("차트 이미지가 등록되었습니다.");
  };

  const startEditImage = (image: TradeJournalImage) => {
    setImageEditingId(image.id);
    setImageEditDraft({
      image_type: image.image_type,
      image_memo: image.image_memo || "",
    });
  };

  const cancelEditImage = () => {
    setImageEditingId(null);
  };

  const saveImageEdit = async (imageId: number) => {
    setSavingImageEdit(true);
    setError("");
    try {
      await repositories.tradeJournals.updateTradeJournalImage(imageId, {
        image_type: imageEditDraft.image_type,
        image_memo: imageEditDraft.image_memo,
      });
      setMessage("차트 이미지가 수정되었습니다.");
      setImageEditingId(null);
      if (selectedJournalId) await loadDetail(selectedJournalId);
      await loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "차트 이미지 수정에 실패했습니다.");
    } finally {
      setSavingImageEdit(false);
    }
  };

  const deleteImage = async (imageId: number) => {
    const ok = window.confirm("이 차트 이미지를 삭제하시겠습니까?");
    if (!ok) return;
    setDeletingImageId(imageId);
    setError("");
    try {
      await repositories.tradeJournals.deleteTradeJournalImage(imageId);
      setMessage("차트 이미지가 삭제되었습니다.");
      setImageEditingId((prev) => (prev === imageId ? null : prev));
      if (selectedJournalId) await loadDetail(selectedJournalId);
      await loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "차트 이미지 삭제에 실패했습니다.");
    } finally {
      setDeletingImageId(null);
    }
  };

  const deleteAppImage = async (imageId: number) => {
    const ok = window.confirm("이 차트 이미지를 삭제하시겠습니까?");
    if (!ok) return;
    setDeletingImageId(imageId);
    setError("");
    try {
      await repositories.images.deleteImage(imageId);
      setDetailAppImages((prev) => prev.filter((image) => image.id !== imageId));
      setMessage("차트 이미지가 삭제되었습니다.");
      await loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "차트 이미지 삭제에 실패했습니다.");
    } finally {
      setDeletingImageId(null);
    }
  };

  const deleteJournal = async () => {
    if (!selectedJournalId || detailMode !== "edit") return;
    const ok = window.confirm("이 매매일지를 삭제하시겠습니까? 등록된 차트 이미지도 함께 삭제될 수 있습니다.");
    if (!ok) return;
    setDeletingJournal(true);
    setError("");
    try {
      if (detailAppImages.length > 0) {
        await Promise.all(detailAppImages.map((image) => repositories.images.deleteImage(image.id)));
      }
      await repositories.tradeJournals.deleteTradeJournal(selectedJournalId);
      setMessage("매매일지가 삭제되었습니다.");
      setSelectedJournalId(null);
      setIsDetailOpen(false);
      setDetailMode("create");
      setImageEditingId(null);
      setDetailImages([]);
      setDetailAppImages([]);
      setPreviewImage(null);
      setGptPackage(null);
      await loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "매매일지 삭제에 실패했습니다.");
    } finally {
      setDeletingJournal(false);
    }
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
      <div className="journal-hero-row">
        <section className="journal-hero-panel">
          <h1>매매일지</h1>
          <p>매매일지 관리 · GPT 매매일지 복기</p>
        </section>

        <section className="journal-summary-compact" aria-label="매매일지 요약">
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">총 거래</span>
            <strong className="journal-summary-value">{summaryStats.total}건</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">승리</span>
            <strong className="journal-summary-value journal-summary-value-win">{summaryStats.wins}건</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">손실</span>
            <strong className="journal-summary-value journal-summary-value-loss">{summaryStats.losses}건</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">평균 수익률</span>
            <strong className="journal-summary-value">{formatRate(summaryStats.avgProfitRate)}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">실현손익 합계</span>
            <strong className="journal-summary-value journal-summary-value-money" title={formatWon(summaryStats.realizedSum)}>{formatWon(summaryStats.realizedSum)}</strong>
          </div>
        </section>
      </div>

      <SectionCard title="조회 기간">
        <div className="mb-2 text-xs text-slate-600">
          매수일 기준으로 매매일지를 조회합니다.
          <span className="info-dot" title="매수일 기준으로 매매일지를 조회합니다. 매도일 기준 분석은 후속 기능으로 분리됩니다.">i</span>
        </div>
        <div className="trade-journal-search-row">
          <input
            className="input-control trade-journal-date-input"
            type="date"
            value={filters.start_date}
            onChange={(e) => setFilters((p) => ({ ...p, start_date: e.target.value }))}
            aria-label="시작일"
          />
          <input
            className="input-control trade-journal-date-input"
            type="date"
            value={filters.end_date}
            onChange={(e) => setFilters((p) => ({ ...p, end_date: e.target.value }))}
            aria-label="종료일"
          />
          <input
            className="input-control trade-journal-stock-input"
            value={filters.stock_name}
            onChange={(e) => setFilters((p) => ({ ...p, stock_name: e.target.value }))}
            placeholder="종목명"
          />
          <select
            className="select-control trade-journal-status-select"
            value={filters.result_type}
            onChange={(e) => setFilters((p) => ({ ...p, result_type: e.target.value }))}
          >
            {RESULT_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn-primary trade-journal-search-btn" onClick={() => void loadList()}>
            {loading ? "조회 중" : "조회"}
          </button>
          <button
            type="button"
            className="btn btn-secondary trade-journal-reset-btn"
            onClick={() =>
              setFilters({
                start_date: threeDaysAgo(),
                end_date: today(),
                stock_name: "",
                result_type: "",
              })
            }
          >
            초기화
          </button>
          <button type="button" className="btn btn-secondary trade-journal-create-btn" onClick={openCreate}>
            + 새 매매일지
          </button>
        </div>
      </SectionCard>

      <SectionCard title="GPT 실패 패턴 분석 패키지">
        <div className="mb-2 text-xs text-slate-600">
          조회 기간 기준의 손실/실패 거래를 모아 GPT 분석 패키지를 생성합니다.
          <span className="info-dot" title="조회 기간 또는 목록 기준의 손실 거래, 실패 사유 기록 거래를 모아 GPT 분석 패키지를 생성합니다.">i</span>
        </div>
        <div className="mb-2 flex flex-wrap gap-2">
          <button type="button" className="btn btn-secondary" onClick={() => void generateFailurePatternPackage()} disabled={failureLoading}>
            {failureLoading ? "생성 중..." : "패키지 생성"}
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => void copyFailurePatternPackage()} disabled={!failurePatternPackage?.markdown}>
            전체 복사
          </button>
        </div>
        {failurePatternPackage?.markdown ? (
          <div className="rounded border border-slate-200 bg-slate-50 p-3">
            <p className="mb-2 text-sm font-medium text-slate-700">GPT 실패 패턴 분석 패키지 미리보기</p>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs text-slate-700">{failurePatternPackage.markdown}</pre>
          </div>
        ) : null}
      </SectionCard>

      {message ? <p className="inline-result inline-success">{message}</p> : null}
      {error ? <p className="inline-result inline-error">{error}</p> : null}

      <SectionCard title="매매일지 목록">
        <div className="trade-journal-table-shell">
          <table className="data-table trade-journal-table">
            <thead>
              <tr>
                <th>매수일</th>
                <th>매도일</th>
                <th>종목명</th>
                <th>상태</th>
                <th>결과</th>
                <th>매매기법</th>
                <th>수익률</th>
                <th>실현손익</th>
                <th>이미지 <span className="info-dot" title="등록된 차트 이미지 개수입니다.">i</span></th>
                <th>관리</th>
              </tr>
            </thead>
            <tbody>
              {safeItems.map((item) => (
                <tr key={item.id} className="trade-journal-row" onClick={() => void openEdit(item.id)}>
                  <td>{item.buy_date?.slice(0, 10)}</td>
                  <td>{item.sell_date?.slice(0, 10) || "-"}</td>
                  <td>{item.stock_name}</td>
                  <td>{item.sell_date ? "매도완료" : "보유중"}</td>
                  <td>{RESULT_TYPE_OPTIONS.find((x) => x.value === (item.result_type || "holding"))?.label || "보유중"}</td>
                  <td>{item.trade_method_name || "-"}</td>
                  <td>{formatRate(item.profit_rate)}</td>
                  <td>{formatWon(item.realized_profit)}</td>
                  <td>{safeNumber(item.image_count)}</td>
                  <td><button type="button" className="btn btn-secondary btn-table-sm" onClick={(e) => { e.stopPropagation(); void openEdit(item.id); }}>상세</button></td>
                </tr>
              ))}
              {safeItems.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-6 text-center text-sm text-slate-500">조회된 매매일지가 없습니다.</td>
                </tr>
              ) : null}
              <tr className="trade-journal-summary-row">
                <td colSpan={7}>실현손익 합계</td>
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
                    {safeMethods.map((m) => (
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
                  <button type="button" className="btn btn-secondary" onClick={() => void uploadImage()} disabled={!selectedJournalId || !imageFile}>
                    이미지 업로드
                  </button>
                </div>
                <div className="mt-2">
                  <textarea
                    className="textarea-control"
                    rows={6}
                    value={imageMemo}
                    onChange={(e) => setImageMemo(e.target.value)}
                    placeholder="이미지 메모"
                  />
                </div>
                <div className="trade-image-list mt-2">
                  {detailImages.map((img) => (
                    <article key={img.id} className="trade-journal-image-card">
                      <div className="trade-image-card-header">
                        <div className="trade-image-card-title-wrap">
                          <span className="badge badge-blue">{img.image_type}</span>
                          <small className="trade-image-card-title">{img.original_filename || img.image_path}</small>
                        </div>
                        <div className="trade-image-card-actions">
                          <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => startEditImage(img)}>
                            수정
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-table-sm"
                            onClick={() => void deleteImage(img.id)}
                            disabled={deletingImageId === img.id}
                          >
                            {deletingImageId === img.id ? "삭제중" : "삭제"}
                          </button>
                        </div>
                      </div>
                      {img.image_url ? (
                        <button
                          type="button"
                          className="journal-image-thumb"
                          onClick={() =>
                            setPreviewImage({
                              src: getImageUrl(img.image_url),
                              title: img.original_filename || img.image_path || "차트 이미지",
                              caption: img.image_memo || "",
                              badge: getImageTypeLabel(img.image_type),
                            })
                          }
                          aria-label="차트 이미지 크게 보기"
                        >
                          <img src={getImageUrl(img.image_url)} alt={img.original_filename || "trade"} />
                        </button>
                      ) : null}
                      {imageEditingId === img.id ? (
                        <div className="trade-image-memo-edit">
                          <select
                            className="select-control"
                            value={imageEditDraft.image_type}
                            onChange={(e) => setImageEditDraft((prev) => ({ ...prev, image_type: e.target.value }))}
                          >
                            {IMAGE_TYPE_OPTIONS.map((o) => (
                              <option key={o.value} value={o.value}>
                                {o.label}
                              </option>
                            ))}
                          </select>
                          <textarea
                            className="textarea-control"
                            rows={4}
                            value={imageEditDraft.image_memo}
                            onChange={(e) => setImageEditDraft((prev) => ({ ...prev, image_memo: e.target.value }))}
                            placeholder="이미지 메모"
                          />
                          <div className="trade-image-memo-actions">
                            <button type="button" className="btn btn-primary btn-table-sm" onClick={() => void saveImageEdit(img.id)} disabled={savingImageEdit}>
                              {savingImageEdit ? "저장중" : "저장"}
                            </button>
                            <button type="button" className="btn btn-secondary btn-table-sm" onClick={cancelEditImage}>
                              취소
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="trade-image-memo">{img.image_memo || "메모 없음"}</p>
                      )}
                    </article>
                  ))}
                  {detailAppImages.map((img) => (
                    <article key={"app-" + img.id} className="trade-journal-image-card">
                      <div className="trade-image-card-header">
                        <div className="trade-image-card-title-wrap">
                          <span className="badge badge-blue">공통 이미지</span>
                          <small className="trade-image-card-title">{img.original_file_name}</small>
                        </div>
                        <div className="trade-image-card-actions">
                          <button type="button" className="btn btn-danger btn-table-sm" onClick={() => void deleteAppImage(img.id)} disabled={deletingImageId === img.id}>
                            {deletingImageId === img.id ? "삭제중" : "삭제"}
                          </button>
                        </div>
                      </div>
                      {img.file_url ? (
                        <button
                          type="button"
                          className="journal-image-thumb"
                          onClick={() =>
                            setPreviewImage({
                              src: getImageUrl(img.file_url),
                              title: img.original_file_name || "차트 이미지",
                              caption: img.description || "",
                              badge: "공통 이미지",
                            })
                          }
                          aria-label="차트 이미지 크게 보기"
                        >
                          <img src={getImageUrl(img.file_url)} alt={img.original_file_name || "trade"} />
                        </button>
                      ) : null}
                      <p className="trade-image-memo">{img.description || "메모 없음"}</p>
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
                <button className="btn btn-danger" type="button" onClick={() => void deleteJournal()} disabled={deletingJournal}>
                  {deletingJournal ? "삭제중" : "삭제"}
                </button>
              ) : null}
            </div>
          </aside>
          {previewImage ? (
            <div className="journal-image-preview-backdrop" onClick={() => setPreviewImage(null)} role="presentation">
              <div className="journal-image-preview-modal" onClick={(event) => event.stopPropagation()} role="dialog" aria-modal="true" aria-label="차트 이미지 미리보기">
                <button type="button" className="journal-image-preview-close" onClick={() => setPreviewImage(null)} aria-label="닫기">
                  닫기
                </button>
                <img className="journal-image-preview-img" src={previewImage.src} alt={previewImage.title} />
                <div className="journal-image-preview-caption">
                  {previewImage.badge ? <span className="badge badge-blue">{previewImage.badge}</span> : null}
                  <strong>{previewImage.title}</strong>
                  {previewImage.caption ? <p>{previewImage.caption}</p> : null}
                </div>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export default TradeJournalsPage;
