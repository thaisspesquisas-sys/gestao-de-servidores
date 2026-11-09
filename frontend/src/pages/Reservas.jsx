import { Fragment, useState } from "react";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useApi, useFetch, qs, errMsg, fmtDate } from "@/lib/api";
import { useMe } from "@/context/MeContext";
import { PageHeader, Loading, Badge, TableWrap, SelectF, Empty } from "@/components/common";

const hoje = () => new Date().toISOString().slice(0, 10);

const ReservaForm = ({ inicial, onClose, escolas, cargos, onSaved }) => {
  const api = useApi();
  const { me } = useMe();
  const [d, setD] = useState(() => inicial?.id ? { ...inicial } : { data_reserva: hoje(), responsavel: me?.nome || me?.email || "", quantidade: 1, funcao: "", previsao_utilizacao: "" });
  const set = (k) => (e) => setD({ ...d, [k]: e.target.value });
  const salvar = async () => {
    try {
      const body = { school_id: d.school_id, cargo: d.cargo, funcao: d.funcao || "", quantidade: parseInt(d.quantidade, 10), motivo: d.motivo, data_reserva: d.data_reserva, responsavel: d.responsavel, previsao_utilizacao: d.previsao_utilizacao || "" };
      if (inicial?.id) await api("put", `/reservas/${inicial.id}`, body); else await api("post", "/reservas", body);
      toast.success("Reserva salva"); onSaved(); onClose();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-xl bg-white max-h-[90vh] overflow-y-auto" data-testid="reserva-form">
        <DialogHeader><DialogTitle>{inicial?.id ? "Alterar reserva" : "Nova reserva de vagas"}</DialogTitle></DialogHeader>
        <datalist id="res-cargos">{cargos.map((c) => <option key={c} value={c} />)}</datalist>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="sm:col-span-2"><SelectF noAll value={d.school_id} onChange={(v) => setD({ ...d, school_id: v })} options={escolas} placeholder="Escola" testid="reserva-form-escola" /></div>
          <Input list="res-cargos" placeholder="Cargo" value={d.cargo || ""} onChange={set("cargo")} data-testid="reserva-form-cargo" />
          <Input placeholder="Função (opcional)" value={d.funcao || ""} onChange={set("funcao")} data-testid="reserva-form-funcao" />
          <label className="text-xs text-slate-600">Quantidade<Input type="number" min="1" value={d.quantidade} onChange={set("quantidade")} data-testid="reserva-form-quantidade" /></label>
          <label className="text-xs text-slate-600">Data da reserva<Input type="date" value={d.data_reserva} onChange={set("data_reserva")} data-testid="reserva-form-data" /></label>
          <label className="text-xs text-slate-600">Responsável<Input value={d.responsavel} onChange={set("responsavel")} data-testid="reserva-form-responsavel" /></label>
          <label className="text-xs text-slate-600">Previsão de utilização<Input type="date" value={d.previsao_utilizacao} onChange={set("previsao_utilizacao")} data-testid="reserva-form-previsao" /></label>
          <Textarea className="sm:col-span-2" placeholder="Motivo (nomeação futura, concurso, processo seletivo...)" value={d.motivo || ""} onChange={set("motivo")} data-testid="reserva-form-motivo" />
        </div>
        <Button onClick={salvar} className="bg-[#0B192C] hover:bg-[#1E3E62]" data-testid="reserva-form-save">Salvar reserva</Button>
      </DialogContent>
    </Dialog>
  );
};

export default function Reservas() {
  const api = useApi();
  const { canOperar, canGestao } = useMe();
  const [sit, setSit] = useState("ativa");
  const [form, setForm] = useState(null);
  const [aberto, setAberto] = useState(null);
  const { data: meta } = useFetch("/meta");
  const { data, loading, reload } = useFetch(`/reservas${qs({ situacao: sit })}`);
  const escolas = (meta?.escolas || []).map((e) => ({ value: e.id, label: e.nome }));
  const acao = async (r, tipo) => {
    const obs = window.prompt(tipo === "cancelar" ? "Motivo do cancelamento:" : "Observação da efetivação (ex.: nº da portaria de nomeação):");
    if (obs === null) return;
    try { await api("post", `/reservas/${r.id}/${tipo}`, { observacao: obs }); toast.success(tipo === "cancelar" ? "Reserva cancelada — vaga liberada" : "Reserva efetivada"); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div>
      <PageHeader eyebrow="Nomeações futuras · concursos · processos seletivos" title="Reservas de Vagas" subtitle="Reservas ativas são descontadas das vagas disponíveis. Todas as operações ficam registradas no histórico."
        actions={canOperar && <Button onClick={() => setForm({})} className="bg-[#0B192C] hover:bg-[#1E3E62]" data-testid="reserva-new-button"><Plus className="h-4 w-4 mr-1" /> Nova reserva</Button>} />
      <div className="w-60 mb-4"><SelectF value={sit} onChange={setSit} allLabel="Todas" testid="reserva-status-filter"
        options={[{ value: "ativa", label: "Ativas" }, { value: "efetivada", label: "Efetivadas" }, { value: "cancelada", label: "Canceladas" }]} /></div>
      {loading && !data ? <Loading /> : !data?.length ? <Empty>Nenhuma reserva encontrada.</Empty> : (
        <TableWrap testid="reservas-table">
          <thead><tr><th>Escola</th><th>Cargo / Função</th><th>Qtd.</th><th>Motivo</th><th>Data</th><th>Responsável</th><th>Previsão</th><th>Situação</th><th>Ações</th></tr></thead>
          <tbody>{data.map((r) => (<Fragment key={r.id}>
            <tr data-testid={`reserva-row-${r.id}`}>
              <td className="text-xs font-medium">{r.escola}</td><td className="text-xs">{r.cargo}{r.funcao && ` / ${r.funcao}`}</td><td className="num text-center">{r.quantidade}</td>
              <td className="text-xs max-w-[220px]">{r.motivo}</td><td className="text-xs">{r.data_reserva}</td><td className="text-xs">{r.responsavel}</td><td className="text-xs">{r.previsao_utilizacao || "—"}</td>
              <td><Badge kind={r.situacao}>{r.situacao}</Badge></td>
              <td className="whitespace-nowrap space-x-1">
                <Button size="sm" variant="ghost" onClick={() => setAberto(aberto === r.id ? null : r.id)} data-testid={`reserva-history-${r.id}`}>Histórico</Button>
                {r.situacao === "ativa" && canOperar && <Button size="sm" variant="outline" onClick={() => setForm(r)} data-testid={`reserva-edit-${r.id}`}>Alterar</Button>}
                {r.situacao === "ativa" && canGestao && <Button size="sm" variant="outline" className="text-emerald-700" onClick={() => acao(r, "efetivar")} data-testid={`btn-efetivar-reserva-${r.id}`}>Efetivar</Button>}
                {r.situacao === "ativa" && canGestao && <Button size="sm" variant="outline" className="text-red-700" onClick={() => acao(r, "cancelar")} data-testid={`btn-cancelar-reserva-${r.id}`}>Cancelar</Button>}
              </td>
            </tr>
            {aberto === r.id && <tr><td colSpan={9} className="bg-slate-50"><ul className="text-xs space-y-1">{r.historico.map((h, i) => <li key={i}>{fmtDate(h.ts)} · <b>{h.acao}</b> · {h.usuario}{h.observacao ? ` — ${h.observacao}` : ""}</li>)}</ul></td></tr>}
          </Fragment>))}</tbody>
        </TableWrap>
      )}
      {form && <ReservaForm inicial={form} onClose={() => setForm(null)} escolas={escolas} cargos={meta?.cargos || []} onSaved={reload} />}
    </div>
  );
}
