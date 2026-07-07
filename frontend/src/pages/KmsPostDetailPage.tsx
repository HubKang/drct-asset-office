import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import StatusBadge from "@/components/common/StatusBadge";
import KmsRichEditor from "@/components/kms/KmsRichEditor";
import { repositories } from "@/services";
import {
  KMS_IMPORTANCE_OPTIONS,
  KMS_LEARNING_STATUS_OPTIONS,
  type KmsCategory,
  type KmsImportance,
  type KmsLearningStatus,
  type KmsPost,
  type KmsPostPayload,
} from "@/types/kms";
import { sanitizeKmsHtml, toKmsDisplayHtml, toKmsEditableHtml, toKmsPlainText } from "@/utils/kmsRichContent";

function KmsPostDetailPage() {
  const navigate = useNavigate();
  const { postId } = useParams();
  const numericPostId = Number(postId);
  const [post, setPost] = useState<KmsPost | null>(null);
  const [categories, setCategories] = useState<KmsCategory[]>([]);
  const [isEditing, setIsEditing] = useState(false);
  const [form, setForm] = useState<KmsPostPayload | null>(null);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setMessage("");
    try {
      const [postRow, categoryRows] = await Promise.all([
        repositories.kms.getPost(numericPostId),
        repositories.kms.listCategories(),
      ]);
      setPost(postRow);
      setCategories(categoryRows);
      setForm({
        category_id: postRow.category_id,
        title: postRow.title,
        summary: postRow.summary || "",
        content: toKmsEditableHtml(postRow.content_html || postRow.content),
        source_url: postRow.source_url || "",
        importance: postRow.importance,
        learning_status: postRow.learning_status,
        is_pinned: postRow.is_pinned,
        is_active: postRow.is_active,
        tags: postRow.tags.join(", "),
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "지식글을 불러오지 못했습니다.");
    }
  };

  useEffect(() => {
    if (Number.isFinite(numericPostId)) void load();
  }, [numericPostId]);

  const save = async () => {
    if (!form) return;
    const cleanContent = sanitizeKmsHtml(form.content);
    const contentText = toKmsPlainText(cleanContent);
    if (!form.category_id || !form.title.trim() || !contentText) {
      setMessage("카테고리, 제목, 본문은 필수입니다.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const updated = await repositories.kms.updatePost(numericPostId, {
        ...form,
        title: form.title.trim(),
        summary: form.summary || null,
        content: cleanContent,
        content_format: "html",
        content_html: cleanContent,
        content_text: contentText,
        source_url: form.source_url || null,
      });
      setPost(updated);
      setForm((prev) => prev && ({ ...prev, content: toKmsEditableHtml(updated.content_html || updated.content) }));
      setIsEditing(false);
      setMessage("수정되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "수정에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const deactivate = async () => {
    if (!window.confirm("이 지식글을 비활성화하시겠습니까? 실제 삭제는 수행하지 않습니다.")) return;
    setSaving(true);
    try {
      await repositories.kms.deactivatePost(numericPostId);
      navigate("/kms/posts");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "비활성화에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  if (!post || !form) {
    return (
      <div className="space-y-4">
        <PageHeader title="지식글 상세" description="KMS 지식글을 불러오는 중입니다." />
        {message ? <div className="alert alert-warning">{message}</div> : null}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={post.title}
        description={`${post.category_name || "미분류"} · ${post.importance} · ${post.learning_status}`}
        action={(
          <div className="kms-action-row">
            <button type="button" className="btn btn-secondary" onClick={() => navigate("/kms/posts")}>목록으로</button>
            <button type="button" className="btn btn-primary" onClick={() => setIsEditing((prev) => !prev)}>{isEditing ? "보기" : "수정"}</button>
          </div>
        )}
      />

      {message ? <div className="alert alert-warning">{message}</div> : null}

      {isEditing ? (
        <section className="kms-panel kms-post-form-panel">
          <div className="kms-panel-header">
            <div>
              <h2 className="kms-panel-title">지식글 수정</h2>
              <p className="kms-panel-description">기본 정보와 본문 서식을 나눠 정리합니다.</p>
            </div>
          </div>
          <div className="kms-form-section">
            <div className="kms-form-section-header">
              <h3>기본 정보</h3>
              <p>제목, 분류, 학습 상태를 수정합니다.</p>
            </div>
            <div className="kms-form-grid kms-basic-info-grid">
              <label className="kms-form-field kms-form-wide">
                <span className="kms-form-label">제목 *</span>
                <input className="input kms-form-control" value={form.title} onChange={(event) => setForm((prev) => prev && ({ ...prev, title: event.target.value }))} />
              </label>
              <label className="kms-form-field">
                <span className="kms-form-label">카테고리 *</span>
                <select className="select kms-form-control" value={form.category_id} onChange={(event) => setForm((prev) => prev && ({ ...prev, category_id: Number(event.target.value) }))}>
                  {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                </select>
              </label>
              <label className="kms-form-field">
                <span className="kms-form-label">중요도</span>
                <select className="select kms-form-control" value={form.importance} onChange={(event) => setForm((prev) => prev && ({ ...prev, importance: event.target.value as KmsImportance }))}>
                  {KMS_IMPORTANCE_OPTIONS.map((option) => <option key={option}>{option}</option>)}
                </select>
              </label>
              <label className="kms-form-field">
                <span className="kms-form-label">학습 상태</span>
                <select className="select kms-form-control" value={form.learning_status} onChange={(event) => setForm((prev) => prev && ({ ...prev, learning_status: event.target.value as KmsLearningStatus }))}>
                  {KMS_LEARNING_STATUS_OPTIONS.map((option) => <option key={option}>{option}</option>)}
                </select>
              </label>
            </div>
          </div>
          <div className="kms-form-section">
            <div className="kms-form-section-header">
              <h3>요약</h3>
              <p>지식글의 핵심을 짧게 정리합니다.</p>
            </div>
            <label className="kms-form-field">
              <textarea className="textarea kms-form-control kms-summary-textarea" value={form.summary || ""} onChange={(event) => setForm((prev) => prev && ({ ...prev, summary: event.target.value }))} />
            </label>
          </div>
          <div className="kms-form-section">
            <div className="kms-form-section-header">
              <h3>본문 작성 *</h3>
              <p>본문 서식과 표, 이미지 링크를 수정합니다.</p>
            </div>
            <KmsRichEditor resetKey={`detail-${numericPostId}`} value={form.content} selectLocalImage={() => repositories.kms.selectLocalImage()} imageUploadDomain="kms" ownerType="kms_post" ownerId={numericPostId} onChange={(content) => setForm((prev) => prev && ({ ...prev, content }))} />
          </div>
          <div className="kms-form-section">
            <div className="kms-form-section-header">
              <h3>분류/참고 정보</h3>
              <p>태그, 참고 URL, 고정 여부를 관리합니다.</p>
            </div>
            <div className="kms-form-grid">
              <label className="kms-form-field">
                <span className="kms-form-label">태그</span>
                <input className="input kms-form-control" value={String(form.tags || "")} onChange={(event) => setForm((prev) => prev && ({ ...prev, tags: event.target.value }))} />
                <small className="kms-form-help">예: 단타, 거래량, 전고점, 눌림목</small>
              </label>
              <label className="kms-form-field">
                <span className="kms-form-label">참고 URL</span>
                <input className="input kms-form-control" value={form.source_url || ""} onChange={(event) => setForm((prev) => prev && ({ ...prev, source_url: event.target.value }))} />
              </label>
              <label className="kms-check-field">
                <input type="checkbox" checked={form.is_pinned} onChange={(event) => setForm((prev) => prev && ({ ...prev, is_pinned: event.target.checked }))} />
                <span>고정</span>
              </label>
            </div>
          </div>
          <div className="kms-action-row">
            <button type="button" className="btn btn-primary" onClick={() => void save()} disabled={saving}>{saving ? "저장 중..." : "저장"}</button>
            <button type="button" className="btn btn-danger" onClick={() => void deactivate()} disabled={saving}>비활성화</button>
          </div>
        </section>
      ) : (
        <section className="kms-panel">
          <article className="kms-detail-grid">
            <div className="kms-detail">
              <div className="kms-card-badges">
                <StatusBadge label={post.category_name || "미분류"} tone="slate" />
                <StatusBadge label={post.importance} tone={post.importance === "핵심" ? "rose" : "blue"} />
                <StatusBadge label={post.learning_status} tone={post.learning_status === "복습 필요" ? "amber" : "emerald"} />
                {post.is_pinned ? <StatusBadge label="고정" tone="blue" /> : null}
              </div>
              <div className="kms-chip-row">
                {post.tags.length ? post.tags.map((tag) => <span key={tag} className="kms-chip selected">#{tag}</span>) : <span className="kms-muted-guide">태그 없음</span>}
              </div>
              {post.summary ? (
                <section className="kms-content-section">
                  <h3>요약</h3>
                  <p className="kms-detail-summary">{post.summary}</p>
                </section>
              ) : null}
              <section className="kms-content-section">
                <h3>본문</h3>
                <div className="kms-detail-content kms-rich-content" dangerouslySetInnerHTML={{ __html: toKmsDisplayHtml(post.content_html || post.content) }} />
              </section>
              {post.source_url ? (
                <a className="kms-source-link" href={post.source_url} target="_blank" rel="noreferrer">참고 URL 새 창 열기</a>
              ) : null}
            </div>
            <div className="kms-detail-meta-card">
              <h3>메타 정보</h3>
              <dl>
                <div><dt>카테고리</dt><dd>{post.category_name || "미분류"}</dd></div>
                <div><dt>중요도</dt><dd>{post.importance}</dd></div>
                <div><dt>학습 상태</dt><dd>{post.learning_status}</dd></div>
                <div><dt>작성일</dt><dd>{post.created_at}</dd></div>
                <div><dt>수정일</dt><dd>{post.updated_at}</dd></div>
              </dl>
            </div>
          </article>
        </section>
      )}
    </div>
  );
}

export default KmsPostDetailPage;
