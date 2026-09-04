import { useState } from "react";

import MarkerLearningWorkspace from "@/components/drctStockSignals/MarkerLearningWorkspace";
import SignalResearchTab from "@/components/drctStockSignals/SignalResearchTab";

function SignalResearchHub(){
  const [mode,setMode]=useState<"search"|"marker">("marker");
  return <div className="drct-research-hub"><nav className="drct-research-mode-tabs" aria-label="차트마커 학습과 검색식 관리"><button type="button" className={mode==="marker"?"is-active":""} onClick={()=>setMode("marker")}>차트마커 학습</button><button type="button" className={mode==="search"?"is-active":""} onClick={()=>setMode("search")}>검색식 관리</button></nav>{mode==="marker"?<MarkerLearningWorkspace/>:<SignalResearchTab/>}</div>;
}

export default SignalResearchHub;
