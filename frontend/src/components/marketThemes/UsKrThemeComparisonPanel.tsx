import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import SectionCard from "@/components/common/SectionCard";
import UsKrLeadAnalysisPanel from "@/components/marketThemes/UsKrLeadAnalysisPanel";
import UsKrTodayObservationPanel, { type TodayDirection, type TodayMetric } from "@/components/marketThemes/UsKrTodayObservationPanel";
import { repositories } from "@/services";
import type { ThemeLinkOption, UsKrThemeLink, UsKrThemeLinkSummary } from "@/types/usKrThemeLink";

type Props = { section: "link" | "analysis" | "watch"; onSummaryChange: (value: UsKrThemeLinkSummary) => void };
type PendingPair = { us: ThemeLinkOption; kr: ThemeLinkOption } | null;
const EMPTY = { us_active_themes: 0, kr_active_themes: 0, linked_themes: 0, unlinked_us_themes: 0, unlinked_kr_themes: 0 };
const ALL_GROUPS = "__all__";

const sortThemes = (rows: ThemeLinkOption[]) => [...rows].sort((a, b) =>
  a.group_name.localeCompare(b.group_name, "ko") || a.theme_name.localeCompare(b.theme_name, "ko"),
);

export default function UsKrThemeComparisonPanel({ section, onSummaryChange }: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [links, setLinks] = useState<UsKrThemeLink[]>([]);
  const [usThemes, setUsThemes] = useState<ThemeLinkOption[]>([]);
  const [krThemes, setKrThemes] = useState<ThemeLinkOption[]>([]);
  const [selectedUsId, setSelectedUsId] = useState<number | null>(null);
  const [dragUsId, setDragUsId] = useState<number | null>(null);
  const [dragOverKrId, setDragOverKrId] = useState<number | null>(null);
  const [pendingPair, setPendingPair] = useState<PendingPair>(null);
  const [connectingUsId, setConnectingUsId] = useState<number | null>(null);
  const [editing, setEditing] = useState<UsKrThemeLink | null>(null);
  const [editUsId, setEditUsId] = useState(0);
  const [editKrId, setEditKrId] = useState(0);
  const [editMemo, setEditMemo] = useState("");
  const [usGroup, setUsGroup] = useState(ALL_GROUPS);
  const [krGroup, setKrGroup] = useState(ALL_GROUPS);
  const [usKeyword, setUsKeyword] = useState("");
  const [krKeyword, setKrKeyword] = useState("");
  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(true);
  const usPoolRef = useRef<HTMLDivElement>(null);
  const krPoolRef = useRef<HTMLDivElement>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await repositories.usKrThemeLinks.overview();
      setLinks(data.links);
      setUsThemes(data.us_themes);
      setKrThemes(data.kr_themes);
      onSummaryChange(data.summary);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "한미 테마 연결 정보를 불러오지 못했습니다.");
      onSummaryChange(EMPTY);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!success) return undefined;
    const timer = window.setTimeout(() => setSuccess(""), 3500);
    return () => window.clearTimeout(timer);
  }, [success]);

  const unlinkedUs = useMemo(() => sortThemes(usThemes.filter((row) => row.active === 1 && !row.linked)), [usThemes]);
  const unlinkedKr = useMemo(() => sortThemes(krThemes.filter((row) => row.active === 1 && !row.linked)), [krThemes]);
  const usGroups = useMemo(() => [...new Set(unlinkedUs.map((row) => row.group_name))].sort((a, b) => a.localeCompare(b, "ko")), [unlinkedUs]);
  const krGroups = useMemo(() => [...new Set(unlinkedKr.map((row) => row.group_name))].sort((a, b) => a.localeCompare(b, "ko")), [unlinkedKr]);
  const visibleUs = useMemo(() => {
    const term = usKeyword.trim().toLowerCase();
    return unlinkedUs.filter((row) => (usGroup === ALL_GROUPS || row.group_name === usGroup)
      && (!term || `${row.group_name} ${row.theme_name}`.toLowerCase().includes(term)));
  }, [unlinkedUs, usGroup, usKeyword]);
  const visibleKr = useMemo(() => {
    const term = krKeyword.trim().toLowerCase();
    return unlinkedKr.filter((row) => (krGroup === ALL_GROUPS || row.group_name === krGroup)
      && (!term || `${row.group_name} ${row.theme_name}`.toLowerCase().includes(term)));
  }, [unlinkedKr, krGroup, krKeyword]);
  const filtered = useMemo(() => links.filter((row) => {
    const text = `${row.us_group_name} ${row.us_theme_name} ${row.kr_group_name} ${row.kr_theme_name} ${row.memo || ""}`.toLowerCase();
    return (!keyword.trim() || text.includes(keyword.trim().toLowerCase()))
      && (statusFilter === "all" || (statusFilter === "active" ? row.active === 1 : row.active === 0));
  }), [links, keyword, statusFilter]);

  const configuredWindow = [0, 60, 120, 250].includes(Number(searchParams.get("window"))) ? Number(searchParams.get("window")) : 120;
  const configuredMetric = searchParams.get("metric") === "simple_return" ? "simple_return" : "theme_strength";
  const configuredDirection = (["ALL", "UP", "DOWN"].includes(searchParams.get("direction") || "") ? searchParams.get("direction") : "ALL") as TodayDirection;
  const configuredLinkId = Number(searchParams.get("link_id")) || 0;
  const updateObservationConfig = (window: number, metric: TodayMetric, direction: TodayDirection) => {
    if (String(window) === searchParams.get("window") && metric === searchParams.get("metric") && direction === searchParams.get("direction")) return;
    const next = new URLSearchParams(searchParams); next.set("window", String(window)); next.set("metric", metric); next.set("direction", direction); setSearchParams(next, { replace: true });
  };
  const openAnalysis = (linkId: number, window: number, metric: TodayMetric, direction: TodayDirection) => {
    const next = new URLSearchParams(searchParams); next.set("section", "analysis"); next.set("link_id", String(linkId)); next.set("window", String(window)); next.set("metric", metric); next.set("direction", direction); setSearchParams(next, { replace: true });
  };
  if (section === "analysis") return <UsKrLeadAnalysisPanel links={links} overviewLoading={loading} initialLinkId={configuredLinkId} initialWindow={configuredWindow} initialMetric={configuredMetric} />;
  if (section === "watch") return <UsKrTodayObservationPanel initialWindow={configuredWindow} initialMetric={configuredMetric} initialDirection={configuredDirection} onConfigChange={updateObservationConfig} onOpenAnalysis={openAnalysis} />;

  const createLink = async (us: ThemeLinkOption, kr: ThemeLinkOption) => {
    if (connectingUsId !== null) return;
    setConnectingUsId(us.id);
    setError("");
    try {
      await repositories.usKrThemeLinks.create({ us_theme_id: us.id, kr_theme_id: kr.id, memo: null });
      setSelectedUsId(null);
      setPendingPair(null);
      setSuccess(`${us.theme_name} ↔ ${kr.theme_name} 테마를 연결했습니다.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "테마 연결에 실패했습니다.");
    } finally {
      setConnectingUsId(null);
      setDragUsId(null);
      setDragOverKrId(null);
    }
  };
  const beginEdit = (row: UsKrThemeLink) => {
    setEditing(row);
    setEditUsId(row.us_theme_id);
    setEditKrId(row.kr_theme_id);
    setEditMemo(row.memo || "");
  };
  const saveEdit = async () => {
    if (!editing || !editUsId || !editKrId) return;
    setError("");
    try {
      await repositories.usKrThemeLinks.update(editing.id, { us_theme_id: editUsId, kr_theme_id: editKrId, memo: editMemo.trim() || null });
      setSuccess("테마 연결 정보를 수정했습니다.");
      setEditing(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "테마 연결을 수정하지 못했습니다.");
    }
  };
  const remove = async (row: UsKrThemeLink) => {
    if (!window.confirm(`${row.us_theme_name} ↔ ${row.kr_theme_name} 연결을 해제할까요?`)) return;
    try {
      await repositories.usKrThemeLinks.delete(row.id);
      if (editing?.id === row.id) setEditing(null);
      setSuccess(`${row.us_theme_name} ↔ ${row.kr_theme_name} 연결을 해제했습니다.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "테마 연결을 해제하지 못했습니다.");
    }
  };
  const selectedUs = unlinkedUs.find((row) => row.id === selectedUsId) || null;
  const isUsPoolEmpty = unlinkedUs.length === 0;
  const isKrPoolEmpty = unlinkedKr.length === 0;

  return <div className="space-y-4 us-kr-theme-comparison">
    <SectionCard title="한미 테마 연결" className="us-kr-link-board-card">
      <div className="us-kr-board-heading">
        <div><p>미국 테마를 국내 테마로 끌어 놓아 1:1로 연결합니다.</p><strong>US D-1 → KR D0</strong></div>
        {selectedUs ? <p className="us-kr-selection-guide"><strong>{selectedUs.theme_name}</strong> 선택됨 · 연결할 국내 테마를 선택하세요.</p> : null}
      </div>
      <div className={`us-kr-link-board${dragUsId ? " is-dragging" : ""}`}>
        <section className="us-kr-theme-pool us-pool" aria-labelledby="us-pool-title">
          <header><h3 id="us-pool-title">미국 US <span>· 미연결 {unlinkedUs.length}</span></h3><span>Drag source</span></header>
          <div className="us-kr-pool-filters">
            <select className="select-control" value={usGroup} onChange={(e) => setUsGroup(e.target.value)} aria-label="미국 테마그룹 필터"><option value={ALL_GROUPS}>미국 테마그룹 전체</option>{usGroups.map((group) => <option key={group} value={group}>{group}</option>)}</select>
            <input className="input-control" value={usKeyword} onChange={(e) => setUsKeyword(e.target.value)} placeholder="미국 테마 검색" aria-label="미국 테마 검색" />
          </div>
          <div className="us-kr-theme-card-list" ref={usPoolRef}>
            {visibleUs.map((row) => <div key={row.id} className={`us-kr-theme-card us-card${selectedUsId === row.id ? " is-selected" : ""}${dragUsId === row.id ? " is-drag-source" : ""}${connectingUsId === row.id ? " is-saving" : ""}`} role="button" tabIndex={0} draggable={connectingUsId === null} aria-pressed={selectedUsId === row.id} onClick={() => setSelectedUsId((current) => current === row.id ? null : row.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedUsId((current) => current === row.id ? null : row.id); } }} onDragStart={(e) => { e.dataTransfer.effectAllowed = "link"; e.dataTransfer.setData("text/plain", String(row.id)); setDragUsId(row.id); setPendingPair(null); }} onDragEnd={() => { setDragUsId(null); setDragOverKrId(null); }}><span><strong>{row.theme_name}</strong><small>{row.group_name}</small></span><span className="us-kr-drag-handle" aria-hidden="true">⋮⋮</span></div>)}
            {!loading && visibleUs.length === 0 ? <p className="us-kr-pool-empty">{isUsPoolEmpty ? "모든 활성 미국 테마가 연결되었습니다." : "조건에 맞는 미연결 테마가 없습니다."}</p> : null}
          </div>
        </section>
        <div className="us-kr-board-arrow" aria-hidden="true"><span>US → KR</span><b>→</b></div>
        <section className="us-kr-theme-pool kr-pool" aria-labelledby="kr-pool-title">
          <header><h3 id="kr-pool-title">국내 KRX <span>· 미연결 {unlinkedKr.length}</span></h3><span>Drop target</span></header>
          <div className="us-kr-pool-filters">
            <select className="select-control" value={krGroup} onChange={(e) => setKrGroup(e.target.value)} aria-label="국내 테마그룹 필터"><option value={ALL_GROUPS}>국내 테마그룹 전체</option>{krGroups.map((group) => <option key={group} value={group}>{group}</option>)}</select>
            <input className="input-control" value={krKeyword} onChange={(e) => setKrKeyword(e.target.value)} placeholder="국내 테마 검색" aria-label="국내 테마 검색" />
          </div>
          <div className="us-kr-theme-card-list" ref={krPoolRef}>
            {visibleKr.map((row) => <div key={row.id} className={`us-kr-theme-card kr-card${dragUsId ? " is-drop-ready" : ""}${dragOverKrId === row.id ? " is-drop-target" : ""}`} role="button" tabIndex={0} onClick={() => { if (selectedUs) setPendingPair({ us: selectedUs, kr: row }); }} onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && selectedUs) { e.preventDefault(); setPendingPair({ us: selectedUs, kr: row }); } }} onDragEnter={(e) => { if (dragUsId) { e.preventDefault(); setDragOverKrId(row.id); } }} onDragOver={(e) => { if (dragUsId) { e.preventDefault(); e.dataTransfer.dropEffect = "link"; } }} onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOverKrId(null); }} onDrop={(e) => { e.preventDefault(); const id = Number(e.dataTransfer.getData("text/plain")) || dragUsId; const us = unlinkedUs.find((item) => item.id === id); if (us) void createLink(us, row); }}><span><strong>{row.theme_name}</strong><small>{row.group_name}</small></span>{dragOverKrId === row.id && dragUsId ? <em>{unlinkedUs.find((item) => item.id === dragUsId)?.theme_name} → 연결</em> : null}</div>)}
            {!loading && visibleKr.length === 0 ? <p className="us-kr-pool-empty">{isKrPoolEmpty ? "모든 활성 국내 테마가 연결되었습니다." : "조건에 맞는 미연결 테마가 없습니다."}</p> : null}
          </div>
        </section>
      </div>
      {pendingPair ? <div className="us-kr-click-confirm" role="dialog" aria-label="테마 연결 확인"><p><strong>{pendingPair.us.theme_name}</strong><span>→</span><strong>{pendingPair.kr.theme_name}</strong></p><div><button className="secondary-button" type="button" onClick={() => setPendingPair(null)}>취소</button><button className="primary-button" type="button" disabled={connectingUsId !== null} onClick={() => void createLink(pendingPair.us, pendingPair.kr)}>연결</button></div></div> : null}
      {success ? <p className="us-kr-success-message" role="status">{success}</p> : null}
      {error ? <p className="form-error-message" role="alert">{error}</p> : null}
    </SectionCard>
    <SectionCard title={`연결된 테마 · ${filtered.length}`} className="us-kr-linked-list-card">
      <div className="us-kr-link-filters"><select className="select-control" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="all">상태 전체</option><option value="active">연결</option><option value="inactive">비활성</option></select><input className="input-control" value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="테마명 또는 메모 검색" /><button className="secondary-button" type="button" onClick={() => { setKeyword(""); setStatusFilter("all"); }}>초기화</button></div>
      <div className="table-scroll us-kr-link-table-scroll"><table className="data-table us-kr-link-table"><colgroup><col className="us-kr-link-col-status" /><col className="us-kr-link-col-theme" /><col className="us-kr-link-col-arrow" /><col className="us-kr-link-col-theme" /><col className="us-kr-link-col-memo" /><col className="us-kr-link-col-actions" /></colgroup><thead><tr><th>상태</th><th>미국 테마</th><th className="us-kr-table-arrow" aria-label="연결">연결</th><th>국내 테마</th><th>메모</th><th className="us-kr-link-actions-heading">작업</th></tr></thead><tbody>
        {filtered.map((row) => <tr key={row.id}><td><span className="status-badge active">연결</span></td><td><small>{row.us_group_name}</small><strong>{row.us_theme_name}</strong></td><td className="us-kr-table-arrow">→</td><td><small>{row.kr_group_name}</small><strong>{row.kr_theme_name}</strong></td><td className="us-kr-link-memo">{row.memo || "-"}</td><td className="us-kr-link-actions"><div><button className="secondary-button" type="button" onClick={() => beginEdit(row)}>수정</button><button className="danger-button" type="button" onClick={() => void remove(row)}>연결 해제</button></div></td></tr>)}
        {!loading && filtered.length === 0 ? <tr><td colSpan={6} className="empty-table-cell">등록된 연결이 없습니다.</td></tr> : null}
      </tbody></table></div>
    </SectionCard>
    {editing ? <div className="modal-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) setEditing(null); }}><section className="us-kr-edit-modal" role="dialog" aria-modal="true" aria-labelledby="us-kr-edit-title"><header><div><h2 id="us-kr-edit-title">한미 테마 연결 수정</h2><p>연결 대상과 관찰 메모를 수정합니다.</p></div><button type="button" aria-label="닫기" onClick={() => setEditing(null)}>×</button></header><div className="us-kr-edit-fields"><label><span>미국 테마</span><select className="select-control" value={editUsId} onChange={(e) => setEditUsId(Number(e.target.value))}>{usThemes.filter((row) => !row.linked || row.id === editing.us_theme_id).map((row) => <option key={row.id} value={row.id}>{row.group_name} · {row.theme_name}</option>)}</select></label><div className="us-kr-edit-arrow" aria-hidden="true">→</div><label><span>국내 테마</span><select className="select-control" value={editKrId} onChange={(e) => setEditKrId(Number(e.target.value))}>{krThemes.filter((row) => !row.linked || row.id === editing.kr_theme_id).map((row) => <option key={row.id} value={row.id}>{row.group_name} · {row.theme_name}</option>)}</select></label><label className="us-kr-edit-memo"><span>메모</span><textarea className="input-control" value={editMemo} maxLength={500} onChange={(e) => setEditMemo(e.target.value)} placeholder="연결 근거 또는 관찰 메모" /></label></div><footer><button className="secondary-button" type="button" onClick={() => setEditing(null)}>취소</button><button className="primary-button" type="button" onClick={() => void saveEdit()}>저장</button></footer></section></div> : null}
  </div>;
}
