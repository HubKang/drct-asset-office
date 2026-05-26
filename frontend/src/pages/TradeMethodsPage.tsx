import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import { repositories } from "@/services";
import type { TradeMethod } from "@/types/tradeJournal";

type ActiveFilter = "all" | "active" | "inactive";

const defaultForm = {
  method_name: "",
  description: "",
  entry_rule: "",
  take_profit_rule: "",
  stop_loss_rule: "",
  exit_rule: "",
  sort_order: 0,
  is_active: true,
};

function TradeMethodsPage() {
  const [items, setItems] = useState<TradeMethod[]>([]);
  const [keyword, setKeyword] = useState("");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("active");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(defaultForm);

  const formTitle = useMemo(() => (editingId ? "매매기법 수정" : "신규 매매기법 등록"), [editingId]);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const isActive = activeFilter === "all" ? undefined : activeFilter === "active" ? 1 : 0;
      const rows = await repositories.tradeJournals.listTradeMethods({
        keyword: keyword.trim() || undefined,
        is_active: isActive,
      });
      setItems(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "매매기법 목록 조회에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const resetForm = () => {
    setEditingId(null);
    setForm(defaultForm);
  };

  const onSubmit = async () => {
    setMessage("");
    setError("");
    if (!form.method_name.trim()) {
      setError("매매기법명을 입력해 주세요.");
      return;
    }
    setSaving(true);
    try {
      if (editingId) {
        await repositories.tradeJournals.updateTradeMethod(editingId, {
          method_name: form.method_name.trim(),
          description: form.description.trim() || undefined,
          entry_rule: form.entry_rule.trim() || undefined,
          take_profit_rule: form.take_profit_rule.trim() || undefined,
          stop_loss_rule: form.stop_loss_rule.trim() || undefined,
          exit_rule: form.exit_rule.trim() || undefined,
          sort_order: Number(form.sort_order) || 0,
          is_active: form.is_active,
        });
        setMessage("매매기법이 수정되었습니다.");
      } else {
        await repositories.tradeJournals.createTradeMethod({
          method_name: form.method_name.trim(),
          description: form.description.trim() || undefined,
          entry_rule: form.entry_rule.trim() || undefined,
          take_profit_rule: form.take_profit_rule.trim() || undefined,
          stop_loss_rule: form.stop_loss_rule.trim() || undefined,
          exit_rule: form.exit_rule.trim() || undefined,
          sort_order: Number(form.sort_order) || 0,
          is_active: form.is_active,
        });
        setMessage("매매기법이 등록되었습니다.");
      }
      await load();
      if (!editingId) resetForm();
    } catch (e) {
      setError(e instanceof Error ? e.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const onEdit = (item: TradeMethod) => {
    setEditingId(item.id);
    setForm({
      method_name: item.method_name || "",
      description: item.description || "",
      entry_rule: item.entry_rule || "",
      take_profit_rule: item.take_profit_rule || "",
      stop_loss_rule: item.stop_loss_rule || "",
      exit_rule: item.exit_rule || "",
      sort_order: item.sort_order || 0,
      is_active: item.is_active === 1,
    });
  };

  const onToggleActive = async (item: TradeMethod) => {
    setMessage("");
    setError("");
    try {
      await repositories.tradeJournals.updateTradeMethod(item.id, { is_active: item.is_active !== 1 });
      setMessage("매매기법 상태가 변경되었습니다.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "상태 변경 중 오류가 발생했습니다.");
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="매매기법" description="자주 사용하는 매매기법과 진입·익절·손절 기준을 등록하고 관리합니다." />

      <SectionCard title="검색">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <input
            className="input-control"
            placeholder="매매기법명/설명/조건 검색"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
          <select className="select-control" value={activeFilter} onChange={(e) => setActiveFilter(e.target.value as ActiveFilter)}>
            <option value="all">전체</option>
            <option value="active">활성</option>
            <option value="inactive">비활성</option>
          </select>
          <button type="button" className="btn btn-primary" onClick={() => void load()} disabled={loading}>
            {loading ? "조회 중..." : "조회"}
          </button>
          <button type="button" className="btn btn-secondary" onClick={resetForm}>
            신규 매매기법 등록
          </button>
        </div>
        {message ? <p className="mt-2 text-sm text-emerald-700">{message}</p> : null}
        {error ? <p className="mt-2 text-sm text-rose-700">{error}</p> : null}
      </SectionCard>

      <SectionCard title="매매기법 목록">
        <div className="table-shell">
          <table className="data-table min-w-[1200px]">
            <thead>
              <tr>
                <th>정렬</th>
                <th>매매기법명</th>
                <th>설명</th>
                <th>진입 조건</th>
                <th>익절 기준</th>
                <th>손절 기준</th>
                <th>활성</th>
                <th>관리</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.sort_order}</td>
                  <td>{item.method_name}</td>
                  <td className="max-w-[200px] truncate" title={item.description || ""}>{item.description || "-"}</td>
                  <td className="max-w-[220px] truncate" title={item.entry_rule || ""}>{item.entry_rule || "-"}</td>
                  <td className="max-w-[220px] truncate" title={item.take_profit_rule || ""}>{item.take_profit_rule || "-"}</td>
                  <td className="max-w-[220px] truncate" title={item.stop_loss_rule || ""}>{item.stop_loss_rule || "-"}</td>
                  <td>
                    <span className={`badge ${item.is_active === 1 ? "badge-emerald" : "badge-slate"}`}>
                      {item.is_active === 1 ? "활성" : "비활성"}
                    </span>
                  </td>
                  <td className="space-x-2">
                    <button type="button" className="btn btn-secondary" onClick={() => onEdit(item)}>수정</button>
                    <button type="button" className="btn btn-secondary" onClick={() => void onToggleActive(item)}>
                      {item.is_active === 1 ? "비활성화" : "활성화"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      <SectionCard title={formTitle}>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          <input
            className="input-control"
            placeholder="매매기법명 (예: 장대양봉 눌림)"
            value={form.method_name}
            onChange={(e) => setForm((prev) => ({ ...prev, method_name: e.target.value }))}
          />
          <input
            className="input-control"
            placeholder="설명"
            value={form.description}
            onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
          />
          <textarea
            className="textarea-control"
            placeholder="진입 조건 (예: 거래대금 동반 장대양봉 이후 5일선 또는 10일선 부근 지지 확인)"
            value={form.entry_rule}
            onChange={(e) => setForm((prev) => ({ ...prev, entry_rule: e.target.value }))}
          />
          <textarea
            className="textarea-control"
            placeholder="익절 기준 (예: 전고점 돌파 후 거래량 둔화 시 분할매도)"
            value={form.take_profit_rule}
            onChange={(e) => setForm((prev) => ({ ...prev, take_profit_rule: e.target.value }))}
          />
          <textarea
            className="textarea-control"
            placeholder="손절 기준 (예: 기준봉 저점 이탈 또는 5일선 이탈 시 손절)"
            value={form.stop_loss_rule}
            onChange={(e) => setForm((prev) => ({ ...prev, stop_loss_rule: e.target.value }))}
          />
          <textarea
            className="textarea-control"
            placeholder="청산/매도 기준"
            value={form.exit_rule}
            onChange={(e) => setForm((prev) => ({ ...prev, exit_rule: e.target.value }))}
          />
          <input
            type="number"
            className="input-control"
            placeholder="정렬 순서"
            value={form.sort_order}
            onChange={(e) => setForm((prev) => ({ ...prev, sort_order: Number(e.target.value) || 0 }))}
          />
          <select
            className="select-control"
            value={form.is_active ? "1" : "0"}
            onChange={(e) => setForm((prev) => ({ ...prev, is_active: e.target.value === "1" }))}
          >
            <option value="1">활성</option>
            <option value="0">비활성</option>
          </select>
        </div>
        <div className="mt-3 flex gap-2">
          <button type="button" className="btn btn-primary" onClick={() => void onSubmit()} disabled={saving}>
            {saving ? "저장 중..." : "저장"}
          </button>
          <button type="button" className="btn btn-secondary" onClick={resetForm}>
            초기화
          </button>
        </div>
      </SectionCard>
    </div>
  );
}

export default TradeMethodsPage;
