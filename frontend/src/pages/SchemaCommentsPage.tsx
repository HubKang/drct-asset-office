import { useEffect, useMemo, useState } from "react";
import { repositories } from "@/services";
import type { SchemaCommentColumn, SchemaCommentTable } from "@/types/schemaComment";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";

function SchemaCommentsPage() {
  const [tableName, setTableName] = useState("");
  const [tables, setTables] = useState<SchemaCommentTable[]>([]);
  const [selectedTableId, setSelectedTableId] = useState<string>("");
  const [columns, setColumns] = useState<SchemaCommentColumn[]>([]);
  const [loading, setLoading] = useState(false);
  const [columnLoading, setColumnLoading] = useState(false);

  const safeTables = Array.isArray(tables) ? tables : [];
  const safeColumns = Array.isArray(columns) ? columns : [];

  const selectedTable = useMemo(
    () => safeTables.find((table) => table.table_id === selectedTableId) ?? null,
    [safeTables, selectedTableId],
  );

  const summary = useMemo(() => {
    const pkCount = safeColumns.filter((column) => column.is_pk).length;
    const notNullCount = safeColumns.filter((column) => !column.is_nullable).length;
    return {
      tableCount: safeTables.length,
      columnCount: safeColumns.length,
      pkCount,
      notNullCount,
    };
  }, [safeTables, safeColumns]);

  const loadColumns = async (targetTableId: string) => {
    if (!targetTableId) {
      setColumns([]);
      return;
    }
    setColumnLoading(true);
    try {
      const nextColumns = await repositories.schemaComments.listColumns(targetTableId);
      setColumns(Array.isArray(nextColumns) ? nextColumns : []);
    } finally {
      setColumnLoading(false);
    }
  };

  const loadTables = async (filter?: string) => {
    setLoading(true);
    try {
      const nextTables = await repositories.schemaComments.listTables(filter || undefined);
      const normalizedTables = Array.isArray(nextTables) ? nextTables : [];
      setTables(normalizedTables);

      if (normalizedTables.length === 0) {
        setSelectedTableId("");
        setColumns([]);
        return;
      }

      const hasSelected = normalizedTables.some((table) => table.table_id === selectedTableId);
      const nextSelected = hasSelected ? selectedTableId : normalizedTables[0].table_id;
      setSelectedTableId(nextSelected);
      await loadColumns(nextSelected);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTables();
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader title="DrCT테이블정보" description="DrCT에셋 데이터베이스의 테이블과 컬럼 구조를 조회합니다." />

      <SectionCard title="조회 필터">
        <form
          className="schema-comment-filter-row"
          onSubmit={(e) => {
            e.preventDefault();
            void loadTables(tableName);
          }}
        >
          <input
            className="input-control schema-comment-filter-input"
            placeholder="테이블명 검색"
            value={tableName}
            onChange={(e) => setTableName(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "조회 중..." : "조회"}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setTableName("");
              void loadTables();
            }}
            disabled={loading}
          >
            초기화
          </button>
        </form>
      </SectionCard>

      <div className="schema-comment-layout">
        <SectionCard title="테이블 목록">
          {safeTables.length === 0 ? (
            <EmptyState message="조회된 테이블이 없습니다." />
          ) : (
            <div className="schema-comment-table-list">
              <p className="text-muted">총 {summary.tableCount}개 테이블</p>
              {safeTables.map((table) => (
                <button
                  key={table.table_id}
                  type="button"
                  className={`schema-comment-table-item${table.table_id === selectedTableId ? " selected" : ""}`}
                  onClick={() => {
                    setSelectedTableId(table.table_id);
                    void loadColumns(table.table_id);
                  }}
                >
                  <div className="schema-comment-table-item-head">
                    <strong title={table.table_id}>{table.table_id}</strong>
                    <StatusBadge label={`컬럼 ${table.column_count}개`} tone="slate" />
                  </div>
                  <p title={table.table_name}>테이블명: {table.table_name || table.table_id}</p>
                  <small title={table.table_comment_ko || ""}>{table.table_comment_ko || "설명 없음"}</small>
                </button>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard title="컬럼 상세">
          {!selectedTable ? (
            <EmptyState message="왼쪽에서 테이블을 선택하면 컬럼 정보가 표시됩니다." />
          ) : (
            <div className="space-y-3">
              <div className="schema-comment-selected-head">
                <h3>선택 테이블: {selectedTable.table_id}</h3>
                <p>테이블 설명: {selectedTable.table_comment_ko || selectedTable.table_name || "설명 없음"}</p>
                <div className="schema-comment-summary-row">
                  <StatusBadge label={`컬럼 ${summary.columnCount}개`} tone="blue" />
                  <StatusBadge label={`PK ${summary.pkCount}개`} tone="amber" />
                  <StatusBadge label={`NOT NULL ${summary.notNullCount}개`} tone="slate" />
                </div>
              </div>

              {columnLoading ? (
                <p className="text-muted">컬럼 정보를 불러오는 중입니다.</p>
              ) : safeColumns.length === 0 ? (
                <EmptyState message="컬럼 정보가 없습니다." />
              ) : (
                <div className="table-shell schema-comment-column-shell">
                  <table className="data-table schema-comment-column-table">
                    <thead>
                      <tr>
                        <th>컬럼 ID</th>
                        <th>컬럼명</th>
                        <th>PK</th>
                        <th>NULL</th>
                        <th>데이터 타입</th>
                        <th>길이</th>
                        <th>기본값</th>
                        <th>설명</th>
                      </tr>
                    </thead>
                    <tbody>
                      {safeColumns.map((column) => (
                        <tr key={`${selectedTable.table_id}-${column.column_name}-${column.column_id}`}>
                          <td className="cell-nowrap">{column.column_id}</td>
                          <td title={column.column_name} className="schema-ellipsis">{column.column_name || "-"}</td>
                          <td><StatusBadge label={column.is_pk ? "PK" : "-"} tone={column.is_pk ? "amber" : "slate"} /></td>
                          <td><StatusBadge label={column.is_nullable ? "NULL" : "NOT NULL"} tone={column.is_nullable ? "slate" : "blue"} /></td>
                          <td title={column.data_type} className="schema-ellipsis">{column.data_type || "-"}</td>
                          <td className="cell-nowrap">{column.data_length ?? "-"}</td>
                          <td title={column.default_value || ""} className="schema-ellipsis">{column.default_value || "-"}</td>
                          <td title={column.comment_ko || ""} className="schema-ellipsis">{column.comment_ko || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}

export default SchemaCommentsPage;
