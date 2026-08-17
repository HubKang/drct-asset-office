import { useEffect, useMemo, useState } from "react";
import { Info, X } from "lucide-react";
import { repositories } from "@/services";
import type { ScenarioCategoryScore, ScenarioExecutionReview, ScenarioHabitTrade, ScenarioHabitsResponse, ScenarioResponseDistribution } from "@/types/tradeTraining";
import { formatHoldingBars, getTradeTrainingEventLabel } from "@/utils/tradeTrainingLabels";

type Props = { accountId: number; onOpenResult: (sessionId: number, selection?: { buyDate: string; sellDate: string } | null) => void };
const pct = (value?: number | null) => value == null ? "-" : value.toLocaleString("ko-KR", { maximumFractionDigits: 1 }) + "%";
const won = (value?: number | null) => value == null ? "-" : Math.round(value).toLocaleString("ko-KR") + "원";

function Progress({ value, tone = "blue" }: { value?: number | null; tone?: "blue" | "red" | "neutral" }) {
  const width = Math.max(0, Math.min(100, Number(value || 0)));
  return <span className="scenario-progress"><i className={tone} style={{ width: width + "%" }} /></span>;
}
function ResponseBar({ title, data }: { title: string; data: ScenarioResponseDistribution }) {
  const rows = [
    ["당일", data.counts.same_day, data.percentages.same_day, "same"],
    ["1~2봉", data.counts.one_to_two, data.percentages.one_to_two, "soon"],
    ["3봉 이상", data.counts.three_plus, data.percentages.three_plus, "late"],
    ["보유·미응답", data.counts.held_or_unanswered, data.percentages.held_or_unanswered, "pending"],
  ] as const;
  const total = data.episode_count ?? data.total;
  return <section className="scenario-habit-section scenario-response-panel"><div className="scenario-section-head"><strong>{title}</strong><span className="scenario-basis-label">{total}구간</span></div>
    {total === 0 ? <div className="scenario-no-data"><strong>{title.replace(" 대응 속도", "")} 구간 없음</strong><p>선택 기간에 해당 계획가격 도달 Episode가 없습니다.</p></div> : <>
      <div className="scenario-stacked-bar" aria-label={title + " 분포"}>{rows.map(([label, , value, key]) => <i key={key} className={key} style={{ width: value + "%" }} title={label + " " + pct(value)} />)}</div>
      <div className="scenario-bar-legend">{rows.map(([label, count, value, key]) => <span key={key} title={pct(value)}><i className={key} />{label} {count}</span>)}</div>
      {Number(data.max_unresolved_bars || 0) > 0 ? <p className="scenario-response-note">최대 미응답 {data.max_unresolved_bars}봉</p> : null}
    </>}
  </section>;
}
function ExecutionTrend({ data, onSelect }: { data: ScenarioHabitsResponse; onSelect: (id?: number | null) => void }) {
  const points = data.execution_trend.filter((row) => row.score != null);
  if (!points.length) return <div className="scenario-empty">시나리오 데이터가 있는 완료 거래가 없습니다.</div>;
  const width = 1000, height = 300, average = Number(data.summary.average_execution_rate || 0), labelStep = Math.max(1, Math.ceil(points.length / 14));
  const x = (i: number) => 58 + i * ((width - 88) / Math.max(1, points.length - 1));
  const y = (v: number) => 26 + (100 - v) * 2.22;
  const tradeMap = new Map(data.trades.map((trade) => [trade.scenario_id, trade]));
  return <>{points.length < 3 ? <div className="scenario-sample-note"><span>추세 참고용</span>평가 가능 거래 {points.length}건 · 거래가 더 누적되면 추세 해석의 신뢰도가 높아집니다.</div> : null}<div className="scenario-trend-scroll"><svg viewBox={"0 0 " + width + " " + height} className="scenario-trend-chart" role="img" aria-label="거래별 매매시나리오 실행률 추세" preserveAspectRatio="none">
    {[0,25,50,75,100].map((v) => <g key={v}><line x1="58" x2={width-30} y1={y(v)} y2={y(v)} className="grid"/><text x="18" y={y(v)+4}>{v}</text></g>)}
    <line x1="58" x2={width-30} y1={y(average)} y2={y(average)} className="average"/><text x={width-32} y={y(average)-7} textAnchor="end" className="average-label">선택 평균 {pct(average)}</text><polyline points={points.map((r,i)=>x(i)+","+y(Number(r.score))).join(" ")} className="trend"/>
    {points.map((r,i)=>{const trade=tradeMap.get(r.scenario_id); return <g key={r.trade_sequence+"-"+i} className="scenario-trend-point" onClick={()=>onSelect(r.scenario_id)}><circle cx={x(i)} cy={y(Number(r.score))} r="6" className={r.result_type==="WIN"?"win":r.result_type==="LOSS"?"loss":"flat"}/>{i%labelStep===0||i===points.length-1?<text x={x(i)} y="278" textAnchor="middle">#{r.trade_sequence}</text>:null}<title>{`#${r.trade_sequence} ${r.stock_name}\n실행률 ${pct(r.score)}\n수익률 ${pct(trade?.return_pct)}\n순손익 ${won(trade?.net_pnl)}\n계획 밖 ${trade?.unplanned_action_count ?? 0}건`}</title></g>})}
  </svg></div></>;
}

function ScenarioCategoryBars({ rows }: { rows: ScenarioCategoryScore[] }) {
  const [openKey, setOpenKey] = useState<string | null>(null);
  return <div className="scenario-category-list">{rows.map((row) => {
    const applicable = row.applicable ?? row.score != null;
    const tradeCount = row.applicable_trade_count ?? row.eligible_count;
    const itemCount = row.applicable_item_count ?? row.eligible_count;
    return <div key={row.key} className={"scenario-category-row " + (applicable ? "" : "not-applicable")}>
      <button type="button" className="scenario-category-name" onClick={()=>setOpenKey(openKey===row.key?null:row.key)} aria-expanded={openKey===row.key}><span>{row.label}</span><Info size={14}/></button>
      {applicable ? <><Progress value={row.rate ?? row.score}/><strong>{pct(row.rate ?? row.score)}</strong><em>{Number(row.earned_score || 0).toFixed(0)} / {Number(row.max_score || 0).toFixed(0)}</em></> : <><span className="scenario-category-empty">평가 대상 없음</span><strong>-</strong><em>-</em></>}
      {openKey===row.key?<div className="scenario-category-popover" role="dialog"><button type="button" onClick={()=>setOpenKey(null)} aria-label="닫기"><X size={14}/></button><strong>{row.label}</strong>{applicable?<dl><div><dt>평가 거래</dt><dd>{tradeCount}건</dd></div><div><dt>평가 항목</dt><dd>{itemCount}개</dd></div><div><dt>완전 실행</dt><dd>{row.full_count || 0}개</dd></div><div><dt>사유 기록</dt><dd>{row.partial_count || 0}개</dd></div><div><dt>미이행</dt><dd>{row.miss_count || 0}개</dd></div><div><dt>획득 점수</dt><dd>{Number(row.earned_score || 0).toFixed(2)}점</dd></div><div><dt>최대 점수</dt><dd>{Number(row.max_score || 0).toFixed(2)}점</dd></div></dl>:<p>선택 거래에는 이 영역의 평가 항목이 없습니다.</p>}{applicable?<p>{Number(row.earned_score || 0).toFixed(2)} ÷ {Number(row.max_score || 0).toFixed(2)} × 100 = {pct(row.rate ?? row.score)}</p>:null}</div>:null}
    </div>;
  })}</div>;
}

function ProfitLossAsymmetryPanel({ data, infoOpen, onToggleInfo }: { data: ScenarioHabitsResponse["asymmetry"]; infoOpen: boolean; onToggleInfo: () => void }) {
  const averageProfit = Math.abs(Number(data.average_win_pnl ?? data.average_profit ?? 0));
  const averageLoss = Math.abs(Number(data.average_loss_pnl_abs ?? data.average_loss ?? 0));
  const amountMax = Math.max(averageProfit, averageLoss, 1);
  const winHold = Math.max(0, Number(data.average_win_holding_bars || 0));
  const lossHold = Math.max(0, Number(data.average_loss_holding_bars || 0));
  const holdingMax = Math.max(winHold, lossHold, 1);
  const plRatio = Math.max(0, Number(data.profit_loss_ratio || 0));
  const holdingDifference = Math.round(Math.abs(lossHold - winHold));
  const amountRatio = averageProfit && averageLoss ? Math.max(averageProfit, averageLoss) / Math.min(averageProfit, averageLoss) : null;
  return <section className="scenario-habit-section scenario-asymmetry-panel">
    <div className="scenario-section-head"><strong>손실은 짧게, 이익은 길게</strong><div className="scenario-section-tools"><span className="scenario-basis-label">완료 손익 거래 기준</span><button type="button" className="scenario-info-button" onClick={onToggleInfo} aria-label="지표 설명"><Info size={16}/></button></div></div>
    {infoOpen ? <div className="scenario-info-popover" role="dialog" onMouseDown={onToggleInfo}><p onMouseDown={(event)=>event.stopPropagation()}>손실 거래는 계획한 기준에서 빠르게 제한하고, 수익 거래는 추세가 유지되는 동안 보유하여 평균 수익이 평균 손실보다 커지는 구조를 확인합니다.<br/><br/>평균 수익과 평균 손실은 동일한 금액 기준으로 비교합니다. 수익·손실 보유기간도 동일한 최대 봉 수를 기준으로 비교합니다.</p></div> : null}
    <div className="scenario-asymmetry-comparisons">
      <div><h4>금액 비대칭</h4>
        <div className="scenario-comparison-row"><span>평균 수익 <b>+{won(averageProfit)}</b></span><Progress value={averageProfit / amountMax * 100} tone="red"/><em>{pct(averageProfit / amountMax * 100)}</em></div>
        <div className="scenario-comparison-row"><span>평균 손실 <b>-{won(averageLoss)}</b></span><Progress value={averageLoss / amountMax * 100}/><em>{pct(averageLoss / amountMax * 100)}</em></div>
      </div>
      <div><h4>보유기간 비대칭</h4>
        <div className="scenario-comparison-row"><span>수익 거래 평균 보유 <b>{formatHoldingBars(winHold)}</b></span><Progress value={winHold / holdingMax * 100} tone="red"/><em>{pct(winHold / holdingMax * 100)}</em></div>
        <div className="scenario-comparison-row"><span>손실 거래 평균 보유 <b>{formatHoldingBars(lossHold)}</b></span><Progress value={lossHold / holdingMax * 100}/><em>{pct(lossHold / holdingMax * 100)}</em></div>
      </div>
    </div>
    <p className="scenario-fact">{lossHold >= winHold ? "손실 거래의 평균 보유기간이 수익 거래보다 " + holdingDifference + "봉 깁니다." : "수익 거래의 평균 보유기간이 손실 거래보다 " + holdingDifference + "봉 깁니다."}{amountRatio ? " 평균 " + (averageLoss >= averageProfit ? "손실금액은 평균 수익금액" : "수익금액은 평균 손실금액") + "의 " + amountRatio.toFixed(2) + "배입니다." : ""}</p>
    <div className="scenario-ratio-block">
      <div><div className="scenario-ratio-title"><strong>Winning Ratio {pct(data.winning_ratio)}</strong><span>수익 {data.win_count || 0} · 손실 {data.loss_count || 0} · 보합 {data.flat_count || 0}</span></div></div>
      <div><div className="scenario-ratio-title"><strong>Profit/Loss {plRatio.toFixed(2)}</strong><span>평균 수익 {plRatio.toFixed(2)} : 평균 손실 1.00</span></div></div>
    </div>
  </section>;
}
export default function ScenarioHabitsPanel({ accountId, onOpenResult }: Props) {
  const [range,setRange]=useState<"20"|"50"|"all">("20"), [stockId,setStockId]=useState(""), [result,setResult]=useState("all"), [scenario,setScenario]=useState("all");
  const [data,setData]=useState<ScenarioHabitsResponse|null>(null), [selected,setSelected]=useState<ScenarioHabitTrade|null>(null), [review,setReview]=useState<ScenarioExecutionReview|null>(null);
  const [infoOpen,setInfoOpen]=useState(false), [loading,setLoading]=useState(false), [error,setError]=useState("");
  useEffect(()=>{ let alive=true; setLoading(true); setError("");
    repositories.tradeTraining.getScenarioHabits(accountId,{range,stock_id:stockId?Number(stockId):undefined,result,scenario}).then(r=>{if(alive)setData(r)}).catch(e=>{if(alive)setError(e instanceof Error?e.message:"매매시나리오 습관을 불러오지 못했습니다.")}).finally(()=>{if(alive)setLoading(false)});
    return()=>{alive=false};
  },[accountId,range,stockId,result,scenario]);
  useEffect(()=>{ if(!selected?.scenario_id){setReview(null);return} repositories.tradeTraining.getRiskScenarioExecutionReview(selected.scenario_id).then(setReview).catch(()=>setReview(null)) },[selected?.scenario_id]);
  useEffect(()=>{ if(!infoOpen&&!selected)return; const close=(e:KeyboardEvent)=>{if(e.key==="Escape"){setInfoOpen(false);setSelected(null)}}; window.addEventListener("keydown",close); return()=>window.removeEventListener("keydown",close)},[infoOpen,selected]);
  const stockOptions=useMemo(()=>{const map=new Map<number,string>();data?.trades.forEach(t=>{if(t.stock_id)map.set(t.stock_id,t.stock_name||t.stock_code)});return [...map.entries()]},[data?.trades]);
  const weakest=useMemo(()=>[...(data?.category_scores||[])].filter(r=>r.score!=null).sort((a,b)=>Number(a.score)-Number(b.score))[0],[data?.category_scores]);
  if(loading&&!data)return <div className="scenario-empty">매매시나리오 습관을 계산하는 중입니다.</div>;
  if(error)return <div className="inline-result inline-error">{error}</div>;
  if(!data)return null;
  const evaluableCount=data.coverage.evaluable_trade_count??data.coverage.scored_trade_count;
  const closedCount=data.coverage.closed_trade_count??data.coverage.trade_count;
  const scenarioCreatedCount=data.summary.scenario_created_count??data.coverage.scenario_trade_count;
  const scenarioDenominator=data.summary.scenario_creation_denominator??closedCount;
  const scenarioCreationRate=data.summary.scenario_creation_rate??data.summary.plan_creation_rate;
  const unplannedCount=data.summary.unplanned_order_count??0;
  const evaluatedOrderCount=data.summary.evaluated_order_count??0;
  return <div className="scenario-habits">
    <div className="scenario-habit-filters">
      <select value={range} onChange={e=>setRange(e.target.value as typeof range)} aria-label="거래 범위"><option value="20">최근 20거래</option><option value="50">최근 50거래</option><option value="all">전체</option></select>
      <select value={stockId} onChange={e=>setStockId(e.target.value)} aria-label="종목"><option value="">전체 종목</option>{stockOptions.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select>
      <select value={result} onChange={e=>setResult(e.target.value)} aria-label="손익 결과"><option value="all">전체 결과</option><option value="win">수익</option><option value="loss">손실</option><option value="flat">보합</option></select>
      <select value={scenario} onChange={e=>setScenario(e.target.value)} aria-label="시나리오 여부"><option value="all">전체 시나리오</option><option value="planned">계획 있음</option><option value="unplanned">계획 없음</option></select>
    </div>
    <section className="scenario-habit-overview">
      <div><span>매매시나리오 실행률</span><strong>{pct(data.summary.average_execution_rate)}</strong><small>평가 {evaluableCount} / {closedCount}거래</small></div>
      <div><span>계획 생성률</span><strong>{pct(scenarioCreationRate)}</strong><small>작성 {scenarioCreatedCount} / {scenarioDenominator}거래</small></div>
      <div className="scenario-overview-caution"><span>계획 밖 주문</span><strong>{pct(data.summary.unplanned_order_rate)}</strong><small>{unplannedCount} / {evaluatedOrderCount} 주문 · 낮을수록 일관성이 높습니다.</small></div>
      <div><span>Profit/Loss Ratio</span><strong>{Number(data.asymmetry.profit_loss_ratio || 0).toFixed(2)}</strong><small>수익 {Number(data.asymmetry.profit_loss_ratio || 0).toFixed(2)} : 손실 1</small></div>
    </section>
    {evaluableCount<3?<div className="scenario-sample-note"><span>표본 적음</span>평가 거래가 적어 비율 변동이 클 수 있습니다.</div>:null}
    <section className="scenario-habit-section scenario-trend-section"><div className="scenario-section-head"><strong>거래별 매매시나리오 실행률</strong><div className="scenario-result-legend"><span><i className="win"/>수익</span><span><i className="loss"/>손실</span><span><i className="flat"/>보합</span></div></div><ExecutionTrend data={data} onSelect={id=>setSelected(data.trades.find(t=>t.scenario_id===id)||null)}/></section>
    <section className="scenario-habit-section"><div className="scenario-section-head"><strong>영역별 실행률</strong><span className="scenario-basis-label">평가 항목 기준</span></div><ScenarioCategoryBars rows={data.category_scores}/></section>
    <div className="scenario-habit-split scenario-response-grid"><ResponseBar title="익절 대응" data={data.target_response_distribution}/><ResponseBar title="손절 대응" data={data.stop_response_distribution}/></div>
    <ProfitLossAsymmetryPanel data={data.asymmetry} infoOpen={infoOpen} onToggleInfo={()=>setInfoOpen(v=>!v)}/>
    <div className="scenario-habit-split scenario-risk-deviation-grid"><section className="scenario-habit-section scenario-risk-section"><div className="scenario-section-head"><strong>계좌 위험 사용</strong><span className="scenario-basis-label">{data.account_risk.positions.length?`${pct(data.account_risk.current_open_risk_pct)} / 한도 ${pct(data.account_risk.max_open_risk_pct)}`:"현재 포지션 없음"}</span></div>{data.account_risk.positions.length?<><div className="scenario-risk-bullet"><i style={{width:Math.min(100,Number(data.account_risk.current_open_risk_pct||0))+"%"}}/>{[60,80,100].map(v=><b key={v} style={{left:v+"%"}}/>)}</div><div className="scenario-risk-positions">{data.account_risk.positions.map(r=><span key={r.session_id}>{r.stock_name} {pct(r.risk_usage_pct)}</span>)}</div></>:<div className="scenario-risk-empty-line"/>}<p className="scenario-data-pending">변동성 기반 비중 분석 데이터 수집 전</p></section>
      <section className="scenario-habit-section scenario-deviation-panel"><div className="scenario-section-head"><strong>계획 이탈</strong><span className="scenario-basis-label">행동 단위 기준</span></div><div className="scenario-deviation-row"><span>계획 변경</span><strong>{data.plan_change_distribution.total}건</strong><Progress value={data.plan_change_distribution.reason_recording_rate}/><em>사유 기록 {pct(data.plan_change_distribution.reason_recording_rate)}</em></div><div className="scenario-deviation-row"><span>계획 밖 주문</span><strong>{data.unplanned_action_distribution.total}건</strong><Progress value={data.unplanned_action_distribution.reason_recording_rate} tone="neutral"/><em>사유 기록 {pct(data.unplanned_action_distribution.reason_recording_rate)}</em></div></section></div>
    <section className="scenario-habit-section scenario-detail-section"><div className="scenario-section-head"><strong>거래별 상세</strong><span className="scenario-basis-label">행을 선택하면 평가 근거를 확인할 수 있습니다.</span></div><div className="table-shell scenario-trade-table"><table className="data-table compact-table"><thead><tr><th>#</th><th>종목</th><th>청산일</th><th>손익</th><th>수익률</th><th>매매시나리오 실행률</th><th>최대 위험</th><th>계획 밖</th><th>상세</th></tr></thead><tbody>{data.trades.map(t=><tr key={t.id} onClick={()=>setSelected(t)}><td>#{t.trade_sequence}</td><td>{t.stock_name||t.stock_code}</td><td>{t.closed_chart_date}</td><td>{won(t.net_pnl)}</td><td>{pct(t.return_pct)}</td><td>{t.has_scenario_data?<><Progress value={t.scenario_execution_rate}/><small>{pct(t.scenario_execution_rate)}</small></>:"시나리오 데이터 없음"}</td><td>{pct(t.max_risk_pct)}</td><td>{t.unplanned_action_count}건</td><td><button type="button" className="btn btn-secondary">보기</button></td></tr>)}</tbody></table></div></section>
    {selected?<div className="scenario-drawer-backdrop" onMouseDown={()=>setSelected(null)}><aside className="scenario-review-drawer" role="dialog" aria-modal="true" onMouseDown={e=>e.stopPropagation()}><div className="scenario-section-head"><strong>거래 #{selected.trade_sequence} {selected.stock_name||selected.stock_code}</strong><button type="button" className="scenario-info-button" onClick={()=>setSelected(null)} aria-label="닫기"><X size={18}/></button></div>
      <div className="scenario-review-summary"><span>손익 {won(selected.net_pnl)}</span><span>수익률 {pct(selected.return_pct)}</span><span>매매시나리오 실행률 {selected.has_scenario_data?pct(selected.scenario_execution_rate):"데이터 없음"}</span></div>
      {review?<><ScenarioCategoryBars rows={review.category_scores}/><ol className="scenario-timeline">{review.timeline.map((r,i)=><li key={String(r.id||i)}><i className={String(r.severity||"INFO").toLowerCase()}/><div><strong>{getTradeTrainingEventLabel(String(r.event_type||""))}</strong><span>{String(r.chart_date||r.created_at||"-")}</span><p>{String(r.message||"")}</p></div></li>)}</ol></>:<p>{selected.has_scenario_data?"실행 이력을 불러오는 중입니다.":"시나리오 데이터 없음"}</p>}
      <button type="button" className="btn btn-primary" onClick={()=>onOpenResult(selected.training_session_id,{buyDate:selected.chart_entry_date||selected.opened_chart_date,sellDate:selected.chart_exit_date||selected.closed_chart_date})}>결과 리포트 열기</button></aside></div>:null}
  </div>;
}
