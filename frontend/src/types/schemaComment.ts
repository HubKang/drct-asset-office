export type SchemaComment = {
  table_name: string;
  column_name: string | null;
  comment_ko: string;
};

export type SchemaCommentTable = {
  table_id: string;
  table_name: string;
  table_comment_ko: string | null;
  column_count: number;
};

export type SchemaCommentColumn = {
  column_id: number;
  column_name: string;
  is_pk: boolean;
  is_nullable: boolean;
  data_type: string;
  data_length: number | null;
  default_value: string | null;
  comment_ko: string | null;
};
