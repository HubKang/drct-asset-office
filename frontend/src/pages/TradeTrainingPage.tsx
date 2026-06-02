import { FormEvent, useEffect, useMemo, useState } from "react";
import { BarChart3, PauseCircle, Play, Search, Settings, ShoppingCart, StepForward, X } from "lucide-react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type {
  SimulationReview,
  TrainingCandle,
  TrainingEquityCurvePoint,
  TrainingGptPackage,
  TrainingOrderRequest,
  TrainingResult,
  TrainingSessionDetail,
  TrainingStockItem,
} from "@/types/tradeTraining";

type OrderMode = "BUY" | "SELL";

const DEFAULT_MA_TEXT = "5,10,20,60,120";

function fmtNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function fmtWon(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${fmtNumber(value, 0)}원`;
}

function fmtSignedWon(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const sign = Number(value) > 0 ? "+" : "";
  return `${sign}${fmtWon(value)}`;
}

function fmtPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  const sign = Number(value) > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(2)}%`;
}

function profitClass(value: number | null | undefined): string {
  const amount = Number(value || 0);
  if (amount > 0) return "training-positive";
  if (amount < 0) return "training-negative";
  return "";
}

function normalizeMas(value: string): number[] {
  const items = value
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item) && item > 0 && item <= 240);
  return Array.from(new Set(items)).sort((a, b) => a - b);
}

function maStyle(key: string): { color: string; width: number } {
  const period = Number(key.replace("ma", ""));
  switch (period) {
    case 5:
      return { color: "#111827", width: 1.4 };
    case 10:
      return { color: "#ef4444", width: 1.4 };
    case 20:
      return { color: "#eab308", width: 2.1 };
    case 60:
      return { color: "#16a34a", width: 1.5 };
    case 120:
      return { color: "#2563eb", width: 1.5 };
    default:
      return { color: "#64748b", width: 1.2 };
  }
}

function CandleChart({ candles }: { candles: TrainingCandle[] }) {
  const width = 1080;
  const priceHeight = 420;
  const volumeHeight = 96;
  const pad = { top: 22, right: 46, bottom: 30, left: 62 };
  const chartWidth = width - pad.left - pad.right;
  const height = pad.top + priceHeight + volumeHeight + pad.bottom + 22;

  if (candles.length === 0) {
    return <div className="training-chart-empty">훈련을 시작하면 차트가 표시됩니다.</div>;
  }

  const priced = candles.filter((candle) => candle.high !== null && candle.low !== null);
  const minPrice = priced.length ? Math.min(...priced.map((candle) => Number(candle.low))) : 0;
  const maxPrice = priced.length ? Math.max(...priced.map((candle) => Number(candle.high))) : 1;
  const span = Math.max(1, maxPrice - minPrice);
  const maxVolume = Math.max(1, ...candles.map((candle) => Number(candle.volume || 0)));
  const slot = chartWidth / Math.max(1, candles.length);
  const bodyWidth = Math.max(4, Math.min(13, slot * 0.58));
  const maKeys = Array.from(new Set(candles.flatMap((candle) => Object.keys(candle.moving_averages || {})))).sort(
    (a, b) => Number(a.replace("ma", "")) - Number(b.replace("ma", "")),
  );

  const yPrice = (value: number | null) => {
    if (value === null || !Number.isFinite(value)) return pad.top + priceHeight;
    return pad.top + ((maxPrice - value) / span) * priceHeight;
  };
  const xAt = (idx: number) => pad.left + idx * slot + slot / 2;

  return (
    <div className="training-chart-shell">
      <svg className="training-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="일봉 훈련 차트">
        <rect x={0} y={0} width={width} height={height} rx={8} fill="#ffffff" />
        {[0, 0.25, 0.5, 0.75, 1].map((rate) => {
          const y = pad.top + priceHeight * rate;
          const price = maxPrice - span * rate;
          return (
            <g key={rate}>
              <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="#e2e8f0" />
              <text x={width - pad.right + 6} y={y + 4} fontSize="11" fill="#64748b">
                {fmtNumber(price)}
              </text>
            </g>
          );
        })}

        {maKeys.map((key) => {
          const style = maStyle(key);
          const points = candles
            .map((candle, candleIdx) => {
              const value = candle.moving_averages?.[key];
              return value === null || value === undefined ? null : `${xAt(candleIdx)},${yPrice(Number(value))}`;
            })
            .filter(Boolean)
            .join(" ");
          return points ? <polyline key={key} points={points} fill="none" stroke={style.color} strokeWidth={style.width} /> : null;
        })}

        {candles.map((candle, idx) => {
          const x = xAt(idx);
          const open = Number(candle.open || 0);
          const close = Number(candle.close || 0);
          const high = Number(candle.high || 0);
          const low = Number(candle.low || 0);
          const isUp = close >= open;
          const color = isUp ? "#dc2626" : "#2563eb";
          const top = yPrice(Math.max(open, close));
          const bottom = yPrice(Math.min(open, close));
          const bodyHeight = Math.max(2, bottom - top);
          const volumeBarHeight = (Number(candle.volume || 0) / maxVolume) * volumeHeight;
          return (
            <g key={candle.trade_date}>
              <line x1={x} x2={x} y1={yPrice(high)} y2={yPrice(low)} stroke={color} strokeWidth={1.4} />
              <rect x={x - bodyWidth / 2} y={top} width={bodyWidth} height={bodyHeight} fill={isUp ? "#fff1f2" : "#eff6ff"} stroke={color} strokeWidth={1.2} />
              <rect x={x - bodyWidth / 2} y={pad.top + priceHeight + 22 + volumeHeight - volumeBarHeight} width={bodyWidth} height={volumeBarHeight} fill={isUp ? "#fecaca" : "#bfdbfe"} />
            </g>
          );
        })}

        <line x1={pad.left} x2={width - pad.right} y1={pad.top + priceHeight + 22 + volumeHeight} y2={pad.top + priceHeight + 22 + volumeHeight} stroke="#cbd5e1" />
        <text x={pad.left} y={height - 8} fontSize="11" fill="#64748b">{candles[0]?.trade_date}</text>
        <text x={width - pad.right - 84} y={height - 8} fontSize="11" fill="#64748b">{candles[candles.length - 1]?.trade_date}</text>
        {maKeys.map((key, idx) => {
          const style = maStyle(key);
          return (
            <g key={key} transform={`translate(${pad.left + idx * 76}, 15)`}>
              <line x1={0} x2={18} y1={0} y2={0} stroke={style.color} strokeWidth={style.width} />
              <text x={22} y={4} fontSize="11" fill="#475569">{key.toUpperCase()}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function EquityCurveChart({ points }: { points: TrainingEquityCurvePoint[] }) {
  const width = 760;
  const height = 180;
  const pad = { top: 16, right: 22, bottom: 28, left: 56 };
  if (points.length === 0) return <div className="training-chart-empty training-equity-empty">자산 스냅샷이 아직 없습니다.</div>;
  const values = points.map((point) => Number(point.total_asset || 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  const innerWidth = width - pad.left - pad.right;
  const innerHeight = height - pad.top - pad.bottom;
  const xAt = (idx: number) => pad.left + (idx / Math.max(1, points.length - 1)) * innerWidth;
  const yAt = (value: number) => pad.top + ((max - value) / span) * innerHeight;
  const polyline = points.map((point, idx) => `${xAt(idx)},${yAt(Number(point.total_asset || 0))}`).join(" ");
  return (
    <div className="training-equity-chart-shell">
      <svg viewBox={`0 0 ${width} ${height}`} className="training-equity-chart" role="img" aria-label="자산 흐름">
        <rect x={0} y={0} width={width} height={height} rx={8} fill="#ffffff" />
        {[0, 0.5, 1].map((rate) => {
          const y = pad.top + innerHeight * rate;
          const value = max - span * rate;
          return (
            <g key={rate}>
              <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="#e2e8f0" />
              <text x={6} y={y + 4} fontSize="11" fill="#64748b">{fmtNumber(value)}</text>
            </g>
          );
        })}
        <polyline points={polyline} fill="none" stroke="#111827" strokeWidth={2} />
        {points.map((point, idx) => (
          <circle key={`${point.trade_date}-${idx}`} cx={xAt(idx)} cy={yAt(Number(point.total_asset || 0))} r={2.4} fill="#111827" />
        ))}
        <text x={pad.left} y={height - 8} fontSize="11" fill="#64748b">{points[0]?.trade_date}</text>
        <text x={width - pad.right - 82} y={height - 8} fontSize="11" fill="#64748b">{points[points.length - 1]?.trade_date}</text>
      </svg>
    </div>
  );
}

function SettingsModal({
  q,
  setQ,
  stocks,
  selectedStock,
  setSelectedStock,
  initialCash,
  setInitialCash,
  feeRatePct,
  setFeeRatePct,
  displayDays,
  setDisplayDays,
  movingAverageText,
  setMovingAverageText,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  loading,
  onSearch,
  onStart,
  onClose,
}: {
  q: string;
  setQ: (value: string) => void;
  stocks: TrainingStockItem[];
  selectedStock: TrainingStockItem | null;
  setSelectedStock: (stock: TrainingStockItem) => void;
  initialCash: number;
  setInitialCash: (value: number) => void;
  feeRatePct: number;
  setFeeRatePct: (value: number) => void;
  displayDays: number;
  setDisplayDays: (value: number) => void;
  movingAverageText: string;
  setMovingAverageText: (value: string) => void;
  startDate: string;
  setStartDate: (value: string) => void;
  endDate: string;
  setEndDate: (value: string) => void;
  loading: boolean;
  onSearch: () => Promise<void>;
  onStart: () => Promise<void>;
  onClose: () => void;
}) {
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await onStart();
  };

  return (
    <div className="training-modal-backdrop" role="presentation">
      <form className="training-modal training-settings-modal" onSubmit={submit}>
        <div className="training-modal-head">
          <div>
            <h3>매매훈련 설정</h3>
            <p className="training-result-subtitle">가격 데이터가 있는 종목과 훈련 조건을 선택합니다.</p>
          </div>
          <button type="button" className="training-icon-button" onClick={onClose} aria-label="닫기">
            <X size={18} />
          </button>
        </div>

        <div className="training-stock-search">
          <input className="input-control" value={q} onChange={(event) => setQ(event.target.value)} placeholder="종목명 또는 코드 검색" />
          <button className="btn btn-secondary" type="button" disabled={loading} onClick={() => void onSearch()}>
            <Search size={16} /> 검색
          </button>
        </div>

        <div className="training-stock-list training-settings-stock-list">
          {stocks.length === 0 ? <EmptyState message="가격 데이터가 있는 종목이 없습니다." /> : null}
          {stocks.map((stock) => (
            <button
              type="button"
              className={`training-stock-item ${selectedStock?.stock_id === stock.stock_id ? "selected" : ""}`}
              key={stock.stock_id}
              onClick={() => setSelectedStock(stock)}
            >
              <strong>{stock.stock_name}</strong>
              <span>{stock.stock_code} · {stock.market || "-"} · {fmtNumber(stock.price_count)}개 · {stock.first_date}~{stock.last_date}</span>
            </button>
          ))}
        </div>

        <div className="training-option-grid training-settings-option-grid">
          <label><span>초기자금</span><input className="input-control" type="number" min={1} value={initialCash} onChange={(event) => setInitialCash(Number(event.target.value) || 0)} /></label>
          <label><span>수수료율(%)</span><input className="input-control" type="number" min={0} step={0.01} value={feeRatePct} onChange={(event) => setFeeRatePct(Number(event.target.value) || 0)} /></label>
          <label><span>표시 일수</span><input className="input-control" type="number" min={1} max={400} value={displayDays} onChange={(event) => setDisplayDays(Number(event.target.value) || 80)} /></label>
          <label><span>이동평균선</span><input className="input-control" value={movingAverageText} onChange={(event) => setMovingAverageText(event.target.value)} /></label>
          <label><span>시작일</span><input className="input-control" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
          <label><span>종료일</span><input className="input-control" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
        </div>
        <p className="training-settings-help">시작일을 비우면 수집된 최초 일자부터 시작하고, 종료일을 비우면 수집된 최종 일자까지 진행합니다.</p>

        <div className="training-modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>닫기</button>
          <button type="submit" className="btn btn-primary" disabled={!selectedStock || loading}>
            {loading ? "시작 중..." : "훈련 시작"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ResultModal({ result, onClose }: { result: TrainingResult; onClose: () => void }) {
  const [review, setReview] = useState<SimulationReview | null>(null);
  const [gptPackage, setGptPackage] = useState<TrainingGptPackage | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [packageLoading, setPackageLoading] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [reviewError, setReviewError] = useState("");

  useEffect(() => {
    const loadReview = async () => {
      setReviewLoading(true);
      setReviewError("");
      try {
        const response = await repositories.tradeTraining.getReview(result.session_id);
        setReview(response);
      } catch (error) {
        setReviewError(error instanceof Error ? error.message : "훈련 회고를 불러오지 못했습니다.");
      } finally {
        setReviewLoading(false);
      }
    };
    void loadReview();
  }, [result.session_id]);

  const updateReview = (field: keyof SimulationReview, value: string | number | null) => {
    setReview((prev) => {
      const base: SimulationReview = prev ?? {
        session_id: result.session_id,
        review_status: "미복기",
        self_review_text: "",
        gpt_prompt_text: "",
        gpt_review_text: "",
        improvement_point: "",
        next_training_goal: "",
        main_mistake: "",
        discipline_score: null,
        reviewed_at: null,
        created_at: null,
        updated_at: null,
      };
      return { ...base, [field]: value };
    });
  };

  const saveReview = async (nextPrompt?: string) => {
    if (!review) return;
    setReviewLoading(true);
    setSaveMessage("");
    setReviewError("");
    try {
      const response = await repositories.tradeTraining.saveReview(result.session_id, {
        review_status: review.review_status,
        self_review_text: review.self_review_text,
        gpt_prompt_text: nextPrompt ?? review.gpt_prompt_text,
        gpt_review_text: review.gpt_review_text,
        improvement_point: review.improvement_point,
        next_training_goal: review.next_training_goal,
        main_mistake: review.main_mistake,
        discipline_score: review.discipline_score,
      });
      setReview(response);
      setSaveMessage("훈련 복기를 저장했습니다.");
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "훈련 복기를 저장하지 못했습니다.");
    } finally {
      setReviewLoading(false);
    }
  };

  const buildGptPackage = async () => {
    setPackageLoading(true);
    setSaveMessage("");
    setReviewError("");
    try {
      if (review) {
        await repositories.tradeTraining.saveReview(result.session_id, {
          review_status: review.review_status,
          self_review_text: review.self_review_text,
          gpt_prompt_text: review.gpt_prompt_text,
          gpt_review_text: review.gpt_review_text,
          improvement_point: review.improvement_point,
          next_training_goal: review.next_training_goal,
          main_mistake: review.main_mistake,
          discipline_score: review.discipline_score,
        });
      }
      const response = await repositories.tradeTraining.getGptPackage(result.session_id);
      setGptPackage(response);
      if (review) {
        const saved = await repositories.tradeTraining.saveReview(result.session_id, {
          review_status: review.review_status,
          self_review_text: review.self_review_text,
          gpt_prompt_text: response.generated_prompt,
          gpt_review_text: review.gpt_review_text,
          improvement_point: review.improvement_point,
          next_training_goal: review.next_training_goal,
          main_mistake: review.main_mistake,
          discipline_score: review.discipline_score,
        });
        setReview(saved);
      }
      setSaveMessage("GPT 훈련복기 패키지를 생성했습니다.");
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "GPT 복기 패키지를 생성하지 못했습니다.");
    } finally {
      setPackageLoading(false);
    }
  };

  const copyPrompt = async () => {
    if (!gptPackage) return;
    try {
      await navigator.clipboard.writeText(gptPackage.generated_prompt);
      setSaveMessage("GPT 훈련복기 패키지를 복사했습니다.");
    } catch {
      setSaveMessage("복사에 실패했습니다. 아래 내용을 직접 선택해 복사해 주세요.");
    }
  };

  const summaryItems = [
    { label: "초기자금", value: fmtWon(result.initial_cash) },
    { label: "최종자산", value: fmtWon(result.final_total_asset) },
    { label: "누적손익", value: fmtSignedWon(result.total_profit), className: profitClass(result.total_profit) },
    { label: "누적수익률", value: fmtPercent(result.total_return_rate), className: profitClass(result.total_return_rate) },
    { label: "총 거래", value: `${fmtNumber(result.trade_count)}건` },
    { label: "승률", value: fmtPercent(result.win_rate) },
    { label: "평균수익", value: fmtPercent(result.average_profit_rate), className: "training-positive" },
    { label: "평균손실", value: fmtPercent(result.average_loss_rate), className: "training-negative" },
    { label: "최대수익", value: fmtSignedWon(result.max_profit_amount), className: profitClass(result.max_profit_amount) },
    { label: "최대손실", value: fmtSignedWon(result.max_loss_amount), className: profitClass(result.max_loss_amount) },
    { label: "평균보유일", value: result.average_holding_days === null ? "-" : `${fmtNumber(result.average_holding_days, 1)}일` },
    { label: "총 수수료", value: fmtWon(result.total_fees) },
  ];

  return (
    <div className="training-modal-backdrop" role="presentation">
      <div className="training-modal training-result-modal" role="dialog" aria-modal="true" aria-label="훈련 결과 리포트">
        <div className="training-modal-head">
          <div>
            <h3>훈련 결과 리포트</h3>
            <p className="training-result-subtitle">{result.stock_name || result.stock_code} · {result.start_date} ~ {result.current_date || result.end_date} · {result.status}</p>
          </div>
          <button type="button" className="training-icon-button" onClick={onClose} aria-label="닫기">
            <X size={18} />
          </button>
        </div>

        <div className="training-result-grid">
          {summaryItems.map((item) => (
            <div key={item.label}>
              <span>{item.label}</span>
              <strong className={item.className || ""}>{item.value}</strong>
            </div>
          ))}
        </div>

        <div className="training-result-grid training-result-small-grid">
          <div><span>매수 사유 입력률</span><strong>{fmtPercent(result.buy_reason_fill_rate)}</strong></div>
          <div><span>매도 사유 입력률</span><strong>{fmtPercent(result.sell_reason_fill_rate)}</strong></div>
          <div><span>매수/매도</span><strong>{fmtNumber(result.buy_count)} / {fmtNumber(result.sell_count)}</strong></div>
          <div><span>승/패/보합</span><strong>{fmtNumber(result.winning_trade_count)} / {fmtNumber(result.losing_trade_count)} / {fmtNumber(result.break_even_trade_count)}</strong></div>
        </div>

        <section className="training-result-section">
          <h4>자산 흐름</h4>
          <EquityCurveChart points={result.equity_curve} />
        </section>

        <section className="training-result-section">
          <h4>거래별 결과</h4>
          {result.trade_pairs.length === 0 ? <EmptyState message="아직 청산된 거래쌍이 없습니다." /> : (
            <div className="table-shell">
              <table className="data-table compact-table training-result-table">
                <thead>
                  <tr>
                    <th>매수일</th>
                    <th>매도일</th>
                    <th className="numeric-cell">보유일</th>
                    <th className="numeric-cell">매수가</th>
                    <th className="numeric-cell">매도가</th>
                    <th className="numeric-cell">수량</th>
                    <th className="numeric-cell">손익</th>
                    <th className="numeric-cell">수익률</th>
                    <th>매수 사유</th>
                    <th>매도 사유</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trade_pairs.map((pair, idx) => (
                    <tr key={`${pair.buy_date}-${pair.sell_date}-${idx}`}>
                      <td>{pair.buy_date}</td>
                      <td>{pair.sell_date}</td>
                      <td className="numeric-cell">{fmtNumber(pair.holding_days)}</td>
                      <td className="numeric-cell">{fmtWon(pair.buy_price)}</td>
                      <td className="numeric-cell">{fmtWon(pair.sell_price)}</td>
                      <td className="numeric-cell">{fmtNumber(pair.quantity)}</td>
                      <td className={`numeric-cell ${profitClass(pair.profit_amount)}`}>{fmtSignedWon(pair.profit_amount)}</td>
                      <td className={`numeric-cell ${profitClass(pair.profit_rate)}`}>{fmtPercent(pair.profit_rate)}</td>
                      <td>{pair.buy_reason || "-"}</td>
                      <td>{pair.sell_reason || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="training-result-section training-review-section">
          <h4>훈련 회고</h4>
          <p className="training-result-help">먼저 자기 회고와 다음 훈련 목표를 적으면 GPT 복기 패키지가 더 좋아집니다.</p>
          {reviewLoading && !review ? <p className="text-sm text-muted">훈련 회고를 불러오는 중입니다.</p> : null}
          {reviewError ? <div className="inline-result inline-error">{reviewError}</div> : null}
          {review ? (
            <>
              <div className="training-review-grid">
                <label>
                  <span>복기 상태</span>
                  <select className="select-control" value={review.review_status} onChange={(event) => updateReview("review_status", event.target.value)}>
                    <option value="미복기">미복기</option>
                    <option value="복기완료">복기완료</option>
                  </select>
                </label>
                <label>
                  <span>핵심 실수</span>
                  <select className="select-control" value={review.main_mistake} onChange={(event) => updateReview("main_mistake", event.target.value)}>
                    <option value="">선택 안 함</option>
                    <option value="추격매수">추격매수</option>
                    <option value="손절 지연">손절 지연</option>
                    <option value="조기 매도">조기 매도</option>
                    <option value="근거 부족 매수">근거 부족 매수</option>
                    <option value="비중 과다">비중 과다</option>
                    <option value="매도 기준 부재">매도 기준 부재</option>
                    <option value="감정 개입">감정 개입</option>
                    <option value="기타">기타</option>
                  </select>
                </label>
                <label>
                  <span>원칙 준수 점수</span>
                  <input
                    className="input-control"
                    type="number"
                    min={0}
                    max={100}
                    value={review.discipline_score ?? ""}
                    onChange={(event) => updateReview("discipline_score", event.target.value === "" ? null : Number(event.target.value))}
                  />
                </label>
              </div>
              <div className="training-review-text-grid">
                <label><span>자기 회고</span><textarea className="textarea-control" value={review.self_review_text} onChange={(event) => updateReview("self_review_text", event.target.value)} /></label>
                <label><span>개선할 점</span><textarea className="textarea-control" value={review.improvement_point} onChange={(event) => updateReview("improvement_point", event.target.value)} /></label>
                <label><span>다음 훈련 목표</span><textarea className="textarea-control" value={review.next_training_goal} onChange={(event) => updateReview("next_training_goal", event.target.value)} /></label>
                <label><span>GPT 복기 결과</span><textarea className="textarea-control" value={review.gpt_review_text} onChange={(event) => updateReview("gpt_review_text", event.target.value)} /></label>
              </div>
              <div className="training-result-actions">
                <button type="button" className="btn btn-secondary" disabled={reviewLoading} onClick={() => void saveReview()}>
                  훈련 복기 저장
                </button>
                <button type="button" className="btn btn-primary" disabled={packageLoading} onClick={() => void buildGptPackage()}>
                  GPT 훈련복기 패키지 생성
                </button>
              </div>
            </>
          ) : null}
        </section>

        <section className="training-result-section training-gpt-section">
          <h4>GPT 훈련복기</h4>
          <div className="training-result-note">
            GPT 자동 호출은 하지 않습니다. 아래 요청문을 복사해 GPT에 붙여넣어 사용하세요. 이 기능은 투자 조언이 아니라 훈련 복기와 습관 교정을 위한 기능입니다.
          </div>
          {gptPackage ? (
            <div className="training-gpt-package">
              <div className="training-gpt-package-head">
                <strong>{gptPackage.package_title}</strong>
                <button type="button" className="btn btn-secondary" onClick={() => void copyPrompt()}>복사</button>
              </div>
              <textarea className="textarea-control training-gpt-prompt" value={gptPackage.generated_prompt} readOnly />
            </div>
          ) : (
            <p className="training-result-help">GPT 훈련복기 패키지 생성 버튼을 누르면 결과 리포트와 훈련 회고를 묶은 요청문이 생성됩니다.</p>
          )}
        </section>

        {saveMessage ? <div className="inline-result">{saveMessage}</div> : null}
      </div>
    </div>
  );
}

function OrderModal({
  mode,
  detail,
  onClose,
  onSubmit,
}: {
  mode: OrderMode;
  detail: TrainingSessionDetail;
  onClose: () => void;
  onSubmit: (payload: TrainingOrderRequest) => Promise<void>;
}) {
  const candle = detail.current_candle;
  const close = Number(candle?.close || 0);
  const defaultPercent = mode === "BUY" ? 10 : 100;
  const [price, setPrice] = useState(close);
  const [percent, setPercent] = useState(defaultPercent);
  const [quantity, setQuantity] = useState(1);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const feeRate = Number(detail.session.options?.fee_rate || 0);
  const amount = price * quantity;
  const fee = amount * feeRate;
  const expectedProfit = mode === "SELL" ? (price - detail.session.avg_price) * quantity - fee : null;
  const expectedProfitRate = mode === "SELL" && detail.session.avg_price > 0 ? ((price - detail.session.avg_price) / detail.session.avg_price) * 100 : null;
  const totalCost = amount + fee;
  const remainingCash = detail.session.cash - totalCost;
  const maxAffordableQuantity =
    mode === "BUY"
      ? Math.floor(detail.session.cash / Math.max(1, price * (1 + feeRate)))
      : detail.session.position_qty;
  const invalidOrder =
    quantity < 1 ||
    price < 1 ||
    (mode === "BUY" && totalCost > detail.session.cash) ||
    (mode === "SELL" && quantity > detail.session.position_qty);

  const calculateQuantity = (nextPercent: number, nextPrice = price) => {
    if (mode === "BUY") {
      const targetAmount = detail.session.initial_cash * (nextPercent / 100);
      const cashLimitedAmount = Math.min(targetAmount, detail.session.cash);
      return Math.max(0, Math.floor(cashLimitedAmount / Math.max(1, nextPrice * (1 + feeRate))));
    }
    return Math.max(0, Math.floor(detail.session.position_qty * (nextPercent / 100)));
  };

  useEffect(() => {
    setQuantity(calculateQuantity(percent, price));
  }, [percent, price, mode, feeRate]);

  const onQuantityChange = (nextQuantity: number) => {
    const safeQuantity = Math.max(0, Math.min(nextQuantity || 0, maxAffordableQuantity));
    setQuantity(safeQuantity);
    if (mode === "BUY") {
      const nextPercent = Math.min(100, Math.round(((safeQuantity * price) / Math.max(1, detail.session.initial_cash)) * 100));
      setPercent(nextPercent);
    } else {
      const nextPercent = Math.min(100, Math.round((safeQuantity / Math.max(1, detail.session.position_qty)) * 100));
      setPercent(nextPercent);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({ price, quantity, reason: reason.trim() || null });
    } finally {
      setSubmitting(false);
    }
  };

  const quickPercents = mode === "BUY" ? [10, 20, 30, 50, 100] : [25, 50, 100];

  return (
    <div className="training-modal-backdrop" role="presentation">
      <form className="training-modal" onSubmit={submit}>
        <div className="training-modal-head">
          <h3>{mode === "BUY" ? "매수 주문" : "매도 주문"}</h3>
          <button type="button" className="training-icon-button" onClick={onClose} aria-label="닫기">
            <X size={18} />
          </button>
        </div>

        <div className="training-modal-market">
          <strong>{detail.session.current_date}</strong>
          <span>시가 {fmtWon(candle?.open)} · 고가 {fmtWon(candle?.high)} · 저가 {fmtWon(candle?.low)} · 종가 {fmtWon(candle?.close)}</span>
        </div>

        {mode === "SELL" ? (
          <div className="training-order-summary">
            <div><span>보유수량</span><strong>{fmtNumber(detail.session.position_qty)}주</strong></div>
            <div><span>평균단가</span><strong>{fmtWon(detail.session.avg_price)}</strong></div>
          </div>
        ) : null}

        <div className="training-order-grid">
          <label>
            <span>주문가격</span>
            <input className="input-control" type="number" min={1} value={price} onChange={(event) => setPrice(Number(event.target.value) || 0)} />
          </label>
          <label>
            <span>주문수량</span>
            <input className="input-control" type="number" min={0} max={maxAffordableQuantity} value={quantity} onChange={(event) => onQuantityChange(Number(event.target.value) || 0)} />
          </label>
        </div>

        <div className="training-slider-block">
          <div className="training-slider-head">
            <span>{mode === "BUY" ? `초기자금 기준 ${percent}%` : `보유수량 기준 ${percent}%`}</span>
            <strong>{fmtNumber(quantity)}주</strong>
          </div>
          <input className="training-order-slider" type="range" min={0} max={100} step={1} value={percent} onChange={(event) => setPercent(Number(event.target.value))} />
          <div className="training-quick-percent-row">
            {quickPercents.map((value) => (
              <button type="button" className={value === percent ? "selected" : ""} key={value} onClick={() => setPercent(value)}>
                {value}%
              </button>
            ))}
          </div>
        </div>

        <div className="training-order-summary">
          <div><span>{mode === "BUY" ? "주문금액" : "예상 매도금액"}</span><strong>{fmtWon(amount)}</strong></div>
          <div><span>수수료</span><strong>{fmtWon(fee)}</strong></div>
          {mode === "BUY" ? <div><span>총 필요금액</span><strong>{fmtWon(totalCost)}</strong></div> : null}
          {mode === "BUY" ? <div><span>주문 후 예상 현금</span><strong className={profitClass(remainingCash)}>{fmtWon(remainingCash)}</strong></div> : null}
          {mode === "SELL" ? <div><span>예상 실현손익</span><strong className={profitClass(expectedProfit)}>{fmtSignedWon(expectedProfit)}</strong></div> : null}
          {mode === "SELL" ? <div><span>예상 실현수익률</span><strong className={profitClass(expectedProfitRate)}>{fmtPercent(expectedProfitRate)}</strong></div> : null}
        </div>

        {mode === "BUY" && totalCost > detail.session.cash ? (
          <div className="inline-result inline-error">수수료를 포함한 총 필요금액이 현재 현금을 초과합니다.</div>
        ) : null}
        {mode === "SELL" && quantity > detail.session.position_qty ? (
          <div className="inline-result inline-error">매도 수량이 현재 보유수량을 초과합니다.</div>
        ) : null}

        <label className="training-reason-field">
          <span>{mode === "BUY" ? "매수 사유" : "매도 사유"}</span>
          <textarea className="textarea-control" value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>

        <div className="training-modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>취소</button>
          <button type="submit" className={mode === "BUY" ? "btn btn-primary" : "btn btn-danger"} disabled={submitting || invalidOrder}>
            {submitting ? "처리 중..." : mode === "BUY" ? "매수 실행" : "매도 실행"}
          </button>
        </div>
      </form>
    </div>
  );
}

function TrainingKpiStrip({ detail }: { detail: TrainingSessionDetail }) {
  const positionProfit = detail.account.position_profit ?? detail.account.unrealized_profit;
  const positionReturnRate = detail.account.position_return_rate ?? detail.account.unrealized_return_rate;
  const realizedProfit = detail.account.realized_profit ?? detail.session.realized_profit;
  const items = [
    { label: "현재가", value: fmtWon(detail.account.current_price ?? detail.current_candle?.close) },
    { label: "보유수량", value: `${fmtNumber(detail.session.position_qty)}주` },
    { label: "평균단가", value: fmtWon(detail.session.avg_price) },
    { label: "현재포지션손익", value: fmtSignedWon(positionProfit), className: profitClass(positionProfit) },
    { label: "현재포지션수익률", value: fmtPercent(positionReturnRate), className: profitClass(positionReturnRate) },
    { label: "실현손익", value: fmtSignedWon(realizedProfit), className: profitClass(realizedProfit) },
    { label: "누적손익", value: fmtSignedWon(detail.account.total_profit), className: profitClass(detail.account.total_profit) },
    { label: "누적수익률", value: fmtPercent(detail.account.total_return_rate), className: profitClass(detail.account.total_return_rate) },
  ];
  return (
    <div className="training-kpi-strip">
      {items.map((item) => (
        <div key={item.label}>
          <span>{item.label}</span>
          <strong className={item.className || ""}>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}

function TradeTrainingPage() {
  const [q, setQ] = useState("");
  const [stocks, setStocks] = useState<TrainingStockItem[]>([]);
  const [selectedStock, setSelectedStock] = useState<TrainingStockItem | null>(null);
  const [initialCash, setInitialCash] = useState(50_000_000);
  const [feeRatePct, setFeeRatePct] = useState(0.1);
  const [displayDays, setDisplayDays] = useState(80);
  const [movingAverageText, setMovingAverageText] = useState(DEFAULT_MA_TEXT);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [detail, setDetail] = useState<TrainingSessionDetail | null>(null);
  const [result, setResult] = useState<TrainingResult | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resultLoading, setResultLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [orderMode, setOrderMode] = useState<OrderMode | null>(null);

  const loadStocks = async (keyword = q) => {
    setLoading(true);
    setError("");
    try {
      const response = await repositories.tradeTraining.listStocks({ q: keyword.trim() || undefined, limit: 30 });
      setStocks(response.items);
      setSelectedStock((prev) => prev ?? response.items[0] ?? null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "훈련 가능 종목을 불러오지 못했습니다.");
      setStocks([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadStocks("");
  }, []);

  const startSession = async () => {
    if (!selectedStock) return;
    setLoading(true);
    setError("");
    setMessage("");
    setResult(null);
    try {
      const response = await repositories.tradeTraining.createSession({
        stock_code: selectedStock.stock_code,
        initial_cash: initialCash,
        fee_rate: feeRatePct / 100,
        display_days: displayDays,
        start_date: startDate || null,
        end_date: endDate || null,
        moving_averages: normalizeMas(movingAverageText),
      });
      setDetail(response);
      setSettingsOpen(false);
      setMessage("훈련 세션을 시작했습니다.");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "훈련 세션을 시작하지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const openResultReport = async (sessionId?: number) => {
    const targetSessionId = sessionId ?? detail?.session.id;
    if (!targetSessionId) return;
    setResultLoading(true);
    setError("");
    try {
      const response = await repositories.tradeTraining.getResult(targetSessionId);
      setResult(response);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "결과 리포트를 불러오지 못했습니다.");
    } finally {
      setResultLoading(false);
    }
  };

  const mutateDetail = async (action: () => Promise<TrainingSessionDetail>, successMessage: string) => {
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await action();
      setDetail(response);
      setMessage(successMessage);
      if (response.session.status === "완료") {
        await openResultReport(response.session.id);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "요청을 처리하지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const finishSession = async () => {
    if (!detail) return;
    setLoading(true);
    setError("");
    setMessage("");
    try {
      const response = await repositories.tradeTraining.finish(detail.session.id);
      setDetail((prev) => (prev ? { ...prev, session: response.session, account: response.account } : prev));
      setMessage(response.message);
      await openResultReport(response.session.id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "훈련을 종료하지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const submitOrder = async (payload: TrainingOrderRequest) => {
    if (!detail || !orderMode) return;
    const response =
      orderMode === "BUY"
        ? await repositories.tradeTraining.buy(detail.session.id, payload)
        : await repositories.tradeTraining.sell(detail.session.id, payload);
    setDetail(response);
    setOrderMode(null);
    setMessage(orderMode === "BUY" ? "매수 체결되었습니다." : "매도 체결되었습니다.");
  };

  const progressText = useMemo(() => {
    if (!detail) return "-";
    return `${fmtNumber(detail.session.current_index + 1)}일차 · ${detail.session.start_date} ~ ${detail.session.end_date}`;
  }, [detail]);

  const canTrade = detail?.session.status === "진행중";

  return (
    <div className="space-y-4">
      <PageHeader
        title="매매훈련"
        description="과거 일봉을 하루씩 넘기며 매수·매도 판단을 훈련합니다."
        action={
          <button type="button" className="btn btn-primary" onClick={() => setSettingsOpen(true)}>
            <Settings size={16} /> 훈련 설정
          </button>
        }
      />

      <div className="training-main training-main-focused">
        {error ? <div className="inline-result inline-error">{error}</div> : null}
        {message ? <div className="inline-result">{message}</div> : null}

        {!detail ? (
          <SectionCard title="훈련 화면">
            <EmptyState message="훈련 설정 버튼을 눌러 종목과 조건을 선택하세요." />
          </SectionCard>
        ) : (
          <>
            <SectionCard title={`${detail.session.stock_name || detail.session.stock_code} 리플레이`}>
              <div className="training-session-head">
                <div>
                  <strong>{detail.session.current_date}</strong>
                  <span>{progressText} · 상태 {detail.session.status}</span>
                </div>
                <div className="training-session-actions">
                  <button className="btn btn-secondary" type="button" disabled={!canTrade || loading} onClick={() => mutateDetail(() => repositories.tradeTraining.next(detail.session.id), "다음 거래일로 이동했습니다.")}>
                    <StepForward size={16} /> 다음
                  </button>
                  <button className="btn btn-primary" type="button" disabled={!canTrade || loading} onClick={() => setOrderMode("BUY")}>
                    <ShoppingCart size={16} /> 매수
                  </button>
                  <button className="btn btn-danger" type="button" disabled={!canTrade || detail.session.position_qty <= 0 || loading} onClick={() => setOrderMode("SELL")}>
                    매도
                  </button>
                  <button className="btn btn-secondary" type="button" disabled={resultLoading} onClick={() => void openResultReport()}>
                    <BarChart3 size={16} /> 결과 리포트
                  </button>
                  <button className="btn btn-secondary" type="button" disabled={loading} onClick={finishSession}>
                    <PauseCircle size={16} /> 종료
                  </button>
                </div>
              </div>

              <TrainingKpiStrip detail={detail} />
              <CandleChart candles={detail.candles} />

              <div className="training-current-grid">
                <div><span>시가</span><strong>{fmtWon(detail.current_candle?.open)}</strong></div>
                <div><span>고가</span><strong>{fmtWon(detail.current_candle?.high)}</strong></div>
                <div><span>저가</span><strong>{fmtWon(detail.current_candle?.low)}</strong></div>
                <div><span>종가</span><strong>{fmtWon(detail.current_candle?.close)}</strong></div>
                <div><span>거래량</span><strong>{fmtNumber(detail.current_candle?.volume)}</strong></div>
              </div>
            </SectionCard>

            <SectionCard title="거래 로그">
              {detail.trades.length === 0 ? <EmptyState message="아직 체결된 훈련 거래가 없습니다." /> : (
                <div className="table-shell">
                  <table className="data-table compact-table training-log-table">
                    <thead><tr><th>일자</th><th>구분</th><th className="numeric-cell">가격</th><th className="numeric-cell">수량</th><th className="numeric-cell">손익</th><th>사유</th></tr></thead>
                    <tbody>
                      {detail.trades.map((trade) => (
                        <tr key={trade.id}>
                          <td>{trade.trade_date}</td>
                          <td><span className={trade.side === "BUY" ? "badge badge-blue" : "badge badge-rose"}>{trade.side === "BUY" ? "매수" : "매도"}</span></td>
                          <td className="numeric-cell">{fmtWon(trade.price)}</td>
                          <td className="numeric-cell">{fmtNumber(trade.quantity)}</td>
                          <td className={`numeric-cell ${profitClass(trade.realized_profit)}`}>{fmtSignedWon(trade.realized_profit)}</td>
                          <td>{trade.reason || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </SectionCard>
          </>
        )}
      </div>

      {settingsOpen ? (
        <SettingsModal
          q={q}
          setQ={setQ}
          stocks={stocks}
          selectedStock={selectedStock}
          setSelectedStock={setSelectedStock}
          initialCash={initialCash}
          setInitialCash={setInitialCash}
          feeRatePct={feeRatePct}
          setFeeRatePct={setFeeRatePct}
          displayDays={displayDays}
          setDisplayDays={setDisplayDays}
          movingAverageText={movingAverageText}
          setMovingAverageText={setMovingAverageText}
          startDate={startDate}
          setStartDate={setStartDate}
          endDate={endDate}
          setEndDate={setEndDate}
          loading={loading}
          onSearch={() => loadStocks()}
          onStart={startSession}
          onClose={() => setSettingsOpen(false)}
        />
      ) : null}
      {detail && orderMode ? <OrderModal mode={orderMode} detail={detail} onClose={() => setOrderMode(null)} onSubmit={submitOrder} /> : null}
      {result ? <ResultModal result={result} onClose={() => setResult(null)} /> : null}
    </div>
  );
}

export default TradeTrainingPage;
