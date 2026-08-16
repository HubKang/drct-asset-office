import type { TrainingCandle } from "@/types/tradeTraining";

export type ChartMarker = { id:number; marker_group_id:number; name:string; description:string|null; symbol:string; sort_order:number; is_active:boolean; stock_count:number; marker_count:number; success_count:number; failure_count:number };
export type ChartMarkerKnowledgeItem = { id:number; title:string; summary:string|null; category_id:number|null; category_name:string|null; knowledge_type_name:string|null; is_active:boolean; sort_order:number };
export type ChartMarkerGroup = { id:number; name:string; description:string|null; color:string; sort_order:number; is_active:boolean; knowledge_items:ChartMarkerKnowledgeItem[]; markers:ChartMarker[] };
export type ChartMarkerReviewResult = "SUCCESS" | "FAILURE" | null;
export type ChartMarkerEvent = { id:number; stock_id:number; marker_id:number; marker_date:string; memo:string|null; review_result:ChartMarkerReviewResult; reviewed_at:string|null; marker_name:string; symbol:string; marker_group_id:number; group_name:string; group_color:string; created?:boolean };
export type ChartMarkerReviewEvent = ChartMarkerEvent & { stock_code:string; stock_name:string };
export type ChartMarkerReviewChart = { stock_id:number; marker_date:string; marker_index:number|null; total_candles:number; available_before:number; available_after:number; candles:TrainingCandle[] };
export type MarkerGroupWrite = { name:string; description?:string|null; color:string; sort_order:number; is_active:boolean; knowledge_item_ids:number[] };
export type MarkerWrite = { marker_group_id:number; name:string; description?:string|null; symbol:string; sort_order:number; is_active:boolean };
