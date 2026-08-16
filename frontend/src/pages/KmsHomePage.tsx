import { useEffect, useMemo, useState } from "react";
import { BookOpen, Check, ClipboardList, Info, Plus, Search, Tags, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import {
  type KmsCategorySummary,
  type KmsHomeSummary,
  type KmsRecentPost,
  type KmsTagMatchMode,
} from "@/types/kms";

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

const splitTags = (value: string) =>
  value
    .split(",")
    .map((tag) => tag.trim().replace(/^#/, ""))
    .filter(Boolean);

const mergeTags = (...groups: string[][]) => {
  const seen = new Set<string>();
  return groups.flat().map((tag) => tag.trim().replace(/^#+/, "")).filter((tag) => {
    const key = tag.toLocaleLowerCase("ko-KR");
    if (!tag || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

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
        path: makePostsPath({ status_code: "VERIFYING" }),
      },
      {
        label: "실전 적용 후보",
        value: summary.overall.practice_candidate_count,
        help: "매매에 적용해 볼 글",
        path: makePostsPath({ status_code: "APPLIED" }),
      },
      {
        label: "핵심 지식",
        value: summary.overall.core_count,
        help: "중요도가 핵심인 글",
        path: makePostsPath({ importance_code: "CORE" }),
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

  const popularTags = summary.popular_tags.filter((tag) => tag.use_count > 0).slice(0, 12);
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
    setSelectedTags((prev) => mergeTags(prev, tags));
  };

  const removeTag = (tag: string) => {
    const key = tag.toLocaleLowerCase("ko-KR");
    setSelectedTags((prev) => prev.filter((item) => item.toLocaleLowerCase("ko-KR") !== key));
  };

  const runTagSearch = () => {
    const mergedTags = mergeTags(selectedTags, splitTags(tagInput));
    setSelectedTags(mergedTags);
    setTagInput("");
    navigate(makePostsPath({ tags: mergedTags.join(","), match_mode: matchMode }));
  };

  const commitTagInput = () => {
    const tags = splitTags(tagInput);
    if (!tags.length) return false;
    addTags(tags);
    setTagInput("");
    return true;
  };

  const openPost = (postId: number) => navigate(makePostsPath({ item_id: postId }));
  const openCategory = (category: KmsCategorySummary) => navigate(makePostsPath({ category_id: category.category_id }));

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
        <div className="kms-home-tag-input-row">
          <Search className="kms-home-tag-input-icon" size={18} aria-hidden="true" />
          <input
            className="input"
            value={tagInput}
            placeholder="태그 추가 또는 검색… (Enter 또는 쉼표)"
            onChange={(event) => setTagInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === ",") {
                event.preventDefault();
                commitTagInput();
              }
              if (event.key === "Enter") {
                event.preventDefault();
                if (!commitTagInput()) runTagSearch();
              }
            }}
            aria-label="태그 추가"
          />
        </div>
        <div className="kms-home-tag-box kms-home-popular-tags">
          <div className="kms-home-tag-box-header">
            <div>
              <h3>인기 태그</h3>
              <p>자주 등록된 태그를 선택하세요.</p>
            </div>
          </div>
          <div className="kms-home-chip-row">
            {popularTags.length ? (
              popularTags.map((tag) => {
                const isSelected = selectedTags.some((selected) => selected.toLocaleLowerCase("ko-KR") === tag.name.toLocaleLowerCase("ko-KR"));
                return (
                  <button
                    key={tag.id}
                    type="button"
                    className={`kms-chip kms-popular-tag-chip ${isSelected ? "selected" : ""}`}
                    aria-pressed={isSelected}
                    aria-label={`${tag.name} 태그 ${isSelected ? "선택 해제" : "선택"}`}
                    onClick={() => isSelected ? removeTag(tag.name) : addTags([tag.name])}
                  >
                    {isSelected ? <Check size={13} aria-hidden="true" /> : null}
                    <span className="kms-popular-tag-name">#{tag.name}</span>
                    <span className="kms-popular-tag-count">{tag.use_count}</span>
                  </button>
                );
              })
            ) : (
              <span className="kms-home-muted">아직 사용된 태그가 없습니다.</span>
            )}
          </div>
        </div>
        <div className="kms-home-tag-box kms-home-selected-tags">
          <h3 className="kms-selected-tag-title">선택 태그</h3>
          <div className="kms-selected-tags-content">
            {selectedTags.length ? (
              <div className="kms-home-chip-row">
                {selectedTags.map((tag) => (
                  <span key={tag} className="kms-selected-tag-chip">
                    <span title={`#${tag}`}>#{tag}</span>
                    <button type="button" onClick={() => removeTag(tag)} aria-label={`선택 태그 ${tag} 제거`}><X size={12} aria-hidden="true" /></button>
                  </span>
                ))}
              </div>
            ) : (
              <p className="kms-selected-tags-empty">인기 태그를 누르거나 위 입력창에서 태그를 추가하세요.</p>
            )}
            <div className="kms-selected-tag-actions">
              <button
                type="button"
                className="kms-tag-mode-help"
                aria-label="AND와 OR 검색 조건 안내"
                title={'AND: 선택한 모든 태그가 포함된 지식\nOR: 선택한 태그 중 하나 이상 포함된 지식'}
              >
                <Info size={14} aria-hidden="true" />
              </button>
              <div className={`kms-tag-mode-toggle ${selectedTags.length < 2 ? "muted" : ""}`} aria-label="태그 조합 조건">
                {(["AND", "OR"] as KmsTagMatchMode[]).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    className={matchMode === mode ? "active" : ""}
                    aria-label={`${mode} 검색 조건 선택`}
                    aria-pressed={matchMode === mode}
                    disabled={selectedTags.length < 2}
                    onClick={() => setMatchMode(mode)}
                  >{mode}</button>
                ))}
              </div>
              {selectedTags.length ? (
                <button type="button" className="kms-clear-selected-tags" onClick={() => setSelectedTags([])}>전체 해제</button>
              ) : null}
              <button
                type="button"
                className="btn btn-primary"
                onClick={runTagSearch}
                disabled={loading || (!selectedTags.length && !splitTags(tagInput).length)}
              >
                <Search size={16} aria-hidden="true" />선택한 태그로 검색
              </button>
            </div>
          </div>
        </div>
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
          onOpenList={() => navigate(makePostsPath({ status_code: "VERIFYING" }))}
        />
        <FlowCard
          title="실전 적용 후보"
          description="매매 계획에 연결할 후보"
          posts={summary.practice_candidate_posts}
          emptyText="실전 적용 후보 글이 없습니다."
          onOpenPost={openPost}
          onOpenList={() => navigate(makePostsPath({ status_code: "APPLIED" }))}
        />
      </div>
    </div>
  );
}

export default KmsHomePage;
