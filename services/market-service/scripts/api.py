#!/usr/bin/env python3
"""
  ./api.py up                     start postgres (docker compose)
  ./api.py down [-v]              stop postgres (-v also wipes the data)
  ./api.py start                  start the server (mvnw spring-boot:run)
  ./api.py user alice             sign up (creates user, ledger account, wallet)
  ./api.py mint <user-id> 5
  ./api.py redeem <user-id> 2
  ./api.py balances               balance per account and asset, with its owner
  ./api.py <table>                select * from that table
                                  (users wallets accounts ledger_transactions postings
                                   market_transactions mints redeems)
  ./api.py db "select ..."        any SQL
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

SERVICE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
COMPOSE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "..", "..", "infra", "compose.yml")
URL = "http://localhost:8080"
DB = "postgresql://market:market@localhost:5432/market"
SHARE = "11111111-1111-1111-1111-111111111111"
TABLES = ["users", "wallets", "accounts", "ledger_transactions", "postings",
          "market_transactions", "mints", "redeems"]

# accounts without a wallet are platform accounts (one is created per server start)
BALANCES = """
select coalesce(u.username, '(platform)') as owner, p.account_id, p.asset_id, sum(p.amount) as balance
from postings p
left join wallets w on w.account_id = p.account_id
left join users u on u.id = w.user_id
group by 1, 2, 3
order by 1, 3
"""


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
    # PGHOST stops Debian's pg_wrapper warning about a missing local cluster
    subprocess.run(["psql", DB, "-c", q], env={**os.environ, "PGHOST": "localhost"})


cmd, *a = sys.argv[1:] or ["help"]

if cmd == "up":
    subprocess.run(["docker", "compose", "-f", COMPOSE, "up", "-d"])
elif cmd == "down":
    subprocess.run(["docker", "compose", "-f", COMPOSE, "down", *a])
elif cmd == "start":
    subprocess.run(["./mvnw", "spring-boot:run"], cwd=SERVICE_DIR)
elif cmd == "user":
    post("/users", {"owner": a[0]})
elif cmd in ("mint", "redeem"):
    post(f"/market/{cmd}", {"userId": a[0], "amount": int(a[1]), "playerShare": SHARE})
elif cmd == "balances":
    sql(BALANCES)
elif cmd in TABLES:
    sql(f"select * from {cmd}")
elif cmd == "db":
    sql(a[0])
else:
    print(__doc__)
