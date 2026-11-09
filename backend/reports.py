import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from engine import compute, agg_por

NAVY = "0B192C"
GOLD = "D4AF37"
SISTEMA = "GESTÃO INTELIGENTE DE VAGAS – EDUCAÇÃO"

TIPOS = {
    "geral": "Quadro geral de vagas da rede",
    "por_escola": "Quadro de vagas por escola",
    "por_cargo": "Quadro de vagas por cargo",
    "por_funcao": "Quadro de vagas por função",
    "ocupadas": "Vagas ocupadas",
    "disponiveis": "Vagas disponíveis",
    "reservadas": "Vagas reservadas",
    "deficit_excedente": "Déficit e excedente de profissionais",
    "servidores_unidade": "Relação de servidores por unidade",
    "historico": "Histórico de alterações",
}

V = lambda x: "—" if x is None else x
COLS_AGG = ["Base", "Autorizadas (oficial)", "Previsto (regra)", "Ocupadas", "Reservadas", "Disponíveis", "Excedente"]


def _agg_rows(items):
    return [[i["nome"], i["base"], i["autorizadas"], i["previsto"], i["ocupadas"], i["reservadas"], i["disponiveis"], i["excedente"]] for i in items]


def _linha(r):
    return [r["escola"], r["cargo"], r["funcao"] or "—", V(r["base"]), V(r["autorizadas"]), V(r["previsto"]),
            r["ocupadas"], r["reservadas"], V(r["disponiveis"]), V(r["excedente"])]


COLS_LINHA = ["Escola", "Cargo", "Função", "Base", "Autorizadas", "Previsto", "Ocupadas", "Reservadas", "Disponíveis", "Excedente"]


async def build(tipo: str, st: dict, f: dict, auditoria: list):
    res = compute(st, f)
    linhas = res["linhas"]
    if tipo == "geral":
        tot = {k: sum(r[k] or 0 for r in linhas) for k in ("base", "autorizadas", "previsto", "ocupadas", "reservadas", "disponiveis", "excedente")}
        rows = _agg_rows(agg_por(linhas, "cargo")) + [["TOTAL DA REDE", tot["base"], tot["autorizadas"], tot["previsto"], tot["ocupadas"],
                                                       tot["reservadas"], tot["disponiveis"], tot["excedente"]]]
        return ["Cargo"] + COLS_AGG, rows
    if tipo == "por_escola":
        return ["Escola"] + COLS_AGG, _agg_rows(agg_por(linhas, "escola"))
    if tipo == "por_cargo":
        return COLS_LINHA, [_linha(r) for r in sorted(linhas, key=lambda r: (r["cargo"], r["escola"]))]
    if tipo == "por_funcao":
        return ["Função"] + COLS_AGG, _agg_rows(agg_por([{**r, "funcao": r["funcao"] or "(SEM FUNÇÃO NO QUADRO)"} for r in linhas], "funcao"))
    if tipo == "ocupadas":
        return COLS_LINHA, [_linha(r) for r in linhas if r["ocupadas"]]
    if tipo == "disponiveis":
        return COLS_LINHA, [_linha(r) for r in linhas if r["disponiveis"]]
    if tipo == "reservadas":
        return COLS_LINHA, [_linha(r) for r in linhas if r["reservadas"]]
    if tipo == "deficit_excedente":
        return ["Escola"] + COLS_AGG, _agg_rows([e for e in agg_por(linhas, "escola") if e["disponiveis"] or e["excedente"]])
    if tipo == "servidores_unidade":
        vs = sorted(res["vinculos"], key=lambda v: (v["escola"] or "~ " + (v.get("lotacao") or ""), v["nome"]))
        return (["Unidade", "Matrícula", "Nome", "Cargo", "Função", "Vínculo", "C.H.", "Situação"],
                [[v["escola"] or f"(não identificada) {v.get('lotacao') or ''}", v["matricula"], v["nome"], v["cargo_padrao"],
                  v.get("funcao") or "", v.get("vinculo") or "", v.get("carga_horaria") or "", v["situacao_nome"]] for v in vs])
    if tipo == "historico":
        return (["Data/hora", "Usuário", "Ação", "Entidade", "Descrição"],
                [[a["ts"][:19].replace("T", " "), a.get("usuario") or "", a["acao"], a["entidade"], a.get("descricao") or ""] for a in auditoria])
    raise KeyError(tipo)


def to_xlsx(titulo, subtitulo, cols, rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]
    ws.append([SISTEMA])
    ws.append([titulo])
    ws.append([subtitulo])
    ws.append([])
    ws.append(cols)
    ws["A1"].font = Font(bold=True, color=NAVY, size=12)
    ws["A2"].font = Font(bold=True, size=14)
    for c in ws[5]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(wrap_text=True)
    for r in rows:
        ws.append(list(r))
    for i, _ in enumerate(cols, start=1):
        ws.column_dimensions[ws.cell(5, i).column_letter].width = 40 if i == 1 else 18
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_pdf(titulo, subtitulo, cols, rows) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1.2 * cm, rightMargin=1.2 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
                            title=titulo)
    ss = getSampleStyleSheet()
    cell = ss["BodyText"].clone("c", fontSize=7, leading=8.5)
    head = ss["BodyText"].clone("h", fontSize=7.5, leading=9, textColor=colors.white, fontName="Helvetica-Bold")
    data = [[Paragraph(str(c), head) for c in cols]] + [[Paragraph(str(V(x)), cell) for x in r] for r in rows]
    if not rows:
        data.append([Paragraph("Nenhum registro encontrado para os filtros selecionados.", cell)] + [""] * (len(cols) - 1))
    width = landscape(A4)[0] - 2.4 * cm
    first = 0.3 if len(cols) > 6 else 0.4
    cw = [width * first] + [width * (1 - first) / (len(cols) - 1)] * (len(cols) - 1)
    t = Table(data, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#" + NAVY)),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, colors.HexColor("#" + GOLD)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story = [Paragraph(f"<font color='#{NAVY}'><b>{SISTEMA}</b></font>", ss["Heading4"]),
             Paragraph(titulo, ss["Heading2"]), Paragraph(subtitulo, ss["BodyText"]), Spacer(1, 8), t]
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _footer(canvas, doc):
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(1.2 * cm, 0.7 * cm, f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')} — dados importados e validados no sistema")
    canvas.drawRightString(landscape(A4)[0] - 1.2 * cm, 0.7 * cm, f"Página {doc.page}")
