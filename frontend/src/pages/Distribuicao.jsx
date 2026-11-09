import { useState } from "react";
import { toast } from "sonner";
import { Pencil, Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApi, useFetch, errMsg } from "@/lib/api";
import { useMe } from "@/context/MeContext";
import { PageHeader, Loading, Empty } from "@/components/common";

const Row = ({ r, etapas, canEdit, onSaved }) => {
  const api = useApi();
  const [edit, setEdit] = useState(null);
  const vals = edit || r.etapas;
  const total = etapas.reduce((s, e) => s + (Number(vals[e]) || 0), 0);
  const salvar = async () => {
    try {
      const body = { etapas: Object.fromEntries(etapas.map((e) => [e, parseInt(edit[e] || 0, 10)])) };
      await api("put", `/distribuicao/${r.school_id}`, body);
      toast.success(`Quadro de ${r.escola} atualizado`);
      setEdit(null); onSaved();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <tr data-testid={`dist-row-${r.school_id}`} className={edit ? "bg-[#FDF8EA]" : ""}>
      <td className="sticky left-0 bg-white z-[1] font-medium text-xs min-w-[220px] border-r border-slate-200">{r.escola}{!r.cadastrado && <span className="block text-[10px] text-amber-700">sem quadro de turmas</span>}</td>
      {etapas.map((e) => (
        <td key={e} className="num text-center">
          {edit ? <input type="number" min="0" value={edit[e] ?? 0} onChange={(ev) => setEdit({ ...edit, [e]: ev.target.value })} className="w-12 border border-slate-300 rounded px-1 py-0.5 text-center bg-white" data-testid={`dist-input-${r.school_id}-${e}`.replace(/\s|º|É/g, "_")} />
            : vals[e] || ""}
        </td>
      ))}
      <td className="num text-center font-semibold" data-testid={`dist-total-${r.school_id}`}>{total}</td>
      {canEdit && (
        <td className="whitespace-nowrap">
          {edit ? (<>
            <button onClick={salvar} className="p-1 text-emerald-700" data-testid={`dist-save-${r.school_id}`}><Save className="h-4 w-4" /></button>
            <button onClick={() => setEdit(null)} className="p-1 text-slate-500"><X className="h-4 w-4" /></button></>)
            : <button onClick={() => setEdit({ ...r.etapas })} className="p-1 text-slate-600 hover:text-[#0B192C]" data-testid={`dist-edit-${r.school_id}`}><Pencil className="h-4 w-4" /></button>}
        </td>
      )}
    </tr>
  );
};

export default function Distribuicao() {
  const { canOperar } = useMe();
  const { data, loading, reload } = useFetch("/distribuicao");
  return (
    <div>
      <PageHeader eyebrow="Estrutura escolar" title="Quadro de Distribuição Escolar" subtitle="Quantitativos por etapa de ensino. Estes números representam TURMAS — a necessidade de profissionais é calculada somente pelas regras definidas em Regras e Situações." />
      {loading && !data ? <Loading /> : !data?.linhas.length ? <Empty>Nenhuma escola cadastrada. Importe o Quadro de Distribuição na Central de Importação.</Empty> : (
        <div className="overflow-auto rounded-lg border border-slate-200 bg-white max-h-[75vh]" data-testid="table-quadro-distribuicao">
          <table className="table-dense w-full border-collapse">
            <thead><tr><th className="sticky left-0 z-[3] text-left">Escola</th>{data.etapas.map((e) => <th key={e}>{e}</th>)}<th>Total</th>{canOperar && <th></th>}</tr></thead>
            <tbody>
              {data.linhas.map((r) => <Row key={r.school_id} r={r} etapas={data.etapas} canEdit={canOperar} onSaved={reload} />)}
              <tr className="font-semibold bg-slate-50"><td className="sticky left-0 bg-slate-100 z-[1]">TOTAL</td>{data.etapas.map((e) => <td key={e} className="num text-center bg-slate-100">{data.totais[e]}</td>)}
                <td className="num text-center bg-slate-100" data-testid="dist-total-geral">{data.total_geral}</td>{canOperar && <td className="bg-slate-100"></td>}</tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
