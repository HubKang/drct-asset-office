import sampleSchemaComments from "@/data/json/sampleSchemaComments.json";
import type { SchemaComment, SchemaCommentColumn, SchemaCommentTable } from "@/types/schemaComment";

const schemaComments = sampleSchemaComments as SchemaComment[];

function parseDataType(rawType: string | null | undefined): { dataType: string; dataLength: number | null } {
  const typeText = (rawType || "").trim();
  if (!typeText) {
    return { dataType: "-", dataLength: null };
  }
  const match = typeText.match(/\((\d+)\)/);
  return {
    dataType: typeText,
    dataLength: match ? Number(match[1]) : null,
  };
}

export const schemaCommentMockRepository = {
  async list(tableName?: string): Promise<SchemaComment[]> {
    if (!tableName) return schemaComments;
    return schemaComments.filter((c) => c.table_name === tableName);
  },
  async listTables(tableName?: string): Promise<SchemaCommentTable[]> {
    const rows = tableName ? schemaComments.filter((c) => c.table_name.includes(tableName)) : schemaComments;
    const grouped = new Map<string, SchemaCommentTable>();

    for (const row of rows) {
      const previous = grouped.get(row.table_name);
      const tableComment = row.column_name ? previous?.table_comment_ko ?? null : row.comment_ko;
      const count = row.column_name ? (previous?.column_count ?? 0) + 1 : previous?.column_count ?? 0;
      grouped.set(row.table_name, {
        table_id: row.table_name,
        table_name: tableComment || row.table_name,
        table_comment_ko: tableComment,
        column_count: count,
      });
    }

    return [...grouped.values()].sort((a, b) => a.table_id.localeCompare(b.table_id));
  },
  async listColumns(tableName: string): Promise<SchemaCommentColumn[]> {
    const rows = schemaComments.filter((c) => c.table_name === tableName && c.column_name);
    return rows.map((row, index) => {
      const parsed = parseDataType("TEXT");
      return {
        column_id: index,
        column_name: row.column_name || "",
        is_pk: row.column_name === "id",
        is_nullable: row.column_name !== "id",
        data_type: parsed.dataType,
        data_length: parsed.dataLength,
        default_value: null,
        comment_ko: row.comment_ko,
      };
    });
  },
};
