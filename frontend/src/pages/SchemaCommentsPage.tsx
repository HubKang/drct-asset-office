import { useEffect, useState } from "react";
import { repositories } from "@/services";
import type { SchemaComment } from "@/types/schemaComment";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";

function SchemaCommentsPage() {
  const [items, setItems] = useState<SchemaComment[]>([]);
  const [tableName, setTableName] = useState("");

  const load = async () => {
    setItems(await repositories.schemaComments.list(tableName || undefined));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader title="스키마 코멘트" description="데이터 사전 기준으로 테이블/컬럼 한글 설명을 조회합니다." />

      <SectionCard title="조회 필터">
        <div className="flex gap-2">
          <input className="input-control" placeholder="table_name 필터" value={tableName} onChange={(e) => setTableName(e.target.value)} />
          <button className="btn btn-primary" onClick={load}>조회</button>
        </div>
      </SectionCard>

      <SectionCard title="데이터 사전">
        {items.length === 0 ? (
          <EmptyState message="조회된 스키마 코멘트가 없습니다." />
        ) : (
          <div className="table-shell">
            <table className="data-table min-w-[900px]">
              <thead>
                <tr><th>table_name</th><th>column_name</th><th>comment_ko</th></tr>
              </thead>
              <tbody>
                {items.map((i, idx) => (
                  <tr key={`${i.table_name}-${i.column_name}-${idx}`}>
                    <td><StatusBadge label={i.table_name} tone="blue" /></td>
                    <td>{i.column_name || "테이블 설명"}</td>
                    <td>{i.comment_ko}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
}

export default SchemaCommentsPage;
