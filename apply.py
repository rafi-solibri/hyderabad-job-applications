"""Submit applications to Greenhouse and Lever career portals and verify each one."""
from __future__ import annotations

import json
import mimetypes
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANDIDATE = json.loads((ROOT / "data" / "candidate.json").read_text(encoding="utf-8"))
RESUME = ROOT / CANDIDATE["resumePath"]
LOG = ROOT / "data" / "applications" / "log.jsonl"
RESULTS = ROOT / "data" / "applications" / "results.json"
CTX = ssl.create_default_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

EXTRA_JOBS = [
    {
        "company": "Keyloop",
        "title": "Principle Software Architect",
        "location": "India (Hyderabad)",
        "url": "https://jobs.lever.co/keyloop/c2142ca2-378f-4868-b51d-a7819a1e4a9d",
        "ats": "Lever",
        "job_id": "c2142ca2-378f-4868-b51d-a7819a1e4a9d",
        "board": "keyloop",
    },
    {
        "company": "Dun & Bradstreet",
        "title": "Principle Engineer – Java and Cloud",
        "location": "Hyderabad - India",
        "url": "https://jobs.lever.co/dnb/d5c26842-0658-4101-93fe-18615b91d198",
        "ats": "Lever",
        "job_id": "d5c26842-0658-4101-93fe-18615b91d198",
        "board": "dnb",
    },
    {
        "company": "Cprime",
        "title": "ServiceNow Technical Architect",
        "location": "Hyderabad, India",
        "url": "https://jobs.lever.co/cprime/5411042f-1539-4121-9b5b-11ec98878fcd",
        "ats": "Lever",
        "job_id": "5411042f-1539-4121-9b5b-11ec98878fcd",
        "board": "cprime",
    },
]

SKIP_TITLE = re.compile(
    r"vmware|windows\)|infra architect|associate architect|ai/ml|presales|pre-sales|account manager",
    re.I,
)


def http(url, data=None, headers=None, method=None, timeout=45):
    h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read() if e.fp else b""
    except Exception as e:
        return 0, {}, str(e).encode()


def get_json(url):
    status, _, body = http(url)
    if status != 200:
        return None, status
    try:
        return json.loads(body.decode("utf-8", errors="replace")), status
    except Exception:
        return None, status


def log_event(event):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def answer_text(question: str) -> str | None:
    q = question.lower()
    c = CANDIDATE
    if any(k in q for k in ("linkedin", "linked in")):
        return c["linkedIn"]
    if "github" in q or "portfolio" in q or "website" in q:
        return c["linkedIn"]
    if "current company" in q or "current employer" in q or "present employer" in q:
        return c["currentEmployer"]
    if "current title" in q or "current role" in q or "job title" in q:
        return c["currentRole"]
    if "notice" in q:
        return c["noticePeriod"]
    if "current ctc" in q or "current salary" in q or "current compensation" in q:
        return str(c["currentCtcInr"])
    if "expected ctc" in q or "expected salary" in q or "desired salary" in q or "salary expectation" in q:
        return str(c["expectedCtcInr"])
    if "ctc" in q or "compensation" in q or "salary" in q:
        return f"Current {c['currentCtcLpa']} LPA, expected {c['expectedCtcLpa']} LPA"
    if "year" in q and "experience" in q:
        return str(c["yearsExperience"])
    if "city" in q:
        return c["city"]
    if "state" in q or "province" in q:
        return c["state"]
    if "country" in q and "work" not in q:
        return c["country"]
    if "address" in q:
        return f"{c['city']}, {c['state']}, {c['country']}"
    if "hear about" in q or "how did you" in q or "source" in q:
        return c["howHeard"]
    if "sponsor" in q or "visa" in q:
        return "No"
    if "authorized" in q or "right to work" in q or "legally" in q:
        return "Yes"
    if "relocat" in q:
        return "No - Hyderabad only (Madhapur / Gachibowli / Financial District)"
    if "gender" in q:
        return c["gender"]
    if "cover letter" in q or "why do you" in q or "why are you" in q or "additional information" in q:
        return (
            f"I am a Technical Architect with {c['yearsExperience']}+ years designing .NET, cloud, "
            "and distributed systems. I am based in Hyderabad and targeting roles in Madhapur, "
            "Gachibowli, and Financial District. Current CTC 52 LPA, expected 60 LPA, immediate joiner."
        )
    return None


def pick_choice(question: str, options: list) -> str | None:
    q = question.lower()
    labels = []
    for opt in options:
        if isinstance(opt, dict):
            labels.append((str(opt.get("label") or opt.get("value") or ""), str(opt.get("value") or opt.get("label") or "")))
        else:
            labels.append((str(opt), str(opt)))

    def find(*needles):
        for label, value in labels:
            low = label.lower()
            if any(n in low for n in needles):
                return value
        return None

    if any(k in q for k in ("sponsor", "visa", "require sponsorship")):
        return find("no", "not required") or find("no")
    if any(k in q for k in ("authorized", "right to work", "legally authorized", "work permit")):
        return find("yes", "citizen") or find("yes")
    if "relocat" in q:
        return find("no")
    if "hear" in q or "source" in q:
        return find("career", "company website", "website") or find("other")
    if "gender" in q or "sex" in q:
        return find("male") or find("decline", "don't wish", "not wish")
    if "race" in q or "ethnicity" in q or "veteran" in q or "disability" in q or "lgbt" in q:
        return find("decline", "don't wish", "not wish", "prefer not")
    if "hyderabad" in q or "location" in q and "prefer" in q:
        return find("hyderabad")
    if "notice" in q:
        return find("immediate", "0", "serving") or find("immediate")
    return None


class MultipartForm:
    def __init__(self):
        self.boundary = "----RafiApply" + str(int(time.time() * 1000))
        self.parts: list[bytes] = []

    def add_field(self, name: str, value: str):
        block = (
            f"--{self.boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode("utf-8")
        self.parts.append(block)

    def add_file(self, name: str, path: Path):
        data = path.read_bytes()
        filename = path.name
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        header = (
            f"--{self.boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode("utf-8")
        self.parts.append(header + data + b"\r\n")

    def body(self) -> bytes:
        return b"".join(self.parts) + f"--{self.boundary}--\r\n".encode()

    def content_type(self) -> str:
        return f"multipart/form-data; boundary={self.boundary}"


def apply_greenhouse(job: dict) -> dict:
    board = job.get("board") or job.get("company")
    jid = job["job_id"]
    detail, status = get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}?questions=true")
    if not detail:
        return {"ok": False, "status": status, "detail": "Could not load Greenhouse job questions"}

    form = MultipartForm()
    form.add_field("first_name", CANDIDATE["firstName"])
    form.add_field("last_name", CANDIDATE["lastName"])
    form.add_field("email", CANDIDATE["email"])
    form.add_field("phone", CANDIDATE["phone"])
    if RESUME.exists():
        form.add_file("resume", RESUME)

    unanswered = []
    for q in detail.get("questions") or []:
        name = str(q.get("name") or q.get("label") or "")
        label = str(q.get("label") or name)
        qid = str(q.get("id") or "")
        required = bool(q.get("required"))
        fields = q.get("fields") or [{"name": name, "type": q.get("type"), "values": q.get("values")}]
        for field in fields:
            fname = field.get("name") or name or qid
            ftype = (field.get("type") or q.get("type") or "input_text").lower()
            if fname in {"first_name", "last_name", "email", "phone", "resume", "cover_letter"}:
                continue
            options = field.get("values") or q.get("values") or []
            value = None
            if options:
                value = pick_choice(label, options)
            if value is None:
                value = answer_text(label)
            if value is None and required:
                unanswered.append(label)
                continue
            if value is not None:
                form.add_field(str(fname), str(value))

    status, headers, body = http(
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}",
        data=form.body(),
        headers={"Content-Type": form.content_type()},
    )
    text = body.decode("utf-8", errors="replace")[:1500]
    ok = status in (200, 201) and "error" not in text.lower()
    return {
        "ok": ok,
        "status": status,
        "unanswered": unanswered,
        "response": text,
        "success_hint": headers.get("Location") or "",
    }


def apply_lever(job: dict) -> dict:
    board = job.get("board") or job["company"].lower().replace(" ", "")
    jid = job["job_id"]
    form = MultipartForm()
    form.add_field("name", CANDIDATE["fullName"])
    form.add_field("email", CANDIDATE["email"])
    form.add_field("phone", CANDIDATE["phone"])
    form.add_field("org", CANDIDATE["currentEmployer"])
    form.add_field("urls[LinkedIn]", CANDIDATE["linkedIn"])
    form.add_field(
        "comments",
        (
            f"Technical Architect, {CANDIDATE['yearsExperience']}+ years, Hyderabad. "
            f"Current CTC {CANDIDATE['currentCtcLpa']} LPA, expected {CANDIDATE['expectedCtcLpa']} LPA, "
            f"notice {CANDIDATE['noticePeriod']}. Targeting Madhapur / Gachibowli / Financial District."
        ),
    )
    if RESUME.exists():
        form.add_file("resume", RESUME)

    urls = [
        f"https://api.lever.co/v0/postings/{board}/{jid}?apply",
        f"https://jobs.lever.co/{board}/{jid}",
    ]
    last = {"ok": False, "status": 0, "response": "no attempt"}
    for url in urls:
        status, _, body = http(url, data=form.body(), headers={"Content-Type": form.content_type()})
        text = body.decode("utf-8", errors="replace")[:1500]
        ok = status in (200, 201, 204) and "error" not in text.lower()
        last = {"ok": ok, "status": status, "response": text, "endpoint": url}
        if ok:
            return last
    return last


def load_jobs() -> list[dict]:
    hyd = json.loads((ROOT / "data" / "hyd_jobs.json").read_text(encoding="utf-8"))
    jobs = []
    for j in hyd:
        if SKIP_TITLE.search(j.get("title") or ""):
            continue
        if j["ats"] == "Greenhouse":
            j = dict(j)
            j["board"] = j["company"]
        jobs.append(j)
    jobs.extend(EXTRA_JOBS)
    seen = set()
    out = []
    for j in jobs:
        key = (j["company"].lower(), j["title"].lower(), j.get("job_id"))
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


def main():
    if not RESUME.exists():
        raise SystemExit(f"Resume missing: {RESUME}")
    jobs = load_jobs()
    print(f"Applying to {len(jobs)} jobs", flush=True)
    results = []
    for job in jobs:
        print(f"\n-> {job['company']}: {job['title']}", flush=True)
        if job["ats"] == "Greenhouse":
            result = apply_greenhouse(job)
        elif job["ats"] == "Lever":
            result = apply_lever(job)
        else:
            result = {"ok": False, "status": 0, "detail": f"{job['ats']} requires account login; skipped for verified apply"}
        row = {**job, **result}
        results.append(row)
        log_event({"event": "apply", **row})
        print(f"   ok={row.get('ok')} status={row.get('status')} {str(row.get('detail') or row.get('response') or '')[:180]}", flush=True)
        time.sleep(1.2)

    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    applied = [r for r in results if r.get("ok")]
    failed = [r for r in results if not r.get("ok")]
    print(f"\nSubmitted: {len(applied)}  Failed/blocked: {len(failed)}")


if __name__ == "__main__":
    main()
