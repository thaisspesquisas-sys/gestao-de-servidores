import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useApi, useFetch, errMsg } from "@/lib/api";
import { useMe } from "@/context/MeContext";
import { PageHeader, Card, Loading, Badge, TableWrap, SelectF } from "@/components/common";

const SitRow = ({ s, labels, isAdmin, onSaved }) => {
  const api = useApi();
  const [d, setD] = useState(s);
  const changed = d.regra !== s.regra || d.conta_como_ativo !== s.conta_como_ativo;
  const salvar = async () => {
    try { await api("put", `/situacoes/${s.codigo}`, { regra: d.regra, conta_como_ativo: d.conta_como_ativo, descricao: d.descricao || "" }); toast.success(`Regra de "${s.nome}" atualizada — indicadores recalculados`); onSaved(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <tr data-testid={`situacao-row-${s.codigo}`}>
      <td className="font-medium text-sm">{s.nome} {s.sugerida && <Badge kind="reserva">sugerida — revisar</Badge>}</td>
      <td className="min-w-[260px]">{isAdmin ? <SelectF noAll value={d.regra} onChange={(v) => setD({ ...d, regra: v })} options={Object.entries(labels).map(([value, label]) => ({ value, label }))} testid={`situacao-regra-${s.codigo}`} /> : <Badge kind={s.regra}>{labels[s.regra]}</Badge>}</td>
      <td className="text-center"><Switch checked={!!d.conta_como_ativo} disabled={!isAdmin} onCheckedChange={(v) => setD({ ...d, conta_como_ativo: v })} data-testid={`situacao-ativo-${s.codigo}`} /></td>
      <td>{isAdmin && <Button size="sm" variant="outline" disabled={!changed && !s.sugerida} onClick={salvar} data-testid={`situacao-save-${s.codigo}`}><Save className="h-3.5 w-3.5 mr-1" />{s.sugerida && !changed ? "Confirmar" : "Salvar"}</Button>}</td>
    </tr>
  );
};

const Dimensionamento = ({ isAdmin, cargos }) => {
  const api = useApi();
  const { data, loading, reload } = useFetch("/regras");
  const [d, setD] = useState(null);
  useEffect(() => {
    if (data) setD(data);
  }, [data]);
  if (loading || !d) return <Loading />;
  const setE = (i, k, v) => setD({ ...d, etapas: d.etapas.map((e, j) => (j === i ? { ...e, [k]: v } : e)) });
  const salvar = async () => {
    try {
      await api("put", "/regras", { base_calculo: d.base_calculo, etapas: d.etapas.map((e) => ({ etapa: e.etapa, cargo: e.cargo || null, fator: e.fator === "" || e.fator === null ? null : Number(e.fator) })) });
      toast.success("Regras de dimensionamento salvas"); reload();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <>
      <datalist id="dim-cargos">{cargos.map((c) => <option key={c} value={c} />)}</datalist>
      <div className="mb-4 max-w-xl">
        <div className="text-[11px] font-semibold uppercase text-slate-500 mb-1">Base de cálculo das vagas</div>
        <SelectF noAll value={d.base_calculo} onChange={(v) => setD({ ...d, base_calculo: v })} testid="regras-base-calculo"
          options={[{ value: "oficial", label: "Somente o Quadro Oficial de Vagas (recomendado)" }, { value: "oficial_ou_previsto", label: "Quadro oficial; na ausência, previsto pelas regras de turmas" }]} />
      </div>
      <TableWrap testid="regras-etapas-table" maxH="none">
        <thead><tr><th>Etapa</th><th>Cargo que atende a etapa</th><th>Profissionais por turma</th></tr></thead>
        <tbody>{d.etapas.map((e, i) => (
          <tr key={e.etapa}><td className="font-medium text-sm">{e.etapa}</td>
            <td><Input list="dim-cargos" disabled={!isAdmin} value={e.cargo || ""} onChange={(ev) => setE(i, "cargo", ev.target.value)} placeholder="Sem regra definida" className="h-8 text-xs bg-white" data-testid={`regra-cargo-${i}`} /></td>
            <td><Input type="number" step="0.1" min="0" disabled={!isAdmin} value={e.fator ?? ""} onChange={(ev) => setE(i, "fator", ev.target.value)} placeholder="—" className="h-8 w-28 text-xs bg-white" data-testid={`regra-fator-${i}`} /></td></tr>))}</tbody>
      </TableWrap>
      {isAdmin && <Button onClick={salvar} className="mt-4 bg-[#0B192C] hover:bg-[#1E3E62]" data-testid="regras-save-button"><Save className="h-4 w-4 mr-1" /> Salvar regras</Button>}
    </>
  );
};

export default function Regras() {
  const api = useApi();
  const { isAdmin } = useMe();
  const { data: meta, loading, reload } = useFetch("/meta");
  const [nova, setNova] = useState("");
  const criar = async () => {
    try { await api("post", "/situacoes", { nome: nova, regra: "pendente", conta_como_ativo: true }); setNova(""); toast.success("Situação criada (regra pendente)"); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div>
      <PageHeader eyebrow="Configuração administrativa" title="Regras e Situações Funcionais" subtitle="Defina, a qualquer momento, como cada situação funcional interfere no quadro de vagas e como as turmas se convertem em necessidade de profissionais. Toda alteração recalcula os indicadores e fica registrada na auditoria." />
      <div className="grid grid-cols-1 2xl:grid-cols-2 gap-5">
        <Card title="Situações funcionais e efeito na vaga" testid="situacoes-card">
          {loading || !meta ? <Loading /> : (
            <>
              <TableWrap testid="situacoes-table" maxH="none">
                <thead><tr><th>Situação</th><th>Regra no quadro de vagas</th><th>Conta como ativo</th><th></th></tr></thead>
                <tbody>{meta.situacoes.map((s) => <SitRow key={s.codigo + s.regra + s.sugerida} s={s} labels={meta.regras_label} isAdmin={isAdmin} onSaved={reload} />)}</tbody>
              </TableWrap>
              {isAdmin && (
                <div className="flex gap-2 mt-4"><Input value={nova} onChange={(e) => setNova(e.target.value)} placeholder="Nova situação (ex.: Licença maternidade)" className="bg-white" data-testid="situacao-new-input" />
                  <Button variant="outline" disabled={nova.length < 3} onClick={criar} data-testid="situacao-new-button"><Plus className="h-4 w-4" /></Button></div>
              )}
              <p className="text-xs text-slate-500 mt-3">"Ocupa": conta como vaga ocupada · "Libera": a vaga volta a ficar disponível · "Reserva": a vaga fica bloqueada (reservada) · "Não definida": mantém ocupada e sinaliza pendência. Nenhuma vaga é liberada automaticamente sem regra.</p>
            </>
          )}
        </Card>
        <Card title="Dimensionamento: turmas → profissionais" testid="dimensionamento-card">
          <p className="text-xs text-slate-500 mb-4">Sem regra definida, o sistema não estima necessidade de profissionais. Resultados por regra são sempre identificados como "regra", nunca como dado oficial.</p>
          <Dimensionamento isAdmin={isAdmin} cargos={meta?.cargos || []} />
        </Card>
      </div>
    </div>
  );
}
