import { FormEvent, useEffect, useMemo, useState } from "react";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { ClassificationRule, ClassificationRuleCreatePayload } from "@/types/classificationRule";

const defaultForm: ClassificationRuleCreatePayload = {
  target_type: "news",
  rule_group: "tag",
  rule_name: "",
  keywords: "",
  output_field: "ai_tags",
  output_value: "",
  score_delta: 0,
  priority: 100,
  is_active: true,
  description: "",
};

function ClassificationRulesPage() {
  const [items, setItems] = useState<ClassificationRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [targetType, setTargetType] = useState("");
  const [ruleGroup, setRuleGroup] = useState("");
  const [isActive, setIsActive] = useState("");
  const [keyword, setKeyword] = useState("");

  const [form, setForm] = useState<ClassificationRuleCreatePayload>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [submitLoading, setSubmitLoading] = useState(false);

  const isEdit = useMemo(() => editingId !== null, [editingId]);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await repositories.classificationRules.listClassificationRules({
        target_type: targetType || undefined,
        rule_group: ruleGroup || undefined,
        is_active: isActive === "" ? undefined : isActive === "true",
        keyword: keyword || undefined,
        limit: 100,
        offset: 0,
      });
      setItems(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "분류 규칙을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onSearch = async (e: FormEvent) => {
    e.preventDefault();
    await load();
  };

  const onReset = async () => {
    setTargetType("");
    setRuleGroup("");
    setIsActive("");
    setKeyword("");
    setTimeout(() => {
      load();
    }, 0);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitLoading(true);
    setError("");
    try {
      if (isEdit && editingId !== null) {
        await repositories.classificationRules.updateClassificationRule(editingId, form);
      } else {
        await repositories.classificationRules.createClassificationRule(form);
      }
      setForm(defaultForm);
      setEditingId(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "규칙 저장 중 오류가 발생했습니다.");
    } finally {
      setSubmitLoading(false);
    }
  };

  const startEdit = (row: ClassificationRule) => {
    setEditingId(row.id);
    setForm({
      target_type: row.target_type,
      rule_group: row.rule_group,
      rule_name: row.rule_name,
      keywords: row.keywords,
      output_field: row.output_field,
      output_value: row.output_value,
      score_delta: row.score_delta,
      priority: row.priority,
      is_active: row.is_active,
      description: row.description ?? "",
    });
  };

  const onDeactivate = async (ruleId: number) => {
    try {
      await repositories.classificationRules.deactivateClassificationRule(ruleId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "규칙 비활성화 중 오류가 발생했습니다.");
    }
  };

  const onCancelEdit = () => {
    setEditingId(null);
    setForm(defaultForm);
  };

  return (
    <div className="space-y-4">
      <PageHeader title="분류 규칙 관리" description="뉴스와 공시의 태그·중요도·감성/리스크 분류 기준을 관리합니다." />

      <SectionCard title="검색/필터">
        <form onSubmit={onSearch} className="grid grid-cols-1 gap-2 md:grid-cols-6">
          <select className="select-control" value={targetType} onChange={(e) => setTargetType(e.target.value)}>
            <option value="">전체 대상</option>
            <option value="news">뉴스</option>
            <option value="disclosure">공시</option>
          </select>
          <select className="select-control" value={ruleGroup} onChange={(e) => setRuleGroup(e.target.value)}>
            <option value="">전체 그룹</option>
            <option value="tag">태그</option>
            <option value="sentiment">감성</option>
            <option value="importance">중요도</option>
            <option value="disclosure_event_type">공시 이벤트</option>
            <option value="disclosure_risk_level">공시 리스크</option>
          </select>
          <select className="select-control" value={isActive} onChange={(e) => setIsActive(e.target.value)}>
            <option value="">전체 상태</option>
            <option value="true">사용</option>
            <option value="false">미사용</option>
          </select>
          <input className="input-control" placeholder="keyword" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
          <button type="submit" className="btn btn-primary">검색</button>
          <button type="button" className="btn btn-secondary" onClick={onReset}>초기화</button>
        </form>
      </SectionCard>

      <SectionCard title="규칙 등록/수정">
        <form onSubmit={onSubmit} className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <select className="select-control" value={form.target_type} onChange={(e) => setForm({ ...form, target_type: e.target.value })}>
            <option value="news">news</option>
            <option value="disclosure">disclosure</option>
          </select>
          <select className="select-control" value={form.rule_group} onChange={(e) => setForm({ ...form, rule_group: e.target.value })}>
            <option value="tag">tag</option>
            <option value="sentiment">sentiment</option>
            <option value="importance">importance</option>
            <option value="disclosure_event_type">disclosure_event_type</option>
            <option value="disclosure_risk_level">disclosure_risk_level</option>
          </select>
          <input className="input-control" placeholder="rule_name" value={form.rule_name} onChange={(e) => setForm({ ...form, rule_name: e.target.value })} required />
          <input className="input-control" placeholder="output_field" value={form.output_field} onChange={(e) => setForm({ ...form, output_field: e.target.value })} required />
          <textarea className="textarea-control md:col-span-2" placeholder="keywords (쉼표 구분)" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} required />
          <input className="input-control" placeholder="output_value" value={form.output_value} onChange={(e) => setForm({ ...form, output_value: e.target.value })} required />
          <textarea className="textarea-control" placeholder="description" value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <input type="number" className="input-control" placeholder="score_delta" value={form.score_delta ?? 0} onChange={(e) => setForm({ ...form, score_delta: Number(e.target.value) })} />
          <input type="number" className="input-control" placeholder="priority" value={form.priority ?? 100} onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })} />
          <label className="flex items-center gap-2 rounded-xl border border-[var(--color-hairline-cool)] px-3 py-2 text-sm">
            <input type="checkbox" checked={Boolean(form.is_active)} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
            is_active
          </label>
          <div className="flex gap-2 md:col-span-4">
            <button type="submit" className="btn btn-primary" disabled={submitLoading}>
              {isEdit ? "저장" : "신규 등록"}
            </button>
            {isEdit ? <button type="button" className="btn btn-secondary" onClick={onCancelEdit}>취소</button> : null}
          </div>
        </form>
      </SectionCard>

      <SectionCard title="규칙 목록">
        {loading ? <p className="text-sm text-muted">조회 중입니다.</p> : null}
        {error ? <p className="text-sm text-rose-600">{error}</p> : null}
        {!loading && !error && items.length === 0 ? <EmptyState message="분류 규칙이 없습니다." /> : null}

        {!loading && !error && items.length > 0 ? (
          <div className="table-shell">
            <table className="data-table min-w-[1550px]">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>대상</th>
                  <th>그룹</th>
                  <th>규칙명</th>
                  <th>키워드</th>
                  <th>출력 필드</th>
                  <th>출력 값</th>
                  <th>점수 가감</th>
                  <th>우선순위</th>
                  <th>사용 여부</th>
                  <th>설명</th>
                  <th>수정</th>
                  <th>비활성화</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr key={row.id}>
                    <td>{row.id}</td>
                    <td>{row.target_type}</td>
                    <td>{row.rule_group}</td>
                    <td>{row.rule_name}</td>
                    <td className="min-w-56">{row.keywords}</td>
                    <td>{row.output_field}</td>
                    <td>{row.output_value}</td>
                    <td>{row.score_delta}</td>
                    <td>{row.priority}</td>
                    <td>{row.is_active ? <StatusBadge label="사용" tone="emerald" /> : <StatusBadge label="미사용" tone="slate" />}</td>
                    <td>{row.description ?? "-"}</td>
                    <td><button type="button" className="btn btn-secondary" onClick={() => startEdit(row)}>수정</button></td>
                    <td>
                      {row.is_active ? (
                        <button type="button" className="btn btn-danger" onClick={() => onDeactivate(row.id)}>비활성화</button>
                      ) : (
                        "-"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="안내">
        <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
          <li>keywords는 쉼표로 구분합니다.</li>
          <li>여러 키워드 중 하나라도 본문에 포함되면 규칙이 적용됩니다.</li>
          <li>priority가 낮을수록 먼저 적용됩니다.</li>
          <li>score_delta는 중요도 점수 보정값이며, is_active가 꺼져 있으면 적용되지 않습니다.</li>
        </ul>
      </SectionCard>
    </div>
  );
}

export default ClassificationRulesPage;
