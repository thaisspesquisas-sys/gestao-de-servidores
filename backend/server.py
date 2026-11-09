import asyncio
import hashlib
import logging
import os
from contextlib import suppress
from typing import Optional, List

from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Query, Response
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel
from starlette.middleware.cors import CORSMiddleware

from core import (db, fs, now_iso, new_id, norm_text, norm_school, clean, mask_cpf, audit, current_member,
                  LEITURA, OPERACAO, GESTAO, ADMIN, ROLES, RANK, ROLE_LABELS, IN_ENV, effective_role, RETIRED_ROLES,
                  ETAPAS, SITUACOES_PADRAO, REGRAS_LABEL)
from engine import load_state, compute, dashboard, enrich, assistente, cargo_key, vaga_key, agg_por
import importer
import reports

try:
    from backend.clerk_auth import clerk_router
except ModuleNotFoundError:
    from clerk_auth import clerk_router

INDEXES = {
    "users": [IndexModel([("user_id", ASCENDING)], name="user_id", unique=True)],
    "servidores": [IndexModel([("id", ASCENDING)], name="id", unique=True), IndexModel([("matricula", ASCENDING)], name="matricula")],
    "schools": [IndexModel([("id", ASCENDING)], name="id", unique=True)],
    "school_aliases": [IndexModel([("alias_norm", ASCENDING)], name="alias_norm", unique=True)],
    "distribuicao": [IndexModel([("school_id", ASCENDING)], name="school_id", unique=True)],
    "quadro": [IndexModel([("id", ASCENDING)], name="id", unique=True)],
    "reservas": [IndexModel([("id", ASCENDING)], name="id", unique=True)],
    "auditoria": [IndexModel([("ts", DESCENDING)], name="ts"), IndexModel([("vaga_key", ASCENDING)], name="vaga_key"),
                  IndexModel([("entidade_id", ASCENDING)], name="entidade_id")],
    "importacoes": [IndexModel([("id", ASCENDING)], name="id", unique=True)],
    "situacoes": [IndexModel([("codigo", ASCENDING)], name="codigo", unique=True)],
    "cargo_map": [IndexModel([("alias", ASCENDING)], name="alias", unique=True)],
}

app = FastAPI()
api = APIRouter(prefix="/api")
log = logging.getLogger(__name__)
_parsed_cache: dict = {}


def filtros(escola: str = "", cargo: str = "", funcao: str = "", vinculo: str = "", situacao: str = "") -> dict:
    return {"escola": escola, "cargo": cargo, "funcao": funcao, "vinculo": vinculo, "situacao": situacao}


def public_serv(v: dict, member: dict) -> dict:
    out = {k: v.get(k) for k in v if k not in ("_id",)}
    if member["role"] != "admin":
        out["cpf"] = mask_cpf(v.get("cpf"))
    return out


# ---------- usuários ----------
@api.get("/me")
async def me(member: dict = Depends(current_member)):
    return {**member, "role_label": ROLE_LABELS[member["role"]]}


@api.get("/users")
async def list_users(admin: dict = Depends(ADMIN)):
    people = await db.users.find(IN_ENV, {"_id": 0}).to_list(1000)
    return {"roles": [{"value": r, "label": ROLE_LABELS[r]} for r in ROLES if RANK[r] <= RANK[admin["role"]]],
            "users": [{**p, "role": effective_role(p.get("role"))} for p in people]}


class RoleIn(BaseModel):
    role: str


@api.patch("/users/{user_id}/role")
async def set_role(user_id: str, body: RoleIn, admin: dict = Depends(ADMIN)):
    if body.role not in ROLES or RANK[body.role] > RANK[admin["role"]]:
        raise HTTPException(403, "Permissão insuficiente")
    target = await db.users.find_one({"user_id": user_id, **IN_ENV}, {"_id": 0})
    if target is None:
        raise HTTPException(404, "Usuário não encontrado")
    if (effective_role(target.get("role")) == "admin" and body.role != "admin"
            and await db.users.count_documents({"role": "admin", **IN_ENV}) <= 1):
        raise HTTPException(409, "Mantenha ao menos um administrador")
    await db.users.update_one({"user_id": user_id}, {"$set": {"role": body.role}})
    await audit(admin, "alteracao_permissao", "usuario", user_id, {"role": target.get("role")}, {"role": body.role},
                descricao=target.get("email") or user_id)
    return {"user_id": user_id, "role": body.role}


# ---------- metadados / dashboard ----------
@api.get("/meta")
async def meta(m: dict = Depends(LEITURA)):
    st = await load_state()
    vincs = [enrich(st, s) for s in st["servs"]]
    return {
        "etapas": ETAPAS,
        "escolas": sorted([{"id": s["id"], "nome": s["nome"]} for s in st["schools"].values()], key=lambda x: x["nome"]),
        "cargos": sorted({v["cargo_padrao"] for v in vincs} | {cargo_key(q["cargo"]) for q in st["quadro"]}),
        "funcoes": sorted({v["funcao_padrao"] for v in vincs if v["funcao_padrao"]}),
        "vinculos": sorted({clean(v.get("vinculo")) for v in vincs if v.get("vinculo")}),
        "situacoes": sorted(st["situ"].values(), key=lambda s: s.get("ordem", 99)),
        "regras_label": REGRAS_LABEL,
    }


@api.get("/dashboard")
async def get_dashboard(f: dict = Depends(filtros), m: dict = Depends(LEITURA)):
    return dashboard(await load_state(), f)


@api.get("/vagas")
async def get_vagas(f: dict = Depends(filtros), m: dict = Depends(LEITURA)):
    st = await load_state()
    linhas = compute(st, f)["linhas"]
    return {"linhas": linhas, "por_cargo": agg_por(linhas, "cargo"), "base_calculo": st["cfg"].get("base_calculo", "oficial")}


@api.get("/vagas/historico")
async def vaga_historico(key: str, m: dict = Depends(LEITURA)):
    sid, cargo, funcao = (key.split("|") + ["", "", ""])[:3]
    st = await load_state()
    ids = [v["id"] for v in compute(st, {"escola": sid, "cargo": cargo})["todos"] if v["school_id"] == sid and v["cargo_padrao"] == cargo]
    eventos = await db.auditoria.find({"$or": [{"vaga_key": key}, {"entidade_id": {"$in": ids}}]}, {"_id": 0}).sort("ts", -1).to_list(500)
    return {"eventos": eventos}


# ---------- escolas ----------
@api.get("/escolas")
async def list_escolas(m: dict = Depends(LEITURA)):
    st = await load_state()
    res = compute(st, {})
    agg = {e["school_id"]: e for e in agg_por(res["linhas"], "escola")}
    out = []
    for sid, s in st["schools"].items():
        d = st["dist"].get(sid)
        a = agg.get(sid, {})
        out.append({"id": sid, "nome": s["nome"], "turmas": d["total"] if d else None,
                    "servidores": sum(1 for v in res["todos"] if v["school_id"] == sid and v["ativo"]),
                    "base": a.get("base", 0), "ocupadas": a.get("ocupadas", 0), "reservadas": a.get("reservadas", 0),
                    "disponiveis": a.get("disponiveis", 0), "excedente": a.get("excedente", 0)})
    return sorted(out, key=lambda x: x["nome"])


@api.get("/escolas/{sid}")
async def get_escola(sid: str, m: dict = Depends(LEITURA)):
    st = await load_state()
    if sid not in st["schools"]:
        raise HTTPException(404, "Escola não encontrada")
    res = compute(st, {"escola": sid})
    regras = {r["etapa"]: r for r in st["regras"]}
    d = st["dist"].get(sid)
    etapas = []
    for e in ETAPAS:
        t = (d["etapas"].get(e) or 0) if d else 0
        fator = (regras.get(e) or {}).get("fator")
        etapas.append({"etapa": e, "turmas": t, "previstos": None if fator in (None, "") else -(-t * float(fator) // 1),
                       "cargo_regra": (regras.get(e) or {}).get("cargo")})
    tot = lambda k: sum(r[k] or 0 for r in res["linhas"])
    aliases = [a for a in st["aliases"].values() if a.get("school_id") == sid]
    return {"escola": st["schools"][sid], "etapas": etapas, "tem_distribuicao": d is not None, "linhas": res["linhas"],
            "resumo": {"previsto": tot("previsto"), "base": tot("base"), "ocupadas": tot("ocupadas"), "reservadas": tot("reservadas"),
                       "disponiveis": tot("disponiveis"), "excedente": tot("excedente"),
                       "saldo": tot("disponiveis") - tot("excedente")},
            "servidores": [public_serv(v, m) for v in sorted(res["vinculos"], key=lambda v: v["nome"])],
            "nomes_correspondentes": sorted({e for a in aliases for e in a.get("exemplos", [])})}


class EscolaIn(BaseModel):
    nome: str = Field(min_length=2)


@api.post("/escolas")
async def create_escola(body: EscolaIn, m: dict = Depends(ADMIN)):
    doc = {"id": new_id(), "nome": clean(body.nome), "origem": "manual", "created_at": now_iso()}
    await db.schools.insert_one({**doc})
    await db.school_aliases.update_one({"alias_norm": norm_school(doc["nome"])}, {"$set": {"status": "confirmado", "school_id": doc["id"]},
                                       "$setOnInsert": {"id": new_id(), "exemplos": [doc["nome"]], "created_at": now_iso()}}, upsert=True)
    await audit(m, "nova_unidade", "escola", doc["id"], None, {"nome": doc["nome"]})
    await importer.refresh_suggestions()
    return doc


@api.put("/escolas/{sid}")
async def rename_escola(sid: str, body: EscolaIn, m: dict = Depends(ADMIN)):
    old = await db.schools.find_one({"id": sid}, {"_id": 0})
    if not old:
        raise HTTPException(404, "Escola não encontrada")
    await db.schools.update_one({"id": sid}, {"$set": {"nome": clean(body.nome)}})
    await audit(m, "alteracao_unidade", "escola", sid, {"nome": old["nome"]}, {"nome": clean(body.nome)})
    return {"ok": True}


# ---------- servidores ----------
class ServidorIn(BaseModel):
    matricula: str = Field(min_length=1)
    nome: str = Field(min_length=2)
    cpf: str = ""
    cargo: str = Field(min_length=2)
    funcao: str = ""
    lotacao: str = ""
    secretaria: str = ""
    vinculo: str = ""
    carga_horaria: str = ""
    admissao: str = ""
    situacao: str = "ativo"
    obs: str = ""


@api.get("/servidores")
async def list_servidores(q: str = "", f: dict = Depends(filtros), lotacao_status: str = "", page: int = 1, page_size: int = Query(50, le=500),
                          m: dict = Depends(LEITURA)):
    st = await load_state()
    vs = compute(st, f)["vinculos"]
    if q:
        nq = norm_text(q)
        vs = [v for v in vs if nq in norm_text(v["nome"]) or nq in norm_text(v["matricula"]) or nq in norm_text(v.get("lotacao"))]
    if lotacao_status:
        vs = [v for v in vs if v["lotacao_status"] == lotacao_status and not v["school_id"]]
    vs.sort(key=lambda v: norm_text(v["nome"]))
    total = len(vs)
    s = (page - 1) * page_size
    return {"total": total, "page": page, "items": [public_serv(v, m) for v in vs[s:s + page_size]]}


@api.get("/servidores/{vid}")
async def get_servidor(vid: str, m: dict = Depends(LEITURA)):
    st = await load_state()
    doc = await db.servidores.find_one({"id": vid}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Vínculo não encontrado")
    v = enrich(st, doc)
    outros = [public_serv(enrich(st, o), m) for o in st["servs"] if o["id"] != vid and (
        norm_text(o["nome"]) == norm_text(doc["nome"]) or o["matricula"] == doc["matricula"] or (doc.get("cpf") and o.get("cpf") == doc["cpf"]))]
    hist = await db.auditoria.find({"entidade_id": vid}, {"_id": 0}).sort("ts", -1).to_list(200)
    return {"vinculo": public_serv(v, m), "outros_vinculos": outros, "historico": hist}


@api.post("/servidores")
async def create_servidor(body: ServidorIn, m: dict = Depends(OPERACAO)):
    data = {k: clean(v) for k, v in body.model_dump().items()}
    if await db.servidores.find_one({"matricula": data["matricula"], "arquivado": {"$ne": True}}, {"_id": 0, "cargo": 1, "id": 1}) and \
            await db.servidores.find_one({"matricula": data["matricula"], "cargo": data["cargo"]}):
        raise HTTPException(409, "Já existe vínculo com esta matrícula e cargo")
    doc = {"id": new_id(), **data, "situacao_detalhe": "Cadastro manual", "created_at": now_iso(), "updated_at": now_iso(), "arquivado": False}
    await db.servidores.insert_one({**doc})
    await importer.ensure_aliases([data["lotacao"]])
    await audit(m, "novo_servidor", "servidor", doc["id"], None, {**data, "cpf": mask_cpf(data["cpf"])}, descricao=f"{data['nome']} ({data['matricula']})")
    return doc


@api.put("/servidores/{vid}")
async def update_servidor(vid: str, body: ServidorIn, m: dict = Depends(OPERACAO)):
    old = await db.servidores.find_one({"id": vid}, {"_id": 0})
    if not old:
        raise HTTPException(404, "Vínculo não encontrado")
    data = {k: clean(v) for k, v in body.model_dump().items()}
    if m["role"] != "admin" and set(data["cpf"]) <= {"*", ".", "-"} | set("0123456789") and "*" in data["cpf"]:
        data["cpf"] = old.get("cpf", "")
    diff = {k: v for k, v in data.items() if (old.get(k) or "") != v}
    if not diff:
        return {"ok": True, "alterado": False}
    await db.servidores.update_one({"id": vid}, {"$set": {**diff, "updated_at": now_iso()}})
    acao = "mudanca_lotacao" if "lotacao" in diff else "mudanca_cargo" if "cargo" in diff else "mudanca_situacao" if "situacao" in diff else "alteracao_servidor"
    mask = lambda d: {**d, **({"cpf": mask_cpf(d["cpf"])} if "cpf" in d else {})}
    await audit(m, acao, "servidor", vid, mask({k: old.get(k) for k in diff}), mask(diff), descricao=f"{old['nome']} ({old['matricula']})")
    if "lotacao" in diff:
        await importer.ensure_aliases([diff["lotacao"]])
    return {"ok": True, "alterado": True}


class MotivoIn(BaseModel):
    motivo: str = Field(min_length=3)


@api.post("/servidores/{vid}/arquivar")
async def arquivar_servidor(vid: str, body: MotivoIn, m: dict = Depends(ADMIN)):
    old = await db.servidores.find_one({"id": vid}, {"_id": 0})
    if not old:
        raise HTTPException(404, "Vínculo não encontrado")
    await db.servidores.update_one({"id": vid}, {"$set": {"arquivado": True, "arquivado_em": now_iso(), "arquivado_motivo": body.motivo}})
    await audit(m, "arquivamento_servidor", "servidor", vid, {"arquivado": False}, {"arquivado": True, "motivo": body.motivo},
                descricao=f"{old['nome']} ({old['matricula']}) — autorizado pelo administrador")
    return {"ok": True}


# ---------- distribuição ----------
@api.get("/distribuicao")
async def get_distribuicao(m: dict = Depends(LEITURA)):
    st = await load_state()
    rows = []
    for sid, s in st["schools"].items():
        d = st["dist"].get(sid)
        rows.append({"school_id": sid, "escola": s["nome"], "etapas": d["etapas"] if d else {e: 0 for e in ETAPAS},
                     "total": d["total"] if d else 0, "cadastrado": d is not None})
    rows.sort(key=lambda r: r["escola"])
    totais = {e: sum(r["etapas"].get(e) or 0 for r in rows) for e in ETAPAS}
    return {"etapas": ETAPAS, "linhas": rows, "totais": totais, "total_geral": sum(totais.values())}


class DistIn(BaseModel):
    etapas: dict


@api.put("/distribuicao/{sid}")
async def put_distribuicao(sid: str, body: DistIn, m: dict = Depends(OPERACAO)):
    if not await db.schools.find_one({"id": sid}):
        raise HTTPException(404, "Escola não encontrada")
    etapas = {}
    for e in ETAPAS:
        v = body.etapas.get(e) or 0
        if not isinstance(v, int) or v < 0:
            raise HTTPException(422, f"Valor inválido em {e}")
        etapas[e] = v
    old = await db.distribuicao.find_one({"school_id": sid}, {"_id": 0})
    await db.distribuicao.update_one({"school_id": sid}, {"$set": {"school_id": sid, "etapas": etapas, "total": sum(etapas.values()),
                                                                     "updated_at": now_iso()}}, upsert=True)
    await audit(m, "alteracao_distribuicao", "distribuicao", sid, old and old["etapas"], etapas, descricao="Edição manual do quadro de turmas")
    return {"ok": True, "total": sum(etapas.values())}


# ---------- quadro oficial ----------
class QuadroIn(BaseModel):
    school_id: str
    cargo: str = Field(min_length=2)
    funcao: str = ""
    quantidade: int = Field(ge=0)


@api.get("/quadro")
async def get_quadro(m: dict = Depends(LEITURA)):
    st = await load_state()
    return [{**q, "escola": st["schools"].get(q["school_id"], {}).get("nome")} for q in st["quadro"]]


@api.post("/quadro")
async def upsert_quadro(body: QuadroIn, m: dict = Depends(ADMIN)):
    if not await db.schools.find_one({"id": body.school_id}):
        raise HTTPException(404, "Escola não encontrada")
    cargo, funcao = cargo_key(body.cargo), cargo_key(body.funcao)
    old = await db.quadro.find_one({"school_id": body.school_id, "cargo": cargo, "funcao": funcao}, {"_id": 0})
    doc = {"id": old["id"] if old else new_id(), "school_id": body.school_id, "cargo": cargo, "funcao": funcao, "quantidade": body.quantidade}
    await db.quadro.update_one({"id": doc["id"]}, {"$set": {**doc, "updated_at": now_iso()}}, upsert=True)
    await audit(m, "alteracao_quadro_autorizado", "quadro", doc["id"], old and {"quantidade": old["quantidade"]}, {"quantidade": body.quantidade},
                vaga_key=vaga_key(body.school_id, cargo, funcao), descricao=f"{cargo} {funcao}".strip())
    return doc


@api.post("/quadro/{qid}/remover")
async def remove_quadro(qid: str, body: MotivoIn, m: dict = Depends(ADMIN)):
    old = await db.quadro.find_one({"id": qid}, {"_id": 0})
    if not old:
        raise HTTPException(404, "Registro não encontrado")
    await db.quadro_removidos.insert_one({**old, "removido_em": now_iso(), "motivo": body.motivo})
    await db.quadro.delete_one({"id": qid})
    await audit(m, "remocao_quadro_autorizado", "quadro", qid, old, None, vaga_key=vaga_key(old["school_id"], old["cargo"], old["funcao"]),
                descricao=f"Autorizado pelo administrador: {body.motivo}")
    return {"ok": True}


# ---------- reservas ----------
class ReservaIn(BaseModel):
    school_id: str
    cargo: str = Field(min_length=2)
    funcao: str = ""
    quantidade: int = Field(ge=1)
    motivo: str = Field(min_length=3)
    data_reserva: str
    responsavel: str = Field(min_length=2)
    previsao_utilizacao: str = ""


@api.get("/reservas")
async def list_reservas(situacao: str = "", m: dict = Depends(LEITURA)):
    st = await load_state()
    qf = {"situacao": situacao} if situacao else {}
    items = await db.reservas.find(qf, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [{**r, "escola": st["schools"].get(r["school_id"], {}).get("nome")} for r in items]


async def _reserva(rid):
    r = await db.reservas.find_one({"id": rid}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Reserva não encontrada")
    return r


@api.post("/reservas")
async def create_reserva(body: ReservaIn, m: dict = Depends(OPERACAO)):
    if not await db.schools.find_one({"id": body.school_id}):
        raise HTTPException(404, "Escola não encontrada")
    data = body.model_dump()
    data["cargo"], data["funcao"] = cargo_key(data["cargo"]), cargo_key(data["funcao"])
    hist = [{"ts": now_iso(), "usuario": m.get("email"), "acao": "criada", "dados": data}]
    doc = {"id": new_id(), **data, "situacao": "ativa", "historico": hist, "created_at": now_iso(), "criado_por": m.get("email")}
    await db.reservas.insert_one({**doc})
    await audit(m, "reserva_vaga", "reserva", doc["id"], None, data, vaga_key=vaga_key(data["school_id"], data["cargo"], data["funcao"]),
                descricao=f"{data['quantidade']} vaga(s) {data['cargo']} — {data['motivo']}")
    return doc


@api.put("/reservas/{rid}")
async def update_reserva(rid: str, body: ReservaIn, m: dict = Depends(OPERACAO)):
    old = await _reserva(rid)
    if old["situacao"] != "ativa":
        raise HTTPException(409, "Somente reservas ativas podem ser alteradas")
    data = body.model_dump()
    data["cargo"], data["funcao"] = cargo_key(data["cargo"]), cargo_key(data["funcao"])
    antes = {k: old.get(k) for k in data}
    await db.reservas.update_one({"id": rid}, {"$set": data, "$push": {"historico": {"ts": now_iso(), "usuario": m.get("email"), "acao": "alterada",
                                                                                      "antes": antes, "depois": data}}})
    await audit(m, "alteracao_reserva", "reserva", rid, antes, data, vaga_key=vaga_key(data["school_id"], data["cargo"], data["funcao"]))
    return {"ok": True}


class AcaoReservaIn(BaseModel):
    observacao: str = ""


async def _mudar_situacao(rid, nova, body, m, acao):
    old = await _reserva(rid)
    if old["situacao"] != "ativa":
        raise HTTPException(409, "Reserva não está ativa")
    await db.reservas.update_one({"id": rid}, {"$set": {"situacao": nova, f"{nova}_em": now_iso()},
                                               "$push": {"historico": {"ts": now_iso(), "usuario": m.get("email"), "acao": nova, "observacao": body.observacao}}})
    await audit(m, acao, "reserva", rid, {"situacao": "ativa"}, {"situacao": nova, "observacao": body.observacao},
                vaga_key=vaga_key(old["school_id"], old["cargo"], old["funcao"]),
                descricao=f"{old['quantidade']} vaga(s) {old['cargo']}")
    return {"ok": True}


@api.post("/reservas/{rid}/cancelar")
async def cancelar_reserva(rid: str, body: AcaoReservaIn, m: dict = Depends(GESTAO)):
    return await _mudar_situacao(rid, "cancelada", body, m, "liberacao_vaga")


@api.post("/reservas/{rid}/efetivar")
async def efetivar_reserva(rid: str, body: AcaoReservaIn, m: dict = Depends(GESTAO)):
    return await _mudar_situacao(rid, "efetivada", body, m, "efetivacao_reserva")


# ---------- regras ----------
class SituacaoIn(BaseModel):
    regra: str
    conta_como_ativo: bool
    descricao: str = ""


@api.put("/situacoes/{codigo}")
async def put_situacao(codigo: str, body: SituacaoIn, m: dict = Depends(ADMIN)):
    if body.regra not in REGRAS_LABEL:
        raise HTTPException(422, "Regra inválida")
    old = await db.situacoes.find_one({"codigo": codigo}, {"_id": 0})
    if not old:
        raise HTTPException(404, "Situação não encontrada")
    new = {"regra": body.regra, "conta_como_ativo": body.conta_como_ativo, "descricao": body.descricao, "sugerida": False, "updated_at": now_iso()}
    await db.situacoes.update_one({"codigo": codigo}, {"$set": new})
    await audit(m, "alteracao_regra_situacao", "situacao", codigo, {k: old.get(k) for k in ("regra", "conta_como_ativo")},
                {"regra": body.regra, "conta_como_ativo": body.conta_como_ativo}, descricao=old["nome"])
    return {"ok": True}


class NovaSituacaoIn(BaseModel):
    nome: str = Field(min_length=3)
    regra: str = "pendente"
    conta_como_ativo: bool = True


@api.post("/situacoes")
async def create_situacao(body: NovaSituacaoIn, m: dict = Depends(ADMIN)):
    codigo = norm_text(body.nome).lower().replace(" ", "_")
    if await db.situacoes.find_one({"codigo": codigo}):
        raise HTTPException(409, "Situação já existe")
    await db.situacoes.insert_one({"codigo": codigo, "nome": body.nome, "regra": body.regra, "conta_como_ativo": body.conta_como_ativo,
                                   "ordem": 50, "sugerida": False})
    await audit(m, "nova_situacao", "situacao", codigo, None, body.model_dump())
    return {"codigo": codigo}


@api.get("/regras")
async def get_regras(m: dict = Depends(LEITURA)):
    st = await load_state()
    regras = {r["etapa"]: r for r in st["regras"]}
    return {"etapas": [{"etapa": e, "cargo": (regras.get(e) or {}).get("cargo"), "fator": (regras.get(e) or {}).get("fator")} for e in ETAPAS],
            "base_calculo": st["cfg"].get("base_calculo", "oficial")}


class RegraEtapa(BaseModel):
    etapa: str
    cargo: Optional[str] = None
    fator: Optional[float] = Field(default=None, ge=0)


class RegrasIn(BaseModel):
    etapas: List[RegraEtapa]
    base_calculo: str


@api.put("/regras")
async def put_regras(body: RegrasIn, m: dict = Depends(ADMIN)):
    if body.base_calculo not in ("oficial", "oficial_ou_previsto"):
        raise HTTPException(422, "Base de cálculo inválida")
    old = await get_regras(m)
    for r in body.etapas:
        if r.etapa in ETAPAS:
            await db.etapa_regras.update_one({"etapa": r.etapa}, {"$set": {"etapa": r.etapa, "cargo": cargo_key(r.cargo) or None, "fator": r.fator}}, upsert=True)
    await db.settings.update_one({"id": "config"}, {"$set": {"id": "config", "base_calculo": body.base_calculo}}, upsert=True)
    await audit(m, "alteracao_regras_dimensionamento", "regras", "dimensionamento", old, body.model_dump())
    return {"ok": True}


# ---------- correspondência ----------
@api.get("/correspondencia")
async def get_correspondencia(m: dict = Depends(LEITURA)):
    st = await load_state()
    counts = {}
    for s in st["servs"]:
        n = norm_school(s.get("lotacao"))
        counts[n] = counts.get(n, 0) + 1
    out = []
    for a in st["aliases"].values():
        out.append({**a, "escola": st["schools"].get(a.get("school_id") or "", {}).get("nome"),
                    "sugestao": st["schools"].get(a.get("sugestao_id") or "", {}).get("nome"), "vinculos": counts.get(a["alias_norm"], 0)})
    ordem = {"pendente": 0, "nao_escola": 1, "confirmado": 2}
    return sorted(out, key=lambda a: (ordem.get(a["status"], 3), -a["vinculos"]))


class ValidarIn(BaseModel):
    acao: str
    school_id: Optional[str] = None
    nome: Optional[str] = None


@api.post("/correspondencia/{aid}/validar")
async def validar_alias(aid: str, body: ValidarIn, m: dict = Depends(ADMIN)):
    a = await db.school_aliases.find_one({"id": aid}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Registro não encontrado")
    if body.acao == "vincular":
        if not body.school_id or not await db.schools.find_one({"id": body.school_id}):
            raise HTTPException(422, "Escolha a escola")
        new = {"status": "confirmado", "school_id": body.school_id}
    elif body.acao == "nova_escola":
        esc = await create_escola(EscolaIn(nome=body.nome or a["exemplos"][0]), m)
        new = {"status": "confirmado", "school_id": esc["id"]}
    elif body.acao == "nao_escola":
        new = {"status": "nao_escola", "school_id": None}
    elif body.acao == "pendente":
        new = {"status": "pendente", "school_id": None}
    else:
        raise HTTPException(422, "Ação inválida")
    await db.school_aliases.update_one({"id": aid}, {"$set": {**new, "auto": False, "validado_por": m.get("email"), "validado_em": now_iso()}})
    await audit(m, "validacao_correspondencia", "correspondencia", aid, {"status": a["status"], "school_id": a.get("school_id")}, new,
                descricao=" / ".join(a.get("exemplos", [])[:3]))
    return {"ok": True}


@api.get("/cargos")
async def get_cargos(m: dict = Depends(LEITURA)):
    st = await load_state()
    counts = {}
    for s in st["servs"]:
        k = cargo_key(s.get("cargo"))
        counts[k] = counts.get(k, 0) + 1
    return sorted([{"alias": k, "cargo_padrao": st["cargo_map"].get(k, k), "vinculos": n, "mapeado": k in st["cargo_map"]}
                   for k, n in counts.items()], key=lambda x: x["alias"])


class CargoMapIn(BaseModel):
    alias: str
    cargo_padrao: str = Field(min_length=2)


@api.put("/cargos")
async def put_cargo(body: CargoMapIn, m: dict = Depends(ADMIN)):
    alias, padrao = cargo_key(body.alias), cargo_key(body.cargo_padrao)
    old = await db.cargo_map.find_one({"alias": alias}, {"_id": 0})
    if alias == padrao:
        await db.cargo_map.delete_one({"alias": alias})
    else:
        await db.cargo_map.update_one({"alias": alias}, {"$set": {"alias": alias, "cargo_padrao": padrao}}, upsert=True)
    await audit(m, "correspondencia_cargo", "cargo", alias, old and {"cargo_padrao": old["cargo_padrao"]}, {"cargo_padrao": padrao})
    return {"ok": True}


# ---------- importação ----------
async def _sheets(imp):
    if imp["id"] not in _parsed_cache:
        stream = await fs.open_download_stream(imp["file_id"])
        data = await stream.read()
        _parsed_cache.clear() if len(_parsed_cache) > 5 else None
        _parsed_cache[imp["id"]] = dict(importer.read_sheets(imp["filename"], data))
    return _parsed_cache[imp["id"]]


@api.post("/importacao/upload")
async def upload(file: UploadFile = File(...), m: dict = Depends(ADMIN)):
    data = await file.read()
    if not data:
        raise HTTPException(422, "Arquivo vazio")
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(413, "Arquivo acima de 30 MB")
    try:
        sheets = await asyncio.to_thread(importer.read_sheets, file.filename, data)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        log.exception("leitura")
        raise HTTPException(422, f"Não foi possível ler o arquivo: {e}")
    file_id = await fs.upload_from_stream(file.filename, data, metadata={"content_type": file.content_type})
    imp = {"id": new_id(), "filename": file.filename, "file_id": file_id, "tamanho": len(data), "sha256": hashlib.sha256(data).hexdigest(),
           "usuario": m.get("email"), "ts": now_iso(), "status": "em_analise"}
    await db.importacoes.insert_one({**imp})
    _parsed_cache[imp["id"]] = dict(sheets)
    abas = []
    for name, rows in sheets:
        det = importer.detect(name, rows)
        hdr = rows[det["header_row"]] if rows else []
        abas.append({"sheet": name, "linhas": len(rows), "header_row": det["header_row"], "categoria": det["categoria"],
                     "mapping": det["mapping"], "situacao_padrao": det["situacao_padrao"], "cabecalho": hdr,
                     "amostra": rows[det["header_row"] + 1: det["header_row"] + 6], "primeiras_linhas": rows[:12]})
    return {"id": imp["id"], "filename": file.filename, "abas": abas, "campos": {k: list(v.keys()) for k, v in importer.CAMPOS.items()},
            "obrigatorios": importer.OBRIGATORIOS}


class SheetCfg(BaseModel):
    sheet: str
    categoria: str
    header_row: int = 0
    mapping: dict = {}
    situacao_padrao: str = "auto"


class ImportCfg(BaseModel):
    abas: List[SheetCfg]


async def _imp(iid):
    imp = await db.importacoes.find_one({"id": iid}, {"_id": 0})
    if not imp:
        raise HTTPException(404, "Importação não encontrada")
    return imp


@api.post("/importacao/{iid}/previa")
async def previa(iid: str, body: ImportCfg, m: dict = Depends(ADMIN)):
    imp = await _imp(iid)
    return await importer.process(imp, await _sheets(imp), [c.model_dump() for c in body.abas], False, m)


@api.post("/importacao/{iid}/confirmar")
async def confirmar(iid: str, body: ImportCfg, m: dict = Depends(ADMIN)):
    imp = await _imp(iid)
    if imp["status"] == "concluida":
        raise HTTPException(409, "Importação já confirmada")
    res = await importer.process(imp, await _sheets(imp), [c.model_dump() for c in body.abas], True, m)
    resumo = [{k: p[k] for k in ("sheet", "categoria", "lidos", "novos", "alterados", "sem_alteracao")} | {"erros": len(p["erros"])} for p in res["planilhas"]]
    await db.importacoes.update_one({"id": iid}, {"$set": {"status": "concluida", "concluida_em": now_iso(), "resumo": resumo,
                                                          "config": [c.model_dump() for c in body.abas]}})
    await audit(m, "importacao_arquivo", "importacao", iid, None, {"arquivo": imp["filename"], "resumo": resumo}, descricao=imp["filename"])
    return res


@api.get("/importacao")
async def list_importacoes(m: dict = Depends(LEITURA)):
    return await db.importacoes.find({}, {"_id": 0, "file_id": 0}).sort("ts", -1).to_list(200)


@api.get("/importacao/{iid}/arquivo")
async def download_arquivo(iid: str, m: dict = Depends(ADMIN)):
    imp = await _imp(iid)
    stream = await fs.open_download_stream(imp["file_id"])
    return Response(await stream.read(), media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{imp["filename"]}"'})


# ---------- assistente / relatórios / auditoria ----------
class PerguntaIn(BaseModel):
    pergunta: str = Field(min_length=3)


@api.post("/assistente")
async def perguntar(body: PerguntaIn, m: dict = Depends(LEITURA)):
    return assistente(await load_state(), body.pergunta)


@api.get("/relatorios/{tipo}")
async def relatorio(tipo: str, formato: str = "pdf", f: dict = Depends(filtros), m: dict = Depends(LEITURA)):
    if tipo not in reports.TIPOS:
        raise HTTPException(404, "Relatório inexistente")
    if tipo == "historico" and m["role"] not in ("admin", "gestor"):
        raise HTTPException(403, "Permissão insuficiente")
    st = await load_state()
    aud = await db.auditoria.find({}, {"_id": 0}).sort("ts", -1).to_list(5000) if tipo == "historico" else []
    cols, rows = await reports.build(tipo, st, f, aud)
    partes = []
    if f.get("escola"):
        partes.append("Escola: " + st["schools"].get(f["escola"], {}).get("nome", ""))
    for k in ("cargo", "funcao", "vinculo", "situacao"):
        if f.get(k):
            partes.append(f"{k.capitalize()}: {f[k]}")
    sub = ("Filtros — " + "; ".join(partes)) if partes else "Toda a rede municipal"
    sub += f" · Base de cálculo: {'quadro oficial' if st['cfg'].get('base_calculo', 'oficial') == 'oficial' else 'quadro oficial ou previsto por regra'}"
    titulo = reports.TIPOS[tipo]
    if formato == "xlsx":
        content = await asyncio.to_thread(reports.to_xlsx, titulo, sub, cols, rows)
        mt, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        content = await asyncio.to_thread(reports.to_pdf, titulo, sub, cols, rows)
        mt, ext = "application/pdf", "pdf"
    return Response(content, media_type=mt, headers={"Content-Disposition": f'attachment; filename="relatorio_{tipo}.{ext}"'})


@api.get("/auditoria")
async def get_auditoria(acao: str = "", entidade: str = "", q: str = "", page: int = 1, m: dict = Depends(GESTAO)):
    flt = {}
    if acao:
        flt["acao"] = acao
    if entidade:
        flt["entidade"] = entidade
    if q:
        flt["$or"] = [{"descricao": {"$regex": q, "$options": "i"}}, {"usuario": {"$regex": q, "$options": "i"}}]
    total = await db.auditoria.count_documents(flt)
    items = await db.auditoria.find(flt, {"_id": 0}).sort("ts", -1).skip((page - 1) * 50).limit(50).to_list(50)
    acoes = await db.auditoria.distinct("acao")
    return {"total": total, "items": items, "acoes": sorted(acoes)}


app.include_router(api)
app.include_router(clerk_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


async def ensure_indexes():
    for coll, models in INDEXES.items():
        for mdl in models:
            try:
                await db[coll].create_indexes([mdl])
            except Exception as exc:
                log.error("ensure_indexes(%s.%s): %s", coll, mdl.document["name"], exc)


@app.on_event("startup")
async def startup():
    for i, (codigo, nome, regra, ativo) in enumerate(SITUACOES_PADRAO):
        await db.situacoes.update_one({"codigo": codigo}, {"$setOnInsert": {"codigo": codigo, "nome": nome, "regra": regra,
                                                                             "conta_como_ativo": ativo, "ordem": i, "sugerida": True}}, upsert=True)
    for e in ETAPAS:
        await db.etapa_regras.update_one({"etapa": e}, {"$setOnInsert": {"etapa": e, "cargo": None, "fator": None}}, upsert=True)
    await db.settings.update_one({"id": "config"}, {"$setOnInsert": {"id": "config", "base_calculo": "oficial"}}, upsert=True)
    for old, new in RETIRED_ROLES.items():
        await db.users.update_many({"role": old}, {"$set": {"role": new}})
    app.state.index_task = asyncio.create_task(ensure_indexes())


@app.on_event("shutdown")
async def shutdown():
    app.state.index_task.cancel()
    with suppress(asyncio.CancelledError):
        await app.state.index_task
