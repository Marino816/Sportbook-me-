import subprocess, json, sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

raw = subprocess.run(["railway","variables","list","--service","Sportbook-me-","--kv"], capture_output=True, text=True)
secret = None
for ln in raw.stdout.strip().split("\n"):
    if ln.startswith("SPORTSDATAIO_API_KEY=***        secret = ln.partition("=")[2]
        break

if secret is None:
    print("API_KEY_PRESENT=***    sys.exit(1)

def chk(path):
    u = "https://api.sportsdata.io/v3/mlb/" + path
    r = Request(u)
    r.add_header("Ocp-Apim-Subscription-Key", secret)
    try:
        res = urlopen(r, timeout=15)
        d = json.loads(res.read())
        c = len(d) if isinstance(d, list) else "object"
        return res.status, c, None
    except HTTPError as e:
        return e.code, None, e.read().decode()[:300]
    except Exception as e:
        return 0, None, str(e)[:200]

tests = [
    ("Games","scores/json/GamesByDate/2026-AUG-07"),
    ("Players","scores/json/Players"),
    ("DFS","projections/json/DfsSlatesByDate/2026-AUG-07"),
    ("Salary","projections/json/ProjectedDfsByDate/2026-AUG-07"),
    ("Proj","projections/json/DailyProjectionsByDate/2026-AUG-07"),
]

all_ok = True
for name, path in tests:
    s, c, e = chk(path)
    ok = s == 200
    if name == "Games":
        print("API_AUTH=***  if ok else "false")
    print(name + "_ACCESS=***  + str(s))
    if e:
        print("  " + name + ": " + str(s) + " " + e[:120])
        all_ok = False
    else:
        print("  " + name + ": " + str(s) + " (" + str(c) + " items)")

failed = [(name, path) for name, path in tests if chk(path)[0] != 200]
# Reuse cached results
codes = {name: chk(path)[0] for name, path in tests}
codes = {name: s for name, path in tests for s,c,e in [chk(path)]}
# Just use what we have
if all_ok:
    print("ACCOUNT_ACCESS=FULL")
    print("DATA_MODE=LIVE")
else:
    print("ACCOUNT_ACCESS=LIMITED")
    print("DATA_MODE=SEE_ABOVE")
