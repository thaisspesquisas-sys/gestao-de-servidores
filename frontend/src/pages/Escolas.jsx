import { useState } from "react";
import { Link } from "react-router-dom";
import { Search, Building2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useFetch, fmt } from "@/lib/api";
import { PageHeader, Loading, Empty } from "@/components/common";

const Stat = ({ l, v, c = "text-[#0B192C]" }) => (
  <div><div className="text-[10px] uppercase tracking-wide text-slate-500">{l}</div><div className={`num text-lg font-semibold ${c}`}>{fmt(v)}</div></div>
);

export default function Escolas() {
  const [q, setQ] = useState("");
  const { data, loading } = useFetch("/escolas");
  const lista = (data || []).filter((e) => e.nome.toLowerCase().includes(q.toLowerCase()));
  return (
    <div>
      <PageHeader eyebrow="Consulta individual" title="Consulta por Escola" subtitle="Selecione uma unidade para ver turmas, profissionais previstos, ocupantes, vagas e a relação nominal dos servidores." />
      <div className="relative max-w-md mb-6"><Search className="h-4 w-4 absolute left-3 top-3 text-slate-400" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar escola" className="pl-9 bg-white" data-testid="escola-search-input" /></div>
      {loading && !data ? <Loading /> : !lista.length ? <Empty>Nenhuma escola encontrada.</Empty> : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {lista.map((e, i) => (
            <Link key={e.id} to={`/escolas/${e.id}`} className="gold-line fade-up bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-[box-shadow,transform] duration-200 overflow-hidden" style={{ animationDelay: `${Math.min(i, 12) * 30}ms` }} data-testid={`escola-card-${e.id}`}>
              <div className="flex items-start gap-3"><Building2 className="h-5 w-5 text-[#D4AF37] shrink-0 mt-0.5" /><div className="font-display font-bold text-[#0B192C] leading-snug">{e.nome}</div></div>
              <div className="grid grid-cols-3 gap-3 mt-4">
                <Stat l="Turmas" v={e.turmas} /><Stat l="Servidores" v={e.servidores} /><Stat l="Autorizadas" v={e.base} />
                <Stat l="Disponíveis" v={e.disponiveis} c="text-emerald-700" /><Stat l="Reservadas" v={e.reservadas} c="text-amber-700" /><Stat l="Excedente" v={e.excedente} c="text-violet-700" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
