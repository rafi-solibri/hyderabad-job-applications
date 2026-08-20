"""Apply to company career-portal jobs from the ready queue using Chromium.

Naukri / LinkedIn / Indeed / Cutshort / Foundit / Instahyre are recorded as
OTHER_AUTOMATION without opening them. Company career sites (Greenhouse, Lever,
Workday, Phenom, SmartRecruiters, etc.) are tried first.
"""
from __future__ import annotations

import argparse
import json
import os
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
LESSONS = ROOT / "data" / "applications" / "headed_lessons.jsonl"
RESUME = str((ROOT / apply_now.C["resumePath"]).resolve())
C = apply_now.C
CHROME = os.environ.get("CHROME_BIN", "/usr/local/bin/google-chrome")
# Always the rafi.success@gmail.com Chrome profile. Never a throwaway session.
PROFILE = ROOT / "data" / "chrome_profile"
CDP = "http://127.0.0.1:9222"
PROFILE_EMAIL = "rafi.success@gmail.com"

# These boards are covered by other automations — this runner skips them.
LOGIN_HOSTS = (
    "linkedin.com", "www.linkedin.com", "foundit.in", "www.foundit.in",
    "naukri.com", "www.naukri.com", "indeed.com", "www.indeed.com",
    "instahyre.com", "www.instahyre.com",
    "cutshort.io", "www.cutshort.io", "cutshort.com", "www.cutshort.com",
)
PUBLIC_HOST_HINTS = (
    "jobs.lever.co", "greenhouse.io", "ashbyhq.com", "smartrecruiters.com",
    "myworkdayjobs.com", "myworkdaysite.com", "schwabjobs.com",
    "jobs.thermofisher.com", "careers.dhl.com", "jobs.zf.com",
    "oraclecloud.com", "careers.statestreet.com", "taleo.net",
    "amazon.jobs", "workable.com", "icims.com", "phenom.com",
    "successfactors.com", "eightfold.ai", "jobvite.com",
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


def classify_url(url: str, job: dict | None = None) -> str:
    """Career portals are tried. Aggregator boards are left to other automations."""
    row = dict(job or {})
    if url:
        row["apply_url"] = url
    if apply_now.is_aggregator_board(row):
        return "OTHER_AUTOMATION"
    host = _host(url)
    if host in LOGIN_HOSTS or any(host.endswith("." + h) for h in ("linkedin.com", "naukri.com", "indeed.com", "foundit.in", "instahyre.com", "cutshort.io")):
        return "OTHER_AUTOMATION"
    if (url or "").startswith("http"):
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
        "button:has-text('Easy Apply')",
        "button:has-text('Apply on company website')",
        "button:has-text('Apply now')",
        "a:has-text('Apply Now')",
        "button:has-text('Apply Now')",
        "a:has-text('I'm interested')",
        "button:has-text('I'm interested')",
        "a[data-automation-id='jobPostingApplyButton']",
        "button[data-automation-id='jobPostingApplyButton']",
        "a[data-automation-id='adventureButton']",
        "button[data-automation-id='adventureButton']",
        "a:has-text('Start application')",
        "button:has-text('Start application')",
        "a[href*='/apply']",
        "button:has-text('Apply')",
        "a:has-text('Apply')",
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


def record_lesson(job: dict, row: dict, learned: int = 0) -> None:
    LESSONS.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "company": job.get("company"),
        "title": job.get("title"),
        "ats": job.get("ats"),
        "url": row.get("final_url") or job.get("apply_url") or job.get("url"),
        "status": row.get("status"),
        "note": row.get("note"),
        "fields_learned": learned,
        "host": _host(row.get("final_url") or job.get("apply_url") or ""),
    }
    with LESSONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def wait_for_human(page, job: dict, seconds: int) -> dict:
    """Leave Chrome on this application so a human can finish CAPTCHA/login/submit."""
    print(
        f"  Chrome is on this form. Finish CAPTCHA, login, leftover fields, then Submit. "
        f"I will learn answers and wait up to {seconds}s.",
        flush=True,
    )
    deadline = time.time() + seconds
    learned = 0
    while time.time() < deadline:
        try:
            changed = form_memory.remember(page, job) or []
            learned += len(changed)
        except Exception:
            pass
        if is_success(page):
            print("  Submitted. Learning this form for later runs.", flush=True)
            return {
                "ok": True,
                "status": "SUBMITTED",
                "note": "submitted in headed Chrome (human + autofill)",
                "learned": learned,
            }
        page.wait_for_timeout(2500)
    print(f"  Still no confirmation after {seconds}s. Learned {learned} field(s).", flush=True)
    return {
        "ok": False,
        "status": "WAITING_EXPIRED",
        "note": f"waited {seconds}s; learned {learned} fields",
        "learned": learned,
    }


def apply_one(page, job: dict, wait_seconds: int = 0) -> dict:
    url = job.get("apply_url") or apply_now.apply_url(job) or job.get("url") or ""
    kind = classify_url(url, job)
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
    learned = 0
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=35000)
        page.wait_for_timeout(1800)
        dismiss_overlays(page)
        block = is_login_or_captcha(page)
        if block and not wait_seconds:
            row["status"] = block
            row["final_url"] = page.url
            row["note"] = "blocked before fill"
            return row
        click_apply_gate(page)
        dismiss_overlays(page)
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
        learned += len(form_memory.remember(page, job) or [])

        for _ in range(6):
            dismiss_overlays(page)
            if is_success(page):
                row["ok"] = True
                row["status"] = "SUBMITTED"
                row["final_url"] = page.url
                return row
            block = is_login_or_captcha(page)
            if block and not wait_seconds:
                row["status"] = block
                row["final_url"] = page.url
                return row
            if block and wait_seconds:
                break
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

        if wait_seconds:
            human = wait_for_human(page, job, wait_seconds)
            row["ok"] = human["ok"]
            row["status"] = human["status"]
            row["note"] = human["note"]
            row["final_url"] = page.url
            learned += int(human.get("learned") or 0)
            row["fields_learned"] = learned
            record_lesson(job, row, learned)
            return row

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
        if wait_seconds:
            try:
                human = wait_for_human(page, job, wait_seconds)
                if human.get("ok"):
                    row.update({k: human[k] for k in ("ok", "status", "note")})
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
        kind = classify_url(url, job)
        if kind == "TRY":
            try_jobs.append(job)
        else:
            blocked.append({
                **{k: job.get(k) for k in ("company", "title", "location", "url", "ats", "job_id")},
                "apply_url": url,
                "ok": False,
                "status": "OTHER_AUTOMATION" if kind == "OTHER_AUTOMATION" else "LOGIN_BLOCKED",
                "note": "Naukri/LinkedIn/Indeed/Cutshort/Foundit/Instahyre left to other automations",
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


def launch_context(pw, headed: bool):
    args = ["--no-sandbox", "--disable-dev-shm-usage"]
    if headed:
        os.environ.setdefault("DISPLAY", ":1")
        # Reuse the already-open rafi.success@gmail.com Chrome. Never spawn a second profile.
        try:
            browser = pw.chromium.connect_over_cdp(CDP)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
            print(f"  Using open Chrome profile {PROFILE_EMAIL} ({PROFILE})", flush=True)
            return None, context, page
        except Exception as exc:
            print(f"  CDP attach failed ({exc}); launching {PROFILE_EMAIL} profile.", flush=True)
        PROFILE.mkdir(parents=True, exist_ok=True)
        args += ["--start-maximized", f"--remote-debugging-port=9222", "--profile-directory=Default"]
        kwargs = {
            "user_data_dir": str(PROFILE),
            "headless": False,
            "args": args,
            "locale": "en-IN",
            "viewport": {"width": 1600, "height": 1000},
            "accept_downloads": True,
        }
        if Path(CHROME).exists():
            kwargs["executable_path"] = CHROME
        context = pw.chromium.launch_persistent_context(**kwargs)
        page = context.pages[0] if context.pages else context.new_page()
        return None, context, page
    browser = pw.chromium.launch(headless=True, args=args)
    context = browser.new_context(
        locale="en-IN",
        viewport={"width": 1400, "height": 900},
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
    )
    return browser, context, context.new_page()


def main(limit: int = 12, headed: bool = False, wait_seconds: int = 0) -> list[dict]:
    apply_now.BATCH = apply_now.load_all_discovered()
    form_memory.seed_from_learned()
    queue = apply_now.queue()
    try_jobs, blocked_board = public_queue(queue)
    print(
        f"Queue {len(queue)} | company career portals {len(try_jobs)} | "
        f"other-board automations {len(blocked_board)}",
        flush=True,
    )
    if headed:
        print(f"Headed Chrome on DISPLAY={os.environ.get('DISPLAY', ':1')} — complete CAPTCHA/login in the desktop view.", flush=True)
    results: list[dict] = []
    if not headed:
        results.extend(blocked_board[:8])

    with sync_playwright() as pw:
        browser, context, page = launch_context(pw, headed)
        for i, job in enumerate(try_jobs[:limit], 1):
            print(f"\n[{i}/{min(limit, len(try_jobs))}] {job.get('company')}: {job.get('title')}", flush=True)
            try:
                job["resume_path"] = tailor_resume.for_job(job)
                print(f"  Tailored: {tailor_resume.CURRENT.get('headline')}", flush=True)
            except Exception as exc:
                job["resume_path"] = RESUME
                print(f"  Tailor failed ({exc}); using architect resume.", flush=True)
            row = apply_one(page, job, wait_seconds=wait_seconds)
            results.append(row)
            if row.get("ok") and row.get("status") == "SUBMITTED":
                apply_now.persist_applied(row, row.get("note") or "cloud_apply submitted")
            else:
                apply_now.log({"event": "cloud_apply", **{k: v for k, v in row.items() if k != "confirmation"}})
            save_cloud(results)
            print(f"  {row.get('status')} ok={row.get('ok')} {row.get('final_url')}", flush=True)
            time.sleep(1.0)
        if headed:
            print("  Leaving rafi.success@gmail.com Chrome open.", flush=True)
        elif browser:
            browser.close()
        else:
            context.close()

    submitted = sum(1 for r in results if r.get("ok") and r.get("status") == "SUBMITTED")
    print(f"\nCloud apply done. Submitted {submitted}. Tried {len(try_jobs[:limit])} company career-portal jobs.", flush=True)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", help="Open visible Chrome on the cloud desktop")
    parser.add_argument("--wait", type=int, default=0, help="Seconds to wait for human CAPTCHA/login/submit")
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    wait = args.wait if args.wait else (420 if args.headed else 0)
    main(limit=args.limit, headed=args.headed, wait_seconds=wait)
