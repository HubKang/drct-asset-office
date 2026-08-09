import { FormEvent, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, ChevronDown, ChevronUp, Pencil, Plus, Power, X } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import { repositories } from "@/services";
import type { ChartMarker, ChartMarkerGroup, ChartMarkerReviewChart, ChartMarkerReviewEvent } from "@/types/chartMarker";

function ReviewChart({ data, event, loading }: { data: ChartMarkerReviewChart | null; event: ChartMarkerReviewEvent; loading: boolean }) {
  const [hovered, setHovered] = useState<number | null>(null);
  if (loading) return <div className="chart-marker-chart-skeleton" aria-label="차트 로딩 중" />;
  if (!data?.candles.length) return <div className="chart-marker-empty">해당 기간의 가격 데이터가 없습니다.</div>;
  const rows = data.candles, width = 920, height = 450, p = { l: 54, r: 30, t: 42, b: 40 }, volH = 72, priceH = height - p.t - p.b - volH - 30;
  const values = rows.flatMap((row) => [row.low, row.high]).filter((value): value is number => value != null);
  const min = Math.min(...values), max = Math.max(...values), span = Math.max(1, max - min);
  const x = (index: number) => p.l + (index + .5) * (width - p.l - p.r) / rows.length;
  const y = (value: number) => p.t + (max - value) / span * priceH;
  const slot = (width - p.l - p.r) / rows.length, body = Math.max(3, Math.min(11, slot * .55)), maxVol = Math.max(1, ...rows.map((row) => Number(row.volume || 0)));
  const d0 = rows.findIndex((row) => row.trade_date === event.marker_date);
  const maSeries = [{ key: "ma5", color: "#111827" }, { key: "ma10", color: "#ef4444" }, { key: "ma20", color: "#eab308" }, { key: "ma60", color: "#16a34a" }];
  const hover = hovered == null ? null : rows[hovered];
  return <div className="chart-marker-review-chart">
    <div className="chart-marker-ma-legend">{maSeries.map((ma) => <span key={ma.key}><i style={{ background: ma.color }} />{ma.key.toUpperCase()}</span>)}</div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${event.stock_name} ${event.marker_date} 전후 차트`} onMouseLeave={() => setHovered(null)}>
      <rect width={width} height={height} rx="10" fill="#fff" />
      {[0, .25, .5, .75, 1].map((rate) => <line key={rate} x1={p.l} x2={width - p.r} y1={p.t + rate * priceH} y2={p.t + rate * priceH} stroke="#e2e8f0" />)}
      {d0 >= 0 ? <rect x={x(d0) - slot / 2} y={p.t} width={slot} height={priceH + 24 + volH} fill={event.group_color} opacity=".055" /> : null}
      {maSeries.map((ma) => { const points = rows.map((row, index) => row.moving_averages[ma.key] == null ? null : `${x(index)},${y(Number(row.moving_averages[ma.key]))}`).filter(Boolean).join(" "); return points ? <polyline key={ma.key} points={points} fill="none" stroke={ma.color} strokeWidth="1.4" /> : null; })}
      {rows.map((row, index) => { if (row.open == null || row.close == null || row.high == null || row.low == null) return null; const up = row.close >= row.open, color = up ? "#dc2626" : "#2563eb", top = y(Math.max(row.open, row.close)), bottom = y(Math.min(row.open, row.close)), volume = Number(row.volume || 0) / maxVol * volH; return <g key={row.trade_date}><line x1={x(index)} x2={x(index)} y1={y(row.high)} y2={y(row.low)} stroke={color} /><rect x={x(index) - body / 2} y={top} width={body} height={Math.max(2, bottom - top)} fill={up ? "#fff1f2" : "#eff6ff"} stroke={color} /><rect x={x(index) - body / 2} y={p.t + priceH + 24 + volH - volume} width={body} height={volume} fill={up ? "#fecaca" : "#bfdbfe"} /><rect x={x(index) - slot / 2} y={p.t} width={slot} height={priceH + 24 + volH} fill="transparent" onMouseEnter={() => setHovered(index)} onMouseMove={() => setHovered(index)} /></g>; })}
      {d0 >= 0 ? <g pointerEvents="none"><line x1={x(d0)} x2={x(d0)} y1={p.t} y2={p.t + priceH + 24 + volH} stroke={event.group_color} strokeWidth="2" strokeDasharray="5 4" /><circle cx={x(d0)} cy={p.t + 10} r="11" fill={event.group_color} stroke="#fff" strokeWidth="2" /><text x={x(d0)} y={p.t + 14} textAnchor="middle" fill="#fff" fontSize="11">{event.symbol}</text><rect x={x(d0) - 58} y={height - 28} width="116" height="22" rx="6" fill={event.group_color} opacity=".12" /><text x={x(d0)} y={height - 13} textAnchor="middle" fill={event.group_color} fontWeight="700" fontSize="12">D0 · {event.marker_date}</text></g> : null}
      <text x={p.l} y={height - 12} fontSize="11" fill="#64748b">{rows[0].trade_date}</text><text x={width - p.r} y={height - 12} textAnchor="end" fontSize="11" fill="#64748b">{rows[rows.length - 1]?.trade_date}</text>
    </svg>
    {hover ? <div className="chart-marker-chart-tooltip"><strong>{hover.trade_date}</strong><span>시가 <b>{hover.open?.toLocaleString() ?? "-"}</b></span><span>고가 <b>{hover.high?.toLocaleString() ?? "-"}</b></span><span>저가 <b>{hover.low?.toLocaleString() ?? "-"}</b></span><span>종가 <b>{hover.close?.toLocaleString() ?? "-"}</b></span><span>거래량 <b>{hover.volume?.toLocaleString() ?? "-"}</b></span></div> : null}
  </div>;
}

type EditorState = { kind: "group"; group?: ChartMarkerGroup; marker?: never } | { kind: "marker"; marker?: ChartMarker; group?: never } | null;

function CatalogTab({ groups, reload }: { groups: ChartMarkerGroup[]; reload: () => Promise<void> }) {
  const [selected, setSelected] = useState<number | null>(groups[0]?.id ?? null), [editor, setEditor] = useState<EditorState>(null), [saving, setSaving] = useState(false), [error, setError] = useState("");
  const group = groups.find((item) => item.id === selected) ?? groups[0];
  useEffect(() => { if (!group && groups[0]) setSelected(groups[0].id); }, [groups, group]);
  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!editor) return; setSaving(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      if (editor.kind === "group") {
        const current = editor.group, payload = { name: String(form.get("name")), description: String(form.get("description") || ""), color: String(form.get("color")), sort_order: current?.sort_order ?? Math.max(0, ...groups.map((item) => item.sort_order)) + 10, is_active: form.get("is_active") === "on" };
        if (current) await repositories.chartMarkers.updateGroup(current.id, payload); else await repositories.chartMarkers.createGroup(payload);
      } else if (group) {
        const current = editor.marker, payload = { name: String(form.get("name")), description: String(form.get("description") || ""), symbol: String(form.get("symbol") || "◆"), sort_order: current?.sort_order ?? Math.max(0, ...group.markers.map((item) => item.sort_order)) + 10, is_active: form.get("is_active") === "on" };
        if (current) await repositories.chartMarkers.updateMarker(current.id, payload); else await repositories.chartMarkers.createMarker({ ...payload, marker_group_id: group.id });
      }
      setEditor(null); await reload();
    } catch (nextError) { setError(nextError instanceof Error ? nextError.message : "저장하지 못했습니다."); } finally { setSaving(false); }
  };
  const toggleGroup = async () => { if (!group) return; await repositories.chartMarkers.updateGroup(group.id, { is_active: !group.is_active }); await reload(); };
  const toggleMarker = async (marker: ChartMarker) => { await repositories.chartMarkers.updateMarker(marker.id, { is_active: !marker.is_active }); await reload(); };
  const moveMarker = async (marker: ChartMarker, direction: -1 | 1) => {
    if (!group) return;
    const ordered = [...group.markers].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
    const index = ordered.findIndex((item) => item.id === marker.id), targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= ordered.length) return;
    [ordered[index], ordered[targetIndex]] = [ordered[targetIndex], ordered[index]];
    await Promise.all(ordered.map((item, itemIndex) => repositories.chartMarkers.updateMarker(item.id, { sort_order: (itemIndex + 1) * 10 })));
    await reload();
  };
  return <>
    <div className="chart-marker-section-intro"><div><h2>마커그룹</h2><p>차트에서 사용할 관찰 기준을 그룹과 마커로 관리합니다.</p></div><button className="btn btn-primary" type="button" onClick={() => setEditor({ kind: "group" })}><Plus size={16} /> 새 그룹</button></div>
    <div className="chart-marker-master-detail"><aside className="panel chart-marker-group-panel"><div className="chart-marker-panel-title"><h3>마커그룹</h3><span>{groups.length}개</span></div><div className="chart-marker-group-list">{groups.map((item) => <button type="button" key={item.id} className={item.id === group?.id ? "active" : ""} onClick={() => setSelected(item.id)}><i style={{ background: item.color }} /><span><strong>{item.name}</strong><small>{item.is_active ? "활성" : "비활성"}</small></span><b>{item.markers.length}</b></button>)}</div></aside>
      <main className="panel chart-marker-detail-panel">{group ? <><header className="chart-marker-detail-header"><div><div className="chart-marker-group-heading"><i style={{ background: group.color }} /><h2>{group.name}</h2><span className={`chart-marker-status ${group.is_active ? "active" : ""}`}>{group.is_active ? "활성" : "비활성"}</span></div><p>{group.description || "등록된 그룹 설명이 없습니다."}</p></div><div><button className="btn btn-secondary" type="button" onClick={() => setEditor({ kind: "group", group })}><Pencil size={15} /> 수정</button><button className="btn btn-secondary" type="button" onClick={() => void toggleGroup()}><Power size={15} /> {group.is_active ? "비활성" : "활성화"}</button></div></header><div className="chart-marker-detail-toolbar"><div><h3>등록 마커</h3><span>{group.markers.length}개</span></div><button className="btn btn-primary" type="button" onClick={() => setEditor({ kind: "marker" })}><Plus size={16} /> 마커 추가</button></div><div className="chart-marker-card-list">{group.markers.length ? group.markers.map((marker, index) => <article key={marker.id} className={!marker.is_active ? "inactive" : ""}><div className="chart-marker-symbol" style={{ color: group.color, background: `${group.color}12` }}>{marker.symbol}</div><div className="chart-marker-card-copy"><strong>{marker.name}</strong><p>{marker.description || "등록된 설명이 없습니다."}</p></div><span className={`chart-marker-status ${marker.is_active ? "active" : ""}`}>{marker.is_active ? "활성" : "비활성"}</span><div className="chart-marker-order-actions"><button title="위로 이동" disabled={index === 0} onClick={() => void moveMarker(marker, -1)}><ChevronUp size={16} /></button><button title="아래로 이동" disabled={index === group.markers.length - 1} onClick={() => void moveMarker(marker, 1)}><ChevronDown size={16} /></button></div><div className="chart-marker-card-actions"><button onClick={() => setEditor({ kind: "marker", marker })}>수정</button><button className={!marker.is_active ? "activate" : "danger"} onClick={() => void toggleMarker(marker)}>{marker.is_active ? "비활성" : "활성화"}</button></div></article>) : <div className="chart-marker-empty compact">등록된 마커가 없습니다.<br />마커 추가를 눌러 관찰 기준을 만들어 주세요.</div>}</div></> : <div className="chart-marker-empty">마커그룹을 먼저 등록해 주세요.</div>}</main>
    </div>
    {editor ? <div className="chart-marker-editor-backdrop" onMouseDown={() => setEditor(null)}><form className="chart-marker-editor" onSubmit={save} onMouseDown={(event) => event.stopPropagation()}><header><div><h3>{editor.kind === "group" ? `마커그룹 ${editor.group ? "수정" : "등록"}` : `차트마커 ${editor.marker ? "수정" : "등록"}`}</h3><p>{editor.kind === "group" ? "관찰 기준을 묶는 상위 그룹입니다." : `${group?.name || "선택 그룹"}에 사용할 마커입니다.`}</p></div><button type="button" onClick={() => setEditor(null)}><X size={20} /></button></header><label>{editor.kind === "group" ? "그룹명" : "마커명"}<input className="input-control" name="name" required autoFocus defaultValue={editor.kind === "group" ? editor.group?.name : editor.marker?.name} /></label>{editor.kind === "group" ? <label>대표 색상<div className="chart-marker-color-input"><input type="color" name="color" defaultValue={editor.group?.color ?? "#64748b"} /><span>차트에서 마커를 구분할 때 사용합니다.</span></div></label> : <label>표시 심볼<input className="input-control chart-marker-symbol-input" name="symbol" maxLength={12} defaultValue={editor.marker?.symbol ?? "◆"} /></label>}<label>설명<textarea className="input-control" name="description" rows={3} defaultValue={editor.kind === "group" ? editor.group?.description ?? "" : editor.marker?.description ?? ""} /></label><label className="chart-marker-active-check"><input name="is_active" type="checkbox" defaultChecked={editor.kind === "group" ? editor.group?.is_active ?? true : editor.marker?.is_active ?? true} /> 활성 상태로 사용</label>{error ? <p className="inline-result inline-error">{error}</p> : null}<footer><button className="btn btn-secondary" type="button" onClick={() => setEditor(null)}>취소</button><button className="btn btn-primary" disabled={saving}>{saving ? "저장 중…" : editor.group || editor.marker ? "수정" : "등록"}</button></footer></form></div> : null}
  </>;
}

export default function ChartMarkerReviewPage() {
  const [tab, setTab] = useState<"catalog" | "review">("catalog"), [groups, setGroups] = useState<ChartMarkerGroup[]>([]), [groupId, setGroupId] = useState<number | null>(null), [markerId, setMarkerId] = useState<number | null>(null), [events, setEvents] = useState<ChartMarkerReviewEvent[]>([]), [selected, setSelected] = useState<ChartMarkerReviewEvent | null>(null), [chart, setChart] = useState<ChartMarkerReviewChart | null>(null), [chartLoading, setChartLoading] = useState(false), [error, setError] = useState("");
  const reload = async () => { try { setGroups((await repositories.chartMarkers.catalog()).items); } catch (nextError) { setError(nextError instanceof Error ? nextError.message : "마커를 불러오지 못했습니다."); } };
  useEffect(() => { void reload(); }, []);
  const activeGroups = groups.filter((item) => item.is_active), group = activeGroups.find((item) => item.id === groupId) ?? activeGroups[0], markers = group?.markers.filter((item) => item.is_active) ?? [];
  useEffect(() => { if (group && group.id !== groupId) setGroupId(group.id); }, [group, groupId]);
  useEffect(() => { if (!markers.some((item) => item.id === markerId)) setMarkerId(markers[0]?.id ?? null); }, [groupId, groups]);
  useEffect(() => { if (tab !== "review" || !markerId) { setEvents([]); setSelected(null); return; } repositories.chartMarkers.reviewEvents(markerId).then((response) => { setEvents(response.items); setSelected(response.items[0] ?? null); }).catch((nextError) => setError(nextError.message)); }, [tab, markerId]);
  useEffect(() => { if (!selected) { setChart(null); return; } setChartLoading(true); repositories.chartMarkers.reviewChart(selected.stock_id, selected.marker_date).then(setChart).catch((nextError) => setError(nextError.message)).finally(() => setChartLoading(false)); }, [selected?.id]);
  const grouped = useMemo(() => Array.from(events.reduce((map, item) => { const rows = map.get(item.stock_id) ?? []; rows.push(item); map.set(item.stock_id, rows); return map; }, new Map<number, ChartMarkerReviewEvent[]>()).values()), [events]);
  const selectedIndex = selected ? events.findIndex((item) => item.id === selected.id) : -1;
  const moveSelection = (offset: number) => { const next = events[selectedIndex + offset]; if (next) setSelected(next); };
  const deleteReviewEvent = async (item: ChartMarkerReviewEvent) => {
    if (!window.confirm(`${item.stock_name} · ${item.marker_date} 마커 기록을 삭제하시겠습니까?`)) return;
    try {
      await repositories.chartMarkers.deleteEvent(item.id);
      const remaining = events.filter((event) => event.id !== item.id);
      setEvents(remaining);
      if (selected?.id === item.id) {
        const deletedIndex = events.findIndex((event) => event.id === item.id);
        setSelected(remaining[Math.min(deletedIndex, remaining.length - 1)] ?? null);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "마커 기록을 삭제하지 못했습니다.");
    }
  };
  return <div className="chart-marker-page space-y-4">
    <PageHeader title="매매훈련 차트마커 복기" description="훈련 차트에서 발견한 현상을 기록하고 같은 유형의 실제 사례를 반복 복기합니다." />
    <div className="chart-marker-tabs">
      <button className={tab === "catalog" ? "active" : ""} onClick={() => setTab("catalog")}>마커그룹</button>
      <button className={tab === "review" ? "active" : ""} onClick={() => setTab("review")}>차트마커 복기</button>
    </div>
    {error ? <div className="inline-result inline-error">{error}</div> : null}
    {tab === "catalog" ? <CatalogTab groups={groups} reload={reload} /> : <>
      <div className="chart-marker-review-intro"><div><h2>차트마커 복기</h2><p>같은 마커가 기록된 사례를 종목별로 비교합니다.</p></div><strong>사례 {events.length}건</strong></div>
      <div className="chart-marker-filters">
        <label>마커그룹<select className="input-control" value={group?.id ?? ""} onChange={(event) => setGroupId(Number(event.target.value))}>{activeGroups.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>차트마커<select className="input-control" value={markerId ?? ""} onChange={(event) => setMarkerId(Number(event.target.value))}>{markers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      </div>
      {!groups.length ? <div className="chart-marker-empty">등록된 차트마커가 없습니다.<br />마커그룹 탭에서 먼저 마커를 등록해 주세요.</div> : !events.length ? <div className="chart-marker-empty">이 마커로 기록된 차트 사례가 없습니다.<br />종목매매훈련 차트에서 캔들을 우클릭하여 마커를 기록해 주세요.</div> : <div className="chart-marker-review-grid">
        <aside className="panel chart-marker-case-panel">
          <header><h3>관련 종목 / 캔들일자</h3><span>{events.length}건</span></header>
          <div className="chart-marker-case-scroll">{grouped.map((rows) => <div className="chart-marker-stock" key={rows[0].stock_id}>
            <div><strong>{rows[0].stock_name}</strong><span>{rows.length}건</span></div>
            {rows.map((item) => <div className={`chart-marker-case-row ${selected?.id === item.id ? "active" : ""}`} key={item.id}>
              <button className="chart-marker-case-date" onClick={() => setSelected(item)}><i />{item.marker_date}</button>
              <button className="chart-marker-case-delete" title={`${item.marker_date} 마커 삭제`} onClick={() => void deleteReviewEvent(item)}>삭제</button>
            </div>)}
          </div>)}</div>
        </aside>
        {selected ? <main className="panel chart-marker-review-detail">
          <header><div><h2>{selected.stock_name}</h2><time>{selected.marker_date}</time><p><span style={{ color: selected.group_color, background: `${selected.group_color}12`, borderColor: `${selected.group_color}40` }}>{selected.group_name}</span><b style={{ color: selected.group_color }}>{selected.symbol}</b>{selected.marker_name}</p></div><div className="chart-marker-review-nav"><button className="btn btn-secondary" disabled={selectedIndex <= 0} onClick={() => moveSelection(-1)}><ArrowLeft size={15} /> 이전 사례</button><strong>{selectedIndex + 1} / {events.length}</strong><button className="btn btn-secondary" disabled={selectedIndex >= events.length - 1} onClick={() => moveSelection(1)}>다음 사례 <ArrowRight size={15} /></button></div></header>
          <div className="chart-marker-chart-heading"><div><h3>마커 기준 ±1개월 차트</h3><p>기준일 전·후 각 20거래일</p></div><span>D0 {selected.marker_date}</span></div>
          <ReviewChart data={chart} event={selected} loading={chartLoading} />
          <section className="chart-marker-memo"><strong>메모</strong><p>{selected.memo || "등록된 메모가 없습니다."}</p></section>
        </main> : null}
      </div>}
    </>}
  </div>;
}
