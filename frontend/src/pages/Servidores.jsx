import { useState } from "react";
import { Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useFetch, qs, fmt } from "@/lib/api";
import { useMe } from "@/context/MeContext";
import { PageHeader, FilterBar, Loading, Badge, TableWrap, SelectF } from "@/components/common";
import { ServidorDialog, ServidorForm } from "@/components/ServidorDialog";

export default function Servidores() {
  const { canOperar } = useMe();
  const [f, setF] = useState({});
  const [q, setQ] = useState("");
  const [lot, setLot] = useState("");
  const [page, setPage] = useState(1);
  const [sel, setSel] = useState(null);
  const [novo, setNovo] = useState(false);
  const { data: meta } = useFetch("/meta");
  const { data, loading, reload } = useFetch(`/servidores${qs({ ...f, q, page, lotacao_status: lot })}`);
  const pages = data ? Math.max(1, Math.ceil(data.total / 50)) : 1;
  return (
    <div>
      <PageHeader eyebrow="Cadastro funcional" title="Servidores e Vínculos" subtitle="Cada matrícula é um vínculo funcional. Um mesmo servidor pode ter vários vínculos (matrículas, cargos ou lotações diferentes)."
        actions={canOperar && <Button onClick={() => setNovo(true)} className="bg-[#0B192C] hover:bg-[#1E3E62]" data-testid="servidor-new-button"><Plus className="h-4 w-4 mr-1" /> Novo vínculo</Button>} />
      <div className="flex flex-col md:flex-row gap-3 mb-3">
        <div className="relative flex-1"><Search className="h-4 w-4 absolute left-3 top-3 text-slate-400" />
          <Input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Buscar por nome, matrícula ou lotação" className="pl-9 bg-white" data-testid="servidor-search-input" /></div>
        <SelectF className="md:w-72" value={lot} onChange={(v) => { setLot(v); setPage(1); }} allLabel="Todas as lotações" testid="servidor-lotacao-status"
          options={[{ value: "pendente", label: "Lotação aguardando validação" }, { value: "nao_escola", label: "Fora das unidades escolares" }]} />
      </div>
      <FilterBar meta={meta} value={f} onChange={(v) => { setF(v); setPage(1); }} />
      {loading && !data ? <Loading /> : (
        <>
          <div className="text-sm text-slate-600 mb-2" data-testid="servidor-total">{fmt(data?.total)} vínculo(s)</div>
          <TableWrap testid="servidores-table">
            <thead><tr><th>Matrícula</th><th>Nome</th><th>Cargo</th><th>Função</th><th>Escola / Lotação</th><th>Vínculo</th><th>C.H.</th><th>Situação</th></tr></thead>
            <tbody>{data?.items.map((v) => (
              <tr key={v.id} className="cursor-pointer" onClick={() => setSel(v.id)} data-testid={`servidor-row-${v.matricula}`}>
                <td className="num">{v.matricula}</td><td className="font-medium">{v.nome}</td><td className="text-xs">{v.cargo_padrao}</td><td className="text-xs">{v.funcao}</td>
                <td className="text-xs">{v.escola || <span className={v.lotacao_status === "pendente" ? "text-red-700" : "text-slate-500"}>{v.lotacao || "—"}{v.lotacao_status === "pendente" && " (validar)"}</span>}</td>
                <td className="text-xs">{v.vinculo}</td><td className="text-xs whitespace-nowrap">{v.carga_horaria}</td><td><Badge kind={v.regra}>{v.situacao_nome}</Badge></td>
              </tr>))}</tbody>
          </TableWrap>
          <div className="flex items-center justify-end gap-2 mt-3 text-sm">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)} data-testid="servidor-prev-page">Anterior</Button>
            <span data-testid="servidor-page">Página {page} de {pages}</span>
            <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)} data-testid="servidor-next-page">Próxima</Button>
          </div>
        </>
      )}
      <ServidorDialog id={sel} onClose={() => setSel(null)} situacoes={meta?.situacoes || []} onChanged={reload} />
      <ServidorForm open={novo} onClose={() => setNovo(false)} situacoes={meta?.situacoes || []} onSaved={reload} />
    </div>
  );
}
