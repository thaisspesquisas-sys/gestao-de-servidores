import { useState } from "react";
import { toast } from "sonner";
import { FileDown, FileSpreadsheet, Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApi, useFetch, qs, errMsg, downloadFile } from "@/lib/api";
import { useMe } from "@/context/MeContext";
import { PageHeader, FilterBar } from "@/components/common";

const TIPOS = [
  ["geral", "Quadro geral de vagas da rede"], ["por_escola", "Quadro de vagas por escola"], ["por_cargo", "Quadro por cargo"],
  ["por_funcao", "Quadro por função"], ["ocupadas", "Vagas ocupadas"], ["disponiveis", "Vagas disponíveis"], ["reservadas", "Vagas reservadas"],
  ["deficit_excedente", "Déficit e excedente de profissionais"], ["servidores_unidade", "Relação de servidores por unidade"], ["historico", "Histórico de alterações", true],
];

export default function Relatorios() {
  const api = useApi();
  const { canGestao } = useMe();
  const [f, setF] = useState({});
  const [busy, setBusy] = useState("");
  const { data: meta } = useFetch("/meta");
  const baixar = async (tipo, formato, mode) => {
    setBusy(tipo + formato + (mode || ""));
    try { await downloadFile(api, `/relatorios/${tipo}${qs({ ...f, formato })}`, `relatorio_${tipo}.${formato}`, mode); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  return (
    <div>
      <PageHeader eyebrow="Documentos oficiais" title="Relatórios" subtitle="Relatórios gerados a partir dos dados validados, com exportação em PDF e Excel, impressão e download. Os filtros abaixo se aplicam a todos os relatórios." />
      <FilterBar meta={meta} value={f} onChange={setF} />
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {TIPOS.filter(([, , g]) => !g || canGestao).map(([t, label]) => (
          <div key={t} className="gold-line bg-white border border-slate-200 rounded-xl p-5 shadow-sm overflow-hidden" data-testid={`relatorio-card-${t}`}>
            <div className="font-display font-bold text-[#0B192C]">{label}</div>
            <div className="flex flex-wrap gap-2 mt-4">
              <Button size="sm" variant="outline" disabled={!!busy} onClick={() => baixar(t, "pdf")} data-testid={`relatorio-pdf-${t}`}><FileDown className="h-4 w-4 mr-1" />{busy === t + "pdf" ? "Gerando..." : "PDF"}</Button>
              <Button size="sm" variant="outline" disabled={!!busy} onClick={() => baixar(t, "xlsx")} data-testid={`relatorio-xlsx-${t}`}><FileSpreadsheet className="h-4 w-4 mr-1" />Excel</Button>
              <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => baixar(t, "pdf", "print")} data-testid={`relatorio-print-${t}`}><Printer className="h-4 w-4 mr-1" />Imprimir</Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
