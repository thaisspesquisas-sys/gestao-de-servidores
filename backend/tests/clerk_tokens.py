import os, json, sys, urllib.request, urllib.error
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
SK = os.environ["CLERK_SECRET_KEY"]
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def bapi(path, body=None, method="POST"):
    req = urllib.request.Request("https://api.clerk.com/v1" + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": "Bearer " + SK, "Content-Type": "application/json", "User-Agent": "emergent-test"})
    return json.load(urllib.request.urlopen(req))


def user(email):
    found = bapi(f"/users?email_address={urllib.parse.quote(email)}", method="GET")
    if found:
        return found[0]
    return bapi("/users", {"email_address": [email], "password": "Test-pass-12345!", "skip_password_checks": True})


import urllib.parse
out = {}
for email, role in [("admin+clerk_test@example.com", "admin"), ("consulta+clerk_test@example.com", "consulta"),
                    ("operador+clerk_test@example.com", "operador")]:
    u = user(email)
    db.users.update_one({"user_id": u["id"]}, {"$set": {"user_id": u["id"], "role": role, "env": "preview", "email": email}}, upsert=True)
    s = bapi("/sessions", {"user_id": u["id"]})
    out[role] = bapi(f"/sessions/{s['id']}/tokens", {"expires_in_seconds": 3600})["jwt"]
    if len(sys.argv) > 1 and sys.argv[1] == "ticket":
        out[role + "_ticket"] = bapi("/sign_in_tokens", {"user_id": u["id"], "expires_in_seconds": 3600})["token"]
json.dump(out, open("/tmp/tokens.json", "w"))
print("ok", list(out))
