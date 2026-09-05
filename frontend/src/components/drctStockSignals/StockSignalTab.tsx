import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { BarChart3, ChevronRight, RefreshCw, Search, X } from "lucide-react";

import { ReviewChart, normalizeReviewChart } from "@/pages/ChartMarkerReviewPage";
import { repositories } from "@/services";
import type { ChartMarkerEvent, ChartMarkerReviewChart, ChartMarkerReviewEvent } from "@/types/chartMarker";
import type { DrctCurrentPatternBand, DrctCurrentPatternDetail, DrctCurrentPatternScan, DrctCurrentPatternSignal, DrctCurrentPatternStock } from "@/types/drctStockSignal";

const bandLabel:Record<DrctCurrentPatternBand,string>={VERY_SIMILAR:"매우 유사",HIGH_SIMILARITY:"높은 유사",SIMILAR:"유사"};
const shortMarker=(value:string)=>value.replace(/^.*? - /,"");
const number=(value:number)=>value.toFixed(1);
const detailCache=new Map<string,DrctCurrentPatternDetail>();
const detailRequests=new Map<string,Promise<DrctCurrentPatternDetail>>();
type ChartBundle={chart:ChartMarkerReviewChart;events:ChartMarkerEvent[]};
const chartCache=new Map<string,ChartBundle>();
const chartRequests=new Map<string,Promise<ChartBundle>>();
const detailCacheKey=(analysisDate:string,stockId:number,markerId:number)=>`${analysisDate}:${stockId}:${markerId}`;
const chartCacheKey=(analysisDate:string,stockId:number)=>`${analysisDate}:${stockId}:60:0`;

function loadDetail(analysisDate:string,stockId:number,markerId:number){
  const key=detailCacheKey(analysisDate,stockId,markerId),cached=detailCache.get(key);
  if(cached)return Promise.resolve(cached);
  const pending=detailRequests.get(key);
  if(pending)return pending;
  const request=repositories.drctStockSignals.currentMarkerPatternDetail(stockId,markerId,analysisDate).then(result=>{detailCache.set(key,result);return result;}).finally(()=>detailRequests.delete(key));
  detailRequests.set(key,request);
  return request;
}

function loadChart(analysisDate:string,stockId:number){
  const key=chartCacheKey(analysisDate,stockId),cached=chartCache.get(key);
  if(cached)return Promise.resolve(cached);
  const pending=chartRequests.get(key);
  if(pending)return pending;
  const request=Promise.all([repositories.chartMarkers.reviewChart(stockId,analysisDate,60,0),repositories.chartMarkers.listStockEvents(stockId,analysisDate)]).then(([chart,events])=>{
    const result={chart:normalizeReviewChart(chart,60,0),events:events.items};
    chartCache.set(key,result);
    return result;
  }).finally(()=>chartRequests.delete(key));
  chartRequests.set(key,request);
  return request;
}

function StockSignalTab() {
  const [scan,setScan]=useState<DrctCurrentPatternScan|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const [group,setGroup]=useState("ALL"),[query,setQuery]=useState("");
  const [selectedStock,setSelectedStock]=useState<DrctCurrentPatternStock|null>(null);
  const [selectedSignal,setSelectedSignal]=useState<DrctCurrentPatternSignal|null>(null);
  const requestId=useRef(0),prefetchTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const load=useCallback(async()=>{const request=++requestId.current;setBusy(true);setError("");try{const next=await repositories.drctStockSignals.scanCurrentMarkerPatterns();if(request===requestId.current)setScan(next);}catch{if(request===requestId.current)setError("종목 시그널을 계산하지 못했습니다.");}finally{if(request===requestId.current)setBusy(false);}},[]);
  useEffect(()=>{void load();},[load]);
  useEffect(()=>()=>{if(prefetchTimer.current)clearTimeout(prefetchTimer.current);},[]);
  const groups=useMemo(()=>Array.from(new Set((scan?.stocks??[]).flatMap(stock=>stock.signals.map(signal=>signal.marker_group)))).sort(),[scan]);
  const stocks=useMemo(()=>{const keyword=query.trim().toLowerCase();return (scan?.stocks??[]).filter(stock=>(group==="ALL"||stock.signals.some(signal=>signal.marker_group===group))&&(!keyword||stock.stock_name.toLowerCase().includes(keyword)||stock.stock_code.includes(keyword)));},[scan,group,query]);
  const openDetail=(stock:DrctCurrentPatternStock)=>{setSelectedStock(stock);setSelectedSignal(stock.signals[0]??null);};
  const openWithKeyboard=(event:ReactKeyboardEvent<HTMLElement>,stock:DrctCurrentPatternStock)=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();openDetail(stock);}};
  const schedulePrefetch=(stock:DrctCurrentPatternStock)=>{if(!scan?.analysis_date||!stock.signals[0])return;if(prefetchTimer.current)clearTimeout(prefetchTimer.current);prefetchTimer.current=setTimeout(()=>{void loadDetail(scan.analysis_date!,stock.stock_id,stock.signals[0].marker_id).catch(()=>undefined);},200);};
  const clearPrefetch=()=>{if(prefetchTimer.current){clearTimeout(prefetchTimer.current);prefetchTimer.current=null;}};
  return <div className="drct-current-signals">
    <header className="drct-current-signals-head"><div><h2>현재 종목 시그널</h2><p>국내 활성 테마 연결종목에서 학습된 성공 Marker 패턴과 유사한 종목을 찾습니다.</p></div><button className="btn btn-secondary" type="button" disabled={busy} onClick={()=>void load()}><RefreshCw className={busy?"is-spinning":""} size={15}/>{busy?"패턴 분석 중":"새로고침"}</button></header>
    {error?<div className="drct-current-signal-error" role="alert"><span>{error}</span><button type="button" onClick={()=>void load()}>다시 시도</button></div>:null}
    {!scan?<SignalSkeleton/>:<>
      <section className="drct-current-signal-metrics" aria-label="현재 패턴 분석 요약">{[["기준일",scan.analysis_date?.slice(5).replace("-",".")??"-"],["분석 종목",`${scan.universe_count}개`],["적용 Marker",`${scan.eligible_marker_count}개`],["패턴 후보",`${scan.candidate_stock_count}개`]].map(([label,value])=><article key={label}><span>{label}</span><strong>{value}</strong></article>)}</section>
      <section className="drct-current-signal-filter" aria-label="종목 시그널 필터"><label><span>마커 그룹</span><select aria-label="마커 그룹" value={group} onChange={event=>setGroup(event.target.value)}><option value="ALL">전체</option>{groups.map(name=><option value={name} key={name}>{name}</option>)}</select></label><label className="drct-current-signal-search"><Search size={15}/><input aria-label="종목명 또는 코드 검색" value={query} onChange={event=>setQuery(event.target.value)} placeholder="종목명 또는 코드 검색"/></label><span>후보 {stocks.length}개</span></section>
      <section className="drct-current-signal-panel"><header><div><h3>패턴 후보</h3><p>패턴 유사도는 현재 차트와 과거 성공 Marker 패턴의 유사성으로, 성공확률이 아닙니다.</p></div>{busy?<span className="is-busy">패턴 분석 중…</span>:<span title={`전체 분석 ${scan.timings.total_ms}ms · SQL ${scan.timings.sql_query_count}회`}>ⓘ 분석정보</span>}</header>
        {stocks.length?<div className="drct-current-signal-table">{stocks.map(stock=>{const primary=stock.signals[0],secondary=stock.signals.slice(1),secondaryTitle=secondary.map(item=>`${shortMarker(item.marker_name)} ${number(item.current_pattern_similarity)}`).join("\n");return <article key={stock.stock_id} role="button" tabIndex={0} aria-label={`${stock.stock_name} 종목 시그널 상세 보기`} className={selectedStock?.stock_id===stock.stock_id?"is-selected":""} onClick={()=>openDetail(stock)} onKeyDown={event=>openWithKeyboard(event,stock)} onMouseEnter={()=>schedulePrefetch(stock)} onMouseLeave={clearPrefetch} onFocus={()=>schedulePrefetch(stock)} onBlur={clearPrefetch}><div className="drct-current-stock"><strong>{stock.stock_name}</strong><small>{stock.stock_code}</small></div><div className="drct-current-themes" title={stock.theme_names.join(" · ")}>{stock.theme_names.join(" · ")}</div><div className="drct-current-marker-primary"><span style={{"--marker-color":primary.marker_group_color} as CSSProperties}>{shortMarker(primary.marker_name)}</span>{secondary.length?<em title={secondaryTitle} aria-label={`추가 감지 Marker ${secondary.length}개: ${secondaryTitle.replace(/\n/g,", ")}`}>+{secondary.length}</em>:null}</div><strong className="drct-current-similarity" title="현재 차트와 과거 성공 Marker 패턴의 유사도이며 성공확률이 아닙니다.">{number(primary.current_pattern_similarity)}</strong><span className={`drct-current-band is-${primary.candidate_band.toLowerCase()}`}>{bandLabel[primary.candidate_band]}</span></article>;})}</div>:<div className="drct-current-signal-empty"><BarChart3 size={28}/><strong>현재 패턴 후보가 없습니다.</strong><p>현재 연결종목 중 과거 성공 Marker 패턴과 충분히 유사한 종목이 발견되지 않았습니다.</p></div>}
      </section>
    </>}
    {selectedStock&&selectedSignal&&scan?.analysis_date?<CurrentPatternDrawer stock={selectedStock} signal={selectedSignal} analysisDate={scan.analysis_date} onSelect={setSelectedSignal} onClose={()=>{setSelectedStock(null);setSelectedSignal(null);}}/>:null}
  </div>;
}

function SignalSkeleton(){return <div className="drct-current-signal-skeleton" aria-label="패턴 분석 중"><div/><div/><section>{Array.from({length:7},(_,index)=><i key={index}/>)}</section></div>;}

function CurrentPatternDrawer({stock,signal,analysisDate,onSelect,onClose}:{stock:DrctCurrentPatternStock;signal:DrctCurrentPatternSignal;analysisDate:string;onSelect:(signal:DrctCurrentPatternSignal)=>void;onClose:()=>void}){
  const currentDetailKey=detailCacheKey(analysisDate,stock.stock_id,signal.marker_id),currentChartKey=chartCacheKey(analysisDate,stock.stock_id);
  const [detail,setDetail]=useState<DrctCurrentPatternDetail|null>(()=>detailCache.get(currentDetailKey)??null);
  const [chartBundle,setChartBundle]=useState<ChartBundle|null>(()=>chartCache.get(currentChartKey)??null);
  const [detailError,setDetailError]=useState(""),[chartError,setChartError]=useState("");
  const detailRequestId=useRef(0),chartRequestId=useRef(0);
  useEffect(()=>{const cached=detailCache.get(currentDetailKey);setDetail(cached??null);setDetailError("");const request=++detailRequestId.current;let active=true;if(!cached)loadDetail(analysisDate,stock.stock_id,signal.marker_id).then(next=>{if(active&&request===detailRequestId.current)setDetail(next);}).catch(()=>{if(active&&request===detailRequestId.current)setDetailError("패턴 차이 정보를 불러오지 못했습니다.");});return()=>{active=false;};},[analysisDate,currentDetailKey,signal.marker_id,stock.stock_id]);
  useEffect(()=>{const cached=chartCache.get(currentChartKey);setChartBundle(cached??null);setChartError("");const request=++chartRequestId.current;let active=true;if(!cached)loadChart(analysisDate,stock.stock_id).then(next=>{if(active&&request===chartRequestId.current)setChartBundle(next);}).catch(()=>{if(active&&request===chartRequestId.current)setChartError("현재 차트를 불러오지 못했습니다.");});return()=>{active=false;};},[analysisDate,currentChartKey,stock.stock_id]);
  useEffect(()=>{const close=(event:KeyboardEvent)=>{if(event.key==="Escape")onClose();};document.addEventListener("keydown",close);return()=>document.removeEventListener("keydown",close);},[onClose]);
  const activeDetail=detail?.signal.marker_id===signal.marker_id?detail:null;
  const current=activeDetail?.signal??signal;
  const reviewEvent:ChartMarkerReviewEvent={id:-signal.marker_id,stock_id:stock.stock_id,stock_code:stock.stock_code,stock_name:stock.stock_name,marker_id:signal.marker_id,marker_date:analysisDate,memo:null,review_result:null,reviewed_at:null,marker_name:signal.marker_name,symbol:signal.marker_symbol,marker_group_id:signal.marker_group_id,group_name:signal.marker_group,group_color:signal.marker_group_color};
  return <div className="drct-drawer-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)onClose();}}><aside className="drct-current-signal-drawer" role="dialog" aria-modal="true" aria-label="현재 패턴 후보 상세"><header><div><h3>{stock.stock_name}<small>{stock.stock_code}</small></h3><p>{stock.theme_names.join(" · ")} · 기준일 {analysisDate}</p></div><button type="button" aria-label="닫기" onClick={onClose}><X size={19}/></button></header><nav aria-label="감지 Marker 선택">{stock.signals.map(item=><button type="button" key={item.marker_id} className={item.marker_id===signal.marker_id?"is-active":""} onClick={()=>onSelect(item)}>{shortMarker(item.marker_name)} <b>{number(item.current_pattern_similarity)}</b></button>)}</nav><div className="drct-current-detail-body"><section className="drct-current-detail-summary"><article><span>패턴 유사도</span><strong>{number(current.current_pattern_similarity)}</strong><small>성공확률이 아닙니다.</small></article><article><span>유사 수준</span><strong>{bandLabel[current.candidate_band]}</strong><small>Marker별 학습 분포 기준</small></article><article><span>학습 성공 사례</span><strong>{current.training_case_count}건</strong><small>S-only · CORE</small></article></section><section className="drct-current-loo-range"><header><h4>과거 성공 사례 기준</h4><span>P25 이상을 패턴 후보로 판정합니다.</span></header><div><span>P25 <b>{number(current.loo_p25)}</b></span><span>중앙 <b>{number(current.loo_median)}</b></span><span>P75 <b>{number(current.loo_p75)}</b></span></div></section><section className="drct-current-chart"><h4>현재 차트</h4>{chartError?<p className="drct-signal-inline-error">{chartError}</p>:chartBundle?<ReviewChart data={chartBundle.chart} reviewEvent={reviewEvent} loading={false} markerEvents={chartBundle.events} showD0Marker onContextMenu={()=>{}}/>:<div className="drct-current-chart-skeleton" aria-label="현재 차트 불러오는 중"><i/><i/><i/><i/></div>}</section><section className="drct-current-differences"><h4>패턴 기준과 차이가 큰 항목</h4>{detailError?<p className="drct-signal-inline-error">{detailError}</p>:activeDetail?activeDetail.top_feature_differences.map(item=><article key={item.key}><div><strong>{item.label}</strong><small>차이 {number(item.robust_distance)} IQR</small></div><span>현재 <b>{number(item.current_value)}{item.unit}</b></span><ChevronRight size={14}/><span>성공 패턴 <b>{number(item.signature_median)}{item.unit}</b></span></article>):<div className="drct-current-difference-skeleton" aria-label="패턴 차이 불러오는 중">{Array.from({length:5},(_,index)=><i key={index}/>)}</div>}</section></div></aside></div>;
}

export default StockSignalTab;
