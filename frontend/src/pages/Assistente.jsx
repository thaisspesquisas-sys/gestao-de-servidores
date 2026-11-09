import { useState, useRef, useEffect } from "react";
import { Send, Bot, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApi, errMsg } from "@/lib/api";
import { PageHeader } from "@/components/common";

const SUGESTOES = [
  "Quantas vagas de professor existem disponíveis?",
  "Quais escolas precisam de professores?",
  "Quantos profissionais estão lotados na escola Sarah Faria Braz?",
  "Quantas vagas de educação infantil estão abertas?",
  "Existe algum cargo com excesso de servidores?",
  "Quais escolas apresentam divergências entre o quadro de turmas e a relação de servidores?",
  "Quantos servidores possuem mais de uma matrícula?",
];

const Resposta = ({ r }) => (
  <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm" data-testid="assistente-resposta">
    <p className="text-sm text-slate-900">{r.resposta}</p>
    {r.dados?.length > 0 && (
      <div className="overflow-auto max-h-72 mt-3 border border-slate-200 rounded-lg">
        <table className="table-dense w-full"><thead><tr>{Object.keys(r.dados[0]).map((k) => <th key={k}>{k}</th>)}</tr></thead>
          <tbody>{r.dados.map((d, i) => <tr key={i}>{Object.values(d).map((v, j) => <td key={j} className="text-xs">{v ?? "—"}</td>)}</tr>)}</tbody></table>
      </div>
    )}
    {r.faltando?.length > 0 && (
      <div className="mt-3 text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg p-3" data-testid="assistente-faltando">
        <div className="font-semibold flex items-center gap-1 mb-1"><Info className="h-3.5 w-3.5" /> Dados faltantes para uma resposta completa</div>
        <ul className="list-disc pl-4">{r.faltando.map((f) => <li key={f}>{f}</li>)}</ul>
      </div>
    )}
    {r.fonte && <div className="text-[10px] uppercase tracking-wider text-slate-400 mt-3">Fonte: {r.fonte}</div>}
  </div>
);

export default function Assistente() {
  const api = useApi();
  const [q, setQ] = useState("");
  const [msgs, setMsgs] = useState([]);
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);
  const perguntar = async (texto) => {
    const p = (texto ?? q).trim();
    if (p.length < 3) return;
    setQ(""); setBusy(true);
    setMsgs((m) => [...m, { tipo: "user", texto: p }]);
    try {
      const r = await api("post", "/assistente", { pergunta: p });
      setMsgs((m) => [...m, { tipo: "bot", r }]);
    } catch (e) {
      setMsgs((m) => [...m, { tipo: "bot", r: { resposta: errMsg(e), dados: [], faltando: [] } }]);
    } finally { setBusy(false); }
  };
  return (
    <div>
      <PageHeader eyebrow="Consultas sobre os dados validados" title="Assistente de Consultas" subtitle="Respostas calculadas exclusivamente a partir dos dados registrados e validados no banco. Quando faltam dados, o assistente informa o que precisa ser importado ou configurado." />
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        <div className="xl:col-span-4 space-y-2" data-testid="assistente-sugestoes">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Perguntas frequentes</div>
          {SUGESTOES.map((s, i) => (
            <button key={s} onClick={() => perguntar(s)} className="w-full text-left text-sm bg-white border border-slate-200 rounded-lg px-4 py-3 hover:border-[#D4AF37] hover:bg-[#FDF8EA] transition-colors" data-testid={`assistente-sugestao-${i}`}>{s}</button>
          ))}
        </div>
        <div className="xl:col-span-8 flex flex-col bg-slate-50 border border-slate-200 rounded-xl min-h-[60vh]">
          <div className="flex-1 overflow-y-auto p-5 space-y-4 max-h-[65vh]" data-testid="assistente-conversa">
            {!msgs.length && <div className="text-center text-slate-500 text-sm py-16"><Bot className="h-10 w-10 mx-auto text-[#D4AF37] mb-3" />Faça uma pergunta ou escolha uma sugestão.</div>}
            {msgs.map((m, i) => m.tipo === "user"
              ? <div key={i} className="flex justify-end"><div className="bg-[#0B192C] text-white rounded-xl px-4 py-2.5 text-sm max-w-[80%]">{m.texto}</div></div>
              : <Resposta key={i} r={m.r} />)}
            <div ref={end} />
          </div>
          <form className="flex gap-2 p-4 border-t border-slate-200 bg-white rounded-b-xl" onSubmit={(e) => { e.preventDefault(); perguntar(); }}>
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ex.: Quantas vagas de professor estão disponíveis?" className="bg-white" data-testid="assistente-input" />
            <Button type="submit" disabled={busy} className="bg-[#0B192C] hover:bg-[#1E3E62]" data-testid="assistente-send-button"><Send className="h-4 w-4" /></Button>
          </form>
        </div>
      </div>
    </div>
  );
}
