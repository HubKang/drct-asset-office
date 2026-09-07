import { useEffect, useMemo, useState } from "react";
import { BarChart3, ChevronRight, RefreshCw, Search, X } from "lucide-react";

import SignalEmptyState from "@/components/drctStockSignals/SignalEmptyState";
import SignalSummaryCards from "@/components/drctStockSignals/SignalSummaryCards";
import { ReviewChart, normalizeReviewChart } from "@/pages/ChartMarkerReviewPage";
import { repositories } from "@/services";
import type { ChartMarkerEvent, ChartMarkerReviewChart, ChartMarkerReviewEvent } from "@/types/chartMarker";
import type { DrctSignalEvaluationStatus, DrctSignalPerformanceEvent, DrctSignalPerformanceEventDetail, DrctSignalPerformanceSummary } from "@/types/drctStockSignal";

const statusLabel:Record<DrctSignalEvaluationStatus,string>={PENDING:"평가 중",D5_READY:"5일 확인",D10_READY:"10일 확인",COMPLETE:"평가 완료"};
const signed=(value:number|null)=>value==null?"-":`${value>0?"+":""}${value.toFixed(1)}%`;
const returnTone=(value:number|null)=>value==null?"":value>0?" is-positive":value<0?" is-negative":"";
const shortMarker=(value:string)=>value.replace(/^.*? - /,"");

function SignalPerformanceTab() {
  const [summary,setSummary]=useState<DrctSignalPerformanceSummary|null>(null);
  const [events,setEvents]=useState<DrctSignalPerformanceEvent[]>([]);
  const [period,setPeriod]=useState<number|null>(null),[markerId,setMarkerId]=useState<number|null>(null),[query,setQuery]=useState("");
  const [selected,setSelected]=useState<DrctSignalPerformanceEvent|null>(null);
  const [busy,setBusy]=useState(true),[error,setError]=useState("");

  const loadEvents=async()=>{const result=await repositories.drctStockSignals.performanceEvents(period,markerId,query);setEvents(result.items);};
  const refresh=async()=>{setBusy(true);setError("");try{const next=await repositories.drctStockSignals.refreshPerformance();setSummary(next);await loadEvents();}catch{setError("시그널 성과를 불러오지 못했습니다.");}finally{setBusy(false);}};
  useEffect(()=>{void refresh();},[]);
  useEffect(()=>{if(!summary)return;const timer=setTimeout(()=>{void loadEvents().catch(()=>setError("최근 시그널을 불러오지 못했습니다."));},220);return()=>clearTimeout(timer);},[period,markerId,query]);

  const summaryItems=useMemo(()=>[
    {label:"누적 시그널",value:summary?`${summary.total_count}건`:"-",description:"실제 운영에서 기록",tone:"neutral" as const},
    {label:"평가 완료",value:summary?`${summary.completed_count}건`:"-",description:"20거래일 평가 완료",tone:"complete" as const},
    {label:"평가 중",value:summary?`${summary.pending_count}건`:"-",description:"미래 가격 추적 중",tone:"pending" as const},
    {label:"20일 평균 변화",value:summary&&summary.completed_count>=5?signed(summary.d20_average_pct):"-",status:summary&&summary.completed_count<5?"데이터 축적 중":undefined,description:"완료 사례 5건부터 표시",tone:"neutral" as const},
  ],[summary]);
  const visibleEvents=events.slice(0,20);

  return <div className="drct-signal-tab-content drct-performance-workspace">
    <SignalSummaryCards items={summaryItems}/>
    {error?<p className="drct-signal-inline-error">{error}</p>:null}
    <section className="drct-signal-panel" aria-labelledby="performance-title">
      <header className="drct-signal-panel-header"><div><h2 id="performance-title">마커별 시그널 성과</h2><p>DrCT가 감지한 종목의 이후 움직임을 마커별로 비교합니다.</p></div><button type="button" className="drct-performance-refresh" aria-label="성과 새로고침" title="성과 새로고침" onClick={()=>void refresh()} disabled={busy}><RefreshCw size={15} className={busy?"is-spinning":""}/></button></header>
      {!summary?.total_count&&!busy?<SignalEmptyState icon={BarChart3} title="아직 평가할 시그널이 없습니다." description="종목 시그널을 조회하면 성과 기록이 자동으로 시작됩니다. 5·10·20 거래일이 지나면 결과가 자동으로 채워집니다."/>:
      <div className="drct-performance-grid-table" role="table" aria-label="마커별 시그널 성과">
        <div className="drct-performance-grid-head" role="row"><span>마커</span><span>시그널</span><span>평가 완료</span><span>5거래일 후</span><span>10거래일 후</span><span>20거래일 후</span><span>최대 상승</span><span>최대 하락</span></div>
        {summary?.markers.map(marker=><div className="drct-performance-grid-row" role="row" key={marker.marker_id}><strong title={shortMarker(marker.marker_name)}>{shortMarker(marker.marker_name)}</strong><span data-label="시그널">{marker.signal_count}건</span><span data-label="평가 완료">{marker.completed_count}건</span><span data-label="5거래일 후" className={`drct-return${returnTone(marker.d5_average_pct)}`}>{signed(marker.d5_average_pct)}</span><span data-label="10거래일 후" className={`drct-return${returnTone(marker.d10_average_pct)}`}>{signed(marker.d10_average_pct)}</span><span data-label="20거래일 후" className={`drct-return${returnTone(marker.d20_average_pct)}`}>{signed(marker.d20_average_pct)}</span><span data-label="최대 상승" className={`drct-return${returnTone(marker.max_rise_average_pct)}`}>{signed(marker.max_rise_average_pct)}</span><span data-label="최대 하락" className={`drct-return${returnTone(marker.max_fall_average_pct)}`}>{signed(marker.max_fall_average_pct)}</span></div>)}
      </div>}
    </section>

    <section className="drct-signal-panel" aria-labelledby="recent-signals-title">
      <header className="drct-signal-panel-header"><div><h2 id="recent-signals-title">최근 시그널</h2><p>실제 운영 화면에서 기록된 마커 시그널입니다.</p></div>{events.length>20?<span className="drct-performance-result-count">최근 20건</span>:null}</header>
      <div className="drct-performance-filters"><select aria-label="기간" value={period??"ALL"} onChange={e=>setPeriod(e.target.value==="ALL"?null:Number(e.target.value))}><option value="ALL">전체 기간</option><option value="183">최근 6개월</option><option value="365">최근 1년</option></select><select aria-label="마커" value={markerId??"ALL"} onChange={e=>setMarkerId(e.target.value==="ALL"?null:Number(e.target.value))}><option value="ALL">전체 마커</option>{summary?.markers.map(marker=><option value={marker.marker_id} key={marker.marker_id}>{shortMarker(marker.marker_name)}</option>)}</select><label><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="종목명 또는 코드"/></label></div>
      {!events.length&&!busy?<div className="drct-performance-list-empty">조건에 맞는 시그널이 없습니다.</div>:<div className="drct-performance-event-list" role="table" aria-label="최근 시그널">
        <div className="drct-performance-event-head" role="row"><span>종목</span><span>마커</span><span>발생일</span><span title="시그널 발생 당시 과거 성공 패턴과의 유사도">당시 유사도</span><span>평가 상태</span><span>5일 후</span><span>10일 후</span><span>20일 후</span><span/></div>
        {visibleEvents.map(item=><button type="button" className="drct-performance-event-row" role="row" key={item.id} onClick={()=>setSelected(item)}><strong>{item.stock_name}<small>{item.stock_code}</small></strong><span data-label="마커" title={shortMarker(item.marker_name)}>{shortMarker(item.marker_name)}</span><span data-label="발생일">{item.signal_date}</span><span data-label="당시 유사도" title="시그널 발생 당시 과거 성공 패턴과의 유사도">{item.similarity_score.toFixed(1)}</span><span data-label="평가 상태" className={`drct-performance-status is-${item.evaluation_status.toLowerCase()}`}>{statusLabel[item.evaluation_status]}</span><span data-label="5일 후" className={`drct-return${returnTone(item.d5_return_pct)}`}>{signed(item.d5_return_pct)}</span><span data-label="10일 후" className={`drct-return${returnTone(item.d10_return_pct)}`}>{signed(item.d10_return_pct)}</span><span data-label="20일 후" className={`drct-return${returnTone(item.d20_return_pct)}`}>{signed(item.d20_return_pct)}</span><ChevronRight size={15}/></button>)}
      </div>}
    </section>
    {selected?<PerformanceDrawer item={selected} onClose={()=>setSelected(null)}/>:null}
  </div>;
}

function PerformanceDrawer({item,onClose}:{item:DrctSignalPerformanceEvent;onClose:()=>void}){
  const [detail,setDetail]=useState<DrctSignalPerformanceEventDetail|null>(null),[chart,setChart]=useState<ChartMarkerReviewChart|null>(null),[markerEvents,setMarkerEvents]=useState<ChartMarkerEvent[]>([]),[error,setError]=useState("");
  useEffect(()=>{let active=true;Promise.all([repositories.drctStockSignals.performanceEventDetail(item.id),repositories.chartMarkers.reviewChart(item.stock_id,item.signal_date,60,20),repositories.chartMarkers.listStockEvents(item.stock_id)]).then(([nextDetail,nextChart,nextEvents])=>{if(!active)return;setDetail(nextDetail);setChart(normalizeReviewChart(nextChart,60,20));setMarkerEvents(nextEvents.items);}).catch(()=>active&&setError("성과 상세를 불러오지 못했습니다."));return()=>{active=false;};},[item]);
  useEffect(()=>{const close=(event:KeyboardEvent)=>{if(event.key==="Escape")onClose();};document.addEventListener("keydown",close);return()=>document.removeEventListener("keydown",close);},[onClose]);
  const reviewEvent:ChartMarkerReviewEvent={id:-item.id,stock_id:item.stock_id,stock_code:item.stock_code,stock_name:item.stock_name,marker_id:item.marker_id,marker_date:item.signal_date,memo:null,review_result:null,reviewed_at:null,marker_name:item.marker_name,symbol:item.marker_symbol,marker_group_id:0,group_name:item.marker_group_name,group_color:item.marker_group_color};
  const current=detail??item;
  return <div className="drct-drawer-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)onClose();}}><aside className="drct-current-signal-drawer drct-performance-drawer" role="dialog" aria-modal="true" aria-label="시그널 성과 상세"><header><div><h3>{item.stock_name}<small>{item.stock_code}</small></h3><p>{shortMarker(item.marker_name)} · 발생일 {item.signal_date} · 당시 유사도 {item.similarity_score.toFixed(1)}</p></div><button type="button" aria-label="닫기" onClick={onClose}><X size={19}/></button></header><div className="drct-current-detail-body">{error?<p className="drct-signal-inline-error">{error}</p>:null}<section className="drct-performance-detail-metrics"><article><span>평가 상태</span><strong>{statusLabel[current.evaluation_status]}</strong></article><article><span>5거래일 후</span><strong>{signed(current.d5_return_pct)}</strong></article><article><span>10거래일 후</span><strong>{signed(current.d10_return_pct)}</strong></article><article><span>20거래일 후</span><strong>{signed(current.d20_return_pct)}</strong></article><article><span>최대 상승</span><strong>{signed(current.max_rise_20_pct)}</strong></article><article><span>최대 하락</span><strong>{signed(current.max_fall_20_pct)}</strong></article></section><section className="drct-current-chart"><h4>D0 전후 가격 흐름</h4>{chart?<ReviewChart data={chart} reviewEvent={reviewEvent} loading={false} markerEvents={markerEvents} showD0Marker onContextMenu={()=>{}}/>:<div className="drct-current-chart-skeleton" aria-label="성과 차트 불러오는 중"><i/><i/><i/><i/></div>}</section></div></aside></div>;
}

export default SignalPerformanceTab;
