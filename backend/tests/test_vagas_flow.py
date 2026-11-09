# Regression suite: auth/roles, import (quadro + servidores), vagas formula, reservas, situações, regras,
# correspondência, assistente, relatórios. All test data uses TEST_ prefixes and is removed by id at teardown.
import io
import json
import os
import time

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = BASE_URL + "/api"
TOK = json.load(open("/tmp/tokens.json"))


def H(role):
    return {"Authorization": "Bearer " + TOK[role]}


def _db():
    load_dotenv("/app/backend/.env")
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


CREATED = {"servidores": set(), "quadro": set(), "reservas": set(), "importacoes": set(), "alias_norm": set()}


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    db = _db()
    if CREATED["servidores"]:
        db.servidores.delete_many({"id": {"$in": list(CREATED["servidores"])}})
    if CREATED["quadro"]:
        db.quadro.delete_many({"id": {"$in": list(CREATED["quadro"])}})
    if CREATED["reservas"]:
        db.reservas.delete_many({"id": {"$in": list(CREATED["reservas"])}})
    for iid in CREATED["importacoes"]:
        imp = db.importacoes.find_one({"id": iid})
        if imp:
            db["arquivos_importados.files"].delete_one({"_id": imp["file_id"]})
            db["arquivos_importados.chunks"].delete_many({"files_id": imp["file_id"]})
            db.importacoes.delete_one({"id": iid})
    for n in CREATED["alias_norm"]:
        db.school_aliases.delete_one({"alias_norm": n})


def upload(name, text):
    r = requests.post(f"{API}/importacao/upload", headers=H("admin"), files={"file": (name, io.BytesIO(text.encode("utf-8")), "text/csv")})
    assert r.status_code == 200, r.text
    d = r.json()
    CREATED["importacoes"].add(d["id"])
    return d


def cfg(up):
    return {"abas": [{k: a[k] for k in ("sheet", "categoria", "header_row", "mapping", "situacao_padrao")} for a in up["abas"]]}


def school(nome):
    m = requests.get(f"{API}/meta", headers=H("admin")).json()
    return next(e for e in m["escolas"] if e["nome"] == nome)


def check_formula(linhas):
    for r in linhas:
        if r["base"] is None:
            assert r["disponiveis"] is None and r["excedente"] is None
            continue
        assert r["reservadas"] == r["reservadas_situacao"] + r["reservadas_manual"]
        assert r["disponiveis"] == max(0, r["base"] - r["ocupadas"] - r["reservadas"]), r
        assert r["excedente"] == max(0, r["ocupadas"] + r["reservadas"] - r["base"]), r


# ---------- auth / roles ----------
class TestAuth:
    @pytest.mark.parametrize("path", ["/me", "/dashboard", "/vagas", "/servidores", "/escolas"])
    def test_401_without_token(self, path):
        assert requests.get(API + path).status_code == 401

    def test_consulta_forbidden_admin_and_operador(self):
        h = H("consulta")
        sid = school("EM COLÉGIO DE PÁDUA")["id"]
        assert requests.post(f"{API}/importacao/upload", headers=h, files={"file": ("x.csv", b"A;B\n1;2", "text/csv")}).status_code == 403
        assert requests.put(f"{API}/regras", headers=h, json={"etapas": [], "base_calculo": "oficial"}).status_code == 403
        assert requests.put(f"{API}/situacoes/licenca", headers=h, json={"regra": "ocupa", "conta_como_ativo": True}).status_code == 403
        assert requests.get(f"{API}/users", headers=h).status_code == 403
        assert requests.put(f"{API}/distribuicao/{sid}", headers=h, json={"etapas": {}}).status_code == 403
        assert requests.post(f"{API}/reservas", headers=h, json={"school_id": sid, "cargo": "X", "quantidade": 1, "motivo": "abc",
                                                                   "data_reserva": "2026-01-10", "responsavel": "TEST"}).status_code == 403
        assert requests.get(f"{API}/me", headers=h).json()["role"] == "consulta"

    def test_consulta_cpf_masked(self):
        items = requests.get(f"{API}/servidores?page_size=500", headers=H("consulta")).json()["items"]
        with_cpf = [i for i in items if i.get("cpf")]
        for i in with_cpf:
            assert sum(c.isdigit() for c in i["cpf"]) <= 5, i["cpf"]
        print("consulta cpf sample", [i["cpf"] for i in with_cpf[:3]], "count", len(with_cpf))


# ---------- relatórios ----------
class TestReports:
    TIPOS = ["geral", "por_escola", "por_cargo", "por_funcao", "ocupadas", "disponiveis", "reservadas", "deficit_excedente",
             "servidores_unidade", "historico"]

    @pytest.mark.parametrize("tipo", TIPOS)
    def test_pdf_xlsx(self, tipo):
        p = requests.get(f"{API}/relatorios/{tipo}?formato=pdf", headers=H("admin"), timeout=120)
        assert p.status_code == 200 and p.content[:4] == b"%PDF", p.text[:200]
        x = requests.get(f"{API}/relatorios/{tipo}?formato=xlsx", headers=H("admin"), timeout=120)
        assert x.status_code == 200 and x.content[:2] == b"PK"

    def test_historico_forbidden_consulta(self):
        assert requests.get(f"{API}/relatorios/historico", headers=H("consulta")).status_code == 403


# ---------- stateful end-to-end flow ----------
class TestFlow:
    st = {}

    def test_01_quadro_import(self):
        esc = school("EM COLÉGIO DE PÁDUA")
        det = requests.get(f"{API}/escolas/{esc['id']}", headers=H("admin")).json()
        occ = sorted([l for l in det["linhas"] if l["funcao"] == ""], key=lambda l: -l["ocupadas"])
        cargo_a, cargo_b = occ[0]["cargo"], occ[1]["cargo"]
        self.st.update(sid=esc["id"], cargo_a=cargo_a, cargo_b=cargo_b, occ_a=occ[0]["ocupadas"], occ_b=occ[1]["ocupadas"])
        csv_text = (f"ESCOLA;CARGO;QUANTIDADE\nEM COLÉGIO DE PÁDUA;{cargo_a};{occ[0]['ocupadas'] + 3}\n"
                    f"EM COLÉGIO DE PÁDUA;{cargo_b};0\nTEST_ESCOLA INEXISTENTE;{cargo_a};5\n")
        up = upload("TEST_quadro.csv", csv_text)
        assert up["abas"][0]["categoria"] == "quadro", up["abas"][0]
        pv = requests.post(f"{API}/importacao/{up['id']}/previa", headers=H("admin"), json=cfg(up)).json()["planilhas"][0]
        assert pv["novos"] == 2 and len(pv["erros"]) == 1 and "TEST_ESCOLA" in pv["erros"][0]["mensagem"], pv
        assert requests.get(f"{API}/quadro", headers=H("admin")).json() == []  # preview does not write
        cf = requests.post(f"{API}/importacao/{up['id']}/confirmar", headers=H("admin"), json=cfg(up))
        assert cf.status_code == 200
        CREATED["alias_norm"].add("TEST ESCOLA INEXISTENTE")
        db = _db()
        a = db.school_aliases.find_one({"exemplos": "TEST_ESCOLA INEXISTENTE"})
        if a:
            CREATED["alias_norm"].add(a["alias_norm"])
        q = requests.get(f"{API}/quadro", headers=H("admin")).json()
        assert len(q) == 2
        CREATED["quadro"].update(x["id"] for x in q)
        again = requests.post(f"{API}/importacao/{up['id']}/confirmar", headers=H("admin"), json=cfg(up))
        assert again.status_code == 409

    def test_02_dashboard_and_formula(self):
        k = requests.get(f"{API}/dashboard", headers=H("admin")).json()["kpis"]
        assert k["autorizadas_oficiais"] == self.st["occ_a"] + 3
        assert k["quadro_oficial_importado"] is True
        assert k["disponiveis"] == 3 and k["excedentes"] == self.st["occ_b"], k
        linhas = requests.get(f"{API}/vagas", headers=H("admin")).json()["linhas"]
        check_formula(linhas)
        ra = next(l for l in linhas if l["school_id"] == self.st["sid"] and l["cargo"] == self.st["cargo_a"] and l["funcao"] == "")
        assert ra["fonte_base"] == "oficial" and ra["disponiveis"] == 3
        self.st["key_a"] = ra["key"]

    def _row_a(self):
        linhas = requests.get(f"{API}/vagas", headers=H("admin")).json()["linhas"]
        check_formula(linhas)
        return next(l for l in linhas if l["key"] == self.st["key_a"])

    def test_03_reservas(self):
        body = {"school_id": self.st["sid"], "cargo": self.st["cargo_a"], "quantidade": 1, "motivo": "TEST_reserva",
                "data_reserva": "2026-01-10", "responsavel": "TEST_resp"}
        r = requests.post(f"{API}/reservas", headers=H("operador"), json=body)
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        CREATED["reservas"].add(rid)
        assert self._row_a()["disponiveis"] == 2
        u = requests.put(f"{API}/reservas/{rid}", headers=H("operador"), json={**body, "quantidade": 2})
        assert u.status_code == 200
        row = self._row_a()
        assert row["disponiveis"] == 1 and row["reservadas_manual"] == 2
        assert requests.post(f"{API}/reservas/{rid}/efetivar", headers=H("operador"), json={}).status_code == 403
        assert requests.post(f"{API}/reservas/{rid}/efetivar", headers=H("admin"), json={"observacao": "TEST"}).status_code == 200
        assert self._row_a()["disponiveis"] == 3
        assert requests.put(f"{API}/reservas/{rid}", headers=H("admin"), json=body).status_code == 409
        rs = next(x for x in requests.get(f"{API}/reservas", headers=H("admin")).json() if x["id"] == rid)
        assert [h["acao"] for h in rs["historico"]] == ["criada", "alterada", "efetivada"]
        r2 = requests.post(f"{API}/reservas", headers=H("admin"), json=body).json()["id"]
        CREATED["reservas"].add(r2)
        assert requests.post(f"{API}/reservas/{r2}/cancelar", headers=H("admin"), json={}).status_code == 200
        assert self._row_a()["disponiveis"] == 3
        ev = requests.get(f"{API}/vagas/historico", params={"key": self.st["key_a"]}, headers=H("admin")).json()["eventos"]
        acoes = {e["acao"] for e in ev}
        assert {"reserva_vaga", "alteracao_reserva", "efetivacao_reserva", "liberacao_vaga", "alteracao_quadro_autorizado"} <= acoes, acoes

    def test_04_servidores_import_duplicates(self):
        csv1 = ("MAT;SERVIDOR;CARGO;LOTAÇÃO;VÍNCULO;OBS\n"
                f"TEST-0001;TEST_MARIA DUPLICADA;{self.st['cargo_a']};EM COLÉGIO DE PÁDUA;ESTATUTÁRIO;\n"
                f"TEST-0002;TEST_MARIA DUPLICADA;{self.st['cargo_a']};EM COLÉGIO DE PÁDUA;ESTATUTÁRIO;\n"
                f"TEST-0003;TEST_JOAO LICENCA;{self.st['cargo_a']};EM COLÉGIO DE PÁDUA;ESTATUTÁRIO;LICENÇA MÉDICA\n")
        up = upload("TEST_serv.csv", csv1)
        assert up["abas"][0]["categoria"] == "servidores", up["abas"][0]
        pv = requests.post(f"{API}/importacao/{up['id']}/previa", headers=H("admin"), json=cfg(up)).json()["planilhas"][0]
        assert pv["novos"] == 3, pv
        requests.post(f"{API}/importacao/{up['id']}/confirmar", headers=H("admin"), json=cfg(up)).raise_for_status()
        db = _db()
        docs = list(db.servidores.find({"matricula": {"$in": ["TEST-0001", "TEST-0002", "TEST-0003"]}}, {"_id": 0}))
        CREATED["servidores"].update(d["id"] for d in docs)
        a = db.school_aliases.find_one({"exemplos": "EM COLÉGIO DE PÁDUA - LICENÇA MÉDICA"})
        if a and a.get("auto"):
            CREATED["alias_norm"].add(a["alias_norm"])
        assert len([d for d in docs if d["nome"] == "TEST_MARIA DUPLICADA"]) == 2
        self.st["lic"] = next(d for d in docs if d["matricula"] == "TEST-0003")
        print("TEST-0003 situacao", self.st["lic"]["situacao"])
        self.st["s1"] = next(d for d in docs if d["matricula"] == "TEST-0001")["id"]
        # occupation of row increased by the 2 ativos
        row = self._row_a()
        print("row after serv import", row)

    def test_05_reimport_lotacao_change(self):
        csv2 = ("MAT;SERVIDOR;CARGO;LOTAÇÃO;VÍNCULO\n"
                f"TEST-0001;TEST_MARIA DUPLICADA;{self.st['cargo_a']};EM JOÃO JASBIK;ESTATUTÁRIO\n"
                f"TEST-0002;TEST_MARIA DUPLICADA;{self.st['cargo_a']};EM COLÉGIO DE PÁDUA;ESTATUTÁRIO\n")
        up = upload("TEST_serv2.csv", csv2)
        pv = requests.post(f"{API}/importacao/{up['id']}/previa", headers=H("admin"), json=cfg(up)).json()["planilhas"][0]
        assert pv["alterados"] == 1 and pv["sem_alteracao"] == 1, pv
        diff = pv["amostra_alterados"][0]["diff"]
        assert diff["lotacao"]["depois"] == "EM JOÃO JASBIK"
        requests.post(f"{API}/importacao/{up['id']}/confirmar", headers=H("admin"), json=cfg(up)).raise_for_status()
        aud = requests.get(f"{API}/auditoria", params={"acao": "mudanca_lotacao", "q": "TEST-0001"}, headers=H("admin")).json()
        assert aud["total"] >= 1
        sv = requests.get(f"{API}/servidores/{self.st['s1']}", headers=H("admin")).json()
        assert sv["vinculo"]["escola"] == "EM JOÃO JASBIK"
        assert any(o["matricula"] == "TEST-0002" for o in sv["outros_vinculos"])

    def test_06_situacao_rule(self):
        lic = self.st["lic"]
        if lic["situacao"] != "licenca":
            pytest.fail(f"TEST-0003 situacao detected as {lic['situacao']} (expected licenca)")
        sit = next(s for s in requests.get(f"{API}/meta", headers=H("admin")).json()["situacoes"] if s["codigo"] == "licenca")
        before = requests.get(f"{API}/dashboard", headers=H("admin")).json()["kpis"]["ocupadas"]
        try:
            assert requests.put(f"{API}/situacoes/licenca", headers=H("admin"), json={"regra": "libera", "conta_como_ativo": True}).status_code == 200
            after = requests.get(f"{API}/dashboard", headers=H("admin")).json()["kpis"]["ocupadas"]
            print("ocupadas before/after licenca->libera", before, after)
            assert after < before
        finally:
            requests.put(f"{API}/situacoes/licenca", headers=H("admin"),
                         json={"regra": sit["regra"], "conta_como_ativo": sit["conta_como_ativo"], "descricao": sit.get("descricao", "")})
            _db().situacoes.update_one({"codigo": "licenca"}, {"$set": {"sugerida": sit.get("sugerida", True)}})
        assert requests.get(f"{API}/dashboard", headers=H("admin")).json()["kpis"]["ocupadas"] == before

    def test_07_regras(self):
        old = requests.get(f"{API}/regras", headers=H("admin")).json()
        dist = requests.get(f"{API}/distribuicao", headers=H("admin")).json()
        etapa = max(dist["totais"], key=lambda e: dist["totais"][e])
        try:
            body = {"etapas": [{"etapa": etapa, "cargo": "TEST_CARGO REGRA", "fator": 1.5}], "base_calculo": "oficial_ou_previsto"}
            assert requests.put(f"{API}/regras", headers=H("admin"), json=body).status_code == 200
            linhas = requests.get(f"{API}/vagas", headers=H("admin")).json()["linhas"]
            check_formula(linhas)
            rr = [l for l in linhas if l["cargo"] == "TEST_CARGO REGRA"]
            assert rr and all(l["fonte_base"] == "regra" and l["previsto"] == l["base"] for l in rr), rr[:2]
            assert sum(l["previsto"] for l in rr) >= dist["totais"][etapa] * 1.5 - len(rr)
            k = requests.get(f"{API}/dashboard", headers=H("admin")).json()["kpis"]
            assert k["regras_definidas"] == 1 and k["previstas_regra"] > 0
        finally:
            requests.put(f"{API}/regras", headers=H("admin"), json={"etapas": old["etapas"], "base_calculo": old["base_calculo"]})
        new = requests.get(f"{API}/regras", headers=H("admin")).json()
        assert new == old

    def test_08_correspondencia(self):
        c = requests.get(f"{API}/correspondencia", headers=H("admin")).json()
        a = next(x for x in c if "E. M. PEDRO BAPTISTA DE SOUZA" in x["exemplos"])
        assert a["status"] == "pendente" and a["sugestao"] == "EM PEDRO BATISTA DE SOUZA"
        sid = school("EM PEDRO BATISTA DE SOUZA")["id"]
        n0 = len(requests.get(f"{API}/escolas/{sid}", headers=H("admin")).json()["servidores"])
        try:
            assert requests.post(f"{API}/correspondencia/{a['id']}/validar", headers=H("admin"),
                                 json={"acao": "vincular", "school_id": sid}).status_code == 200
            n1 = len(requests.get(f"{API}/escolas/{sid}", headers=H("admin")).json()["servidores"])
            assert n1 >= n0 + a["vinculos"] - 1 and n1 > n0, (n0, n1, a["vinculos"])
        finally:
            requests.post(f"{API}/correspondencia/{a['id']}/validar", headers=H("admin"), json={"acao": "pendente"})
            _db().school_aliases.update_one({"id": a["id"]}, {"$set": {"auto": a.get("auto", True)},
                                                              "$unset": {"validado_por": "", "validado_em": ""}})
        assert len(requests.get(f"{API}/escolas/{sid}", headers=H("admin")).json()["servidores"]) == n0

    def test_09_assistente(self):
        qs = ["Quantas vagas de professor existem disponíveis?", "Quais escolas precisam de professores?",
              "Quantos profissionais estão lotados na escola Sarah Faria Braz?", "Quantas vagas de educação infantil estão abertas?",
              "Existe algum cargo com excesso de servidores?",
              "Quais escolas apresentam divergências entre o quadro de turmas e a relação de servidores?",
              "Quantos servidores possuem mais de uma matrícula?"]
        for q in qs:
            r = requests.post(f"{API}/assistente", headers=H("consulta"), json={"pergunta": q})
            assert r.status_code == 200, q
            d = r.json()
            assert d["resposta"] and "Não identifiquei" not in d["resposta"], (q, d["resposta"])
            print("Q:", q, "->", d["resposta"][:140], "| faltando:", d["faltando"])

    def test_10_cleanup_quadro_then_faltando(self):
        db = _db()
        db.quadro.delete_many({"id": {"$in": list(CREATED["quadro"])}})
        r = requests.post(f"{API}/assistente", headers=H("admin"), json={"pergunta": "Quais escolas precisam de professores?"}).json()
        assert any("quadro oficial" in f for f in r["faltando"]), r
        k = requests.get(f"{API}/dashboard", headers=H("admin")).json()["kpis"]
        assert k["autorizadas_oficiais"] == 0
