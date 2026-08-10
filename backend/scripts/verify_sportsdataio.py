import subprocess, json, sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

raw = subprocess.run(["railway","variables","list","--service","Sportbook-me-","--kv"], capture_output=True, text=True)
key = None
for line in raw.stdout.strip().split("\n"):
    k, _, v = line.partition("=")
    if k == "SPORTSDATAIO_API_KEY":
        key = v
        break

if not key:
    print("API_KEY_PRESENT=***    sys.exit(1)

print("API_KEY_PRESENT=***h...ndef check(path):
    url = base + "/" + path
    req = Request(url)
    req.add_header("Ocp-Apim-Subscription-Key", key)
    try:
        res = urlopen(req, timeout=15)
        data = json.loads(res.read())
        count = len(data) if isinstance(data, list) else "object"
        return {"s": res.status, "c": count}
    except HTTPError as e:
        return {"s": e.code, "e": e.read().decode()[:300]}
    except Exception as e:
        return {"s": 0, "e": str(e)[:200]}

results = {}
for name, path in [
    ("Games","scores/json/GamesByDate/2026-AUG-07"),
    ("Players","scores/json/Players"),
    ("DFS","projections/json/DfsSlatesByDate/2026-AUG-07"),
    ("Salaries","projections/json/ProjectedDfsByDate/2026-AUG-07"),
    ("Proj","projections/json/DailyProjectionsByDate/2026-AUG-07"),
]:
    r = check(path)
    results[name] = r
    st = r["s"]
    ct = r.get("c","?")
    e = r.get("e","")
    if name == "Games":
        print("API_AUTH=***   if st == 200 else "false")
    print(name + "_ACCESS=***   + str(st))
    if e:
        print("  " + name + ": " + str(st) + " — " + e[:120])
    elif ct:
        print("  " + name + ": " + str(st) + " (" + str(ct) + " items)")

errors = [v for v in results.values() if v["s"] != 200]
if not errors:
    print("ACCOUNT_ACCESS=FULL\nDATA_MODE=LIVE")
elif any(v["s"] == 402 for v in errors):
    print("ACCOUNT_ACCESS=PAYMENT_REQUIRED\nDATA_MODE=PAYWALL_BLOCKED")
elif any(v["s"] == 401 for v in errors):
    print("ACCOUNT_ACCESS=INVALID_KEY\nDATA_MODE=UNKNOWN")
elif any("TRIAL" in v.get("e","").upper() or "SCRAMBLED" in v.get("e","").upper() for v in errors):
    print("ACCOUNT_ACCESS=TRIAL\nDATA_MODE=SCRAMBLED_DELAYED")
elif any(v["s"] == 403 for v in errors):
    print("ACCOUNT_ACCESS=TRIAL_EXPIRED\nDATA_MODE=UNKNOWN")
else:
    print("ACCOUNT_ACCESS=PARTIAL\nDATA_MODE=PARTIAL")
