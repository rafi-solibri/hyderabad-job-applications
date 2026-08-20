"""Drive the already-open headed Chrome (CDP 9222). Does not launch or kill Chrome.

Waits if a CAPTCHA is on screen. After submit, continues the public ATS queue.
Fills stored login credentials when a password field appears (never prints them).
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

import apply_now
import cloud_apply
import form_memory
import tailor_resume

ROOT = Path(__file__).resolve().parent
CDP = "http://127.0.0.1:9222"
RESUME = str((ROOT / apply_now.C["resumePath"]).resolve())
LESSONS = ROOT / "data" / "applications" / "headed_lessons.jsonl"


def stored_login() -> tuple[str, str]:
    mem = json.loads((ROOT / "data" / "field_memory.json").read_text(encoding="utf-8"))
    by = mem.get("by_label") or {}
    email = apply_now.C["email"]
    password = ""
    for key, row in by.items():
        if "password" in key and row.get("value"):
            password = str(row["value"])
            break
    return email, password


def captcha_visible(page) -> bool:
    try:
        n = page.locator("iframe[title*='hCaptcha' i], iframe[src*='hcaptcha'], iframe[src*='recaptcha'], iframe[title*='captcha' i]").count()
        if n:
            for i in range(min(n, 6)):
                loc = page.locator("iframe[title*='hCaptcha' i], iframe[src*='hcaptcha'], iframe[src*='recaptcha'], iframe[title*='captcha' i]").nth(i)
                try:
                    if loc.is_visible():
                        box = loc.bounding_box() or {}
                        if (box.get("width") or 0) > 80 and (box.get("height") or 0) > 80:
                            return True
                except Exception:
                    continue
        blob = (page.inner_text("body") or "")[:2500]
        if re.search(r"drag the shape|select all|i.?m not a robot|verify you are human", blob, re.I):
            return True
    except Exception:
        return False
    return False


def try_login(page) -> bool:
    email, password = stored_login()
    if not password:
        return False
    pw = page.locator("input[type=password]").first
    if not pw.count() or not pw.is_visible():
        return False
    try:
        for sel in ("input[type=email]", "input[name=username]", "input[name=email]", "input[name=session_key]", "#username"):
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                cur = ""
                try:
                    cur = loc.input_value() or ""
                except Exception:
                    pass
                if not cur:
                    loc.fill(email, timeout=1500)
                break
        pw.fill(password, timeout=1500)
        for name in ("Sign in", "Log in", "Continue", "Next", "Sign In", "Log In"):
            btn = page.get_by_role("button", name=re.compile(rf"^{re.escape(name)}$", re.I)).first
            if btn.count() and btn.is_visible():
                btn.click(timeout=2000)
                page.wait_for_timeout(2000)
                return True
        page.keyboard.press("Enter")
        page.wait_for_timeout(2000)
        return True
    except Exception:
        return False


def persist(row: dict) -> None:
    if row.get("ok") and row.get("status") == "SUBMITTED":
        apply_now.persist_applied(row, row.get("note") or "headed chrome submitted")
    apply_now.log({"event": "headed_session", **{k: v for k, v in row.items() if k != "confirmation"}})
    cloud_apply.save_cloud([row])
    LESSONS.parent.mkdir(parents=True, exist_ok=True)
    with LESSONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **row}, ensure_ascii=False) + "\n")


def wait_captcha_or_submit(page, job: dict, seconds: int = 300) -> dict:
    print("  CAPTCHA or leftover fields on screen. Complete them in Chrome; I will detect submit.", flush=True)
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            form_memory.remember(page, job)
        except Exception:
            pass
        if cloud_apply.is_success(page):
            return {"ok": True, "status": "SUBMITTED", "note": "submitted after human captcha/login"}
        # Do not fill_visible here — it resets dropdowns while a human is on CAPTCHA.
        if not captcha_visible(page):
            try_login(page)
            if cloud_apply.is_success(page):
                return {"ok": True, "status": "SUBMITTED", "note": "submitted after captcha cleared"}
        page.wait_for_timeout(3000)
    return {"ok": False, "status": "WAITING_EXPIRED", "note": "captcha/login still open"}


def apply_current(page, job: dict) -> dict:
    url = job.get("apply_url") or apply_now.apply_url(job) or job.get("url") or ""
    row = {
        **{k: job.get(k) for k in ("company", "title", "location", "url", "ats", "job_id")},
        "apply_url": url,
        "ok": False,
        "status": "INCOMPLETE",
        "final_url": page.url,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if cloud_apply.is_success(page):
        row["ok"] = True
        row["status"] = "SUBMITTED"
        row["note"] = "already submitted"
        return row
    if captcha_visible(page):
        human = wait_captcha_or_submit(page, job, 300)
        row.update(human)
        row["final_url"] = page.url
        return row
    try_login(page)
    try:
        job["resume_path"] = tailor_resume.for_job(job)
    except Exception:
        job["resume_path"] = RESUME
    cloud_apply.dismiss_overlays(page)
    cloud_apply.click_apply_gate(page)
    cloud_apply.fill_identity(page)
    tailor_resume.upload(page, job.get("resume_path"))
    form_memory.fill_visible(page)
    form_memory.remember(page, job)
    for _ in range(5):
        if cloud_apply.is_success(page):
            row["ok"] = True
            row["status"] = "SUBMITTED"
            row["final_url"] = page.url
            return row
        if captcha_visible(page):
            human = wait_captcha_or_submit(page, job, 300)
            row.update(human)
            row["final_url"] = page.url
            return row
        try_login(page)
        step = cloud_apply.click_next_or_submit(page)
        page.wait_for_timeout(800)
        if step == "none":
            break
    if captcha_visible(page) or not cloud_apply.is_success(page):
        human = wait_captcha_or_submit(page, job, 240)
        row.update(human)
        row["final_url"] = page.url
        return row
    row["ok"] = True
    row["status"] = "SUBMITTED"
    row["final_url"] = page.url
    return row


def main() -> None:
    apply_now.BATCH = apply_now.load_all_discovered()
    form_memory.seed_from_learned()
    queue = apply_now.queue()
    try_jobs = []
    for job in queue:
        url = job.get("apply_url") or apply_now.apply_url(job) or job.get("url") or ""
        if not url.startswith("http"):
            continue
        job = dict(job)
        job["apply_url"] = url
        try_jobs.append(job)
    print(f"Session driver: {len(try_jobs)} queued jobs (no company skips). Chrome stays open.", flush=True)
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(CDP)
    page = browser.contexts[0].pages[0]
    print("current", page.url, flush=True)

    # If already on a job, finish that first.
    current_url = page.url or ""
    ordered = []
    for job in try_jobs:
        au = job.get("apply_url") or ""
        if au and au.rstrip("/") in current_url.rstrip("/"):
            ordered.insert(0, job)
        else:
            ordered.append(job)
    # de-dupe preserving order
    seen = set()
    jobs = []
    for j in ordered:
        k = str(j.get("job_id") or j.get("apply_url"))
        if k in seen:
            continue
        seen.add(k)
        jobs.append(j)

    for i, job in enumerate(jobs[:8], 1):
        url = job.get("apply_url") or apply_now.apply_url(job)
        print(f"\n[{i}] {job.get('company')}: {job.get('title')}", flush=True)
        if url and url.split("?")[0].rstrip("/") not in (page.url or "").split("?")[0]:
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(1500)
        row = apply_current(page, job)
        persist(row)
        print(f"  {row.get('status')} ok={row.get('ok')} {row.get('final_url')}", flush=True)
        if not row.get("ok"):
            print("  Waiting on this company (no skip). Solve CAPTCHA/login if needed.", flush=True)
            extra = wait_captcha_or_submit(page, job, 300)
            if extra.get("ok"):
                row.update(extra)
                row["final_url"] = page.url
                persist(row)
                print("  submitted after extra wait", flush=True)
            else:
                print("  still blocked on this company; leaving tab open and continuing so more companies get a try", flush=True)
        time.sleep(1)

    print("Session driver finished. Chrome is still open.", flush=True)
    pw.stop()


if __name__ == "__main__":
    main()
