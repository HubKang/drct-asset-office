import { apiRequest } from "@/services/api/apiClient";
import type { ChartMarkerEvent, ChartMarkerGroup, ChartMarkerReviewChart, ChartMarkerReviewEvent, ChartMarkerReviewResult, MarkerGroupWrite, MarkerWrite } from "@/types/chartMarker";

export const chartMarkerApiRepository = {
  catalog: (activeOnly=false) => apiRequest<{items:ChartMarkerGroup[]}>(`/chart-markers/catalog?active_only=${activeOnly}`),
  createGroup: (payload:MarkerGroupWrite) => apiRequest<ChartMarkerGroup>("/chart-markers/groups", {method:"POST", body:JSON.stringify(payload)}),
  updateGroup: (id:number,payload:Partial<MarkerGroupWrite>) => apiRequest<ChartMarkerGroup>(`/chart-markers/groups/${id}`, {method:"PATCH",body:JSON.stringify(payload)}),
  createMarker: (payload:MarkerWrite) => apiRequest(`/chart-markers/markers`, {method:"POST",body:JSON.stringify(payload)}),
  updateMarker: (id:number,payload:Partial<Omit<MarkerWrite,"marker_group_id">>) => apiRequest(`/chart-markers/markers/${id}`, {method:"PATCH",body:JSON.stringify(payload)}),
  listStockEvents: (stockId:number,endDate?:string) => apiRequest<{items:ChartMarkerEvent[]}>(`/chart-markers/events?stock_id=${stockId}${endDate?`&end_date=${endDate}`:""}`),
  upsertEvent: (payload:{stock_id:number;marker_id:number;marker_date:string;memo:string|null}) => apiRequest<ChartMarkerEvent>("/chart-markers/events",{method:"PUT",body:JSON.stringify(payload)}),
  updateEvent: (id:number,payload:{memo?:string|null;review_result?:ChartMarkerReviewResult}) => apiRequest<ChartMarkerEvent>(`/chart-markers/events/${id}`,{method:"PATCH",body:JSON.stringify(payload)}),
  deleteEvent: (id:number) => apiRequest<{deleted:boolean;id:number}>(`/chart-markers/events/${id}`,{method:"DELETE"}),
  reviewEvents: (markerId:number) => apiRequest<{items:ChartMarkerReviewEvent[]}>(`/chart-markers/review/events?marker_id=${markerId}`),
  reviewChart: (stockId:number,markerDate:string,candleCount=81) => apiRequest<ChartMarkerReviewChart>(`/chart-markers/review/chart?stock_id=${stockId}&marker_date=${markerDate}&candle_count=${candleCount}`),
};
