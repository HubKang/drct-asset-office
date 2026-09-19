import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { repositories } from "@/services";
import type { KmsKnowledgeItem, KmsSettingItemSummary } from "@/types/kms";
import { toKmsDisplayHtml } from "@/utils/kmsRichContent";

function SettingBadge({ item, fallback }: { item?: KmsSettingItemSummary | null; fallback: string }) {
  return <span className="kms-knowledge-badge" style={{ "--kms-badge-bg": item?.color || "#f1f5f9" } as CSSProperties} title={item?.item_code || fallback}>{item?.item_name || fallback}</span>;
}

export function KmsKnowledgeDetailView({ item, onRemoveTag, children }: {
  item: KmsKnowledgeItem;
  onRemoveTag?: (tagId: number) => void;
  children?: ReactNode;
}) {
  const tags = item.tags.filter((tag) => tag.is_confirmed);
  return <>
    <div className="kms-card-badges"><SettingBadge item={item.para_type} fallback="유형" /><SettingBadge item={item.category} fallback="미분류" /><SettingBadge item={item.status} fallback="상태" /><SettingBadge item={item.importance} fallback="중요도" /><SettingBadge item={item.usage_context} fallback="사용처" /><SettingBadge item={item.source_type} fallback="출처" /></div>
    {item.summary ? <section className="kms-content-section"><h3>요약</h3><p className="kms-detail-summary">{item.summary}</p></section> : null}
    <section className="kms-content-section"><h3>본문</h3><div className="kms-detail-content kms-rich-content" dangerouslySetInnerHTML={{ __html: toKmsDisplayHtml(item.content) }} /></section>
    <div className="kms-detail-support">
      <section className="kms-detail-group" aria-labelledby={`kms-knowledge-info-title-${item.id}`}>
        <div className="kms-detail-group-heading"><div><h3 id={`kms-knowledge-info-title-${item.id}`}>지식 정보</h3><p>분류에 활용하는 태그와 원문 출처를 확인합니다.</p></div></div>
        <div className="kms-detail-info-grid">
          <article className="kms-detail-info-card">
            <div className="kms-detail-info-card-heading"><h4>태그</h4>{tags.length ? <span>{tags.length}개</span> : null}</div>
            {tags.length ? <div className="kms-chip-row">{tags.map((tag) => onRemoveTag
              ? <button key={tag.id} type="button" className="kms-chip selected" onClick={() => onRemoveTag(tag.tag_id)}>#{tag.tag_name}</button>
              : <span key={tag.id} className="kms-chip selected">#{tag.tag_name}</span>)}</div> : <div className="kms-compact-empty">등록된 태그가 없습니다.</div>}
          </article>
          <article className="kms-detail-info-card">
            <div className="kms-detail-info-card-heading"><h4>출처</h4></div>
            {item.source_url ? <a className="kms-source-link kms-detail-source-link" href={item.source_url} target="_blank" rel="noreferrer">{item.source_url}</a> : <div className="kms-compact-empty">출처 URL이 없습니다.</div>}
          </article>
        </div>
      </section>
      {children}
    </div>
  </>;
}

export default function KmsKnowledgeDetailDrawer({ itemId, onClose }: { itemId: number | null; onClose: () => void }) {
  const [item, setItem] = useState<KmsKnowledgeItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const requestRef = useRef(0);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const load = async () => {
    if (!itemId) return;
    const requestId = ++requestRef.current;
    setLoading(true); setError(""); setItem(null);
    try {
      const result = await repositories.kms.getKnowledgeItem(itemId);
      if (requestId === requestRef.current) setItem(result);
    } catch (reason) {
      if (requestId === requestRef.current) setError(reason instanceof Error ? reason.message : "연결된 지식을 불러오지 못했습니다.");
    } finally {
      if (requestId === requestRef.current) setLoading(false);
    }
  };

  useEffect(() => {
    if (itemId) void load();
    return () => { requestRef.current += 1; };
  }, [itemId]);
  useEffect(() => {
    if (!itemId) return;
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onCloseRef.current(); };
    window.addEventListener("keydown", handleKeyDown);
    window.setTimeout(() => closeButtonRef.current?.focus(), 0);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      window.setTimeout(() => previousFocusRef.current?.focus(), 0);
    };
  }, [itemId]);

  if (!itemId) return null;
  return <div className="kms-detail-drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="kms-detail-drawer" role="dialog" aria-modal="true" aria-label={item ? `${item.title} 지식 상세` : "지식 상세"} onMouseDown={(event) => event.stopPropagation()}>
      <div className="kms-detail-drawer-header"><div><h2>{item?.title || "지식 상세"}</h2><p>{item ? `${item.para_type?.item_name || "-"} · ${item.category?.item_name || "-"} · ${item.created_at}` : "연결된 지식을 불러오는 중입니다."}</p></div><div className="kms-detail-drawer-actions"><button ref={closeButtonRef} type="button" className="btn btn-secondary" onClick={onClose}>닫기</button></div></div>
      <div className="kms-detail-drawer-body">
        {loading ? <div className="theme-detail-drawer-skeleton" aria-label="지식 상세 조회 중"><i /><i /><i /></div> : null}
        {error ? <div className="kms-detail-drawer-state"><div className="alert alert-warning">{error}</div><button type="button" className="btn btn-secondary" onClick={() => void load()}>다시 시도</button></div> : null}
        {!loading && !error && item ? <KmsKnowledgeDetailView item={item} /> : null}
      </div>
    </aside>
  </div>;
}
