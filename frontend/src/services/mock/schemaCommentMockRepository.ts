import sampleSchemaComments from "@/data/json/sampleSchemaComments.json";
import type { SchemaComment } from "@/types/schemaComment";

const schemaComments = sampleSchemaComments as SchemaComment[];

export const schemaCommentMockRepository = {
  async list(tableName?: string): Promise<SchemaComment[]> {
    if (!tableName) return schemaComments;
    return schemaComments.filter((c) => c.table_name === tableName);
  },
};
