import { type CSSProperties, FormEvent, type KeyboardEvent as ReactKeyboardEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, ChevronDown, ChevronUp, ExternalLink, Pencil, Plus, Power, Search, X } from "lucide-react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import { repositories } from "@/services";
import type { ChartMarker, ChartMarkerEvent, ChartMarkerGroup, ChartMarkerKnowledgeItem, ChartMarkerReviewChart, ChartMarkerReviewEvent, ChartMarkerReviewResult } from "@/types/chartMarker";
import type { KmsKnowledgeItem, KmsSettingItem } from "@/types/kms";

const REVIEW_WINDOWS = [
  { key: "40.D0.40", before: 40, after: 40, title: "마커 이전 40봉 · 이후 40봉" },
  { key: "60.D0.20", before: 60, after: 20, title: "마커 이전 60봉 · 이후 20봉" },
  { key: "70.D0.10", before: 70, after: 10, title: "마커 이전 70봉 · 이후 10봉" },
] as const;
type ReviewWindowKey = typeof REVIEW_WINDOWS[number]["key"];

export function normalizeReviewChart(data: ChartMarkerReviewChart, before: number, after: number): ChartMarkerReviewChart {
  const markerIndex = data.marker_index != null && data.candles[data.marker_index]?.trade_date === data.marker_date
    ? data.marker_index
    : data.candles.findIndex((row) => row.trade_date === data.marker_date);
  if (markerIndex < 0) return { ...data, marker_index: null, total_candles: 0, available_before: 0, available_after: 0, requested_before: before, requested_after: after, candles: [] };
  const start = Math.max(0, markerIndex - before);
  const end = Math.min(data.candles.length, markerIndex + after + 1);
  const candles = data.candles.slice(start, end);
  const normalizedMarkerIndex = markerIndex - start;
  return {
    ...data,
    marker_index: normalizedMarkerIndex,
    total_candles: candles.length,
    available_before: normalizedMarkerIndex,
    available_after: Math.max(0, candles.length - normalizedMarkerIndex - 1),
    requested_before: before,
    requested_after: after,
    candles,
  };
}

export function ReviewChart({ data, reviewEvent, loading, markerEvents, showD0Marker, onContextMenu }: {
  data: ChartMarkerReviewChart | null;
  reviewEvent: ChartMarkerReviewEvent;
  loading: boolean;
  markerEvents: ChartMarkerEvent[];
  showD0Marker: boolean;
  onContextMenu: (date: string, x: number, y: number) => void;
}) {
  const [hovered, setHovered] = useState<number | null>(null);
  if (loading) return <div className="chart-marker-chart-skeleton" aria-label="차트 로딩 중" />;
  if (!data?.candles.length) return <div className="chart-marker-empty">{data?.marker_index == null ? "마커 기준일의 가격 데이터를 찾을 수 없습니다." : "표시할 가격 데이터가 없습니다."}</div>;
  const rows = data.candles;
  const d0 = data.marker_index != null && rows[data.marker_index]?.trade_date === data.marker_date
    ? data.marker_index
    : rows.findIndex((row) => row.trade_date === data.marker_date);
  if (d0 < 0) return <div className="chart-marker-empty">마커 기준일의 가격 데이터를 찾을 수 없습니다.</div>;
  const width = 920, height = 450, p = { l: 54, r: 30, t: 42, b: 40 }, volH = 72, priceH = height - p.t - p.b - volH - 30;
  const values = rows.flatMap((row) => [row.low, row.high]).filter((value): value is number => value != null);
  const min = Math.min(...values), max = Math.max(...values), span = Math.max(1, max - min);
  const slotCount = Math.max(1, rows.length);
  const x = (index: number) => p.l + (index + .5) * (width - p.l - p.r) / slotCount;
  const y = (value: number) => p.t + (max - value) / span * priceH;
  const slot = (width - p.l - p.r) / slotCount, body = Math.max(3, Math.min(11, slot * .55)), maxVol = Math.max(1, ...rows.map((row) => Number(row.volume || 0)));
  const maSeries = [{ key: "ma5", color: "#111827" }, { key: "ma10", color: "#ef4444" }, { key: "ma20", color: "#eab308" }, { key: "ma60", color: "#16a34a" }];
  const hover = hovered == null ? null : rows[hovered];
  const previousClose = hovered != null && hovered > 0 ? rows[hovered - 1]?.close : null;
  const closeChangeRate = hover?.close != null && previousClose != null && previousClose !== 0
    ? (hover.close - previousClose) / previousClose * 100
    : null;
  const eventsByDate = markerEvents.reduce((map, markerEvent) => {
    const current = map.get(markerEvent.marker_date) ?? [];
    current.push(markerEvent);
    map.set(markerEvent.marker_date, current);
    return map;
  }, new Map<string, ChartMarkerEvent[]>());
  return <div className="chart-marker-review-chart">
    <div className="chart-marker-ma-legend">{maSeries.map((ma) => <span key={ma.key}><i style={{ background: ma.color }} />{ma.key.toUpperCase()}</span>)}</div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${reviewEvent.stock_name} ${data.marker_date} 전후 차트`} onMouseLeave={() => setHovered(null)}>
      <rect width={width} height={height} rx="10" fill="#fff" />
      {[0, .25, .5, .75, 1].map((rate) => <line key={rate} x1={p.l} x2={width - p.r} y1={p.t + rate * priceH} y2={p.t + rate * priceH} stroke="#e2e8f0" />)}
      {showD0Marker && d0 >= 0 ? <rect x={x(d0) - slot / 2} y={p.t} width={slot} height={priceH + 24 + volH} fill={reviewEvent.group_color} opacity=".055" /> : null}
      {maSeries.map((ma) => { const points = rows.map((row, index) => row.moving_averages[ma.key] == null ? null : `${x(index)},${y(Number(row.moving_averages[ma.key]))}`).filter(Boolean).join(" "); return points ? <polyline key={ma.key} points={points} fill="none" stroke={ma.color} strokeWidth="1.4" /> : null; })}
      {rows.map((row, index) => { if (row.open == null || row.close == null || row.high == null || row.low == null) return null; const up = row.close >= row.open, color = up ? "#dc2626" : "#2563eb", top = y(Math.max(row.open, row.close)), bottom = y(Math.min(row.open, row.close)), volume = Number(row.volume || 0) / maxVol * volH; return <g key={row.trade_date}><line x1={x(index)} x2={x(index)} y1={y(row.high)} y2={y(row.low)} stroke={color} /><rect x={x(index) - body / 2} y={top} width={body} height={Math.max(2, bottom - top)} fill={up ? "#fff1f2" : "#eff6ff"} stroke={color} /><rect x={x(index) - body / 2} y={p.t + priceH + 24 + volH - volume} width={body} height={volume} fill={up ? "#fecaca" : "#bfdbfe"} /><rect x={x(index) - slot / 2} y={p.t} width={slot} height={priceH + 24 + volH} fill="transparent" onMouseEnter={() => setHovered(index)} onMouseMove={() => setHovered(index)} onContextMenu={(mouseEvent) => { mouseEvent.preventDefault(); setHovered(null); onContextMenu(row.trade_date, mouseEvent.clientX, mouseEvent.clientY); }} /></g>; })}
      {rows.flatMap((row, index) => (eventsByDate.get(row.trade_date) ?? []).filter((markerEvent) => showD0Marker || markerEvent.id !== reviewEvent.id).map((markerEvent, markerIndex) => {
        const isD0 = markerEvent.id === reviewEvent.id;
        const markerY = p.t + 12 + markerIndex * 19;
        return <g key={`marker-${markerEvent.id}`} pointerEvents="none"><circle cx={x(index)} cy={markerY} r={isD0 ? 10 : 8} fill={markerEvent.group_color} stroke="#fff" strokeWidth={isD0 ? 3 : 2} /><text x={x(index)} y={markerY + 3.5} textAnchor="middle" fill="#fff" fontSize={isD0 ? 10 : 8} fontWeight="800">{markerEvent.symbol}</text></g>;
      }))}
      {showD0Marker && d0 >= 0 ? <g pointerEvents="none"><line x1={x(d0)} x2={x(d0)} y1={p.t} y2={p.t + priceH + 24 + volH} stroke={reviewEvent.group_color} strokeWidth="2" strokeDasharray="5 4" /><rect x={x(d0) - 58} y={height - 28} width="116" height="22" rx="6" fill={reviewEvent.group_color} opacity=".12" /><text x={x(d0)} y={height - 13} textAnchor="middle" fill={reviewEvent.group_color} fontWeight="700" fontSize="12">D0 · {data.marker_date}</text></g> : null}
      <text x={p.l} y={height - 12} fontSize="11" fill="#64748b">{rows[0].trade_date}</text><text x={width - p.r} y={height - 12} textAnchor="end" fontSize="11" fill="#64748b">{rows[rows.length - 1]?.trade_date}</text>
    </svg>
    {hover ? <div className="chart-marker-chart-tooltip"><strong>{hover.trade_date}</strong><span>시가 <b>{hover.open?.toLocaleString() ?? "-"}</b></span><span>고가 <b>{hover.high?.toLocaleString() ?? "-"}</b></span><span>저가 <b>{hover.low?.toLocaleString() ?? "-"}</b></span><span>종가 <b>{hover.close?.toLocaleString() ?? "-"}</b></span><span>거래량 <b>{hover.volume?.toLocaleString() ?? "-"}</b></span><span>등락률 <b className={closeChangeRate == null ? "" : closeChangeRate > 0 ? "up" : closeChangeRate < 0 ? "down" : "flat"}>{closeChangeRate == null ? "-" : `${closeChangeRate > 0 ? "+" : ""}${closeChangeRate.toFixed(2)}%`}</b></span></div> : null}
  </div>;
}

type EditorState = { kind: "group"; group?: ChartMarkerGroup; marker?: never } | { kind: "marker"; marker?: ChartMarker; group?: never } | null;

function CatalogTab({ groups, reload }: { groups: ChartMarkerGroup[]; reload: () => Promise<void> }) {
  const [selected, setSelected] = useState<number | null>(groups[0]?.id ?? null);
  const [editor, setEditor] = useState<EditorState>(null);
  const [saving, setSaving] = useState(false);
  const [reorderingGroupId, setReorderingGroupId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [knowledgeCategories, setKnowledgeCategories] = useState<KmsSettingItem[]>([]);
  const [knowledgeKeyword, setKnowledgeKeyword] = useState("");
  const [knowledgeCategoryId, setKnowledgeCategoryId] = useState(0);
  const [knowledgeResults, setKnowledgeResults] = useState<KmsKnowledgeItem[] | null>(null);
  const [selectedKnowledge, setSelectedKnowledge] = useState<ChartMarkerKnowledgeItem[]>([]);
  const [knowledgeSearching, setKnowledgeSearching] = useState(false);
  const [knowledgeError, setKnowledgeError] = useState("");
  const orderedGroups = useMemo(
    () => [...groups].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id),
    [groups],
  );
  const group = orderedGroups.find((item) => item.id === selected) ?? orderedGroups[0];
  const linkedKnowledge = group?.knowledge_items ?? [];
  useEffect(() => { if (!group && groups[0]) setSelected(groups[0].id); }, [groups, group]);

  useEffect(() => {
    if (editor?.kind !== "group") return;
    let active = true;
    setSelectedKnowledge(editor.group?.knowledge_items ?? []);
    setKnowledgeKeyword("");
    setKnowledgeCategoryId(0);
    setKnowledgeResults(null);
    setKnowledgeError("");
    repositories.kms.listSettingItems({ group_code: "KNOWLEDGE_CATEGORY", include_inactive: false })
      .then((rows) => {
        if (!active) return;
        setKnowledgeCategories(rows);
        const chartCategory = rows.find((item) => item.item_code.toUpperCase() === "CHART" || item.item_name === "차트");
        setKnowledgeCategoryId(chartCategory?.id ?? 0);
      })
      .catch((nextError) => { if (active) setKnowledgeError(nextError instanceof Error ? nextError.message : "지식 카테고리를 불러오지 못했습니다."); });
    return () => { active = false; };
  }, [editor?.kind, editor?.kind === "group" ? editor.group?.id : undefined]);

  const searchKnowledge = async (categoryId = knowledgeCategoryId) => {
    setKnowledgeSearching(true); setKnowledgeError("");
    try {
      setKnowledgeResults(await repositories.kms.listKnowledgeItems({
        keyword: knowledgeKeyword.trim() || undefined,
        category_id: categoryId || undefined,
        is_active: true,
        limit: 30,
      }));
    } catch (nextError) {
      setKnowledgeError(nextError instanceof Error ? nextError.message : "지식을 검색하지 못했습니다.");
    } finally {
      setKnowledgeSearching(false);
    }
  };

  const searchKnowledgeOnEnter = (event: ReactKeyboardEvent<HTMLSelectElement | HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    event.stopPropagation();
    void searchKnowledge();
  };

  const toLinkedKnowledge = (item: KmsKnowledgeItem): ChartMarkerKnowledgeItem => ({
    id: item.id,
    title: item.title,
    summary: item.summary ?? null,
    category_id: item.category_id ?? null,
    category_name: item.category?.item_name ?? null,
    knowledge_type_name: item.para_type?.item_name ?? null,
    is_active: item.is_active,
    sort_order: selectedKnowledge.length * 10,
  });

  const toggleKnowledge = (item: KmsKnowledgeItem) => {
    setSelectedKnowledge((current) => current.some((row) => row.id === item.id)
      ? current.filter((row) => row.id !== item.id)
      : [...current, toLinkedKnowledge(item)]);
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!editor) return; setSaving(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      if (editor.kind === "group") {
        const current = editor.group, payload = { name: String(form.get("name")), description: String(form.get("description") || ""), color: String(form.get("color")), sort_order: current?.sort_order ?? Math.max(0, ...orderedGroups.map((item) => item.sort_order)) + 10, is_active: form.get("is_active") === "on", knowledge_item_ids: selectedKnowledge.map((item) => item.id) };
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
  const deleteMarker = async (marker: ChartMarker) => {
    if (marker.marker_count > 0) {
      setError("등록된 마커 기록이 있는 마커는 삭제할 수 없습니다.");
      return;
    }
    if (!window.confirm(`"${marker.name}" 마커를 삭제할까요? 삭제한 마커는 복구할 수 없습니다.`)) return;
    setError("");
    try {
      await repositories.chartMarkers.deleteMarker(marker.id);
      await reload();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "마커를 삭제하지 못했습니다.");
    }
  };
  const moveMarker = async (marker: ChartMarker, direction: -1 | 1) => {
    if (!group) return;
    const ordered = [...group.markers].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
    const index = ordered.findIndex((item) => item.id === marker.id), targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= ordered.length) return;
    [ordered[index], ordered[targetIndex]] = [ordered[targetIndex], ordered[index]];
    await Promise.all(ordered.map((item, itemIndex) => repositories.chartMarkers.updateMarker(item.id, { sort_order: (itemIndex + 1) * 10 })));
    await reload();
  };
  const moveGroup = async (targetGroup: ChartMarkerGroup, direction: -1 | 1) => {
    if (reorderingGroupId !== null) return;
    const reordered = [...orderedGroups];
    const index = reordered.findIndex((item) => item.id === targetGroup.id);
    const targetIndex = index + direction;
    if (index < 0 || targetIndex < 0 || targetIndex >= reordered.length) return;
    [reordered[index], reordered[targetIndex]] = [reordered[targetIndex], reordered[index]];
    setReorderingGroupId(targetGroup.id);
    setError("");
    try {
      await Promise.all(reordered.map((item, itemIndex) => repositories.chartMarkers.updateGroup(item.id, { sort_order: (itemIndex + 1) * 10 })));
      await reload();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "마커그룹 순서를 변경하지 못했습니다.");
      await reload();
    } finally {
      setReorderingGroupId(null);
    }
  };
  return <>
    <div className="chart-marker-section-intro"><div><h2>마커그룹</h2><p>차트에서 사용할 관찰 기준을 그룹과 마커로 관리합니다.</p></div><button className="btn btn-primary" type="button" onClick={() => setEditor({ kind: "group" })}><Plus size={16} /> 새 그룹</button></div>
    {error && !editor ? <div className="inline-result inline-error">{error}</div> : null}
    <div className="chart-marker-master-detail"><aside className="panel chart-marker-group-panel"><div className="chart-marker-panel-title"><h3>마커그룹</h3><span>{orderedGroups.length}개</span></div><div className="chart-marker-group-list">{orderedGroups.map((item, index) => <div key={item.id} className={`chart-marker-group-row ${item.id === group?.id ? "active" : ""}`}><button type="button" className="chart-marker-group-select" onClick={() => setSelected(item.id)}><i style={{ background: item.color }} /><span><strong>{item.name}</strong><small>{item.is_active ? "활성" : "비활성"}</small></span><b>{item.markers.length}</b></button><div className="chart-marker-group-order-actions" aria-label={`${item.name} 그룹 순서`}><button type="button" title="그룹 위로 이동" aria-label={`${item.name} 그룹 위로 이동`} disabled={reorderingGroupId !== null || index === 0} onClick={() => void moveGroup(item, -1)}><ChevronUp size={15} /></button><button type="button" title="그룹 아래로 이동" aria-label={`${item.name} 그룹 아래로 이동`} disabled={reorderingGroupId !== null || index === orderedGroups.length - 1} onClick={() => void moveGroup(item, 1)}><ChevronDown size={15} /></button></div></div>)}</div></aside>
      <main className="panel chart-marker-detail-panel">{group ? <><header className="chart-marker-detail-header"><div><div className="chart-marker-group-heading"><i style={{ background: group.color }} /><h2>{group.name}</h2><span className={`chart-marker-status ${group.is_active ? "active" : ""}`}>{group.is_active ? "활성" : "비활성"}</span></div><p>{group.description || "등록된 그룹 설명이 없습니다."}</p></div><div><button className="btn btn-secondary" type="button" onClick={() => setEditor({ kind: "group", group })}><Pencil size={15} /> 수정</button><button className="btn btn-secondary" type="button" onClick={() => void toggleGroup()}><Power size={15} /> {group.is_active ? "비활성" : "활성화"}</button></div></header><section className="chart-marker-linked-knowledge"><div className="chart-marker-linked-heading"><div><h3>연결 지식</h3><span>{linkedKnowledge.length}개</span></div><p>마커를 판단할 때 함께 확인할 지식입니다.</p></div>{linkedKnowledge.length ? <div className="chart-marker-linked-list">{linkedKnowledge.map((item) => <Link key={item.id} to={`/kms/posts?item_id=${item.id}`}><span><strong>{item.title}</strong><small>{[item.category_name, item.knowledge_type_name].filter(Boolean).join(" · ") || "분류 없음"}</small>{item.summary ? <em>{item.summary}</em> : null}</span>{!item.is_active ? <b>비활성</b> : null}<ExternalLink size={14} /></Link>)}</div> : <div className="chart-marker-linked-empty">연결된 지식이 없습니다. 그룹 수정에서 지식을 연결할 수 있습니다.</div>}</section><div className="chart-marker-detail-toolbar"><div><h3>등록 마커</h3><span>{group.markers.length}개</span></div><button className="btn btn-primary" type="button" onClick={() => setEditor({ kind: "marker" })}><Plus size={16} /> 마커 추가</button></div><div className="chart-marker-card-list">{group.markers.length ? group.markers.map((marker, index) => <article key={marker.id} className={!marker.is_active ? "inactive" : ""}><div className="chart-marker-symbol" style={{ color: group.color, background: `${group.color}12` }}>{marker.symbol}</div><div className="chart-marker-card-copy"><div className="chart-marker-card-title"><strong>{marker.name}</strong></div><p>{marker.description || "등록된 설명이 없습니다."}</p></div><div className="chart-marker-card-metrics" aria-label={`${marker.name} 집계`}><span><small>종목</small><strong>{marker.stock_count}</strong></span><span><small>마커</small><strong>{marker.marker_count}</strong></span><span className="success"><small>성공</small><strong>{marker.success_count}</strong></span><span className="failure"><small>실패</small><strong>{marker.failure_count}</strong></span></div><div className="chart-marker-order-actions"><button title="위로 이동" disabled={index === 0} onClick={() => void moveMarker(marker, -1)}><ChevronUp size={16} /></button><button title="아래로 이동" disabled={index === group.markers.length - 1} onClick={() => void moveMarker(marker, 1)}><ChevronDown size={16} /></button></div><div className="chart-marker-card-actions"><button onClick={() => setEditor({ kind: "marker", marker })}>수정</button><button className={marker.is_active ? "danger" : "activate"} aria-label={`${marker.name}을 ${marker.is_active ? "비활성" : "활성"} 상태로 변경`} onClick={() => void toggleMarker(marker)}>{marker.is_active ? "비활성" : "활성"}</button>{marker.marker_count === 0 ? <button className="delete" aria-label={`${marker.name} 마커 삭제`} onClick={() => void deleteMarker(marker)}>삭제</button> : null}</div></article>) : <div className="chart-marker-empty compact">등록된 마커가 없습니다.<br />마커 추가를 눌러 관찰 기준을 만들어 주세요.</div>}</div></> : <div className="chart-marker-empty">마커그룹을 먼저 등록해 주세요.</div>}</main>
    </div>
    {editor ? <div className="chart-marker-editor-backdrop" onMouseDown={() => setEditor(null)}><form className={`chart-marker-editor ${editor.kind === "group" ? "group-editor" : ""}`} onSubmit={save} onMouseDown={(event) => event.stopPropagation()}><header><div><h3>{editor.kind === "group" ? `마커그룹 ${editor.group ? "수정" : "등록"}` : `차트마커 ${editor.marker ? "수정" : "등록"}`}</h3><p>{editor.kind === "group" ? "관찰 기준과 함께 참고할 지식을 연결합니다." : `${group?.name || "선택 그룹"}에 사용할 마커입니다.`}</p></div><button type="button" onClick={() => setEditor(null)}><X size={20} /></button></header><div className="chart-marker-editor-body"><label>{editor.kind === "group" ? "그룹명" : "마커명"}<input className="input-control" name="name" required autoFocus defaultValue={editor.kind === "group" ? editor.group?.name : editor.marker?.name} /></label>{editor.kind === "group" ? <label>대표 색상<div className="chart-marker-color-input"><input type="color" name="color" defaultValue={editor.group?.color ?? "#64748b"} /><span>차트에서 마커를 구분할 때 사용합니다.</span></div></label> : <label>표시 심볼<input className="input-control chart-marker-symbol-input" name="symbol" maxLength={12} defaultValue={editor.marker?.symbol ?? "◆"} /></label>}<label>설명<textarea className="input-control" name="description" rows={3} defaultValue={editor.kind === "group" ? editor.group?.description ?? "" : editor.marker?.description ?? ""} /></label>{editor.kind === "group" ? <section className="chart-marker-knowledge-picker"><div className="chart-marker-picker-heading"><div><strong>연결 지식</strong><span>{selectedKnowledge.length}개 선택</span></div><p>활성 지식을 검색해 여러 개 연결할 수 있습니다.</p></div><div className="chart-marker-knowledge-search"><select aria-label="지식 카테고리" value={knowledgeCategoryId} onChange={(event) => { const nextCategoryId = Number(event.target.value); setKnowledgeCategoryId(nextCategoryId); void searchKnowledge(nextCategoryId); }} onKeyDown={searchKnowledgeOnEnter}><option value={0}>전체 카테고리</option>{knowledgeCategories.map((category) => <option key={category.id} value={category.id}>{category.item_name}</option>)}</select><input className="input-control" value={knowledgeKeyword} placeholder="지식 제목 검색" onChange={(event) => setKnowledgeKeyword(event.target.value)} onKeyDown={searchKnowledgeOnEnter} /><button className="btn btn-secondary" type="button" disabled={knowledgeSearching} onClick={() => void searchKnowledge()}><Search size={13} /> {knowledgeSearching ? "검색 중" : "검색"}</button></div><div className="chart-marker-knowledge-columns"><div><h4>검색 결과</h4><div className="chart-marker-knowledge-results">{knowledgeResults === null ? <p>카테고리나 제목을 입력하고 검색해 주세요.</p> : knowledgeResults.length ? knowledgeResults.map((item) => { const checked = selectedKnowledge.some((row) => row.id === item.id); return <label key={item.id}><input type="checkbox" checked={checked} onChange={() => toggleKnowledge(item)} /><span><strong>{item.title}</strong><small>{[item.category?.item_name, item.para_type?.item_name].filter(Boolean).join(" · ") || "분류 없음"}</small></span></label>; }) : <p>검색 결과가 없습니다.</p>}</div></div><div><h4>선택한 지식</h4><div className="chart-marker-selected-knowledge">{selectedKnowledge.length ? selectedKnowledge.map((item) => <div key={item.id}><span><strong>{item.title}</strong><small>{item.category_name || "분류 없음"}</small></span>{!item.is_active ? <b>비활성</b> : null}<button type="button" aria-label={`${item.title} 연결 해제`} onClick={() => setSelectedKnowledge((current) => current.filter((row) => row.id !== item.id))}><X size={14} /></button></div>) : <p>선택한 지식이 없습니다.</p>}</div></div></div>{knowledgeError ? <p className="inline-result inline-error">{knowledgeError}</p> : null}</section> : null}<label className="chart-marker-active-check"><input name="is_active" type="checkbox" defaultChecked={editor.kind === "group" ? editor.group?.is_active ?? true : editor.marker?.is_active ?? true} /> 활성 상태로 사용</label>{error ? <p className="inline-result inline-error">{error}</p> : null}</div><footer><button className="btn btn-secondary" type="button" onClick={() => setEditor(null)}>취소</button><button className="btn btn-primary" disabled={saving}>{saving ? "저장 중…" : editor.group || editor.marker ? "수정" : "등록"}</button></footer></form></div> : null}
  </>;
}

export default function ChartMarkerReviewPage() {
  const [tab, setTab] = useState<"catalog" | "review">("catalog"), [groups, setGroups] = useState<ChartMarkerGroup[]>([]), [groupId, setGroupId] = useState<number | null>(null), [markerId, setMarkerId] = useState<number | null>(null), [events, setEvents] = useState<ChartMarkerReviewEvent[]>([]), [selected, setSelected] = useState<ChartMarkerReviewEvent | null>(null), [stockQuery, setStockQuery] = useState(""), [chart, setChart] = useState<ChartMarkerReviewChart | null>(null), [chartLoading, setChartLoading] = useState(false), [error, setError] = useState("");
  const [resultFilter, setResultFilter] = useState<"ALL" | "S" | "F">("ALL"), [savingReviewId, setSavingReviewId] = useState<number | null>(null);
  const [windowKey, setWindowKey] = useState<ReviewWindowKey>("60.D0.20");
  const [showD0Marker, setShowD0Marker] = useState(true);
  const [rangeEvents, setRangeEvents] = useState<ChartMarkerEvent[]>([]);
  const [markerMenu, setMarkerMenu] = useState<{ date: string; x: number; y: number } | null>(null);
  const [markerEditor, setMarkerEditor] = useState<{ date: string; event?: ChartMarkerEvent } | null>(null);
  const [editorGroupId, setEditorGroupId] = useState<number | null>(null), [editorMarkerId, setEditorMarkerId] = useState<number | null>(null), [editorMemo, setEditorMemo] = useState(""), [savingMarker, setSavingMarker] = useState(false);
  const [detailHeight, setDetailHeight] = useState<number | null>(null);
  const detailRef = useRef<HTMLElement | null>(null);
  const reload = async () => { try { setGroups((await repositories.chartMarkers.catalog()).items); } catch (nextError) { setError(nextError instanceof Error ? nextError.message : "마커를 불러오지 못했습니다."); } };
  useEffect(() => { void reload(); }, []);
  const activeGroups = groups.filter((item) => item.is_active).sort((a, b) => a.sort_order - b.sort_order || a.id - b.id), group = activeGroups.find((item) => item.id === groupId) ?? activeGroups[0], markers = group?.markers.filter((item) => item.is_active).sort((a, b) => a.sort_order - b.sort_order || a.id - b.id) ?? [];
  useEffect(() => { if (group && group.id !== groupId) setGroupId(group.id); }, [group, groupId]);
  useEffect(() => { if (!markers.some((item) => item.id === markerId)) setMarkerId(markers[0]?.id ?? null); }, [groupId, groups]);
  useEffect(() => { setStockQuery(""); setResultFilter("ALL"); }, [groupId, markerId]);
  useEffect(() => { if (tab !== "review" || !markerId) { setEvents([]); setSelected(null); return; } repositories.chartMarkers.reviewEvents(markerId).then((response) => { setEvents(response.items); setSelected(response.items[0] ?? null); }).catch((nextError) => setError(nextError.message)); }, [tab, markerId]);
  const selectedEventKey = selected ? `${selected.stock_id}-${selected.marker_date}-${selected.marker_id}-${selected.id}` : "";
  const selectedWindow = REVIEW_WINDOWS.find((item) => item.key === windowKey) ?? REVIEW_WINDOWS[1];
  useEffect(() => {
    if (!selected) { setChart(null); setRangeEvents([]); return; }
    let active = true;
    setChart(null);
    setRangeEvents([]);
    setMarkerMenu(null);
    setChartLoading(true);
    repositories.chartMarkers.reviewChart(selected.stock_id, selected.marker_date, selectedWindow.before, selectedWindow.after)
      .then(async (rawChart) => {
        if (!active) return;
        const nextChart = normalizeReviewChart(rawChart, selectedWindow.before, selectedWindow.after);
        setChart(nextChart);
        if (!nextChart.candles.length) return;
        const startDate = nextChart.candles[0].trade_date;
        const endDate = nextChart.candles[nextChart.candles.length - 1].trade_date;
        const stockEvents = await repositories.chartMarkers.listStockEvents(selected.stock_id, endDate);
        if (active) setRangeEvents(stockEvents.items.filter((item) => item.marker_date >= startDate && item.marker_date <= endDate));
      })
      .catch((nextError) => { if (active) setError(nextError.message); })
      .finally(() => { if (active) setChartLoading(false); });
    return () => { active = false; };
  }, [selectedEventKey, windowKey]);
  useLayoutEffect(() => {
    const detail = detailRef.current;
    if (!detail || typeof ResizeObserver === "undefined") return;
    const syncHeight = () => setDetailHeight(Math.ceil(detail.getBoundingClientRect().height));
    syncHeight();
    const observer = new ResizeObserver(syncHeight);
    observer.observe(detail);
    return () => observer.disconnect();
  }, [selectedEventKey, windowKey, chartLoading]);
  const visibleEvents = useMemo(() => {
    const query = stockQuery.trim().toLocaleLowerCase();
    return events.filter((item) => (!query || item.stock_name.toLocaleLowerCase().includes(query)) && (resultFilter === "ALL" || item.review_result === resultFilter));
  }, [events, stockQuery, resultFilter]);
  const filteredGrouped = useMemo(() => Array.from(visibleEvents.reduce((map, item) => { const rows = map.get(item.stock_id) ?? []; rows.push(item); map.set(item.stock_id, rows); return map; }, new Map<number, ChartMarkerReviewEvent[]>()).values()).map((rows) => [...rows].sort((a, b) => b.marker_date.localeCompare(a.marker_date))), [visibleEvents]);
  const visibleEventIds = visibleEvents.map((item) => item.id).join(",");
  useEffect(() => {
    if (!visibleEvents.length) { setSelected(null); return; }
    if (!selected || !visibleEvents.some((item) => item.id === selected.id)) setSelected(visibleEvents[0]);
  }, [visibleEventIds]);
  const selectedIndex = selected ? visibleEvents.findIndex((item) => item.id === selected.id) : -1;
  const moveSelection = (offset: number) => { const next = visibleEvents[selectedIndex + offset]; if (next) setSelected(next); };
  const editorGroup = activeGroups.find((item) => item.id === editorGroupId) ?? activeGroups[0];
  const editorMarkers = editorGroup?.markers.filter((item) => item.is_active).sort((a, b) => a.sort_order - b.sort_order || a.id - b.id) ?? [];
  const groupRank = new Map(activeGroups.map((item, index) => [item.id, index]));
  const markerRank = new Map(activeGroups.flatMap((item) => item.markers.map((marker, index) => [marker.id, index] as const)));
  const menuEvents = markerMenu ? rangeEvents.filter((item) => item.marker_date === markerMenu.date).sort((a, b) => (groupRank.get(a.marker_group_id) ?? 9999) - (groupRank.get(b.marker_group_id) ?? 9999) || (markerRank.get(a.marker_id) ?? 9999) - (markerRank.get(b.marker_id) ?? 9999) || a.id - b.id) : [];
  useEffect(() => { if (!editorGroup) return; if (editorGroup.id !== editorGroupId) setEditorGroupId(editorGroup.id); if (!editorMarkers.some((item) => item.id === editorMarkerId)) setEditorMarkerId(editorMarkers[0]?.id ?? null); }, [editorGroup?.id, editorGroupId, editorMarkerId, groups]);
  const openNewMarker = (date: string) => { const firstGroup = activeGroups[0]; setMarkerEditor({ date }); setEditorGroupId(firstGroup?.id ?? null); setEditorMarkerId(firstGroup?.markers.find((item) => item.is_active)?.id ?? null); setEditorMemo(""); setMarkerMenu(null); setError(""); };
  const openEditMarker = (item: ChartMarkerEvent) => { setMarkerEditor({ date: item.marker_date, event: item }); setEditorGroupId(item.marker_group_id); setEditorMarkerId(item.marker_id); setEditorMemo(item.memo ?? ""); setMarkerMenu(null); setError(""); };
  const refreshRangeEvents = async () => {
    if (!selected || !chart?.candles.length) return;
    const startDate = chart.candles[0].trade_date, endDate = chart.candles[chart.candles.length - 1].trade_date;
    const response = await repositories.chartMarkers.listStockEvents(selected.stock_id, endDate);
    setRangeEvents(response.items.filter((item) => item.marker_date >= startDate && item.marker_date <= endDate));
  };
  const refreshReviewEvents = async () => {
    if (!markerId) return;
    const response = await repositories.chartMarkers.reviewEvents(markerId);
    setEvents(response.items);
    setSelected((current) => response.items.find((item) => item.id === current?.id) ?? response.items[0] ?? null);
  };
  const saveMarker = async (formEvent: FormEvent<HTMLFormElement>) => {
    formEvent.preventDefault();
    if (!selected || !markerEditor || !editorMarkerId) return;
    setSavingMarker(true); setError("");
    try {
      if (markerEditor.event) await repositories.chartMarkers.updateEvent(markerEditor.event.id, { marker_id: editorMarkerId, memo: editorMemo || null });
      else await repositories.chartMarkers.upsertEvent({ stock_id: selected.stock_id, marker_id: editorMarkerId, marker_date: markerEditor.date, memo: editorMemo || null });
      setMarkerEditor(null);
      await Promise.all([refreshReviewEvents(), refreshRangeEvents(), reload()]);
    } catch (nextError) { setError(nextError instanceof Error ? nextError.message : "차트마커를 저장하지 못했습니다."); }
    finally { setSavingMarker(false); }
  };
  const updateReviewResult = async (item: ChartMarkerReviewEvent, nextResult: Exclude<ChartMarkerReviewResult, undefined>) => {
    setSavingReviewId(item.id); setError("");
    try {
      const updated = await repositories.chartMarkers.updateEvent(item.id, { review_result: item.review_result === nextResult ? null : nextResult });
      const merged = { ...item, ...updated } as ChartMarkerReviewEvent;
      setEvents((current) => current.map((event) => event.id === item.id ? merged : event));
      if (selected?.id === item.id) setSelected(merged);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "성공·실패 판정을 저장하지 못했습니다.");
    } finally { setSavingReviewId(null); }
  };
  const deleteReviewEvent = async (item: ChartMarkerReviewEvent) => {
    if (!window.confirm(`${item.stock_name} · ${item.marker_date} 마커 기록을 삭제하시겠습니까?`)) return;
    try {
      await repositories.chartMarkers.deleteEvent(item.id);
      const remaining = events.filter((event) => event.id !== item.id);
      setEvents(remaining);
      setRangeEvents((current) => current.filter((event) => event.id !== item.id));
      await reload();
      if (selected?.id === item.id) {
        const deletedIndex = events.findIndex((event) => event.id === item.id);
        setSelected(remaining[Math.min(deletedIndex, remaining.length - 1)] ?? null);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "마커 기록을 삭제하지 못했습니다.");
    }
  };
  const deleteMarkerFromChart = async (item: ChartMarkerEvent) => {
    if (!window.confirm(`'${item.marker_name}' 마커를 삭제하시겠습니까?`)) return;
    try {
      await repositories.chartMarkers.deleteEvent(item.id);
      setMarkerMenu(null);
      await Promise.all([refreshReviewEvents(), refreshRangeEvents(), reload()]);
    } catch (nextError) { setError(nextError instanceof Error ? nextError.message : "마커 기록을 삭제하지 못했습니다."); }
  };
  return <div className="chart-marker-page space-y-4">
    <PageHeader title="매매훈련 차트마커 복기" description="훈련 차트에서 발견한 현상을 기록하고 같은 유형의 실제 사례를 반복 복기합니다." />
    <div className="chart-marker-tabs">
      <button className={tab === "catalog" ? "active" : ""} onClick={() => setTab("catalog")}>마커그룹</button>
      <button className={tab === "review" ? "active" : ""} onClick={() => setTab("review")}>차트마커 복기</button>
    </div>
    {error ? <div className="inline-result inline-error">{error}</div> : null}
    {tab === "catalog" ? <CatalogTab groups={groups} reload={reload} /> : <>
      <div className="chart-marker-review-intro"><div><h2>차트마커 복기</h2><p>같은 마커가 기록된 사례를 종목별로 비교합니다.</p></div></div>
      <div className="chart-marker-filters">
        <label className="chart-marker-filter-group"><span>마커그룹</span><select className="input-control" value={group?.id ?? ""} onChange={(event) => { setGroupId(Number(event.target.value)); setMarkerId(null); }}>{activeGroups.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <div className="chart-marker-filter-marker"><span>차트마커</span><div className="chart-marker-choice-list" role="group" aria-label="차트마커 선택">{markers.length ? markers.map((item) => <button key={item.id} type="button" className={item.id === markerId ? "active" : ""} style={{ "--chart-marker-accent": group?.color ?? "#2563eb" } as CSSProperties} title={item.name} aria-pressed={item.id === markerId} onClick={() => setMarkerId(item.id)}><span className="chart-marker-choice-symbol" aria-hidden="true">{item.symbol}</span><strong>{item.name}</strong></button>) : <p>등록된 활성 마커가 없습니다.</p>}</div></div>
        <strong className="chart-marker-filter-count">사례 {events.length}건</strong>
      </div>
      {!activeGroups.length ? <div className="chart-marker-empty">등록된 활성 차트마커 그룹이 없습니다.<br />마커그룹 탭에서 먼저 그룹을 활성화해 주세요.</div> : !markers.length ? <div className="chart-marker-empty">이 그룹에 등록된 활성 마커가 없습니다.<br />마커그룹 탭에서 사용할 마커를 활성화해 주세요.</div> : !events.length ? <div className="chart-marker-empty">이 마커로 기록된 차트 사례가 없습니다.<br />종목매매훈련 차트에서 캔들을 우클릭하여 마커를 기록해 주세요.</div> : <div className="chart-marker-review-grid">
        <aside className="panel chart-marker-case-panel" style={{ "--chart-marker-detail-height": detailHeight ? `${detailHeight}px` : undefined } as CSSProperties}>
          <header><h3>관련 종목 / 캔들일자</h3><span>{visibleEvents.length}건</span></header>
          <div className="chart-marker-case-tools"><div className="chart-marker-case-search"><Search size={15} aria-hidden="true" /><input className="input-control" type="search" value={stockQuery} onChange={(event) => setStockQuery(event.target.value)} placeholder="종목명 검색" aria-label="종목명 검색" /></div><div className="chart-marker-result-filter" aria-label="판정 상태 필터">{(["ALL", "S", "F"] as const).map((value) => <button type="button" key={value} className={`${resultFilter === value ? "active" : ""} ${value.toLowerCase()}`} onClick={() => setResultFilter(value)}>{value === "ALL" ? "전체" : value === "S" ? "성공" : "실패"}</button>)}</div></div>
          <div className="chart-marker-case-scroll">{filteredGrouped.length ? filteredGrouped.map((rows) => <div className="chart-marker-stock" key={rows[0].stock_id}>
            <div><strong>{rows[0].stock_name}</strong><span>{rows.length}건</span></div>
            {rows.map((item) => <div className={`chart-marker-case-row ${selected?.id === item.id ? "active" : ""}`} key={`${item.stock_id}-${item.marker_date}-${item.marker_id}-${item.id}`} onClick={() => setSelected(item)}>
              <button className="chart-marker-case-date"><i />{item.marker_date}</button>
              <div className="chart-marker-case-results" onClick={(clickEvent) => clickEvent.stopPropagation()}>
                <button type="button" className={item.review_result === "S" ? "success active" : "success"} disabled={savingReviewId === item.id} title="선택된 판정을 다시 누르면 미평가로 돌아갑니다." onClick={() => void updateReviewResult(item, "S")}>성공{item.review_result === "S" ? " ✓" : ""}</button>
                <button type="button" className={item.review_result === "F" ? "failure active" : "failure"} disabled={savingReviewId === item.id} title="선택된 판정을 다시 누르면 미평가로 돌아갑니다." onClick={() => void updateReviewResult(item, "F")}>실패{item.review_result === "F" ? " ✓" : ""}</button>
              </div>
              <button className="chart-marker-case-delete" title={`${item.marker_date} 마커 삭제`} onClick={(clickEvent) => { clickEvent.stopPropagation(); void deleteReviewEvent(item); }}>삭제</button>
            </div>)}
          </div>) : <div className="chart-marker-search-empty">검색된 종목이 없습니다.</div>}</div>
        </aside>
        {selected ? <main className="panel chart-marker-review-detail" ref={detailRef}>
          <header><div className="chart-marker-review-context"><div className="chart-marker-review-title"><h2>{selected.stock_name}</h2><time>· {selected.marker_date}</time></div><p><span style={{ color: selected.group_color, background: `${selected.group_color}12`, borderColor: `${selected.group_color}40` }}>{selected.group_name}</span><b style={{ color: selected.group_color }}>{selected.symbol}</b>{selected.marker_name}</p></div><div className="chart-marker-review-nav"><button className="btn btn-secondary" disabled={selectedIndex <= 0} onClick={() => moveSelection(-1)}><ArrowLeft size={15} /> 이전 사례</button><strong>{selectedIndex + 1} / {visibleEvents.length}</strong><button className="btn btn-secondary" disabled={selectedIndex >= visibleEvents.length - 1} onClick={() => moveSelection(1)}>다음 사례 <ArrowRight size={15} /></button></div></header>
          <div className="chart-marker-chart-heading"><div><h3>마커 전후 가격 흐름</h3><p>이전 {chart?.available_before ?? selectedWindow.before}개 · D0 · 이후 {chart?.available_after ?? selectedWindow.after}개</p></div><div className="chart-marker-window-controls" aria-label="차트 조회 도구"><label className="chart-marker-d0-toggle" title="복기 기준일의 마커 심볼과 세로선을 차트에 표시합니다."><input type="checkbox" checked={showD0Marker} onChange={(event) => setShowD0Marker(event.target.checked)} /><span>D0 마커 표시</span></label>{REVIEW_WINDOWS.map((item) => <button key={item.key} type="button" className={windowKey === item.key ? "active" : ""} title={item.title} onClick={() => setWindowKey(item.key)}>{item.key}</button>)}<span className="chart-marker-d0-date">D0 {selected.marker_date}</span></div></div>
          <ReviewChart data={chart} reviewEvent={selected} loading={chartLoading} markerEvents={rangeEvents} showD0Marker={showD0Marker} onContextMenu={(date, x, y) => setMarkerMenu({ date, x, y })} />
          <section className="chart-marker-memo"><strong>메모</strong><p>{selected.memo || "등록된 메모가 없습니다."}</p></section>
        </main> : <main className="panel chart-marker-review-detail"><div className="chart-marker-empty compact">조건에 맞는 복기 사례가 없습니다.</div></main>}
      </div>}
      {markerMenu ? <><button type="button" className="chart-marker-menu-dismiss-layer" aria-label="차트마커 메뉴 닫기" onMouseDown={() => setMarkerMenu(null)} /><div className="training-chart-marker-menu chart-marker-review-menu" style={{ left: markerMenu.x + 392 < window.innerWidth ? markerMenu.x + 12 : Math.max(12, markerMenu.x - 392), top: Math.max(12, Math.min(markerMenu.y - 8, window.innerHeight - 420)) }}><header><div><strong>{markerMenu.date}</strong><span>선택한 캔들</span></div><button type="button" onClick={() => setMarkerMenu(null)}>×</button></header><button type="button" className="training-chart-marker-primary-action" onClick={() => openNewMarker(markerMenu.date)}><span>+</span><div><strong>차트마커 기록</strong><small>이 캔들에서 발견한 현상을 기록합니다.</small></div></button>{menuEvents.length ? <section><h4>등록된 마커</h4>{menuEvents.map((item) => <article key={item.id}><span className="training-chart-marker-symbol" style={{ color: item.group_color, background: `${item.group_color}12` }}>{item.symbol}</span><div><small>{item.group_name}</small><strong>{item.marker_name}</strong></div><footer><button type="button" onClick={() => openEditMarker(item)}>수정</button><button type="button" className="danger" onClick={() => void deleteMarkerFromChart(item)}>삭제</button></footer></article>)}</section> : <p className="training-chart-marker-menu-empty">이 캔들에 등록된 마커가 없습니다.</p>}</div></> : null}
      {markerEditor ? <div className="training-chart-marker-modal-backdrop" onMouseDown={() => setMarkerEditor(null)}><form className="training-chart-marker-modal" onSubmit={saveMarker} onMouseDown={(mouseEvent) => mouseEvent.stopPropagation()}><header><div><h3>차트마커 {markerEditor.event ? "수정" : "기록"}</h3><p>{selected?.stock_name} · {markerEditor.date}</p></div><button type="button" onClick={() => setMarkerEditor(null)}>×</button></header><label>마커그룹<select className="input-control" value={editorGroup?.id ?? ""} onChange={(changeEvent) => setEditorGroupId(Number(changeEvent.target.value))}>{activeGroups.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>마커<select className="input-control" value={editorMarkerId ?? ""} onChange={(changeEvent) => setEditorMarkerId(Number(changeEvent.target.value))}>{editorMarkers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>메모<textarea className="input-control" rows={4} maxLength={4000} value={editorMemo} onChange={(changeEvent) => setEditorMemo(changeEvent.target.value)} placeholder="이 현상을 판단한 근거나 특징을 짧게 기록해 주세요." /></label><footer><button type="button" className="btn btn-secondary" onClick={() => setMarkerEditor(null)}>취소</button><button className="btn btn-primary" disabled={savingMarker || !editorMarkerId}>{savingMarker ? "저장 중…" : markerEditor.event ? "수정" : "저장"}</button></footer></form></div> : null}
    </>}
  </div>;
}
