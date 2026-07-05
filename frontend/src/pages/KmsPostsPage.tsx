import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
import { sanitizeKmsHtml, toKmsPlainText } from "@/utils/kmsRichContent";

const emptyForm: KmsPostPayload = {
  category_id: 0,
  title: "",
  summary: "",
  content: "",
  source_url: "",
  importance: "보통",
  learning_status: "미정리",
  is_pinned: false,
  tags: "",
};

function KmsPostsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [categories, setCategories] = useState<KmsCategory[]>([]);
  const [posts, setPosts] = useState<KmsPost[]>([]);
  const [keyword, setKeyword] = useState("");
  const [categoryId, setCategoryId] = useState<number>(Number(searchParams.get("category_id") || 0));
  const [learningStatus, setLearningStatus] = useState("");
  const [importance, setImportance] = useState("");
  const [showForm, setShowForm] = useState(searchParams.get("new") === "1");
  const [form, setForm] = useState<KmsPostPayload>(emptyForm);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const activeCategory = useMemo(() => categories.find((item) => item.id === categoryId) ?? null, [categories, categoryId]);

  const loadCategories = async () => {
    const rows = await repositories.kms.listCategories();
    setCategories(rows);
    setForm((prev) => ({ ...prev, category_id: prev.category_id || rows[0]?.id || 0 }));
  };

  const loadPosts = async () => {
    setLoading(true);
    setMessage("");
    try {
      const rows = await repositories.kms.listPosts({
        keyword: keyword || undefined,
        category_id: categoryId || undefined,
        learning_status: learningStatus || undefined,
        importance: importance || undefined,
        is_active: true,
        limit: 200,
      });
      setPosts(rows);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "지식 게시글을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCategories();
  }, []);

  useEffect(() => {
    void loadPosts();
  }, [categoryId, learningStatus, importance]);

  const selectCategory = (nextCategoryId: number) => {
    setCategoryId(nextCategoryId);
    const next = new URLSearchParams(searchParams);
    if (nextCategoryId) next.set("category_id", String(nextCategoryId));
    else next.delete("category_id");
    next.delete("new");
    setSearchParams(next);
  };

  const resetFilters = () => {
    setKeyword("");
    setLearningStatus("");
    setImportance("");
    selectCategory(0);
  };

  const openForm = () => {
    setShowForm(true);
    const next = new URLSearchParams(searchParams);
    next.set("new", "1");
    setSearchParams(next);
  };

  const closeForm = () => {
    setShowForm(false);
    const next = new URLSearchParams(searchParams);
    next.delete("new");
    setSearchParams(next);
  };

  const savePost = async () => {
    const cleanContent = sanitizeKmsHtml(form.content);
    const contentText = toKmsPlainText(cleanContent);
    if (!form.category_id || !form.title.trim() || !contentText) {
      setMessage("카테고리, 제목, 본문은 필수입니다.");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      await repositories.kms.createPost({
        ...form,
        title: form.title.trim(),
        summary: form.summary || null,
        content: cleanContent,
        content_format: "html",
        content_html: cleanContent,
        content_text: contentText,
        source_url: form.source_url || null,
        tags: form.tags || "",
      });
      setForm({ ...emptyForm, category_id: categories[0]?.id || 0 });
      closeForm();
      await loadPosts();
      setMessage("지식글이 등록되었습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "지식글 등록에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="지식 게시판"
        description="주식과 자본시장 공부 내용을 카드형 지식글로 정리합니다."
        action={<button type="button" className="btn btn-primary" onClick={showForm ? closeForm : openForm}>{showForm ? "등록 취소" : "새 지식 등록"}</button>}
      />

      {message ? <div className="alert alert-warning">{message}</div> : null}

      {showForm ? (
        <section className="kms-panel kms-post-form-panel">
          <div className="kms-panel-header">
            <div>
              <h2 className="kms-panel-title">새 지식 등록</h2>
              <p className="kms-panel-description">기본 정보, 요약, 본문, 분류 정보를 나눠 입력합니다.</p>
            </div>
          </div>
          <div className="kms-form-section">
            <div className="kms-form-section-header">
              <h3>기본 정보</h3>
              <p>제목과 분류 기준을 지정합니다.</p>
            </div>
            <div className="kms-form-grid">
              <label className="kms-form-field">
                <span className="kms-form-label">제목 *</span>
                <input className="input kms-form-control" value={form.title} onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))} />
              </label>
              <label className="kms-form-field">
                <span className="kms-form-label">카테고리 *</span>
                <select className="select kms-form-control" value={form.category_id} onChange={(event) => setForm((prev) => ({ ...prev, category_id: Number(event.target.value) }))}>
                  {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                </select>
              </label>
              <label className="kms-form-field">
                <span className="kms-form-label">중요도</span>
                <select className="select kms-form-control" value={form.importance} onChange={(event) => setForm((prev) => ({ ...prev, importance: event.target.value as KmsImportance }))}>
                  {KMS_IMPORTANCE_OPTIONS.map((option) => <option key={option}>{option}</option>)}
                </select>
              </label>
              <label className="kms-form-field">
                <span className="kms-form-label">학습 상태</span>
                <select className="select kms-form-control" value={form.learning_status} onChange={(event) => setForm((prev) => ({ ...prev, learning_status: event.target.value as KmsLearningStatus }))}>
                  {KMS_LEARNING_STATUS_OPTIONS.map((option) => <option key={option}>{option}</option>)}
                </select>
              </label>
            </div>
          </div>
          <div className="kms-form-section">
            <div className="kms-form-section-header">
              <h3>요약</h3>
              <p>목록과 상세 상단에서 빠르게 읽을 한 줄 설명입니다.</p>
            </div>
            <label className="kms-form-field">
              <span className="kms-form-label">요약</span>
              <textarea className="textarea kms-form-control kms-summary-textarea" value={form.summary || ""} onChange={(event) => setForm((prev) => ({ ...prev, summary: event.target.value }))} />
            </label>
          </div>
          <div className="kms-form-section">
            <div className="kms-form-section-header">
              <h3>본문 작성 *</h3>
              <p>제목, 목록, 인용, 표, 링크, 이미지를 사용해 학습 내용을 구조화합니다.</p>
            </div>
            <KmsRichEditor value={form.content} onChange={(content) => setForm((prev) => ({ ...prev, content }))} />
          </div>
          <div className="kms-form-section">
            <div className="kms-form-section-header">
              <h3>분류/참고 정보</h3>
              <p>다시 찾기 쉬운 태그와 원문 링크를 남깁니다.</p>
            </div>
            <div className="kms-form-grid">
              <label className="kms-form-field">
                <span className="kms-form-label">태그</span>
                <input className="input kms-form-control" placeholder="단타, 거래량, 전고점" value={String(form.tags || "")} onChange={(event) => setForm((prev) => ({ ...prev, tags: event.target.value }))} />
                <small className="kms-form-help">쉼표로 구분해 입력하면 #태그로 정규화됩니다.</small>
              </label>
              <label className="kms-form-field">
                <span className="kms-form-label">참고 URL</span>
                <input className="input kms-form-control" value={form.source_url || ""} onChange={(event) => setForm((prev) => ({ ...prev, source_url: event.target.value }))} />
              </label>
              <label className="kms-check-field">
                <input type="checkbox" checked={form.is_pinned} onChange={(event) => setForm((prev) => ({ ...prev, is_pinned: event.target.checked }))} />
                <span>고정</span>
              </label>
            </div>
          </div>
          <div className="kms-action-row">
            <button type="button" className="btn btn-primary" onClick={() => void savePost()} disabled={saving}>{saving ? "저장 중..." : "저장"}</button>
            <button type="button" className="btn btn-secondary" onClick={closeForm}>취소</button>
          </div>
        </section>
      ) : null}

      <section className="kms-panel kms-filter-panel">
        <div className="kms-posts-layout">
          <aside className="kms-filter-sidebar">
            <div className="kms-sidebar-title">카테고리</div>
            <button type="button" className={!categoryId ? "active" : ""} onClick={() => selectCategory(0)}>
              <span>전체</span>
            </button>
            {categories.map((category) => (
              <button key={category.id} type="button" className={categoryId === category.id ? "active" : ""} onClick={() => selectCategory(category.id)}>
                <span>{category.name}</span>
                <small>{category.parent_id ? "하위분류" : "대분류"}</small>
              </button>
            ))}
          </aside>
          <div className="kms-post-list-panel">
            <div className="kms-search-control-box">
              <input
                className="input"
                value={keyword}
                placeholder="제목/요약/본문 검색"
                onChange={(event) => setKeyword(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void loadPosts();
                }}
              />
              <select className="select compact" value={learningStatus} onChange={(event) => setLearningStatus(event.target.value)}>
                <option value="">학습 상태</option>
                {KMS_LEARNING_STATUS_OPTIONS.map((option) => <option key={option}>{option}</option>)}
              </select>
              <select className="select compact" value={importance} onChange={(event) => setImportance(event.target.value)}>
                <option value="">중요도</option>
                {KMS_IMPORTANCE_OPTIONS.map((option) => <option key={option}>{option}</option>)}
              </select>
              <button type="button" className="btn btn-primary" onClick={() => void loadPosts()} disabled={loading}>검색</button>
              <button type="button" className="btn btn-secondary" onClick={resetFilters}>초기화</button>
            </div>
            <div className="kms-board-title-row">
              <strong>{activeCategory ? `${activeCategory.name} 지식` : "전체 지식"}</strong>
              <span>총 {posts.length.toLocaleString("ko-KR")}건</span>
            </div>
            <div className="kms-result-grid">
              {posts.map((post) => (
                <button key={post.id} type="button" className="kms-post-card" onClick={() => navigate(`/kms/posts/${post.id}`)}>
                  <span className="kms-post-card-meta">{post.category_name} · {post.updated_at}</span>
                  <strong>{post.is_pinned ? "★ " : ""}{post.title}</strong>
                  <p>{post.summary || toKmsPlainText(post.content).slice(0, 140)}</p>
                  <div className="kms-card-badges">
                    <StatusBadge label={post.importance} tone={post.importance === "핵심" ? "rose" : "slate"} />
                    <StatusBadge label={post.learning_status} tone={post.learning_status === "복습 필요" ? "amber" : "blue"} />
                  </div>
                  <span className="kms-tag-list">{post.tags.map((tag) => `#${tag}`).join(" ")}</span>
                </button>
              ))}
              {!posts.length ? (
                <div className="kms-empty-state">
                  <strong>조건에 맞는 지식글이 없습니다.</strong>
                  <span>검색어 또는 필터를 조정하거나 새 지식을 등록해 주세요.</span>
                  <button type="button" className="btn btn-primary" onClick={openForm}>새 지식 등록</button>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export default KmsPostsPage;
