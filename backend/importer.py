import csv
import io
import re
from collections import defaultdict
from datetime import datetime, date

import openpyxl
import pdfplumber
import xlrd

from core import db, new_id, now_iso, norm_text, norm_school, clean, audit, ETAPAS
from engine import cargo_key, similarity, vaga_key

CAMPOS = {
    "servidores": {
        "matricula": ["MAT", "MAT.", "MATRICULA", "MATRICULA FUNCIONAL"],
        "nome": ["SERVIDORES", "SERVIDOR", "NOME", "NOME COMPLETO", "NOME DO SERVIDOR"],
        "cpf": ["CPF"], "cargo": ["CARGO"], "funcao": ["FUNCAO"],
        "lotacao": ["LOTACAO", "ULTIMA LOTACAO", "LOTACAO ATUAL", "UNIDADE DE LOTACAO"],
        "secretaria": ["SECRETARIA", "SECRETARIA DE ORIGEM"],
        "vinculo": ["VINCULO", "TIPO DE CONTRATO", "TIPO DE VINCULO"],
        "carga_horaria": ["C.H.", "CH", "C.H", "CARGA HORARIA"],
        "admissao": ["ADMISSAO", "DATA DE ADMISSAO", "DATA ADMISSAO"],
        "situacao": ["SITUACAO", "SITUACAO FUNCIONAL"],
        "obs": ["OBS", "OBS.", "OBSERVACAO", "OBSERVACOES"],
        "regencia": ["REGENCIA"], "nomeacao": ["NOMEACAO"],
        "data_desligamento": ["APOSENTADORIA", "DATA DA EXONERACAO", "DATA EXONERACAO", "DATA DE DESLIGAMENTO"],
        "tipo_desligamento": ["TIPO DE APOSENTADORIA", "TIPO DE DESLIGAMENTO"],
    },
    "distribuicao": {"escola": ["ESCOLA", "UNIDADE", "NOME DA ESCOLA", "UNIDADE ESCOLAR"],
                     **{e: [norm_text(e)] for e in ETAPAS}, "total": ["TOTAL"]},
    "quadro": {"escola": ["ESCOLA", "UNIDADE", "LOTACAO", "UNIDADE ESCOLAR"], "cargo": ["CARGO"], "funcao": ["FUNCAO"],
               "quantidade": ["QUANTIDADE", "AUTORIZADAS", "VAGAS AUTORIZADAS", "VAGAS", "QTD", "QUANTITATIVO"]},
}
OBRIGATORIOS = {"servidores": ["matricula", "nome", "cargo"], "distribuicao": ["escola"],
                "quadro": ["escola", "cargo", "quantidade"]}
NAO_ESCOLA = ["PERMUTA", "CESSAO", "CESSA0", "CEDID", "LICENCA", "VACANCIA", "APOSENTAD", "EXONERAD"]


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _finish(rows):
    rows = [r for r in rows if any(r)]
    width = max((max(i for i, c in enumerate(r) if c) + 1 for r in rows), default=0)
    return [(r + [""] * width)[:width] for r in rows]


def read_sheets(filename: str, data: bytes):
    ext = filename.lower().rsplit(".", 1)[-1]
    out = []
    if ext in ("xlsx", "xlsm"):
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows, empty = [], 0
            for r in ws.iter_rows(values_only=True):
                vals = [_cell(c) for c in r]
                if any(vals):
                    rows.append(vals)
                    empty = 0
                else:
                    empty += 1
                    if empty > 300:
                        break
            out.append((ws.title, _finish(rows)))
    elif ext == "xls":
        book = xlrd.open_workbook(file_contents=data)
        for sh in book.sheets():
            rows = []
            for i in range(sh.nrows):
                vals = []
                for c in sh.row(i):
                    if c.ctype == xlrd.XL_CELL_DATE:
                        vals.append(xlrd.xldate_as_datetime(c.value, book.datemode).date().isoformat())
                    else:
                        vals.append(_cell(c.value))
                rows.append(vals)
            out.append((sh.name, _finish(rows)))
    elif ext in ("csv", "txt"):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        try:
            dialect = csv.Sniffer().sniff(text[:5000], delimiters=";,\t|")
        except csv.Error:
            dialect = csv.excel
        out.append(("CSV", _finish([[c.strip() for c in r] for r in csv.reader(io.StringIO(text), dialect)])))
    elif ext == "pdf":
        rows = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    for t in tables:
                        rows += [[_cell(c).replace("\n", " ") for c in r] for r in t]
                else:
                    for line in (page.extract_text() or "").splitlines():
                        rows.append([p.strip() for p in re.split(r"\s{2,}", line)])
        out.append(("PDF", _finish(rows)))
    else:
        raise ValueError("Formato não suportado. Use XLSX, XLS, CSV ou PDF.")
    return out


def _match_field(header: str, categoria: str):
    h = norm_text(header).rstrip(":")
    for campo, sins in CAMPOS[categoria].items():
        if h in sins:
            return campo
    for campo, sins in CAMPOS[categoria].items():
        if any(len(s) >= 5 and s in h for s in sins):
            return campo
    return None


def detect(sheet_name: str, rows):
    best = {"header_row": 0, "categoria": "ignorar", "mapping": {}, "score": 0}
    for i, r in enumerate(rows[:15]):
        for cat in CAMPOS:
            mapping = {}
            for j, h in enumerate(r):
                campo = _match_field(h, cat) if h else None
                if campo and campo not in mapping:
                    mapping[campo] = j
            score = len(mapping) + (2 if all(k in mapping for k in OBRIGATORIOS[cat]) else 0)
            if cat == "distribuicao" and sum(1 for e in ETAPAS if e in mapping) < 3:
                score = 0
            if score > best["score"]:
                best = {"header_row": i, "categoria": cat, "mapping": mapping, "score": score}
    if best["score"] < 3:
        best["categoria"] = "ignorar"
    n = norm_text(sheet_name)
    sit = "auto"
    for k, v in [("APOSENTAD", "aposentado"), ("EXONERAD", "exonerado"), ("CEDIDOS DE OUTRA", "recebido_cessao"),
                 ("RECEBID", "recebido_cessao"), ("DESVIAD", "desviado"), ("PERMUTA", "permuta")]:
        if k in n:
            sit = v
    best["situacao_padrao"] = sit
    return best


def detect_situacao(lotacao="", obs="", vinculo="", secretaria=""):
    lot, ob, vin, sec = norm_text(lotacao), norm_text(obs), norm_text(vinculo), norm_text(secretaria)
    for t, origem in ((lot, lotacao), (ob, obs)):
        if "APOSENTAD" in t:
            return "aposentado", origem
        if "EXONERAD" in t:
            return "exonerado", origem
        if "VACANCIA" in t:
            return "vacancia", origem
        if "SEM VENC" in t or re.search(r"\bLSV\b", t):
            return "lsv", origem
        if "PERMUTA" in t:
            return "permuta", origem
        if "CESSAO" in t or "CESSA0" in t or "CEDID" in t:
            return "cedido", origem
        if "LICENCA" in t or "AFASTAD" in t or "AFASTAMENTO" in t:
            return "licenca", origem
        if "DESVIAD" in t or "READAPTAD" in t:
            return "desviado", origem
    if re.search(r"\bCEDID[AO]S? (DA|DE|DO)\b", sec):
        return "recebido_cessao", secretaria
    if "CONTRATO" in vin or "TEMPORARIO" in vin:
        return "contrato_temporario", vinculo
    return "ativo", ""


def _mat(v: str) -> str:
    return re.sub(r"\s+", "", v or "").strip()


def _int(v):
    v = (v or "").strip()
    if not v:
        return 0
    try:
        f = float(v.replace(",", "."))
    except ValueError:
        return None
    return int(f) if f >= 0 and f.is_integer() else None


def build_records(cfg: dict, rows, situ_codes: set):
    cat, hr, mp = cfg["categoria"], int(cfg.get("header_row", 0)), cfg.get("mapping") or {}
    mp = {k: int(v) for k, v in mp.items() if v not in (None, "", -1, "-1")}
    recs, erros = [], []
    falt = [k for k in OBRIGATORIOS[cat] if k not in mp]
    if falt:
        return [], [{"linha": 0, "mensagem": f"Coluna obrigatória não mapeada: {', '.join(falt)}"}]
    for i, r in enumerate(rows[hr + 1:], start=hr + 2):
        get = lambda k: clean(r[mp[k]]) if k in mp and mp[k] < len(r) else ""
        if cat == "servidores":
            rec = {k: get(k) for k in mp}
            rec["matricula"] = _mat(rec.get("matricula"))
            if not rec["matricula"] and not rec.get("nome"):
                continue
            if norm_text(rec.get("nome")) in ("SERVIDOR", "SERVIDORES", "NOME"):
                continue
            if not rec["matricula"]:
                erros.append({"linha": i, "mensagem": f"Sem matrícula (identificador obrigatório): {rec.get('nome')}"})
                continue
            if not rec.get("nome"):
                erros.append({"linha": i, "mensagem": f"Matrícula {rec['matricula']} sem nome"})
                continue
            if rec.get("situacao"):
                code = norm_text(rec["situacao"]).lower().replace(" ", "_")
                sit, origem = (code, rec["situacao"]) if code in situ_codes else detect_situacao(rec["situacao"])
            elif cfg.get("situacao_padrao") and cfg["situacao_padrao"] != "auto":
                sit, origem = cfg["situacao_padrao"], f"Aba/arquivo: {cfg.get('sheet')}"
            else:
                sit, origem = detect_situacao(rec.get("lotacao"), rec.get("obs"), rec.get("vinculo"), rec.get("secretaria"))
            rec["situacao"], rec["situacao_detalhe"] = sit, origem
            recs.append((i, rec))
        elif cat == "distribuicao":
            nome = get("escola")
            if not nome or norm_text(nome) in ("TOTAL", "TOTAL GERAL", "ESCOLA"):
                continue
            etapas, bad = {}, False
            for e in ETAPAS:
                v = _int(get(e))
                if v is None:
                    erros.append({"linha": i, "mensagem": f"{nome}: valor inválido em {e}"})
                    bad = True
                etapas[e] = v or 0
            if bad:
                continue
            total = sum(etapas.values())
            inf = _int(get("total")) if "total" in mp else None
            if inf not in (None, 0) and inf != total:
                erros.append({"linha": i, "mensagem": f"{nome}: TOTAL informado ({inf}) difere da soma das etapas ({total}); usada a soma", "aviso": True})
            recs.append((i, {"escola": nome, "etapas": etapas, "total": total}))
        elif cat == "quadro":
            nome, cargo, q = get("escola"), get("cargo"), _int(get("quantidade"))
            if not nome and not cargo:
                continue
            if q is None or not cargo:
                erros.append({"linha": i, "mensagem": f"{nome}: cargo ou quantidade inválidos"})
                continue
            recs.append((i, {"escola": nome, "cargo": cargo, "funcao": get("funcao"), "quantidade": q}))
    return recs, erros


async def _school_index():
    schools = {s["id"]: s async for s in db.schools.find({"arquivada": {"$ne": True}}, {"_id": 0})}
    aliases = {a["alias_norm"]: a async for a in db.school_aliases.find({}, {"_id": 0})}
    by_norm = {norm_school(s["nome"]): sid for sid, s in schools.items()}
    return schools, aliases, by_norm


def _resolve(nome, aliases, by_norm):
    n = norm_school(nome)
    a = aliases.get(n)
    if a and a["status"] == "confirmado" and a.get("school_id"):
        return a["school_id"]
    return by_norm.get(n)


async def ensure_aliases(nomes):
    schools, aliases, by_norm = await _school_index()
    for nome in {n for n in nomes if clean(n)}:
        n = norm_school(nome)
        if not n:
            continue
        if n in aliases:
            if clean(nome) not in aliases[n].get("exemplos", []):
                await db.school_aliases.update_one({"alias_norm": n}, {"$addToSet": {"exemplos": clean(nome)}})
            continue
        doc = {"id": new_id(), "alias_norm": n, "exemplos": [clean(nome)], "school_id": None, "auto": True,
               "created_at": now_iso(), "sugestao_id": None, "sugestao_score": 0}
        if n in by_norm:
            doc.update(status="confirmado", school_id=by_norm[n])
        elif any(k in norm_text(nome) for k in NAO_ESCOLA):
            doc["status"] = "nao_escola"
        else:
            doc["status"] = "pendente"
        aliases[n] = doc
        await db.school_aliases.insert_one({**doc})
    await refresh_suggestions()


async def refresh_suggestions():
    schools, aliases, by_norm = await _school_index()
    for a in aliases.values():
        if a["status"] != "pendente":
            continue
        if a["alias_norm"] in by_norm:
            await db.school_aliases.update_one({"id": a["id"]}, {"$set": {"status": "confirmado", "school_id": by_norm[a["alias_norm"]]}})
            continue
        best, score = None, 0
        for sid, s in schools.items():
            sc = similarity(a["alias_norm"], norm_school(s["nome"]))
            if sc > score:
                best, score = sid, sc
        await db.school_aliases.update_one({"id": a["id"]}, {"$set": {"sugestao_id": best if score >= 0.5 else None, "sugestao_score": score}})


async def process(imp: dict, sheets: dict, cfgs: list, commit: bool, member: dict) -> dict:
    situ_codes = {s["codigo"] async for s in db.situacoes.find({}, {"codigo": 1})}
    schools, aliases, by_norm = await _school_index()
    existing = [s async for s in db.servidores.find({}, {"_id": 0})]
    by_mat = defaultdict(list)
    for s in existing:
        by_mat[s["matricula"]].append(s)
    dist = {d["school_id"]: d async for d in db.distribuicao.find({}, {"_id": 0})}
    quadro = {(q["school_id"], cargo_key(q["cargo"]), cargo_key(q.get("funcao"))): q async for q in db.quadro.find({}, {"_id": 0})}
    touched, novas_escolas, result = set(), {}, []

    for cfg in cfgs:
        if cfg.get("categoria") in (None, "ignorar") or cfg["sheet"] not in sheets:
            continue
        recs, erros = build_records(cfg, sheets[cfg["sheet"]], situ_codes)
        res = {"sheet": cfg["sheet"], "categoria": cfg["categoria"], "lidos": len(recs), "novos": 0, "alterados": 0,
               "sem_alteracao": 0, "erros": erros, "amostra_novos": [], "amostra_alterados": [], "escolas_pendentes": []}
        if cfg["categoria"] == "servidores":
            lot_pend = set()
            for linha, rec in recs:
                cands = by_mat.get(rec["matricula"], [])
                match = next((c for c in cands if cargo_key(c.get("cargo")) == cargo_key(rec.get("cargo"))), None)
                if not match and len(cands) == 1 and cands[0]["id"] not in touched:
                    match = cands[0]
                if rec.get("lotacao") and _resolve(rec["lotacao"], aliases, by_norm) is None:
                    a = aliases.get(norm_school(rec["lotacao"]))
                    if not a or a["status"] == "pendente":
                        lot_pend.add(rec["lotacao"])
                if match:
                    diff = {k: {"antes": match.get(k) or "", "depois": v} for k, v in rec.items()
                            if v and (match.get(k) or "") != v and k != "situacao_detalhe" and not (k == "nome" and match.get(k))}
                    if diff:
                        res["alterados"] += 1
                        if len(res["amostra_alterados"]) < 50:
                            res["amostra_alterados"].append({"linha": linha, "matricula": rec["matricula"], "nome": match["nome"], "diff": diff})
                        antes = {k: match.get(k) for k in diff}
                        match.update({k: d["depois"] for k, d in diff.items()})
                        match["situacao_detalhe"] = rec.get("situacao_detalhe", match.get("situacao_detalhe"))
                        if commit:
                            await db.servidores.update_one({"id": match["id"]}, {"$set": {**{k: d["depois"] for k, d in diff.items()},
                                                            "situacao_detalhe": match["situacao_detalhe"], "updated_at": now_iso()}})
                            acao = ("mudanca_lotacao" if "lotacao" in diff else "mudanca_cargo" if "cargo" in diff
                                    else "mudanca_situacao" if "situacao" in diff else "alteracao_servidor")
                            await audit(member, acao, "servidor", match["id"], antes, {k: d["depois"] for k, d in diff.items()},
                                        descricao=f"Importação {imp['filename']} / {cfg['sheet']} — {match['nome']} ({match['matricula']})")
                    else:
                        res["sem_alteracao"] += 1
                    touched.add(match["id"])
                else:
                    doc = {"id": new_id(), "cpf": "", "funcao": "", "lotacao": "", "secretaria": "", "vinculo": "",
                           "carga_horaria": "", "admissao": "", "obs": "", **rec, "import_id": imp["id"],
                           "created_at": now_iso(), "updated_at": now_iso(), "arquivado": False}
                    by_mat[rec["matricula"]].append(doc)
                    touched.add(doc["id"])
                    res["novos"] += 1
                    if len(res["amostra_novos"]) < 50:
                        res["amostra_novos"].append({"linha": linha, **{k: rec.get(k, "") for k in ("matricula", "nome", "cargo", "lotacao", "situacao")}})
                    if commit:
                        await db.servidores.insert_one({**doc})
            res["escolas_pendentes"] = sorted(lot_pend)
            if commit:
                await ensure_aliases([r.get("lotacao") for _, r in recs])
                schools, aliases, by_norm = await _school_index()
        elif cfg["categoria"] == "distribuicao":
            for linha, rec in recs:
                sid = _resolve(rec["escola"], aliases, by_norm) or novas_escolas.get(norm_school(rec["escola"]))
                if not sid:
                    sid = new_id()
                    novas_escolas[norm_school(rec["escola"])] = sid
                    res["amostra_novos"].append({"linha": linha, "escola": rec["escola"], "total": rec["total"], "obs": "nova unidade"})
                    res["novos"] += 1
                    if commit:
                        await db.schools.insert_one({"id": sid, "nome": rec["escola"], "origem": "distribuicao", "created_at": now_iso()})
                        n = norm_school(rec["escola"])
                        await db.school_aliases.update_one({"alias_norm": n}, {"$set": {"status": "confirmado", "school_id": sid},
                                                           "$setOnInsert": {"id": new_id(), "exemplos": [rec["escola"]], "auto": True, "created_at": now_iso()}}, upsert=True)
                        await audit(member, "nova_unidade", "escola", sid, None, {"nome": rec["escola"]}, descricao=f"Criada pela importação {imp['filename']}")
                old = dist.get(sid)
                if old and old["etapas"] == rec["etapas"]:
                    res["sem_alteracao"] += 1
                    continue
                if old:
                    res["alterados"] += 1
                    res["amostra_alterados"].append({"linha": linha, "nome": rec["escola"], "diff": {
                        e: {"antes": old["etapas"].get(e, 0), "depois": v} for e, v in rec["etapas"].items() if old["etapas"].get(e, 0) != v}})
                elif sid not in novas_escolas.values():
                    res["novos"] += 1
                    res["amostra_novos"].append({"linha": linha, "escola": rec["escola"], "total": rec["total"]})
                dist[sid] = {"school_id": sid, "etapas": rec["etapas"], "total": rec["total"]}
                if commit:
                    await db.distribuicao.update_one({"school_id": sid}, {"$set": {**dist[sid], "updated_at": now_iso()}}, upsert=True)
                    await audit(member, "alteracao_distribuicao", "distribuicao", sid, old and old["etapas"], rec["etapas"],
                                descricao=f"{rec['escola']} — importação {imp['filename']}")
            if commit:
                await refresh_suggestions()
                schools, aliases, by_norm = await _school_index()
        elif cfg["categoria"] == "quadro":
            for linha, rec in recs:
                sid = _resolve(rec["escola"], aliases, by_norm)
                if not sid:
                    res["erros"].append({"linha": linha, "mensagem": f"Unidade não identificada: '{rec['escola']}' — valide na Correspondência de Escolas"})
                    res["escolas_pendentes"].append(rec["escola"])
                    continue
                k = (sid, cargo_key(rec["cargo"]), cargo_key(rec["funcao"]))
                old = quadro.get(k)
                if old and old["quantidade"] == rec["quantidade"]:
                    res["sem_alteracao"] += 1
                    continue
                res["alterados" if old else "novos"] += 1
                (res["amostra_alterados"] if old else res["amostra_novos"]).append(
                    {"linha": linha, "nome": rec["escola"], "escola": rec["escola"], "cargo": rec["cargo"], "funcao": rec["funcao"],
                     "quantidade": rec["quantidade"], "diff": {"quantidade": {"antes": old["quantidade"], "depois": rec["quantidade"]}} if old else None})
                doc = {"id": old["id"] if old else new_id(), "school_id": sid, "cargo": cargo_key(rec["cargo"]),
                       "funcao": cargo_key(rec["funcao"]), "quantidade": rec["quantidade"]}
                quadro[k] = doc
                if commit:
                    await db.quadro.update_one({"id": doc["id"]}, {"$set": {**doc, "updated_at": now_iso()}}, upsert=True)
                    await audit(member, "alteracao_quadro_autorizado", "quadro", doc["id"], old and {"quantidade": old["quantidade"]},
                                {"quantidade": rec["quantidade"]}, vaga_key=vaga_key(sid, doc["cargo"], doc["funcao"]),
                                descricao=f"{rec['escola']} / {rec['cargo']} — importação {imp['filename']}")
            if commit:
                await ensure_aliases(res["escolas_pendentes"])
        result.append(res)
    return {"planilhas": result}
