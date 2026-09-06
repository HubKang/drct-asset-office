import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { BarChart3, ChevronRight, RefreshCw, Search, X } from "lucide-react";

import { ReviewChart, normalizeReviewChart } from "@/pages/ChartMarkerReviewPage";
import { repositories } from "@/services";
import type { ChartMarkerEvent, ChartMarkerReviewChart, ChartMarkerReviewEvent } from "@/types/chartMarker";
import type { DrctAutomaticImprovementStatus, DrctCurrentPatternBand, DrctCurrentPatternDetail, DrctCurrentPatternScan, DrctCurrentPatternScanWithDiagnostics, DrctCurrentPatternSignal, DrctCurrentPatternStock, DrctMarkerPolicyValidation, DrctPatternDiagnosticSample, DrctPatternDiagnostics, DrctPatternMarkerDiagnostic, DrctPatternDistribution } from "@/types/drctStockSignal";

const bandLabel:Record<DrctCurrentPatternBand,string>={VERY_SIMILAR:"매우 유사",HIGH_SIMILARITY:"높은 유사",SIMILAR:"유사",BELOW_CANDIDATE:"현재 후보 아님"};
const shortMarker=(value:string)=>value.replace(/^.*? - /,"");
const number=(value:number)=>value.toFixed(1);
const detailCache=new Map<string,DrctCurrentPatternDetail>();
const detailRequests=new Map<string,Promise<DrctCurrentPatternDetail>>();
type ChartBundle={chart:ChartMarkerReviewChart;events:ChartMarkerEvent[]};
const chartCache=new Map<string,ChartBundle>();
const chartRequests=new Map<string,Promise<ChartBundle>>();
const policyValidationCache=new Map<string,DrctMarkerPolicyValidation>();
const policyValidationRequests=new Map<string,Promise<DrctMarkerPolicyValidation>>();
let scanCache:DrctCurrentPatternScan|null=null;
let scanRequest:Promise<DrctCurrentPatternScan>|null=null;
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

function loadScan(){
  if(scanRequest)return scanRequest;
  scanRequest=repositories.drctStockSignals.scanCurrentMarkerPatterns().then(result=>{scanCache=result;return result;}).finally(()=>{scanRequest=null;});
  return scanRequest;
}

function loadPolicyValidation(analysisDate:string,markerId:number){
  const key=`${analysisDate}:${markerId}`,cached=policyValidationCache.get(key);
  if(cached)return Promise.resolve(cached);
  const pending=policyValidationRequests.get(key);
  if(pending)return pending;
  const request=repositories.drctStockSignals.markerPolicyValidation(markerId,analysisDate).then(result=>{policyValidationCache.set(key,result);return result;}).finally(()=>policyValidationRequests.delete(key));
  policyValidationRequests.set(key,request);
  return request;
}

function StockSignalTab() {
  const [scan,setScan]=useState<DrctCurrentPatternScan|null>(()=>scanCache);
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const [group,setGroup]=useState("ALL"),[query,setQuery]=useState("");
  const [selectedStock,setSelectedStock]=useState<DrctCurrentPatternStock|null>(null);
  const [selectedSignal,setSelectedSignal]=useState<DrctCurrentPatternSignal|null>(null);
  const [diagnosticsOpen,setDiagnosticsOpen]=useState(false),[diagnostics,setDiagnostics]=useState<DrctPatternDiagnostics|null>(null),[diagnosticsBusy,setDiagnosticsBusy]=useState(false);
  const requestId=useRef(0),prefetchTimer=useRef<ReturnType<typeof setTimeout>|null>(null);
  const load=useCallback(async()=>{const request=++requestId.current;setBusy(true);setError("");try{const next=await loadScan();if(request===requestId.current){setScan(next);setDiagnostics(null);}}catch{if(request===requestId.current)setError("종목 시그널을 계산하지 못했습니다.");}finally{if(request===requestId.current)setBusy(false);}},[]);
  const openDiagnostics=useCallback(async()=>{if(!scan)return;setDiagnosticsOpen(true);if(diagnostics)return;setDiagnosticsBusy(true);try{setDiagnostics(await repositories.drctStockSignals.currentMarkerPatternDiagnostics(scan.analysis_date));}catch{setDiagnosticsOpen(false);setError("추천 기준 점검 정보를 불러오지 못했습니다.");}finally{setDiagnosticsBusy(false);}},[diagnostics,scan]);
  useEffect(()=>{void load();},[load]);
  useEffect(()=>()=>{if(prefetchTimer.current)clearTimeout(prefetchTimer.current);},[]);
  const groups=useMemo(()=>Array.from(new Set((scan?.stocks??[]).flatMap(stock=>stock.signals.map(signal=>signal.marker_group)))).sort(),[scan]);
  const stocks=useMemo(()=>{const keyword=query.trim().toLowerCase();return (scan?.stocks??[]).filter(stock=>(group==="ALL"||stock.signals.some(signal=>signal.marker_group===group))&&(!keyword||stock.stock_name.toLowerCase().includes(keyword)||stock.stock_code.includes(keyword))).sort((a,b)=>(b.signals[0]?.current_pattern_similarity??-Infinity)-(a.signals[0]?.current_pattern_similarity??-Infinity)||a.stock_name.localeCompare(b.stock_name,"ko"));},[scan,group,query]);
  const openDetail=(stock:DrctCurrentPatternStock)=>{setSelectedStock(stock);setSelectedSignal(stock.signals[0]??null);};
  const openDiagnosticSample=(sample:DrctPatternDiagnosticSample,marker:DrctPatternMarkerDiagnostic)=>{const similarity=sample.similarity,loo=marker.loo_distribution;const candidateBand:DrctCurrentPatternBand=similarity>=loo.p75?"VERY_SIMILAR":similarity>=loo.median?"HIGH_SIMILARITY":similarity>=loo.p25?"SIMILAR":"BELOW_CANDIDATE";const signal:DrctCurrentPatternSignal={marker_id:marker.marker_id,marker_name:marker.marker_name,marker_symbol:marker.marker_symbol,marker_group_id:marker.marker_group_id,marker_group:marker.marker_group,marker_group_color:marker.marker_group_color,current_pattern_similarity:similarity,candidate_band:candidateBand,empirical_percentile:sample.empirical_percentile,loo_p25:loo.p25,loo_median:loo.median,loo_p75:loo.p75,training_case_count:marker.training_s_count};setSelectedStock({stock_id:sample.stock_id,stock_code:sample.stock_code,stock_name:sample.stock_name,theme_names:sample.theme_names,signals:[signal]});setSelectedSignal(signal);};
  const openWithKeyboard=(event:ReactKeyboardEvent<HTMLElement>,stock:DrctCurrentPatternStock)=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();openDetail(stock);}};
  const schedulePrefetch=(stock:DrctCurrentPatternStock)=>{if(!scan?.analysis_date||!stock.signals[0])return;if(prefetchTimer.current)clearTimeout(prefetchTimer.current);prefetchTimer.current=setTimeout(()=>{void loadDetail(scan.analysis_date!,stock.stock_id,stock.signals[0].marker_id).catch(()=>undefined);},200);};
  const clearPrefetch=()=>{if(prefetchTimer.current){clearTimeout(prefetchTimer.current);prefetchTimer.current=null;}};
  return <div className="drct-current-signals">
    <header className="drct-current-signals-head"><div><h2>현재 종목 시그널</h2><p>국내 활성 테마 연결종목에서 학습된 성공 Marker 패턴과 유사한 종목을 찾습니다.</p></div><div className="drct-current-signal-actions"><button className="btn btn-secondary" type="button" disabled={!scan||diagnosticsBusy} onClick={()=>void openDiagnostics()}>{diagnosticsBusy?"점검 불러오는 중":"추천 기준 점검"}</button><button className="btn btn-secondary" type="button" disabled={busy} onClick={()=>void load()}><RefreshCw className={busy?"is-spinning":""} size={15}/>{busy?"패턴 분석 중":"새로고침"}</button></div></header>
    {error?<div className="drct-current-signal-error" role="alert"><span>{error}</span><button type="button" onClick={()=>void load()}>다시 시도</button></div>:null}
    {!scan?<SignalSkeleton/>:<>
      <section className="drct-current-signal-metrics" aria-label="현재 패턴 분석 요약">{[["기준일",scan.analysis_date?.slice(5).replace("-",".")??"-"],["분석 종목",`${scan.universe_count}개`],["적용 Marker",`${scan.eligible_marker_count}개`],["패턴 후보",`${scan.candidate_stock_count}개`]].map(([label,value])=><article key={label}><span>{label}</span><strong>{value}</strong></article>)}</section>
      <section className="drct-current-signal-filter" aria-label="종목 시그널 필터"><label><span>마커 그룹</span><select aria-label="마커 그룹" value={group} onChange={event=>setGroup(event.target.value)}><option value="ALL">전체</option>{groups.map(name=><option value={name} key={name}>{name}</option>)}</select></label><label className="drct-current-signal-search"><Search size={15}/><input aria-label="종목명 또는 코드 검색" value={query} onChange={event=>setQuery(event.target.value)} placeholder="종목명 또는 코드 검색"/></label><span>후보 {stocks.length}개</span></section>
      <section className="drct-current-signal-panel"><header><div><h3>패턴 후보</h3><p>패턴 유사도는 현재 차트와 과거 성공 Marker 패턴의 유사성으로, 성공확률이 아닙니다.</p></div>{busy?<span className="is-busy">패턴 분석 중…</span>:<span title={`전체 분석 ${scan.timings.total_ms}ms · SQL ${scan.timings.sql_query_count}회`}>ⓘ 분석정보</span>}</header>
        {stocks.length?<div className="drct-current-signal-table">{stocks.map(stock=>{const primary=stock.signals[0],secondary=stock.signals.slice(1),secondaryTitle=secondary.map(item=>`${shortMarker(item.marker_name)} ${number(item.current_pattern_similarity)}`).join("\n");return <article key={stock.stock_id} role="button" tabIndex={0} aria-label={`${stock.stock_name} 종목 시그널 상세 보기`} className={selectedStock?.stock_id===stock.stock_id?"is-selected":""} onClick={()=>openDetail(stock)} onKeyDown={event=>openWithKeyboard(event,stock)} onMouseEnter={()=>schedulePrefetch(stock)} onMouseLeave={clearPrefetch} onFocus={()=>schedulePrefetch(stock)} onBlur={clearPrefetch}><div className="drct-current-stock"><strong>{stock.stock_name}</strong><small>{stock.stock_code}</small></div><div className="drct-current-themes" title={stock.theme_names.join(" · ")}>{stock.theme_names.join(" · ")}</div><div className="drct-current-marker-primary"><span style={{"--marker-color":primary.marker_group_color} as CSSProperties}>{shortMarker(primary.marker_name)}</span>{secondary.length?<em title={secondaryTitle} aria-label={`추가 감지 Marker ${secondary.length}개: ${secondaryTitle.replace(/\n/g,", ")}`}>+{secondary.length}</em>:null}</div><strong className="drct-current-similarity" title="현재 차트와 과거 성공 Marker 패턴의 유사도이며 성공확률이 아닙니다.">{number(primary.current_pattern_similarity)}</strong><span className={`drct-current-band is-${primary.candidate_band.toLowerCase()}`}>{bandLabel[primary.candidate_band]}</span></article>;})}</div>:<div className="drct-current-signal-empty"><BarChart3 size={28}/><strong>현재 패턴 후보가 없습니다.</strong><p>현재 연결종목 중 과거 성공 Marker 패턴과 충분히 유사한 종목이 발견되지 않았습니다.</p></div>}
      </section>
    </>}
    {diagnosticsOpen&&scan&&diagnostics?<SimplePatternDiagnosticsDrawer scan={{...scan,diagnostics}} onClose={()=>setDiagnosticsOpen(false)} onOpenSample={openDiagnosticSample}/>:null}
    {selectedStock&&selectedSignal&&scan?.analysis_date?<CurrentPatternDrawer stock={selectedStock} signal={selectedSignal} analysisDate={scan.analysis_date} onSelect={setSelectedSignal} onClose={()=>{setSelectedStock(null);setSelectedSignal(null);}}/>:null}
  </div>;
}

function SignalSkeleton(){return <div className="drct-current-signal-skeleton" aria-label="패턴 분석 중"><div/><div/><section>{Array.from({length:7},(_,index)=><i key={index}/>)}</section></div>;}

type DiagnosticThreshold="p25"|"median"|"p75"|"p90";
const recommendationLevels:{key:DiagnosticThreshold;label:string;level:25|50|75|90;help:string}[]=[
  {key:"p25",label:"넓게",level:25,help:"과거 성공 사례의 넓은 범위까지 후보로 포함하는 기준입니다."},
  {key:"median",label:"기본",level:50,help:"과거 성공 사례의 중간 수준을 기준으로 합니다."},
  {key:"p75",label:"엄격",level:75,help:"성공 사례 중 더 닮은 종목을 중심으로 봅니다."},
  {key:"p90",label:"매우 엄격",level:90,help:"성공 사례 중 매우 강하게 닮은 종목만 봅니다."},
];
const rangeLabels={NARROW:"선별적",MODERATE:"적당함",BROAD:"넓음",VERY_BROAD:"매우 넓음"} as const;
const interpretationLabels={SELECTIVE:"현재 기준에서도 비교적 선별적으로 후보를 찾고 있습니다.",BROAD_REDUCES_STRICT:"현재 기준은 후보를 넓게 찾습니다. 엄격한 기준에서는 후보가 크게 줄어듭니다.",BROAD_STABLE:"현재 기준에서 후보가 넓게 잡히며, 엄격한 기준에서도 감소 폭이 크지 않습니다.",HARD_TO_DISTINGUISH:"현재 패턴 특징만으로는 이 Marker를 일반 종목과 구분하기 어려운 구간이 있습니다."} as const;
const actionLabels={KEEP_CURRENT_REVIEW:"현재 기준에서도 후보가 충분히 좁습니다. 대표 차트를 확인해 보세요.",REVIEW_STRICT_CHARTS:"후보가 넓게 잡히고 있습니다. 엄격 기준의 실제 차트를 확인해 보세요.",REVIEW_STRICT_AND_FEATURES:"엄격 기준의 차트를 확인하고, 구분이 어렵다면 향후 차트 모양 특징 보강을 검토하세요."} as const;
const segmentLabels:Record<string,string>={p90_or_above:"90 이상",p75_to_p90:"75~90",median_to_p75:"50~75",p25_to_median:"25~50",below_p25:"현재 기준 미만"};

function DistributionRange({label,tone,distribution,n}:{label:string;tone:"loo"|"current";distribution:DrctPatternDistribution;n:number}){
  const points=[{key:"min",label:"최저",value:distribution.min},{key:"p25",label:"25",value:distribution.p25},{key:"median",label:"50",value:distribution.median},{key:"p75",label:"75",value:distribution.p75},{key:"p90",label:"90",value:distribution.p90},{key:"max",label:"최고",value:distribution.max}];
  return <article className={`drct-diagnostic-range is-${tone}`}><header><strong>{label}</strong><span>{n}건</span></header><div className="drct-diagnostic-scale" aria-label={`${label} 유사도 분포`}><i/><b style={{left:`${distribution.min}%`,width:`${Math.max(0,distribution.max-distribution.min)}%`}}/>{points.map(point=><em key={point.key} style={{left:`${Math.max(0,Math.min(100,point.value))}%`}} title={`${point.label} ${number(point.value)}`}/>)}</div><dl>{points.map(point=><div key={point.key}><dt>{point.label}</dt><dd>{number(point.value)}</dd></div>)}</dl></article>;
}

function PatternDiagnosticsDrawer({scan,onClose,onOpenSample}:{scan:DrctCurrentPatternScanWithDiagnostics;onClose:()=>void;onOpenSample:(sample:DrctPatternDiagnosticSample,marker:DrctPatternMarkerDiagnostic)=>void}){
  const markers=scan.diagnostics.markers;
  const [markerId,setMarkerId]=useState(markers[0]?.marker_id??0),[threshold,setThreshold]=useState<DiagnosticThreshold>("p25");
  const marker=markers.find(item=>item.marker_id===markerId)??markers[0];
  useEffect(()=>{const close=(event:KeyboardEvent)=>{if(event.key==="Escape")onClose();};document.addEventListener("keydown",close);return()=>document.removeEventListener("keydown",close);},[onClose]);
  const selectedLevel=recommendationLevels.find(item=>item.key===threshold)??recommendationLevels[0];
  return <div className="drct-drawer-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)onClose();}}><aside className="drct-pattern-diagnostic-drawer" role="dialog" aria-modal="true" aria-label="추천 기준 점검"><header><div><h3>추천 기준 점검</h3><p>성공 사례와 현재 종목을 비교해 이 Marker가 후보를 얼마나 넓게 찾는지 확인합니다.</p></div><button type="button" aria-label="닫기" onClick={onClose}><X size={19}/></button></header><div className="drct-pattern-diagnostic-body"><section className="drct-diagnostic-summary">{[["현재 기준",`${scan.candidate_stock_count}종목`],["엄격하게",`${scan.diagnostics.policies.p75.candidate_stock_count}종목`],["매우 엄격하게",`${scan.diagnostics.policies.p90.candidate_stock_count}종목`],["복수 패턴 종목",`${scan.diagnostics.policies.p25.multiple_marker_stock_count}종목`]].map(([label,value])=><article key={label}><span>{label}</span><strong>{value}</strong></article>)}</section><section className="drct-diagnostic-workspace"><nav aria-label="Marker 추천 기준 목록"><header><h4>Marker 목록</h4><span>적용 {markers.length}개</span></header>{markers.map(item=><button type="button" className={item.marker_id===marker?.marker_id?"is-active":""} key={item.marker_id} onClick={()=>{setMarkerId(item.marker_id);setThreshold("p25");}}><i style={{background:item.marker_group_color}}/><span><strong>{shortMarker(item.marker_name)}</strong><small>성공 학습 {item.training_s_count}건 · 후보 {item.friendly.current_candidate_count}개</small></span><em>후보 범위 {rangeLabels[item.friendly.candidate_range_status]} · 엄격하게 {item.friendly.reference_levels.level_75.candidate_count}개</em></button>)}</nav>{marker?<main><header><div><span style={{color:marker.marker_group_color}}>{marker.marker_group}</span><h4>{shortMarker(marker.marker_name)}</h4></div><small>추천 기준 자동 점검</small></header><section className="drct-friendly-marker-summary"><article><span>성공 학습</span><strong>{marker.training_s_count}건</strong></article><article><span>현재 기준 후보</span><strong>{marker.friendly.current_candidate_count}종목</strong></article><article><span>엄격 기준 후보</span><strong>{marker.friendly.reference_levels.level_75.candidate_count}종목</strong></article><article><span>후보 범위</span><strong className={`is-${marker.friendly.candidate_range_status.toLowerCase()}`}>{rangeLabels[marker.friendly.candidate_range_status]}</strong></article></section><section className={`drct-friendly-interpretation is-${marker.friendly.discrimination_status.toLowerCase()}`}><h5>시스템 해석</h5><p>{interpretationLabels[marker.friendly.interpretation_status]}{marker.friendly.interpretation_status==="HARD_TO_DISTINGUISH"?" 엄격하게 보면 후보가 줄어드는지도 함께 확인하세요.":""}</p></section><section className="drct-diagnostic-simulation"><header><div><h5>추천 범위 비교</h5><p>기준을 바꿔 보면서 후보 종목이 얼마나 달라지는지 확인합니다. 실제 운영 기준은 변경되지 않습니다.</p></div><strong>{marker.thresholds[threshold].candidate_count}종목</strong></header><nav>{recommendationLevels.map(item=><button type="button" className={threshold===item.key?"is-active":""} key={item.key} title={`유사도 기준 ${item.level}: ${item.help}`} onClick={()=>setThreshold(item.key)}><strong>{item.label}</strong><small>기준 {item.level}</small></button>)}</nav><p className="drct-friendly-level-help">유사도 기준 {selectedLevel.level} · {selectedLevel.help}</p><div className="drct-diagnostic-samples">{marker.thresholds[threshold].samples.map(sample=><button type="button" key={sample.stock_id} onClick={()=>onOpenSample(sample,marker)}><span><strong>{sample.stock_name}</strong><small>{sample.stock_code} · {sample.theme_names.join(" · ")}</small></span><b>{number(sample.similarity)}</b></button>)}</div></section><section className="drct-shadow-research"><header><div><h5>자동 개선 연구</h5><p>현재 운영 기준은 유지한 채 후보 범위 축소 방식을 자동 비교합니다.</p></div><span>검증 중</span></header><div><article><span>현재 후보</span><strong>{marker.friendly.current_candidate_count}종목</strong></article><ChevronRight size={16}/><article><span>개선 후보</span><strong>{marker.friendly.shadow.candidate_count}종목</strong></article></div><small>새 성공 사례가 추가되면 학습 기준과 개선 후보가 자동으로 다시 계산됩니다.</small></section><section className="drct-friendly-action"><h5>현재 권장 행동</h5><p>{actionLabels[marker.friendly.action_hint]}</p></section><details className="drct-friendly-details"><summary>세부 비교 보기</summary><section className="drct-diagnostic-distributions"><h5>성공 사례와 현재 분석 종목 비교</h5><p>점수가 분포한 범위를 비교해 후보가 넓게 잡히는 이유를 확인합니다.</p><DistributionRange label="과거 성공 사례" tone="loo" distribution={marker.loo_distribution} n={marker.loo_evaluated_count}/><DistributionRange label="현재 분석 종목" tone="current" distribution={marker.current_distribution} n={marker.current_evaluable_count}/></section></details><details className="drct-friendly-details"><summary>알고리즘 상세</summary><section className="drct-algorithm-friendly-detail"><p>운영 기준은 과거 성공 사례 P25를 사용하는 Baseline V1입니다. SHADOW V1은 Baseline을 충족하면서 현재 분석 종목 P90 이상인 사례만 비교하며 운영 후보에는 적용하지 않습니다.</p><dl><div><dt>Signature / Similarity</dt><dd>V1 / V1</dd></div><div><dt>운영 정책</dt><dd>{scan.diagnostics.baseline_policy_version}</dd></div><div><dt>개선 연구</dt><dd>{marker.friendly.shadow.policy_version}</dd></div><div><dt>상태</dt><dd>Runtime · 비저장</dd></div><div><dt>Median Gap</dt><dd>{number(marker.median_gap)}</dd></div><div><dt>P75 Gap</dt><dd>{number(marker.p75_gap)}</dd></div></dl><small>{marker.p90_sample_warning}</small></section><section className="drct-diagnostic-segments"><h5>기술 구간별 차트 검토</h5><div>{Object.entries(marker.segments).map(([key,segment])=><article key={key}><header><strong>{segmentLabels[key]}</strong><span>{segment.count}개</span></header>{segment.samples.map(sample=><button type="button" key={sample.stock_id} onClick={()=>onOpenSample(sample,marker)}><span>{sample.stock_name}{!sample.is_current_candidate?<em>현재 후보 아님</em>:null}</span><b>{number(sample.similarity)}</b></button>)}</article>)}</div></section></details></main>:<div className="drct-current-signal-empty"><strong>분석 가능한 Marker가 없습니다.</strong></div>}</section></div></aside></div>;
}

const improvementStatusLabels:Record<DrctAutomaticImprovementStatus,string>={NEED_MORE_DATA:"데이터 더 필요",VALIDATING:"자동 검증 중",IMPROVEMENT_READY:"개선안 검토 가능",KEEP_CURRENT:"현재 방식 유지"};

function SimplePatternDiagnosticsDrawer({scan,onClose,onOpenSample}:{scan:DrctCurrentPatternScanWithDiagnostics;onClose:()=>void;onOpenSample:(sample:DrctPatternDiagnosticSample,marker:DrctPatternMarkerDiagnostic)=>void}){
  const markers=scan.diagnostics.markers;
  const [markerId,setMarkerId]=useState(markers[0]?.marker_id??0);
  const [validation,setValidation]=useState<DrctMarkerPolicyValidation|null>(()=>scan.analysis_date?policyValidationCache.get(`${scan.analysis_date}:${markers[0]?.marker_id??0}`)??null:null);
  const [validationBusy,setValidationBusy]=useState(false),[validationError,setValidationError]=useState("");
  const marker=markers.find(item=>item.marker_id===markerId)??markers[0];
  useEffect(()=>{const close=(event:KeyboardEvent)=>{if(event.key==="Escape")onClose();};document.addEventListener("keydown",close);return()=>document.removeEventListener("keydown",close);},[onClose]);
  useEffect(()=>{
    if(!marker||!scan.analysis_date)return;
    const key=`${scan.analysis_date}:${marker.marker_id}`,cached=policyValidationCache.get(key);
    let active=true;
    setValidation(cached??null);setValidationError("");
    if(!cached){setValidationBusy(true);loadPolicyValidation(scan.analysis_date,marker.marker_id).then(result=>{if(active)setValidation(result);}).catch(()=>{if(active)setValidationError("자동 검증 결과를 불러오지 못했습니다.");}).finally(()=>{if(active)setValidationBusy(false);});}else setValidationBusy(false);
    return()=>{active=false;};
  },[marker,scan.analysis_date]);
  if(!marker)return <div className="drct-drawer-backdrop"><aside className="drct-pattern-diagnostic-drawer"><div className="drct-current-signal-empty"><strong>분석 가능한 Marker가 없습니다.</strong></div></aside></div>;
  const status=validation?.automatic_improvement_status??"VALIDATING";
  const statusLabel=improvementStatusLabels[status];
  const average=(value:number|null|undefined)=>value==null?"-":`${Math.round(value)}종목`;
  return <div className="drct-drawer-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)onClose();}}><aside className="drct-pattern-diagnostic-drawer is-simple" role="dialog" aria-modal="true" aria-label="추천 기준 점검">
    <header><div><h3>추천 기준 점검</h3><p>현재 방식과 추천 개선안을 자동으로 비교합니다. 사용자가 기준을 조절할 필요는 없습니다.</p></div><button type="button" aria-label="닫기" onClick={onClose}><X size={19}/></button></header>
    <div className="drct-pattern-diagnostic-body">
      <section className="drct-diagnostic-summary is-simple-summary"><article><span>현재 후보</span><strong>{scan.candidate_stock_count}종목</strong></article><article><span>추천 개선안</span><strong>{scan.diagnostics.shadow_policy.candidate_stock_count}종목</strong></article><article><span>현재 상태</span><strong className={`is-${status.toLowerCase()}`}>{validationBusy?"알고리즘 검증 중":statusLabel}</strong></article></section>
      <section className="drct-diagnostic-workspace is-simple-workspace"><nav aria-label="Marker 목록"><header><h4>Marker 선택</h4><span>적용 {markers.length}개</span></header>{markers.map(item=>{const cached=scan.analysis_date?policyValidationCache.get(`${scan.analysis_date}:${item.marker_id}`):null;return <button type="button" className={item.marker_id===marker.marker_id?"is-active":""} key={item.marker_id} onClick={()=>setMarkerId(item.marker_id)}><i style={{background:item.marker_group_color}}/><span><strong>{shortMarker(item.marker_name)}</strong><small>성공 학습 {item.training_s_count}건 · 현재 후보 {item.friendly.current_candidate_count}종목</small></span><em>개선안 {item.friendly.shadow.candidate_count}종목 · {cached?improvementStatusLabels[cached.automatic_improvement_status]:"자동 검증"}</em></button>;})}</nav>
        <main><header><div><span style={{color:marker.marker_group_color}}>{marker.marker_group}</span><h4>{shortMarker(marker.marker_name)}</h4></div><small>자동학습 · 자동검증</small></header>
          <section className="drct-friendly-marker-summary is-simple-marker-summary"><article><span>성공 학습</span><strong>{marker.training_s_count}건</strong></article><article><span>현재 후보</span><strong>{marker.friendly.current_candidate_count}종목</strong></article><article><span>개선안 후보</span><strong>{marker.friendly.shadow.candidate_count}종목</strong></article><article><span>자동 개선</span><strong className={`is-${status.toLowerCase()}`}>{validationBusy?"검증 중":statusLabel}</strong></article></section>
          {validationError?<p className="drct-signal-inline-error" role="alert">{validationError}</p>:validationBusy?<section className="drct-validation-loading"><RefreshCw className="is-spinning" size={18}/><div><strong>알고리즘 검증 중</strong><p>과거 성공 사례를 다시 확인하고 있습니다.</p></div></section>:validation?<section className={`drct-historical-validation is-${status.toLowerCase()}`}><header><div><h5>과거 성공 사례 재검증</h5><p>{validation.status_message}</p></div><strong>{statusLabel}</strong></header><div><article><span>현재 방식</span><strong>{validation.baseline_hit_count}/{validation.historical_valid_target_count} 다시 탐지</strong></article><article><span>추천 개선안</span><strong>{validation.improvement_hit_count}/{validation.historical_valid_target_count} 다시 탐지</strong></article><article><span>평균 후보</span><strong>{average(validation.baseline_average_candidate_count)} <ChevronRight size={14}/> {average(validation.improvement_average_candidate_count)}</strong></article></div><small>새 성공 사례가 추가되면 다음 검증에서 자동으로 반영됩니다. 별도 조작은 필요하지 않습니다.</small></section>:null}
          <details className="drct-friendly-details"><summary>후보 비교</summary><section className="drct-simple-candidate-compare"><article><header><h5>현재 방식</h5><strong>{marker.friendly.current_candidate_count}종목</strong></header>{marker.thresholds.p25.samples.slice(0,5).map(sample=><button type="button" key={sample.stock_id} onClick={()=>onOpenSample(sample,marker)}><span>{sample.stock_name}</span><b>{number(sample.similarity)}</b></button>)}</article><article><header><h5>추천 개선안</h5><strong>{marker.friendly.shadow.candidate_count}종목</strong></header>{marker.friendly.shadow.samples.slice(0,5).map(sample=><button type="button" key={sample.stock_id} onClick={()=>onOpenSample(sample,marker)}><span>{sample.stock_name}</span><b>{number(sample.similarity)}</b></button>)}</article></section></details>
          <details className="drct-friendly-details"><summary>추천 범위 자세히 보기</summary><section className="drct-diagnostic-policy"><h4>연구용 범위 비교</h4><p>아래 값은 비교 정보이며 실제 운영 기준을 변경하지 않습니다.</p><div>{recommendationLevels.map(item=><article key={item.key}><span>{item.label}</span><strong>{marker.thresholds[item.key].candidate_count}종목</strong><small>{item.help}</small></article>)}</div></section></details>
          <details className="drct-friendly-details"><summary>알고리즘 상세</summary><section className="drct-algorithm-friendly-detail"><p>현재 운영 방식과 개선안은 분리되어 있으며, 검증 결과만으로 자동 교체하지 않습니다.</p><dl><div><dt>현재 방식</dt><dd>{scan.diagnostics.baseline_policy_version}</dd></div><div><dt>추천 개선안</dt><dd>{marker.friendly.shadow.policy_version}</dd></div><div><dt>계산 방식</dt><dd>Runtime · 비저장</dd></div><div><dt>검증 사례</dt><dd>{validation?.historical_valid_target_count??0}건</dd></div></dl>{validation?<><small>{validation.historical_universe_notice}</small><section className="drct-validation-targets">{validation.targets.map(target=><article key={target.chart_marker_event_id}><span>{target.d0} · {target.stock_name}</span><b>현재 {target.baseline_hit?"탐지":"미탐지"} · 개선 {target.improvement_hit?"탐지":"미탐지"}</b></article>)}</section></>:null}<section className="drct-diagnostic-distributions"><DistributionRange label="과거 성공 사례" tone="loo" distribution={marker.loo_distribution} n={marker.loo_evaluated_count}/><DistributionRange label="현재 분석 종목" tone="current" distribution={marker.current_distribution} n={marker.current_evaluable_count}/></section></section></details>
        </main>
      </section>
    </div>
  </aside></div>;
}

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
