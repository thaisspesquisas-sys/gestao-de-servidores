import { useState } from "react";
import { toast } from "sonner";
import { History, Pencil, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApi, useFetch, qs, fmt, fmtDate, errMsg } from "@/lib/api";
import { useMe } from "@/context/MeContext";
import { PageHeader, FilterBar, Loading, Badge, TableWrap, Kpi, SelectF, Empty } from "@/components/common";

const Historico = ({ k, onClose }) => {
  const { data, loading } = useFetch(k ? `/vagas/historico${qs({ key: k })}` : null);
  return (
    <Dialog open={!!k} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl bg-white max-h-[85vh] overflow-y-auto" data-testid="vaga-history-dialog">
        <DialogHeader><DialogTitle>Histórico da vaga</DialogTitle></DialogHeader>
        {loading ? <Loading /> : !data?.eventos.length ? <Empty>Nenhum evento registrado para esta vaga.</Empty> : (
          <ul className="space-y-2 text-sm">{data.eventos.map((e) => (
            <li key={e.id} className="border-l-2 border-[#D4AF37] pl-3"><div className="text-xs text-slate-500">{fmtDate(e.ts)} · {e.usuario}</div>
              <div><b>{e.acao}</b> — {e.descricao}</div></li>))}</ul>
        )}
      </DialogContent>
    </Dialog>
  );
};

export const QuadroDialog = ({ open, onClose, inicial, escolas, onSaved }) => {
  const api = useApi();
  const [d, setD] = useState({});
  const abrir = open && d._o !== open;
  if (abrir) setD({ _o: open, school_id: inicial?.school_id || "", cargo: inicial?.cargo || "", funcao: inicial?.funcao || "", quantidade: inicial?.autorizadas ?? "" });
  const salvar = async () => {
    try {
      await api("post", "/quadro", { school_id: d.school_id, cargo: d.cargo, funcao: d.funcao, quantidade: parseInt(d.quantidade, 10) });
      toast.success("Quadro autorizado atualizado"); onSaved(); onClose();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) { setD({}); onClose(); } }}>
      <DialogContent className="max-w-lg bg-white">
        <DialogHeader><DialogTitle>Quadro oficial — vagas autorizadas</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <SelectF noAll value={d.school_id} onChange={(v) => setD({ ...d, school_id: v })} options={escolas} placeholder="Escola" testid="quadro-form-escola" />
          <Input placeholder="Cargo" list="cargos-dl" value={d.cargo || ""} onChange={(e) => setD({ ...d, cargo: e.target.value })} data-testid="quadro-form-cargo" />
          <Input placeholder="Função (opcional)" value={d.funcao || ""} onChange={(e) => setD({ ...d, funcao: e.target.value })} data-testid="quadro-form-funcao" />
          <Input type="number" min="0" placeholder="Quantidade autorizada" value={d.quantidade} onChange={(e) => setD({ ...d, quantidade: e.target.value })} data-testid="quadro-form-quantidade" />
          <Button onClick={salvar} className="bg-[#0B192C] hover:bg-[#1E3E62]" data-testid="quadro-form-save">Salvar</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default function Vagas() {
  const { isAdmin } = useMe();
  const [f, setF] = useState({});
  const [hist, setHist] = useState(null);
  const [qd, setQd] = useState(null);
  const [soBase, setSoBase] = useState("");
  const { data: meta } = useFetch("/meta");
  const { data, loading, reload } = useFetch(`/vagas${qs(f)}`);
  const linhas = (data?.linhas || []).filter((r) => (soBase === "com" ? r.base !== null : soBase === "sem" ? r.base === null : true));
  const s = (k) => linhas.reduce((a, r) => a + (r[k] || 0), 0);
  const escolas = (meta?.escolas || []).map((e) => ({ value: e.id, label: e.nome }));
  return (
    <div>
      <PageHeader eyebrow="Ocupadas · Disponíveis · Reservadas" title="Controle de Vagas" subtitle="Vagas disponíveis = Vagas autorizadas − Vagas ocupadas − Vagas reservadas. Excesso de ocupação aparece separadamente como excedente."
        actions={isAdmin && <Button onClick={() => setQd({})} className="bg-[#0B192C] hover:bg-[#1E3E62]" data-testid="quadro-new-button"><Plus className="h-4 w-4 mr-1" /> Vagas autorizadas</Button>} />
      <datalist id="cargos-dl">{(meta?.cargos || []).map((c) => <option key={c} value={c} />)}</datalist>
      <FilterBar meta={meta} value={f} onChange={setF} />
      <div className="mb-4 w-72"><SelectF value={soBase} onChange={setSoBase} allLabel="Todas as linhas" testid="vagas-base-filter"
        options={[{ value: "com", label: "Com vagas autorizadas / base" }, { value: "sem", label: "Sem quadro autorizado" }]} /></div>
      {loading && !data ? <Loading /> : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-5">
            <Kpi testid="vagas-kpi-base" label="Autorizadas (base)" value={s("base")} />
            <Kpi testid="vagas-kpi-ocupadas" label="Ocupadas" value={s("ocupadas")} tone="blue" />
            <Kpi testid="vagas-kpi-reservadas" label="Reservadas" value={s("reservadas")} tone="amber" />
            <Kpi testid="vagas-kpi-disponiveis" label="Disponíveis" value={s("disponiveis")} tone="green" />
            <Kpi testid="vagas-kpi-excedente" label="Excedentes" value={s("excedente")} tone="violet" />
          </div>
          <TableWrap testid="vagas-table">
            <thead><tr><th>Escola</th><th>Cargo</th><th>Função</th><th>Autorizadas</th><th>Previsto (regra)</th><th>Base</th><th>Ocupadas</th><th>Reservadas</th><th>Disponíveis</th><th>Excedente</th><th></th></tr></thead>
            <tbody>{linhas.map((r) => (
              <tr key={r.key} data-testid={`vaga-row-${r.key}`}>
                <td className="text-xs font-medium min-w-[180px]">{r.escola}</td><td className="text-xs">{r.cargo}</td><td className="text-xs">{r.funcao || "—"}</td>
                <td className="num text-center">{fmt(r.autorizadas)}</td><td className="num text-center">{fmt(r.previsto)}</td>
                <td className="text-center">{r.base === null ? <span className="text-xs text-slate-400">sem quadro</span> : <><span className="num">{r.base}</span> <Badge kind={r.fonte_base}>{r.fonte_base}</Badge></>}</td>
                <td className="num text-center">{r.ocupadas}{r.pendentes > 0 && <span className="text-[10px] text-red-700 block">{r.pendentes} s/ regra</span>}</td>
                <td className="num text-center">{r.reservadas}</td>
                <td className="num text-center text-emerald-700 font-semibold">{fmt(r.disponiveis)}</td>
                <td className="num text-center text-violet-700 font-semibold">{r.excedente ? r.excedente : r.excedente === 0 ? 0 : "—"}</td>
                <td className="whitespace-nowrap">
                  <button className="p-1 text-slate-500 hover:text-[#0B192C]" onClick={() => setHist(r.key)} data-testid={`vaga-history-${r.key}`}><History className="h-4 w-4" /></button>
                  {isAdmin && <button className="p-1 text-slate-500 hover:text-[#0B192C]" onClick={() => setQd(r)} data-testid={`vaga-edit-${r.key}`}><Pencil className="h-4 w-4" /></button>}
                </td>
              </tr>))}</tbody>
          </TableWrap>
        </>
      )}
      <Historico k={hist} onClose={() => setHist(null)} />
      <QuadroDialog open={!!qd} inicial={qd} onClose={() => setQd(null)} escolas={escolas} onSaved={reload} />
    </div>
  );
}
