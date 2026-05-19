import { RotateCw, Search } from "lucide-react";
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
  limit: "50",
  offset: "0",
};

function CollectionRunsPage() {
  const [items, setItems] = useState<CollectionRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<CollectionRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [collectorName, setCollectorName] = useState(initialFilters.collectorName);
  const [status, setStatus] = useState(initialFilters.status);
  const [target, setTarget] = useState(initialFilters.target);
  const [limit, setLimit] = useState(initialFilters.limit);
  const [offset, setOffset] = useState(initialFilters.offset);

  const load = async (params?: { collectorName?: string; status?: string; target?: string; limit?: string; offset?: string }) => {
    const activeCollector = params?.collectorName ?? collectorName;
    const activeStatus = params?.status ?? status;
    const activeTarget = params?.target ?? target;
    const activeLimit = params?.limit ?? limit;
    const activeOffset = params?.offset ?? offset;

    setLoading(true);
    setError("");
    try {
      const data = await repositories.collectionRuns.listCollectionRuns({
        collector_name: activeCollector || undefined,
        status: activeStatus || undefined,
        target: activeTarget || undefined,
        limit: Number(activeLimit) || 50,
        offset: Number(activeOffset) || 0,
      });
      setItems(data);
      if (selectedRun) {
        const updated = data.find((item) => item.id === selectedRun.id) ?? null;
        setSelectedRun(updated);
      }
    } catch {
      setError("수집 이력을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const summary = useMemo(() => {
    const result = { total: items.length, success: 0, failed: 0, partial: 0, running: 0 };
    for (const item of items) {
      if (item.status === "success") result.success += 1;
      else if (item.status === "failed") result.failed += 1;
      else if (item.status === "partial") result.partial += 1;
      else if (item.status === "running") result.running += 1;
    }
    return result;
  }, [items]);

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    await load();
  };

  const onRefresh = async () => {
    await load();
  };

  const onReset = async () => {
    setCollectorName(initialFilters.collectorName);
    setStatus(initialFilters.status);
    setTarget(initialFilters.target);
    setLimit(initialFilters.limit);
    setOffset(initialFilters.offset);
    setSelectedRun(null);
    await load({
      collectorName: initialFilters.collectorName,
      status: initialFilters.status,
      target: initialFilters.target,
      limit: initialFilters.limit,
      offset: initialFilters.offset,
    });
  };

  return (
    <div className="space-y-4">
      <PageHeader title="수집 이력 관리" description="뉴스, 공시, 가격 등 데이터 수집 작업의 실행 결과를 확인합니다." />

      <SectionCard title="검색">
        <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-7">
          <div className="relative md:col-span-2">
            <p className="mb-1 text-xs text-slate-600">수집기명</p>
            <Search size={16} className="absolute left-3 top-8 text-slate-400" />
            <input className="input-control pl-9" placeholder="수집명 또는 내부 수집기명" value={collectorName} onChange={(e) => setCollectorName(e.target.value)} />
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
            <select className="select-control" value={limit} onChange={(e) => setLimit(e.target.value)}>
              <option value="20">20</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </div>
          <div>
            <p className="mb-1 text-xs text-slate-600">시작 위치</p>
            <select className="select-control" value={offset} onChange={(e) => setOffset(e.target.value)}>
              <option value="0">0</option>
              <option value="20">20</option>
              <option value="50">50</option>
            </select>
          </div>
          <div className="flex items-end gap-2">
            <button type="submit" className="btn btn-primary">검색</button>
            <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
            <button type="button" className="btn btn-secondary inline-flex items-center gap-1" onClick={onRefresh}>
              <RotateCw size={14} /> 새로고침
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard title="상태 요약">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
          <div className="card"><p className="text-xs text-muted">전체</p><p className="text-lg font-semibold">{summary.total}</p></div>
          <div className="card"><p className="text-xs text-emerald-700">성공</p><p className="text-lg font-semibold text-emerald-800">{summary.success}</p></div>
          <div className="card"><p className="text-xs text-rose-700">실패</p><p className="text-lg font-semibold text-rose-800">{summary.failed}</p></div>
          <div className="card"><p className="text-xs text-amber-700">부분성공</p><p className="text-lg font-semibold text-amber-800">{summary.partial}</p></div>
          <div className="card"><p className="text-xs text-indigo-700">진행중</p><p className="text-lg font-semibold text-indigo-800">{summary.running}</p></div>
        </div>
      </SectionCard>

      <SectionCard title="수집 이력 목록">
        {loading ? <p className="text-sm text-muted">조회 중입니다.</p> : null}
        {error ? <p className="text-sm text-rose-600">{error}</p> : null}

        {!loading && !error && items.length === 0 ? <EmptyState message="수집 이력이 없습니다." /> : null}

        {!loading && !error && items.length > 0 ? (
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
