import { useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen, ChevronRight, FlaskConical, History, Pencil, Plus, Power, X } from "lucide-react";

import SignalEmptyState from "@/components/drctStockSignals/SignalEmptyState";
import HtsRuleImportPanel from "@/components/drctStockSignals/HtsRuleImportPanel";
import SignalAnalysisWorkspace from "@/components/drctStockSignals/SignalAnalysisWorkspace";
import { repositories } from "@/services";
import type { DrctSignalMarkerOptionGroup, DrctSignalSearch, DrctSignalSearchCreate, DrctSignalSearchDetail, DrctSignalVersion, DrctSignalVersionCreate, DrctTrainingOverview } from "@/types/drctStockSignal";

type ModalType = "create" | "edit" | "version" | "markers" | "history" | "source" | null;
const emptyCreateForm: DrctSignalSearchCreate = { name: "", description: "", hts_reference_conditions: "", hts_condition_expression: "", change_note: "" };
const errorMessage = (reason: unknown) => reason instanceof Error ? reason.message : "요청을 처리하지 못했습니다.";
const formatDate = (value?: string | null) => value ? value.slice(0, 10) : "-";

function SignalResearchTab() {
  const [searches, setSearches] = useState<DrctSignalSearch[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DrctSignalSearchDetail | null>(null);
  const [modal, setModal] = useState<ModalType>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<DrctSignalSearchCreate>(emptyCreateForm);
  const [editForm, setEditForm] = useState({ name: "", description: "", display_order: 100 });
  const [versionForm, setVersionForm] = useState<DrctSignalVersionCreate>({ hts_reference_conditions: "", hts_condition_expression: "", drct_rule_text: "", change_note: "" });
  const [versions, setVersions] = useState<DrctSignalVersion[]>([]);
  const [viewVersion, setViewVersion] = useState<DrctSignalVersion | null>(null);
  const [markerOptions, setMarkerOptions] = useState<DrctSignalMarkerOptionGroup[]>([]);
  const [checkedMarkerIds, setCheckedMarkerIds] = useState<number[]>([]);
  const [overview, setOverview] = useState<DrctTrainingOverview | null>(null);

  const loadSearches = useCallback(async (preferredId?: number) => {
    setLoading(true); setError(null);
    try {
      const [rows, overviewResult] = await Promise.all([repositories.drctStockSignals.listSearches(true), repositories.drctStockSignals.trainingOverview()]);
      setSearches(rows);
      setOverview(overviewResult);
      setSelectedId((current) => preferredId && rows.some((row) => row.id === preferredId) ? preferredId : current && rows.some((row) => row.id === current) ? current : rows[0]?.id ?? null);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setLoading(false); }
  }, []);

  const loadDetail = useCallback(async (searchId: number) => {
    setError(null);
    try { setDetail(await repositories.drctStockSignals.getSearch(searchId)); }
    catch (reason) { setDetail(null); setError(errorMessage(reason)); }
  }, []);

  useEffect(() => { void loadSearches(); }, [loadSearches]);
  useEffect(() => { if (selectedId) void loadDetail(selectedId); else setDetail(null); }, [selectedId, loadDetail]);

  const refresh = async (searchId: number) => { await loadSearches(searchId); await loadDetail(searchId); };
  const openEdit = () => { if (detail) { setEditForm({ name: detail.name, description: detail.description ?? "", display_order: detail.display_order }); setModal("edit"); } };
  const openVersion = () => { if (detail) { setVersionForm({ hts_reference_conditions: detail.current_version.hts_reference_conditions, hts_condition_expression: detail.current_version.hts_condition_expression, drct_rule_text: detail.current_version.drct_rule_text ?? "", change_note: "" }); setModal("version"); } };
  const openMarkers = async () => { if (!detail) return; try { const response = await repositories.drctStockSignals.markerOptions(); setMarkerOptions(response.items); setCheckedMarkerIds(detail.marker_links.map((link) => link.marker_definition_id)); setModal("markers"); } catch (reason) { setError(errorMessage(reason)); } };
  const openHistory = async () => { if (!detail) return; try { const rows = await repositories.drctStockSignals.listVersions(detail.id); setVersions(rows); setViewVersion(rows[0] ?? null); setModal("history"); } catch (reason) { setError(errorMessage(reason)); } };

  const submitCreate = async (event: React.FormEvent) => { event.preventDefault(); setSaving(true); setError(null); try { const created = await repositories.drctStockSignals.createSearch(createForm); setCreateForm(emptyCreateForm); setModal(null); await refresh(created.id); } catch (reason) { setError(errorMessage(reason)); } finally { setSaving(false); } };
  const submitEdit = async (event: React.FormEvent) => { event.preventDefault(); if (!detail) return; setSaving(true); setError(null); try { await repositories.drctStockSignals.updateSearch(detail.id, { name: editForm.name, description: editForm.description || null, display_order: editForm.display_order }); setModal(null); await refresh(detail.id); } catch (reason) { setError(errorMessage(reason)); } finally { setSaving(false); } };
  const submitVersion = async (event: React.FormEvent) => { event.preventDefault(); if (!detail) return; setSaving(true); setError(null); try { await repositories.drctStockSignals.createVersion(detail.id, versionForm); setModal(null); await refresh(detail.id); } catch (reason) { setError(errorMessage(reason)); } finally { setSaving(false); } };
  const submitMarkers = async () => { if (!detail) return; setSaving(true); setError(null); try { await repositories.drctStockSignals.replaceMarkerLinks(detail.id, checkedMarkerIds); setModal(null); await refresh(detail.id); } catch (reason) { setError(errorMessage(reason)); } finally { setSaving(false); } };
  const setActive = async (active: boolean) => { if (!detail) return; if (!active && !window.confirm("이 검색식을 비활성화할까요? 과거 Version과 마커 연결은 유지됩니다.")) return; setSaving(true); try { await repositories.drctStockSignals.updateSearch(detail.id, active ? { is_active: true, lifecycle_status: "REFERENCE" } : { is_active: false }); await refresh(detail.id); } catch (reason) { setError(errorMessage(reason)); } finally { setSaving(false); } };

  const overviewById = useMemo(() => new Map(overview?.items.map((item) => [item.search_id, item]) ?? []), [overview]);

  return <div className="drct-signal-research-layout phase-two">
    <section className="drct-signal-panel drct-signal-research-list" aria-labelledby="condition-list-title">
      <header className="drct-signal-panel-header"><div><h2 id="condition-list-title">검색식</h2><p>HTS 참조 조건과 Version을 관리합니다.</p></div><button type="button" className="btn btn-primary drct-signal-new-button" onClick={() => { setCreateForm(emptyCreateForm); setModal("create"); }}><Plus size={15} /> 새 검색식</button></header>
      {overview ? <div className="drct-training-overview" aria-label="학습 준비 현황">{[["등록", overview.registered_search_count], ["검색조건 완료", overview.rule_valid_count], ["마커 연결", overview.marker_linked_count], ["학습 데이터 준비", overview.dataset_ready_count]].map(([label, value]) => <div key={String(label)}><span>{label}</span><strong>{value}</strong></div>)}</div> : null}
      {error ? <p className="drct-signal-inline-error" role="alert">{error}</p> : null}
      {loading ? <p className="drct-signal-list-state">검색식을 불러오는 중입니다.</p> : null}
      {!loading && searches.length === 0 ? <SignalEmptyState icon={BookOpen} title="등록된 DrCT 검색식이 없습니다." description="새 검색식을 등록해 HTS 참조 조건과 Version을 관리하세요." compact /> : <div className="drct-signal-search-list">{searches.map((search) => { const research = overviewById.get(search.id); const ruleReady = research?.rule_valid; return <button key={search.id} type="button" className={selectedId === search.id ? "is-selected" : ""} onClick={() => setSelectedId(search.id)}><span className="drct-signal-search-name"><i className={search.is_active ? "" : "is-inactive"} />{search.name}</span><span className="drct-signal-search-meta"><b>{search.lifecycle_status}</b><em>v{search.current_version_no}</em></span><span className="drct-signal-search-counts">{ruleReady ? "검색조건 완료" : "검색조건 변환 필요"} · 마커 {search.training_summary.linked_marker_count}</span><span className={`drct-training-card-status ${research?.research_status === "RULE_REVIEW_NEEDED" ? "is-review" : ""}`}>학습 상태 · {research?.research_status === "RULE_REVIEW_NEEDED" ? "검색조건 검토 필요" : research?.dataset_ready ? "학습 데이터 준비" : "준비 항목 확인"}</span><ChevronRight size={15} /></button>; })}</div>}
    </section>

    <section className="drct-signal-panel drct-signal-research-detail" aria-labelledby="condition-detail-title">
      {!detail ? <SignalEmptyState icon={FlaskConical} title="검색식을 선택하면 상세 정보와 성공패턴 학습 상태를 확인할 수 있습니다." description="HTS 참조식과 DrCT 실행식은 서로 구분해 관리합니다." /> : <div className="drct-signal-detail-content">
        <header className="drct-signal-detail-header phase5c"><div><div className="drct-definition-badges"><span className={`drct-signal-status ${detail.lifecycle_status.toLowerCase()}`}>{detail.lifecycle_status}</span><span>v{detail.current_version_no}</span><span className={detail.current_version.structured_rule?.validation_status === "VALID" ? "is-ready" : "is-pending"}>{detail.current_version.structured_rule?.validation_status === "VALID" ? "검색조건 완료" : "검색조건 변환 필요"}</span></div><h2 id="condition-detail-title">{detail.name}</h2><p>{detail.description || "검색식 설명이 없습니다."}</p></div><div className="drct-signal-detail-actions"><button type="button" className="btn btn-secondary" onClick={openEdit}><Pencil size={14} /> 수정</button><button type="button" className="btn btn-secondary" onClick={() => void openHistory()}><History size={14} /> 버전 이력</button><button type="button" className={`btn btn-secondary ${detail.is_active ? "danger" : ""}`} disabled={saving} onClick={() => void setActive(!detail.is_active)}><Power size={14} /> {detail.is_active ? "비활성" : "활성화"}</button></div></header>
        <section className="drct-signal-detail-section drct-compact-definition" id="drct-rule-section"><div className="drct-signal-detail-section-head"><div><h3>검색식 정의</h3><p>이 검색식이 무엇을 찾는지 확인하고 실행 조건을 관리합니다.</p></div><button type="button" className="btn btn-secondary" onClick={openVersion}>HTS 새 Version</button></div><div className="drct-rule-reference-grid"><article className="drct-hts-summary"><header><div><h4>HTS 참조식</h4><p>매매훈련 종목 선정에 사용한 원본입니다.</p></div><span>참조</span></header><dl><div><dt>조건 수</dt><dd>{(detail.current_version.hts_reference_conditions.match(/(^|\n)\s*[A-Z]\s+/g) ?? []).length}개</dd></div><div><dt>최종 조건식</dt><dd>{detail.current_version.hts_condition_expression}</dd></div></dl><button type="button" className="btn btn-secondary" onClick={() => setModal("source")}>전체 조건 보기</button></article><HtsRuleImportPanel detail={detail} onVersionCreated={() => refresh(detail.id)} onError={setError} /></div></section>
      </div>}
    </section>

    {detail ? <SignalAnalysisWorkspace detail={detail} onManageMarkers={() => void openMarkers()} onError={setError} /> : null}

    {modal ? <div className="drct-signal-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving) setModal(null); }}><section className={`drct-signal-modal ${modal === "history" || modal === "markers" || modal === "source" ? "is-wide" : ""}`} role="dialog" aria-modal="true" aria-label="검색식 관리"><header><div><h3>{modal === "create" ? "새 검색식" : modal === "edit" ? "검색식 기본정보 수정" : modal === "version" ? `새 Version · v${(detail?.current_version_no ?? 0) + 1}` : modal === "markers" ? "차트마커 연결 관리" : modal === "source" ? "HTS 전체 조건" : "Version History"}</h3><p>{modal === "version" ? "기존 Version은 보존되고 새 Version이 Current가 됩니다." : modal === "markers" ? "검색식과 마커 종류의 연결만 변경합니다." : modal === "source" ? "읽기 전용 HTS 참조 원문과 최종 조건식입니다." : "DrCT 종목 시그널 검색식 관리"}</p></div><button type="button" aria-label="닫기" disabled={saving} onClick={() => setModal(null)}><X size={19} /></button></header>
      {modal === "create" ? <form onSubmit={submitCreate} className="drct-signal-form"><label>검색식명 *<input required value={createForm.name} onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })} /></label><label>설명<textarea rows={2} value={createForm.description ?? ""} onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })} /></label><label>HTS 참조 조건 *<textarea required rows={9} value={createForm.hts_reference_conditions} onChange={(e) => setCreateForm({ ...createForm, hts_reference_conditions: e.target.value })} /></label><label>HTS 최종 조건식 *<textarea required rows={3} value={createForm.hts_condition_expression} onChange={(e) => setCreateForm({ ...createForm, hts_condition_expression: e.target.value })} /></label><label>변경 메모<textarea rows={2} value={createForm.change_note ?? ""} onChange={(e) => setCreateForm({ ...createForm, change_note: e.target.value })} /></label><footer><button type="button" className="btn btn-secondary" onClick={() => setModal(null)}>취소</button><button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "저장 중" : "등록"}</button></footer></form> : null}
      {modal === "edit" ? <form onSubmit={submitEdit} className="drct-signal-form"><label>검색식명 *<input required value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} /></label><label>설명<textarea rows={4} value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} /></label><label>표시 순서<input type="number" min={0} value={editForm.display_order} onChange={(e) => setEditForm({ ...editForm, display_order: Number(e.target.value) })} /></label><footer><button type="button" className="btn btn-secondary" onClick={() => setModal(null)}>취소</button><button type="submit" className="btn btn-primary" disabled={saving}>저장</button></footer></form> : null}
      {modal === "version" ? <form onSubmit={submitVersion} className="drct-signal-form"><label>HTS 참조 조건 *<textarea required rows={9} value={versionForm.hts_reference_conditions} onChange={(e) => setVersionForm({ ...versionForm, hts_reference_conditions: e.target.value })} /></label><label>HTS 최종 조건식 *<textarea required rows={3} value={versionForm.hts_condition_expression} onChange={(e) => setVersionForm({ ...versionForm, hts_condition_expression: e.target.value })} /></label><label>DrCT Rule Draft<textarea rows={5} placeholder="실행되는 Rule이 아닌 사람이 읽는 Draft입니다." value={versionForm.drct_rule_text ?? ""} onChange={(e) => setVersionForm({ ...versionForm, drct_rule_text: e.target.value })} /></label><label>변경 메모 *<textarea required rows={2} value={versionForm.change_note} onChange={(e) => setVersionForm({ ...versionForm, change_note: e.target.value })} /></label><footer><button type="button" className="btn btn-secondary" onClick={() => setModal(null)}>취소</button><button type="submit" className="btn btn-primary" disabled={saving}>v{(detail?.current_version_no ?? 0) + 1} 생성</button></footer></form> : null}
      {modal === "markers" ? <div className="drct-signal-marker-picker">{markerOptions.length ? markerOptions.map((group) => <fieldset key={group.id}><legend><i style={{ background: group.color }} />{group.name}</legend>{group.markers.map((marker) => <label key={marker.id}><input type="checkbox" checked={checkedMarkerIds.includes(marker.id)} onChange={(e) => setCheckedMarkerIds((ids) => e.target.checked ? [...ids, marker.id] : ids.filter((id) => id !== marker.id))} /><span>{marker.symbol}</span><div><strong>{marker.name}</strong>{marker.description ? <small>{marker.description}</small> : null}</div></label>)}</fieldset>) : <p className="drct-signal-section-empty">연결 가능한 활성 차트마커가 없습니다.</p>}<footer><button type="button" className="btn btn-secondary" onClick={() => setModal(null)}>취소</button><button type="button" className="btn btn-primary" disabled={saving} onClick={() => void submitMarkers()}>연결 저장</button></footer></div> : null}
      {modal === "history" ? <div className="drct-signal-history"><aside>{versions.map((version) => <button key={version.id} type="button" className={viewVersion?.id === version.id ? "is-selected" : ""} onClick={() => setViewVersion(version)}><strong>v{version.version_no} {version.is_current ? <span>CURRENT</span> : null}</strong><small>{formatDate(version.created_at)}</small><p>{version.change_note || "변경 메모 없음"}</p></button>)}</aside>{viewVersion ? <article><h4>v{viewVersion.version_no} 읽기 전용</h4><h5>HTS 참조 조건</h5><pre>{viewVersion.hts_reference_conditions}</pre><h5>HTS 최종 조건식</h5><pre>{viewVersion.hts_condition_expression}</pre><h5>DrCT Structured Rule</h5><pre>{viewVersion.structured_rule ? JSON.stringify(viewVersion.structured_rule.rule, null, 2) : "미구성"}</pre><h5>변경 메모</h5><p>{viewVersion.change_note || "-"}</p></article> : null}</div> : null}
      {modal === "source" && detail ? <div className="drct-hts-source-modal"><section><h4>참조 조건</h4><pre>{detail.current_version.hts_reference_conditions}</pre></section><section><h4>최종 조건식</h4><pre>{detail.current_version.hts_condition_expression}</pre></section></div> : null}
    </section></div> : null}
  </div>;
}

export default SignalResearchTab;
