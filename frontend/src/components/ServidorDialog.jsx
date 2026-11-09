import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApi, errMsg, fmtDate } from "@/lib/api";
import { useMe } from "@/context/MeContext";
import { Badge, Loading, SelectF } from "@/components/common";

const CAMPOS = [
  ["matricula", "Matrícula"], ["nome", "Nome completo"], ["cpf", "CPF"], ["cargo", "Cargo"], ["funcao", "Função"],
  ["lotacao", "Escola de lotação"], ["secretaria", "Secretaria de origem"], ["vinculo", "Tipo de contrato"],
  ["carga_horaria", "Carga horária"], ["admissao", "Data de admissão"], ["obs", "Observações"],
];

const Field = ({ label, value }) => (
  <div><div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div><div className="text-sm text-slate-900 break-words">{value || "—"}</div></div>
);

export const ServidorForm = ({ open, onClose, inicial, situacoes, onSaved }) => {
  const api = useApi();
  const [d, setD] = useState({});
  useEffect(() => {
    setD(inicial || { situacao: "ativo" });
  }, [inicial, open]);
  const salvar = async () => {
    try {
      const body = Object.fromEntries([...CAMPOS.map(([k]) => [k, d[k] || ""]), ["situacao", d.situacao || "ativo"]]);
      if (inicial?.id) await api("put", `/servidores/${inicial.id}`, body);
      else await api("post", "/servidores", body);
      toast.success("Vínculo salvo e registrado na auditoria");
      onSaved?.(); onClose();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl bg-white max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>{inicial?.id ? "Editar vínculo funcional" : "Novo vínculo funcional"}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {CAMPOS.map(([k, l]) => (
            <label key={k} className="text-xs text-slate-600">{l}
              <Input value={d[k] || ""} onChange={(e) => setD({ ...d, [k]: e.target.value })} className="mt-1 bg-white" data-testid={`servidor-form-${k}`} disabled={k === "matricula" && !!inicial?.id} />
            </label>
          ))}
          <label className="text-xs text-slate-600">Situação funcional
            <div className="mt-1"><SelectF noAll value={d.situacao || "ativo"} onChange={(v) => setD({ ...d, situacao: v })} options={situacoes.map((s) => ({ value: s.codigo, label: s.nome }))} testid="servidor-form-situacao" /></div>
          </label>
        </div>
        <Button onClick={salvar} className="bg-[#0B192C] hover:bg-[#1E3E62] mt-2" data-testid="servidor-form-save">Salvar</Button>
      </DialogContent>
    </Dialog>
  );
};

export const ServidorDialog = ({ id, onClose, situacoes = [], onChanged }) => {
  const api = useApi();
  const { canOperar, isAdmin } = useMe();
  const [data, setData] = useState(null);
  const [edit, setEdit] = useState(false);
  const load = async () => {
    try { setData(await api("get", `/servidores/${id}`)); } catch (e) { toast.error(errMsg(e)); }
  };
  useEffect(() => {
    if (id) { setData(null); load(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  const arquivar = async () => {
    const motivo = window.prompt("Motivo do arquivamento (autorização administrativa):");
    if (!motivo) return;
    try { await api("post", `/servidores/${id}/arquivar`, { motivo }); toast.success("Vínculo arquivado"); onChanged?.(); onClose(); } catch (e) { toast.error(errMsg(e)); }
  };
  const v = data?.vinculo;
  return (
    <>
      <Dialog open={!!id && !edit} onOpenChange={(o) => !o && onClose()}>
        <DialogContent className="max-w-3xl bg-white max-h-[90vh] overflow-y-auto" data-testid="servidor-dialog">
          <DialogHeader><DialogTitle>Vínculo funcional</DialogTitle></DialogHeader>
          {!v ? <Loading /> : (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-lg font-bold text-[#0B192C]">{v.nome}</span>
                <span className="num text-sm bg-slate-100 rounded px-2 py-0.5" data-testid="servidor-dialog-matricula">Mat. {v.matricula}</span>
                <Badge kind={v.regra}>{v.situacao_nome}</Badge>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <Field label="CPF" value={v.cpf} /><Field label="Cargo" value={v.cargo} /><Field label="Cargo padronizado" value={v.cargo_padrao} />
                <Field label="Função" value={v.funcao} /><Field label="Lotação (planilha)" value={v.lotacao} /><Field label="Escola identificada" value={v.escola || (v.lotacao_status === "nao_escola" ? "Fora das unidades escolares" : "Aguardando validação")} />
                <Field label="Secretaria de origem" value={v.secretaria} /><Field label="Tipo de contrato" value={v.vinculo} /><Field label="Carga horária" value={v.carga_horaria} />
                <Field label="Admissão" value={v.admissao} /><Field label="Origem da situação" value={v.situacao_detalhe} /><Field label="Observações" value={v.obs} />
              </div>
              {data.outros_vinculos.length > 0 && (
                <div><div className="text-sm font-semibold mb-1">Outros vínculos do mesmo servidor (mesmo nome/CPF/matrícula)</div>
                  <ul className="text-sm space-y-1">{data.outros_vinculos.map((o) => <li key={o.id}><span className="num">{o.matricula}</span> · {o.cargo} · {o.escola || o.lotacao} · {o.situacao_nome}</li>)}</ul></div>
              )}
              <div><div className="text-sm font-semibold mb-1">Histórico</div>
                {data.historico.length === 0 ? <p className="text-xs text-slate-500">Sem alterações registradas após o cadastro.</p> : (
                  <ul className="text-xs space-y-1 max-h-40 overflow-auto">{data.historico.map((h) => (
                    <li key={h.id}>{fmtDate(h.ts)} · <b>{h.acao}</b> · {h.usuario}: {Object.keys(h.depois || {}).map((k) => `${k}: "${(h.antes || {})[k] ?? ""}" → "${h.depois[k]}"`).join("; ")}</li>))}</ul>
                )}</div>
              <div className="flex gap-2">
                {canOperar && <Button variant="outline" onClick={() => setEdit(true)} data-testid="servidor-dialog-edit">Editar</Button>}
                {isAdmin && <Button variant="outline" className="text-red-700" onClick={arquivar} data-testid="servidor-dialog-archive">Arquivar vínculo</Button>}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
      <ServidorForm open={edit} onClose={() => setEdit(false)} inicial={v} situacoes={situacoes} onSaved={() => { load(); onChanged?.(); }} />
    </>
  );
};
