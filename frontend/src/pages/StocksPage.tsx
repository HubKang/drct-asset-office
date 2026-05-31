import { useEffect, useMemo, useState } from "react";
import { Loader2, PenLine, Trash2 } from "lucide-react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { Stock, StockUpdateInput } from "@/types/stock";
import type { StockSyncResponse } from "@/types/stockSync";

type MarketFilter = "ALL" | "KOSPI" | "KOSDAQ" | "INACTIVE";
type SecurityFilter = "ALL" | "common_stock" | "preferred_stock" | "etf" | "etn" | "spac" | "reit" | "other";
type SyncMarket = "ALL" | "KOSPI" | "KOSDAQ";
type SecurityType = "common_stock" | "preferred_stock" | "etf" | "etn" | "spac" | "reit" | "other";

const SECURITY_TYPES: SecurityType[] = ["common_stock", "preferred_stock", "etf", "etn", "spac", "reit", "other"];
const SECURITY_LABELS: Record<SecurityType, string> = {
  common_stock: "보통주",
  preferred_stock: "우선주",
  etf: "ETF",
  etn: "ETN",
  spac: "스팩",
  reit: "리츠",
  other: "기타",
};

function StocksPage() {
  const [items, setItems] = useState<Stock[]>([]);
  const [keyword, setKeyword] = useState("");
  const [marketFilter, setMarketFilter] = useState<MarketFilter>("ALL");
  const [securityFilter, setSecurityFilter] = useState<SecurityFilter>("ALL");
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const [editId, setEditId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<StockUpdateInput>({});

  const [syncMarket, setSyncMarket] = useState<SyncMarket>("ALL");
  const [includeSecurityTypes, setIncludeSecurityTypes] = useState<SecurityType[]>(["common_stock"]);
  const [typeCounts, setTypeCounts] = useState<Record<SecurityType, number>>({
    common_stock: 0,
    preferred_stock: 0,
    etf: 0,
    etn: 0,
    spac: 0,
    reit: 0,
    other: 0,
  });
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncResult, setSyncResult] = useState<StockSyncResponse | null>(null);
  const [syncError, setSyncError] = useState("");
  const [showRawLog, setShowRawLog] = useState(false);

  const buildListParams = (nextOffset = offset) => {
    const params: {
      keyword?: string;
      market?: string;
      is_active?: number;
      security_type?: string;
      limit: number;
      offset: number;
    } = { limit, offset: nextOffset };
    if (keyword.trim()) params.keyword = keyword.trim();
    if (marketFilter === "KOSPI" || marketFilter === "KOSDAQ") params.market = marketFilter;
    params.is_active = marketFilter === "INACTIVE" ? 0 : 1;
    if (securityFilter !== "ALL") params.security_type = securityFilter;
    return params;
  };

  const load = async (nextOffset = offset) => {
    const data = await repositories.stocks.list(buildListParams(nextOffset));
    setItems(data);
  };

  const loadTypeCounts = async () => {
    const next: Record<SecurityType, number> = { common_stock: 0, preferred_stock: 0, etf: 0, etn: 0, spac: 0, reit: 0, other: 0 };
    await Promise.all(
      SECURITY_TYPES.map(async (type) => {
        let count = 0;
        for (let pageOffset = 0; pageOffset < 50000; pageOffset += 500) {
          const rows = await repositories.stocks.list({ is_active: 1, security_type: type, limit: 500, offset: pageOffset });
          count += rows.length;
          if (rows.length < 500) break;
        }
        next[type] = count;
      }),
    );
    setTypeCounts(next);
  };

  useEffect(() => {
    void load();
  }, [offset]);

  useEffect(() => {
    void loadTypeCounts();
  }, []);

  const activeCount = useMemo(() => items.filter((i) => i.is_active === 1).length, [items]);

  const onSearch = async () => {
    setOffset(0);
    await load(0);
  };

  const onResetSearch = async () => {
    setKeyword("");
    setMarketFilter("ALL");
    setSecurityFilter("ALL");
    setOffset(0);
    await load(0);
  };

  const startEdit = (item: Stock) => {
    setEditId(item.id);
    setEditForm({
      stock_name: item.stock_name,
      market: item.market || "",
      sector: item.sector || "",
      industry: item.industry || "",
      security_type: item.security_type || "common_stock",
    });
  };

  const onUpdate = async () => {
    if (!editId) return;
    await repositories.stocks.update(editId, editForm);
    setEditId(null);
    setEditForm({});
    await load();
  };

  const onDeactivate = async (stockId: number) => {
    await repositories.stocks.deactivate(stockId);
    await load();
    await loadTypeCounts();
  };

  const toggleSecurityType = (type: SecurityType) => {
    setIncludeSecurityTypes((prev) => (prev.includes(type) ? prev.filter((x) => x !== type) : [...prev, type]));
  };

  const runSync = async (preview: boolean) => {
    if (includeSecurityTypes.length === 0) {
      setSyncError("종목 유형을 1개 이상 선택해주세요.");
      return;
    }
    if (!preview) {
      const ok = window.confirm(
        "최신 KRX 목록으로 종목 마스터를 재구축하시겠습니까?\n\n현재 종목 마스터 목록은 재구성되며, 선택한 종목유형만 최신 목록으로 다시 반영됩니다.\n기존 수집 데이터는 삭제되지 않습니다.",
      );
      if (!ok) return;
    }

    setSyncLoading(true);
    setSyncError("");
    setSyncResult(null);
    setShowRawLog(false);
    try {
      const markets = syncMarket === "ALL" ? ["KOSPI", "KOSDAQ"] : [syncMarket];
      const result = await repositories.stocks.syncStocks({
        markets,
        dry_run: preview,
        deactivate_missing: false,
        include_security_types: includeSecurityTypes,
        mode: "rebuild",
      });
      setSyncResult(result);
      await load();
      await loadTypeCounts();
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : "종목 갱신 중 오류가 발생했습니다.");
    } finally {
      setSyncLoading(false);
    }
  };

  const canPrev = offset > 0;
  const canNext = items.length >= limit;
  const renderSecurityType = (value: string | null) => SECURITY_LABELS[(value as SecurityType) || "other"] || "기타";

  return (
    <div className="space-y-4">
      <PageHeader
        title="종목 관리"
        description="KRX 최신 목록을 기준으로 DrCT에셋 종목 마스터를 재구축합니다."
        action={<StatusBadge label={`활성 ${activeCount} / 이번 페이지 ${items.length}`} tone="blue" />}
      />

      <SectionCard title="최신 KRX 목록 재구축">
        <div className="watchlist-card-title-wrap">
          <span className="watchlist-card-title">동기화 옵션</span>
          <span className="hint-icon" title="선택한 종목유형 기준으로 기존 종목 마스터를 비활성화한 뒤 최신 KRX 목록으로 다시 반영합니다.">
            i
          </span>
        </div>

        <div className="stock-sync-market-row">
          <select className="select-control" value={syncMarket} onChange={(e) => setSyncMarket(e.target.value as SyncMarket)}>
            <option value="ALL">전체 시장</option>
            <option value="KOSPI">KOSPI</option>
            <option value="KOSDAQ">KOSDAQ</option>
          </select>
          <div className="stock-sync-market-actions">
            <button className="btn btn-secondary" onClick={() => void runSync(true)} disabled={syncLoading}>
              미리보기
            </button>
            <button className="btn btn-primary" onClick={() => void runSync(false)} disabled={syncLoading}>
              선택 타입 최신 목록으로 갱신
            </button>
            {syncLoading ? (
              <span className="inline-flex items-center gap-1 text-sm text-slate-600">
                <Loader2 size={14} className="animate-spin" />
                처리 중...
              </span>
            ) : null}
          </div>
        </div>

        <div className="stock-type-card-grid">
          {SECURITY_TYPES.map((type) => {
            const selected = includeSecurityTypes.includes(type);
            return (
              <button key={type} type="button" className={`stock-type-card ${selected ? "selected" : ""}`} onClick={() => toggleSecurityType(type)}>
                <strong>{SECURITY_LABELS[type]}</strong>
                <span>현재 DB {typeCounts[type].toLocaleString()}건</span>
                <em>{selected ? "선택" : "미선택"}</em>
              </button>
            );
          })}
        </div>

        {syncError ? <div className="inline-result inline-error">{syncError}</div> : null}
        {syncResult ? (
          <>
            <div className="stock-sync-summary-grid">
              <div className="stock-sync-summary-card"><span>원본 수집</span><strong>{syncResult.raw_fetched_count.toLocaleString()}</strong></div>
              <div className="stock-sync-summary-card"><span>대상 추출</span><strong>{syncResult.eligible_count.toLocaleString()}</strong></div>
              <div className="stock-sync-summary-card"><span>기존 비활성화</span><strong>{syncResult.deleted_existing_count.toLocaleString()}</strong></div>
              <div className="stock-sync-summary-card"><span>신규 등록</span><strong>{syncResult.inserted_count.toLocaleString()}</strong></div>
              <div className="stock-sync-summary-card"><span>재활성/갱신</span><strong>{(syncResult.reactivated_count + syncResult.updated_count).toLocaleString()}</strong></div>
              <div className="stock-sync-summary-card"><span>오류</span><strong>{syncResult.error_count.toLocaleString()}</strong></div>
            </div>
            {syncResult.dry_run ? <div className="inline-result">미리보기 결과입니다. DB에는 반영되지 않았습니다.</div> : null}
            <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setShowRawLog((v) => !v)}>
              {showRawLog ? "상세 로그 숨기기" : "상세 로그 보기"}
            </button>
            {showRawLog ? <div className="inline-result">{syncResult.message}</div> : null}
          </>
        ) : null}
      </SectionCard>

      <SectionCard title="검색">
        <form
          className="stock-search-row"
          onSubmit={(e) => {
            e.preventDefault();
            void onSearch();
          }}
        >
          <select className="select-control" value={marketFilter} onChange={(e) => setMarketFilter(e.target.value as MarketFilter)}>
            <option value="ALL">전체</option>
            <option value="KOSPI">KOSPI</option>
            <option value="KOSDAQ">KOSDAQ</option>
            <option value="INACTIVE">비활성</option>
          </select>
          <select className="select-control" value={securityFilter} onChange={(e) => setSecurityFilter(e.target.value as SecurityFilter)}>
            <option value="ALL">종목유형</option>
            {SECURITY_TYPES.map((t) => (
              <option key={t} value={t}>
                {SECURITY_LABELS[t]}
              </option>
            ))}
          </select>
          <div><input className="input-control" placeholder="종목코드 또는 종목명" value={keyword} onChange={(e) => setKeyword(e.target.value)} /></div>
          <button type="submit" className="btn btn-primary stock-search-btn">검색</button>
          <button type="button" className="btn btn-secondary stock-search-btn" onClick={onResetSearch}>초기화</button>
        </form>
      </SectionCard>

      {editId ? (
        <SectionCard title="종목 수정">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-6">
            <input className="input-control" placeholder="종목명" value={editForm.stock_name || ""} onChange={(e) => setEditForm({ ...editForm, stock_name: e.target.value })} />
            <input className="input-control" placeholder="시장" value={editForm.market || ""} onChange={(e) => setEditForm({ ...editForm, market: e.target.value })} />
            <input className="input-control" placeholder="섹터" value={editForm.sector || ""} onChange={(e) => setEditForm({ ...editForm, sector: e.target.value })} />
            <input className="input-control" placeholder="업종" value={editForm.industry || ""} onChange={(e) => setEditForm({ ...editForm, industry: e.target.value })} />
            <select className="select-control" value={editForm.security_type || "common_stock"} onChange={(e) => setEditForm({ ...editForm, security_type: e.target.value })}>
              {SECURITY_TYPES.map((type) => <option key={type} value={type}>{SECURITY_LABELS[type]}</option>)}
            </select>
            <div className="flex gap-2">
              <button className="btn btn-primary" onClick={onUpdate}>저장</button>
              <button className="btn btn-secondary" onClick={() => setEditId(null)}>취소</button>
            </div>
          </div>
        </SectionCard>
      ) : null}

      <SectionCard title="종목 목록">
        {items.length === 0 ? (
          <EmptyState message="조회된 종목이 없습니다." />
        ) : (
          <>
            <div className="table-shell">
              <table className="data-table compact-table min-w-[1320px]">
                <thead>
                  <tr><th>ID</th><th>종목코드</th><th>종목명</th><th>시장</th><th>종목유형</th><th>섹터</th><th>업종</th><th>ISIN</th><th>활성</th><th>마지막 동기화</th><th>작업</th></tr>
                </thead>
                <tbody>
                  {items.map((s) => (
                    <tr key={s.id}>
                      <td>{s.id}</td><td className="cell-nowrap font-medium text-slate-800">{s.stock_code}</td>
                      <td className="cell-nowrap max-w-[220px] truncate" title={s.stock_name}>{s.stock_name}</td>
                      <td className="cell-nowrap">{s.market || "-"}</td><td className="cell-nowrap">{renderSecurityType(s.security_type)}</td>
                      <td className="cell-nowrap">{s.sector || "-"}</td><td className="cell-nowrap">{s.industry || "-"}</td>
                      <td className="cell-nowrap">{s.isin_code || "-"}</td>
                      <td>{s.is_active === 1 ? <StatusBadge label="활성" tone="emerald" /> : <StatusBadge label="비활성" tone="slate" />}</td>
                      <td className="cell-nowrap">{s.last_synced_at || "-"}</td>
                      <td>
                        <div className="flex gap-2">
                          <button className="btn btn-secondary inline-flex items-center gap-1" onClick={() => startEdit(s)}><PenLine size={13} />수정</button>
                          <button className="btn btn-danger inline-flex items-center gap-1" onClick={() => onDeactivate(s.id)}><Trash2 size={13} />비활성화</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination-bar">
              <div className="pagination-info">현재 위치: {offset + 1} ~ {offset + items.length} / 조회 건수: {items.length}건</div>
              <div className="pagination-actions">
                <button className="btn btn-secondary" onClick={() => setOffset((prev) => Math.max(0, prev - limit))} disabled={!canPrev}>이전</button>
                <button className="btn btn-secondary" onClick={() => setOffset((prev) => prev + limit)} disabled={!canNext}>다음</button>
              </div>
            </div>
          </>
        )}
      </SectionCard>
    </div>
  );
}

export default StocksPage;
