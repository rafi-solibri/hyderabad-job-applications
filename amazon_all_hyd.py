import json, ssl, urllib.parse, urllib.request, re
from pathlib import Path

CTX = ssl.create_default_context()
UA = "Mozilla/5.0"
HYD = re.compile(r"hyderabad|telangana", re.I)
TITLE = re.compile(
    r"architect|principal|staff|lead|senior|sde|software development engineer|software engineer",
    re.I,
)
SKIP = re.compile(r"intern|campus|recruiter|account executive", re.I)

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, context=CTX, timeout=25) as resp:
        return json.loads(resp.read().decode())

jobs = []
for q in ("", "software"):
    for offset in range(0, 400, 100):
        qs = urllib.parse.urlencode({
            "base_query": q,
            "loc_query": "Hyderabad, Telangana, India",
            "result_limit": 100,
            "offset": offset,
        })
        data = get(f"https://www.amazon.jobs/en/search.json?{qs}")
        batch = data.get("jobs") or []
        print(q, offset, len(batch), "hits", data.get("hits", "?"))
        for item in batch:
            loc = f"{item.get('city_name','')} {item.get('location','')}"
            title = item.get("title") or ""
            if not HYD.search(loc) or not TITLE.search(title) or SKIP.search(title):
                continue
            jid = item.get("id_icims") or item.get("id")
            jobs.append({
                "company": "Amazon",
                "title": title,
                "location": loc,
                "url": f"https://www.amazon.jobs/en/jobs/{jid}",
                "ats": "Amazon",
                "job_id": str(jid),
                "already_applied": False,
            })
        if not batch:
            break

# merge
existing = json.loads(Path("data/discovery_all_matched.json").read_text(encoding="utf-8"))
allj = existing + jobs
seen, unique = set(), []
for j in allj:
    key = (j["company"].lower(), j["title"].lower(), str(j.get("job_id") or "")[:40])
    if key in seen:
        continue
    seen.add(key)
    unique.append(j)
openj = [j for j in unique if not j.get("already_applied")]
Path("data/discovery_all_matched.json").write_text(json.dumps(unique, indent=2), encoding="utf-8")
Path("data/discovery_batch.json").write_text(json.dumps(openj[:300], indent=2), encoding="utf-8")
print("unique", len(unique), "open", len(openj))
