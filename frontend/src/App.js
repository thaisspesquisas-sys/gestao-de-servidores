import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Show, SignIn, SignUp, SignOutButton } from "@clerk/react";
import { Toaster } from "@/components/ui/sonner";
import ClerkAuthProvider from "@/components/auth/ClerkAuthProvider";
import { MeProvider, useMeState } from "@/context/MeContext";
import Layout from "@/components/Layout";
import { Loading } from "@/components/common";
import Dashboard from "@/pages/Dashboard";
import Importacao from "@/pages/Importacao";
import Servidores from "@/pages/Servidores";
import Distribuicao from "@/pages/Distribuicao";
import Correspondencia from "@/pages/Correspondencia";
import Vagas from "@/pages/Vagas";
import Reservas from "@/pages/Reservas";
import Regras from "@/pages/Regras";
import Escolas from "@/pages/Escolas";
import EscolaDetalhe from "@/pages/EscolaDetalhe";
import Assistente from "@/pages/Assistente";
import Relatorios from "@/pages/Relatorios";
import Auditoria from "@/pages/Auditoria";
import Usuarios from "@/pages/Usuarios";

const AuthShell = ({ children }) => (
  <div className="min-h-screen grid lg:grid-cols-2">
    <div className="hidden lg:flex flex-col justify-between bg-[#0B192C] text-white p-12 grid-bg relative overflow-hidden">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-lg bg-[#D4AF37] text-[#0B192C] grid place-items-center font-display font-extrabold">GIV</div>
        <span className="text-xs uppercase tracking-[0.25em] text-[#D4AF37]">Secretaria Municipal de Educação</span>
      </div>
      <div>
        <h1 className="text-4xl xl:text-5xl font-extrabold leading-tight">Gestão Inteligente<br />de Vagas – Educação</h1>
        <p className="text-slate-300 mt-5 max-w-md">Controle, dimensionamento e distribuição de servidores da Rede Municipal de Ensino.</p>
      </div>
      <p className="text-xs text-slate-400">Acesso restrito · Dados pessoais protegidos conforme a LGPD</p>
    </div>
    <div className="flex items-center justify-center p-6 bg-[#f6f8fb]">{children}</div>
  </div>
);

const Pending = () => (
  <AuthShell>
    <div className="max-w-sm text-center" data-testid="pending-approval">
      <h2 className="text-2xl font-bold text-[#0B192C]">Acesso aguardando aprovação</h2>
      <p className="text-sm text-slate-600 mt-3">Sua conta foi criada. Um administrador precisa liberar seu perfil de acesso antes que você possa consultar os dados.</p>
      <SignOutButton><button className="mt-6 px-4 py-2 rounded-md bg-[#0B192C] text-white text-sm" data-testid="pending-signout-button">Sair</button></SignOutButton>
    </div>
  </AuthShell>
);

const Gate = () => {
  const { me, loading, error } = useMeState();
  if (loading && !me) return <Loading label="Verificando acesso..." />;
  if (error && !me) return <div className="p-10 text-sm text-red-700">Erro ao verificar acesso: {error}</div>;
  if (me?.role === "pendente") return <Pending />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="importacao" element={<Importacao />} />
        <Route path="servidores" element={<Servidores />} />
        <Route path="distribuicao" element={<Distribuicao />} />
        <Route path="correspondencia" element={<Correspondencia />} />
        <Route path="vagas" element={<Vagas />} />
        <Route path="reservas" element={<Reservas />} />
        <Route path="regras" element={<Regras />} />
        <Route path="escolas" element={<Escolas />} />
        <Route path="escolas/:id" element={<EscolaDetalhe />} />
        <Route path="assistente" element={<Assistente />} />
        <Route path="relatorios" element={<Relatorios />} />
        <Route path="auditoria" element={<Auditoria />} />
        <Route path="usuarios" element={<Usuarios />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
};

const Protected = () => (
  <>
    <Show when="signed-in"><MeProvider><Gate /></MeProvider></Show>
    <Show when="signed-out"><Navigate to="/sign-in" replace /></Show>
  </>
);

export default function App() {
  return (
    <BrowserRouter>
      <ClerkAuthProvider>
        <Routes>
          <Route path="/sign-in/*" element={<AuthShell><SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" withSignUp /></AuthShell>} />
          <Route path="/sign-up/*" element={<AuthShell><SignUp routing="path" path="/sign-up" signInUrl="/sign-in" /></AuthShell>} />
          <Route path="/*" element={<Protected />} />
        </Routes>
      </ClerkAuthProvider>
      <Toaster richColors position="top-right" />
    </BrowserRouter>
  );
}
