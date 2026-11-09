import { useState } from "react";
import { toast } from "sonner";
import { Upload, Eye, CheckCircle2, Download, FileSpreadsheet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApi, useFetch, errMsg, fmtDate, downloadFile } from "@/lib/api";
import { PageHeader, Card, SelectF, Loading, Badge, TableWrap } from "@/components/common";

const CATS = [
  { value: "servidores", label: "A) Relação geral de servidores" },
  { value: "distribuicao", label: "B) Quadro de distribuição das escolas" },
  { value: "quadro", label: "C) Quadro oficial de vagas" },
  { value: "ignorar", label: "Ignorar esta aba" },
];

const MapEditor = ({ aba, campos, obrig, onChange }) => {
  const header = aba.primeiras_linhas[aba.header_row] || [];
  const cols = header.map((h, i) => ({ value: String(i), label: `${String.fromCharCode(65 + (i % 26))}${i >= 26 ? Math.floor(i / 26) : ""} · ${h || "(vazio)"}` }));
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
      {campos.map((c) => (
        <div key={c}>
          <div className="text-[11px] font-semibold uppercase text-slate-500 mb-1">{c.replace("_", " ")}{obrig.includes(c) && <span className="text-red-600"> *</span>}</div>
          <SelectF value={aba.mapping[c] !== undefined && aba.mapping[c] !== null ? String(aba.mapping[c]) : ""} onChange={(v) => onChange({ ...aba.mapping, [c]: v === "" ? null : Number(v) })}
            options={cols} allLabel="(não mapear)" testid={`map-${aba.sheet}-${c}`.replace(/\s/g, "_")} />
        </div>
      ))}
    </div>
  );
};

const AbaConfig = ({ aba, idx, info, situacoes, onChange }) => (
  <div className="border border-slate-200 rounded-lg p-4 bg-slate-50/40" data-testid={`aba-config-${idx}`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="font-semibold text-[#0B192C] flex items-center gap-2"><FileSpreadsheet className="h-4 w-4 text-[#D4AF37]" />{aba.sheet}<span className="text-xs font-normal text-slate-500">{aba.linhas} linhas com dados</span></div>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3">
      <div><div className="text-[11px] font-semibold uppercase text-slate-500 mb-1">Categoria</div>
        <SelectF noAll value={aba.categoria} onChange={(v) => onChange({ ...aba, categoria: v, mapping: v === aba._detCat ? aba._detMap : {} })} options={CATS} testid={`aba-categoria-${idx}`} /></div>
      <div><div className="text-[11px] font-semibold uppercase text-slate-500 mb-1">Linha do cabeçalho</div>
        <SelectF noAll value={String(aba.header_row)} onChange={(v) => onChange({ ...aba, header_row: Number(v) })}
          options={aba.primeiras_linhas.map((r, i) => ({ value: String(i), label: `Linha ${i + 1}: ${r.filter(Boolean).slice(0, 3).join(" | ").slice(0, 50)}` }))} testid={`aba-header-${idx}`} /></div>
      {aba.categoria === "servidores" && (
        <div><div className="text-[11px] font-semibold uppercase text-slate-500 mb-1">Situação funcional dos registros</div>
          <SelectF noAll value={aba.situacao_padrao} onChange={(v) => onChange({ ...aba, situacao_padrao: v })}
            options={[{ value: "auto", label: "Identificar automaticamente (lotação/obs/vínculo)" }, ...situacoes.map((s) => ({ value: s.codigo, label: s.nome }))]} testid={`aba-situacao-${idx}`} /></div>
      )}
    </div>
    {aba.categoria !== "ignorar" && <MapEditor aba={aba} campos={info.campos[aba.categoria]} obrig={info.obrigatorios[aba.categoria]} onChange={(m) => onChange({ ...aba, mapping: m })} />}
  </div>
);

const Resultado = ({ r }) => (
  <div className="border border-slate-200 rounded-lg p-4" data-testid={`preview-${r.sheet}`}>
    <div className="flex flex-wrap items-center gap-2 mb-3">
      <span className="font-semibold text-[#0B192C]">{r.sheet}</span><Badge>{r.categoria}</Badge>
      <Badge kind="libera">{r.novos} novos</Badge><Badge kind="reserva">{r.alterados} alterados</Badge>
      <Badge>{r.sem_alteracao} sem alteração</Badge><Badge kind="pendente">{r.erros.filter((e) => !e.aviso).length} erros</Badge>
    </div>
    {r.erros.length > 0 && (
      <details className="mb-2"><summary className="text-sm cursor-pointer text-red-700">Erros e avisos ({r.erros.length})</summary>
        <ul className="text-xs mt-2 max-h-48 overflow-auto space-y-0.5">{r.erros.map((e, i) => <li key={i} className={e.aviso ? "text-amber-700" : "text-red-700"}>Linha {e.linha}: {e.mensagem}</li>)}</ul></details>
    )}
    {r.escolas_pendentes.length > 0 && (
      <details className="mb-2"><summary className="text-sm cursor-pointer text-amber-800">Lotações que precisarão de validação ({r.escolas_pendentes.length})</summary>
        <div className="text-xs mt-2 flex flex-wrap gap-1">{r.escolas_pendentes.map((e) => <Badge key={e} kind="reserva">{e}</Badge>)}</div></details>
    )}
    {r.amostra_alterados.length > 0 && (
      <details className="mb-2"><summary className="text-sm cursor-pointer">Alterações identificadas (amostra)</summary>
        <ul className="text-xs mt-2 max-h-56 overflow-auto space-y-1">{r.amostra_alterados.map((a, i) => (
          <li key={i}><b>{a.nome}</b> {a.matricula && <span className="num">({a.matricula})</span>}: {Object.entries(a.diff || {}).map(([k, d]) => `${k}: "${d.antes}" → "${d.depois}"`).join("; ")}</li>))}</ul></details>
    )}
    {r.amostra_novos.length > 0 && (
      <details><summary className="text-sm cursor-pointer">Registros novos (amostra)</summary>
        <ul className="text-xs mt-2 max-h-56 overflow-auto space-y-0.5">{r.amostra_novos.map((a, i) => <li key={i}>Linha {a.linha}: {Object.values(a).slice(1).filter(Boolean).join(" · ")}</li>)}</ul></details>
    )}
  </div>
);

export default function Importacao() {
  const api = useApi();
  const hist = useFetch("/importacao");
  const { data: meta } = useFetch("/meta");
  const [file, setFile] = useState(null);
  const [info, setInfo] = useState(null);
  const [abas, setAbas] = useState([]);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState("");

  const enviar = async () => {
    if (!file) return toast.error("Selecione um arquivo");
    setBusy("upload"); setPreview(null);
    try {
      const fd = new FormData(); fd.append("file", file);
      const r = await api("post", "/importacao/upload", fd);
      setInfo(r);
      setAbas(r.abas.map((a) => ({ ...a, _detCat: a.categoria, _detMap: a.mapping })));
      toast.success(`Arquivo lido: ${r.abas.length} aba(s) encontrada(s)`);
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  const body = () => ({ abas: abas.map(({ sheet, categoria, header_row, mapping, situacao_padrao }) => ({ sheet, categoria, header_row, mapping, situacao_padrao })) });
  const previa = async () => {
    setBusy("previa");
    try { setPreview(await api("post", `/importacao/${info.id}/previa`, body())); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };
  const confirmar = async () => {
    setBusy("confirmar");
    try {
      const r = await api("post", `/importacao/${info.id}/confirmar`, body());
      const tot = r.planilhas.reduce((s, p) => s + p.novos + p.alterados, 0);
      toast.success(`Importação concluída: ${tot} registro(s) gravados/atualizados`);
      setInfo(null); setAbas([]); setPreview(null); setFile(null); hist.reload();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); }
  };

  return (
    <div>
      <PageHeader eyebrow="Fonte de dados" title="Central de Importação de Dados" subtitle="Importe planilhas oficiais (XLSX, XLS, CSV ou PDF). O sistema identifica cabeçalhos, sugere o mapeamento de colunas e mostra uma prévia antes de salvar." />
      <Card title="1. Enviar arquivo" className="mb-5">
        <div className="flex flex-col sm:flex-row gap-3">
          <Input type="file" accept=".xlsx,.xls,.xlsm,.csv,.pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="import-file-input" className="bg-white" />
          <Button onClick={enviar} disabled={busy === "upload"} className="bg-[#0B192C] hover:bg-[#1E3E62]" data-testid="import-upload-button"><Upload className="h-4 w-4 mr-2" />{busy === "upload" ? "Lendo..." : "Ler arquivo"}</Button>
        </div>
      </Card>
      {info && (
        <Card title={`2. Configurar abas de "${info.filename}"`} className="mb-5" testid="import-config">
          <div className="space-y-4">{abas.map((a, i) => (
            <AbaConfig key={a.sheet} aba={a} idx={i} info={info} situacoes={meta?.situacoes || []} onChange={(n) => { setAbas(abas.map((x, j) => (j === i ? n : x))); setPreview(null); }} />))}</div>
          <div className="flex gap-2 mt-5">
            <Button onClick={previa} disabled={!!busy} variant="outline" data-testid="import-preview-button"><Eye className="h-4 w-4 mr-2" />{busy === "previa" ? "Analisando..." : "Gerar prévia"}</Button>
          </div>
        </Card>
      )}
      {preview && (
        <Card title="3. Prévia da leitura" className="mb-5" testid="import-preview">
          <div className="space-y-3">{preview.planilhas.map((r) => <Resultado key={r.sheet} r={r} />)}</div>
          {!preview.planilhas.length && <p className="text-sm text-slate-500">Nenhuma aba selecionada para importação.</p>}
          <Button onClick={confirmar} disabled={!!busy || !preview.planilhas.length} className="mt-5 bg-[#D4AF37] text-[#0B192C] hover:bg-[#B89628]" data-testid="import-confirm-button">
            <CheckCircle2 className="h-4 w-4 mr-2" />{busy === "confirmar" ? "Gravando..." : "Confirmar e salvar"}</Button>
        </Card>
      )}
      <Card title="Histórico de importações">
        {hist.loading ? <Loading /> : (
          <TableWrap testid="import-history-table" maxH="50vh">
            <thead><tr><th>Data</th><th>Arquivo</th><th>Usuário</th><th>Situação</th><th>Resumo</th><th></th></tr></thead>
            <tbody>{(hist.data || []).map((h) => (
              <tr key={h.id}>
                <td className="whitespace-nowrap">{fmtDate(h.ts)}</td><td>{h.filename}</td><td>{h.usuario}</td>
                <td><Badge kind={h.status === "concluida" ? "confirmado" : "reserva"}>{h.status === "concluida" ? "Concluída" : "Não confirmada"}</Badge></td>
                <td className="text-xs">{(h.resumo || []).map((r) => `${r.sheet}: ${r.novos} novos, ${r.alterados} alt., ${r.erros} erros`).join(" · ")}</td>
                <td><Button size="sm" variant="ghost" onClick={() => downloadFile(api, `/importacao/${h.id}/arquivo`, h.filename)} data-testid={`import-download-${h.id}`}><Download className="h-4 w-4" /></Button></td>
              </tr>))}</tbody>
          </TableWrap>
        )}
      </Card>
    </div>
  );
}
