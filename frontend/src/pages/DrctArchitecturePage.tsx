import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type {
  ArchitectureCleanupCandidateItem,
  ArchitectureCleanupHistoryItem,
  ArchitectureDeleteEligibilityItem,
  ArchitectureFolderStatusItem,
  ArchitectureReferenceCheckResponse,
} from "@/types/architecture";

type TabKey =
  | "folder_status"
  | "cleanup_candidates"
  | "delete_eligibility"
  | "operational_data"
  | "cleanup_history"
  | "architecture_docs";

type DeleteFilterValue =
  | "all"
  | "safe_to_delete"
  | "archived_delete_candidate"
  | "safe_to_delete_after_archive"
  | "protected"
  | "blocked_by_reference"
  | "review_required"
  | "unknown";

const TABS: { key: TabKey; label: string }[] = [
  { key: "folder_status", label: "폴더 현황" },
  { key: "cleanup_candidates", label: "정리 후보" },
  { key: "delete_eligibility", label: "삭제 가능 여부" },
  { key: "operational_data", label: "운영 데이터" },
  { key: "cleanup_history", label: "정리 이력" },
  { key: "architecture_docs", label: "아키텍처 문서" },
];

const DELETE_FILTER_OPTIONS: { value: DeleteFilterValue; label: string }[] = [
  { value: "all", label: "전체" },
  { value: "safe_to_delete", label: "삭제 가능" },
  { value: "archived_delete_candidate", label: "Archive 삭제 가능" },
  { value: "safe_to_delete_after_archive", label: "Archive 후 삭제 가능" },
  { value: "protected", label: "삭제 금지" },
  { value: "blocked_by_reference", label: "코드 참조 있음" },
  { value: "review_required", label: "사용 여부 확인 필요" },
  { value: "unknown", label: "판단 불가" },
];

const formatMb = (bytes?: number) =>
  `${(Number(bytes ?? 0) / (1024 * 1024)).toLocaleString("ko-KR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} MB`;

const statusClass = (status: string) => {
  if (status === "safe_to_delete" || status === "archived_delete_candidate") return "badge badge-emerald";
  if (status === "blocked_by_reference" || status === "review_required") return "badge badge-amber";
  if (status === "protected" || status === "archive_delete_blocked") return "badge badge-rose";
  return "badge badge-slate";
};

const isDeleteSelectable = (item: ArchitectureDeleteEligibilityItem) =>
  item.deletion_status === "safe_to_delete" || item.deletion_status === "archived_delete_candidate";

function DrctArchitecturePage() {
  const [activeTab, setActiveTab] = useState<TabKey>("folder_status");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [statusItems, setStatusItems] = useState<ArchitectureFolderStatusItem[]>([]);
  const [cleanupItems, setCleanupItems] = useState<ArchitectureCleanupCandidateItem[]>([]);
  const [deleteEligibilityItems, setDeleteEligibilityItems] = useState<ArchitectureDeleteEligibilityItem[]>([]);
  const [historyItems, setHistoryItems] = useState<ArchitectureCleanupHistoryItem[]>([]);
  const [referenceResult, setReferenceResult] = useState<ArchitectureReferenceCheckResponse | null>(null);

  const [scannedAt, setScannedAt] = useState("");
  const [totalSize, setTotalSize] = useState(0);
  const [operationalSize, setOperationalSize] = useState(0);
  const [cacheArtifactSize, setCacheArtifactSize] = useState(0);
  const [cleanupSize, setCleanupSize] = useState(0);

  const [selectedCleanupTargets, setSelectedCleanupTargets] = useState<Record<string, boolean>>({});
  const [selectedDeleteTargets, setSelectedDeleteTargets] = useState<Record<string, boolean>>({});
  const [deleteFilter, setDeleteFilter] = useState<DeleteFilterValue>("all");

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");

  const cleanupTargets = useMemo(
    () => Object.entries(selectedCleanupTargets).filter(([, checked]) => checked).map(([path]) => path),
    [selectedCleanupTargets]
  );
  const isAllCleanupSelected = useMemo(
    () => cleanupItems.length > 0 && cleanupItems.every((item) => selectedCleanupTargets[item.path]),
    [cleanupItems, selectedCleanupTargets]
  );

  const filteredDeleteItems = useMemo(() => {
    if (deleteFilter === "all") return deleteEligibilityItems;
    return deleteEligibilityItems.filter((item) => item.deletion_status === deleteFilter);
  }, [deleteEligibilityItems, deleteFilter]);

  const safeDeleteTargets = useMemo(
    () => Object.entries(selectedDeleteTargets).filter(([, checked]) => checked).map(([path]) => path),
    [selectedDeleteTargets]
  );

  const refreshFolderStatus = async () => {
    const response = await repositories.architecture.fetchFolderStatus();
    setStatusItems(response.items);
    setScannedAt(response.scanned_at);
    setTotalSize(response.total_size_bytes);
    setOperationalSize(response.operational_data_size_bytes);
    setCacheArtifactSize(response.cache_and_artifact_size_bytes);
    setCleanupSize(response.cleanup_candidate_size_bytes);
  };

  const refreshCleanupCandidates = async () => {
    const response = await repositories.architecture.fetchCleanupCandidates();
    setCleanupItems(response.items);
    setSelectedCleanupTargets(Object.fromEntries(response.items.map((item) => [item.path, false])));
  };

  const refreshDeleteEligibility = async () => {
    const response = await repositories.architecture.fetchDeleteEligibility();
    setDeleteEligibilityItems(response.items);
    setSelectedDeleteTargets(Object.fromEntries(response.items.map((item) => [item.path, false])));
  };

  const refreshHistory = async () => {
    const response = await repositories.architecture.fetchCleanupHistory();
    setHistoryItems(response.items);
  };

  const refreshAll = async () => {
    setLoading(true);
    setMessage("");
    setError("");
    try {
      await Promise.all([refreshFolderStatus(), refreshCleanupCandidates(), refreshDeleteEligibility(), refreshHistory()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "아키텍처 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshAll();
  }, []);

  const runReferenceCheck = async (path: string) => {
    try {
      const result = await repositories.architecture.referenceCheck(path);
      setReferenceResult(result);
      setMessage(`참조 검사 완료: ${path} (${result.reference_count.toLocaleString("ko-KR")}건)`);
      if (activeTab === "delete_eligibility") {
        await refreshDeleteEligibility();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "참조 검사에 실패했습니다.");
    }
  };

  const runArchive = async () => {
    if (cleanupTargets.length === 0) {
      setError("Archive할 항목을 선택해 주세요.");
      return;
    }
    const ok = window.confirm("선택한 항목을 archive/cleanup 아래로 이동하시겠습니까? DB, 이미지, 환경파일은 대상이 아닙니다.");
    if (!ok) return;

    setLoading(true);
    setMessage("");
    setError("");
    try {
      const response = await repositories.architecture.runCleanup({
        targets: cleanupTargets,
        mode: "archive",
        confirm: true,
      });
      const summary = response.results.reduce(
        (acc, cur) => {
          acc[cur.status] = (acc[cur.status] ?? 0) + 1;
          return acc;
        },
        {} as Record<string, number>
      );
      setMessage(
        `Archive 완료: archived ${summary.archived ?? 0}, copy_only ${summary.archived_copy_only ?? 0}, blocked ${
          summary.blocked ?? 0
        }, skipped ${summary.skipped ?? 0}, error ${summary.error ?? 0}`
      );
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Archive 실행에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const onTrySafeDelete = () => {
    if (safeDeleteTargets.length === 0) {
      setError("삭제할 항목을 선택해 주세요.");
      return;
    }
    setDeleteConfirmText("");
    setShowDeleteConfirm(true);
  };

  const runSafeDelete = async () => {
    if (deleteConfirmText !== "삭제를 확인합니다") {
      setError("확인 문구를 정확히 입력해 주세요.");
      return;
    }
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const response = await repositories.architecture.deleteSafeCandidates({
        targets: safeDeleteTargets,
        confirm_text: deleteConfirmText,
      });
      const summary = response.results.reduce(
        (acc, cur) => {
          acc[cur.status] = (acc[cur.status] ?? 0) + 1;
          return acc;
        },
        {} as Record<string, number>
      );
      setMessage(
        `안전 삭제 완료: deleted ${summary.deleted ?? 0}, blocked ${summary.blocked ?? 0}, skipped ${summary.skipped ?? 0}, error ${
          summary.error ?? 0
        }`
      );
      setShowDeleteConfirm(false);
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "안전 삭제 실행에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const operationalItems = useMemo(
    () => statusItems.filter((item) => item.category === "operational_data" || item.category === "upload_data" || item.category === "protected"),
    [statusItems]
  );

  return (
    <div className="space-y-4">
      <PageHeader
        title="DrCT아키텍처"
        description="개발 소스, 운영 데이터, 캐시/산출물, 정리 후보를 구분하여 프로젝트 운영 상태를 점검합니다."
      />

      <SectionCard title="요약">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-5">
          <div className="rounded border border-slate-200 bg-white p-3">
            <p className="text-xs text-slate-500">전체 스캔 용량</p>
            <strong>{formatMb(totalSize)}</strong>
          </div>
          <div className="rounded border border-slate-200 bg-white p-3">
            <p className="text-xs text-slate-500">운영 데이터 용량</p>
            <strong>{formatMb(operationalSize)}</strong>
          </div>
          <div className="rounded border border-slate-200 bg-white p-3">
            <p className="text-xs text-slate-500">캐시/산출물 용량</p>
            <strong>{formatMb(cacheArtifactSize)}</strong>
          </div>
          <div className="rounded border border-slate-200 bg-white p-3">
            <p className="text-xs text-slate-500">정리 후보 용량</p>
            <strong>{formatMb(cleanupSize)}</strong>
          </div>
          <div className="rounded border border-slate-200 bg-white p-3">
            <p className="text-xs text-slate-500">마지막 스캔 시각</p>
            <strong>{scannedAt || "-"}</strong>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="안내">
        <p className="text-sm text-slate-600">
          GitHub 저장소 정리를 위해서는 삭제 가능 여부가 <strong>삭제 가능</strong> 또는 <strong>Archive 삭제 가능</strong>인 항목만 정리하세요.
          <strong> 사용 여부 확인 필요</strong> 또는 <strong>코드 참조 있음</strong> 항목은 삭제하지 마세요.
        </p>
      </SectionCard>

      <SectionCard title="아키텍처 탭">
        <div className="gpt-domain-tabs">
          {TABS.map((tab) => (
            <button key={tab.key} type="button" className={`gpt-domain-tab ${activeTab === tab.key ? "active" : ""}`} onClick={() => setActiveTab(tab.key)}>
              {tab.label}
            </button>
          ))}
        </div>
      </SectionCard>

      {loading ? <p className="inline-result">처리 중입니다.</p> : null}
      {message ? <p className="inline-result inline-success">{message}</p> : null}
      {error ? <p className="inline-result inline-error">{error}</p> : null}

      {activeTab === "folder_status" ? (
        <SectionCard title="폴더 현황">
          <div className="mb-2 flex gap-2">
            <button type="button" className="btn btn-secondary" onClick={() => void refreshAll()}>
              새로고침
            </button>
          </div>
          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th>경로</th>
                  <th>구분</th>
                  <th>역할</th>
                  <th>용량</th>
                  <th>파일 수</th>
                  <th>최근 수정일</th>
                  <th>정책</th>
                  <th>위험도</th>
                  <th>참조 검사</th>
                </tr>
              </thead>
              <tbody>
                {statusItems.map((item) => (
                  <tr key={`status-${item.path}`}>
                    <td>{item.path}</td>
                    <td>{item.category}</td>
                    <td>{item.role}</td>
                    <td>{formatMb(item.size_bytes)}</td>
                    <td>{item.file_count.toLocaleString("ko-KR")}</td>
                    <td>{item.latest_modified_at || "-"}</td>
                    <td>
                      <span className="badge badge-slate">{item.policy}</span>
                    </td>
                    <td>
                      <span className="badge badge-amber">{item.risk_level}</span>
                    </td>
                    <td>
                      <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void runReferenceCheck(item.path)}>
                        검사
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}

      {activeTab === "cleanup_candidates" ? (
        <SectionCard title="정리 후보">
          <div className="mb-2 flex gap-2">
            <button type="button" className="btn btn-primary" onClick={() => void runArchive()}>
              선택 항목 Archive
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => void refreshAll()}>
              새로고침
            </button>
          </div>
          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th>
                    <label className="inline-flex items-center gap-1 text-xs">
                      <input
                        type="checkbox"
                        checked={isAllCleanupSelected}
                        onChange={(e) =>
                          setSelectedCleanupTargets(
                            Object.fromEntries(cleanupItems.map((item) => [item.path, e.target.checked]))
                          )
                        }
                      />
                      <span>모두선택</span>
                    </label>
                  </th>
                  <th>경로</th>
                  <th>유형</th>
                  <th>용량</th>
                  <th>파일 수</th>
                  <th>최근 수정일</th>
                  <th>추천 조치</th>
                  <th>위험도</th>
                  <th>참조 검사</th>
                </tr>
              </thead>
              <tbody>
                {cleanupItems.map((item) => (
                  <tr key={`cleanup-${item.path}`}>
                    <td>
                      <input
                        type="checkbox"
                        checked={!!selectedCleanupTargets[item.path]}
                        onChange={(e) => setSelectedCleanupTargets((prev) => ({ ...prev, [item.path]: e.target.checked }))}
                      />
                    </td>
                    <td>{item.path}</td>
                    <td>{item.candidate_type}</td>
                    <td>{formatMb(item.size_bytes)}</td>
                    <td>{item.file_count.toLocaleString("ko-KR")}</td>
                    <td>{item.latest_modified_at || "-"}</td>
                    <td>
                      <span className="badge badge-slate">{item.policy}</span>
                    </td>
                    <td>
                      <span className="badge badge-amber">{item.risk_level}</span>
                    </td>
                    <td>
                      <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => void runReferenceCheck(item.path)}>
                        참조 검사
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}

      {activeTab === "delete_eligibility" ? (
        <SectionCard title="삭제 가능 여부">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-sm font-semibold text-slate-700">삭제 판정</label>
              <select
                className="select-control"
                style={{ width: 220, minHeight: 36 }}
                value={deleteFilter}
                onChange={(e) => {
                  setDeleteFilter(e.target.value as DeleteFilterValue);
                  setSelectedDeleteTargets({});
                }}
              >
                {DELETE_FILTER_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="text-sm text-slate-600">
                표시 {filteredDeleteItems.length.toLocaleString("ko-KR")}건 / 전체 {deleteEligibilityItems.length.toLocaleString("ko-KR")}건
              </p>
            </div>
            <div className="flex gap-2">
              <button type="button" className="btn btn-primary" onClick={onTrySafeDelete}>
                선택 항목 안전 삭제
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => void refreshDeleteEligibility()}>
                새로고침
              </button>
            </div>
          </div>

          <div className="table-shell architecture-delete-grid-shell">
            <table className="data-table architecture-delete-grid-table">
              <colgroup>
                <col style={{ width: 56 }} />
                <col style={{ width: 280 }} />
                <col style={{ width: 120 }} />
                <col style={{ width: 90 }} />
                <col style={{ width: 90 }} />
                <col style={{ width: 140 }} />
                <col style={{ width: 420 }} />
                <col style={{ width: 90 }} />
                <col style={{ width: 90 }} />
                <col style={{ width: 90 }} />
              </colgroup>
              <thead>
                <tr>
                  <th>선택</th>
                  <th>경로</th>
                  <th>구분</th>
                  <th>용량</th>
                  <th>파일 수</th>
                  <th>삭제 판정</th>
                  <th>판정 사유</th>
                  <th>참조 건수</th>
                  <th>Git 추적</th>
                  <th>위험도</th>
                </tr>
              </thead>
              <tbody>
                {filteredDeleteItems.map((item) => {
                  const selectable = isDeleteSelectable(item);
                  return (
                    <tr key={`elig-${item.path}`}>
                      <td className="cell-nowrap">
                        <input
                          type="checkbox"
                          disabled={!selectable}
                          checked={!!selectedDeleteTargets[item.path]}
                          onChange={(e) => setSelectedDeleteTargets((prev) => ({ ...prev, [item.path]: e.target.checked }))}
                        />
                      </td>
                      <td className="cell-nowrap" title={item.path}>
                        {item.path}
                      </td>
                      <td className="cell-nowrap" title={item.category}>
                        {item.category}
                      </td>
                      <td className="cell-nowrap text-right">{formatMb(item.size_bytes)}</td>
                      <td className="cell-nowrap text-right">{item.file_count.toLocaleString("ko-KR")}</td>
                      <td className="cell-nowrap">
                        <span className={statusClass(item.deletion_status)} title={item.deletion_label}>
                          {item.deletion_label}
                        </span>
                      </td>
                      <td className="cell-nowrap" title={item.delete_reason}>
                        {item.delete_reason}
                      </td>
                      <td className="cell-nowrap text-right">{item.reference_count == null ? "-" : item.reference_count.toLocaleString("ko-KR")}</td>
                      <td className="cell-nowrap text-center">{item.is_git_tracked == null ? "-" : item.is_git_tracked ? "예" : "아니오"}</td>
                      <td className="cell-nowrap">
                        <span className="badge badge-amber" title={item.risk_level}>
                          {item.risk_level}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {showDeleteConfirm ? (
            <div className="mt-3 rounded border border-slate-200 bg-slate-50 p-3">
              <p className="mb-2 text-sm text-slate-700">
                삭제 확인 문구를 입력해 주세요: <strong>삭제를 확인합니다</strong>
              </p>
              <input
                type="text"
                className="mb-2 w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm"
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                placeholder="삭제를 확인합니다"
              />
              <div className="flex gap-2">
                <button type="button" className="btn btn-danger" onClick={() => void runSafeDelete()}>
                  안전 삭제 실행
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setShowDeleteConfirm(false)}>
                  취소
                </button>
              </div>
            </div>
          ) : null}
        </SectionCard>
      ) : null}

      {activeTab === "operational_data" ? (
        <SectionCard title="운영 데이터">
          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th>경로</th>
                  <th>정책</th>
                  <th>역할</th>
                  <th>용량</th>
                  <th>파일 수</th>
                  <th>최근 수정일</th>
                </tr>
              </thead>
              <tbody>
                {operationalItems.map((item) => (
                  <tr key={`op-${item.path}`}>
                    <td>{item.path}</td>
                    <td>
                      <span className="badge badge-rose">삭제 금지</span>
                    </td>
                    <td>{item.role}</td>
                    <td>{formatMb(item.size_bytes)}</td>
                    <td>{item.file_count.toLocaleString("ko-KR")}</td>
                    <td>{item.latest_modified_at || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}

      {activeTab === "cleanup_history" ? (
        <SectionCard title="정리 이력">
          <div className="mb-2 flex gap-2">
            <button type="button" className="btn btn-secondary" onClick={() => void refreshHistory()}>
              새로고침
            </button>
          </div>
          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th>실행일시</th>
                  <th>모드</th>
                  <th>대상</th>
                  <th>원본 경로</th>
                  <th>보관 경로</th>
                  <th>용량</th>
                  <th>파일 수</th>
                  <th>상태</th>
                  <th>메시지</th>
                </tr>
              </thead>
              <tbody>
                {historyItems.map((item, index) => (
                  <tr key={`history-${index}`}>
                    <td>{item.executed_at}</td>
                    <td>{item.mode}</td>
                    <td>{item.target}</td>
                    <td>{item.original_path}</td>
                    <td>{item.archived_path || "-"}</td>
                    <td>{formatMb(item.size_bytes)}</td>
                    <td>{item.file_count.toLocaleString("ko-KR")}</td>
                    <td>{item.status}</td>
                    <td>{item.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}

      {activeTab === "architecture_docs" ? (
        <SectionCard title="아키텍처 문서">
          <div className="space-y-2 text-sm text-slate-700">
            <p>
              <strong>backend</strong>: FastAPI API/Service/Repository 레이어로 비즈니스 로직과 DB 접근을 분리합니다.
            </p>
            <p>
              <strong>frontend</strong>: React 페이지/컴포넌트, API Repository, 타입 레이어로 UI와 데이터 접근을 분리합니다.
            </p>
            <p>
              <strong>db/data</strong>: DB 파일과 업로드 파일(매매일지 이미지)은 운영 핵심 데이터로 삭제 금지 대상입니다.
            </p>
            <p>
              <strong>cache/build artifact</strong>: <code>.cache</code>, <code>.mpltcache</code>, <code>data_cache</code>, <code>dist</code>,{" "}
              <code>__pycache__</code>, <code>*.pyc</code> 는 정리 후보입니다.
            </p>
            <p>
              <strong>사용 여부 확인 대상</strong>: <code>marcap</code>, <code>agents</code>, <code>prompts</code>, <code>knowledge</code> 는
              참조 검사 후 판단합니다.
            </p>
            <p>
              <strong>정리 원칙</strong>: 기본은 archive 우선이며, 안전 삭제는 삭제 가능 판정 항목만 제한적으로 실행합니다.
            </p>
          </div>
        </SectionCard>
      ) : null}

      {referenceResult ? (
        <SectionCard title={`참조 검사 결과: ${referenceResult.path}`}>
          <p className="mb-2 text-sm text-slate-600">참조 건수: {referenceResult.reference_count.toLocaleString("ko-KR")}</p>
          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th>파일</th>
                  <th>라인</th>
                  <th>스니펫</th>
                </tr>
              </thead>
              <tbody>
                {referenceResult.matches.map((match, index) => (
                  <tr key={`ref-${index}`}>
                    <td>{match.file_path}</td>
                    <td>{match.line_no}</td>
                    <td>{match.snippet}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      ) : null}
    </div>
  );
}

export default DrctArchitecturePage;
