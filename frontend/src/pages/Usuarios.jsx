import { toast } from "sonner";
import { useApi, useFetch, errMsg, fmtDate } from "@/lib/api";
import { PageHeader, Loading, TableWrap, SelectF, Card } from "@/components/common";

const PERFIS = [
  ["Administrador", "Acesso completo: importações, configurações, regras, usuários e autorizações."],
  ["Gestor da Secretaria", "Consulta geral, relatórios, auditoria e movimentações autorizadas (efetivar/cancelar reservas)."],
  ["Operador", "Cadastro, atualização e conferência de servidores, turmas e reservas."],
  ["Consulta", "Somente visualização das informações autorizadas (CPF mascarado)."],
  ["Aguardando aprovação", "Conta criada sem acesso aos dados até liberação do administrador."],
];

export default function Usuarios() {
  const api = useApi();
  const { data, loading, reload } = useFetch("/users");
  const mudar = async (u, role) => {
    try { await api("patch", `/users/${u.user_id}/role`, { role }); toast.success("Perfil atualizado"); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div>
      <PageHeader eyebrow="Controle de acesso · LGPD" title="Usuários e Permissões" subtitle="Novos usuários criam a própria conta pela tela de login e ficam aguardando aprovação até que um administrador defina o perfil." />
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        <div className="xl:col-span-8">
          {loading && !data ? <Loading /> : (
            <TableWrap testid="usuarios-table">
              <thead><tr><th>E-mail</th><th>Nome</th><th>Desde</th><th>Perfil</th></tr></thead>
              <tbody>{data?.users.map((u) => (
                <tr key={u.user_id} data-testid={`usuario-row-${u.email}`}>
                  <td className="text-sm">{u.email}</td><td className="text-sm">{u.nome}</td><td className="text-xs">{fmtDate(u.created_at)}</td>
                  <td className="w-64"><SelectF noAll value={u.role} onChange={(r) => mudar(u, r)} options={data.roles} testid={`usuario-role-${u.email}`} /></td>
                </tr>))}</tbody>
            </TableWrap>
          )}
        </div>
        <Card title="Níveis de acesso" className="xl:col-span-4">
          <ul className="space-y-3">{PERFIS.map(([p, d]) => <li key={p}><div className="font-semibold text-sm text-[#0B192C]">{p}</div><div className="text-xs text-slate-600">{d}</div></li>)}</ul>
        </Card>
      </div>
    </div>
  );
}
