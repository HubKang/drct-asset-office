import { useEffect, useMemo, useState } from "react";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { TrainingCalendarDay, TrainingCalendarResponse } from "@/types/tradeTraining";

const formatMonth = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
const formatDate = (date: Date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const todayMonth = () => formatMonth(new Date());
const todayDate = () => formatDate(new Date());

const fmtCount = (value: number) => `${Number(value || 0).toLocaleString("ko-KR")}건`;
const fmtScore = (value: number) => `${Math.round(Number(value || 0))}점`;
const fmtRate = (value: number) => {
  const n = Number(value || 0);
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
};

const getReturnGradientLevel = (value: number) => {
  const absValue = Math.abs(value);
  if (absValue >= 30) return "strong";
  if (absValue >= 10) return "medium";
  if (absValue >= 3) return "soft";
  return "pale";
};

const getReturnToneClass = (value?: number | null) => {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "training-return-neutral";
  return `training-return-${n > 0 ? "positive" : "negative"}-${getReturnGradientLevel(n)}`;
};

const getReturnTextClass = (value?: number | null) => {
  const n = Number(value);
  if (!Number.isFinite(n) || n === 0) return "training-neutral";
  return n > 0 ? "training-positive" : "training-negative";
};

const monthDays = (month: string) => {
  const [year, monthNumber] = month.split("-").map(Number);
  const first = new Date(year, monthNumber - 1, 1);
  const last = new Date(year, monthNumber, 0);
  const blanks = Array.from({ length: first.getDay() }, () => null);
  const days = Array.from({ length: last.getDate() }, (_, idx) => {
    const day = String(idx + 1).padStart(2, "0");
    return `${month}-${day}`;
  });
  return [...blanks, ...days];
};

function TradeTrainingCalendarPage() {
  const [month, setMonth] = useState(todayMonth());
  const [data, setData] = useState<TrainingCalendarResponse | null>(null);
  const [selectedDate, setSelectedDate] = useState(todayDate());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showScoreHelp, setShowScoreHelp] = useState(false);

  const dayMap = useMemo(() => {
    const map = new Map<string, TrainingCalendarDay>();
    (data?.days ?? []).forEach((day) => map.set(day.date, day));
    return map;
  }, [data]);

  const selectedDay = dayMap.get(selectedDate) ?? null;
  const calendarCells = useMemo(() => monthDays(month), [month]);
  const maxScore = Math.max(1, ...(data?.days ?? []).map((day) => day.training_score));

  const load = async (targetMonth = month) => {
    setLoading(true);
    setError("");
    try {
      const result = await repositories.tradeTraining.getCalendar(targetMonth);
      setData(result);
      if (!selectedDate.startsWith(targetMonth)) {
        const fallback = result.days[0]?.date || `${targetMonth}-01`;
        setSelectedDate(fallback);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "매매훈련 캘린더를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(month);
  }, []);

  const applyMonth = (nextMonth: string, nextSelectedDate = `${nextMonth}-01`) => {
    if (!/^\d{4}-\d{2}$/.test(nextMonth)) return;
    setMonth(nextMonth);
    setSelectedDate(nextSelectedDate);
    void load(nextMonth);
  };

  const moveMonth = (delta: number) => {
    const [year, monthNumber] = month.split("-").map(Number);
    const next = new Date(year, monthNumber - 1 + delta, 1);
    applyMonth(formatMonth(next));
  };

  const goThisMonth = () => {
    applyMonth(todayMonth(), todayDate());
  };

  return (
    <div className="training-calendar-page space-y-4">
      <div className="journal-hero-row training-calendar-hero-row">
        <section className="journal-hero-panel">
          <h1>매매훈련 캘린더</h1>
          <p>매일의 매매훈련 기록, 복기 상태, 훈련점수와 성장 추이를 확인합니다.</p>
        </section>

        <section className="journal-summary-compact training-calendar-hero-summary" aria-label="월간 훈련 요약">
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">총 훈련</span>
            <strong className="journal-summary-value">{fmtCount(data?.summary.total_sessions ?? 0)}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">훈련일</span>
            <strong className="journal-summary-value">{fmtCount(data?.summary.training_days ?? 0)}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">평균 훈련점수</span>
            <strong className="journal-summary-value">{fmtScore(data?.summary.avg_training_score ?? 0)}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">평균 수익률</span>
            <strong className="journal-summary-value">{fmtRate(data?.summary.avg_return_rate ?? 0)}</strong>
          </div>
          <div className="journal-summary-mini-card">
            <span className="journal-summary-label">복기 완료율</span>
            <strong className="journal-summary-value">{fmtRate(data?.summary.review_completion_rate ?? 0).replace("+", "")}</strong>
          </div>
        </section>
      </div>

      <SectionCard title="월간 훈련 조회">
        <div className="training-calendar-toolbar">
          <div className="training-calendar-month-control calendar-period-nav">
            <button type="button" className="btn btn-secondary calendar-nav-button" onClick={() => moveMonth(-1)} aria-label="이전 월">◀</button>
            <input className="input-control calendar-period-input" type="month" value={month} onChange={(e) => applyMonth(e.target.value)} />
            <button type="button" className="btn btn-secondary calendar-nav-button" onClick={() => moveMonth(1)} aria-label="다음 월">▶</button>
            <button type="button" className="btn btn-secondary calendar-today-button" onClick={goThisMonth} disabled={loading}>이번달</button>
          </div>
        </div>
        {error ? <div className="inline-result inline-error">{error}</div> : null}
      </SectionCard>

      <div className="training-calendar-main-grid">
        <SectionCard title="월간 훈련 캘린더">
          <div className="training-calendar-week-row">
            {["일", "월", "화", "수", "목", "금", "토"].map((label) => <span key={label}>{label}</span>)}
          </div>
          <div className="training-calendar-grid">
            {calendarCells.map((date, idx) => {
              if (!date) return <div key={`blank-${idx}`} className="training-calendar-day-cell blank" />;
              const day = dayMap.get(date);
              const selected = date === selectedDate;
              return (
                <button
                  key={date}
                  type="button"
                  className={`training-calendar-day-cell ${day ? getReturnToneClass(day.total_return_rate) : "training-calendar-day-cell-empty"} ${selected ? "training-calendar-day-cell-selected" : ""}`}
                  onClick={() => setSelectedDate(date)}
                >
                  <span className="training-calendar-day-number">{Number(date.slice(-2))}</span>
                  {day ? (
                    <span className="training-calendar-day-body">
                      <b>{day.training_count}건 · {day.training_score}점</b>
                      <em className={getReturnTextClass(day.total_return_rate)}>{fmtRate(day.total_return_rate)}</em>
                      <small>복기 {day.review_saved_count}/{day.review_required_count}</small>
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </SectionCard>

        <SectionCard title="선택일 상세">
          <div className="training-calendar-selected-detail">
            <div className="training-calendar-detail-head">
              <div>
                <strong>{selectedDate}</strong>
                <span>{selectedDay ? `훈련 ${selectedDay.training_count}건` : "저장된 훈련 기록 없음"}</span>
              </div>
              <button type="button" className="info-dot" onClick={() => setShowScoreHelp((prev) => !prev)} title="훈련점수 계산 기준">i</button>
            </div>
            {showScoreHelp ? (
              <div className="training-calendar-score-help">
                <strong>일일 훈련점수 계산 기준</strong>
                <p>기본 20점, 훈련 1건당 5점, 양수 수익률 1%당 3점, 훈련 3건 단위 보너스, 수익률 +3% 단위 보너스, 복기 저장 1건당 5점을 더해 최대 100점으로 계산합니다.</p>
              </div>
            ) : null}
            {selectedDay ? (
              <>
                <div className="training-calendar-detail-kpis">
                  <div><span>훈련점수</span><strong>{fmtScore(selectedDay.training_score)}</strong></div>
                  <div><span>총 수익률</span><strong className={getReturnTextClass(selectedDay.total_return_rate)}>{fmtRate(selectedDay.total_return_rate)}</strong></div>
                  <div><span>평균 수익률</span><strong className={getReturnTextClass(selectedDay.avg_return_rate)}>{fmtRate(selectedDay.avg_return_rate)}</strong></div>
                  <div><span>복기</span><strong>{selectedDay.review_saved_count}/{selectedDay.review_required_count}</strong></div>
                </div>
                <div className="training-calendar-method-list">
                  {selectedDay.method_groups.map((group) => (
                    <article key={`${group.trade_method_id ?? "free"}-${group.trade_method_name}`} className="training-calendar-method-card">
                      <div className="training-calendar-method-head">
                        <strong>{group.trade_method_name}</strong>
                        <span className={getReturnTextClass(group.total_return_rate)}>{group.training_count}건 · {fmtRate(group.total_return_rate)}</span>
                      </div>
                      {group.stocks.map((stock) => (
                        <div key={`${stock.stock_code || stock.stock_name}`} className="training-calendar-stock-row">
                          <span>{stock.stock_name}<small>{stock.stock_code || ""}</small></span>
                          <span>{stock.training_count}건</span>
                          <span className={getReturnTextClass(stock.avg_return_rate)}>{fmtRate(stock.avg_return_rate)}</span>
                          <span>복기 {stock.review_saved_count}건</span>
                        </div>
                      ))}
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <p className="training-calendar-empty">선택한 날짜에 저장된 매매훈련 기록이 없습니다.</p>
            )}
          </div>
        </SectionCard>
      </div>

      <SectionCard title="월간 성장 추이">
        <div className="training-calendar-growth-chart">
          {(data?.days ?? []).map((day) => (
            <button key={day.date} type="button" onClick={() => setSelectedDate(day.date)} title={`${day.date} ${fmtRate(day.total_return_rate)}`}>
              <span
                className={getReturnToneClass(day.total_return_rate)}
                style={{ height: `${Math.max(8, (day.training_score / maxScore) * 100)}%` }}
              />
              <small>{Number(day.date.slice(-2))}</small>
            </button>
          ))}
          {(data?.days ?? []).length === 0 ? <p className="training-calendar-empty">이 달에 저장된 매매훈련 기록이 없습니다.</p> : null}
        </div>
        <div className="training-calendar-daily-table-wrap">
          <table className="data-table compact-table training-calendar-daily-table">
            <thead>
              <tr>
                <th>날짜</th>
                <th>훈련</th>
                <th>훈련점수</th>
                <th>총 수익률</th>
                <th>복기</th>
                <th>주요 매매기법</th>
                <th>상세</th>
              </tr>
            </thead>
            <tbody>
              {(data?.days ?? []).map((day) => (
                <tr key={day.date}>
                  <td>{day.date}</td>
                  <td>{day.training_count}건</td>
                  <td>{day.training_score}점</td>
                  <td className={getReturnTextClass(day.total_return_rate)}>{fmtRate(day.total_return_rate)}</td>
                  <td>{day.review_saved_count}/{day.review_required_count}</td>
                  <td>{day.method_groups[0]?.trade_method_name || "-"}</td>
                  <td><button type="button" className="btn btn-secondary btn-table-sm" onClick={() => setSelectedDate(day.date)}>보기</button></td>
                </tr>
              ))}
              {(data?.days ?? []).length === 0 ? (
                <tr><td colSpan={7}>조회된 훈련 기록이 없습니다.</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}

export default TradeTrainingCalendarPage;
