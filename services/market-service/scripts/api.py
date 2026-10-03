#!/usr/bin/env python3
"""
  ./api.py init
  ./api.py user alice
  ./api.py mint <user-id> 5
  ./api.py redeem <user-id> 2
  ./api.py <table>                select * from that table
                                  (users accounts user_accounts platform_account
                                   transactions mints redeems postings)
  ./api.py db "select ..."        any SQL
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

URL = "http://localhost:8080"
DB = "postgresql://market:market@localhost:5432/market"
SHARE = "11111111-1111-1111-1111-111111111111"
TABLES = ["users", "accounts", "user_accounts", "platform_account",
          "transactions", "mints", "redeems", "postings"]


def post(path, body=None):
    req = urllib.request.Request(
        URL + path, method="POST",
        data=json.dumps(body).encode() if body is not None else b"",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            print(r.status, r.read().decode())
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode())
    except urllib.error.URLError as e:
        sys.exit(f"cannot reach {URL}: {e.reason}")


def sql(q):
    subprocess.run(["psql", DB, "-c", q])


cmd, *a = sys.argv[1:] or ["help"]

if cmd == "init":
    post("/market/init")
elif cmd == "user":
    post("/users", {"owner": a[0]})
elif cmd in ("mint", "redeem"):
    post(f"/market/{cmd}", {"user": a[0], "amount": int(a[1]), "playerShare": SHARE})
elif cmd in TABLES:
    sql(f"select * from {cmd}")
elif cmd == "db":
    sql(a[0])
else:
    print(__doc__)
