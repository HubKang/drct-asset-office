import { useEffect, useMemo, useState, type CSSProperties } from "react";
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
import { sanitizeKmsHtml, toKmsDisplayHtml, toKmsEditableHtml, toKmsPlainText } from "@/utils/kmsRichContent";

const pageSize = 20;
const categoryAccentColors = ["#2563eb", "#f97316", "#8b5cf6", "#10b981", "#06b6d4", "#6366f1", "#ec4899", "#64748b", "#a855f7", "#0f766e"];

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

const toKmsUserMessage = (error: unknown, fallback: string) => {
  const message = error instanceof Error ? error.message : "";
  if (
    message.includes("goal_text")
    || message.includes("gpt_result_text")
    || message.includes("parsed_goal")
    || message.includes("요청 형식이 맞지 않습니다")
  ) {
    return "지식 게시판 데이터를 불러오는 중 문제가 발생했습니다. 화면을 다시 조회해 주세요. 문제가 반복되면 관리자에게 문의해 주세요.";
  }
  return message || fallback;
};

function KmsPostsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [categories, setCategories] = useState<KmsCategory[]>([]);
  const [posts, setPosts] = useState<KmsPost[]>([]);
  const [categoryCounts, setCategoryCounts] = useState<Record<number, number>>({});
  const [totalPostCount, setTotalPostCount] = useState(0);
  const [keyword, setKeyword] = useState(searchParams.get("keyword") || "");
  const [categoryId, setCategoryId] = useState<number>(Number(searchParams.get("category_id") || 0));
  const [learningStatus, setLearningStatus] = useState(searchParams.get("learning_status") || "");
  const [importance, setImportance] = useState(searchParams.get("importance") || "");
  const [currentPage, setCurrentPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);
  const [selectedPost, setSelectedPost] = useState<KmsPost | null>(null);
  const [drawerEditing, setDrawerEditing] = useState(false);
  const [drawerForm, setDrawerForm] = useState<KmsPostPayload | null>(null);
  const [showForm, setShowForm] = useState(searchParams.get("new") === "1");
  const [form, setForm] = useState<KmsPostPayload>(emptyForm);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [drawerSaving, setDrawerSaving] = useState(false);
  const [drawerDeleting, setDrawerDeleting] = useState(false);
  const [message, setMessage] = useState("");

  const activeCategory = useMemo(() => categories.find((item) => item.id === categoryId) ?? null, [categories, categoryId]);
  const totalPages = Math.max(1, Math.ceil(posts.length / pageSize));
  const pagedPosts = useMemo(() => posts.slice((currentPage - 1) * pageSize, currentPage * pageSize), [currentPage, posts]);
  const pageNumbers = useMemo(() => {
    const start = Math.max(1, currentPage - 2);
    const end = Math.min(totalPages, start + 4);
    return Array.from({ length: end - start + 1 }, (_, index) => start + index);
  }, [currentPage, totalPages]);

  const loadCategories = async () => {
    const rows = await repositories.kms.listCategories();
    setCategories(rows);
    setForm((prev) => ({ ...prev, category_id: prev.category_id || rows[0]?.id || 0 }));
  };

  const loadCategoryCounts = async () => {
    try {
      const rows = await repositories.kms.listPosts({ is_active: true, limit: 1000 });
      const nextCounts: Record<number, number> = {};
      rows.forEach((post) => {
        nextCounts[post.category_id] = (nextCounts[post.category_id] || 0) + 1;
      });
      setCategoryCounts(nextCounts);
      setTotalPostCount(rows.length);
    } catch (error) {
      setMessage(toKmsUserMessage(error, "카테고리별 지식글 수를 불러오지 못했습니다."));
    }
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
      setCurrentPage(1);
      setSelectedPost((prev) => (prev && rows.some((post) => post.id === prev.id) ? prev : null));
    } catch (error) {
      setMessage(toKmsUserMessage(error, "지식 게시글을 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCategories();
    void loadCategoryCounts();
  }, []);

  useEffect(() => {
    void loadPosts();
  }, [categoryId, learningStatus, importance, reloadKey]);

  useEffect(() => {
    if (!selectedPost) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedPost(null);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [selectedPost]);

  useEffect(() => {
    if (!selectedPost) {
      setDrawerEditing(false);
      setDrawerForm(null);
      return;
    }
    setDrawerEditing(false);
    setDrawerForm({
      category_id: selectedPost.category_id,
      title: selectedPost.title,
      summary: selectedPost.summary || "",
      content: toKmsEditableHtml(selectedPost.content_html || selectedPost.content),
      source_url: selectedPost.source_url || "",
      importance: selectedPost.importance,
      learning_status: selectedPost.learning_status,
      is_pinned: selectedPost.is_pinned,
      is_active: selectedPost.is_active,
      tags: selectedPost.tags.join(", "),
    });
  }, [selectedPost]);

  const selectCategory = (nextCategoryId: number) => {
    setCurrentPage(1);
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
    setCurrentPage(1);
    selectCategory(0);
    setReloadKey((prev) => prev + 1);
  };

  const runSearch = async () => {
    setCurrentPage(1);
    setReloadKey((prev) => prev + 1);
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
      setMessage(toKmsUserMessage(error, "지식글 등록에 실패했습니다."));
    } finally {
      setSaving(false);
    }
  };

  const saveDrawerPost = async () => {
    if (!selectedPost || !drawerForm) return;
    const cleanContent = sanitizeKmsHtml(drawerForm.content);
    const contentText = toKmsPlainText(cleanContent);
    if (!drawerForm.category_id || !drawerForm.title.trim() || !contentText) {
      setMessage("카테고리, 제목, 본문은 필수입니다.");
      return;
    }
    setDrawerSaving(true);
    setMessage("");
    try {
      const updated = await repositories.kms.updatePost(selectedPost.id, {
        ...drawerForm,
        title: drawerForm.title.trim(),
        summary: drawerForm.summary || null,
        content: cleanContent,
        content_format: "html",
        content_html: cleanContent,
        content_text: contentText,
        source_url: drawerForm.source_url || null,
      });
      setSelectedPost(updated);
      setDrawerForm({
        category_id: updated.category_id,
        title: updated.title,
        summary: updated.summary || "",
        content: toKmsEditableHtml(updated.content_html || updated.content),
        source_url: updated.source_url || "",
        importance: updated.importance,
        learning_status: updated.learning_status,
        is_pinned: updated.is_pinned,
        is_active: updated.is_active,
        tags: updated.tags.join(", "),
      });
      setPosts((prev) => prev.map((post) => (post.id === updated.id ? updated : post)));
      await loadCategoryCounts();
      setDrawerEditing(false);
      setMessage("지식글이 수정되었습니다.");
    } catch (error) {
      setMessage(toKmsUserMessage(error, "지식글 수정에 실패했습니다."));
    } finally {
      setDrawerSaving(false);
    }
  };

  const deleteDrawerPost = async () => {
    if (!selectedPost) return;
    if (!window.confirm("이 지식글을 삭제하시겠습니까? 삭제한 글은 목록에서 숨겨집니다.")) return;
    setDrawerDeleting(true);
    setMessage("");
    try {
      const deleted = await repositories.kms.deactivatePost(selectedPost.id);
      setPosts((prev) => prev.filter((post) => post.id !== deleted.id));
      setSelectedPost(null);
      setDrawerEditing(false);
      setDrawerForm(null);
      await loadCategoryCounts();
      setMessage("지식글이 삭제되었습니다.");
    } catch (error) {
      setMessage(toKmsUserMessage(error, "지식글 삭제에 실패했습니다."));
    } finally {
      setDrawerDeleting(false);
    }
  };
  return (
    <div className="space-y-4">
      <PageHeader
        title="지식 게시판"
        description="주식과 자본시장 공부 내용을 목록으로 빠르게 훑고 상세를 확인합니다."
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
            <div className="kms-form-grid kms-basic-info-grid">
              <label className="kms-form-field kms-form-wide">
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
              <textarea className="textarea kms-form-control kms-summary-textarea" value={form.summary || ""} onChange={(event) => setForm((prev) => ({ ...prev, summary: event.target.value }))} />
            </label>
          </div>
          <div className="kms-form-section">
            <div className="kms-form-section-header">
              <h3>본문 작성 *</h3>
              <p>제목, 목록, 인용, 표, 링크, 이미지를 사용해 학습 내용을 구조화합니다.</p>
            </div>
            <KmsRichEditor resetKey={showForm ? "new-kms-post" : "closed-new-kms-post"} value={form.content} selectLocalImage={() => repositories.kms.selectLocalImage()} onChange={(content) => setForm((prev) => ({ ...prev, content }))} />
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
          <aside className="kms-filter-sidebar kms-posts-category-panel">
            <div className="kms-posts-category-header">
              <strong>카테고리</strong>
              <span className="kms-posts-category-description">분류별 지식글을 빠르게 탐색합니다.</span>
            </div>
            <div className="kms-posts-category-list">
              <button
                type="button"
                className={!categoryId ? "kms-posts-category-row kms-posts-category-row-active" : "kms-posts-category-row"}
                style={{ "--category-accent": "#2563eb" } as CSSProperties}
                onClick={() => selectCategory(0)}
              >
                <span className="kms-posts-category-dot" aria-hidden="true" />
                <span className="kms-posts-category-name">전체</span>
                <span className={totalPostCount ? "kms-posts-category-count has-posts" : "kms-posts-category-count"}>{totalPostCount.toLocaleString("ko-KR")}</span>
              </button>
              <div className="kms-posts-category-divider" />
              {categories.map((category, index) => {
                const count = categoryCounts[category.id] || 0;
                return (
                  <button
                    key={category.id}
                    type="button"
                    className={categoryId === category.id ? "kms-posts-category-row kms-posts-category-row-active" : "kms-posts-category-row"}
                    style={{ "--category-accent": categoryAccentColors[index % categoryAccentColors.length] } as CSSProperties}
                    onClick={() => selectCategory(category.id)}
                  >
                    <span className="kms-posts-category-dot" aria-hidden="true" />
                    <span className="kms-posts-category-name">{category.name}</span>
                    <span className={count ? "kms-posts-category-count has-posts" : "kms-posts-category-count"}>{count.toLocaleString("ko-KR")}</span>
                  </button>
                );
              })}
            </div>
            <div className="kms-posts-category-footer">
              <span>카테고리는 KMS 설정에서 관리합니다.</span>
              <button type="button" className="kms-posts-category-settings-link" onClick={() => navigate("/kms/settings")}>KMS 설정으로 이동</button>
            </div>
          </aside>
          <div className="kms-post-list-panel">
            <div className="kms-search-control-box">
              <input
                className="input"
                value={keyword}
                placeholder="제목/요약/본문 검색"
                onChange={(event) => setKeyword(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void runSearch();
                }}
              />
              <select className="select compact" value={learningStatus} onChange={(event) => { setCurrentPage(1); setLearningStatus(event.target.value); }}>
                <option value="">학습 상태</option>
                {KMS_LEARNING_STATUS_OPTIONS.map((option) => <option key={option}>{option}</option>)}
              </select>
              <select className="select compact" value={importance} onChange={(event) => { setCurrentPage(1); setImportance(event.target.value); }}>
                <option value="">중요도</option>
                {KMS_IMPORTANCE_OPTIONS.map((option) => <option key={option}>{option}</option>)}
              </select>
              <button type="button" className="btn btn-primary" onClick={() => void runSearch()} disabled={loading}>검색</button>
              <button type="button" className="btn btn-secondary" onClick={resetFilters}>초기화</button>
            </div>
            <div className="kms-board-title-row">
              <strong>{activeCategory ? `${activeCategory.name} 지식` : "전체 지식"}</strong>
              <span>총 {posts.length.toLocaleString("ko-KR")}건</span>
            </div>
            <div className="kms-posts-table" role="table" aria-label="지식글 목록">
              <div className="kms-posts-table-head" role="row">
                <span>제목</span>
                <span>수정일</span>
              </div>
              {pagedPosts.map((post) => (
                <button key={post.id} type="button" className={selectedPost?.id === post.id ? "kms-posts-row active" : "kms-posts-row"} onClick={() => setSelectedPost(post)}>
                  <span className="kms-posts-title-cell">
                    <strong>{post.is_pinned ? "★ " : ""}{post.title}</strong>
                    <small>
                      {post.category_name || "미분류"} · {post.importance} · {post.learning_status}
                      {post.tags.length ? ` · ${post.tags.map((tag) => `#${tag}`).join(" ")}` : ""}
                    </small>
                    <em>{post.summary || toKmsPlainText(post.content).slice(0, 100)}</em>
                  </span>
                  <span className="kms-posts-date-cell">{post.updated_at}</span>
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
            {posts.length ? (
              <div className="kms-pagination">
                <span>{currentPage.toLocaleString("ko-KR")} / {totalPages.toLocaleString("ko-KR")} 페이지</span>
                <button type="button" className="btn btn-secondary" disabled={currentPage <= 1} onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}>이전</button>
                {pageNumbers.map((page) => (
                  <button key={page} type="button" className={page === currentPage ? "kms-page-button active" : "kms-page-button"} onClick={() => setCurrentPage(page)}>{page}</button>
                ))}
                <button type="button" className="btn btn-secondary" disabled={currentPage >= totalPages} onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}>다음</button>
              </div>
            ) : null}
          </div>
        </div>
      </section>
      {selectedPost ? (
        <div className="kms-detail-drawer-backdrop" onClick={() => setSelectedPost(null)}>
          <aside className="kms-detail-drawer" onClick={(event) => event.stopPropagation()}>
            <div className="kms-detail-drawer-header">
              <div>
                <h2>{drawerEditing ? "지식글 수정" : selectedPost.title}</h2>
                <p>{selectedPost.category_name || "미분류"} · {selectedPost.importance} · {selectedPost.learning_status}</p>
              </div>
              <div className="kms-detail-drawer-actions">
                {drawerEditing ? (
                  <button type="button" className="btn btn-primary" onClick={() => void saveDrawerPost()} disabled={drawerSaving}>
                    {drawerSaving ? "저장 중..." : "저장"}
                  </button>
                ) : (
                  <>
                    <button type="button" className="btn btn-primary" onClick={() => setDrawerEditing(true)} disabled={drawerDeleting}>
                      수정
                    </button>
                    <button type="button" className="btn btn-danger" onClick={() => void deleteDrawerPost()} disabled={drawerDeleting}>
                      {drawerDeleting ? "삭제 중..." : "삭제"}
                    </button>
                  </>
                )}
                <button type="button" className="btn btn-secondary kms-detail-drawer-close" onClick={() => setSelectedPost(null)} disabled={drawerSaving || drawerDeleting}>
                  닫기
                </button>
              </div>
            </div>
            <div className="kms-detail-drawer-body">
              {drawerEditing && drawerForm ? (
                <div className="kms-detail-drawer-edit-form">
                  <div className="kms-form-section">
                    <div className="kms-form-section-header">
                      <h3>기본 정보</h3>
                      <p>제목, 카테고리, 중요도, 학습 상태를 수정합니다.</p>
                    </div>
                    <div className="kms-form-grid kms-basic-info-grid">
                      <label className="kms-form-field kms-form-wide">
                        <span className="kms-form-label">제목 *</span>
                        <input className="input kms-form-control" value={drawerForm.title} onChange={(event) => setDrawerForm((prev) => prev && ({ ...prev, title: event.target.value }))} />
                      </label>
                      <label className="kms-form-field">
                        <span className="kms-form-label">카테고리 *</span>
                        <select className="select kms-form-control" value={drawerForm.category_id} onChange={(event) => setDrawerForm((prev) => prev && ({ ...prev, category_id: Number(event.target.value) }))}>
                          {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                        </select>
                      </label>
                      <label className="kms-form-field">
                        <span className="kms-form-label">중요도</span>
                        <select className="select kms-form-control" value={drawerForm.importance} onChange={(event) => setDrawerForm((prev) => prev && ({ ...prev, importance: event.target.value as KmsImportance }))}>
                          {KMS_IMPORTANCE_OPTIONS.map((option) => <option key={option}>{option}</option>)}
                        </select>
                      </label>
                      <label className="kms-form-field">
                        <span className="kms-form-label">학습 상태</span>
                        <select className="select kms-form-control" value={drawerForm.learning_status} onChange={(event) => setDrawerForm((prev) => prev && ({ ...prev, learning_status: event.target.value as KmsLearningStatus }))}>
                          {KMS_LEARNING_STATUS_OPTIONS.map((option) => <option key={option}>{option}</option>)}
                        </select>
                      </label>
                    </div>
                  </div>
                  <div className="kms-form-section">
                    <div className="kms-form-section-header">
                      <h3>요약</h3>
                      <p>목록과 상세 상단에 표시할 설명입니다.</p>
                    </div>
                    <label className="kms-form-field">
                      <textarea className="textarea kms-form-control kms-summary-textarea" value={drawerForm.summary || ""} onChange={(event) => setDrawerForm((prev) => prev && ({ ...prev, summary: event.target.value }))} />
                    </label>
                  </div>
                  <div className="kms-form-section">
                    <div className="kms-form-section-header">
                      <h3>본문 작성 *</h3>
                      <p>본문과 첨부 이미지를 drawer 안에서 바로 수정합니다.</p>
                    </div>
                    <KmsRichEditor resetKey={`drawer-${selectedPost.id}`} value={drawerForm.content} selectLocalImage={() => repositories.kms.selectLocalImage()} onChange={(content) => setDrawerForm((prev) => prev && ({ ...prev, content }))} />
                  </div>
                  <div className="kms-form-section">
                    <div className="kms-form-section-header">
                      <h3>분류/참고 정보</h3>
                      <p>태그, 참고 URL, 고정 여부를 관리합니다.</p>
                    </div>
                    <div className="kms-form-grid">
                      <label className="kms-form-field">
                        <span className="kms-form-label">태그</span>
                        <input className="input kms-form-control" value={String(drawerForm.tags || "")} onChange={(event) => setDrawerForm((prev) => prev && ({ ...prev, tags: event.target.value }))} />
                      </label>
                      <label className="kms-form-field">
                        <span className="kms-form-label">참고 URL</span>
                        <input className="input kms-form-control" value={drawerForm.source_url || ""} onChange={(event) => setDrawerForm((prev) => prev && ({ ...prev, source_url: event.target.value }))} />
                      </label>
                      <label className="kms-check-field">
                        <input type="checkbox" checked={drawerForm.is_pinned} onChange={(event) => setDrawerForm((prev) => prev && ({ ...prev, is_pinned: event.target.checked }))} />
                        <span>고정</span>
                      </label>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <div className="kms-card-badges">
                    <StatusBadge label={selectedPost.category_name || "미분류"} tone="slate" />
                    <StatusBadge label={selectedPost.importance} tone={selectedPost.importance === "핵심" ? "rose" : "blue"} />
                    <StatusBadge label={selectedPost.learning_status} tone={selectedPost.learning_status === "복습 필요" ? "amber" : "emerald"} />
                    {selectedPost.is_pinned ? <StatusBadge label="고정" tone="blue" /> : null}
                  </div>
                  <div className="kms-chip-row">
                    {selectedPost.tags.length ? selectedPost.tags.map((tag) => <span key={tag} className="kms-chip static">#{tag}</span>) : <span className="kms-muted-guide">태그 없음</span>}
                  </div>
                  {selectedPost.summary ? (
                    <section className="kms-content-section">
                      <h3>요약</h3>
                      <p className="kms-detail-summary">{selectedPost.summary}</p>
                    </section>
                  ) : null}
                  <section className="kms-content-section">
                    <h3>본문</h3>
                    <div className="kms-detail-content kms-rich-content" dangerouslySetInnerHTML={{ __html: toKmsDisplayHtml(selectedPost.content_html || selectedPost.content) }} />
                  </section>
                  {selectedPost.source_url ? (
                    <a className="kms-source-link" href={selectedPost.source_url} target="_blank" rel="noreferrer">참고 URL 새 창 열기</a>
                  ) : null}
                  <div className="kms-detail-drawer-meta">
                    <span>작성일 <b>{selectedPost.created_at}</b></span>
                    <span>수정일 <b>{selectedPost.updated_at}</b></span>
                  </div>
                </>
              )}
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

export default KmsPostsPage;
