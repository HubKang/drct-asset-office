import { useEffect, useMemo, useState } from "react";
import { BookOpen, ClipboardList, Filter, Plus, Search, Tags } from "lucide-react";
import { useNavigate } from "react-router-dom";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import {
  KMS_IMPORTANCE_OPTIONS,
  KMS_LEARNING_STATUS_OPTIONS,
  type KmsCategorySummary,
  type KmsHomeSummary,
  type KmsPost,
  type KmsRecentPost,
  type KmsTagMatchMode,
} from "@/types/kms";
import { toKmsPlainText } from "@/utils/kmsRichContent";

const emptySummary: KmsHomeSummary = {
  overall: {
    total_posts: 0,
    review_needed_count: 0,
    practice_candidate_count: 0,
    core_count: 0,
    recent_7d_count: 0,
  },
  categories: [],
  popular_tags: [],
  recent_posts: [],
  review_needed_posts: [],
  practice_candidate_posts: [],
};

const reviewNeededStatus = KMS_LEARNING_STATUS_OPTIONS[3];
const practiceCandidateStatus = KMS_LEARNING_STATUS_OPTIONS[4];
const coreImportance = KMS_IMPORTANCE_OPTIONS[3];

const splitTags = (value: string) =>
  value
    .split(",")
    .map((tag) => tag.trim().replace(/^#/, ""))
    .filter(Boolean);

const formatDate = (value: string | null | undefined) => {
  if (!value) return "수정 이력 없음";
  return value.replace("T", " ").slice(0, 16);
};

const makePostsPath = (params?: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `/kms/posts?${query}` : "/kms/posts";
};

type FlowCardProps = {
  title: string;
  description: string;
  posts: KmsRecentPost[];
  emptyText: string;
  onOpenPost: (postId: number) => void;
  onOpenList: () => void;
};

function FlowCard({ title, description, posts, emptyText, onOpenPost, onOpenList }: FlowCardProps) {
  const visiblePosts = posts.slice(0, 5);
  return (
    <section className="kms-home-flow-card">
      <div className="kms-home-section-head compact">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <button type="button" className="kms-home-link-button" onClick={onOpenList}>전체</button>
      </div>
      <div className="kms-home-flow-list">
        {visiblePosts.length ? (
          visiblePosts.map((post) => (
            <button key={`${title}-${post.post_id}`} type="button" className="kms-home-flow-item" onClick={() => onOpenPost(post.post_id)}>
              <strong>{post.title}</strong>
              <span>{post.category_name || "미분류"} · {formatDate(post.updated_at)}</span>
            </button>
          ))
        ) : (
          <div className="kms-home-empty compact">{emptyText}</div>
        )}
      </div>
    </section>
  );
}

function KmsHomePage() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<KmsHomeSummary>(emptySummary);
  const [tagInput, setTagInput] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [matchMode, setMatchMode] = useState<KmsTagMatchMode>("AND");
  const [searchResults, setSearchResults] = useState<KmsPost[]>([]);
  const [hasSearchedTags, setHasSearchedTags] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const statCards = useMemo(
    () => [
      {
        label: "전체 지식글",
        value: summary.overall.total_posts,
        help: "등록된 활성 지식글",
        path: makePostsPath(),
      },
      {
        label: "복습 필요",
        value: summary.overall.review_needed_count,
        help: "다시 확인할 글",
        path: makePostsPath({ learning_status: reviewNeededStatus }),
      },
      {
        label: "실전 적용 후보",
        value: summary.overall.practice_candidate_count,
        help: "매매에 적용해 볼 글",
        path: makePostsPath({ learning_status: practiceCandidateStatus }),
      },
      {
        label: "핵심 지식",
        value: summary.overall.core_count,
        help: "중요도가 핵심인 글",
        path: makePostsPath({ importance: coreImportance }),
      },
      {
        label: "최근 7일",
        value: summary.overall.recent_7d_count,
        help: "최근 작성 또는 수정",
        path: makePostsPath({ recent: 7 }),
      },
    ],
    [summary],
  );

  const popularTags = summary.popular_tags.slice(0, 10);
  const tagPreviewResults = searchResults.slice(0, 5);

  const load = async () => {
    setLoading(true);
    setMessage("");
    try {
      const data = await repositories.kms.getHomeSummary();
      setSummary(data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "KMS 요약을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const addTags = (tags: string[]) => {
    setSelectedTags((prev) => Array.from(new Set([...prev, ...tags])));
  };

  const removeTag = (tag: string) => {
    setSelectedTags((prev) => prev.filter((item) => item !== tag));
  };

  const runTagSearch = async () => {
    const mergedTags = Array.from(new Set([...selectedTags, ...splitTags(tagInput)]));
    setSelectedTags(mergedTags);
    setTagInput("");
    setHasSearchedTags(true);
    if (!mergedTags.length) {
      setSearchResults([]);
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      const rows = await repositories.kms.searchPostsByTags({ tag_names: mergedTags, match_mode: matchMode });
      setSearchResults(rows);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "태그 검색에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const openPost = (postId: number) => navigate(`/kms/posts/${postId}`);
  const openCategory = (category: KmsCategorySummary) => navigate(makePostsPath({ category_id: category.category_id }));
  const openTagResults = () => navigate(makePostsPath({ keyword: selectedTags.join(" ") }));

  return (
    <div className="kms-home-page">
      <section className="kms-home-hero">
        <div>
          <span className="kms-home-eyebrow">Knowledge dashboard</span>
          <h1>DrCT KMS</h1>
          <p>주식과 자본시장 공부 내용을 누적하고, 태그와 카테고리로 다시 찾는 지식 대시보드입니다.</p>
        </div>
        <div className="kms-home-actions">
          <button type="button" className="btn btn-primary" onClick={() => navigate("/kms/posts?new=1")}>
            <Plus size={16} aria-hidden="true" />새 지식글 등록
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => navigate("/kms/posts")}>
            <ClipboardList size={16} aria-hidden="true" />지식 게시판
          </button>
        </div>
      </section>

      {message ? <div className="alert alert-warning">{message}</div> : null}

      <section className="kms-home-kpi-grid" aria-label="KMS 요약">
        {statCards.map((card) => (
          <button key={card.label} type="button" className="kms-home-kpi-card" onClick={() => navigate(card.path)}>
            <span>{card.label}</span>
            <strong className={card.value === 0 ? "muted" : ""}>{card.value.toLocaleString("ko-KR")}</strong>
            <small>{card.help}</small>
          </button>
        ))}
      </section>

      <section className="kms-home-search-section">
        <div className="kms-home-section-head">
          <div>
            <h2><Tags size={18} aria-hidden="true" />태그로 지식 찾기</h2>
            <p>여러 태그를 조합해 관련 지식글을 빠르게 좁혀봅니다.</p>
          </div>
        </div>
        <div className="kms-home-search-row">
          <input
            className="input"
            value={tagInput}
            placeholder="태그를 쉼표로 입력하세요. 예: 실적, 수급"
            onChange={(event) => setTagInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void runTagSearch();
            }}
          />
          <select className="select compact" value={matchMode} onChange={(event) => setMatchMode(event.target.value as KmsTagMatchMode)}>
            <option value="AND">AND</option>
            <option value="OR">OR</option>
          </select>
          <button type="button" className="btn btn-primary" onClick={() => void runTagSearch()} disabled={loading}>
            <Search size={16} aria-hidden="true" />검색
          </button>
        </div>
        <div className="kms-home-tag-area">
          <div>
            <span className="kms-home-mini-title">인기 태그</span>
            <div className="kms-home-chip-row">
              {popularTags.length ? (
                popularTags.map((tag) => (
                  <button key={tag.id} type="button" className="kms-chip" onClick={() => addTags([tag.name])}>
                    #{tag.name} <span>{tag.use_count}</span>
                  </button>
                ))
              ) : (
                <span className="kms-home-muted">아직 사용된 태그가 없습니다.</span>
              )}
            </div>
          </div>
          {selectedTags.length ? (
            <div>
              <span className="kms-home-mini-title">선택 태그</span>
              <div className="kms-home-chip-row">
                {selectedTags.map((tag) => (
                  <button key={tag} type="button" className="kms-chip selected" onClick={() => removeTag(tag)}>
                    #{tag} <span aria-hidden="true">x</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
        <div className="kms-home-quick-filters" aria-label="빠른 필터">
          <button type="button" onClick={() => navigate(makePostsPath({ learning_status: reviewNeededStatus }))}><Filter size={14} aria-hidden="true" />복습 필요</button>
          <button type="button" onClick={() => navigate(makePostsPath({ learning_status: practiceCandidateStatus }))}>실전 적용 후보</button>
          <button type="button" onClick={() => navigate(makePostsPath({ importance: coreImportance }))}>핵심 지식</button>
          <button type="button" onClick={() => navigate(makePostsPath({ recent: 7 }))}>최근 7일</button>
          <button type="button" onClick={() => navigate("/kms/posts")}>전체 보기</button>
        </div>
        {hasSearchedTags ? (
          <div className="kms-home-tag-results">
            <div className="kms-home-section-head compact">
              <div>
                <h2>검색 결과 미리보기</h2>
                <p>{searchResults.length.toLocaleString("ko-KR")}건 중 최대 5건을 표시합니다.</p>
              </div>
              {searchResults.length ? <button type="button" className="kms-home-link-button" onClick={openTagResults}>전체 결과 보기</button> : null}
            </div>
            {tagPreviewResults.length ? (
              <div className="kms-home-result-list">
                {tagPreviewResults.map((post) => (
                  <button key={post.id} type="button" className="kms-home-result-item" onClick={() => openPost(post.id)}>
                    <span>{post.category_name || "미분류"} · {post.importance} · {post.learning_status}</span>
                    <strong>{post.title}</strong>
                    <p>{post.summary || toKmsPlainText(post.content).slice(0, 110)}</p>
                  </button>
                ))}
              </div>
            ) : (
              <div className="kms-home-empty compact">조건에 맞는 지식글이 없습니다.</div>
            )}
          </div>
        ) : null}
      </section>

      <section className="kms-home-category-section">
        <div className="kms-home-section-head">
          <div>
            <h2><BookOpen size={18} aria-hidden="true" />대분류 카테고리 현황</h2>
            <p>카테고리별 글 수와 학습 흐름을 한 줄 지표로 확인합니다.</p>
          </div>
        </div>
        <div className="kms-home-category-grid">
          {summary.categories.length ? (
            summary.categories.map((category) => (
              <button key={category.category_id} type="button" className="kms-home-category-card" onClick={() => openCategory(category)}>
                <div className="kms-home-category-top">
                  <strong>{category.category_name}</strong>
                  <StatusBadge label={`${category.total_posts}글`} tone="slate" />
                </div>
                {category.total_posts ? (
                  <div className="kms-home-category-metrics">
                    <span>핵심 <b>{category.core_count}</b></span>
                    <span>복습 <b>{category.review_needed_count}</b></span>
                    <span>후보 <b>{category.practice_candidate_count}</b></span>
                    <span>최근 <b>{category.recent_7d_count}</b></span>
                  </div>
                ) : (
                  <p className="kms-home-category-empty">아직 등록된 지식글이 없습니다.</p>
                )}
                <div className="kms-home-category-tags">
                  {category.top_tags.length ? category.top_tags.slice(0, 4).map((tag) => <span key={tag}>#{tag}</span>) : <span>대표 태그 없음</span>}
                </div>
                <small className="kms-home-category-updated">마지막 수정 {formatDate(category.last_updated_at)}</small>
              </button>
            ))
          ) : (
            <div className="kms-home-empty">표시할 카테고리가 없습니다.</div>
          )}
        </div>
      </section>

      <div className="kms-home-flow-grid">
        <FlowCard
          title="최근 작성/수정"
          description="가장 최근 움직인 지식글"
          posts={summary.recent_posts}
          emptyText="아직 최근 지식글이 없습니다."
          onOpenPost={openPost}
          onOpenList={() => navigate(makePostsPath({ recent: 7 }))}
        />
        <FlowCard
          title="복습 필요"
          description="다시 확인할 학습 항목"
          posts={summary.review_needed_posts}
          emptyText="복습 필요로 표시된 글이 없습니다."
          onOpenPost={openPost}
          onOpenList={() => navigate(makePostsPath({ learning_status: reviewNeededStatus }))}
        />
        <FlowCard
          title="실전 적용 후보"
          description="매매 계획에 연결할 후보"
          posts={summary.practice_candidate_posts}
          emptyText="실전 적용 후보 글이 없습니다."
          onOpenPost={openPost}
          onOpenList={() => navigate(makePostsPath({ learning_status: practiceCandidateStatus }))}
        />
      </div>
    </div>
  );
}

export default KmsHomePage;