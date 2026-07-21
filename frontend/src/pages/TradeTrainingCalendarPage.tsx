import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, ClipboardCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type {
  TrainingCalendarDay,
  TrainingCalendarGrowthPoint,
  TrainingCalendarItem,
  TrainingCalendarResponse,
} from "@/types/tradeTraining";

const formatMonth = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
const formatDate = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const currentMonth = () => formatMonth(new Date());
const currentDate = () => formatDate(new Date());

const fmtRate = (value: number) => {
  const number = Number(value || 0);
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
};

const fmtMoney = (value: number) => {
  const number = Math.round(Number(value || 0));
  return `${number > 0 ? "+" : ""}${number.toLocaleString("ko-KR")}원`;
};

const returnClass = (value?: number | null) => {
  const number = Number(value || 0);
  if (number > 0) return "training-positive";
  if (number < 0) return "training-negative";
  return "training-neutral";
};

const monthCells = (month: string) => {
  const [year, monthNumber] = month.split("-").map(Number);
  const first = new Date(year, monthNumber - 1, 1);
  const last = new Date(year, monthNumber, 0);
  return [
    ...Array.from({ length: first.getDay() }, () => null),
    ...Array.from({ length: last.getDate() }, (_, index) => `${month}-${String(index + 1).padStart(2, "0")}`),
  ];
};

const compactTime = (value?: string | null) => {
  if (!value) return "";
  const normalized = value.replace("T", " ");
  return normalized.length >= 16 ? normalized.slice(11, 16) : "";
};

function GrowthChart({
  points,
  selectedDate,
  onSelect,
}: {
  points: TrainingCalendarGrowthPoint[];
  selectedDate: string;
  onSelect: (date: string) => void;
}) {
  if (!points.length) return <p className="training-calendar-empty">이 달에 완료된 매매훈련이 없습니다.</p>;

  const width = 1000;
  const height = 286;
  const left = 72;
  const right = 76;
  const top = 42;
  const bottom = 38;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const niceAxisLimit = (value: number) => {
    const safeValue = Math.max(1, value);
    const magnitude = 10 ** Math.floor(Math.log10(safeValue));
    const normalized = safeValue / magnitude;
    const niceNormalized = [1, 1.2, 1.5, 2, 2.5, 5, 10].find((candidate) => candidate >= normalized) ?? 10;
    return niceNormalized * magnitude;
  };
  const maxDaily = Math.max(1, ...points.map((point) => Math.abs(point.daily_return_rate)));
  const dailyLimit = niceAxisLimit(maxDaily);
  const dailyTicks = [dailyLimit, dailyLimit / 2, 0, -dailyLimit / 2, -dailyLimit];

  const cumulativeValues = points.map((point) => point.cumulative_return_rate);
  const maxCumulative = Math.max(1, ...cumulativeValues.map((value) => Math.abs(value)));
  const cumulativeLimit = niceAxisLimit(maxCumulative);
  const cumulativeMin = -cumulativeLimit;
  const cumulativeMax = cumulativeLimit;
  const cumulativeRange = cumulativeLimit * 2;
  const step = points.length === 1 ? 0 : plotWidth / (points.length - 1);
  const xAt = (index: number) => (points.length === 1 ? left + plotWidth / 2 : left + step * index);
  const dailyY = (value: number) => top + ((dailyLimit - value) / (dailyLimit * 2)) * plotHeight;
  const cumulativeY = (value: number) => top + ((cumulativeMax - value) / cumulativeRange) * plotHeight;
  const zeroY = dailyY(0);
  const linePoints = points.map((point, index) => `${xAt(index)},${cumulativeY(point.cumulative_return_rate)}`).join(" ");
  const barWidth = points.length === 1 ? 18 : Math.max(5, Math.min(14, step * 0.46));
  const axisRate = (value: number) => {
    const absolute = Math.abs(value);
    const digits = absolute < 10 ? 1 : 0;
    return `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`;
  };
  const showDateLabel = (point: TrainingCalendarGrowthPoint, index: number) => {
    const day = Number(point.date.slice(-2));
    return index === 0 || index === points.length - 1 || day % 5 === 0 || point.training_count > 0;
  };

  return (
    <div className="training-calendar-growth-chart-v2">
      <div className="training-calendar-chart-legend">
        <span><i className="daily" />일별 평균 수익률</span>
        <span><i className="cumulative" />월 누적 수익률</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="일별 평균 수익률과 월 누적 수익률 이중 축 차트">
        <rect x={left} y={top} width={plotWidth} height={plotHeight} rx={6} className="growth-plot-background" />
        <text x={left} y={18} textAnchor="start" className="growth-axis-title">일별 평균 수익률</text>
        <text x={width - right} y={18} textAnchor="end" className="growth-axis-title">월 누적 수익률</text>

        {dailyTicks.map((tick, index) => {
          const y = top + (plotHeight / (dailyTicks.length - 1)) * index;
          const cumulativeTick = cumulativeMax - (cumulativeRange / (dailyTicks.length - 1)) * index;
          return (
            <g key={`axis-${tick}`}>
              <line x1={left} y1={y} x2={width - right} y2={y} className="growth-grid-line" />
              <text x={left - 10} y={y + 4} textAnchor="end" className="growth-axis-label">{axisRate(tick)}</text>
              <text x={width - right + 10} y={y + 4} textAnchor="start" className="growth-axis-label">{axisRate(cumulativeTick)}</text>
            </g>
          );
        })}
        <line x1={left} y1={zeroY} x2={width - right} y2={zeroY} className="growth-axis-zero" />

        {points.map((point, index) => {
          const x = xAt(index);
          const selected = point.date === selectedDate;
          return selected ? (
            <rect
              key={`selected-${point.date}`}
              x={x - Math.max(barWidth, 12)}
              y={top}
              width={Math.max(barWidth * 2, 24)}
              height={plotHeight}
              className="growth-selected-band"
            />
          ) : null;
        })}

        {points.map((point, index) => {
          const x = xAt(index);
          const valueY = dailyY(point.daily_return_rate);
          const barY = Math.min(zeroY, valueY);
          const barHeight = Math.abs(valueY - zeroY);
          return (
            <g key={point.date} onClick={() => onSelect(point.date)} className="growth-point-group">
              {point.daily_return_rate !== 0 ? (
                <rect
                  x={x - barWidth / 2}
                  y={barY}
                  width={barWidth}
                  height={Math.max(2, barHeight)}
                  rx={Math.min(3, barWidth / 2)}
                  className={point.daily_return_rate > 0 ? "growth-bar-positive" : "growth-bar-negative"}
                />
              ) : null}
              <rect x={x - Math.max(step / 2, 12)} y={top} width={Math.max(step, 24)} height={plotHeight} fill="transparent" />
              {showDateLabel(point, index) ? (
                <text x={x} y={height - 10} textAnchor="middle" className="growth-date-label">{Number(point.date.slice(-2))}일</text>
              ) : null}
              <title>{`${point.date} · 완료 ${point.training_count}건 · 일별 평균 ${fmtRate(point.daily_return_rate)} · 누적 ${fmtRate(point.cumulative_return_rate)}`}</title>
            </g>
          );
        })}

        <polyline points={linePoints} className="growth-cumulative-line" />
        {points.map((point, index) => (
          point.training_count > 0 || point.date === selectedDate ? (
            <circle
              key={`line-${point.date}`}
              cx={xAt(index)}
              cy={cumulativeY(point.cumulative_return_rate)}
              r={point.date === selectedDate ? 4 : 2.4}
              className={`growth-cumulative-dot ${point.date === selectedDate ? "selected" : ""}`}
            />
          ) : null
        ))}
      </svg>
    </div>
  );
}

function CalendarItemRow({ item, onOpen }: { item: TrainingCalendarItem; onOpen: (item: TrainingCalendarItem) => void }) {
  return (
    <article className="training-calendar-item-row">
      <div className="training-calendar-item-main">
        <span className={`training-calendar-type-badge ${item.training_type.toLowerCase()}`}>
          {item.training_type === "ACCOUNT" ? "계좌매매" : "종목매매"}
        </span>
        <strong>{item.stock_name}</strong>
        <small>{item.stock_code || ""}</small>
        <time>{compactTime(item.completed_at)}</time>
      </div>
      <div className="training-calendar-item-meta">
        {item.training_account_name ? <span>{item.training_account_name}</span> : null}
        <span>{item.chart_entry_date || "-"} → {item.chart_exit_date || "-"}</span>
        <strong className={returnClass(item.return_rate)}>{fmtRate(item.return_rate)}</strong>
        <span className={returnClass(item.net_pnl)}>{fmtMoney(item.net_pnl)}</span>
        <span>복기 {item.review_done ? "완료" : "미완료"}</span>
        {item.scenario_execution_rate != null ? <span>시나리오 {item.scenario_execution_rate.toFixed(1)}%</span> : null}
      </div>
      <button type="button" className="btn btn-secondary btn-table-sm" onClick={() => onOpen(item)}>
        <ClipboardCheck size={15} /> 결과·복기
      </button>
    </article>
  );
}

function TradeTrainingCalendarPage() {
  const navigate = useNavigate();
  const [month, setMonth] = useState(currentMonth());
  const [data, setData] = useState<TrainingCalendarResponse | null>(null);
  const [selectedDate, setSelectedDate] = useState(currentDate());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const dayMap = useMemo(() => new Map((data?.days ?? []).map((day) => [day.date, day])), [data]);
  const selectedDay = dayMap.get(selectedDate) ?? null;
  const cells = useMemo(() => monthCells(month), [month]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    repositories.tradeTraining.getCalendar(month)
      .then((result) => {
        if (cancelled) return;
        setData(result);
        const latestCompletedDate = result.days[result.days.length - 1]?.date;
        const fallback = latestCompletedDate || (month === currentMonth() ? currentDate() : `${month}-01`);
        setSelectedDate(fallback);
      })
      .catch((nextError) => {
        if (cancelled) return;
        setError(nextError instanceof Error ? nextError.message : "매매훈련 캘린더를 불러오지 못했습니다.");
        setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [month]);

  const moveMonth = (delta: number) => {
    const [year, monthNumber] = month.split("-").map(Number);
    setMonth(formatMonth(new Date(year, monthNumber - 1 + delta, 1)));
  };

  const openTrainingResult = (item: TrainingCalendarItem) => {
    navigate("/trading/training", {
      state: {
        calendarSessionId: item.session_id,
        calendarSelection: item.chart_entry_date && item.chart_exit_date
          ? { buyDate: item.chart_entry_date, sellDate: item.chart_exit_date }
          : null,
      },
    });
  };

  return (
    <div className="training-calendar-page training-calendar-unified space-y-4">
      <header className="training-calendar-page-header">
        <div>
          <h1>매매훈련 캘린더</h1>
          <p>실제 훈련 완료일을 기준으로 계좌매매와 종목매매 결과를 함께 확인합니다.</p>
        </div>
        <div className="training-calendar-month-control calendar-period-nav">
          <button type="button" className="btn btn-secondary calendar-nav-button" onClick={() => moveMonth(-1)} aria-label="이전 달">
            <ChevronLeft size={17} />
          </button>
          <input type="month" className="input-control calendar-period-input" value={month} onChange={(event) => setMonth(event.target.value)} />
          <button type="button" className="btn btn-secondary calendar-nav-button" onClick={() => moveMonth(1)} aria-label="다음 달">
            <ChevronRight size={17} />
          </button>
          <button type="button" className="btn btn-secondary calendar-today-button" onClick={() => setMonth(currentMonth())} disabled={loading}>
            이번 달
          </button>
        </div>
      </header>

      {error ? <div className="inline-result inline-error">{error}</div> : null}

      <div className="training-calendar-main-grid">
        <SectionCard title="완료 훈련">
          <div className="training-calendar-week-row">
            {["일", "월", "화", "수", "목", "금", "토"].map((label) => <span key={label}>{label}</span>)}
          </div>
          <div className="training-calendar-grid">
            {cells.map((date, index) => {
              if (!date) return <div key={`blank-${index}`} className="training-calendar-day-cell blank" />;
              const day = dayMap.get(date);
              return (
                <button
                  key={date}
                  type="button"
                  className={`training-calendar-day-cell ${day ? "has-training" : "training-calendar-day-cell-empty"} ${date === selectedDate ? "training-calendar-day-cell-selected" : ""}`}
                  onClick={() => setSelectedDate(date)}
                >
                  <span className="training-calendar-day-number">{Number(date.slice(-2))}</span>
                  {day ? (
                    <span className="training-calendar-day-body">
                      <b>완료 {day.training_count}건</b>
                      <em className={returnClass(day.total_return_rate)}>{fmtRate(day.total_return_rate)}</em>
                      <small>복기 {day.review_saved_count}/{day.review_required_count}</small>
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </SectionCard>

        <SectionCard title="선택일 매매 상세">
          <div className="training-calendar-selected-detail">
            <div className="training-calendar-detail-head">
              <div>
                <strong>{selectedDate}</strong>
                <span>{selectedDay ? `완료 훈련 ${selectedDay.training_count}건 · ${selectedDay.unique_stock_count}종목` : "완료된 훈련 없음"}</span>
              </div>
            </div>
            {selectedDay ? (
              <>
                <div className="training-calendar-day-summary">
                  <span>합산 <strong className={returnClass(selectedDay.total_return_rate)}>{fmtRate(selectedDay.total_return_rate)}</strong></span>
                  <span>평균 <strong className={returnClass(selectedDay.avg_return_rate)}>{fmtRate(selectedDay.avg_return_rate)}</strong></span>
                  <span>수익 {selectedDay.win_count} · 손실 {selectedDay.loss_count} · 보합 {selectedDay.flat_count}</span>
                </div>
                <div className="training-calendar-item-list">
                  {selectedDay.items.map((item) => (
                    <CalendarItemRow key={item.calendar_item_id} item={item} onOpen={openTrainingResult} />
                  ))}
                </div>
              </>
            ) : (
              <p className="training-calendar-empty">선택한 날짜에 완료된 매매훈련이 없습니다.</p>
            )}
          </div>
        </SectionCard>
      </div>

      <SectionCard title="월간 성장 추이">
        <GrowthChart points={data?.growth ?? []} selectedDate={selectedDate} onSelect={setSelectedDate} />
        <div className="training-calendar-daily-table-wrap">
          <table className="data-table compact-table training-calendar-daily-table">
            <thead>
              <tr>
                <th>완료일</th>
                <th>훈련</th>
                <th>종목</th>
                <th>합산 수익률</th>
                <th>평균 수익률</th>
                <th>수익/손실/보합</th>
                <th>복기</th>
                <th>상세</th>
              </tr>
            </thead>
            <tbody>
              {[...(data?.days ?? [])].reverse().map((day: TrainingCalendarDay) => (
                <tr
                  key={day.date}
                  className={day.date === selectedDate ? "training-calendar-table-selected" : ""}
                  onClick={() => setSelectedDate(day.date)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedDate(day.date);
                    }
                  }}
                  tabIndex={0}
                  aria-selected={day.date === selectedDate}
                >
                  <td>{day.date}</td>
                  <td>{day.training_count}건</td>
                  <td>{day.unique_stock_count}종목</td>
                  <td className={returnClass(day.total_return_rate)}>{fmtRate(day.total_return_rate)}</td>
                  <td className={returnClass(day.avg_return_rate)}>{fmtRate(day.avg_return_rate)}</td>
                  <td>{day.win_count}/{day.loss_count}/{day.flat_count}</td>
                  <td>{day.review_saved_count}/{day.review_required_count}</td>
                  <td><button type="button" className="btn btn-secondary btn-table-sm" onClick={(event) => { event.stopPropagation(); setSelectedDate(day.date); }}>보기</button></td>
                </tr>
              ))}
              {(data?.days ?? []).length === 0 ? (
                <tr><td colSpan={8}>이 달에 완료된 매매훈련이 없습니다.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}

export default TradeTrainingCalendarPage;
