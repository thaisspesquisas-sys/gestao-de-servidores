import math
import difflib
from collections import defaultdict, Counter

from core import db, norm_text, norm_school, clean, ETAPAS


def cargo_key(c) -> str:
    return clean(c).upper()


def vaga_key(sid, cargo, funcao) -> str:
    return f"{sid}|{cargo}|{funcao}"


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ta, tb = set(a.split()), set(b.split())
    cont = len(ta & tb) / min(len(ta), len(tb)) * 0.95
    return round(max(difflib.SequenceMatcher(None, a, b).ratio(), cont), 3)


async def load_state() -> dict:
    return {
        "schools": {s["id"]: s async for s in db.schools.find({"arquivada": {"$ne": True}}, {"_id": 0})},
        "aliases": {a["alias_norm"]: a async for a in db.school_aliases.find({}, {"_id": 0})},
        "cargo_map": {c["alias"]: c["cargo_padrao"] async for c in db.cargo_map.find({}, {"_id": 0})},
        "situ": {s["codigo"]: s async for s in db.situacoes.find({}, {"_id": 0})},
        "servs": [s async for s in db.servidores.find({"arquivado": {"$ne": True}}, {"_id": 0})],
        "dist": {d["school_id"]: d async for d in db.distribuicao.find({}, {"_id": 0})},
        "quadro": [q async for q in db.quadro.find({}, {"_id": 0})],
        "reservas": [r async for r in db.reservas.find({"situacao": "ativa"}, {"_id": 0})],
        "regras": [r async for r in db.etapa_regras.find({}, {"_id": 0})],
        "cfg": await db.settings.find_one({"id": "config"}, {"_id": 0}) or {},
    }


def resolve_school(st, lotacao):
    a = st["aliases"].get(norm_school(lotacao))
    if a and a["status"] == "confirmado" and a.get("school_id") in st["schools"]:
        return a["school_id"], "confirmado"
    return None, (a["status"] if a else "pendente")


def map_cargo(st, cargo) -> str:
    k = cargo_key(cargo)
    return st["cargo_map"].get(k, k)


def enrich(st, s: dict) -> dict:
    sid, lot_status = resolve_school(st, s.get("lotacao"))
    sit = st["situ"].get(s.get("situacao") or "ativo")
    return {**s, "school_id": sid, "escola": st["schools"][sid]["nome"] if sid else None,
            "lotacao_status": lot_status, "cargo_padrao": map_cargo(st, s.get("cargo")),
            "funcao_padrao": cargo_key(s.get("funcao")), "regra": sit["regra"] if sit else "pendente",
            "ativo": sit.get("conta_como_ativo", True) if sit else True,
            "situacao_nome": sit["nome"] if sit else (s.get("situacao") or "")}


def vinculo_ok(v, f) -> bool:
    return ((not f.get("escola") or v["school_id"] == f["escola"])
            and (not f.get("cargo") or v["cargo_padrao"] == f["cargo"])
            and (not f.get("funcao") or v["funcao_padrao"] == f["funcao"])
            and (not f.get("vinculo") or norm_text(v.get("vinculo")) == norm_text(f["vinculo"]))
            and (not f.get("situacao") or (v.get("situacao") or "ativo") == f["situacao"]))


def compute(st: dict, f: dict = None) -> dict:
    f = f or {}
    schools = st["schools"]
    vincs = [enrich(st, s) for s in st["servs"]]
    vf = [v for v in vincs if vinculo_ok(v, f)]
    rows = {}

    def keep(sid, cargo, funcao):
        return ((not f.get("escola") or sid == f["escola"]) and (not f.get("cargo") or cargo == f["cargo"])
                and (not f.get("funcao") or funcao == f["funcao"]))

    def row(sid, cargo, funcao):
        k = (sid, cargo, funcao)
        if k not in rows:
            rows[k] = {"key": vaga_key(sid, cargo, funcao), "school_id": sid, "escola": schools[sid]["nome"],
                       "cargo": cargo, "funcao": funcao, "autorizadas": None, "previsto": None, "ocupadas": 0,
                       "reservadas_situacao": 0, "reservadas_manual": 0, "pendentes": 0}
        return rows[k]

    quadro_keys = set()
    for q in st["quadro"]:
        sid, cargo, fn = q["school_id"], map_cargo(st, q["cargo"]), cargo_key(q.get("funcao"))
        if sid in schools:
            quadro_keys.add((sid, cargo, fn))
            if keep(sid, cargo, fn):
                r = row(sid, cargo, fn)
                r["autorizadas"] = (r["autorizadas"] or 0) + int(q.get("quantidade") or 0)

    prev = defaultdict(float)
    for sid, d in st["dist"].items():
        if sid not in schools:
            continue
        for rg in st["regras"]:
            if rg.get("fator") not in (None, "") and rg.get("cargo"):
                prev[(sid, map_cargo(st, rg["cargo"]))] += (d["etapas"].get(rg["etapa"]) or 0) * float(rg["fator"])
    for (sid, cargo), val in prev.items():
        if keep(sid, cargo, "") and val > 0:
            row(sid, cargo, "")["previsto"] = math.ceil(val - 1e-9)

    for v in vf:
        sid = v["school_id"]
        if not sid:
            continue
        fn = v["funcao_padrao"] if (sid, v["cargo_padrao"], v["funcao_padrao"]) in quadro_keys else ""
        r = row(sid, v["cargo_padrao"], fn)
        if v["regra"] in ("ocupa", "pendente"):
            r["ocupadas"] += 1
            if v["regra"] == "pendente":
                r["pendentes"] += 1
        elif v["regra"] == "reserva":
            r["reservadas_situacao"] += 1

    for rs in st["reservas"]:
        sid, cargo, fn = rs["school_id"], map_cargo(st, rs["cargo"]), cargo_key(rs.get("funcao"))
        if sid in schools and keep(sid, cargo, fn):
            row(sid, cargo, fn)["reservadas_manual"] += int(rs.get("quantidade") or 0)

    modo = st["cfg"].get("base_calculo", "oficial")
    for r in rows.values():
        if r["autorizadas"] is not None:
            base, fonte = r["autorizadas"], "oficial"
        elif r["previsto"] is not None and modo == "oficial_ou_previsto":
            base, fonte = r["previsto"], "regra"
        else:
            base, fonte = None, None
        r["reservadas"] = r["reservadas_situacao"] + r["reservadas_manual"]
        r["base"], r["fonte_base"] = base, fonte
        if base is None:
            r["disponiveis"] = r["excedente"] = None
        else:
            saldo = base - r["ocupadas"] - r["reservadas"]
            r["disponiveis"], r["excedente"] = max(saldo, 0), max(-saldo, 0)

    linhas = sorted(rows.values(), key=lambda r: (r["escola"], r["cargo"], r["funcao"]))
    return {"vinculos": vf, "todos": vincs, "linhas": linhas}


def _sum(rows, k):
    return sum(r[k] for r in rows if r.get(k) is not None)


def agg_por(linhas, campo):
    g = defaultdict(lambda: {"autorizadas": 0, "previsto": 0, "base": 0, "ocupadas": 0, "reservadas": 0,
                             "disponiveis": 0, "excedente": 0, "sem_base": 0})
    for r in linhas:
        a = g[r[campo]]
        for k in ("autorizadas", "previsto", "base", "ocupadas", "reservadas", "disponiveis", "excedente"):
            a[k] += r[k] or 0
        if r["base"] is None:
            a["sem_base"] += 1
        if campo == "escola":
            a["school_id"] = r["school_id"]
    return [{"nome": k, **v} for k, v in sorted(g.items())]


def dashboard(st, f) -> dict:
    res = compute(st, f)
    linhas, vf = res["linhas"], res["vinculos"]
    escolas = agg_por(linhas, "escola")
    sids = [f["escola"]] if f.get("escola") else list(st["schools"].keys())
    etapa_turmas = Counter()
    for sid in sids:
        d = st["dist"].get(sid)
        for e in ETAPAS:
            etapa_turmas[e] += (d["etapas"].get(e) or 0) if d else 0
    regras = {r["etapa"]: r for r in st["regras"]}
    por_etapa = []
    for e in ETAPAS:
        rg = regras.get(e) or {}
        fator = rg.get("fator")
        por_etapa.append({"etapa": e, "turmas": etapa_turmas[e],
                          "profissionais_previstos": math.ceil(etapa_turmas[e] * float(fator) - 1e-9) if fator not in (None, "") else None})
    func = Counter((v["funcao_padrao"] or "(SEM FUNÇÃO)") for v in vf if v["ativo"])
    situ = Counter(v["situacao_nome"] or "—" for v in vf)
    kpis = {
        "autorizadas_oficiais": _sum(linhas, "autorizadas"),
        "previstas_regra": _sum(linhas, "previsto"),
        "vagas_base": _sum(linhas, "base"),
        "ocupadas": _sum(linhas, "ocupadas"),
        "reservadas": _sum(linhas, "reservadas"),
        "disponiveis": _sum(linhas, "disponiveis"),
        "excedentes": _sum(linhas, "excedente"),
        "servidores_ativos": sum(1 for v in vf if v["ativo"]),
        "vinculos_total": len(vf),
        "escolas": len(sids),
        "escolas_deficit": sum(1 for e in escolas if e["disponiveis"] > 0),
        "escolas_excedente": sum(1 for e in escolas if e["excedente"] > 0),
        "vinculos_sem_escola": sum(1 for v in vf if not v["school_id"] and v["lotacao_status"] == "pendente"),
        "vinculos_fora_escolas": sum(1 for v in vf if not v["school_id"] and v["lotacao_status"] == "nao_escola"),
        "situacoes_pendentes": sum(1 for v in vf if v["regra"] == "pendente"),
        "linhas_sem_base": sum(1 for r in linhas if r["base"] is None),
        "quadro_oficial_importado": len(st["quadro"]) > 0,
        "regras_definidas": sum(1 for r in st["regras"] if r.get("fator") not in (None, "") and r.get("cargo")),
        "base_calculo": st["cfg"].get("base_calculo", "oficial"),
    }
    return {"kpis": kpis, "por_escola": escolas, "por_cargo": agg_por(linhas, "cargo"),
            "por_funcao": [{"nome": k, "servidores": v} for k, v in func.most_common(25)],
            "por_situacao": [{"nome": k, "servidores": v} for k, v in situ.most_common()],
            "por_etapa": por_etapa}


def find_school_in_text(st, texto):
    q = norm_school(texto)
    best, score = None, 0.0
    for s in st["schools"].values():
        n = norm_school(s["nome"])
        toks = set(n.split())
        if not toks:
            continue
        hit = len(toks & set(q.split())) / len(toks)
        if hit > score:
            best, score = s, hit
    return best if score >= 0.5 else None


def _faltando_base(st):
    falta = []
    if not st["quadro"]:
        falta.append("quadro oficial de vagas (não importado)")
    if st["cfg"].get("base_calculo", "oficial") != "oficial_ou_previsto" or not any(
            r.get("fator") not in (None, "") for r in st["regras"]):
        falta.append("regras de dimensionamento turmas → profissionais habilitadas como base de cálculo")
    return falta


def assistente(st, pergunta: str) -> dict:
    q = norm_text(pergunta)
    res = compute(st, {})
    linhas, vincs = res["linhas"], res["todos"]
    filtro_cargo = None
    if "INFANTIL" in q:
        filtro_cargo = "INFANTIL"
    elif "PROFESSOR" in q:
        filtro_cargo = "PROFESSOR"
    lf = [r for r in linhas if not filtro_cargo or filtro_cargo in norm_text(r["cargo"])]
    rotulo = {"INFANTIL": " de educação infantil", "PROFESSOR": " de professor"}.get(filtro_cargo, "")
    com_base = [r for r in lf if r["base"] is not None]

    def sem_dados(msg):
        return {"resposta": msg, "dados": [], "faltando": _faltando_base(st), "fonte": "Banco de dados validado"}

    if "MAIS DE UMA MATRICULA" in q or "DUAS MATRICULAS" in q or "VARIAS MATRICULAS" in q:
        g = defaultdict(set)
        for v in vincs:
            g[(v.get("cpf") and "".join(c for c in v["cpf"] if c.isdigit())) or norm_text(v["nome"])].add(v["matricula"])
        multi = [(k, m) for k, m in g.items() if len(m) > 1]
        nomes = {norm_text(v["nome"]): v["nome"] for v in vincs}
        return {"resposta": f"{len(multi)} servidor(es) possuem mais de uma matrícula registrada "
                            f"(agrupamento por CPF quando cadastrado; caso contrário, por nome idêntico — confirme os casos por nome).",
                "dados": [{"servidor": nomes.get(k, k), "matriculas": ", ".join(sorted(m))} for k, m in multi[:50]],
                "faltando": [] if any(v.get("cpf") for v in vincs) else ["CPF dos servidores (agrupamento feito por nome)"],
                "fonte": "Relação de servidores"}

    if "DIVERG" in q:
        dados = []
        for sid, s in st["schools"].items():
            turmas = sum((st["dist"].get(sid) or {}).get("etapas", {}).get(e) or 0 for e in ETAPAS)
            n = sum(1 for v in vincs if v["school_id"] == sid)
            if turmas and not n:
                dados.append({"escola": s["nome"], "divergencia": f"{turmas} turmas e nenhum servidor vinculado"})
            elif n and sid not in st["dist"]:
                dados.append({"escola": s["nome"], "divergencia": f"{n} servidores e nenhum quadro de turmas"})
        for r in linhas:
            if r["previsto"] is not None and r["previsto"] != r["ocupadas"]:
                dados.append({"escola": r["escola"], "divergencia": f"{r['cargo']}: previsto por regra {r['previsto']}, ocupadas {r['ocupadas']}"})
        pend = sum(1 for a in st["aliases"].values() if a["status"] == "pendente")
        msg = f"Foram encontradas {len(dados)} divergência(s) entre o quadro de turmas e a relação de servidores."
        if pend:
            msg += f" Há {pend} nome(s) de lotação aguardando validação na Correspondência de Escolas."
        falta = [] if any(r.get("fator") not in (None, "") for r in st["regras"]) else [
            "regras turmas → profissionais (sem elas, só divergências estruturais são verificadas)"]
        return {"resposta": msg, "dados": dados[:100], "faltando": falta, "fonte": "Distribuição + servidores"}

    if "EXCESS" in q or "EXCEDENT" in q or "ACIMA" in q:
        if not com_base:
            return sem_dados("Não é possível verificar excesso: não há vagas autorizadas/base de cálculo registradas.")
        cargos = [c for c in agg_por(com_base, "cargo") if c["excedente"] > 0]
        return {"resposta": f"{len(cargos)} cargo(s){rotulo} apresentam excedente, totalizando {sum(c['excedente'] for c in cargos)} vínculo(s) acima do quadro.",
                "dados": [{"cargo": c["nome"], "base": c["base"], "ocupadas": c["ocupadas"], "excedente": c["excedente"]} for c in cargos],
                "faltando": [], "fonte": "Controle de vagas"}

    escola = find_school_in_text(st, pergunta) if ("LOTAD" in q or "ESCOLA" in q or "UNIDADE" in q) else None
    if escola and ("QUANT" in q or "LOTAD" in q):
        vs = [v for v in vincs if v["school_id"] == escola["id"]]
        ativos = [v for v in vs if v["ativo"]]
        por = Counter(v["cargo_padrao"] for v in ativos)
        return {"resposta": f"{escola['nome']}: {len(ativos)} servidor(es) ativo(s) lotado(s) ({len(vs)} vínculo(s) no total).",
                "dados": [{"cargo": k, "servidores": n} for k, n in por.most_common()], "faltando": [],
                "fonte": "Relação de servidores"}

    if "PRECIS" in q or "DEFICIT" in q or "FALT" in q or "CARENCIA" in q:
        if not com_base:
            return sem_dados("Não é possível indicar escolas com necessidade: não há vagas autorizadas/base de cálculo registradas.")
        esc = [e for e in agg_por(com_base, "escola") if e["disponiveis"] > 0]
        return {"resposta": f"{len(esc)} escola(s) precisam de profissionais{rotulo}, com {sum(e['disponiveis'] for e in esc)} vaga(s) disponível(is).",
                "dados": [{"escola": e["nome"], "disponiveis": e["disponiveis"], "base": e["base"], "ocupadas": e["ocupadas"]} for e in esc],
                "faltando": [], "fonte": "Controle de vagas"}

    if "VAGA" in q:
        if not com_base:
            return sem_dados(f"Existem {_sum(lf, 'ocupadas')} vaga(s){rotulo} ocupadas, mas não há vagas autorizadas/base de cálculo para apurar disponíveis.")
        sem = sum(1 for r in lf if r["base"] is None and r["ocupadas"])
        msg = (f"Vagas{rotulo}: {_sum(com_base, 'base')} na base de cálculo, {_sum(com_base, 'ocupadas')} ocupadas, "
               f"{_sum(com_base, 'reservadas')} reservadas, {_sum(com_base, 'disponiveis')} disponíveis e {_sum(com_base, 'excedente')} excedentes.")
        if sem:
            msg += f" Atenção: {sem} combinação(ões) escola/cargo possuem ocupantes sem quadro autorizado e não entram no cálculo."
        return {"resposta": msg, "dados": [{"cargo": c["nome"], "disponiveis": c["disponiveis"], "reservadas": c["reservadas"]}
                                            for c in agg_por(com_base, "cargo") if c["disponiveis"]][:50],
                "faltando": [], "fonte": "Controle de vagas"}

    if "SERVIDOR" in q or "PROFISSIONA" in q:
        ativos = [v for v in vincs if v["ativo"] and (not filtro_cargo or filtro_cargo in norm_text(v["cargo_padrao"]))]
        return {"resposta": f"Há {len(ativos)} vínculo(s) ativo(s){rotulo} registrados ({len(vincs)} vínculos no total, contados por matrícula).",
                "dados": [{"situacao": k, "vinculos": n} for k, n in Counter(v["situacao_nome"] for v in vincs).most_common()],
                "faltando": [], "fonte": "Relação de servidores"}

    return {"resposta": "Não identifiquei a pergunta. Posso responder sobre: vagas disponíveis (de professor / educação infantil), "
                        "escolas que precisam de professores, profissionais lotados em uma escola (cite o nome), cargos com excesso, "
                        "divergências entre turmas e servidores e servidores com mais de uma matrícula.",
            "dados": [], "faltando": [], "fonte": ""}
