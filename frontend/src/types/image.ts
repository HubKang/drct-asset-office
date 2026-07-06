export type AppImageDomain = "trade_journal" | "trade_method" | "stock_tracking" | "kms";

export type AppImage = {
  id: number;
  domain: AppImageDomain;
  owner_type?: string | null;
  owner_id?: number | null;
  original_file_name: string;
  stored_file_name: string;
  relative_path: string;
  file_url: string;
  file_ext: string;
  mime_type?: string | null;
  file_size: number;
  width?: number | null;
  height?: number | null;
  sort_order: number;
  description?: string | null;
  is_active: number;
  created_at: string;
  updated_at: string;
};

export type AppImageListResponse = {
  items: AppImage[];
  total_count: number;
};

export type AppImageDeleteResponse = {
  success: boolean;
  image_id: number;
  file_deleted: boolean;
  file_missing: boolean;
};
