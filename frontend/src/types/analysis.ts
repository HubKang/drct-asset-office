export type AiSummarizeResponse = {
  status: string;
  target?: string | null;
  processed_count?: number;
  success_count?: number;
  failed_count?: number;
  skipped_count?: number;
  message?: string;
};
