export type AdvisoryPackageType = "swing" | "long_term";

export type AdvisoryPackageGenerateRequest = {
  stock_id: number;
  news_ids: number[];
  disclosure_ids: number[];
  title: string;
  purpose: string;
  package_type: AdvisoryPackageType;
};

export type AdvisoryPackageGenerateResponse = {
  id: number;
  stock_id: number;
  title: string;
  report_type: string;
  package_type: AdvisoryPackageType;
  markdown_content: string;
  created_at: string;
};
