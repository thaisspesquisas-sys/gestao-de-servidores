import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useFetch, qs, fmtDate } from "@/lib/api";
import { PageHeader, Loading, TableWrap, SelectF } from "@/components/common";

const Diff = ({ a }) => {
  const keys = [...new Set([...Object.keys(a.antes || {}), ...Object.keys(a.depois || {})])];
  if (!keys.length) return null;
  const s = (v) => (v === null || v === undefined ? "" : typeof v === "object" ? JSON.stringify(v) : String(v));
  return <div className="text-[11px] space-y-0.5 mt-1">{keys.slice(0, 12).map((k) => <div key={k}><span className="text-slate-500">{k}:</span> <span className="line-through text-red-700/70">{s((a.antes || {})[k]).slice(0, 80)}</span> → <span className="text-emerald-700">{s((a.depois || {})[k]).slice(0, 80)}</span></div>)}</div>;
};

export default function Auditoria() {
  const [acao, setAcao] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(null);
  const { data, loading } = useFetch(`/auditoria${qs({ acao, q, page })}`);
  const pages = data ? Math.max(1, Math.ceil(data.total / 50)) : 1;
  return (
    <div>
      <PageHeader eyebrow="Histórico e auditoria" title="Trilha de Auditoria" subtitle="Todas as alterações: importações, servidores, lotações, cargos, reservas, liberações e quadro autorizado — com data, horário, usuário e dados anteriores e posteriores." />
      <div className="flex flex-col md:flex-row gap-3 mb-4">
        <SelectF className="md:w-72" value={acao} onChange={(v) => { setAcao(v); setPage(1); }} allLabel="Todas as ações" options={(data?.acoes || []).map((a) => ({ value: a, label: a }))} testid="auditoria-acao-filter" />
        <Input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Buscar por descrição ou usuário" className="bg-white md:w-96" data-testid="auditoria-search-input" />
      </div>
      {loading && !data ? <Loading /> : (
        <>
          <TableWrap testid="auditoria-table">
            <thead><tr><th>Data/hora</th><th>Usuário</th><th>Ação</th><th>Entidade</th><th>Descrição / Alterações</th></tr></thead>
            <tbody>{data?.items.map((a) => (
              <tr key={a.id} className="cursor-pointer align-top" onClick={() => setOpen(open === a.id ? null : a.id)}>
                <td className="text-xs whitespace-nowrap">{fmtDate(a.ts)}</td><td className="text-xs">{a.usuario}</td><td className="text-xs font-semibold">{a.acao}</td><td className="text-xs">{a.entidade}</td>
                <td className="text-xs">{a.descricao}{open === a.id && <Diff a={a} />}</td></tr>))}</tbody>
          </TableWrap>
          <div className="flex items-center justify-end gap-2 mt-3 text-sm">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Anterior</Button>
            <span>Página {page} de {pages} · {data?.total} registros</span>
            <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Próxima</Button>
          </div>
        </>
      )}
    </div>
  );
}
