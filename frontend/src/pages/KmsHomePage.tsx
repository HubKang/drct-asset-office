import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { KmsHomeSummary, KmsPost, KmsTagMatchMode } from "@/types/kms";
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

const splitTags = (value: string) =>
  value
    .split(",")
    .map((tag) => tag.trim().replace(/^#/, ""))
    .filter(Boolean);

function KmsHomePage() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<KmsHomeSummary>(emptySummary);
  const [tagInput, setTagInput] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [matchMode, setMatchMode] = useState<KmsTagMatchMode>("AND");
  const [searchResults, setSearchResults] = useState<KmsPost[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const statCards = useMemo(
    () => [
      { label: "전체 지식글", value: summary.overall.total_posts, help: "누적 등록 지식" },
      { label: "복습 필요", value: summary.overall.review_needed_count, help: "다시 볼 지식" },
      { label: "실전 적용 후보", value: summary.overall.practice_candidate_count, help: "기법화 후보" },
      { label: "핵심 지식", value: summary.overall.core_count, help: "중요도 핵심" },
      { label: "최근 7일 작성/수정", value: summary.overall.recent_7d_count, help: "최근 학습 흐름" },
    ],
    [summary],
  );

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

  return (
    <div className="space-y-4">
      <PageHeader
        title="DrCT KMS"
        description="주식과 자본시장 공부 내용을 장기적으로 축적하고 다시 찾는 지식 대시보드입니다."
        action={<button type="button" className="btn btn-primary" onClick={() => navigate("/kms/posts?new=1")}>새 지식 등록</button>}
      />

      {message ? <div className="alert alert-warning">{message}</div> : null}

      <div className="kms-summary-grid">
        {statCards.map((card) => (
          <div key={card.label} className="kms-summary-card">
            <span>{card.label}</span>
            <strong>{card.value.toLocaleString("ko-KR")}</strong>
            <small>{card.help}</small>
          </div>
        ))}
      </div>

      <section className="kms-panel">
        <div className="kms-panel-header">
          <div>
            <h2 className="kms-panel-title">태그 통합 검색</h2>
            <p className="kms-panel-description">여러 태그를 조합해 카테고리를 가로질러 지식을 찾습니다.</p>
          </div>
        </div>
        <div className="kms-search-control-box">
          <input
            className="input"
            value={tagInput}
            placeholder="태그를 쉼표로 입력하세요. 예: 단타, 거래량, 전고점"
            onChange={(event) => setTagInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void runTagSearch();
            }}
          />
          <select className="select compact" value={matchMode} onChange={(event) => setMatchMode(event.target.value as KmsTagMatchMode)}>
            <option value="AND">AND</option>
            <option value="OR">OR</option>
          </select>
          <button type="button" className="btn btn-primary" onClick={() => void runTagSearch()} disabled={loading}>검색</button>
        </div>
        <div className="kms-sub-panel-grid">
          <div className="kms-sub-panel">
            <span className="kms-sub-panel-title">인기 태그</span>
            <div className="kms-chip-row">
              {summary.popular_tags.length ? (
                summary.popular_tags.map((tag) => (
                  <button key={tag.id} type="button" className="kms-chip" onClick={() => addTags([tag.name])}>
                    #{tag.name} <span>{tag.use_count}</span>
                  </button>
                ))
              ) : (
                <span className="kms-muted-guide">아직 사용된 태그가 없습니다.</span>
              )}
            </div>
          </div>
          <div className="kms-sub-panel">
            <span className="kms-sub-panel-title">선택 태그</span>
            <div className="kms-chip-row">
              {selectedTags.length ? (
                selectedTags.map((tag) => (
                  <button key={tag} type="button" className="kms-chip selected" onClick={() => removeTag(tag)}>
                    #{tag} <span aria-hidden="true">x</span>
                  </button>
                ))
              ) : (
                <span className="kms-muted-guide">선택된 태그가 없습니다.</span>
              )}
            </div>
          </div>
        </div>
        {searchResults.length ? (
          <div className="kms-result-grid">
            {searchResults.map((post) => (
              <button key={post.id} type="button" className="kms-post-card" onClick={() => navigate(`/kms/posts/${post.id}`)}>
                <span className="kms-post-card-meta">{post.category_name} · {post.importance} · {post.learning_status}</span>
                <strong>{post.title}</strong>
                <p>{post.summary || toKmsPlainText(post.content).slice(0, 120)}</p>
                <span className="kms-tag-list">{post.tags.map((tag) => `#${tag}`).join(" ")}</span>
              </button>
            ))}
          </div>
        ) : selectedTags.length ? (
          <div className="kms-empty-state">조건에 맞는 지식이 없습니다.</div>
        ) : null}
      </section>

      <section className="kms-panel">
        <div className="kms-panel-header">
          <div>
            <h2 className="kms-panel-title">대분류 카테고리</h2>
            <p className="kms-panel-description">카테고리별 지식 현황과 대표 태그를 확인합니다.</p>
          </div>
        </div>
        <div className="kms-category-grid">
          {summary.categories.map((category) => (
            <button
              key={category.category_id}
              type="button"
              className="kms-category-card"
              onClick={() => navigate(`/kms/posts?category_id=${category.category_id}`)}
            >
              <div className="kms-category-card-header">
                <strong>{category.category_name}</strong>
                <StatusBadge label={`${category.total_posts}글`} tone="slate" />
              </div>
              <div className="kms-metric-grid">
                <span><b>{category.core_count}</b>핵심</span>
                <span><b>{category.review_needed_count}</b>복습</span>
                <span><b>{category.practice_candidate_count}</b>실전 후보</span>
                <span><b>{category.recent_7d_count}</b>최근 7일</span>
              </div>
              <div className="kms-chip-row compact">
                {category.top_tags.length ? (
                  category.top_tags.map((tag) => <span key={tag} className="kms-chip static">#{tag}</span>)
                ) : (
                  <span className="kms-muted-guide">대표 태그 없음</span>
                )}
              </div>
              <small>마지막 수정 {category.last_updated_at || "-"}</small>
            </button>
          ))}
        </div>
      </section>

      <div className="kms-two-column">
        <section className="kms-panel compact">
          <h2 className="kms-panel-title">최근 작성/수정 지식</h2>
          <div className="kms-compact-list">
            {summary.recent_posts.map((post) => (
              <button key={post.post_id} type="button" onClick={() => navigate(`/kms/posts/${post.post_id}`)}>
                <strong>{post.title}</strong>
                <span>{post.category_name} · {post.importance} · {post.learning_status} · {post.updated_at}</span>
              </button>
            ))}
            {!summary.recent_posts.length ? <div className="kms-empty-state compact">아직 최근 수정된 지식이 없습니다.</div> : null}
          </div>
        </section>
        <section className="kms-panel compact">
          <h2 className="kms-panel-title">복습 필요 / 실전 적용 후보</h2>
          <div className="kms-compact-list">
            {[...summary.review_needed_posts, ...summary.practice_candidate_posts].map((post) => (
              <button key={`${post.learning_status}-${post.post_id}`} type="button" onClick={() => navigate(`/kms/posts/${post.post_id}`)}>
                <strong>{post.title}</strong>
                <span>{post.category_name} · {post.learning_status} · {post.updated_at}</span>
              </button>
            ))}
            {!summary.review_needed_posts.length && !summary.practice_candidate_posts.length ? (
              <div className="kms-empty-state compact">복습 필요 또는 실전 적용 후보로 표시된 지식이 없습니다.</div>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}

export default KmsHomePage;
