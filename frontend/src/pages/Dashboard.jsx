import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, PieChart, Pie, Cell } from "recharts";
import { Briefcase, CheckCircle2, Bookmark, CircleDot, Users, School, TrendingDown, TrendingUp, AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import { useFetch, qs } from "@/lib/api";
import { PageHeader, Kpi, Card, FilterBar, Loading, Empty } from "@/components/common";

const C = { ocupadas: "#1E3E62", reservadas: "#D97706", disponiveis: "#059669", excedente: "#7C3AED", base: "#D4AF37" };
const PIE = ["#0B192C", "#1E3E62", "#D4AF37", "#059669", "#D97706", "#7C3AED", "#DC2626", "#64748B", "#0EA5E9", "#A3A3A3", "#14B8A6"];

const Alertas = ({ k }) => {
  const itens = [];
  if (!k.quadro_oficial_importado) itens.push("Nenhum Quadro Oficial de Vagas importado: vagas autorizadas, disponíveis e excedentes só são calculadas onde houver quadro oficial" + (k.base_calculo === "oficial_ou_previsto" ? " ou regra de dimensionamento." : "."));
  if (k.vinculos_sem_escola) itens.push(`${k.vinculos_sem_escola} vínculo(s) com lotação ainda não identificada — valide em Cruzamento & Correspondência.`);
  if (k.situacoes_pendentes) itens.push(`${k.situacoes_pendentes} vínculo(s) em situação sem regra definida (mantidos como ocupados).`);
  if (k.linhas_sem_base) itens.push(`${k.linhas_sem_base} combinação(ões) escola/cargo sem base de cálculo (sem quadro autorizado).`);
  if (!itens.length) return null;
  return (
    <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50/70 p-4 text-sm text-amber-900" data-testid="dashboard-alerts">
      <div className="flex items-center gap-2 font-semibold mb-2"><AlertTriangle className="h-4 w-4" /> Pontos de atenção na base de dados</div>
      <ul className="list-disc pl-5 space-y-1">{itens.map((t) => <li key={t}>{t}</li>)}</ul>
    </div>
  );
};

export default function Dashboard() {
  const [f, setF] = useState({});
  const { data: meta } = useFetch("/meta");
  const { data, loading } = useFetch(`/dashboard${qs(f)}`);
  const k = data?.kpis;
  const escolas = (data?.por_escola || []).map((e) => ({ ...e, nome: e.nome.length > 28 ? e.nome.slice(0, 28) + "…" : e.nome }));
  const cargos = [...(data?.por_cargo || [])].sort((a, b) => b.ocupadas - a.ocupadas).slice(0, 12);
  return (
    <div>
      <PageHeader eyebrow="Painel da rede municipal" title="Dashboard de Indicadores" subtitle="Indicadores calculados automaticamente a partir dos dados importados e validados." />
      <FilterBar meta={meta} value={f} onChange={setF} />
      {loading && !data ? <Loading /> : !k ? <Empty>Sem dados.</Empty> : (
        <>
          <Alertas k={k} />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-5 mb-6">
            <Kpi testid="kpi-vagas-autorizadas" label="Vagas autorizadas" value={k.vagas_base} icon={Briefcase} hint={`${k.autorizadas_oficiais} do quadro oficial${k.base_calculo === "oficial_ou_previsto" ? ` · ${k.vagas_base - k.autorizadas_oficiais} por regra` : ""}`} />
            <Kpi testid="kpi-vagas-ocupadas" label="Vagas ocupadas" value={k.ocupadas} tone="blue" icon={CheckCircle2} hint="Vínculos ativos lotados em escolas" />
            <Kpi testid="kpi-vagas-reservadas" label="Vagas reservadas" value={k.reservadas} tone="amber" icon={Bookmark} hint="Reservas manuais + situações que reservam" />
            <Kpi testid="kpi-vagas-disponiveis" label="Vagas disponíveis" value={k.disponiveis} tone="green" icon={CircleDot} hint="Autorizadas − ocupadas − reservadas" />
            <Kpi testid="kpi-servidores-ativos" label="Servidores ativos" value={k.servidores_ativos} icon={Users} hint={`${k.vinculos_total} vínculos (matrículas) no total`} />
            <Kpi testid="kpi-escolas" label="Escolas cadastradas" value={k.escolas} icon={School} />
            <Kpi testid="kpi-escolas-deficit" label="Escolas com déficit" value={k.escolas_deficit} tone="red" icon={TrendingDown} />
            <Kpi testid="kpi-escolas-excedente" label="Escolas com excedente" value={k.escolas_excedente} tone="violet" icon={TrendingUp} hint={`${k.excedentes} vínculo(s) excedente(s)`} />
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
            <Card title="Distribuição de vagas por escola" className="xl:col-span-12" testid="chart-por-escola">
              {escolas.length ? (
                <div className="h-[380px]"><ResponsiveContainer>
                  <BarChart data={escolas} margin={{ left: 0, right: 8, bottom: 70 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
                    <XAxis dataKey="nome" angle={-40} textAnchor="end" interval={0} tick={{ fontSize: 10 }} height={90} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend verticalAlign="top" height={30} />
                    <Bar dataKey="ocupadas" name="Ocupadas" stackId="a" fill={C.ocupadas} />
                    <Bar dataKey="reservadas" name="Reservadas" stackId="a" fill={C.reservadas} />
                    <Bar dataKey="disponiveis" name="Disponíveis" stackId="a" fill={C.disponiveis} />
                    <Bar dataKey="excedente" name="Excedente" fill={C.excedente} />
                  </BarChart>
                </ResponsiveContainer></div>
              ) : <Empty>Importe a relação de servidores e o quadro de distribuição.</Empty>}
            </Card>
            <Card title="Vagas por cargo (12 maiores)" className="xl:col-span-7" testid="chart-por-cargo">
              <div className="h-[380px]"><ResponsiveContainer>
                <BarChart data={cargos} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="nome" width={190} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="ocupadas" name="Ocupadas" fill={C.ocupadas} />
                  <Bar dataKey="base" name="Autorizadas" fill={C.base} />
                </BarChart>
              </ResponsiveContainer></div>
            </Card>
            <Card title="Vínculos por situação funcional" className="xl:col-span-5" testid="chart-por-situacao">
              <div className="h-[380px]"><ResponsiveContainer>
                <PieChart>
                  <Pie data={data.por_situacao} dataKey="servidores" nameKey="nome" innerRadius={70} outerRadius={120} paddingAngle={2}>
                    {data.por_situacao.map((_, i) => <Cell key={i} fill={PIE[i % PIE.length]} />)}
                  </Pie>
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                </PieChart>
              </ResponsiveContainer></div>
            </Card>
            <Card title="Turmas por etapa de ensino" className="xl:col-span-7" testid="chart-por-etapa">
              <div className="h-[300px]"><ResponsiveContainer>
                <BarChart data={data.por_etapa}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
                  <XAxis dataKey="etapa" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={50} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="turmas" name="Turmas" fill="#1E3E62" />
                  <Bar dataKey="profissionais_previstos" name="Profissionais previstos (regra)" fill="#D4AF37" />
                </BarChart>
              </ResponsiveContainer></div>
              {k.regras_definidas === 0 && <p className="text-xs text-slate-500 mt-2">Profissionais previstos aparecem após definir as regras em <Link className="underline" to="/regras">Regras e Situações</Link>.</p>}
            </Card>
            <Card title="Servidores ativos por função" className="xl:col-span-5" testid="chart-por-funcao">
              <div className="h-[300px]"><ResponsiveContainer>
                <BarChart data={data.por_funcao.slice(0, 10)} layout="vertical">
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="nome" width={170} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="servidores" name="Servidores" fill="#D4AF37" />
                </BarChart>
              </ResponsiveContainer></div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
