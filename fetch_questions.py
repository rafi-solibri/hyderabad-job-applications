import json
import ssl
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
UA = "Mozilla/5.0"
jobs = [
    ("crunchyroll", "8074590"),
    ("crunchyroll", "7985640"),
    ("zscaler", "5177393007"),
    ("inovalon", "7517648003"),
    ("highradius", "7490280003"),
    ("highradius", "7807746003"),
]
out = {}
for board, jid in jobs:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}?questions=true"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=25) as resp:
            data = json.loads(resp.read().decode())
        qs = []
        for q in data.get("questions") or []:
            qs.append({
                "label": q.get("label"),
                "required": q.get("required"),
                "fields": [
                    {"name": f.get("name"), "type": f.get("type"), "values": f.get("values")}
                    for f in (q.get("fields") or [])
                ],
            })
        out[f"{board}:{jid}"] = {"title": data.get("title"), "location": (data.get("location") or {}).get("name"), "questions": qs}
        print(board, jid, "questions", len(qs))
    except Exception as e:
        print(board, jid, "FAIL", e)
Path("data/gh_questions.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
