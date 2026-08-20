import json
import ssl
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
jobs = json.loads(Path("data/discovery_batch.json").read_text(encoding="utf-8"))
done = {"7807811003", "7807736003", "4129751009", "8074590", "7985640", "7517648003", "7490280003", "7807746003", "5177393007"}
out = {}
for job in jobs:
    if job.get("ats") != "Greenhouse":
        continue
    jid = str(job.get("job_id") or "")
    board = job.get("company")
    if not jid or jid in done:
        continue
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}?questions=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        qs = []
        for q in data.get("questions") or []:
            qs.append({
                "label": q.get("label"),
                "required": q.get("required"),
                "fields": [{"name": f.get("name"), "type": f.get("type"), "values": f.get("values")} for f in (q.get("fields") or [])],
            })
        out[f"{board}:{jid}"] = {"title": data.get("title"), "questions": qs}
        print(board, jid, len(qs), "questions")
    except Exception as e:
        print("FAIL", board, jid, e)

# also redwood already submitted - learn from it
for board, jid in (("redwoodsoftware", "4129751009"), ("highradius", "7807811003")):
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}?questions=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        qs = [{"label": q.get("label"), "required": q.get("required"),
               "fields": [{"name": f.get("name"), "type": f.get("type"), "values": f.get("values")} for f in (q.get("fields") or [])]}
              for q in data.get("questions") or []]
        out[f"{board}:{jid}"] = {"title": data.get("title"), "questions": qs}
        print("LEARN", board, jid, len(qs))
    except Exception as e:
        print("FAIL learn", board, jid, e)

Path("data/remaining_questions.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
