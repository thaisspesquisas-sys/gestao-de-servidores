import json, sys, urllib.request

T = json.load(open("/tmp/tokens.json"))["admin"]
BASE = "http://localhost:8001/api"


def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, method=method.upper(),
                                 headers={"Authorization": "Bearer " + T, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))


up = json.load(open(sys.argv[1]))
skip = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else set()
abas = [{"sheet": a["sheet"], "categoria": "ignorar" if a["sheet"].strip() in skip else a["categoria"], "header_row": a["header_row"],
         "mapping": a["mapping"], "situacao_padrao": a["situacao_padrao"]} for a in up["abas"]]
mode = sys.argv[2]
r = call("post", f"/importacao/{up['id']}/{mode}", {"abas": abas})
for p in r["planilhas"]:
    print(p["sheet"], p["categoria"], "lidos", p["lidos"], "novos", p["novos"], "alt", p["alterados"], "iguais", p["sem_alteracao"],
          "erros", len(p["erros"]), "pend", len(p["escolas_pendentes"]))
    for e in p["erros"][:3]:
        print("   ", e)
    for a in p["amostra_alterados"][:3]:
        print("   ALT", a)
