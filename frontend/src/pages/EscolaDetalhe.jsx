import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, FileDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useApi, useFetch, qs, fmt, downloadFile } from "@/lib/api";
import { PageHeader, Card, Kpi, Loading, Badge, TableWrap, Empty } from "@/components/common";
import { ServidorDialog } from "@/components/ServidorDialog";

export default function EscolaDetalhe() {
  const { id } = useParams();
  const api = useApi();
  const [sel, setSel] = useState(null);
  const { data, loading, reload } = useFetch(`/escolas/${id}`);
  const { data: meta } = useFetch("/meta");
  if (loading && !data) return <Loading />;
  if (!data) return <Empty>Escola não encontrada.</Empty>;
  const r = data.resumo;
  return (
    <div>
      <Link to="/escolas" className="inline-flex items-center text-sm text-slate-500 hover:text-[#0B192C] mb-4" data-testid="escola-back-link"><ArrowLeft className="h-4 w-4 mr-1" /> Todas as escolas</Link>
      <PageHeader eyebrow="Unidade escolar" title={data.escola.nome} subtitle={data.nomes_correspondentes.length ? `Também identificada como: ${data.nomes_correspondentes.join(" · ")}` : null}
        actions={<Button variant="outline" onClick={() => downloadFile(api, `/relatorios/servidores_unidade${qs({ formato: "pdf", escola: id })}`, "servidores_unidade.pdf")} data-testid="escola-export-button"><FileDown className="h-4 w-4 mr-1" /> Relação nominal (PDF)</Button>} />
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4 mb-6">
        <Kpi testid="escola-kpi-previsto" label="Previstos (regra)" value={r.previsto || null} hint={r.previsto ? null : "sem regra"} />
        <Kpi testid="escola-kpi-base" label="Autorizadas" value={r.base} />
        <Kpi testid="escola-kpi-ocupadas" label="Ocupantes" value={r.ocupadas} tone="blue" />
        <Kpi testid="escola-kpi-reservadas" label="Reservadas" value={r.reservadas} tone="amber" />
        <Kpi testid="escola-kpi-disponiveis" label="Disponíveis" value={r.disponiveis} tone="green" />
        <Kpi testid="escola-kpi-saldo" label={r.saldo >= 0 ? "Déficit" : "Excedente"} value={Math.abs(r.saldo)} tone={r.saldo > 0 ? "red" : r.saldo < 0 ? "violet" : "navy"} />
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        <Card title="Turmas por etapa" className="xl:col-span-4" testid="escola-etapas">
          {!data.tem_distribuicao ? <Empty>Sem quadro de turmas importado.</Empty> : (
            <TableWrap maxH="none"><thead><tr><th>Etapa</th><th>Turmas</th><th>Previstos</th></tr></thead>
              <tbody>{data.etapas.filter((e) => e.turmas).map((e) => <tr key={e.etapa}><td>{e.etapa}</td><td className="num text-center">{e.turmas}</td><td className="num text-center">{fmt(e.previstos)}</td></tr>)}</tbody></TableWrap>
          )}
        </Card>
        <Card title="Vagas por cargo e função" className="xl:col-span-8" testid="escola-vagas">
          <TableWrap maxH="420px"><thead><tr><th>Cargo</th><th>Função</th><th>Base</th><th>Ocup.</th><th>Res.</th><th>Disp.</th><th>Exced.</th></tr></thead>
            <tbody>{data.linhas.map((l) => (
              <tr key={l.key}><td className="text-xs">{l.cargo}</td><td className="text-xs">{l.funcao || "—"}</td>
                <td className="text-center">{l.base === null ? <span className="text-xs text-slate-400">sem quadro</span> : <span className="num">{l.base}</span>}</td>
                <td className="num text-center">{l.ocupadas}</td><td className="num text-center">{l.reservadas}</td>
                <td className="num text-center text-emerald-700">{fmt(l.disponiveis)}</td><td className="num text-center text-violet-700">{fmt(l.excedente)}</td></tr>))}</tbody></TableWrap>
        </Card>
        <Card title={`Relação nominal dos servidores (${data.servidores.length})`} className="xl:col-span-12" testid="escola-servidores">
          <TableWrap maxH="520px" testid="escola-servidores-table"><thead><tr><th>Matrícula</th><th>Nome</th><th>Cargo</th><th>Função</th><th>Vínculo</th><th>C.H.</th><th>Situação</th></tr></thead>
            <tbody>{data.servidores.map((v) => (
              <tr key={v.id} className="cursor-pointer" onClick={() => setSel(v.id)} data-testid={`escola-servidor-${v.matricula}`}>
                <td className="num">{v.matricula}</td><td className="font-medium">{v.nome}</td><td className="text-xs">{v.cargo_padrao}</td><td className="text-xs">{v.funcao}</td>
                <td className="text-xs">{v.vinculo}</td><td className="text-xs whitespace-nowrap">{v.carga_horaria}</td><td><Badge kind={v.regra}>{v.situacao_nome}</Badge></td></tr>))}</tbody></TableWrap>
        </Card>
      </div>
      <ServidorDialog id={sel} onClose={() => setSel(null)} situacoes={meta?.situacoes || []} onChanged={reload} />
    </div>
  );
}
