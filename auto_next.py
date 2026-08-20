"""Mark the current job submitted from the Firefox title and open exactly one next tab."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import apply_now

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "data" / "auto_slot.json"
FF = Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "firefox.exe"


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done_titles": [], "open_ids": []}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def match_job(title: str, jobs: list[dict]) -> dict | None:
    t = (title or "").lower()
    best = None
    best_n = 0
    for job in jobs:
        name = (job.get("title") or "").lower()
        words = [w for w in name.replace("—", " ").replace("-", " ").split() if len(w) > 3]
        hits = sum(1 for w in words if w in t)
        if hits > best_n and hits >= 2:
            best, best_n = job, hits
        jid = str(job.get("job_id") or "")
        if jid and jid.lower() in t:
            return job
    return best


def job_url(job: dict) -> str:
    url = job.get("apply_url") or apply_now.apply_url(job) or job.get("url") or ""
    if job.get("ats") == "Lever" and url and not url.rstrip("/").endswith("/apply"):
        url = url.rstrip("/") + "/apply"
    return url


def main() -> None:
    title = " ".join(sys.argv[1:]).strip()
    if not title:
        print("NO_TITLE")
        return
    state = load_state()
    key = title[:120]
    if key in state.get("done_titles", []):
        print("ALREADY_HANDLED")
        return

    apply_now.BATCH = apply_now.load_all_discovered()
    pending = apply_now.queue()
    discovered = apply_now.BATCH
    job = match_job(title, pending) or match_job(title, discovered)
    if not job:
        print("NO_MATCH", title[:80])
        return

    jid = str(job.get("job_id") or "")
    apply_now.persist_applied(job, "auto-detected submit from Firefox")
    state.setdefault("done_titles", []).append(key)
    open_ids = [x for x in state.get("open_ids", []) if x != jid]
    apply_now.BATCH = apply_now.load_all_discovered()
    left = apply_now.queue()
    nxt = next(
        (
            j
            for j in left
            if str(j.get("job_id") or "") not in open_ids
            and apply_now.company_key(j.get("company")) not in apply_now.SKIP_COMPANIES
        ),
        None,
    )
    if nxt:
        try:
            import tailor_resume
            path = tailor_resume.for_job(nxt)
            print(f"TAILORED {path}")
            print(f"HEADLINE {tailor_resume.CURRENT.get('headline')}")
        except Exception as exc:
            print(f"TAILOR_FAIL {exc}")
        url = job_url(nxt)
        print(f"OPEN {nxt.get('company')}: {nxt.get('title')}")
        print(url)
        subprocess.Popen([str(FF), "-new-tab", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        nid = str(nxt.get("job_id") or "")
        if nid:
            open_ids.append(nid)
        time.sleep(1.2)
    else:
        print("NO_NEXT")
    state["open_ids"] = open_ids[-3:]
    save_state(state)
    print(f"NOTED SUBMITTED: {job.get('company')}: {job.get('title')}")
    print(f"PENDING {len(left) - (1 if nxt else 0) if nxt else len(left)}")


if __name__ == "__main__":
    main()
