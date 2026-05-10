import { FormEvent, useEffect, useState } from "react";
import codes from "@/data/json/codes.json";
import EmptyState from "@/components/common/EmptyState";
import PageHeader from "@/components/common/PageHeader";
import SectionCard from "@/components/common/SectionCard";
import StatusBadge from "@/components/common/StatusBadge";
import { repositories } from "@/services";
import type { Stock } from "@/types/stock";
import type { Watchlist, WatchlistCreateInput, WatchlistUpdateInput } from "@/types/watchlist";

const statusToneMap: Record<string, "blue" | "slate" | "emerald" | "amber" | "rose"> = {
  관심: "blue",
  관망: "slate",
  매수후보: "emerald",
  보유중: "amber",
  제외: "rose",
};

function WatchlistPage() {
  const [items, setItems] = useState<Watchlist[]>([]);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("");
  const [form, setForm] = useState<WatchlistCreateInput>({ stock_id: 0, status: "관심" });

  const load = async () => {
    setItems(await repositories.watchlist.list({ keyword: keyword || undefined, status: status || undefined }));
  };

  useEffect(() => {
    const run = async () => {
      const [watch, stockList] = await Promise.all([repositories.watchlist.list(), repositories.stocks.list()]);
      setItems(watch);
      setStocks(stockList);
      if (stockList.length > 0) setForm((prev) => ({ ...prev, stock_id: stockList[0].id }));
    };
    run();
  }, []);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    await repositories.watchlist.create(form);
    await load();
  };

  const onUpdate = async (item: Watchlist, patch: WatchlistUpdateInput) => {
    await repositories.watchlist.update(item.id, patch);
    await load();
  };

  const onDelete = async (id: number) => {
    await repositories.watchlist.remove(id);
    await load();
  };

  return (
    <div className="space-y-4">
      <PageHeader title="관심종목 관리" description="투자 관찰 대상과 진입/제외 조건을 관리합니다." />

      <SectionCard title="필터">
        <div className="flex flex-wrap gap-2">
          <select className="select-control" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">전체 상태</option>
            {codes.watchlistStatus.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <input className="input-control min-w-72 flex-1" placeholder="코드/종목명 검색" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
          <button className="btn btn-primary" onClick={load}>검색</button>
        </div>
      </SectionCard>

      <SectionCard title="관심종목 등록">
        <form onSubmit={onCreate} className="grid grid-cols-1 gap-2 md:grid-cols-3">
          <select className="select-control" value={form.stock_id} onChange={(e) => setForm({ ...form, stock_id: Number(e.target.value) })}>
            {stocks.map((s) => <option key={s.id} value={s.id}>{s.stock_code} - {s.stock_name}</option>)}
          </select>
          <select className="select-control" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
            {codes.watchlistStatus.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button type="submit" className="btn btn-primary">등록</button>
          <input className="input-control" placeholder="관심 사유" onChange={(e) => setForm({ ...form, interest_reason: e.target.value })} />
          <input className="input-control" placeholder="진입 조건" onChange={(e) => setForm({ ...form, entry_condition: e.target.value })} />
          <input className="input-control" placeholder="제외 조건" onChange={(e) => setForm({ ...form, exit_condition: e.target.value })} />
        </form>
      </SectionCard>

      <SectionCard title="관심종목 목록">
        {items.length === 0 ? (
          <EmptyState message="조회된 관심종목이 없습니다." />
        ) : (
          <div className="table-shell">
            <table className="data-table min-w-[1200px]">
              <thead>
                <tr>
                  <th>종목</th>
                  <th>상태</th>
                  <th>관심 사유</th>
                  <th>진입 조건</th>
                  <th>제외 조건</th>
                  <th>리스크 메모</th>
                  <th>작업</th>
                </tr>
              </thead>
              <tbody>
                {items.map((w) => (
                  <tr key={w.id}>
                    <td><p className="font-semibold text-slate-900">{w.stock_code}</p><p className="text-xs text-slate-500">{w.stock_name}</p></td>
                    <td><StatusBadge label={w.status} tone={statusToneMap[w.status] ?? "slate"} /></td>
                    <td>{w.interest_reason || "-"}</td>
                    <td>{w.entry_condition || "-"}</td>
                    <td>{w.exit_condition || "-"}</td>
                    <td>{w.risk_note || "-"}</td>
                    <td>
                      <div className="flex gap-2">
                        <button className="btn btn-secondary" onClick={() => onUpdate(w, { status: "관망" })}>상태수정</button>
                        <button className="btn btn-danger" onClick={() => onDelete(w.id)}>삭제</button>
                      </div>
                    </td>
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

export default WatchlistPage;
