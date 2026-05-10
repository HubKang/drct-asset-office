import { useEffect, useMemo, useState } from "react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { AdvisoryPackageGenerateResponse, AdvisoryPackageType } from "@/types/advisoryPackage";
import type { Disclosure } from "@/types/disclosure";
import type { NewsItem } from "@/types/news";
import type { Stock } from "@/types/stock";

const PAGE_SIZE = 20;

function AdvisoryPackagePage() {
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [stockId, setStockId] = useState("");
  const [title, setTitle] = useState("");
  const [purpose, setPurpose] = useState("");

  const [newsItems, setNewsItems] = useState<NewsItem[]>([]);
  const [newsOffset, setNewsOffset] = useState(0);
  const [disclosures, setDisclosures] = useState<Disclosure[]>([]);
  const [disclosureOffset, setDisclosureOffset] = useState(0);
  const [selectedNewsIds, setSelectedNewsIds] = useState<number[]>([]);
  const [selectedDisclosureIds, setSelectedDisclosureIds] = useState<number[]>([]);

  const [loadingNews, setLoadingNews] = useState(false);
  const [loadingDisclosures, setLoadingDisclosures] = useState(false);
  const [loadingGenerate, setLoadingGenerate] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AdvisoryPackageGenerateResponse | null>(null);
  const [copyStatus, setCopyStatus] = useState("");

  const selectedStock = useMemo(() => stocks.find((s) => String(s.id) === stockId), [stocks, stockId]);

  useEffect(() => {
    const loadStocks = async () => {
      try {
        const data = await repositories.stocks.list();
        setStocks(data);
        if (data.length > 0) {
          const firstId = String(data[0].id);
          setStockId(firstId);
          setTitle(`${data[0].stock_name} GPT 투자 자문 패키지`);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "종목 목록을 불러오지 못했습니다.");
      }
    };
    loadStocks();
  }, []);

  useEffect(() => {
    if (!stockId) return;
    setNewsOffset(0);
    setDisclosureOffset(0);
    setSelectedNewsIds([]);
    setSelectedDisclosureIds([]);
    setResult(null);
  }, [stockId]);

  useEffect(() => {
    if (!stockId) return;
    const loadNews = async () => {
      setLoadingNews(true);
      setError("");
      try {
        const data = await repositories.news.listNews({
          stock_id: Number(stockId),
          limit: PAGE_SIZE,
          offset: newsOffset,
        });
        setNewsItems(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "뉴스 목록을 불러오지 못했습니다.");
      } finally {
        setLoadingNews(false);
      }
    };
    loadNews();
  }, [stockId, newsOffset]);

  useEffect(() => {
    if (!stockId) return;
    const loadDisclosures = async () => {
      setLoadingDisclosures(true);
      setError("");
      try {
        const data = await repositories.disclosures.listDisclosures({
          stock_id: Number(stockId),
          limit: PAGE_SIZE,
          offset: disclosureOffset,
        });
        setDisclosures(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "공시 목록을 불러오지 못했습니다.");
      } finally {
        setLoadingDisclosures(false);
      }
    };
    loadDisclosures();
  }, [stockId, disclosureOffset]);

  const aiState = (summary?: string | null, summaryError?: string | null) => {
    if (summary) return "완료";
    if (summaryError) return "오류";
    return "미처리";
  };

  const riskLabel = (risk?: string | null) => {
    const value = (risk || "unknown").toLowerCase();
    if (value === "unknown") return "미분류 / 규칙 확인 필요";
    return value;
  };

  const onGenerate = async (packageType: AdvisoryPackageType) => {
    if (!stockId) {
      setError("종목을 선택해주세요.");
      return;
    }
    if (!title.trim()) {
      setError("패키지 제목을 입력해주세요.");
      return;
    }
    if (!purpose.trim()) {
      setError("검토 목적을 입력해주세요.");
      return;
    }
    setLoadingGenerate(true);
    setError("");
    setCopyStatus("");
    try {
      const data = await repositories.advisoryPackages.generate({
        stock_id: Number(stockId),
        news_ids: selectedNewsIds,
        disclosure_ids: selectedDisclosureIds,
        title: title.trim(),
        purpose: purpose.trim(),
        package_type: packageType,
      });
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "패키지 생성 중 오류가 발생했습니다.");
    } finally {
      setLoadingGenerate(false);
    }
  };

  const copyMarkdown = async () => {
    if (!result?.markdown_content) return;
    try {
      await navigator.clipboard.writeText(result.markdown_content);
      setCopyStatus("복사되었습니다");
    } catch {
      setCopyStatus("복사 실패: 수동 복사를 사용해주세요.");
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="GPT 자문 패키지"
        description="스윙투자/장기투자 용도별 Markdown 패키지를 생성하여 GPT Plus에 붙여넣어 검토합니다."
        action={<StatusBadge label={`선택 뉴스 ${selectedNewsIds.length} / 공시 ${selectedDisclosureIds.length}`} tone="blue" />}
      />

      <SectionCard title="기본 정보">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          <select
            className="select-control"
            value={stockId}
            onChange={(e) => {
              setStockId(e.target.value);
              const stock = stocks.find((s) => String(s.id) === e.target.value);
              if (stock) setTitle(`${stock.stock_name} GPT 투자 자문 패키지`);
            }}
          >
            <option value="">종목 선택</option>
            {stocks.map((stock) => (
              <option key={stock.id} value={stock.id}>
                {stock.stock_name} ({stock.stock_code})
              </option>
            ))}
          </select>
          <input className="input-control" placeholder="패키지 제목" value={title} onChange={(e) => setTitle(e.target.value)} />
          <textarea className="textarea-control md:col-span-2" placeholder="검토 목적" value={purpose} onChange={(e) => setPurpose(e.target.value)} />
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <SectionCard title="뉴스 선택">
          {loadingNews ? <p className="text-sm text-muted">뉴스 로딩 중...</p> : null}
          {!loadingNews && newsItems.length === 0 ? <EmptyState message="해당 종목의 뉴스가 없습니다." /> : null}
          {!loadingNews && newsItems.length > 0 ? (
            <>
              <div className="table-shell">
                <table className="data-table compact-table min-w-[920px]">
                  <thead>
                    <tr>
                      <th className="selection-cell">선택</th>
                      <th>ID</th>
                      <th>AI</th>
                      <th>중요도</th>
                      <th>감성</th>
                      <th>제목</th>
                      <th>발행일</th>
                    </tr>
                  </thead>
                  <tbody>
                    {newsItems.map((item) => {
                      const checked = selectedNewsIds.includes(item.id);
                      return (
                        <tr key={item.id} className={checked ? "selected-row" : ""}>
                          <td className="selection-cell">
                            <input
                              className="selection-checkbox"
                              type="checkbox"
                              checked={checked}
                              onChange={(e) => {
                                if (e.target.checked) setSelectedNewsIds((prev) => Array.from(new Set([...prev, item.id])));
                                else setSelectedNewsIds((prev) => prev.filter((id) => id !== item.id));
                              }}
                            />
                          </td>
                          <td>{item.id}</td>
                          <td>{aiState(item.ai_summary, item.ai_summary_error)}</td>
                          <td>{item.ai_importance_score ?? item.importance_score ?? "-"}</td>
                          <td>{item.ai_sentiment ?? item.sentiment ?? "neutral"}</td>
                          <td className="cell-title cell-clamp-2 min-w-[360px]">{item.title}</td>
                          <td className="cell-nowrap">{item.published_at ?? "-"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="pagination-bar">
                <div className="pagination-info">뉴스 offset {newsOffset} / {newsItems.length}건 조회</div>
                <div className="flex gap-2">
                  <button type="button" className="btn btn-secondary" disabled={newsOffset <= 0} onClick={() => setNewsOffset((v) => Math.max(0, v - PAGE_SIZE))}>이전</button>
                  <button type="button" className="btn btn-secondary" disabled={newsItems.length < PAGE_SIZE} onClick={() => setNewsOffset((v) => v + PAGE_SIZE)}>다음</button>
                </div>
              </div>
            </>
          ) : null}
        </SectionCard>

        <SectionCard title="공시 선택">
          {loadingDisclosures ? <p className="text-sm text-muted">공시 로딩 중...</p> : null}
          {!loadingDisclosures && disclosures.length === 0 ? <EmptyState message="해당 종목의 공시가 없습니다." /> : null}
          {!loadingDisclosures && disclosures.length > 0 ? (
            <>
              <div className="table-shell">
                <table className="data-table compact-table min-w-[920px]">
                  <thead>
                    <tr>
                      <th className="selection-cell">선택</th>
                      <th>ID</th>
                      <th>AI</th>
                      <th>이벤트</th>
                      <th>리스크</th>
                      <th>제목</th>
                      <th>공시일</th>
                    </tr>
                  </thead>
                  <tbody>
                    {disclosures.map((item) => {
                      const checked = selectedDisclosureIds.includes(item.id);
                      return (
                        <tr key={item.id} className={checked ? "selected-row" : ""}>
                          <td className="selection-cell">
                            <input
                              className="selection-checkbox"
                              type="checkbox"
                              checked={checked}
                              onChange={(e) => {
                                if (e.target.checked) setSelectedDisclosureIds((prev) => Array.from(new Set([...prev, item.id])));
                                else setSelectedDisclosureIds((prev) => prev.filter((id) => id !== item.id));
                              }}
                            />
                          </td>
                          <td>{item.id}</td>
                          <td>{aiState(item.ai_summary, item.ai_summary_error)}</td>
                          <td>{item.ai_event_type ?? "기타"}</td>
                          <td>{riskLabel(item.ai_risk_level)}</td>
                          <td className="cell-title cell-clamp-2 min-w-[360px]">{item.disclosure_title}</td>
                          <td className="cell-nowrap">{item.disclosed_at ?? "-"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="pagination-bar">
                <div className="pagination-info">공시 offset {disclosureOffset} / {disclosures.length}건 조회</div>
                <div className="flex gap-2">
                  <button type="button" className="btn btn-secondary" disabled={disclosureOffset <= 0} onClick={() => setDisclosureOffset((v) => Math.max(0, v - PAGE_SIZE))}>이전</button>
                  <button type="button" className="btn btn-secondary" disabled={disclosures.length < PAGE_SIZE} onClick={() => setDisclosureOffset((v) => v + PAGE_SIZE)}>다음</button>
                </div>
              </div>
            </>
          ) : null}
        </SectionCard>
      </div>

      <SectionCard title="패키지 생성">
        <div className="action-row">
          <div className="action-row-left">
            <button type="button" className="btn btn-primary" disabled={loadingGenerate || loadingNews || loadingDisclosures} onClick={() => onGenerate("swing")}>
              {loadingGenerate ? "생성 중..." : "스윙투자 패키지 생성"}
            </button>
            <button type="button" className="btn btn-secondary" disabled={loadingGenerate || loadingNews || loadingDisclosures} onClick={() => onGenerate("long_term")}>
              {loadingGenerate ? "생성 중..." : "장기투자 패키지 생성"}
            </button>
          </div>
          <div className="action-row-right">
            <StatusBadge label={selectedStock ? `${selectedStock.stock_name} (${selectedStock.stock_code})` : "종목 미선택"} tone="slate" />
          </div>
        </div>
        {error ? <div className="inline-result inline-error">{error}</div> : null}
        {copyStatus ? <div className="inline-result">{copyStatus}</div> : null}
      </SectionCard>

      <SectionCard title="Markdown 미리보기">
        {!result ? (
          <EmptyState message="아직 생성된 패키지가 없습니다." />
        ) : (
          <div className="space-y-2">
            <div className="action-row">
              <div className="action-row-left">
                <StatusBadge label={`리포트 ID ${result.id}`} tone="blue" />
                <StatusBadge label={result.report_type} tone="slate" />
                <StatusBadge label={result.package_type} tone="amber" />
              </div>
              <div className="action-row-right">
                <button type="button" className="btn btn-secondary" onClick={copyMarkdown}>Markdown 복사</button>
              </div>
            </div>
            <pre className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs leading-6 whitespace-pre-wrap">{result.markdown_content}</pre>
          </div>
        )}
      </SectionCard>
    </div>
  );
}

export default AdvisoryPackagePage;
