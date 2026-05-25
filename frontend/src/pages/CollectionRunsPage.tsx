import { FormEvent, useEffect, useMemo, useState } from "react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { CollectionRun } from "@/types/collectionRun";
import { truncateText } from "@/utils/format";

const statusLabel: Record<string, string> = {
  running: "진행중",
  success: "성공",
  failed: "실패",
  partial: "부분성공",
};

const statusTone: Record<string, "slate" | "emerald" | "rose" | "amber" | "blue"> = {
  running: "blue",
  success: "emerald",
  failed: "rose",
  partial: "amber",
};

const statusOptions = [
  { value: "running", label: "진행중" },
  { value: "success", label: "성공" },
  { value: "failed", label: "실패" },
  { value: "partial", label: "부분성공" },
];

const initialFilters = {
  collectorName: "",
  status: "",
  target: "",
  limit: "20",
};

function CollectionRunsPage() {
  const [items, setItems] = useState<CollectionRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<CollectionRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [resultMessage, setResultMessage] = useState("");
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const [totalCount, setTotalCount] = useState(0);

  const [collectorName, setCollectorName] = useState(initialFilters.collectorName);
  const [status, setStatus] = useState(initialFilters.status);
  const [target, setTarget] = useState(initialFilters.target);
  const [limit, setLimit] = useState(initialFilters.limit);
  const [page, setPage] = useState(1);

  const pageSize = Number(limit) || 20;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  const load = async (params?: {
    collectorName?: string;
    status?: string;
    target?: string;
    limit?: string;
    page?: number;
  }) => {
    const activeCollector = params?.collectorName ?? collectorName;
    const activeStatus = params?.status ?? status;
    const activeTarget = params?.target ?? target;
    const activeLimit = params?.limit ?? limit;
    const activePage = params?.page ?? page;
    const activePageSize = Number(activeLimit) || 20;
    const activeOffset = Math.max(0, (activePage - 1) * activePageSize);

    setLoading(true);
    setError("");
    setResultMessage("");
    try {
      const data = await repositories.collectionRuns.listCollectionRuns({
        collector_name: activeCollector || undefined,
        status: activeStatus || undefined,
        target: activeTarget || undefined,
        limit: activePageSize,
        offset: activeOffset,
      });
      setItems(data.items);
      setTotalCount(data.total_count);
      if (selectedRun) {
        const updated = data.items.find((item) => item.id === selectedRun.id) ?? null;
        setSelectedRun(updated);
      }
    } catch {
      setError("수집 이력을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load({ page: 1, limit: initialFilters.limit });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const summary = useMemo(() => {
    const result = { total: totalCount, success: 0, failed: 0, partial: 0, running: 0 };
    for (const item of items) {
      if (item.status === "success") result.success += 1;
      else if (item.status === "failed") result.failed += 1;
      else if (item.status === "partial") result.partial += 1;
      else if (item.status === "running") result.running += 1;
    }
    return result;
  }, [items, totalCount]);

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    const nextPage = 1;
    setPage(nextPage);
    await load({ page: nextPage });
  };

  const onReset = async () => {
    const nextPage = 1;
    setCollectorName(initialFilters.collectorName);
    setStatus(initialFilters.status);
    setTarget(initialFilters.target);
    setLimit(initialFilters.limit);
    setPage(nextPage);
    setSelectedRun(null);
    await load({
      collectorName: initialFilters.collectorName,
      status: initialFilters.status,
      target: initialFilters.target,
      limit: initialFilters.limit,
      page: nextPage,
    });
  };

  const onCleanupOlderThanOneMonth = async () => {
    if (cleanupLoading) return;
    setCleanupLoading(true);
    setError("");
    setResultMessage("");
    try {
      const preview = await repositories.collectionRuns.previewCleanupOlderThanOneMonth();
      if (preview.target_count <= 0) {
        setResultMessage("삭제할 1달 전 수집 이력이 없습니다.");
        return;
      }
      const ok = window.confirm(
        `1달 전 수집 이력 ${preview.target_count}건을 삭제합니다.\n실제 수집된 뉴스/공시/가격 데이터는 삭제되지 않습니다.\n계속하시겠습니까?`,
      );
      if (!ok) return;
      const result = await repositories.collectionRuns.cleanupOlderThanOneMonth();
      setResultMessage(result.message);
      setPage(1);
      setSelectedRun(null);
      await load({ page: 1 });
    } catch {
      setError("1달 전 수집 이력 삭제 처리 중 오류가 발생했습니다.");
    } finally {
      setCleanupLoading(false);
    }
  };

  const onChangePageSize = async (nextLimit: string) => {
    const nextPage = 1;
    setLimit(nextLimit);
    setPage(nextPage);
    await load({ limit: nextLimit, page: nextPage });
  };

  const onPrevPage = async () => {
    if (page <= 1 || loading) return;
    const nextPage = page - 1;
    setPage(nextPage);
    await load({ page: nextPage });
  };

  const onNextPage = async () => {
    if (page >= totalPages || loading) return;
    const nextPage = page + 1;
    setPage(nextPage);
    await load({ page: nextPage });
  };

  return (
    <div className="space-y-4">
      <div className="collection-top-grid grid grid-cols-1 gap-4 xl:grid-cols-[minmax(420px,1.2fr)_minmax(420px,1fr)]">
        <div className="collection-header-panel">
          <PageHeader title="수집 이력 관리" description="뉴스, 공시, 가격 등 데이터 수집 작업의 실행 결과를 확인합니다." />
        </div>
        <SectionCard title="상태 요약" className="collection-summary-panel">
          <div className="grid grid-cols-3 gap-2 md:grid-cols-5">
            <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
              <p className="text-xs text-slate-600">전체</p>
              <p className="text-xl font-semibold text-slate-900">{summary.total}</p>
            </div>
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2">
              <p className="text-xs text-emerald-700">성공</p>
              <p className="text-xl font-semibold text-emerald-800">{summary.success}</p>
            </div>
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2">
              <p className="text-xs text-rose-700">실패</p>
              <p className="text-xl font-semibold text-rose-800">{summary.failed}</p>
            </div>
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2">
              <p className="text-xs text-amber-700">부분성공</p>
              <p className="text-xl font-semibold text-amber-800">{summary.partial}</p>
            </div>
            <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-2">
              <p className="text-xs text-indigo-700">진행중</p>
              <p className="text-xl font-semibold text-indigo-800">{summary.running}</p>
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="검색">
        <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-6">
          <div className="md:col-span-2">
            <p className="mb-1 text-xs text-slate-600">수집기명</p>
            <input className="input-control" placeholder="수집명 또는 내부 수집기명" value={collectorName} onChange={(e) => setCollectorName(e.target.value)} />
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-600">상태</p>
            <select className="select-control" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">전체</option>
              {statusOptions.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-600">대상</p>
            <input className="input-control" placeholder="대상 종목코드 또는 target" value={target} onChange={(e) => setTarget(e.target.value)} />
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-600">조회 건수</p>
            <select className="select-control" value={limit} onChange={(e) => void onChangePageSize(e.target.value)}>
              <option value="20">20</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </div>
          <div className="flex items-end gap-2">
            <button type="submit" className="btn btn-primary">검색</button>
            <button type="button" className="btn btn-secondary" onClick={() => void onReset()}>초기화</button>
          </div>
        </form>
      </SectionCard>

      <SectionCard title="수집 이력 목록">
        <div className="mb-3 flex justify-end">
          <button type="button" className="btn btn-danger" disabled={cleanupLoading} onClick={() => void onCleanupOlderThanOneMonth()}>
            {cleanupLoading ? "삭제 중..." : "1달 전 이력 삭제"}
          </button>
        </div>
        {loading ? <p className="text-sm text-muted">조회 중입니다.</p> : null}
        {error ? <p className="text-sm text-rose-600">{error}</p> : null}
        {!error && resultMessage ? <p className="text-sm text-emerald-700">{resultMessage}</p> : null}

        {!loading && !error && items.length === 0 ? <EmptyState message="수집 이력이 없습니다." /> : null}

        {!loading && !error && items.length > 0 ? (
          <>
            <div className="table-shell">
              <table className="data-table min-w-[1200px]">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>수집명</th>
                    <th>실행유형</th>
                    <th>대상</th>
                    <th>상태</th>
                    <th>시작일시</th>
                    <th>종료일시</th>
                    <th>메시지</th>
                    <th>생성일시</th>
                    <th>상세</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((r) => (
                    <tr key={r.id}>
                      <td>{r.id}</td>
                      <td>{r.collector_display_name || r.collector_name}</td>
                      <td>{r.run_type_label || "-"}</td>
                      <td>{r.target || "-"}</td>
                      <td><StatusBadge label={statusLabel[r.status] || r.status} tone={statusTone[r.status] || "slate"} /></td>
                      <td>{r.started_at}</td>
                      <td>{r.finished_at || "-"}</td>
                      <td>{truncateText(r.message, 80)}</td>
                      <td>{r.created_at}</td>
                      <td>
                        {r.message ? (
                          <button type="button" className="btn btn-secondary" onClick={() => setSelectedRun(r)}>
                            자세히
                          </button>
                        ) : (
                          "-"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination-bar">
              <p className="pagination-info">
                총 {totalCount}건 · {page}/{totalPages} 페이지
              </p>
              <div className="pagination-actions">
                <button type="button" className="btn btn-secondary" disabled={page <= 1 || loading} onClick={() => void onPrevPage()}>
                  이전
                </button>
                <button type="button" className="btn btn-secondary" disabled={page >= totalPages || loading} onClick={() => void onNextPage()}>
                  다음
                </button>
              </div>
            </div>
          </>
        ) : null}
      </SectionCard>

      {selectedRun ? (
        <SectionCard title="상세 메시지">
          <div className="space-y-1 text-sm">
            <p><span className="text-muted">ID:</span> {selectedRun.id}</p>
            <p><span className="text-muted">수집명:</span> {selectedRun.collector_display_name || selectedRun.collector_name}</p>
            <p><span className="text-muted">내부 수집기명:</span> {selectedRun.collector_name}</p>
            <p><span className="text-muted">실행유형:</span> {selectedRun.run_type_label || "-"}</p>
            <p><span className="text-muted">그룹:</span> {selectedRun.collector_group_label || "-"}</p>
            <p><span className="text-muted">대상:</span> {selectedRun.target || "-"}</p>
            <p><span className="text-muted">상태:</span> {statusLabel[selectedRun.status] || selectedRun.status}</p>
            <p><span className="text-muted">시작일시:</span> {selectedRun.started_at}</p>
            <p><span className="text-muted">종료일시:</span> {selectedRun.finished_at || "-"}</p>
            <p><span className="text-muted">메시지:</span></p>
            <pre className="whitespace-pre-wrap rounded-xl bg-slate-50 p-3 text-xs text-slate-700">{selectedRun.message || "-"}</pre>
          </div>
        </SectionCard>
      ) : null}
    </div>
  );
}

export default CollectionRunsPage;
