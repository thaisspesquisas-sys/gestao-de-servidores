import { useState } from "react";
import { toast } from "sonner";
import { Check, Plus, Ban } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useApi, useFetch, errMsg } from "@/lib/api";
import { useMe } from "@/context/MeContext";
import { PageHeader, Loading, Badge, TableWrap, SelectF } from "@/components/common";

const STATUS = { pendente: "Aguardando validação", confirmado: "Confirmado", nao_escola: "Não é unidade escolar" };

const AliasRow = ({ a, escolas, isAdmin, onDone }) => {
  const api = useApi();
  const [sid, setSid] = useState(a.school_id || a.sugestao_id || "");
  const act = async (acao, extra = {}) => {
    try { await api("post", `/correspondencia/${a.id}/validar`, { acao, ...extra }); toast.success("Correspondência validada"); onDone(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <tr data-testid={`alias-row-${a.id}`}>
      <td className="text-xs">{a.exemplos.map((e) => <div key={e}>{e}</div>)}</td>
      <td className="num text-center">{a.vinculos}</td>
      <td><Badge kind={a.status}>{STATUS[a.status]}</Badge>{a.auto && a.status !== "pendente" && <div className="text-[10px] text-slate-500 mt-1">automático</div>}</td>
      <td className="text-xs">{a.escola || (a.sugestao ? <span className="text-amber-800">Sugestão: {a.sugestao} <span className="num">({Math.round(a.sugestao_score * 100)}%)</span></span> : "—")}</td>
      {isAdmin && (
        <td className="min-w-[340px]">
          <div className="flex flex-wrap gap-1.5 items-center">
            <SelectF className="w-56" value={sid} onChange={setSid} options={escolas} allLabel="Escolher escola" testid={`alias-select-${a.id}`} />
            <Button size="sm" variant="outline" disabled={!sid} onClick={() => act("vincular", { school_id: sid })} data-testid={`alias-link-${a.id}`}><Check className="h-3.5 w-3.5" /></Button>
            <Button size="sm" variant="outline" title="Criar nova unidade com este nome" onClick={() => act("nova_escola", { nome: a.exemplos[0] })} data-testid={`alias-new-${a.id}`}><Plus className="h-3.5 w-3.5" /></Button>
            <Button size="sm" variant="outline" title="Não é unidade escolar" onClick={() => act("nao_escola")} data-testid={`alias-notschool-${a.id}`}><Ban className="h-3.5 w-3.5" /></Button>
          </div>
        </td>
      )}
    </tr>
  );
};

const CargoRow = ({ c, isAdmin, onDone, cargos }) => {
  const api = useApi();
  const [v, setV] = useState(c.cargo_padrao);
  const salvar = async () => {
    try { await api("put", "/cargos", { alias: c.alias, cargo_padrao: v }); toast.success("Correspondência de cargo salva"); onDone(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <tr>
      <td className="text-xs">{c.alias}</td><td className="num text-center">{c.vinculos}</td>
      <td>{isAdmin ? (
        <div className="flex gap-1.5"><Input list="cargos-list" value={v} onChange={(e) => setV(e.target.value)} className="h-8 text-xs bg-white" data-testid={`cargo-input-${c.alias}`} />
          <Button size="sm" variant="outline" disabled={v === c.cargo_padrao} onClick={salvar} data-testid={`cargo-save-${c.alias}`}><Check className="h-3.5 w-3.5" /></Button></div>
      ) : <span className="text-xs">{c.cargo_padrao}</span>}</td>
    </tr>
  );
};

export default function Correspondencia() {
  const { isAdmin } = useMe();
  const [filtro, setFiltro] = useState("pendente");
  const al = useFetch("/correspondencia");
  const cg = useFetch("/cargos");
  const { data: meta, reload: rMeta } = useFetch("/meta");
  const escolas = (meta?.escolas || []).map((e) => ({ value: e.id, label: e.nome }));
  const lista = (al.data || []).filter((a) => !filtro || a.status === filtro);
  const pend = (al.data || []).filter((a) => a.status === "pendente").length;
  return (
    <div>
      <PageHeader eyebrow="Motor de cruzamento" title="Cruzamento & Correspondência" subtitle="Tabela de correspondência entre as diferentes grafias de nomes de escolas e cargos. Somente nomes idênticos após normalização são vinculados automaticamente; os demais exigem validação do administrador." />
      <Tabs defaultValue="escolas">
        <TabsList className="bg-white border"><TabsTrigger value="escolas" data-testid="tab-escolas">Escolas / Lotações {pend > 0 && <span className="ml-1.5 rounded-full bg-red-600 text-white text-[10px] px-1.5">{pend}</span>}</TabsTrigger>
          <TabsTrigger value="cargos" data-testid="tab-cargos">Cargos</TabsTrigger></TabsList>
        <TabsContent value="escolas">
          <div className="flex gap-3 my-4"><SelectF className="w-72" value={filtro} onChange={setFiltro} allLabel="Todos os status" testid="alias-status-filter"
            options={Object.entries(STATUS).map(([value, label]) => ({ value, label }))} /></div>
          {al.loading && !al.data ? <Loading /> : (
            <TableWrap testid="alias-table">
              <thead><tr><th>Nome(s) encontrado(s) nas planilhas</th><th>Vínculos</th><th>Status</th><th>Escola</th>{isAdmin && <th>Validação</th>}</tr></thead>
              <tbody>{lista.map((a) => <AliasRow key={a.id} a={a} escolas={escolas} isAdmin={isAdmin} onDone={() => { al.reload(); rMeta(); }} />)}</tbody>
            </TableWrap>
          )}
        </TabsContent>
        <TabsContent value="cargos">
          <p className="text-sm text-slate-600 my-4">Unifique grafias diferentes do mesmo cargo (ex.: "PROFESSOR II (1º AO 5º ANO)" e "PROFESSOR 1º AO 5º ANO") para que sejam contadas no mesmo controle de vagas.</p>
          <datalist id="cargos-list">{(meta?.cargos || []).map((c) => <option key={c} value={c} />)}</datalist>
          {cg.loading && !cg.data ? <Loading /> : (
            <TableWrap testid="cargo-table">
              <thead><tr><th>Cargo na planilha</th><th>Vínculos</th><th>Cargo padronizado (controle de vagas)</th></tr></thead>
              <tbody>{(cg.data || []).map((c) => <CargoRow key={c.alias} c={c} isAdmin={isAdmin} onDone={() => { cg.reload(); rMeta(); }} />)}</tbody>
            </TableWrap>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
