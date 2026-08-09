import type { TrainingCandle } from "@/types/tradeTraining";

export type ChartMarker = { id:number; marker_group_id:number; name:string; description:string|null; symbol:string; sort_order:number; is_active:boolean };
export type ChartMarkerGroup = { id:number; name:string; description:string|null; color:string; sort_order:number; is_active:boolean; markers:ChartMarker[] };
export type ChartMarkerEvent = { id:number; stock_id:number; marker_id:number; marker_date:string; memo:string|null; marker_name:string; symbol:string; marker_group_id:number; group_name:string; group_color:string; created?:boolean };
export type ChartMarkerReviewEvent = ChartMarkerEvent & { stock_code:string; stock_name:string };
export type ChartMarkerReviewChart = { stock_id:number; marker_date:string; before_trading_days:number; after_trading_days:number; candles:TrainingCandle[] };
export type MarkerGroupWrite = { name:string; description?:string|null; color:string; sort_order:number; is_active:boolean };
export type MarkerWrite = { marker_group_id:number; name:string; description?:string|null; symbol:string; sort_order:number; is_active:boolean };
