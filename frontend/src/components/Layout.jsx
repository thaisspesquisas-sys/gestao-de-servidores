import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { UserButton } from "@clerk/react";
import {
  LayoutDashboard, FileSpreadsheet, Users, Table, GitCompare, BookmarkCheck, Sliders, Building2, Bot, FileText,
  ShieldAlert, UserCheck, Menu, ClipboardList,
} from "lucide-react";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { useMe } from "@/context/MeContext";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, id: "dashboard" },
  { to: "/escolas", label: "Consulta por Escola", icon: Building2, id: "escolas" },
  { to: "/vagas", label: "Controle de Vagas", icon: ClipboardList, id: "vagas" },
  { to: "/reservas", label: "Reservas", icon: BookmarkCheck, id: "reservas" },
  { to: "/servidores", label: "Servidores", icon: Users, id: "servidores" },
  { to: "/distribuicao", label: "Quadro de Distribuição", icon: Table, id: "distribuicao" },
  { to: "/assistente", label: "Assistente", icon: Bot, id: "assistente" },
  { to: "/relatorios", label: "Relatórios", icon: FileText, id: "relatorios" },
  { to: "/importacao", label: "Central de Importação", icon: FileSpreadsheet, id: "importacao", admin: true },
  { to: "/correspondencia", label: "Cruzamento & Correspondência", icon: GitCompare, id: "correspondencia" },
  { to: "/regras", label: "Regras e Situações", icon: Sliders, id: "regras" },
  { to: "/auditoria", label: "Auditoria", icon: ShieldAlert, id: "auditoria", gestao: true },
  { to: "/usuarios", label: "Usuários e Permissões", icon: UserCheck, id: "usuarios", admin: true },
];

const Nav = ({ onNavigate }) => {
  const { isAdmin, canGestao, me } = useMe();
  return (
    <div className="flex flex-col h-full bg-[#0B192C] text-slate-300">
      <div className="px-5 pt-6 pb-5 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-[#D4AF37] text-[#0B192C] grid place-items-center font-display font-extrabold text-sm">GIV</div>
          <div>
            <div className="font-display font-bold text-white text-sm leading-tight">Gestão Inteligente de Vagas</div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-[#D4AF37] mt-0.5">Educação</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-0.5">
        {NAV.filter((n) => (!n.admin || isAdmin) && (!n.gestao || canGestao)).map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === "/"}
            onClick={onNavigate}
            data-testid={`sidebar-link-${n.id}`}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2 text-[13px] transition-colors duration-150 border-l-2 ${
                isActive ? "bg-white/10 text-white border-[#D4AF37]" : "border-transparent hover:bg-white/5 hover:text-white"
              }`
            }
          >
            <n.icon className="h-4 w-4 shrink-0" />
            {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 border-t border-white/10 text-[11px]">
        <div className="text-slate-400">Perfil de acesso</div>
        <div className="text-[#D4AF37] font-semibold" data-testid="sidebar-role">{me?.role_label}</div>
      </div>
    </div>
  );
};

export default function Layout() {
  const [open, setOpen] = useState(false);
  const { me } = useMe();
  return (
    <div className="min-h-screen flex">
      <aside className="hidden lg:block w-64 shrink-0 fixed inset-y-0 left-0 z-30">
        <Nav />
      </aside>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="p-0 w-72 border-0">
          <Nav onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
      <div className="flex-1 lg:ml-64 min-w-0">
        <header className="sticky top-0 z-20 bg-white/85 backdrop-blur-md border-b border-slate-200">
          <div className="flex items-center justify-between px-4 sm:px-8 h-14">
            <div className="flex items-center gap-3">
              <button className="lg:hidden p-2 rounded-md hover:bg-slate-100" onClick={() => setOpen(true)} data-testid="mobile-menu-button">
                <Menu className="h-5 w-5" />
              </button>
              <div className="text-xs text-slate-500 hidden sm:block">Controle, dimensionamento e distribuição de servidores da Rede Municipal de Ensino</div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-600 hidden md:inline" data-testid="header-user-email">{me?.email}</span>
              <UserButton />
            </div>
          </div>
        </header>
        <main className="px-4 sm:px-8 py-8 max-w-[1600px]">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
