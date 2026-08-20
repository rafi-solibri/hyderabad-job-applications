"""Headed Amazon.jobs apply. Max 4. No DevOps. Opens the apply form directly."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

import firefox_browser
import form_memory

ROOT = Path(__file__).resolve().parent
C = json.loads((ROOT / "data" / "candidate.json").read_text(encoding="utf-8"))
RESUME = str((ROOT / C["resumePath"]).resolve())
BATCH = json.loads((ROOT / "data" / "discovery_batch.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "data" / "applications" / "amazon_results.json"
LOG = ROOT / "data" / "applications" / "log.jsonl"
PROFILE = ROOT / "data" / "browser_profile"
MAX_PER_COMPANY = 3
WAIT_SECONDS = 240
SKIP_TITLE = re.compile(r"devops|devsecops|site reliability|\bsre\b|tech ops|rack manufacturing", re.I)
DONE_IDS = {"10403400"}


def log(event):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def quiet_click(locator, timeout=2000):
    try:
        locator.click(timeout=timeout)
        return True
    except Exception:
        return False


def is_success(page) -> bool:
    try:
        url = page.url.lower()
        if "result=success" in url or "/summary" in url:
            return True
        if any(x in url for x in ("confirmation", "application-success", "thank-you", "/thanks")):
            return True
        text = page.inner_text("body")
        return bool(re.search(
            r"application (was |has been )?(submitted|received)|thank you for applying|"
            r"we.?ve received your application|successfully submitted|application submitted",
            text, re.I,
        ))
    except Exception:
        return False


def needs_login(page) -> bool:
    try:
        url = page.url.lower()
        if any(x in url for x in ("signin", "sign-in", "ap/signin", "/ap/")):
            return True
        text = page.inner_text("body")[:600].lower()
        return "sign in" in text and "password" in text
    except Exception:
        return False


def apply_url(job: dict) -> str:
    jid = job.get("job_id") or ""
    return f"https://account.amazon.jobs/en-US/applicant/jobs/{jid}/apply"


def queue() -> list[dict]:
    done = set(DONE_IDS)
    if RESULTS.exists():
        for row in json.loads(RESULTS.read_text(encoding="utf-8")):
            if row.get("ok") or "result=success" in str(row.get("final_url") or ""):
                done.add(str(row.get("job_id") or ""))
    jobs = []
    for job in BATCH:
        if job.get("ats") != "Amazon" or job.get("already_applied"):
            continue
        if SKIP_TITLE.search(job.get("title") or ""):
            continue
        if str(job.get("job_id") or "") in done:
            continue
        row = dict(job)
        row["apply_url"] = apply_url(job)
        jobs.append(row)
    jobs.sort(key=lambda j: (-int(j.get("score") or 0), j.get("title") or ""))
    return jobs[:MAX_PER_COMPANY]


def fill_amazon(page, job=None):
    for sel, value in (
        ("input[name='firstName'], input[id*='firstName'], input[autocomplete='given-name']", C["firstName"]),
        ("input[name='lastName'], input[id*='lastName'], input[autocomplete='family-name']", C["lastName"]),
        ("input[type='email'], input[name='email'], input[autocomplete='email']", C["email"]),
        ("input[type='tel'], input[name='phone'], input[autocomplete='tel']", "8790251698"),
        ("input[name='linkedIn'], input[id*='linkedin' i]", C["linkedIn"]),
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.fill(value, timeout=1200)
        except Exception:
            continue
    try:
        page.locator("input[type=file]").first.set_input_files(RESUME, timeout=3000)
    except Exception:
        pass
    form_memory.auto_complete(page, job)


def main():
    form_memory.seed_from_learned()
    jobs = queue()
    print(f"Continuing Amazon: {len(jobs)} jobs. Sign in once if asked, then submit each form.", flush=True)
    for j in jobs:
        print(f"  - {j['title']}", flush=True)
    results = []
    if RESULTS.exists():
        try:
            results = json.loads(RESULTS.read_text(encoding="utf-8"))
        except Exception:
            results = []
    with sync_playwright() as p:
        context = firefox_browser.launch_firefox(p)
        page = context.pages[0] if context.pages else context.new_page()
        firefox_browser.ensure_simplify(page)
        for i, job in enumerate(jobs, 1):
            print(f"\n[{i}/{len(jobs)}] Amazon: {job['title']}", flush=True)
            try:
                page.goto(job["apply_url"], wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(1800)
                page.bring_to_front()
                if needs_login(page):
                    print("  YOUR TURN: sign in to amazon.jobs.", flush=True)
                    deadline = time.time() + WAIT_SECONDS
                    while time.time() < deadline and needs_login(page):
                        page.wait_for_timeout(2000)
                    page.goto(job["apply_url"], wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(1200)
                if is_success(page) or "already applied" in page.inner_text("body")[:500].lower():
                    row = {**job, "ok": True, "status": "SUBMITTED", "final_url": page.url}
                else:
                    firefox_browser.trigger_simplify(page)
                    fill_amazon(page, job)
                    firefox_browser.trigger_simplify(page)
                    print("  YOUR TURN: finish remaining fields and click Submit. I will wait 4 minutes.", flush=True)
                    deadline = time.time() + WAIT_SECONDS
                    ok = False
                    last_learn = 0
                    while time.time() < deadline:
                        if is_success(page):
                            ok = True
                            break
                        if time.time() - last_learn > 8:
                            form_memory.remember(page, job)
                            last_learn = time.time()
                        page.wait_for_timeout(2000)
                    row = {**job, "ok": ok, "status": "SUBMITTED" if ok else "WAITING_EXPIRED", "final_url": page.url}
            except Exception as e:
                row = {**job, "ok": False, "status": "ERROR", "note": str(e)[:300]}
            results.append(row)
            log({"event": "amazon_apply", **{k: v for k, v in row.items() if k != "confirmation"}})
            print(f"  {row.get('status')} ok={row.get('ok')}", flush=True)
            RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        context.close()
    print(f"\nDone. Submitted {sum(1 for r in results if r.get('ok'))} / {len(results)}", flush=True)


if __name__ == "__main__":
    main()
