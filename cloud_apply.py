"""Apply to public ATS jobs from the ready queue using Chromium.

Does not use the Windows Firefox / Simplify profile. Login and CAPTCHA
walls are skipped. LinkedIn / Foundit / Naukri URLs are recorded as
LOGIN_BLOCKED without opening them.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

import apply_now
import form_memory
import tailor_resume

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "data" / "applications" / "cloud_results.json"
RESUME = str((ROOT / apply_now.C["resumePath"]).resolve())
C = apply_now.C

LOGIN_HOSTS = (
    "linkedin.com", "www.linkedin.com", "foundit.in", "www.foundit.in",
    "naukri.com", "www.naukri.com", "indeed.com", "www.indeed.com",
    "instahyre.com", "www.instahyre.com",
)
PUBLIC_HOST_HINTS = (
    "jobs.lever.co", "greenhouse.io", "ashbyhq.com", "smartrecruiters.com",
    "myworkdayjobs.com", "myworkdaysite.com", "schwabjobs.com",
    "jobs.thermofisher.com", "careers.dhl.com", "jobs.zf.com",
    "oraclecloud.com", "careers.statestreet.com", "taleo.net",
    "amazon.jobs", "workable.com", "icims.com",
)
SIMPLIFY_RE = re.compile(r"simplify|tailor resume|resume builder", re.I)
LOGIN_RE = re.compile(
    r"sign in to|log in to|login to continue|create (an )?account|"
    r"forgot password|sso|single sign[- ]on|verify you are (a )?human|"
    r"unusual traffic|access denied|please sign in|already have an account",
    re.I,
)
CAPTCHA_RE = re.compile(r"captcha|recaptcha|hcaptcha|cf-challenge|challenge-platform", re.I)
SUCCESS_RE = re.compile(
    r"thanks for (your )?appl|application (was |has been )?(submitted|received)|"
    r"thank you for applying|we.?ve received your application|application received|"
    r"already applied|you previously applied|successfully submitted|application submitted",
    re.I,
)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def classify_url(url: str) -> str:
    host = _host(url)
    if any(host == h or host.endswith("." + h) for h in LOGIN_HOSTS):
        return "LOGIN_BLOCKED"
    if any(h in host for h in PUBLIC_HOST_HINTS):
        return "TRY"
    if host:
        return "TRY"
    return "LOGIN_BLOCKED"


def dismiss_overlays(page) -> None:
    for sel in (
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept all')",
        "button:has-text('Accept All')",
        "button:has-text('Accept')",
        "button:has-text('I agree')",
        "button:has-text('I Agree')",
        "button:has-text('Got it')",
        "button:has-text('Dismiss')",
        "button:has-text('No thanks')",
        "button:has-text('Close')",
        "[aria-label='Close']",
        "[aria-label='Dismiss']",
        "button[aria-label='Close dialog']",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                text = (loc.inner_text() or "") + (loc.get_attribute("aria-label") or "")
                if SIMPLIFY_RE.search(text):
                    continue
                loc.click(timeout=800)
                page.wait_for_timeout(250)
        except Exception:
            continue


def page_text(page) -> str:
    try:
        return page.inner_text("body") or ""
    except Exception:
        return ""


def is_login_or_captcha(page) -> str | None:
    url = (page.url or "").lower()
    if any(h in url for h in ("accounts.google.com", "login.microsoftonline", "signin.", "/login", "/sso")):
        return "LOGIN_BLOCKED"
    try:
        if page.locator("iframe[src*='recaptcha'], iframe[src*='hcaptcha'], .g-recaptcha").count():
            return "CAPTCHA"
    except Exception:
        pass
    blob = page_text(page)[:4000]
    if CAPTCHA_RE.search(blob) and re.search(r"verify|i.?m not a robot|challenge", blob, re.I):
        return "CAPTCHA"
    pw = page.locator("input[type=password]")
    try:
        if pw.count() and LOGIN_RE.search(blob):
            return "LOGIN_BLOCKED"
    except Exception:
        pass
    if LOGIN_RE.search(blob) and re.search(r"password|sign in|log in", blob, re.I):
        if page.locator("input[type=email], input[name='username'], input[name='email']").count():
            return "LOGIN_BLOCKED"
    return None


def is_success(page) -> bool:
    url = (page.url or "").lower()
    if any(x in url for x in ("/thanks", "confirmation", "submitted", "application-success", "/thank")):
        return True
    return bool(SUCCESS_RE.search(page_text(page)[:3000]))


def fill_identity(page) -> None:
    pairs = [
        ("input[name='name'], input[name='full_name'], #name", C["fullName"]),
        ("input[name='first_name'], #first_name, input[autocomplete='given-name']", C["firstName"]),
        ("input[name='last_name'], #last_name, input[autocomplete='family-name']", C["lastName"]),
        ("input[name='email'], #email, input[type=email]", C["email"]),
        ("input[name='phone'], #phone, input[type=tel]", C["phoneNational"]),
        ("input[name='org'], input[name='company']", C["currentEmployer"]),
        ("input[name='urls[LinkedIn]'], input[name='linkedin'], input[placeholder*='LinkedIn' i]", C["linkedIn"]),
        ("#location-input, input[name='location'], input[placeholder*='Location' i]", "Hyderabad, India"),
    ]
    for sel, value in pairs:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                cur = ""
                try:
                    cur = (loc.input_value() or "").strip()
                except Exception:
                    pass
                if not cur:
                    loc.fill(str(value), timeout=1500)
        except Exception:
            continue


def upload_resume(page, path: str) -> bool:
    return tailor_resume.upload(page, path)


def click_apply_gate(page) -> None:
    for sel in (
        "a:has-text('Apply for this job')",
        "button:has-text('Apply for this job')",
        "a:has-text('Apply now')",
        "button:has-text('Apply now')",
        "a:has-text('Apply Now')",
        "button:has-text('Apply Now')",
        "a:has-text('I'm interested')",
        "button:has-text('I'm interested')",
        "a[href*='/apply']",
        "button:has-text('Apply')",
    ):
        try:
            loc = page.locator(sel).first
            if not loc.count() or not loc.is_visible():
                continue
            text = loc.inner_text() or ""
            if SIMPLIFY_RE.search(text):
                continue
            loc.click(timeout=1500)
            page.wait_for_timeout(1200)
            return
        except Exception:
            continue


def click_next_or_submit(page) -> str:
    """Click one navigation control. Returns clicked|submitted|none."""
    dismiss_overlays(page)
    if is_success(page):
        return "submitted"
    for sel in (
        "button:has-text('Submit application')",
        "button:has-text('Submit Application')",
        "button:has-text('Submit your application')",
        "input[type=submit][value*='Submit' i]",
        "button[type=submit]:has-text('Submit')",
        "button:has-text('Submit')",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible() and loc.is_enabled():
                text = loc.inner_text() or loc.get_attribute("value") or ""
                if SIMPLIFY_RE.search(text):
                    continue
                loc.click(timeout=2000)
                page.wait_for_timeout(1800)
                return "submitted" if is_success(page) else "clicked"
        except Exception:
            continue
    for sel in (
        "button:has-text('Next')",
        "button:has-text('Continue')",
        "button:has-text('Save and continue')",
        "button:has-text('Review')",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible() and loc.is_enabled():
                text = loc.inner_text() or ""
                if SIMPLIFY_RE.search(text):
                    continue
                loc.click(timeout=2000)
                page.wait_for_timeout(1400)
                return "clicked"
        except Exception:
            continue
    return "none"


def apply_one(page, job: dict) -> dict:
    url = job.get("apply_url") or apply_now.apply_url(job) or job.get("url") or ""
    kind = classify_url(url)
    row = {
        **{k: job.get(k) for k in ("company", "title", "location", "url", "ats", "job_id")},
        "apply_url": url,
        "ok": False,
        "status": kind,
        "note": "",
        "final_url": url,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if kind != "TRY":
        row["note"] = "login board skipped without opening"
        return row

    resume = job.get("resume_path") or RESUME
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(1500)
        dismiss_overlays(page)
        block = is_login_or_captcha(page)
        if block:
            row["status"] = block
            row["final_url"] = page.url
            row["note"] = "blocked before fill"
            return row
        click_apply_gate(page)
        dismiss_overlays(page)
        block = is_login_or_captcha(page)
        if block:
            row["status"] = block
            row["final_url"] = page.url
            row["note"] = "blocked on apply gate"
            return row
        if is_success(page):
            row["ok"] = True
            row["status"] = "SUBMITTED"
            row["note"] = "already applied"
            row["final_url"] = page.url
            return row

        fill_identity(page)
        apply_now.set_india_phone(page)
        upload_resume(page, resume)
        form_memory.fill_visible(page)
        form_memory.remember(page, job)

        for _ in range(6):
            dismiss_overlays(page)
            if is_success(page):
                row["ok"] = True
                row["status"] = "SUBMITTED"
                row["final_url"] = page.url
                return row
            block = is_login_or_captcha(page)
            if block:
                row["status"] = block
                row["final_url"] = page.url
                return row
            fill_identity(page)
            upload_resume(page, resume)
            form_memory.fill_visible(page)
            step = click_next_or_submit(page)
            if step == "submitted" or is_success(page):
                row["ok"] = True
                row["status"] = "SUBMITTED"
                row["final_url"] = page.url
                return row
            if step == "none":
                break
            page.wait_for_timeout(900)

        row["status"] = "INCOMPLETE"
        row["final_url"] = page.url
        row["note"] = "form still open after fill; no submit confirmation"
        return row
    except Exception as exc:
        row["status"] = "ERROR"
        row["note"] = str(exc)[:280]
        try:
            row["final_url"] = page.url
        except Exception:
            pass
        return row


def public_queue(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    try_jobs = []
    blocked = []
    for job in jobs:
        url = job.get("apply_url") or apply_now.apply_url(job) or job.get("url") or ""
        job = dict(job)
        job["apply_url"] = url
        kind = classify_url(url)
        if kind == "TRY":
            try_jobs.append(job)
        else:
            blocked.append({
                **{k: job.get(k) for k in ("company", "title", "location", "url", "ats", "job_id")},
                "apply_url": url,
                "ok": False,
                "status": "LOGIN_BLOCKED",
                "note": "linkedin/foundit/naukri skipped",
            })
    return try_jobs, blocked


def save_cloud(rows: list[dict]) -> None:
    existing = []
    if RESULTS.exists():
        try:
            existing = json.loads(RESULTS.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    by_id = {}
    for row in existing + rows:
        key = str(row.get("job_id") or row.get("apply_url") or row.get("url") or "")
        if key:
            by_id[key] = row
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(list(by_id.values()), indent=2, ensure_ascii=False), encoding="utf-8")


def main(limit: int = 12) -> list[dict]:
    apply_now.BATCH = apply_now.load_all_discovered()
    form_memory.seed_from_learned()
    queue = apply_now.queue()
    try_jobs, blocked_board = public_queue(queue)
    print(f"Queue {len(queue)} | public ATS {len(try_jobs)} | login boards {len(blocked_board)}", flush=True)
    results: list[dict] = []
    # Do not persist hundreds of LinkedIn skips as applied — report only.
    login_sample = blocked_board[:8]
    results.extend(login_sample)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(
            locale="en-IN",
            viewport={"width": 1400, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        for i, job in enumerate(try_jobs[:limit], 1):
            print(f"\n[{i}/{min(limit, len(try_jobs))}] {job.get('company')}: {job.get('title')}", flush=True)
            try:
                job["resume_path"] = tailor_resume.for_job(job)
                print(f"  Tailored: {tailor_resume.CURRENT.get('headline')}", flush=True)
            except Exception as exc:
                job["resume_path"] = RESUME
                print(f"  Tailor failed ({exc}); using architect resume.", flush=True)
            row = apply_one(page, job)
            results.append(row)
            if row.get("ok") and row.get("status") == "SUBMITTED":
                apply_now.persist_applied(row, row.get("note") or "cloud_apply submitted")
            else:
                apply_now.log({"event": "cloud_apply", **{k: v for k, v in row.items() if k != "confirmation"}})
            save_cloud(results)
            print(f"  {row.get('status')} ok={row.get('ok')} {row.get('final_url')}", flush=True)
            # One job at a time: close extra pages so we never batch-navigate.
            for extra in context.pages[1:]:
                try:
                    extra.close()
                except Exception:
                    pass
            time.sleep(1.2)
        browser.close()

    submitted = sum(1 for r in results if r.get("ok") and r.get("status") == "SUBMITTED")
    print(f"\nCloud apply done. Submitted {submitted}. Tried {len(try_jobs[:limit])} public ATS jobs.", flush=True)
    return results


if __name__ == "__main__":
    main()
