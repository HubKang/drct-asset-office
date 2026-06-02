import type { TradeJournal, TradeMethod } from "@/types/tradeJournal";

export type TradeReviewStatus = "미복기" | "복기완료";
export type TradeGrade = "A" | "B" | "C" | "D" | "";

export type TradeReview = {
  id?: number | null;
  journal_id: number;
  method_id?: number | null;
  review_status: TradeReviewStatus;
  trade_grade?: TradeGrade | null;
  principle_followed?: string | null;
  entry_quality?: string | null;
  exit_quality?: string | null;
  risk_control_quality?: string | null;
  emotion_control_quality?: string | null;
  impulse_trade: number;
  main_mistake?: string | null;
  good_point?: string | null;
  improvement_point?: string | null;
  next_action?: string | null;
  review_memo?: string | null;
  gpt_review_text?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type TradeReviewCheckItem = {
  id: number;
  review_id: number;
  journal_id: number;
  method_id?: number | null;
  item_type: "entry" | "exit" | "failure" | "checklist" | string;
  item_order: number;
  item_text: string;
  is_checked: number;
  note?: string | null;
  source_field?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type TradeReviewListItem = {
  journal_id: number;
  review_id?: number | null;
  stock_name: string;
  stock_code?: string | null;
  buy_date: string;
  sell_date?: string | null;
  method_id?: number | null;
  method_name?: string | null;
  result_type?: string | null;
  profit_rate?: number | null;
  realized_profit?: number | null;
  image_count: number;
  review_status: TradeReviewStatus;
  trade_grade?: TradeGrade | null;
  principle_followed?: string | null;
  main_mistake?: string | null;
  impulse_trade: number;
};

export type TradeReviewListResponse = {
  items: TradeReviewListItem[];
  total_count: number;
};

export type TradeReviewDetail = {
  journal: TradeJournal;
  method?: TradeMethod | null;
  review: TradeReview;
  check_items: TradeReviewCheckItem[];
  image_count: number;
};

export type TradeReviewSaveRequest = {
  review_status?: TradeReviewStatus;
  trade_grade?: TradeGrade;
  principle_followed?: string;
  entry_quality?: string;
  exit_quality?: string;
  risk_control_quality?: string;
  emotion_control_quality?: string;
  impulse_trade?: boolean;
  main_mistake?: string;
  good_point?: string;
  improvement_point?: string;
  next_action?: string;
  review_memo?: string;
  gpt_review_text?: string;
  check_items?: Array<{
    id: number;
    is_checked?: boolean;
    note?: string;
  }>;
};

export type TradeReviewSummary = {
  total_trades: number;
  reviewed_count: number;
  unreviewed_count: number;
  review_rate: number;
  principle_followed_count: number;
  principle_violation_count: number;
  impulse_trade_count: number;
  grade_counts: Record<string, number>;
  top_mistakes: Array<{ name: string; count: number }>;
};

export type TradeReviewGptPackage = {
  journal_id: number;
  stock_name?: string | null;
  package_title: string;
  generated_prompt: string;
  sections: Record<string, string>;
};
