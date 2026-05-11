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

const SECURITY_TYPES = ["common_stock", "preferred_stock", "etf", "etn", "spac", "reit", "other"] as const;
const SECURITY_LABELS: Record<string, string> = {
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

  const [dryRun, setDryRun] = useState(true);
  const [deactivateMissing, setDeactivateMissing] = useState(false);
  const [includeSecurityTypes, setIncludeSecurityTypes] = useState<string[]>(["common_stock"]);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncResult, setSyncResult] = useState<StockSyncResponse | null>(null);
  const [syncError, setSyncError] = useState("");

  const buildListParams = (nextOffset = offset) => {
    const params: {
      keyword?: string;
      market?: string;
      is_active?: number;
      security_type?: string;
      limit: number;
      offset: number;
    } = {
      limit,
      offset: nextOffset,
    };
    if (keyword.trim()) params.keyword = keyword.trim();
    if (marketFilter === "KOSPI" || marketFilter === "KOSDAQ") params.market = marketFilter;
    if (marketFilter === "INACTIVE") params.is_active = 0;
    if (securityFilter !== "ALL") params.security_type = securityFilter;
    return params;
  };

  const load = async (nextOffset = offset) => {
    const data = await repositories.stocks.list(buildListParams(nextOffset));
    setItems(data);
  };

  useEffect(() => {
    load();
  }, [offset]);

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
  };

  const toggleSecurityType = (type: string) => {
    setIncludeSecurityTypes((prev) => (prev.includes(type) ? prev.filter((x) => x !== type) : [...prev, type]));
  };

  const onSync = async (markets: string[]) => {
    if (includeSecurityTypes.length === 0) {
      setSyncError("동기화 대상 종목 유형을 1개 이상 선택해 주세요.");
      return;
    }
    setSyncLoading(true);
    setSyncError("");
    setSyncResult(null);
    try {
      const result = await repositories.stocks.syncStocks({
        markets,
        dry_run: dryRun,
        deactivate_missing: deactivateMissing,
        include_security_types: includeSecurityTypes,
      });
      setSyncResult(result);
      await load();
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : "종목 갱신 중 오류가 발생했습니다.");
    } finally {
      setSyncLoading(false);
    }
  };

  const canPrev = offset > 0;
  const canNext = items.length >= limit;
  const renderSecurityType = (value: string | null) => SECURITY_LABELS[value || "other"] || "기타";

  return (
    <div className="space-y-4">
      <PageHeader
        title="종목 관리"
        description="KRX 공식 상장종목정보를 기준으로 종목 마스터를 관리합니다."
        action={<StatusBadge label={`활성 ${activeCount} / 이번 페이지 ${items.length}`} tone="blue" />}
      />

      <SectionCard title="KRX 종목 마스터 갱신">
        <p className="text-sm text-slate-600">
          KRX 공식 API는 ETF, ETN, 스팩, 리츠 등 상장상품을 함께 반환할 수 있습니다. DrCT에셋의 기본 동기화 대상은 보통주입니다.
        </p>

        <div className="mt-3 space-y-3">
          <div className="stock-sync-actions">
            <button className="btn btn-secondary" onClick={() => onSync(["KOSPI"])} disabled={syncLoading}>
              코스피 종목 갱신
            </button>
            <button className="btn btn-secondary" onClick={() => onSync(["KOSDAQ"])} disabled={syncLoading}>
              코스닥 종목 갱신
            </button>
            <button className="btn btn-secondary" onClick={() => onSync(["KOSPI", "KOSDAQ"])} disabled={syncLoading}>
              전체 종목 갱신
            </button>
            {syncLoading ? (
              <span className="inline-flex items-center gap-1 text-sm text-slate-600">
                <Loader2 size={14} className="animate-spin" />
                처리 중...
              </span>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
              미리보기만 실행
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={deactivateMissing} onChange={(e) => setDeactivateMissing(e.target.checked)} />
              KRX 목록에 없는 기존 종목 비활성화
            </label>
          </div>

          <div className="text-xs text-slate-500">
            <div>미리보기만 실행: DB에 저장하지 않고 변경 예상 결과만 확인합니다.</div>
            <div>KRX 목록에 없는 기존 종목 비활성화: 현재 DB에는 있지만 KRX 최신 목록에는 없는 종목을 비활성 상태로 변경합니다.</div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="mb-2 text-sm font-semibold text-slate-700">동기화 대상</div>
            <div className="flex flex-wrap gap-3">
              {SECURITY_TYPES.map((type) => (
                <label key={type} className="inline-flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" checked={includeSecurityTypes.includes(type)} onChange={() => toggleSecurityType(type)} />
                  {SECURITY_LABELS[type]}
                </label>
              ))}
            </div>
          </div>

          {syncLoading ? (
            <div className="inline-result">
              KRX 공식 종목 정보를 조회하고 있습니다. 전체 상장증권을 수집한 뒤 선택한 시장과 종목 유형만 필터링합니다. 보통 10~60초 정도 소요될 수 있습니다.
            </div>
          ) : null}

          {syncError ? <div className="inline-result inline-error">{syncError}</div> : null}
          {syncResult ? (
            <div className="inline-result">
              {syncResult.message}
              <br />
              raw_fetched={syncResult.raw_fetched_count}, eligible={syncResult.eligible_count}, fetched={syncResult.fetched_count}, inserted=
              {syncResult.inserted_count}, updated={syncResult.updated_count}, reactivated={syncResult.reactivated_count}, deactivated=
              {syncResult.deactivated_count}, skipped={syncResult.skipped_count}, errors={syncResult.error_count}
            </div>
          ) : null}
        </div>
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
            <option value="common_stock">보통주</option>
            <option value="preferred_stock">우선주</option>
            <option value="etf">ETF</option>
            <option value="etn">ETN</option>
            <option value="spac">스팩</option>
            <option value="reit">리츠</option>
            <option value="other">기타</option>
          </select>
          <div>
            <input
              className="input-control"
              placeholder="종목코드 또는 종목명"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary stock-search-btn">
            검색
          </button>
          <button type="button" className="btn btn-secondary stock-search-btn" onClick={onResetSearch}>
            초기화
          </button>
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
              {SECURITY_TYPES.map((type) => (
                <option key={type} value={type}>
                  {SECURITY_LABELS[type]}
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <button className="btn btn-primary" onClick={onUpdate}>
                저장
              </button>
              <button className="btn btn-secondary" onClick={() => setEditId(null)}>
                취소
              </button>
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
                  <tr>
                    <th>ID</th>
                    <th>종목코드</th>
                    <th>종목명</th>
                    <th>시장</th>
                    <th>종목유형</th>
                    <th>섹터</th>
                    <th>업종</th>
                    <th>ISIN</th>
                    <th>활성</th>
                    <th>마지막 동기화</th>
                    <th>작업</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((s) => (
                    <tr key={s.id}>
                      <td>{s.id}</td>
                      <td className="cell-nowrap font-medium text-slate-800">{s.stock_code}</td>
                      <td className="cell-nowrap max-w-[220px] truncate" title={s.stock_name}>
                        {s.stock_name}
                      </td>
                      <td className="cell-nowrap">{s.market || "-"}</td>
                      <td className="cell-nowrap">{renderSecurityType(s.security_type)}</td>
                      <td className="cell-nowrap">{s.sector || "-"}</td>
                      <td className="cell-nowrap">{s.industry || "-"}</td>
                      <td className="cell-nowrap">{s.isin_code || "-"}</td>
                      <td>{s.is_active === 1 ? <StatusBadge label="활성" tone="emerald" /> : <StatusBadge label="비활성" tone="slate" />}</td>
                      <td className="cell-nowrap">{s.last_synced_at || "-"}</td>
                      <td>
                        <div className="flex gap-2">
                          <button className="btn btn-secondary inline-flex items-center gap-1" onClick={() => startEdit(s)}>
                            <PenLine size={13} />
                            수정
                          </button>
                          <button className="btn btn-danger inline-flex items-center gap-1" onClick={() => onDeactivate(s.id)}>
                            <Trash2 size={13} />
                            비활성화
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination-bar">
              <div className="pagination-info">
                현재 위치: {offset + 1} ~ {offset + items.length} / 조회 건수: {items.length}건
              </div>
              <div className="pagination-actions">
                <button className="btn btn-secondary" onClick={() => setOffset((prev) => Math.max(0, prev - limit))} disabled={!canPrev}>
                  이전
                </button>
                <button className="btn btn-secondary" onClick={() => setOffset((prev) => prev + limit)} disabled={!canNext}>
                  다음
                </button>
              </div>
            </div>
          </>
        )}
      </SectionCard>
    </div>
  );
}

export default StocksPage;
