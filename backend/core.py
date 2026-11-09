import os
import re
import uuid
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pymongo import ReturnDocument

load_dotenv(Path(__file__).parent / ".env")

try:
    from backend.clerk_auth import require_user
except ModuleNotFoundError:
    from clerk_auth import require_user

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
fs = AsyncIOMotorGridFSBucket(db, bucket_name="arquivos_importados")

ROLES = ["admin", "gestor", "operador", "consulta", "pendente"]
DEFAULT_ROLE = "pendente"
RETIRED_ROLES = {}
RANK = {r: len(ROLES) - i for i, r in enumerate(ROLES)}
ROLE_LABELS = {"admin": "Administrador", "gestor": "Gestor da Secretaria", "operador": "Operador",
               "consulta": "Consulta", "pendente": "Aguardando aprovação"}
ENV = "live" if os.environ.get("CLERK_PUBLISHABLE_KEY", "").startswith("pk_live_") else "preview"
IN_ENV = {"env": {"$in": [ENV, None]}}

ETAPAS = ["MAT I", "MAT II", "MAT III", "PRÉ I", "PRÉ II", "1º ANO", "2º ANO", "3º ANO", "4º ANO", "5º ANO",
          "6º ANO", "7º ANO", "8º ANO", "9º ANO", "FASE I A V", "FASE VI", "FASE VII", "FASE VIII", "FASE IX"]

# regra: ocupa | libera | reserva | pendente
SITUACOES_PADRAO = [
    ("ativo", "Servidor ativo", "ocupa", True),
    ("aposentado", "Aposentado", "libera", False),
    ("exonerado", "Exonerado", "libera", False),
    ("cedido", "Cedido (para outro órgão)", "reserva", True),
    ("recebido_cessao", "Recebido por cessão", "ocupa", True),
    ("desviado", "Professor desviado de função / readaptado", "ocupa", True),
    ("lsv", "Licença sem vencimento", "reserva", True),
    ("licenca", "Licenças e afastamentos", "ocupa", True),
    ("permuta", "Permuta", "ocupa", True),
    ("contrato_temporario", "Contrato temporário", "ocupa", True),
    ("vacancia", "Vacância", "libera", False),
]
REGRAS_LABEL = {"ocupa": "Ocupa a vaga", "libera": "Libera a vaga", "reserva": "Mantém a vaga reservada",
                "pendente": "Regra não definida (mantém ocupada e sinaliza)"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_text(s) -> str:
    if s is None:
        return ""
    return " ".join(strip_accents(str(s)).upper().replace("º", "O").replace("ª", "A").split())


def clean(s) -> str:
    if s is None:
        return ""
    return " ".join(str(s).split())


SCHOOL_STOP = {"E", "M", "EM", "CRECHE", "ESCOLA", "C", "CM", "PROF", "PROFA", "PROFO", "DR", "DRO", "MUN",
               "MUNICIPAL", "DE", "DA", "DO", "DOS", "DAS", "A", "O"}


def norm_school(s) -> str:
    t = strip_accents(str(s or "")).upper().replace("º", " ").replace("ª", " ")
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    toks = [w for w in t.split() if w not in SCHOOL_STOP and not (len(w) == 1 and w.isalpha())]
    return " ".join(toks)


def mask_cpf(cpf: str) -> str:
    d = re.sub(r"\D", "", cpf or "")
    return f"***.***.***-{d[-2:]}" if d else ""


async def audit(member: dict, acao: str, entidade: str, entidade_id: str = "", antes=None, depois=None,
                vaga_key: str = None, descricao: str = ""):
    await db.auditoria.insert_one({
        "id": new_id(), "ts": now_iso(), "user_id": member.get("user_id"),
        "usuario": member.get("email") or member.get("user_id"), "acao": acao, "entidade": entidade,
        "entidade_id": entidade_id, "antes": antes, "depois": depois, "vaga_key": vaga_key,
        "descricao": descricao,
    })


def effective_role(role) -> str:
    role = RETIRED_ROLES.get(role, role)
    return role if role in ROLES else DEFAULT_ROLE


def _clerk_user(user_id: str) -> dict:
    r = requests.get(f"https://api.clerk.com/v1/users/{user_id}", timeout=10,
                     headers={"Authorization": f"Bearer {os.environ['CLERK_SECRET_KEY']}", "User-Agent": "emergent-app"})
    r.raise_for_status()
    return r.json()


def _is_admin(info: dict) -> bool:
    admins = {e.strip().lower() for e in os.environ.get("ADMIN_EMAIL", "").split(",") if e.strip()}
    return any(e["email_address"].lower() in admins and (e.get("verification") or {}).get("status") == "verified"
               for e in info.get("email_addresses", []))


async def current_member(user: dict = Depends(require_user)) -> dict:
    uid = user["user_id"]
    member = await db.users.find_one({"user_id": uid}, {"_id": 0})
    if member is None or not member.get("role"):
        info = _clerk_user(uid)
        role = "admin" if _is_admin(info) else DEFAULT_ROLE
        emails = info.get("email_addresses") or []
        email = emails[0]["email_address"] if emails else ""
        name = " ".join(x for x in [info.get("first_name"), info.get("last_name")] if x)
        await db.users.update_one({"user_id": uid, "role": {"$in": [None, ""]}}, {"$set": {"role": role}})
        member = await db.users.find_one_and_update(
            {"user_id": uid},
            {"$setOnInsert": {"user_id": uid, "role": role, "created_at": now_iso()},
             "$set": {"email": email, "nome": name}},
            upsert=True, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if member.get("env") != ENV:
        await db.users.update_one({"user_id": uid}, {"$set": {"env": ENV}})
    return {**member, "env": ENV, "role": effective_role(member["role"])}


def require_role(*roles: str):
    async def check(member: dict = Depends(current_member)) -> dict:
        if member["role"] not in roles:
            raise HTTPException(status_code=403, detail="Permissão insuficiente")
        return member
    return check


LEITURA = require_role("admin", "gestor", "operador", "consulta")
OPERACAO = require_role("admin", "gestor", "operador")
GESTAO = require_role("admin", "gestor")
ADMIN = require_role("admin")
