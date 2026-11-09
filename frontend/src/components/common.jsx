import { Loader2 } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fmt } from "@/lib/api";

export const PageHeader = ({ title, subtitle, actions, eyebrow }) => (
  <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between mb-8 fade-up">
    <div>
      {eyebrow && <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#B89628] mb-2">{eyebrow}</div>}
      <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight text-[#0B192C]" data-testid="page-title">{title}</h1>
      {subtitle && <p className="text-sm text-slate-500 mt-2 max-w-2xl">{subtitle}</p>}
    </div>
    {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
  </div>
);

const TONES = {
  navy: "text-[#0B192C]",
  blue: "text-blue-700",
  green: "text-emerald-700",
  amber: "text-amber-700",
  red: "text-red-700",
  violet: "text-violet-700",
};

export const Kpi = ({ label, value, tone = "navy", hint, testid, icon: Icon }) => (
  <div className="gold-line bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow duration-200 overflow-hidden" data-testid={testid}>
    <div className="flex items-start justify-between gap-2">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
      {Icon && <Icon className="h-4 w-4 text-[#D4AF37]" />}
    </div>
    <div className={`num text-3xl font-semibold mt-3 ${TONES[tone]}`} data-testid={testid ? `${testid}-value` : undefined}>{fmt(value)}</div>
    {hint && <div className="text-xs text-slate-500 mt-1.5">{hint}</div>}
  </div>
);

export const Card = ({ title, children, actions, className = "", testid }) => (
  <section className={`bg-white border border-slate-200 rounded-xl shadow-sm ${className}`} data-testid={testid}>
    {title && (
      <div className="flex items-center justify-between gap-2 px-5 pt-5 pb-3">
        <h3 className="section-title text-base font-bold text-[#0B192C]">{title}</h3>
        {actions}
      </div>
    )}
    <div className="px-5 pb-5">{children}</div>
  </section>
);

export const SelectF = ({ value, onChange, options, placeholder, testid, allLabel = "Todos", className = "w-full", noAll }) => (
  <Select value={value || "__all"} onValueChange={(v) => onChange(v === "__all" ? "" : v)}>
    <SelectTrigger className={`bg-white ${className}`} data-testid={testid}>
      <SelectValue placeholder={placeholder} />
    </SelectTrigger>
    <SelectContent className="bg-white max-h-80">
      {!noAll && <SelectItem value="__all">{allLabel}</SelectItem>}
      {options.map((o) => (
        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
      ))}
    </SelectContent>
  </Select>
);

export const FilterBar = ({ meta, value, onChange, fields = ["escola", "cargo", "funcao", "vinculo", "situacao"] }) => {
  if (!meta) return null;
  const opts = {
    escola: meta.escolas.map((e) => ({ value: e.id, label: e.nome })),
    cargo: meta.cargos.map((c) => ({ value: c, label: c })),
    funcao: meta.funcoes.map((c) => ({ value: c, label: c })),
    vinculo: meta.vinculos.map((c) => ({ value: c, label: c })),
    situacao: meta.situacoes.map((s) => ({ value: s.codigo, label: s.nome })),
  };
  const labels = { escola: "Todas as escolas", cargo: "Todos os cargos", funcao: "Todas as funções", vinculo: "Todos os vínculos", situacao: "Todas as situações" };
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-6" data-testid="filter-bar">
      {fields.map((f) => (
        <SelectF key={f} value={value[f]} onChange={(v) => onChange({ ...value, [f]: v })} options={opts[f]} allLabel={labels[f]} placeholder={labels[f]} testid={`filter-${f}-select`} />
      ))}
    </div>
  );
};

export const Loading = ({ label = "Carregando..." }) => (
  <div className="flex items-center gap-2 text-slate-500 text-sm py-10 justify-center" data-testid="loading">
    <Loader2 className="h-4 w-4 animate-spin" /> {label}
  </div>
);

export const Empty = ({ children }) => (
  <div className="text-center text-sm text-slate-500 py-10 border border-dashed border-slate-300 rounded-lg bg-slate-50/60" data-testid="empty-state">{children}</div>
);

const BADGE = {
  ocupa: "bg-blue-50 text-blue-700 border-blue-200",
  libera: "bg-emerald-50 text-emerald-700 border-emerald-200",
  reserva: "bg-amber-50 text-amber-800 border-amber-200",
  pendente: "bg-red-50 text-red-700 border-red-200",
  ativa: "bg-amber-50 text-amber-800 border-amber-200",
  cancelada: "bg-slate-100 text-slate-600 border-slate-200",
  efetivada: "bg-emerald-50 text-emerald-700 border-emerald-200",
  confirmado: "bg-emerald-50 text-emerald-700 border-emerald-200",
  nao_escola: "bg-slate-100 text-slate-600 border-slate-200",
  oficial: "bg-[#FDF8EA] text-[#8a6d12] border-[#e8d48f]",
  regra: "bg-violet-50 text-violet-700 border-violet-200",
};

export const Badge = ({ kind, children, testid }) => (
  <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium whitespace-nowrap ${BADGE[kind] || "bg-slate-100 text-slate-700 border-slate-200"}`} data-testid={testid}>
    {children}
  </span>
);

export const TableWrap = ({ children, testid, maxH = "70vh" }) => (
  <div className="overflow-auto rounded-lg border border-slate-200 bg-white" style={{ maxHeight: maxH }} data-testid={testid}>
    <table className="table-dense w-full text-left border-collapse">{children}</table>
  </div>
);
