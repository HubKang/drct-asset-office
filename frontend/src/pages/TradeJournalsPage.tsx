import { useEffect, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import { appConfig } from "@/services/config/appConfig";
import type { Stock } from "@/types/stock";
import type { TradeJournal, TradeJournalImage, TradeJournalSaveRequest, TradeMethod } from "@/types/tradeJournal";

type DetailMode = "create" | "edit";

type ImageFormState = {
  imageType: string;
  imageMemo: string;
  file: File | null;
};

const RESULT_TYPE_OPTIONS = [
  { value: "", label: "전체" },
  { value: "holding", label: "보유중" },
  { value: "profit", label: "익절" },
  { value: "loss", label: "손절" },
  { value: "break_even", label: "본전" },
];

const IMAGE_TYPE_OPTIONS = [
  { value: "buy_chart", label: "매수 당시 차트" },
  { value: "sell_chart", label: "매도 당시 차트" },
  { value: "one_week_after_chart", label: "1주 후 차트" },
  { value: "review_chart", label: "복기 차트" },
];

const today = () => new Date().toISOString().slice(0, 10);
const toInputDate = (value?: string | null) => (value ? value.slice(0, 10) : "");
const toNumber = (value?: number | null) => Number(value ?? 0);
const formatRate = (value?: number | null) => `${Number(value ?? 0).toFixed(2)}%`;
const formatWon = (value?: number | null) => `${Number(value ?? 0).toLocaleString("ko-KR")}원`;
const formatResult = (value?: string | null) => RESULT_TYPE_OPTIONS.find((option) => option.value === value)?.label ?? "보유중";
const resolveImageUrl = (url?: string | null) => {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${appConfig.apiBaseUrl}${url.startsWith("/") ? url : `/${url}`}`;
};

const createDefaultForm = (): TradeJournalSaveRequest => ({
  buy_date: today(),
  sell_date: today(),
  stock_code: "",
  stock_name: "",
  stock_theme: "",
  trade_method_id: null,
  result_type: "holding",
  profit_rate: 0,
  realized_profit: 0,
  trade_reason: "",
  success_reason: "",
  failure_reason: "",
  review_memo: "",
  remark: "",
});

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
    stock_theme: "",
    trade_method_id: "",
    result_type: "",
  });

  const [selectedJournalId, setSelectedJournalId] = useState<number | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailMode, setDetailMode] = useState<DetailMode>("create");
  const [detailForm, setDetailForm] = useState<TradeJournalSaveRequest>(createDefaultForm());
  const [detailImages, setDetailImages] = useState<TradeJournalImage[]>([]);

  const [stockModalOpen, setStockModalOpen] = useState(false);
  const [stockKeyword, setStockKeyword] = useState("");
  const [stockCandidates, setStockCandidates] = useState<Stock[]>([]);
  const [stockSearchLoading, setStockSearchLoading] = useState(false);

  const [imageModalOpen, setImageModalOpen] = useState(false);
  const [imageForm, setImageForm] = useState<ImageFormState>({
    imageType: "buy_chart",
    imageMemo: "",
    file: null,
  });

  const setField = <K extends keyof TradeJournalSaveRequest>(key: K, value: TradeJournalSaveRequest[K]) => {
    setDetailForm((prev) => ({ ...prev, [key]: value }));
  };

  const loadTradeMethods = async () => {
    try {
      const rows = await repositories.tradeJournals.listTradeMethods({ is_active: 1 });
      setTradeMethods(rows);
    } catch {
      // ignore
    }
  };

  const loadList = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await repositories.tradeJournals.fetchTradeJournals({
        start_date: filters.start_date,
        end_date: filters.end_date,
        stock_name: filters.stock_name.trim() || undefined,
        stock_theme: filters.stock_theme.trim() || undefined,
        trade_method_id: filters.trade_method_id ? Number(filters.trade_method_id) : undefined,
        result_type: filters.result_type || undefined,
      });
      setItems(response.items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "매매일지 목록 조회에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (journalId: number) => {
    const [detail, images] = await Promise.all([
      repositories.tradeJournals.fetchTradeJournalDetail(journalId),
      repositories.tradeJournals.fetchTradeJournalImages(journalId),
    ]);
    setDetailForm({
      buy_date: toInputDate(detail.buy_date),
      sell_date: toInputDate(detail.sell_date),
      stock_code: detail.stock_code ?? "",
      stock_name: detail.stock_name ?? "",
      stock_theme: detail.stock_theme ?? "",
      trade_method_id: detail.trade_method_id ?? null,
      trade_method_name: detail.trade_method_name ?? "",
      result_type: detail.result_type ?? "holding",
      profit_rate: toNumber(detail.profit_rate),
      realized_profit: toNumber(detail.realized_profit),
      trade_reason: detail.trade_reason ?? "",
      success_reason: detail.success_reason ?? "",
      failure_reason: detail.failure_reason ?? "",
      review_memo: detail.review_memo ?? "",
      remark: detail.remark ?? "",
    });
    setDetailImages(images ?? []);
  };

  useEffect(() => {
    void loadTradeMethods();
    void loadList();
  }, []);

  const openCreatePanel = () => {
    setSelectedJournalId(null);
    setDetailMode("create");
    setDetailForm(createDefaultForm());
    setDetailImages([]);
    setIsDetailOpen(true);
    setMessage("");
    setError("");
  };

  const handleRowClick = async (journalId: number) => {
    if (selectedJournalId === journalId && isDetailOpen) {
      setSelectedJournalId(null);
      setIsDetailOpen(false);
      return;
    }
    setSelectedJournalId(journalId);
    setDetailMode("edit");
    setIsDetailOpen(true);
    setError("");
    try {
      await loadDetail(journalId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "상세 조회에 실패했습니다.");
    }
  };

  const closeDetailPanel = () => {
    setIsDetailOpen(false);
    setSelectedJournalId(null);
  };

  const handleSave = async () => {
    setError("");
    setMessage("");
    if (!detailForm.buy_date || !detailForm.stock_name?.trim()) {
      setError("매수일자와 종목명은 필수입니다.");
      return;
    }
    setSaving(true);
    try {
      const payload: TradeJournalSaveRequest = {
        buy_date: detailForm.buy_date,
        sell_date: detailForm.sell_date || null,
        stock_code: detailForm.stock_code || undefined,
        stock_name: detailForm.stock_name.trim(),
        stock_theme: detailForm.stock_theme?.trim() || undefined,
        trade_method_id: detailForm.trade_method_id ?? null,
        result_type: detailForm.result_type || "holding",
        profit_rate: toNumber(detailForm.profit_rate),
        realized_profit: Math.trunc(toNumber(detailForm.realized_profit)),
        trade_reason: detailForm.trade_reason?.trim() || undefined,
        success_reason: detailForm.success_reason?.trim() || undefined,
        failure_reason: detailForm.failure_reason?.trim() || undefined,
        review_memo: detailForm.review_memo?.trim() || undefined,
        remark: detailForm.remark?.trim() || undefined,
      };

      if (detailMode === "create") {
        const created = await repositories.tradeJournals.createTradeJournal(payload);
        setMessage("매매일지가 등록되었습니다.");
        await loadList();
        if (created?.id) {
          setSelectedJournalId(created.id);
          setDetailMode("edit");
          await loadDetail(created.id);
        }
      } else if (selectedJournalId) {
        await repositories.tradeJournals.updateTradeJournal(selectedJournalId, payload);
        setMessage("매매일지가 수정되었습니다.");
        await loadList();
        await loadDetail(selectedJournalId);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedJournalId || detailMode !== "edit") return;
    if (!window.confirm("이 매매일지를 삭제하시겠습니까?")) return;
    setMessage("");
    setError("");
    try {
      await repositories.tradeJournals.deleteTradeJournal(selectedJournalId);
      closeDetailPanel();
      await loadList();
      setMessage("매매일지가 삭제되었습니다.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "삭제에 실패했습니다.");
    }
  };

  const searchStocks = async () => {
    if (!stockKeyword.trim()) return;
    setStockSearchLoading(true);
    try {
      const rows = await repositories.stocks.list({
        keyword: stockKeyword.trim(),
        is_active: 1,
        limit: 30,
      });
      setStockCandidates(rows ?? []);
    } catch {
      setStockCandidates([]);
    } finally {
      setStockSearchLoading(false);
    }
  };

  const handlePickStock = (stock: Stock) => {
    setField("stock_code", stock.stock_code);
    setField("stock_name", stock.stock_name);
    setField("stock_theme", [stock.sector, stock.industry].filter(Boolean).join(", "));
    setStockModalOpen(false);
  };

  const handleImageUpload = async () => {
    if (!selectedJournalId || detailMode !== "edit") {
      setError("이미지는 저장된 매매일지에서만 추가할 수 있습니다.");
      return;
    }
    if (!imageForm.file) {
      setError("이미지 파일을 선택해 주세요.");
      return;
    }
    try {
      await repositories.tradeJournals.uploadTradeJournalImage(selectedJournalId, {
        image_type: imageForm.imageType,
        image_memo: imageForm.imageMemo.trim() || undefined,
        file: imageForm.file,
      });
      setImageModalOpen(false);
      setImageForm({ imageType: "buy_chart", imageMemo: "", file: null });
      await loadDetail(selectedJournalId);
      await loadList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "이미지 등록에 실패했습니다.");
    }
  };

  const selectedRowForHighlight = (journalId: number) =>
    selectedJournalId === journalId && isDetailOpen && detailMode === "edit";

  return (
    <div className="space-y-4">
      <PageHeader title="매매일지" description="목록에서 선택한 매매일지를 우측 대형 상세 패널에서 관리합니다." />

      <SectionCard title="검색 조건">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-6">
          <input className="input-control" type="date" value={filters.start_date} onChange={(e) => setFilters((prev) => ({ ...prev, start_date: e.target.value }))} />
          <input className="input-control" type="date" value={filters.end_date} onChange={(e) => setFilters((prev) => ({ ...prev, end_date: e.target.value }))} />
          <input className="input-control" placeholder="종목명" value={filters.stock_name} onChange={(e) => setFilters((prev) => ({ ...prev, stock_name: e.target.value }))} />
          <input className="input-control" placeholder="종목테마" value={filters.stock_theme} onChange={(e) => setFilters((prev) => ({ ...prev, stock_theme: e.target.value }))} />
          <select className="select-control" value={filters.trade_method_id} onChange={(e) => setFilters((prev) => ({ ...prev, trade_method_id: e.target.value }))}>
            <option value="">매매기법 전체</option>
            {tradeMethods.map((item) => (
              <option key={item.id} value={String(item.id)}>
                {item.method_name}
              </option>
            ))}
          </select>
          <select className="select-control" value={filters.result_type} onChange={(e) => setFilters((prev) => ({ ...prev, result_type: e.target.value }))}>
            {RESULT_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="mt-2">
          <button type="button" className="btn btn-primary" onClick={() => void loadList()} disabled={loading}>
            {loading ? "조회 중..." : "조회"}
          </button>
        </div>
      </SectionCard>

      {message ? <p className="inline-result inline-success">{message}</p> : null}
      {error ? <p className="inline-result inline-error">{error}</p> : null}

      <SectionCard title="매매일지 목록">
        <div className="mb-3 flex justify-end">
          <button type="button" className="btn btn-primary" onClick={openCreatePanel}>
            추가
          </button>
        </div>
        <div className="trade-journal-table-shell">
          <table className="data-table trade-journal-table">
            <colgroup>
              <col style={{ width: "11%" }} />
              <col style={{ width: "11%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "14%" }} />
              <col style={{ width: "9%" }} />
              <col style={{ width: "8%" }} />
              <col style={{ width: "12%" }} />
              <col style={{ width: "9%" }} />
            </colgroup>
            <thead>
              <tr>
                <th>매수일자</th>
                <th>매도일자</th>
                <th>종목테마</th>
                <th>매매기법명</th>
                <th>종목명</th>
                <th>익절/손절</th>
                <th>수익률</th>
                <th>실현손익</th>
                <th>이미지수</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className={`trade-journal-row ${selectedRowForHighlight(item.id) ? "selected" : ""}`} onClick={() => void handleRowClick(item.id)}>
                  <td>{toInputDate(item.buy_date)}</td>
                  <td>{toInputDate(item.sell_date) || "-"}</td>
                  <td title={item.stock_theme || "-"}>{item.stock_theme || "-"}</td>
                  <td title={item.trade_method_name || "-"}>{item.trade_method_name || "-"}</td>
                  <td title={item.stock_name || "-"}>{item.stock_name || "-"}</td>
                  <td>{formatResult(item.result_type)}</td>
                  <td>{formatRate(item.profit_rate)}</td>
                  <td>{formatWon(item.realized_profit)}</td>
                  <td>{item.image_count ?? 0}개</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {isDetailOpen ? (
        <>
          <div className="trade-journal-detail-dim" onClick={closeDetailPanel} />
          <aside className="trade-journal-detail-drawer">
            <div className="trade-journal-detail-drawer-header">
              <h3>매매일지 상세</h3>
              <button type="button" className="btn btn-secondary" onClick={closeDetailPanel}>
                닫기
              </button>
            </div>

            <div className="trade-journal-detail-drawer-body">
              <div className="trade-journal-detail-grid">
                <input className="input-control" type="date" value={detailForm.buy_date} onChange={(e) => setField("buy_date", e.target.value)} />
                <input className="input-control" type="date" value={detailForm.sell_date || ""} onChange={(e) => setField("sell_date", e.target.value)} />
                <div className="trade-journal-stock-select">
                  <input className="input-control" placeholder="종목명(필수)" value={detailForm.stock_name} onChange={(e) => setField("stock_name", e.target.value)} />
                  <button type="button" className="btn btn-secondary" onClick={() => setStockModalOpen(true)}>
                    검색
                  </button>
                </div>
                <input className="input-control" placeholder="종목테마" value={detailForm.stock_theme || ""} onChange={(e) => setField("stock_theme", e.target.value)} />
                <select
                  className="select-control"
                  value={detailForm.trade_method_id ? String(detailForm.trade_method_id) : ""}
                  onChange={(e) => setField("trade_method_id", e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">매매기법 선택</option>
                  {tradeMethods.map((method) => (
                    <option key={method.id} value={String(method.id)}>
                      {method.method_name}
                    </option>
                  ))}
                </select>
                <select className="select-control" value={detailForm.result_type || "holding"} onChange={(e) => setField("result_type", e.target.value)}>
                  {RESULT_TYPE_OPTIONS.filter((option) => option.value).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <input
                  className="input-control"
                  type="number"
                  step="0.01"
                  placeholder="수익률"
                  value={detailForm.profit_rate ?? 0}
                  onChange={(e) => setField("profit_rate", Number(e.target.value))}
                />
                <input
                  className="input-control"
                  type="number"
                  step="1"
                  placeholder="실현손익"
                  value={detailForm.realized_profit ?? 0}
                  onChange={(e) => setField("realized_profit", Number(e.target.value))}
                />
              </div>

              <div className="detail-section">
                <label className="detail-label">매매기록</label>
                <textarea
                  className="textarea-control"
                  placeholder="예: 09:10 전일 계획 종목 관찰 -> 09:15 돌파 후 매수 -> 10:20 일부 익절 -> 종가 전 정리"
                  value={detailForm.remark || ""}
                  onChange={(e) => setField("remark", e.target.value)}
                />
              </div>

              <div className="trade-journal-detail-grid detail-section">
                <textarea className="textarea-control" placeholder="매매 이유" value={detailForm.trade_reason || ""} onChange={(e) => setField("trade_reason", e.target.value)} />
                <textarea className="textarea-control" placeholder="성공 사유" value={detailForm.success_reason || ""} onChange={(e) => setField("success_reason", e.target.value)} />
                <textarea className="textarea-control" placeholder="실패 사유" value={detailForm.failure_reason || ""} onChange={(e) => setField("failure_reason", e.target.value)} />
                <textarea className="textarea-control" placeholder="복기 메모" value={detailForm.review_memo || ""} onChange={(e) => setField("review_memo", e.target.value)} />
              </div>

              <div className="detail-section">
                <div className="mb-2 flex items-center justify-between">
                  <strong>차트 이미지</strong>
                  <button type="button" className="btn btn-secondary" onClick={() => setImageModalOpen(true)}>
                    이미지 추가
                  </button>
                </div>
                {detailImages.length === 0 ? <p className="text-muted">등록된 이미지가 없습니다.</p> : null}
                <div className="trade-journal-image-grid">
                  {detailImages.map((image) => (
                    <article key={image.id} className="trade-journal-image-card">
                      {image.image_url ? (
                        <img
                          src={resolveImageUrl(image.image_url)}
                          alt={image.original_filename || "trade image"}
                          className="trade-journal-image-preview"
                        />
                      ) : null}
                      <div className="trade-journal-image-meta">
                        <strong>{IMAGE_TYPE_OPTIONS.find((option) => option.value === image.image_type)?.label ?? image.image_type}</strong>
                        {image.image_memo ? <p>{image.image_memo}</p> : null}
                        <small>{image.original_filename || image.image_path}</small>
                      </div>
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={async () => {
                          await repositories.tradeJournals.deleteTradeJournalImage(image.id);
                          if (selectedJournalId) {
                            await loadDetail(selectedJournalId);
                            await loadList();
                          }
                        }}
                      >
                        삭제
                      </button>
                    </article>
                  ))}
                </div>
              </div>
            </div>

            <div className="trade-journal-detail-drawer-footer">
              {detailMode === "edit" ? (
                <button type="button" className="btn btn-danger" onClick={() => void handleDelete()}>
                  삭제
                </button>
              ) : null}
              <button type="button" className="btn btn-primary" onClick={() => void handleSave()} disabled={saving}>
                {saving ? "저장 중..." : "저장"}
              </button>
            </div>
          </aside>
        </>
      ) : null}

      {stockModalOpen ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h3 className="section-title">종목 검색</h3>
            <div className="flex gap-2">
              <input className="input-control" placeholder="종목명/코드 검색어" value={stockKeyword} onChange={(e) => setStockKeyword(e.target.value)} />
              <button type="button" className="btn btn-primary" onClick={() => void searchStocks()} disabled={stockSearchLoading}>
                {stockSearchLoading ? "검색 중..." : "검색"}
              </button>
            </div>
            <div className="trade-journal-stock-results">
              {stockCandidates.map((stock) => (
                <button key={stock.id} type="button" className="trade-journal-stock-item" onClick={() => handlePickStock(stock)}>
                  <strong>{stock.stock_name}</strong>
                  <span>{stock.stock_code}</span>
                </button>
              ))}
            </div>
            <div className="mt-3 flex justify-end">
              <button type="button" className="btn btn-secondary" onClick={() => setStockModalOpen(false)}>
                닫기
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {imageModalOpen ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h3 className="section-title">이미지 추가</h3>
            <div className="grid grid-cols-1 gap-2">
              <select className="select-control" value={imageForm.imageType} onChange={(e) => setImageForm((prev) => ({ ...prev, imageType: e.target.value }))}>
                {IMAGE_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <input
                className="input-control"
                type="file"
                accept="image/*"
                onChange={(e) => {
                  const selected = e.target.files?.[0] || null;
                  setImageForm((prev) => ({ ...prev, file: selected }));
                }}
              />
              <textarea
                className="textarea-control"
                placeholder="이미지 메모"
                value={imageForm.imageMemo}
                onChange={(e) => setImageForm((prev) => ({ ...prev, imageMemo: e.target.value }))}
              />
            </div>
            <div className="mt-3 flex justify-end gap-2">
              <button type="button" className="btn btn-secondary" onClick={() => setImageModalOpen(false)}>
                닫기
              </button>
              <button type="button" className="btn btn-primary" onClick={() => void handleImageUpload()}>
                저장
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default TradeJournalsPage;
