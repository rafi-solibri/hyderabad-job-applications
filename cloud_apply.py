"""Apply to leftover Hyderabad / Remote-India jobs in headed Chrome.

Every run: discover, then apply leftover company career portals (Greenhouse,
Lever, Workday, Phenom, SmartRecruiters, Oracle, etc.). Only after that queue
is empty, apply Naukri / LinkedIn / Indeed / Cutshort / Foundit / Instahyre.
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
import ats_fill
import form_memory
import google_auth
import simplify_copilot
import tailor_resume

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "data" / "applications" / "cloud_results.json"
LESSONS = ROOT / "data" / "applications" / "headed_lessons.jsonl"
SUBMITTED_LOG = ROOT / "data" / "applications" / "SUBMITTED.md"
RESUME = str((ROOT / apply_now.C["resumePath"]).resolve())
C = apply_now.C
# Bypass /usr/local/bin/google-chrome — that wrapper forces ~/.config/google-chrome.
CHROME = os.environ.get("CHROME_BIN", "/opt/google/chrome/chrome")
# Always the rafi.success@gmail.com Chrome profile. Never a throwaway session.
PROFILE = ROOT / "data" / "chrome_profile"
CDP = "http://127.0.0.1:9222"
PROFILE_EMAIL = "rafi.success@gmail.com"
# One application tab only. Open the next job after a successful submit,
# a closed/404 posting, or a career-site login that rejects every portal password.
MAX_OPEN_APPLICATIONS = 1
DONE_STATUSES = frozenset({"SUBMITTED", "CLOSED", "AUTH_FAILED"})
# Park these and open the next leftover. STUCK = Copilot/form loop; do not sit on it.
PARK_STATUSES = frozenset({"CAPTCHA", "WAITING_EXPIRED", "OWNER_SIGNIN", "STUCK", "NEED_INPUT"})
KEEP_TAB_STATUSES = frozenset({"CAPTCHA", "OWNER_SIGNIN", "NEED_INPUT"})
TERMINAL_STATUSES = DONE_STATUSES | PARK_STATUSES | frozenset({"ERROR"})
PARKED_CAPTCHA_URLS: set[str] = set()
SESSION_SKIP_KEYS: set[str] = set()
FOUNDIT_AKAMAI_BLOCKED = False
GOOGLE_SIGNIN_BLOCKED = False
GOOGLE_2FA_PARKED = False
LINKEDIN_RESTRICTED = False
LINKEDIN_RESTRICTED_NOTE = "LinkedIn account temporarily restricted until 2026-08-22"
# 22 Aug 2026 8:30 PM PDT. Session-skip until then; do not persist-skip guest walls.
LINKEDIN_RESTRICTED_UNTIL = datetime(2026, 8, 23, 3, 30, tzinfo=timezone.utc)
_RECAPTCHA_CLICKS = 0
ICIMS_LOGIN_CLICKED = False
ICIMS_CONTINUE_CLICKS = 0
ICIMS_PASSWORD_SUBMITS = 0
# Owner is at the desktop filling leftover fields. Pause instead of skipping.
OWNER_PRESENT = False
WATCH_OPEN = False

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
    r"thank you for applying|thank you for your job application|"
    r"you have successfully applied|successfully applied|"
    r"we.?ve received your application|application received|"
    r"already applied|you previously applied|successfully submitted|application submitted|"
    r"application sent",
    re.I,
)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _stable_apply_url(url: str) -> str:
    """Workday steps share one job; ignore query, encoding, and applyManually."""
    u = (url or "").split("?")[0].lower().replace("%2c", ",")
    u = re.sub(r"/applymanually.*", "/apply", u)
    u = re.sub(r"/apply/.*", "/apply", u)
    return u.rstrip("/")


def _ats_loop_host(url: str) -> bool:
    """Career ATS pages that loop required fields / skills without changing URL."""
    u = (url or "").lower()
    return "myworkdayjobs" in u or "avature.net" in u or "login.icims.com" in u


def seed_parked_captcha_urls() -> None:
    path = ROOT / "data" / "applications" / "CAPTCHA.md"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("http"):
            park_tab_url(line)


def classify_url(url: str, job: dict | None = None, allow_aggregators: bool = True) -> str:
    """Career portals and aggregator boards (Naukri/LinkedIn/Indeed/…) are both tried.

    Aggregators used to wait until career leftovers were empty; that blocked
    hundreds of Easy Apply jobs behind slow Workday forms.
    """
    row = dict(job or {})
    if url:
        row["apply_url"] = url
    if apply_now.is_aggregator_board(row):
        return "TRY" if allow_aggregators else "OTHER_AUTOMATION"
    host = _host(url)
    if host in LOGIN_HOSTS or any(host.endswith("." + h) for h in ("linkedin.com", "naukri.com", "indeed.com", "foundit.in", "instahyre.com", "cutshort.io")):
        return "TRY" if allow_aggregators else "OTHER_AUTOMATION"
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
    # Guest apply forms (Oracle /apply/email, Lever /apply) are not login walls.
    if "indeed.com/auth" in url or "indeed.com/oauth" in url:
        return "LOGIN_BLOCKED"
    if "linkedin.com/login" in url or "linkedin.com/uas/login" in url:
        return "LOGIN_BLOCKED"
    if "/apply" in url or "/job/" in url:
        pass
    elif any(h in url for h in ("accounts.google.com", "login.microsoftonline", "signin.", "/sso")):
        return "LOGIN_BLOCKED"
    if "/login" in url and "/apply" not in url and "icims.com" in url:
        return "LOGIN_BLOCKED"
    if "/login" in url and "/apply" not in url and "job" not in url:
        if "foundit.in" in url:
            return None
        return "LOGIN_BLOCKED"
    try:
        n = page.locator("iframe[title*='hCaptcha' i], iframe[src*='hcaptcha'][title*='challenge' i]").count()
        if n:
            for i in range(min(n, 4)):
                loc = page.locator("iframe[title*='hCaptcha' i], iframe[src*='hcaptcha']").nth(i)
                try:
                    if loc.is_visible():
                        box = loc.bounding_box() or {}
                        if (box.get("width") or 0) > 280 and (box.get("height") or 0) > 140:
                            return "CAPTCHA"
                except Exception:
                    continue
    except Exception:
        pass
    blob = page_text(page)[:4000]
    # Invisible/checkbox reCAPTCHA is not a blocker. Only a visible puzzle is.
    if re.search(r"drag the shape|select all (the )?squares|click (the )?images", blob, re.I):
        return "CAPTCHA"
    pw = page.locator("input[type=password]")
    try:
        if pw.count() and pw.first.is_visible() and LOGIN_RE.search(blob) and "/apply" not in url:
            return "LOGIN_BLOCKED"
    except Exception:
        pass
    return None


MID_WIZARD_URL = (
    "/apply/section/",
    "/apply/email",
    "/apply/form",
    "stepname=applicant",
    "stepname=myinformation",
    "stepname=myexperience",
    "stepname=voluntary",
    "stepname=applicationreview",
    "stepname=acknowledg",
    "stepname=eoe",
    "stepname=selfidentify",
)
SUCCESS_URL = (
    "/thanks",
    "/confirmation",
    "application-success",
    "/thank-you",
    "/thankyou",
    "applythankyou",
    "stepname=applicationcomplete",
    "stepname=thank",
    "stepname=confirmation",
    "jobtasks/completed/application",
    "/jobs/success",
    "showacp",
    "multiapplyresp",
)


def is_success(page) -> bool:
    url = (page.url or "").lower()
    if any(x in url for x in SUCCESS_URL):
        return True
    try:
        loc = page.locator("#already-applied, span.already-applied").first
        if loc.count() and loc.is_visible():
            return True
    except Exception:
        pass
    # Mid-wizard URLs are not a submit confirmation.
    if any(x in url for x in MID_WIZARD_URL) or "stepname=" in url:
        return False
    try:
        loc = page.get_by_role("button", name=re.compile(r"applied", re.I)).first
        if loc.count():
            t = ((loc.inner_text() or "") + " " + (loc.get_attribute("aria-label") or "")).lower()
            if "applied" in t:
                return True
    except Exception:
        pass
    return bool(SUCCESS_RE.search(page_text(page)[:3000]))


def already_applied_visible(page) -> bool:
    try:
        loc = page.locator("#already-applied, span.already-applied").first
        if loc.count() and loc.is_visible():
            return True
    except Exception:
        pass
    try:
        loc = page.get_by_role("button", name=re.compile(r"applied", re.I)).first
        if loc.count():
            t = ((loc.inner_text() or "") + " " + (loc.get_attribute("aria-label") or "")).lower()
            if "applied" in t:
                return True
    except Exception:
        pass
    try:
        blob = page_text(page)[:3000]
    except Exception:
        blob = ""
    return bool(re.search(r"application sent|already applied|you previously applied|#already-applied", blob, re.I))


def linkedin_account_restricted(page) -> bool:
    try:
        url = (page.url or "").lower()
        blob = ((page.title() or "") + " " + page_text(page)[:3500]).lower()
    except Exception:
        return False
    if "linkedin.com" not in url:
        return False
    return bool(re.search(r"temporarily restricted|restriction will be lifted", blob))


def linkedin_blocked_now() -> bool:
    """True while the LinkedIn account restriction is in force. Session-skip only."""
    if LINKEDIN_RESTRICTED:
        return True
    return datetime.now(timezone.utc) < LINKEDIN_RESTRICTED_UNTIL


def persist_skip_all_linkedin(note: str | None = None) -> int:
    """Account restriction is not a guest wall. Do not reopen LinkedIn until it lifts."""
    global LINKEDIN_RESTRICTED
    LINKEDIN_RESTRICTED = True
    note = note or LINKEDIN_RESTRICTED_NOTE
    apply_now.BATCH = apply_now.load_all_discovered()
    n = 0
    for job in apply_now.queue():
        u = (job.get("apply_url") or job.get("url") or "").lower()
        if "linkedin.com" not in u:
            continue
        if apply_now.is_applied(job):
            continue
        apply_now.persist_skipped({**job, "status": "SKIPPED"}, note)
        SESSION_SKIP_KEYS.update(apply_now.job_match_keys(job))
        n += 1
    print(f"  Skipping {n} LinkedIn leftovers — {note}.", flush=True)
    return n


def fill_identity(page) -> None:
    pairs = [
        ("input[name='name'], input[name='full_name'], #name", C["fullName"]),
        ("input[name='first_name'], #first_name, input[autocomplete='given-name'], #first-name-input", C["firstName"]),
        ("input[name='last_name'], #last_name, input[autocomplete='family-name'], #last-name-input", C["lastName"]),
        ("input[name='phone'], #phone, input[type=tel]", C["phoneNational"]),
        ("input[name='org'], input[name='company']", C["currentEmployer"]),
        ("input[name='urls[LinkedIn]'], input[name='linkedin'], #linkedin-input, input[placeholder*='LinkedIn' i]", C["linkedIn"]),
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
    fill_email_fields(page)


def fill_email_fields(page) -> int:
    """Fill Email and Confirm/Verify email with the same address. Never log it."""
    email = C.get("email") or google_auth.EMAIL
    if not email:
        return 0
    filled = 0
    try:
        loc = page.locator(
            "input[type=email], #email, #email-input, #confirm-email-input, "
            "spl-input[type=email], spl-input[id*='email' i], "
            "input[id*='email' i], input[name*='email' i], input[autocomplete='email']"
        )
        n = loc.count()
    except Exception:
        n = 0
    seen: set[tuple] = set()
    for i in range(min(n, 8)):
        el = loc.nth(i)
        try:
            if not el.is_visible():
                continue
            meta = (
                (el.get_attribute("name") or "")
                + " "
                + (el.get_attribute("id") or "")
                + " "
                + (el.get_attribute("aria-label") or "")
                + " "
                + (el.get_attribute("placeholder") or "")
            ).lower()
            if any(x in meta for x in ("honey", "honeypot", "robot")):
                continue
            box = el.bounding_box() or {}
            key = (round(box.get("x") or 0), round(box.get("y") or 0), el.get_attribute("id") or str(i))
            if key in seen:
                continue
            seen.add(key)
            target = el
            try:
                tag = (el.evaluate("n => (n.tagName || '').toLowerCase()") or "")
            except Exception:
                tag = ""
            if tag not in {"input", "textarea"}:
                inner = el.locator("input:not([type=hidden]), textarea").first
                if inner.count():
                    target = inner
            cur = ""
            try:
                cur = (target.input_value() or "").strip()
            except Exception:
                pass
            if cur.lower() == str(email).lower():
                host_invalid = False
                try:
                    host_invalid = "ng-invalid" in (el.get_attribute("class") or "")
                except Exception:
                    pass
                if not host_invalid:
                    continue
            target.scroll_into_view_if_needed(timeout=1500)
            target.click(timeout=2000)
            target.fill("", timeout=2000)
            target.press_sequentially(str(email), delay=15)
            try:
                target.press("Tab")
            except Exception:
                pass
            filled += 1
        except Exception:
            continue
    if filled:
        print(f"  Filled {filled} email / confirm-email field(s).", flush=True)
    return filled


def fill_portal_account(page, password: str | None = None) -> str:
    """Fill Create Account / Sign In email + password on any career ATS. Never log the secret."""
    url = ""
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "accounts.google.com" in url:
        return "skip"
    if "icims.com" in url:
        return "skip"
    password = password or google_auth.load_portal_password()
    if not password:
        print("  APPLY_ACCOUNT_PASSWORD missing from .env; cannot create/sign-in accounts.", flush=True)
        return "missing"
    email = google_auth.EMAIL
    filled_email = False
    for sel in (
        "[data-automation-id='email']",
        "[data-automation-id='emailAddress']",
        "input[type=email]",
        "input[autocomplete='username']",
        "input[autocomplete='email']",
        "input[name='email']",
        "input[id*='email' i]",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.fill(email, timeout=2000)
                filled_email = True
                break
        except Exception:
            continue
    if not filled_email:
        for pattern in (r"email address", r"^email$", r"username"):
            try:
                loc = page.get_by_label(re.compile(pattern, re.I)).first
                if loc.count() and loc.is_visible():
                    loc.fill(email, timeout=2000)
                    filled_email = True
                    break
            except Exception:
                continue
    filled_pw = 0
    seen: set[tuple] = set()
    for sel in (
        "[data-automation-id='password']",
        "[data-automation-id='verifyPassword']",
        "[data-automation-id='confirmPassword']",
        "input[autocomplete='new-password']",
        "input[autocomplete='current-password']",
        "input[type=password]",
    ):
        if filled_pw >= 2:
            break
        try:
            loc = page.locator(sel)
            n = loc.count()
        except Exception:
            n = 0
        for i in range(min(n, 4)):
            if filled_pw >= 2:
                break
            el = loc.nth(i)
            try:
                if not el.is_visible():
                    continue
                meta = ((el.get_attribute("name") or "") + " " + (el.get_attribute("id") or "") + " " + (el.get_attribute("aria-label") or "") + " " + (el.get_attribute("placeholder") or "")).lower()
                if any(x in meta for x in ("honey", "honeypot", "website", "robot")):
                    continue
                box = el.bounding_box() or {}
                key = (
                    round(box.get("x") or 0),
                    round(box.get("y") or 0),
                    el.get_attribute("data-automation-id") or el.get_attribute("id") or sel,
                )
                if key in seen:
                    continue
                seen.add(key)
                el.fill(password, timeout=2000)
                filled_pw += 1
            except Exception:
                continue
    if filled_email or filled_pw:
        print(
            f"  Filled career-site account fields (email={int(filled_email)} password_boxes={filled_pw}).",
            flush=True,
        )
        return "ok"
    # iCIMS / Avature often put the login in an iframe.
    try:
        fl = page.frame_locator("iframe").first
        box = fl.locator("input[type=email], input[name='email'], input[name='username']").first
        if box.count():
            box.fill(email, timeout=2500)
            filled_email = True
        pbox = fl.locator("input[type=password]").first
        if pbox.count():
            pbox.fill(password, timeout=2500)
            filled_pw = 1
        if filled_email or filled_pw:
            print(
                f"  Filled iframe account fields (email={int(filled_email)} password_boxes={filled_pw}).",
                flush=True,
            )
            # iCIMS Auth0 / Returning candidate login is owned by fill_icims_login.
            # Clicking Log in / Continue here opens extra login.icims.com tabs.
            if "icims.com" in url:
                return "ok"
            try:
                fl.get_by_role("button", name=re.compile(r"sign in|log in|continue", re.I)).first.click(timeout=2500)
            except Exception:
                pass
            return "ok"
    except Exception:
        pass
    return "none"


def _account_gate_blob(page) -> str:
    try:
        return (page_text(page) or "")[:2500]
    except Exception:
        return ""


def on_account_gate(page) -> bool:
    try:
        url = (page.url or "").lower()
        title = (page.title() or "").lower()
    except Exception:
        return False
    if "accounts.google.com" in url:
        return False
    try:
        if not page.locator("input[type=password]").count():
            return False
    except Exception:
        return False
    blob = _account_gate_blob(page).lower()
    return any(
        x in url + " " + title + " " + blob
        for x in ("create account", "sign in", "/login", "verify new password", "already have an account")
    )


def account_auth_rejected(page) -> bool:
    return bool(
        re.search(
            r"wrong email address or password|account might be locked|invalid password|"
            r"incorrect password|already (have an account|exists)",
            _account_gate_blob(page),
            re.I,
        )
    )


def _click_account_button(page, label: str) -> bool:
    try:
        loc = page.locator(f"[data-automation-id='{label}']")
        if loc.count() and loc.first.is_visible():
            loc.first.click(force=True, timeout=3000)
            return True
    except Exception:
        pass
    try:
        loc = page.get_by_role("button", name=re.compile(rf"^{re.escape(label)}$", re.I))
        if loc.count():
            loc.last.click(force=True, timeout=3000)
            return True
    except Exception:
        pass
    return False


def _on_sign_in_form(page) -> bool:
    title = ""
    try:
        title = (page.title() or "").lower()
    except Exception:
        pass
    blob = _account_gate_blob(page).lower()
    if "forgot your password" in blob or "don't have an account" in blob:
        return True
    return "sign in" in title and "create account" not in title


def _switch_to_sign_in(page) -> None:
    if _on_sign_in_form(page):
        return
    try:
        loc = page.locator("[data-automation-id='signInContent'], [data-automation-id='auth_signin_link']")
        if loc.count() and loc.first.is_visible():
            loc.first.click(timeout=2000)
            page.wait_for_timeout(800)
            return
    except Exception:
        pass
    try:
        if page.get_by_role("button", name="Sign In", exact=True).count():
            page.get_by_role("button", name="Sign In", exact=True).last.click(timeout=2000)
            page.wait_for_timeout(800)
    except Exception:
        pass


def _click_sign_in_with_email(page) -> None:
    """Workday often hides password until Sign in with email is clicked."""
    try:
        loc = page.locator("[data-automation-id='SignInWithEmailButton']").first
        if loc.count() and loc.is_visible():
            loc.click(timeout=2500)
            page.wait_for_timeout(900)
            print("  Clicked Sign in with email.", flush=True)
    except Exception:
        pass


def _aggregator_host(url: str) -> bool:
    host = _host(url)
    return any(
        host == h or host.endswith("." + h)
        for h in (
            "linkedin.com", "naukri.com", "indeed.com", "foundit.in",
            "instahyre.com", "cutshort.io", "cutshort.com",
        )
    )


def google_password_create_parked(page=None, context=None) -> bool:
    """True when Google is asking to create/change a password. Never fill that form."""
    ctx = context or getattr(page, "context", None)
    pages = list(ctx.pages) if ctx is not None else ([page] if page is not None else [])
    for p in pages:
        try:
            if p is None or p.is_closed():
                continue
            u = (p.url or "").lower()
        except Exception:
            continue
        if "accounts.google.com" in u and ("changepassword" in u or "speedbump" in u):
            return True
    return False


def _google_chooser_pages(page) -> list:
    pages = []
    for p in google_auth._all_browser_pages(page):
        try:
            if p.is_closed():
                continue
            url = (p.url or "").lower()
        except Exception:
            continue
        if "accounts.google.com" not in url:
            continue
        if any(x in url for x in (
            "rotatecookies", "passive", "checkcookie", "mail.google.com",
            "changepassword", "speedbump",
        )):
            continue
        pages.append(p)
    return pages


def click_google_account_chooser(page) -> bool:
    """Pick rafi.success@gmail.com on the Google GSI/OAuth popup. Do not navigate the apply tab."""
    if google_password_create_parked(page):
        return False
    email = google_auth.EMAIL
    hit = False
    for p in _google_chooser_pages(page):
        if OWNER_PRESENT or WATCH_OPEN:
            # Do not steal the CAPTCHA / apply tab the owner is looking at.
            pass
        else:
            try:
                p.bring_to_front()
            except Exception:
                pass
        for sel in (
            f"div[data-identifier='{email}']",
            f"li[data-identifier='{email}']",
            f"[data-identifier='{email}']",
            f"[data-email='{email}']",
        ):
            try:
                loc = p.locator(sel).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=2500)
                    print(f"  Chose Google account {email}.", flush=True)
                    p.wait_for_timeout(2200)
                    google_auth.fill_google_password_challenges(page)
                    return True
            except Exception:
                continue
        try:
            loc = p.get_by_text(email, exact=False).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=2500)
                print(f"  Chose Google account {email}.", flush=True)
                p.wait_for_timeout(2200)
                google_auth.fill_google_password_challenges(page)
                return True
        except Exception:
            pass
        try:
            loc = p.get_by_text(re.compile(r"Rafi Ahmed Mohammed Abdul", re.I)).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=2500)
                print(f"  Chose Google account {email}.", flush=True)
                p.wait_for_timeout(2200)
                google_auth.fill_google_password_challenges(page)
                return True
        except Exception:
            pass
    n = google_auth.fill_google_password_challenges(page)
    return hit or bool(n)


def try_board_google_signin(page) -> str:
    """LinkedIn/Naukri guest walls: use the already-open Google session, not portal passwords."""
    if google_password_create_parked(page):
        print("  Google change-password parked. Not starting another Google sign-in.", flush=True)
        return "skip"
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if not _aggregator_host(url) and "accounts.google.com" not in url:
        return "skip"
    if click_google_account_chooser(page):
        google_auth.fill_google_password_challenges(page)
        return "ok"
    if _google_chooser_pages(page):
        google_auth.fill_google_password_challenges(page)
        return "ok"
    if not any(x in url for x in ("/signup", "/login", "/uas/login", "cold-join", "auth", "checkpoint", "/register")):
        try:
            n = page.get_by_role("button", name=re.compile(r"google", re.I)).count()
            n += page.get_by_role("link", name=re.compile(r"google", re.I)).count()
            if not n:
                return "skip"
        except Exception:
            return "skip"
    if getattr(page, "_google_signin_clicked", False):
        click_google_account_chooser(page)
        return "ok"
    for name in (
        "Continue with Google",
        "Sign in with Google",
        "Sign in using Google",
        "Google",
    ):
        for role in ("button", "link"):
            try:
                loc = page.get_by_role(role, name=re.compile(rf"{re.escape(name)}", re.I)).first
                if not loc.count():
                    loc = page.get_by_text(re.compile(name, re.I)).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=2500)
                    print(f"  Clicked '{name}' on the job board.", flush=True)
                    try:
                        page._google_signin_clicked = True
                    except Exception:
                        pass
                    page.wait_for_timeout(2800)
                    click_google_account_chooser(page)
                    return "ok"
            except Exception:
                continue
    return "skip"


def fill_foundit_native_login(page) -> str:
    """Foundit email+password. Never click Google (change-password wall). Never log secrets."""
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "foundit.in" not in url:
        return "skip"
    if google_password_create_parked(page):
        print("  Foundit: using native password login, not Google.", flush=True)
    for name in (
        "Login via Password",
        "login via password",
        "Use password",
        "Sign in with Email",
        "Login with Email",
        "Use Email",
        "Login using Password",
    ):
        try:
            loc = page.get_by_text(re.compile(rf"^{re.escape(name)}$", re.I)).first
            if not loc.count():
                loc = page.get_by_text(re.compile(name, re.I)).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=2000)
                page.wait_for_timeout(600)
                break
        except Exception:
            continue
    passwords = []
    gp = google_auth.load_google_password()
    if gp:
        passwords.append(gp)
    for p in google_auth.load_portal_passwords():
        if p not in passwords:
            passwords.append(p)
    if not passwords:
        return "missing"
    email = google_auth.EMAIL
    try:
        em = page.locator(
            "input[type=email], input[name*='email' i], input[placeholder*='Email' i]"
        ).first
        if em.count() and em.is_visible():
            em.fill(email, timeout=2000)
    except Exception:
        pass
    for password in passwords:
        try:
            box = page.locator("input[type=password]").first
            if not box.count() or not box.is_visible():
                continue
            box.fill(password, timeout=2000)
            btn = page.get_by_role(
                "button", name=re.compile(r"login|sign in|continue", re.I)
            ).first
            if btn.count() and btn.is_visible():
                btn.click(timeout=2000)
            page.wait_for_timeout(1500)
            print("  Filled Foundit native login.", flush=True)
            return "ok"
        except Exception:
            continue
    return "skip"


def try_portal_auth(page) -> str:
    """Sign In with each portal password. Create Account only if no account exists. Never log secrets."""
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if _aggregator_host(url):
        if "foundit.in" in url:
            return fill_foundit_native_login(page)
        try_board_google_signin(page)
        return "skip"
    if "login.icims.com" in url:
        return "skip"
    _click_sign_in_with_email(page)
    if not on_account_gate(page):
        return fill_portal_account(page)
    passwords = google_auth.load_portal_passwords()
    if not passwords:
        print("  APPLY_ACCOUNT_PASSWORD missing from .env; cannot create/sign-in accounts.", flush=True)
        return "missing"
    _switch_to_sign_in(page)
    for i, password in enumerate(passwords, 1):
        fill_portal_account(page, password)
        clicked = _click_account_button(page, "signInSubmitButton")
        if not clicked and _on_sign_in_form(page):
            clicked = _click_account_button(page, "Sign In")
        if not clicked:
            continue
        page.wait_for_timeout(2800)
        if account_auth_rejected(page):
            print(f"  Portal password #{i} rejected; trying next.", flush=True)
            continue
        if not on_account_gate(page) or "sign in" not in ((page.title() or "").lower()):
            print(f"  Signed in with portal password #{i}.", flush=True)
            return "ok"
        print(f"  Portal password #{i} did not advance; trying next.", flush=True)
    blob = _account_gate_blob(page).lower()
    if account_auth_rejected(page) and re.search(r"locked|wrong email|incorrect password|invalid password", blob, re.I):
        print("  All portal passwords rejected or account locked. Closing this application.", flush=True)
        return "failed"
    title = ""
    try:
        title = (page.title() or "").lower()
    except Exception:
        title = ""
    need_create = "create account" in title or bool(re.search(r"don'?t have an account|no account (found|exists)", blob, re.I))
    try:
        need_create = need_create or bool(page.locator("[data-automation-id='verifyPassword']").count())
    except Exception:
        pass
    if need_create and not account_auth_rejected(page):
        fill_portal_account(page, passwords[0])
        if _click_account_button(page, "createAccountSubmitButton") or _click_account_button(page, "Create Account"):
            page.wait_for_timeout(2500)
        if not on_account_gate(page) and not account_auth_rejected(page):
            print("  Created career-site account with portal password #1.", flush=True)
            return "ok"
        if account_auth_rejected(page):
            print("  Create Account rejected. Closing this application.", flush=True)
            return "failed"
    print("  All portal passwords rejected on this Sign In / Create Account page.", flush=True)
    return "failed"


def upload_resume(page, path: str) -> bool:
    return tailor_resume.upload(page, path)


CLICK_APPLY_GATE_JS = r"""() => {
  const onNaukri = /naukri\.com/i.test(location.hostname || '');
  const skipRe = /tailor resume|resume builder|search for jobs|refer a friend|join our talent|talent network|sign in|log in|cookie|privacy|withdraw|save job|share|follow|indeed|linkedin|facebook|twitter|xing|wechat|glassdoor|google plus/i;
  const ranked = [
    /^apply manually$/i,
    /^autofill with resume$/i,
    /^apply for this job$/i,
    /^quick apply$/i,
    /^apply on naukri$/i,
    /^apply now$/i,
    /^apply to /i,
    /^i'?m interested$/i,
    /^start applying$/i,
    /^easy apply$/i,
    /^apply as (a )?guest$/i,
    /^continue without an account$/i,
    /^continue with application$/i,
    /^apply$/i,
  ];
  const fire = (el, label) => {
    const btn = el.closest('button, a, [role="button"]') || el;
    btn.scrollIntoView({block: 'center'});
    const r = btn.getBoundingClientRect();
    const x = r.left + Math.max(r.width / 2, 2);
    const y = r.top + Math.max(r.height / 2, 2);
    for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
      btn.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window, clientX: x, clientY: y}));
    }
    try { btn.click(); } catch (e) {}
    return label;
  };
  const labelOf = (el) => ((el.innerText || el.value || el.getAttribute('aria-label') || el.title || '') + '').replace(/\s+/g, ' ').trim();
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const st = window.getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none') return false;
    if (r.width > 4 && r.height > 4) return true;
    const tag = (el.tagName || '').toLowerCase();
    return tag.startsWith('spl-') || tag === 'button' || (el.shadowRoot && /apply|interested/i.test(el.innerText || el.getAttribute('aria-label') || ''));
  };
  const candidates = [];
  const collect = (root) => {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('spl-button, button, a, [role="button"], input[type=button], input[type=submit], .c-spl-button').forEach((el) => {
      if (!visible(el)) return;
      const id = (el.id || '').toLowerCase();
      if (id === 'start-application-button' || id === 'proxy-submit-button' || id === 'fill-button') return;
      const r = el.getBoundingClientRect();
      if (!onNaukri && r.left > window.innerWidth * 0.78) return;
      if (onNaukri && r.left > window.innerWidth * 0.93) return;
      const t = labelOf(el);
      if (!t || t.length > 48 || skipRe.test(t)) return;
      const auto = el.getAttribute('data-automation-id') || '';
      candidates.push({el, t, auto});
    });
    root.querySelectorAll('*').forEach((el) => {
      if (el.shadowRoot) collect(el.shadowRoot);
    });
  };
  collect(document);
  for (const frame of document.querySelectorAll('iframe')) {
    try { collect(frame.contentDocument); } catch (e) {}
  }
  for (const re of ranked) {
    for (const c of candidates) {
      if (re.test(c.t)) return fire(c.el, c.t);
    }
  }
  for (const c of candidates) {
    if (c.auto === 'applyManually' || c.auto === 'adventureButton' || c.auto === 'jobPostingApplyButton') {
      return fire(c.el, c.t || 'Workday Apply');
    }
  }
  for (const el of document.querySelectorAll('a[href*="apply"], a[href*="Apply"]')) {
    if (!visible(el)) continue;
    const t = labelOf(el);
    const href = (el.href || '').toLowerCase();
    if (skipRe.test(t) || (!onNaukri && /indeed|linkedin|naukri|glassdoor/.test(href + ' ' + t))) continue;
    return fire(el, t || 'apply-link');
  }
  return '';
}"""


SKIP_APPLY_LABEL = re.compile(
    r"indeed|linkedin|glassdoor|naukri|tailor resume|resume builder|share|"
    r"refer|save job|talent network|facebook|twitter",
    re.I,
)


def _looks_like_copilot(loc) -> bool:
    """Copilot lives on the right. Clicking it as ATS Apply loops Start Application."""
    try:
        el_id = (loc.get_attribute("id") or "").lower()
        if el_id in {"start-application-button", "proxy-submit-button", "fill-button"}:
            return True
        box = loc.bounding_box() or {}
        vw = 1400
        try:
            vw = loc.page.evaluate("() => window.innerWidth") or 1400
        except Exception:
            pass
        return (box.get("x") or 0) > float(vw) * 0.78
    except Exception:
        return False


def click_instahyre_apply(page) -> str:
    """Instahyre's header Apply ignores synthetic clicks — use a real mouse click."""
    try:
        url = (page.url or "").lower()
    except Exception:
        return ""
    if "instahyre.com" not in url or "/job-" not in url:
        return ""
    if already_applied_visible(page):
        return ""
    try:
        box = page.evaluate(
            """() => {
              const hits = [];
              for (const el of document.querySelectorAll('a, button')) {
                const t = ((el.innerText || '') + '').replace(/\\s+/g, ' ').trim();
                if (!/^apply( to .+)?$/i.test(t)) continue;
                const r = el.getBoundingClientRect();
                if (r.width < 50 || r.height < 22) continue;
                if (r.y < 60 || r.y > 340) continue;
                hits.push({x: r.x, y: r.y, w: r.width, h: r.height, t});
              }
              hits.sort((a, b) => a.y - b.y || b.w - a.w);
              return hits[0] || null;
            }"""
        )
    except Exception:
        box = None
    if not box:
        return ""
    try:
        info = page.evaluate(
            """() => ({
              sx: window.screenX || 0,
              sy: window.screenY || 0,
              oh: window.outerHeight || 0,
              ih: window.innerHeight || 0,
            })"""
        )
    except Exception:
        info = {}
    chrome_top = max(0, int((info.get("oh") or 0) - (info.get("ih") or 0)))
    _xdotool_click(
        (info.get("sx") or 0) + box["x"] + box["w"] / 2,
        (info.get("sy") or 0) + chrome_top + box["y"] + box["h"] / 2,
    )
    label = (box.get("t") or "Apply").strip()[:40]
    print(f"  Clicked Instahyre '{label}'.", flush=True)
    try:
        page.wait_for_timeout(2200)
    except Exception:
        pass
    return label


def naukri_external_apply_label(label: str) -> bool:
    """True when Naukri's sticky footer is company-site / iimjobs / Apply attempted, not Quick apply."""
    t = (label or "").lower()
    if not t:
        return False
    if re.search(r"quick apply", t) and "applied" not in t and "company site" not in t:
        return False
    return bool(
        re.search(
            r"company.?site|apply attempted|iimjobs|apply on (?!naukri)",
            t,
        )
    )


def click_naukri_quick_apply(page) -> str:
    """Naukri JD apply is `#apply-button` (chatbot drawer). The TopTier Quick apply badge does not submit."""
    try:
        url = (page.url or "").lower()
    except Exception:
        return ""
    if "naukri.com" not in url:
        return ""
    if already_applied_visible(page) or is_success(page):
        return ""
    collapse_copilot_panel(page)
    try:
        foot = page.get_by_role("button", name=re.compile(r"^quick apply$", re.I)).first
        if foot.count():
            try:
                foot.scroll_into_view_if_needed(timeout=1500)
            except Exception:
                pass
            label = ((foot.inner_text() or "") + " " + (foot.get_attribute("aria-label") or "")).strip()
            if re.search(r"applied", label, re.I):
                print("  Naukri footer shows already applied.", flush=True)
                return ""
            if naukri_external_apply_label(label):
                print("  Naukri company-site / external apply. Next leftover.", flush=True)
                return ""
            foot.click(timeout=2500, force=True)
            print(f"  Clicked Naukri footer {label[:40]!r}.", flush=True)
            page.wait_for_timeout(2200)
            hit = label[:40] or "Quick apply"
            for name in ("Send application", "Submit application", "Apply now", "Apply"):
                try:
                    loc = page.get_by_role("button", name=re.compile(rf"^{re.escape(name)}$", re.I)).first
                    if loc.count() and loc.is_visible() and not _looks_like_copilot(loc):
                        loc.click(timeout=1500, force=True)
                        print(f"  Clicked Naukri '{name}'.", flush=True)
                        page.wait_for_timeout(1500)
                        return name
                except Exception:
                    continue
            return hit
    except Exception:
        pass
    for sel in (
        "#apply-button",
        "button.apply-button",
        "[class*='styles_apply-button']",
        "[class*='jhc__apply-button-container'] button",
        "[class*='jhc__apply-button-container'] a",
    ):
        try:
            loc = page.locator(sel).first
            if not loc.count():
                continue
            try:
                loc.scroll_into_view_if_needed(timeout=1500)
            except Exception:
                pass
            loc.click(timeout=2500, force=True)
            print(f"  Clicked Naukri Apply ({sel}).", flush=True)
            page.wait_for_timeout(2500)
            hit = "Apply"
            break
        except Exception:
            continue
    else:
        hit = ""
        try:
            dbg = page.evaluate(
                """() => Array.from(document.querySelectorAll('button')).map((el) => {
                  const r = el.getBoundingClientRect();
                  return {
                    id: el.id || '',
                    cls: ((el.className || '') + '').slice(0, 80),
                    t: ((el.innerText || '') + '').replace(/\\s+/g, ' ').trim().slice(0, 40),
                    w: Math.round(r.width),
                    h: Math.round(r.height),
                    x: Math.round(r.x),
                    y: Math.round(r.y),
                  };
                })"""
            ) or []
            print(f"  Naukri buttons ({len(dbg)}): {dbg}", flush=True)
            apply_btns = [
                b for b in dbg
                if re.search(r"apply|interested", (b.get("t") or "") + " " + (b.get("id") or ""), re.I)
            ]
        except Exception as exc:
            print(f"  Naukri button dump failed ({exc}).", flush=True)
            apply_btns = []
        for b in apply_btns:
            bid = (b.get("id") or "").strip()
            try:
                loc = page.locator(f"#{bid}").first if bid else page.get_by_role(
                    "button", name=re.compile(rf"^{re.escape(b.get('t') or 'Apply')}$", re.I)
                ).first
                if not loc.count():
                    continue
                loc.click(timeout=2000, force=True)
                print(f"  Clicked Naukri button {bid or b.get('t')!r}.", flush=True)
                page.wait_for_timeout(2200)
                hit = b.get("t") or "Apply"
                break
            except Exception:
                continue
        if not hit:
            for loc in (
                page.locator("xpath=//*[normalize-space()='Quick apply']/ancestor::*[self::button or self::a or self::div][1]").first,
                page.get_by_text(re.compile(r"^quick apply$", re.I)).first,
            ):
                try:
                    if not loc.count():
                        continue
                    loc.click(timeout=2000, force=True)
                    print("  Clicked Naukri 'Quick apply' control.", flush=True)
                    page.wait_for_timeout(2000)
                    hit = "Quick apply"
                    break
                except Exception:
                    continue
    if not hit:
        return ""
    for name in ("Send application", "Submit application", "Apply now", "Apply"):
        try:
            loc = page.get_by_role("button", name=re.compile(rf"^{re.escape(name)}$", re.I)).first
            if loc.count() and loc.is_visible() and not _looks_like_copilot(loc):
                loc.click(timeout=1500, force=True)
                print(f"  Clicked Naukri '{name}'.", flush=True)
                page.wait_for_timeout(1500)
                return name
        except Exception:
            continue
    return hit


def click_apply_gate(page) -> str:
    """Click Apply / Start application / Apply Manually. Never Tailor Resume or Indeed."""
    insta = click_instahyre_apply(page)
    if insta:
        return insta
    naukri = click_naukri_quick_apply(page)
    if naukri:
        return naukri
    try:
        hit = page.evaluate(CLICK_APPLY_GATE_JS) or ""
    except Exception:
        hit = ""
    if hit and not SKIP_APPLY_LABEL.search(hit):
        print(f"  Clicked '{hit}'.", flush=True)
        page.wait_for_timeout(1200)
        if re.match(r"^apply( now)?$", hit.strip(), re.I):
            for name in ("Apply Manually", "Autofill with Resume"):
                try:
                    loc = page.get_by_text(name, exact=True).first
                    if loc.count() and loc.is_visible():
                        loc.click(timeout=1500, force=True)
                        print(f"  Clicked '{name}'.", flush=True)
                        page.wait_for_timeout(1800)
                        return name
                except Exception:
                    continue
        return hit
    for label in ("I'm interested", "Easy Apply", "Apply"):
        if click_spl_button(page, label):
            print(f"  Clicked SmartRecruiters '{label}'.", flush=True)
            return label
    for sel in (
        '[data-automation-id="applyManually"]',
        '[data-automation-id="adventureButton"]',
        '[data-automation-id="jobPostingApplyButton"]',
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                text = (loc.inner_text() or "Workday Apply").strip()[:40]
                if SKIP_APPLY_LABEL.search(text) or SIMPLIFY_RE.search(text):
                    continue
                loc.click(timeout=1500, force=True)
                print(f"  Clicked '{text}'.", flush=True)
                page.wait_for_timeout(2000)
                return text
        except Exception:
            continue
    for name in (
        "Apply Manually",
        "Autofill with Resume",
        "Apply for this job",
        "Apply Now",
        "Apply now",
        "I'm interested",
        "Start applying",
        "Quick apply",
        "Apply on Naukri",
        "Easy Apply",
        "Apply as a guest",
        "Continue without an account",
        "Apply to",
        "Apply",
    ):
        exact = name in ("Apply", "Apply now", "Apply Now")
        for role in ("button", "link"):
            try:
                loc = page.get_by_role(role, name=re.compile(rf"^{re.escape(name)}" if name == "Apply to" else rf"^{re.escape(name)}$", re.I)).first
                if not loc.count() or not loc.is_visible():
                    continue
                text = (loc.inner_text() or name)
                if SKIP_APPLY_LABEL.search(text) or SIMPLIFY_RE.search(text) or _looks_like_copilot(loc):
                    continue
                loc.click(timeout=1500, force=True)
                print(f"  Clicked '{text.strip()[:40]}'.", flush=True)
                page.wait_for_timeout(1800)
                return text.strip()[:40]
            except Exception:
                continue
    return ""


def collapse_copilot_panel(page) -> str:
    """Copilot's sidebar covers Oracle Next and PIN boxes. Collapse it; never close the tab."""
    try:
        hit = page.evaluate(
            """() => {
              const ids = ['close-button'];
              for (const id of ids) {
                const el = document.getElementById(id);
                if (el) { el.click(); return '#' + id; }
              }
              for (const el of document.querySelectorAll('button, [role=button]')) {
                const t = ((el.getAttribute('aria-label') || el.title || el.id || '') + '').toLowerCase();
                if (/collapse|close copilot|hide copilot/.test(t)) {
                  el.click();
                  return t.slice(0, 40);
                }
              }
              const overlay = document.querySelector('.simplify-jobs-shadow-root');
              if (overlay) overlay.style.pointerEvents = 'none';
              return overlay ? 'pointer-events-none' : '';
            }"""
        ) or ""
    except Exception:
        hit = ""
    if hit:
        try:
            page.wait_for_timeout(200)
        except Exception:
            pass
    return hit


def fill_oracle_hidden_radios(page) -> int:
    """Oracle Yes/No radios are 0×0. Click the visible aria-labelledby label."""
    try:
        groups = page.evaluate(
            """() => {
              const groups = {};
              for (const el of document.querySelectorAll('input[type=radio]')) {
                const name = el.name || el.id;
                const labId = (el.getAttribute('aria-labelledby') || '').split(' ')[0];
                const lab = labId ? document.getElementById(labId)
                  : document.querySelector('label[for="' + el.id + '"]');
                const opt = ((lab && lab.innerText) || '').trim();
                const wrap = el.closest('fieldset, [class*=question], [role=group], li, section')
                  || el.parentElement;
                const qlab = wrap && wrap.querySelector('label, legend, h3, h4');
                const q = ((qlab && qlab.innerText) || (wrap && wrap.innerText) || '')
                  .replace(/\\s+/g, ' ').trim().slice(0, 240);
                groups[name] = groups[name] || {q, options: [], checked: false};
                if (el.checked) groups[name].checked = true;
                groups[name].options.push({id: el.id, opt});
              }
              return groups;
            }"""
        ) or {}
    except Exception:
        return 0
    n = 0
    for group in groups.values():
        if group.get("checked"):
            continue
        q = group.get("q") or ""
        opts = [o.get("opt") or "" for o in group.get("options") or []]
        want = form_memory.infer_answer(q, opts)
        if not want:
            continue
        want_l = want.strip().lower()
        target = None
        for opt in group.get("options") or []:
            t = (opt.get("opt") or "").strip().lower()
            if t == want_l or t.startswith(want_l) or want_l in t:
                target = opt
                break
        if not target:
            continue
        try:
            page.evaluate(
                """(id) => {
                  const el = document.getElementById(id);
                  if (!el || el.checked) return;
                  const labId = (el.getAttribute('aria-labelledby') || '').split(' ')[0];
                  const lab = labId ? document.getElementById(labId)
                    : document.querySelector('label[for="' + id + '"]');
                  if (lab) lab.click();
                  else {
                    el.checked = true;
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                  }
                }""",
                target.get("id"),
            )
            n += 1
        except Exception:
            continue
    if n:
        print(f"  Selected {n} Oracle Yes/No answer(s).", flush=True)
    return n


def fill_oracle_pills(page) -> int:
    """Oracle multi-choice pills (how-heard, degree). Click the inferred option only."""
    try:
        groups = page.evaluate(
            """() => {
              return [...document.querySelectorAll('ul.cx-select-pills-container')]
                .filter(ul => ul.offsetParent)
                .map(ul => {
                  const lab = (ul.parentElement && ul.parentElement.querySelector('label'))
                    || ul.previousElementSibling;
                  const q = ((lab && lab.innerText) || '').replace(/\\s+/g, ' ').trim().slice(0, 200);
                  const pills = [...ul.querySelectorAll('button.cx-select-pill-section')].map(b => ({
                    t: (b.innerText || '').trim(),
                    sel: (b.className || '').includes('--selected'),
                  }));
                  return {q, pills};
                });
            }"""
        ) or []
    except Exception:
        return 0
    n = 0
    for group in groups:
        pills = group.get("pills") or []
        if any(p.get("sel") for p in pills):
            continue
        labels = [p.get("t") or "" for p in pills]
        want = form_memory.infer_answer(group.get("q") or "", labels)
        if not want:
            continue
        want_l = want.strip().lower()
        match = ""
        for text in labels:
            t = text.strip().lower()
            if t == want_l or want_l in t or t.startswith(want_l):
                match = text
                break
            if "bachelor" in want_l and "bachelor" in t:
                match = text
                break
            if "career" in want_l and "career site" in t:
                match = text
                break
        if not match:
            continue
        try:
            loc = page.locator("button.cx-select-pill-section").filter(has_text=match)
            if loc.count():
                loc.first.scroll_into_view_if_needed(timeout=2000)
                loc.first.click(timeout=2500, force=True)
                n += 1
                page.wait_for_timeout(250)
        except Exception:
            continue
    if n:
        print(f"  Selected {n} Oracle pill choice(s).", flush=True)
    return n


def fill_oracle_comboboxes(page) -> int:
    """Type into visible Oracle cx-select inputs and click the matching list item."""
    try:
        boxes = page.evaluate(
            """() => [...document.querySelectorAll('input[role=combobox]')].map(el => {
              const r = el.getBoundingClientRect();
              const lab = document.querySelector('label[for="' + el.id + '"]');
              const wrap = el.closest('div, li, section');
              const qlab = wrap && wrap.querySelector('label');
              return {
                id: el.id,
                name: el.name || '',
                value: (el.value || '').trim(),
                invalid: el.getAttribute('aria-invalid') === 'true',
                vis: r.width > 8 && r.height > 8,
                q: ((lab && lab.innerText) || (qlab && qlab.innerText) || el.name || '')
                  .replace(/\\s+/g, ' ').trim().slice(0, 160),
              };
            }).filter(x => x.vis || x.invalid)"""
        ) or []
    except Exception:
        return 0
    n = 0
    for box in boxes:
        if (box.get("value") or "").strip() and not box.get("invalid"):
            continue
        q = box.get("q") or box.get("name") or ""
        want = form_memory.infer_answer(q, [])
        name = (box.get("name") or "").lower()
        if not want:
            if name in {"country", "countrycode"}:
                want = "India"
            elif name in {"region2", "state", "stateprovincecode"}:
                want = "Telangana"
            elif "edu" in name or "highest" in q.lower():
                want = "Bachelor's degree"
            elif "please specify" in q.lower():
                want = "DTCC.com"
            elif name in {"educationalestablishment"}:
                want = "V.R. Siddhartha Engineering College"
        if not want:
            continue
        sel = f'[id="{box["id"]}"]'
        try:
            loc = page.locator(sel).first
            if not loc.count():
                continue
            loc.scroll_into_view_if_needed(timeout=2000)
            loc.click(timeout=2000, force=True)
            loc.fill("")
            query = want.split("(")[0].strip()
            loc.type(query[:24], delay=25)
            page.wait_for_timeout(700)
            picked = page.evaluate(
                """(want) => {
                  const w = String(want || '').toLowerCase();
                  const items = [...document.querySelectorAll('.cx-select__list-item')];
                  for (const el of items) {
                    const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                    if (!t || t.length > 90) continue;
                    const r = el.getBoundingClientRect();
                    if (r.width < 8 || r.height < 8) continue;
                    const low = t.toLowerCase();
                    if (low === w || low.startsWith(w) || w.includes(low) || low.includes(w.split(' ')[0])) {
                      el.click();
                      return t;
                    }
                  }
                  return '';
                }""",
                want,
            )
            if picked:
                n += 1
                page.wait_for_timeout(250)
        except Exception:
            continue
    if n:
        print(f"  Filled {n} Oracle combobox(es).", flush=True)
    return n


def _gmail_tab(page):
    try:
        ctx = page.context
    except Exception:
        return None
    for p in ctx.pages:
        try:
            if "mail.google.com" in (p.url or ""):
                return p
        except Exception:
            continue
    return None


def latest_gmail_identity_code(page, job: dict | None = None) -> str:
    """Read a 6-digit identity code from the already-open Gmail tab. Never print it."""
    gmail = _gmail_tab(page)
    if not gmail:
        return ""
    skip = {str((job or {}).get("job_id") or "")}
    try:
        url = (job or {}).get("apply_url") or (job or {}).get("url") or page.url or ""
        skip |= {m.group(1) for m in re.finditer(r"/job/(\d{5,})", url)}
    except Exception:
        pass
    skip.discard("")
    try:
        blob = gmail.inner_text("body") or ""
    except Exception:
        blob = ""
    patterns = (
        r"using this code:\s*(\d{6})",
        r"one-time pass code:\s*(\d{6})",
        r"code to confirm your identity[^0-9]{0,40}(\d{6})",
        r"verification code[^0-9]{0,40}(\d{6})",
        r"confirm your identity using this code:\s*(\d{6})",
    )
    for pat in patterns:
        for match in re.finditer(pat, blob, re.I):
            code = match.group(1)
            if code in skip or code.startswith("202"):
                continue
            return code
    return ""


def fill_email_identity_code(page, job: dict | None = None) -> bool:
    """Oracle PIN / VERIFY screens: paste the Gmail identity code and continue."""
    try:
        blob = page_text(page)[:1800]
    except Exception:
        blob = ""
    has_pin = False
    try:
        has_pin = bool(page.locator('[id="pin-code-1"]').count())
    except Exception:
        has_pin = False
    if not has_pin and not re.search(
        r"verify it'?s you|we've sent a verification code|enter verification code",
        blob,
        re.I,
    ):
        return False
    code = latest_gmail_identity_code(page, job)
    if not code:
        print("  Identity code screen: no code in the open Gmail tab yet.", flush=True)
        return False
    filled = False
    try:
        filled = bool(
            page.evaluate(
                """(code) => {
                  const digits = String(code).split('');
                  let n = 0;
                  for (let i = 0; i < digits.length; i++) {
                    const el = document.getElementById('pin-code-' + (i + 1));
                    if (!el) continue;
                    el.value = digits[i];
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    n++;
                  }
                  const single = document.querySelector(
                    'input[autocomplete="one-time-code"], input[name*=pin i], input[aria-label*="verification code" i]'
                  );
                  if (!n && single) {
                    single.value = code;
                    single.dispatchEvent(new Event('input', {bubbles: true}));
                    n = 1;
                  }
                  return n > 0;
                }""",
                code,
            )
        )
    except Exception:
        filled = False
    if not filled:
        return False
    print("  Filled identity verification code from Gmail.", flush=True)
    try:
        loc = page.get_by_text("Keep me signed in", exact=False).first
        if loc.count() and loc.is_visible():
            loc.click(timeout=800, force=True)
    except Exception:
        pass
    try:
        page.evaluate(
            """() => {
              for (const b of document.querySelectorAll('button')) {
                if (/^verify$/i.test((b.innerText || '').trim())) { b.click(); return true; }
              }
              return false;
            }"""
        )
        page.wait_for_timeout(2500)
    except Exception:
        pass
    return True


def fill_oracle_form(page, job: dict | None = None) -> int:
    """Oracle Cloud easy-apply: hidden radios, pills, comboboxes, email PIN."""
    n = 0
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "oraclecloud.com" not in url:
        fill_email_identity_code(page, job)
        return 0
    n += fill_oracle_hidden_radios(page)
    n += fill_oracle_pills(page)
    n += fill_oracle_comboboxes(page)
    fill_email_identity_code(page, job)
    return n


def _dismiss_native_file_dialog() -> None:
    """Copilot/Workday sometimes opens a GTK file picker that blocks every click."""
    try:
        import subprocess
        env = os.environ.copy()
        env.setdefault("DISPLAY", ":1")
        subprocess.run(["xdotool", "key", "Escape"], env=env, timeout=2, check=False)
    except Exception:
        pass


def _workday_form_field(page, pattern: str):
    loc = page.locator("[data-automation-id^='formField-']").filter(
        has_text=re.compile(pattern, re.I)
    ).first
    if loc.count():
        return loc
    q = page.get_by_text(re.compile(pattern, re.I)).first
    if q.count():
        return q.locator("xpath=ancestor::*[starts-with(@data-automation-id,'formField')][1]")
    return page.locator("[data-automation-id='__missing__']")


def _pick_workday_list_option(page, typed: str = "Career Site") -> bool:
    """Click a Workday promptOption, including nested source lists (category → site)."""
    page.wait_for_timeout(300)
    picked = False
    for _ in range(4):
        opts = page.locator("[data-automation-id='promptOption']")
        if not opts.count():
            opts = page.locator("[role='option']")
        if not opts.count():
            break
        preferred = (
            r"^naukri$",
            r"^iimjobs$",
            r"^linkedin$",
            r"career site",
            r"company website",
            re.escape(typed) if typed else r"career",
            r"azure",
            r"aws",
            r"c#",
            r"\.net",
            r"sql",
            r"agile",
            r"english",
            r"mobile",
            r"cell",
        )
        clicked = False
        for pat in preferred:
            try:
                hit = opts.filter(has_text=re.compile(pat, re.I)).first
                if hit.count():
                    hit.click(timeout=1500, force=True)
                    page.wait_for_timeout(400)
                    clicked = True
                    picked = True
                    break
            except Exception:
                continue
        if not clicked:
            skip = {
                "", "select", "select one", "select an option", "search",
                "no options", "no items", "no results", "please select a value",
            }
            try:
                n = min(opts.count(), 20)
            except Exception:
                n = 0
            for i in range(n):
                try:
                    opt = opts.nth(i)
                    text = (opt.inner_text() or "").strip()
                    if text.lower() in skip or len(text) > 80:
                        continue
                    opt.click(timeout=1500, force=True)
                    page.wait_for_timeout(400)
                    clicked = True
                    picked = True
                    break
                except Exception:
                    continue
        if not clicked:
            break
    if picked:
        return True
    try:
        if page.locator("[data-automation-id='promptOption'], [role='option']").count():
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(120)
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)
            return True
    except Exception:
        pass
    return False


WORKDAY_CLICK_NO_JS = """(root) => {
  if (!root) return 'missing';
  const radios = [...root.querySelectorAll('input[type=radio], [role=radio]')];
  for (const el of radios) {
    const t = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '') + ' ' + (el.value || '')).toLowerCase();
    const on = el.checked || el.getAttribute('aria-checked') === 'true';
    if (on && /\\bno\\b/.test(t)) return 'already';
  }
  let target = radios.find((el) => {
    const t = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '') + ' ' + (el.value || '')).trim().toLowerCase();
    return t === 'no' || t === 'false' || el.value === 'false';
  });
  if (!target && radios.length >= 2) target = radios[1];
  if (!target) {
    const lab = [...root.querySelectorAll('label')].find((l) => /^\\s*No\\s*$/i.test((l.innerText || '').trim()));
    if (lab) { lab.click(); return 'label'; }
    return 'none';
  }
  const lab = target.id ? root.querySelector('label[for="' + target.id + '"]') : null;
  (lab || target).click();
  if (target.tagName === 'INPUT') {
    target.checked = true;
    target.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
    target.dispatchEvent(new Event('change', {bubbles: true, composed: true}));
  }
  return 'clicked';
}"""


def _workday_prompt_committed(field) -> bool:
    try:
        return bool(
            field.locator(
                "[data-automation-id='multiselectlistItem'], "
                "[data-automation-id='selectedItem'], "
                "[data-automation-id='promptSelectedItem']"
            ).count()
        )
    except Exception:
        return False


WORKDAY_SKILL_SEARCHES = (
    "Azure",
    "Microsoft Azure",
    "Amazon Web Services (AWS)",
    "AWS",
    "SQL",
    "SQL Server",
    "Microsoft SQL Server",
    "Agile",
    "Agile Methodologies",
    "C#",
    "C Sharp",
    "C# (Programming Language)",
    ".NET",
    ".NET Framework",
    ".NET Core",
    "ASP.NET",
    "ASP.NET Core",
    "Kubernetes",
    "Docker",
    "Angular",
    "AngularJS",
    "React.js",
    "React",
    "Microservices",
    "Apache Kafka",
    "Kafka",
    "REST",
    "RESTful WebServices",
    "API",
    "Software Development",
    "Software Engineering",
    "Solution Architecture",
    "Architecture",
)


def _workday_skill_field(page):
    """Workday skills widget: formField id, or the block that contains Type to Add Skills."""
    for sel in (
        "[data-automation-id='formField-skills']",
        "[data-automation-id*='Skills']",
        "[data-automation-id*='skill']",
    ):
        loc = page.locator(sel).first
        try:
            if loc.count():
                return loc
        except Exception:
            continue
    loc = _workday_form_field(page, r"type to add skills|add skills")
    try:
        if loc.count():
            return loc
    except Exception:
        pass
    try:
        t = page.get_by_text(re.compile(r"type to add skills", re.I)).first
        if t.count():
            wrap = t.locator("xpath=ancestor::*[.//input[@placeholder]][1]")
            if wrap.count():
                return wrap
    except Exception:
        pass
    return page.locator("[data-automation-id='__missing__']")


def _workday_clear_prompt_input(page, box) -> None:
    try:
        box.click(timeout=800, force=True)
        box.fill("")
    except Exception:
        try:
            page.keyboard.press("Control+a")
            page.keyboard.press("Backspace")
        except Exception:
            pass
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
    except Exception:
        pass


def _workday_skill_search_empty(page, field) -> bool:
    """True only when the open list has no catalog rows. Ignore the standing 'No Items' hint."""
    try:
        opts = page.locator(
            "[data-automation-id='promptOption'], [role='option'], "
            "[data-automation-id='menuItem']"
        )
        n = opts.count()
    except Exception:
        n = 0
    if n == 0:
        return True
    real = 0
    for i in range(min(n, 12)):
        try:
            text = (opts.nth(i).inner_text() or "").strip().lower()
        except Exception:
            continue
        if text and text not in {"no items", "no results", "no results were found", "search"}:
            real += 1
    return real == 0


def _workday_add_skill(page, field, skill: str) -> bool:
    """Type a catalog skill, press Enter (required), then click a list option."""
    if _workday_prompt_committed(field):
        return True
    collapse_copilot_panel(page)
    try:
        field.scroll_into_view_if_needed(timeout=1500)
    except Exception:
        pass
    box = field.locator(
        "[data-automation-id='searchBox'] input, "
        "input[placeholder*='Search' i], "
        "input[placeholder*='Type to Add' i], "
        "input:not([type=hidden]):not([type=radio]):not([type=checkbox])"
    ).first
    if not box.count():
        box = field.locator("[role=combobox], [contenteditable='true']").first
    if not box.count():
        return False
    try:
        box.click(timeout=1500, force=True)
    except Exception:
        return False
    _workday_clear_prompt_input(page, box)
    try:
        box.type(skill, delay=35)
    except Exception:
        try:
            page.keyboard.type(skill, delay=35)
        except Exception:
            return False
    # State Street: "Options load only after you press Enter."
    try:
        page.keyboard.press("Enter")
    except Exception:
        return False
    page.wait_for_timeout(1400)
    try:
        page.wait_for_selector(
            "[data-automation-id='promptOption'], [role='option'], "
            "[data-automation-id='menuItem']",
            timeout=4000,
            state="attached",
        )
    except Exception:
        pass
    if _workday_skill_search_empty(page, field):
        _workday_clear_prompt_input(page, box)
        return False
    if not _pick_workday_list_option(page, skill):
        _workday_clear_prompt_input(page, box)
        return False
    if _workday_prompt_committed(field):
        print(f"  Workday: added skill {skill}.", flush=True)
        return True
    _workday_clear_prompt_input(page, box)
    return False


def fill_workday_skills(page) -> int:
    """Commit at least one Workday skill chip. Typed text alone is not enough."""
    field = _workday_skill_field(page)
    has_field = False
    try:
        has_field = bool(field.count())
    except Exception:
        has_field = False
    if has_field and _workday_prompt_committed(field):
        return 0
    try:
        btn = page.get_by_role("button", name=re.compile(r"autofill \d+ skills?", re.I)).first
        if btn.count() and btn.is_visible():
            btn.click(timeout=1500)
            print("  Clicked Copilot Autofill skill(s).", flush=True)
            page.wait_for_timeout(800)
            if has_field and _workday_prompt_committed(field):
                return 1
    except Exception:
        pass
    if has_field:
        for name in WORKDAY_SKILL_SEARCHES:
            if _workday_add_skill(page, field, name):
                return 1
    try:
        label = page.get_by_text(re.compile(r"type to add skills", re.I)).first
        if label.count() and label.is_visible():
            label.click(timeout=1200)
            page.wait_for_timeout(400)
    except Exception:
        pass
    # Widget often has no formField id — use the in-form Search box (not header Search for Jobs).
    try:
        boxes = page.locator(
            "input[placeholder='Search'], input[placeholder*='Type to Add' i], "
            "input[placeholder*='Add Skills' i]"
        )
        nbox = boxes.count()
    except Exception:
        nbox = 0
    for i in range(min(nbox, 8)):
        box = boxes.nth(i)
        try:
            if not box.is_visible():
                continue
            bb = box.bounding_box() or {}
            if (bb.get("width") or 0) < 180 or (bb.get("y") or 0) < 120:
                continue
        except Exception:
            continue
        for name in WORKDAY_SKILL_SEARCHES:
            try:
                box.click(timeout=1200, force=True)
                box.fill("")
                box.type(name, delay=30)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1800)
            except Exception:
                continue
            if _pick_workday_list_option(page, name):
                print(f"  Workday: added skill {name} (search box).", flush=True)
                return 1
            _workday_clear_prompt_input(page, box)
    print(
        "  Workday: no catalog skill matched. Leftover: Type to Add Skills — pick one in Desktop.",
        flush=True,
    )
    return 0


def _workday_form_fields(page, pattern: str):
    loc = page.locator("[data-automation-id^='formField-']").filter(
        has_text=re.compile(pattern, re.I)
    )
    try:
        n = loc.count()
    except Exception:
        n = 0
    return [loc.nth(i) for i in range(n)]


def _workday_fill_text_fields(page, pattern: str, value: str) -> int:
    n = 0
    for field in _workday_form_fields(page, pattern):
        try:
            box = field.locator(
                "input:not([type=hidden]):not([type=radio]):not([type=checkbox]), textarea"
            ).first
            if not box.count() or not box.is_visible():
                continue
            cur = ""
            try:
                cur = (box.input_value() or "").strip()
            except Exception:
                pass
            if cur and cur.lower() not in {"", "select", "n/a"} and value.lower() != "n/a":
                continue
            if cur.lower() == value.lower():
                continue
            box.click(timeout=800, force=True)
            box.fill("")
            box.type(value, delay=20)
            n += 1
        except Exception:
            continue
    return n


def fill_workday_compliance(page) -> int:
    """State Street conflict questions: No + N/A. Typed blanks keep Next disabled."""
    filled = 0
    for pat in (
        r"relative of a current public official",
        r"senior commercial person",
        r"senior level person",
        r"please select one of the below",
    ):
        for field in _workday_form_fields(page, pat):
            if _workday_select_prompt(page, field, "No"):
                filled += 1
                print(f"  Workday: {pat} = No.", flush=True)
    filled += _workday_fill_text_fields(page, r"relationship with this individual", "N/A")
    filled += _workday_fill_text_fields(page, r"institution name and level", "N/A")
    filled += _workday_fill_text_fields(
        page,
        r"name of your agency|enter your name \(required\)",
        "Mohammed Abdul Rafi Ahmed / N/A",
    )
    if filled:
        print(f"  Workday: filled {filled} compliance field(s).", flush=True)
    return filled


def _workday_select_prompt(page, field, typed: str) -> bool:
    """Open a Workday prompt and click a list option. Typed search text is not a value."""
    try:
        if not field.count():
            return False
        if _workday_prompt_committed(field):
            return True
        collapse_copilot_panel(page)
        field.scroll_into_view_if_needed(timeout=1500)
        box = field.locator(
            "input:not([type=hidden]):not([type=radio]):not([type=checkbox])"
        ).first
        if not box.count():
            box = field.locator(
                "[role=combobox], [data-automation-id='selectWidget'], button"
            ).first
        if not box.count():
            box = field
        box.click(timeout=1500, force=True)
        page.wait_for_timeout(250)
        # Short filter so the list is not empty. Full phrases like
        # "Company Careers Website" often match zero Workday options.
        needle = (typed or "Career").split()[0]
        try:
            box.fill("")
            box.type(needle, delay=40)
        except Exception:
            try:
                page.keyboard.press("Control+a")
                page.keyboard.type(needle, delay=40)
            except Exception:
                pass
        try:
            page.wait_for_selector(
                "[data-automation-id='promptOption']", timeout=2500, state="attached"
            )
        except Exception:
            pass
        return _pick_workday_list_option(page, typed)
    except Exception:
        return False


def fill_workday_required_questions(page) -> int:
    """Click Workday widgets Copilot cannot fill: how-heard, previously-worked, device type.

    Typed text in a how-heard search box is not a selection — Next stays disabled
    until a promptOption is clicked. Previously-worked is a Yes/No radio; click
    the circle to the left of No. Phone Device Type must be Mobile, not the phone number.
    """
    _dismiss_native_file_dialog()
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    filled = 0
    collapse_copilot_panel(page)
    # How-heard overlay covers the Yes/No radios — pick a source leaf first, then No.
    hear = _workday_form_field(page, r"how did you hear")
    if _workday_select_prompt(page, hear, "Naukri"):
        filled += 1
        print("  Workday: how did you hear — selected an option.", flush=True)
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    except Exception:
        pass
    prev = _workday_form_field(page, r"previously worked")
    try:
        if prev.count():
            hit = prev.evaluate(WORKDAY_CLICK_NO_JS)
            if hit in {"clicked", "label", "already"}:
                filled += 1
                print(f"  Workday: previously worked = No ({hit}).", flush=True)
            else:
                no = prev.get_by_text("No", exact=True).first
                if no.count():
                    box = no.bounding_box() or {}
                    y = (box.get("y") or 0) + max((box.get("height") or 8) / 2, 4)
                    page.mouse.click(max((box.get("x") or 24) - 12, 8), y)
                    filled += 1
                    print("  Workday: previously worked = No (mouse).", flush=True)
    except Exception:
        pass
    device = _workday_form_field(page, r"phone device type|device type")
    if _workday_select_prompt(page, device, "Mobile"):
        filled += 1
        print("  Workday: phone device type = Mobile.", flush=True)
    lang = page.locator(
        "[data-automation-id='formField-language'], [data-automation-id='language']"
    ).first
    if not lang.count():
        lang = _workday_form_field(page, r"field language|languages")
    if _workday_select_prompt(page, lang, "English"):
        filled += 1
        print("  Workday: language = English.", flush=True)
    if fill_workday_skills(page):
        filled += 1
    filled += fill_workday_compliance(page)
    return filled


def fill_workday_form(page) -> int:
    """Fill Workday easy-apply fields by data-automation-id. Copilot often never attaches."""
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "myworkdayjobs.com" not in url and "myworkdaysite.com" not in url:
        return 0
    _dismiss_native_file_dialog()
    a = form_memory._answers()
    mapping = [
        ("legalNameSection_firstName", a["firstName"]),
        ("legalNameSection_lastName", a["lastName"]),
        ("legalNameSection_middleName", "Abdul Rafi"),
        ("addressSection_addressLine1", "303, Vishnu Homes, Whitefields"),
        ("addressSection_addressLine2", "Kondapur"),
        ("addressSection_city", a["city"]),
        ("addressSection_postalCode", "500084"),
        ("phone-number", a["phone"]),
        ("phoneNumber", a["phone"]),
        ("email", a["email"]),
        ("candidateEmail", a["email"]),
        ("linkedinQuestion", a["linkedin"] or ""),
    ]
    filled = 0
    for auto_id, value in mapping:
        if not value:
            continue
        try:
            loc = page.locator(f"[data-automation-id='{auto_id}']").first
            if not loc.count():
                continue
            target = loc
            tag = ""
            try:
                tag = (loc.evaluate("el => (el.tagName||'').toLowerCase()") or "")
            except Exception:
                tag = ""
            if tag not in {"input", "textarea"}:
                inner = loc.locator("input:not([type=hidden]):not([type=checkbox]):not([type=radio]), textarea").first
                if inner.count():
                    target = inner
            if not target.is_visible():
                continue
            cur = ""
            try:
                cur = (target.input_value() or "").strip()
            except Exception:
                pass
            if cur:
                continue
            target.click(timeout=1200)
            ats_fill.native_fill(target, str(value))
            filled += 1
        except Exception:
            continue
    # Country / state typeaheads
    try:
        form_memory.fill_india_state_typeahead(page)
    except Exception:
        pass
    form_memory.fill_visible(page)
    collapse_copilot_panel(page)
    filled += fill_workday_required_questions(page)
    page.wait_for_timeout(400)
    if filled:
        print(f"  Filled {filled} Workday field(s).", flush=True)
    # Workday Next / Submit on the form, not Copilot.
    try:
        nxt = page.locator("[data-automation-id='bottom-navigation-next-button']").first
        if nxt.count() and nxt.is_enabled():
            collapse_copilot_panel(page)
            nxt.click(timeout=2000, force=True)
            page.wait_for_timeout(1200)
            print("  Clicked Workday Next.", flush=True)
            filled += 1
    except Exception:
        pass
    return filled


def icims_auth0_blocked(page) -> bool:
    """Auth0 /u/login/password rate-limit or Oops page. Do not keep POSTing."""
    ctx = getattr(page, "context", None)
    pages = list(ctx.pages) if ctx is not None else [page]
    for p in pages:
        try:
            if p.is_closed():
                continue
            u = (p.url or "").lower()
        except Exception:
            continue
        if "login.icims.com" not in u:
            continue
        blob = ""
        try:
            blob += " " + (p.title() or "")
        except Exception:
            pass
        try:
            blob += " " + (p.inner_text("body") or "")[:2000]
        except Exception:
            pass
        try:
            blob += " " + (p.evaluate("() => (document.body && document.body.innerText) || ''") or "")[:2000]
        except Exception:
            pass
        t = blob.lower()
        if "rate limit" in t or "oops, something went wrong" in t or "invalid_request" in t:
            return True
    return False


def fill_icims_login(page) -> int:
    """Schwab iCIMS: open Returning candidate login once, then Auth0 email/Continue."""
    global ICIMS_LOGIN_CLICKED
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    # Do not hijack unrelated leftover jobs just because an Auth0 tab is parked.
    if "icims.com" not in url:
        return 0
    if icims_auth0_blocked(page):
        print("  iCIMS Auth0 rate-limited. Not submitting another password.", flush=True)
        return 0
    email = google_auth.EMAIL
    phone = apply_now.C.get("phoneNational") or "8790251698"
    filled = 0
    filled += _fill_icims_universal_login(page)
    if ICIMS_LOGIN_CLICKED:
        return filled
    if "login.icims.com" not in url:
        for name in ("Returning candidate login", "Log in >"):
            try:
                loc = page.get_by_role("link", name=re.compile(rf"^{re.escape(name)}$", re.I)).first
                if not loc.count():
                    loc = page.get_by_text(re.compile(rf"^{re.escape(name)}$", re.I)).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=2000)
                    print(f"  Clicked iCIMS '{name}'.", flush=True)
                    ICIMS_LOGIN_CLICKED = True
                    page.wait_for_timeout(2000)
                    filled += 1
                    break
            except Exception:
                continue
    filled += _fill_icims_universal_login(page)
    if filled:
        return filled
    try:
        fr = page.frame_locator(
            "iframe[name='icims_content_iframe'], iframe#icims_content_iframe, iframe"
        ).first
        em = fr.locator("#email, input[name='css_loginName'], input[type=email]").first
        if em.count():
            em.fill(email, timeout=2500)
            filled += 1
        ph = fr.locator("#phoneNumber, input[name='css_phoneNumber']").first
        if ph.count():
            ph.fill(str(phone), timeout=2500)
            filled += 1
        btn = fr.locator("#enterEmailSubmitButton").first
        if btn.count() and not ICIMS_LOGIN_CLICKED:
            btn.click(timeout=2500)
            print("  Clicked iCIMS email continue.", flush=True)
            page.wait_for_timeout(1500)
            filled += 1
    except Exception:
        pass
    if filled:
        print(f"  Filled {filled} iCIMS login control(s).", flush=True)
    return filled


def _prune_icims_login_tabs(page) -> None:
    """Keep one Auth0 identifier tab. Extra Returning-candidate clicks used to open many."""
    ctx = getattr(page, "context", None)
    if ctx is None:
        return
    tabs = []
    for p in list(ctx.pages):
        try:
            if p.is_closed():
                continue
            if "login.icims.com" in (p.url or "").lower():
                tabs.append(p)
        except Exception:
            continue
    for extra in tabs[:-1]:
        try:
            extra.close()
        except Exception:
            continue


def _fill_icims_universal_login(page) -> int:
    """Fill username/email + Continue on login.icims.com Auth0. Never log secrets."""
    global ICIMS_LOGIN_CLICKED, ICIMS_CONTINUE_CLICKS, ICIMS_PASSWORD_SUBMITS
    email = google_auth.EMAIL
    filled = 0
    _prune_icims_login_tabs(page)
    ctx = getattr(page, "context", None)
    pages = list(ctx.pages) if ctx is not None else [page]
    for p in pages:
        try:
            if p.is_closed():
                continue
            u = (p.url or "").lower()
        except Exception:
            continue
        if "login.icims.com" not in u:
            continue
        ICIMS_LOGIN_CLICKED = True
        if not (OWNER_PRESENT or WATCH_OPEN):
            try:
                p.bring_to_front()
            except Exception:
                pass
        if "/login/password" not in u:
            for sel in (
                "input[name='username']",
                "input[name='email']",
                "input[type=email]",
                "#username",
                "input[autocomplete='username']",
            ):
                try:
                    loc = p.locator(sel).first
                    if loc.count() and loc.is_visible():
                        loc.fill(email, timeout=2500)
                        filled += 1
                        print("  Filled iCIMS username/email.", flush=True)
                        break
                except Exception:
                    continue
            pw_visible = False
            try:
                pw = p.locator("input[type=password]").first
                pw_visible = bool(pw.count() and pw.is_visible())
            except Exception:
                pw_visible = False
            if not pw_visible and ICIMS_CONTINUE_CLICKS < 2:
                try:
                    btn = p.get_by_role("button", name=re.compile(r"^continue$", re.I)).first
                    if btn.count() and btn.is_visible():
                        btn.click(timeout=2500)
                        ICIMS_CONTINUE_CLICKS += 1
                        print("  Clicked iCIMS Continue.", flush=True)
                        p.wait_for_timeout(2000)
                        filled += 1
                except Exception:
                    pass
        passwords = google_auth.load_portal_passwords()
        if passwords and ICIMS_PASSWORD_SUBMITS < len(passwords):
            try:
                pw = p.locator("input[type=password]").first
                if pw.count():
                    pw.fill(passwords[ICIMS_PASSWORD_SUBMITS], timeout=2500)
                    nxt = p.get_by_role("button", name=re.compile(r"^(continue|log in|sign in)$", re.I)).first
                    if nxt.count():
                        nxt.click(timeout=2500, force=True)
                    ICIMS_PASSWORD_SUBMITS += 1
                    print("  Submitted iCIMS password.", flush=True)
                    p.wait_for_timeout(2500)
                    filled += 1
            except Exception:
                pass
        return filled
    return 0


def click_dhl_apply_method(page) -> bool:
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "avature.net" not in url and "careers.dhl.com" not in url:
        return False
    # Only the method-picker page. "Start" on later steps is a progress tab, not Apply.
    if "applicationmethods" not in url:
        try:
            if not page.get_by_text("Upload resume", exact=True).count():
                return False
        except Exception:
            return False
    for name in ("Upload resume", "Without Resume"):
        try:
            loc = page.get_by_role("button", name=name, exact=False).first
            if not loc.count():
                loc = page.get_by_role("link", name=name, exact=False).first
            if not loc.count():
                loc = page.get_by_text(name, exact=True).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=2000)
                print(f"  Clicked DHL '{name}'.", flush=True)
                page.wait_for_timeout(1500)
                return True
        except Exception:
            continue
    return False


def fill_leftover_dropdowns(page) -> int:
    """Salutation / preferred language / similar selects Copilot leaves on 'Select an option'."""
    filled = 0
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    pairs = [
        (r"salutation", "Mr"),
        (r"preferred language", "English"),
        (r"^degree$|degree \*|highest (degree|education)", "Bachelor"),
    ]
    # Workday how-heard is a nested prompt (Career → Asia Job Boards → Naukri).
    # Typing "Career" here undoes fill_workday_required_questions().
    if "myworkdayjobs" not in url and "workday" not in url:
        pairs.insert(2, (r"how did you hear", "Career"))
    pairs = tuple(pairs)
    for pat, value in pairs:
        try:
            lab = page.get_by_text(re.compile(pat, re.I)).first
            if not lab.count() or not lab.is_visible():
                continue
            box = page.get_by_label(re.compile(pat, re.I)).first
            if not box.count():
                box = lab.locator(
                    "xpath=ancestor::*[self::div or self::li or self::fieldset][1]"
                ).locator("select, [role=combobox], button, [class*='select']").first
            if not box.count():
                continue
            if ats_fill.handle_dropdown(page, box, value):
                filled += 1
                print(f"  Selected '{value}' for {pat}.", flush=True)
        except Exception:
            continue
    texts = (
        (r"name of university|university/college|school or university", "V.R. Siddhartha Engineering College"),
        (r"^grade$|grade \*|overall result|gpa", "First Class"),
    )
    for pat, value in texts:
        try:
            box = page.get_by_label(re.compile(pat, re.I)).first
            if not box.count() or not box.is_visible():
                continue
            try:
                cur = (box.input_value() or "").strip()
            except Exception:
                cur = ""
            if cur:
                continue
            box.fill(value, timeout=2000)
            filled += 1
            print(f"  Filled '{value}' for {pat}.", flush=True)
        except Exception:
            continue
    return filled


def click_next_or_submit(page) -> str:
    """Click one navigation control. Returns clicked|submitted|none."""
    collapse_copilot_panel(page)
    dismiss_overlays(page)
    if is_success(page):
        return "submitted"
    try:
        nav_url = (page.url or "").lower()
    except Exception:
        nav_url = ""
    # Auth0 Continue / Schwab Log in are owned by fill_icims_login. Generic Continue
    # here reopened extra identifier tabs and never reached the password step.
    if "login.icims.com" in nav_url or (
        "icims.com" in nav_url and "/login" in nav_url and ICIMS_LOGIN_CLICKED
    ):
        if fill_icims_login(page):
            return "clicked"
        return "none"
    # Real ATS Submit, not Copilot #proxy-submit-button (Phenom review stays put otherwise).
    if ats_fill.click_ats_submit(page):
        for _ in range(6):
            if is_success(page) or simplify_copilot.submitted(page):
                return "submitted"
            page.wait_for_timeout(800)
        return "clicked"
    for label in ("Submit application", "Submit Application", "Submit", "Save and Next", "Next"):
        if click_spl_button(page, label):
            print(f"  Clicked ATS '{label}'.", flush=True)
            page.wait_for_timeout(800)
            return "submitted" if is_success(page) else "clicked"
    for sel in (
        "button:has-text('Submit application')",
        "button:has-text('Submit Application')",
        "button:has-text('Submit your application')",
        "button:has-text('Submit Your Application')",
        "input[type=submit][value*='Submit' i]",
        "button[type=submit]:has-text('Submit')",
        "[data-automation-id='bottom-navigation-next-button'][aria-label*='Submit' i]",
        "[data-automation-id='pageFooterNextButton']",
        "button:has-text('Submit')",
        "spl-button:has-text('Submit')",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible() and loc.is_enabled():
                text = loc.inner_text() or loc.get_attribute("value") or loc.get_attribute("aria-label") or ""
                el_id = loc.get_attribute("id") or ""
                if el_id == "proxy-submit-button" or SIMPLIFY_RE.search(text) or SKIP_APPLY_LABEL.search(text):
                    continue
                loc.scroll_into_view_if_needed(timeout=1500)
                loc.click(timeout=2000, force=True)
                page.wait_for_timeout(1800)
                return "submitted" if is_success(page) else "clicked"
        except Exception:
            continue
    for sel in (
        "[data-automation-id='bottom-navigation-next-button']",
        "button:has-text('Next')",
        "button:has-text('Continue')",
        "button:has-text('Save and Next')",
        "button:has-text('Save & Next')",
        "button:has-text('Save and continue')",
        "button:has-text('Save & Continue')",
        "button:has-text('Review')",
        "button:has-text('I Acknowledge')",
        "button:has-text('Acknowledge')",
        "button.btn-primary:has-text('Next')",
        "button.btn-primary:has-text('Continue')",
        "spl-button:has-text('Next')",
        "spl-button:has-text('Continue')",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible() and loc.is_enabled():
                text = loc.inner_text() or loc.get_attribute("aria-label") or ""
                if SIMPLIFY_RE.search(text) or SKIP_APPLY_LABEL.search(text):
                    continue
                loc.click(timeout=2000, force=True)
                page.wait_for_timeout(1400)
                return "clicked"
        except Exception:
            continue
    try:
        loc = page.locator("button.apply-flow-pagination__button.theme-color-1").last
        if loc.count() and loc.is_enabled():
            aria = (loc.get_attribute("aria-label") or loc.inner_text() or "").strip()
            if aria and not re.search(r"required fields to continue", aria, re.I):
                loc.click(timeout=2000, force=True)
                page.wait_for_timeout(1600)
                return "submitted" if is_success(page) else "clicked"
    except Exception:
        pass
    return "none"


def notify_captcha(job: dict, page) -> None:
    """Tell the owner in the agent log that a CAPTCHA needs solving now."""
    company = job.get("company") or ""
    title = job.get("title") or ""
    url = ""
    try:
        url = page.url
    except Exception:
        url = job.get("apply_url") or ""
    if OWNER_PRESENT or WATCH_OPEN:
        action = "I stopped on this tab. Solve the CAPTCHA — I will wait and then submit."
    else:
        action = "Parked this tab. Starting the next leftover now."
    banner = (
        f"\n{'!' * 72}\n"
        f"  CAPTCHA — please solve it now in Desktop / Take control\n"
        f"  {company}: {title}\n"
        f"  {url}\n"
        f"  {action}\n"
        f"{'!' * 72}\n"
    )
    print(banner, flush=True)
    if url:
        PARKED_CAPTCHA_URLS.add(url)
        PARKED_CAPTCHA_URLS.add(url.split("?")[0])
    path = ROOT / "data" / "applications" / "CAPTCHA.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"- **NEED CAPTCHA** {company} — {title}\n  {url}\n"
    prev = path.read_text(encoding="utf-8") if path.exists() else "# CAPTCHA — owner action needed\n\n"
    if url and url in prev:
        return
    path.write_text(prev + line, encoding="utf-8")


def park_tab_url(url: str) -> None:
    if not url:
        return
    PARKED_CAPTCHA_URLS.add(url)
    PARKED_CAPTCHA_URLS.add(url.split("?")[0])


def notify_amazon_signin(job: dict, page) -> None:
    """Keep the Amazon sign-in tab open so the owner can log in when they are here."""
    company = job.get("company") or "Amazon"
    title = job.get("title") or ""
    url = ""
    try:
        url = page.url
    except Exception:
        url = job.get("apply_url") or ""
    park_tab_url(url)
    park_tab_url("https://passport.amazon.jobs/")
    banner = (
        f"\n{'!' * 72}\n"
        f"  AMAZON SIGN-IN — please sign in on this tab (Desktop / Take control)\n"
        f"  {company}: {title}\n"
        f"  {url}\n"
        f"  Leaving this tab open. Starting the next leftover now.\n"
        f"{'!' * 72}\n"
    )
    print(banner, flush=True)


def required_field_issues(page) -> list[str]:
    """Visible required-field messages the owner may need to complete."""
    try:
        blob = page_text(page)
    except Exception:
        return []
    out: list[str] = []
    for raw in blob.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if re.search(
            r"this information is required|is required \(|no results were found|"
            r"please provide a valid email|confirm your email|"
            r"^institution\*|^institution required|"
            r"this field is required|please select a value|"
            r"enter n/a if not applicable|please select one of the below|"
            r"errors found",
            line,
            re.I,
        ):
            if 8 < len(line) < 220 and line not in out:
                out.append(line)
    return out[:12]


def form_fingerprint(page) -> str:
    """Stable signature of the current form so we can detect a repeat loop."""
    try:
        url = (page.url or "").split("?")[0]
    except Exception:
        url = ""
    issues = "|".join(required_field_issues(page)[:8])
    invalid = ""
    try:
        invalid = page.evaluate(
            """() => [...document.querySelectorAll('.ng-invalid[id], [aria-invalid="true"][id], spl-input.ng-invalid, spl-autocomplete[errorstate]')]
              .map(el => el.id || el.getAttribute('label') || el.tagName).filter(Boolean).slice(0,12).join('|')"""
        ) or ""
    except Exception:
        pass
    editor = ""
    try:
        if page.locator("spl-button[aria-label*='Cancel adding' i]").count():
            editor = "open-editor"
    except Exception:
        pass
    return f"{url}::{issues}::{invalid}::{editor}"


def cancel_incomplete_editors(page) -> int:
    """Close Add Experience / Add Education drawers that block Submit."""
    n = 0
    try:
        n = int(
            page.evaluate(
                """() => {
                  const hosts = [...document.querySelectorAll('spl-button')].filter(h =>
                    /cancel adding/i.test(h.getAttribute('aria-label') || '')
                  );
                  for (const h of hosts) {
                    const btn = (h.shadowRoot && h.shadowRoot.querySelector('button, .c-spl-button, [role=button]'))
                      || h.querySelector('button, .c-spl-button') || h;
                    btn.click();
                  }
                  return hosts.length;
                }"""
            )
            or 0
        )
    except Exception:
        n = 0
    if n:
        print(f"  Cancelled {n} incomplete Add Experience/Education editor(s).", flush=True)
        try:
            page.wait_for_timeout(600)
        except Exception:
            pass
    return n


def click_spl_button(page, label: str) -> bool:
    """Click the inner shadow-root control of a SmartRecruiters spl-button."""
    try:
        hit = page.evaluate(
            _with_walk("""(label) => {
              const want = String(label || '').trim().toLowerCase();
              const hosts = [];
              walk(document, el => {
                if (el.tagName === 'SPL-BUTTON') hosts.push(el);
              });
              const match = hosts.filter(h => {
                const t = ((h.innerText || h.getAttribute('aria-label') || '') + '').replace(/\\s+/g, ' ').trim().toLowerCase();
                return t === want || t.startsWith(want) || t.includes(want);
              });
              const host = match.length ? match[match.length - 1] : null;
              if (!host) return '';
              let btn = null;
              walk(host, el => {
                if (btn) return;
                const cls = (el.className || '').toString();
                if (cls.includes('c-spl-button') || el.tagName === 'BUTTON') btn = el;
              });
              (btn || host).click();
              return (host.innerText || label).trim().slice(0, 40);
            }"""),
            label,
        )
        if hit:
            page.wait_for_timeout(1200)
            return True
    except Exception:
        pass
    try:
        host = page.locator("spl-button").filter(has_text=re.compile(rf"^{re.escape(label)}$", re.I))
        if host.count():
            host.last.click(force=True, timeout=2500)
            page.wait_for_timeout(1200)
            return True
    except Exception:
        pass
    return False


WALK_DOM_JS = """
const walk = (root, fn) => {
  if (!root) return;
  if (root.nodeType === 1) fn(root);
  const kids = root.querySelectorAll ? root.querySelectorAll('*') : [];
  for (const el of kids) {
    fn(el);
    if (el.shadowRoot) walk(el.shadowRoot, fn);
  }
  if (root.shadowRoot) walk(root.shadowRoot, fn);
};
"""


def _with_walk(js_fn: str) -> str:
    """Playwright evaluate() needs one function. Define walk, then call js_fn."""
    return "((...args) => { " + WALK_DOM_JS + " return (" + js_fn + ")(...args); })"


def fill_spl_autocomplete(page, needle: str, want: str) -> bool:
    """Pick a SmartRecruiters spl-autocomplete option (nested shadow DOM)."""
    if not needle or not want:
        return False
    try:
        result = page.evaluate(
            _with_walk(
            """({needle, want}) => {
              const n = String(needle).toLowerCase();
              const wantL = String(want).toLowerCase();
              let host = null;
              walk(document, el => {
                if (host || !el.tagName) return;
                if (el.tagName === 'SPL-AUTOCOMPLETE') {
                  const t = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')).toLowerCase();
                  if (t.includes(n)) host = el;
                }
              });
              if (!host) return {ok: false, err: 'no host'};
              let trigger = null;
              walk(host, el => {
                if (!trigger && (el.className || '').toString().includes('c-spl-dropdown-trigger')) trigger = el;
              });
              if (trigger) trigger.click();
              const opts = [];
              walk(host, el => {
                if (el.tagName === 'SPL-SELECT-OPTION') {
                  const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                  if (t) opts.push(t);
                }
              });
              const uniq = [...new Set(opts)];
              const match = uniq.find(o => o.toLowerCase() === wantL)
                || uniq.find(o => o.toLowerCase().includes(wantL))
                || uniq.find(o => wantL.includes(o.toLowerCase()));
              if (!match) return {ok: false, err: 'no match', opts: uniq};
              let picked = null;
              walk(host, el => {
                if (picked) return;
                if (el.tagName === 'SPL-SELECT-OPTION' || el.tagName === 'SPL-DROPDOWN-ITEM') {
                  const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                  if (t === match) picked = el;
                }
              });
              if (picked) {
                const inner = (picked.shadowRoot && picked.shadowRoot.querySelector('.c-spl-dropdown-item, [role=option]')) || picked;
                inner.click();
                picked.click();
              }
              let inp = null;
              walk(host, el => { if (!inp && el.tagName === 'INPUT') inp = el; });
              return {ok: !!picked, picked: match, value: inp && inp.value, opts: uniq};
            }"""),
            {"needle": needle, "want": want},
        ) or {}
        if result.get("ok"):
            print(f"  SmartRecruiters select {needle[:40]!r} -> {result.get('picked')}", flush=True)
            page.wait_for_timeout(250)
            return True
    except Exception:
        return False
    return False


def fill_spl_text(page, needle: str, value: str) -> bool:
    """Type into a SmartRecruiters spl-input so Angular validates."""
    if not needle or not value:
        return False
    try:
        box = page.evaluate(
            _with_walk("""(needle) => {
              const n = String(needle).toLowerCase();
              let host = null;
              walk(document, el => {
                if (host || !el.tagName) return;
                if (el.tagName === 'SPL-INPUT') {
                  const t = ((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '') + ' ' + (el.id || '')).toLowerCase();
                  if (t.includes(n)) host = el;
                }
              });
              if (!host) return null;
              let inp = null;
              walk(host, el => { if (!inp && el.tagName === 'INPUT') inp = el; });
              if (!inp) return null;
              inp.scrollIntoView({block: 'center'});
              const r = inp.getBoundingClientRect();
              return {x: r.x, y: r.y, w: r.width, h: r.height, cur: inp.value || ''};
            }"""),
            needle,
        )
        if not box:
            return False
        if (box.get("cur") or "").strip() == value.strip():
            return False
        page.mouse.click(box["x"] + 16, box["y"] + (box["h"] or 18) / 2)
        page.keyboard.press("Control+A")
        page.keyboard.type(value, delay=12)
        page.keyboard.press("Tab")
        print(f"  SmartRecruiters typed {needle[:40]!r}", flush=True)
        return True
    except Exception:
        return False


def click_spl_radio(page, label: str) -> bool:
    try:
        hit = page.evaluate(
            _with_walk("""(label) => {
              const want = String(label).toLowerCase();
              const radios = [];
              walk(document, el => {
                if (el.tagName === 'SPL-RADIO') {
                  const t = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')).toLowerCase();
                  radios.push({el, t, val: String(el.value || el.getAttribute('value') || '')});
                }
              });
              let host = radios.find(r => r.t.trim() === want || r.t.includes(want));
              if (!host && (want === 'yes' || want === '1')) host = radios.find(r => r.val === '1') || radios[0];
              if (!host) return false;
              host.el.scrollIntoView({block: 'center'});
              let inner = null;
              walk(host.el, el => {
                if (inner) return;
                if ((el.className || '').toString().includes('c-spl-radio') || (el.tagName === 'INPUT' && el.type === 'radio')) inner = el;
              });
              (inner || host.el).click();
              host.el.click();
              return true;
            }"""),
            label,
        )
        if hit:
            print(f"  SmartRecruiters radio {label}", flush=True)
            page.wait_for_timeout(200)
            return True
    except Exception:
        return False
    return False


def click_spl_radio_group(page, needle: str, want: str) -> bool:
    """Select Yes/No inside a named SmartRecruiters radio group."""
    try:
        hit = page.evaluate(
            _with_walk("""({needle, want}) => {
              const n = String(needle).toLowerCase();
              const wantL = String(want).toLowerCase();
              let group = null;
              walk(document, el => {
                if (group || el.tagName !== 'SPL-RADIO-GROUP') return;
                const t = (el.innerText || '').toLowerCase();
                if (t.includes(n)) group = el;
              });
              if (!group) return false;
              const radios = [];
              walk(group, el => {
                if (el.tagName === 'SPL-RADIO') radios.push(el);
              });
              let host = null;
              for (const el of radios) {
                const t = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')).toLowerCase();
                const v = String(el.value || el.getAttribute('value') || '');
                if ((wantL === 'yes' || wantL === '1') && (t.includes('yes') || v === '1')) { host = el; break; }
                if ((wantL === 'no' || wantL === '0') && (t.includes('no') || v === '0')) { host = el; break; }
              }
              if (!host) return false;
              host.scrollIntoView({block: 'center'});
              let inner = null;
              walk(host, el => {
                if (inner) return;
                if ((el.className || '').toString().includes('c-spl-radio') || (el.tagName === 'INPUT' && el.type === 'radio')) inner = el;
              });
              (inner || host).click();
              host.click();
              return true;
            }"""),
            {"needle": needle, "want": want},
        )
        if hit:
            print(f"  SmartRecruiters radio {needle[:40]!r} -> {want}", flush=True)
            page.wait_for_timeout(200)
            return True
    except Exception:
        return False
    return False


def check_spl_checkbox(page) -> int:
    """Check Lit/Angular spl-checkbox (privacy consent). Native .click() is ignored."""
    n = 0
    try:
        n = int(
            page.evaluate(
                _with_walk("""() => {
                  let n = 0;
                  walk(document, el => {
                    if (!el.tagName || el.tagName !== 'SPL-CHECKBOX') return;
                    const t = ((el.innerText || '') + ' ' + (el.getAttribute('data-test') || ''));
                    if (!/terms|privacy|agree|consent|certify|declare|consent-box/i.test(t) && el.getAttribute('data-test') !== 'consent-box') return;
                    try { el.checked = true; } catch (e) {}
                    try { el.value = true; el.setAttribute('value', 'true'); } catch (e) {}
                    let inp = null;
                    let wrap = null;
                    walk(el, node => {
                      if (!inp && node.tagName === 'INPUT' && node.type === 'checkbox') inp = node;
                      if (!wrap && (node.className || '').toString().includes('c-spl-checkbox-wrapper')) wrap = node;
                    });
                    const on = (wrap && String(wrap.className).includes('--checked')) || (inp && inp.checked);
                    if (!on) {
                      try { el.click(); } catch (e) {}
                    }
                    if (inp) {
                      inp.checked = true;
                      inp.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
                      inp.dispatchEvent(new Event('change', {bubbles: true, composed: true}));
                    }
                    try { el.dispatchEvent(new CustomEvent('spl-change', {bubbles: true, composed: true, detail: {checked: true}})); } catch (e) {}
                    n++;
                  });
                  return n;
                }""")
            )
            or 0
        )
    except Exception:
        n = 0
    return n


def fill_smartrecruiters_form(page, job: dict | None = None) -> int:
    """Fill SmartRecruiters OneClick / screening questions inside nested shadow roots."""
    url = ""
    try:
        url = page.url or ""
    except Exception:
        url = ""
    if "smartrecruiters.com" not in url.lower():
        return 0
    filled = 0
    try:
        autos = page.evaluate(
            _with_walk("""() => {
              const rows = [];
              walk(document, el => {
                if (el.tagName !== 'SPL-AUTOCOMPLETE') return;
                const q = ((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')).replace(/\\s+/g, ' ').trim();
                const opts = [];
                walk(el, node => {
                  if (node.tagName === 'SPL-SELECT-OPTION') {
                    const t = (node.innerText || '').replace(/\\s+/g, ' ').trim();
                    if (t) opts.push(t);
                  }
                });
                let inp = null;
                walk(el, node => { if (!inp && node.tagName === 'INPUT') inp = node; });
                rows.push({id: el.id, q: q.slice(0, 160), opts: [...new Set(opts)], value: (inp && inp.value) || ''});
              });
              return rows;
            }""")
        ) or []
    except Exception:
        autos = []
    for row in autos:
        if (row.get("value") or "").strip():
            continue
        q = row.get("q") or ""
        want = form_memory.infer_answer(q, row.get("opts") or [])
        if not want:
            continue
        needle = re.sub(r"^select\s+", "", q, flags=re.I)[:48]
        if fill_spl_autocomplete(page, needle, want):
            filled += 1
    try:
        texts = page.evaluate(
            _with_walk("""() => {
              const rows = [];
              walk(document, el => {
                if (el.tagName !== 'SPL-INPUT') return;
                const q = (el.innerText || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
                if (!q || /email|confirm/i.test(q)) return;
                let inp = null;
                walk(el, node => { if (!inp && node.tagName === 'INPUT') inp = node; });
                const r = el.getBoundingClientRect();
                if (r.height < 8) return;
                rows.push({q: q.slice(0, 160), value: (inp && inp.value) || ''});
              });
              return rows;
            }""")
        ) or []
    except Exception:
        texts = []
    for row in texts:
        if (row.get("value") or "").strip():
            continue
        q = row.get("q") or ""
        want = form_memory.infer_answer(q, [])
        if not want:
            continue
        if fill_spl_text(page, q[:40], want):
            filled += 1
    blob = ""
    try:
        groups = page.evaluate(
            _with_walk("""() => {
              const rows = [];
              walk(document, el => {
                if (el.tagName !== 'SPL-RADIO-GROUP') return;
                rows.push({
                  q: (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 160),
                  value: String(el.value || el.getAttribute('value') || ''),
                });
              });
              return rows;
            }""")
        ) or []
    except Exception:
        groups = []
    for row in groups:
        if (row.get("value") or "").strip() not in {"", "null", "undefined"}:
            continue
        q = row.get("q") or ""
        want = form_memory.infer_answer(q, ["Yes", "No"])
        if not want:
            continue
        needle = q[:48]
        if click_spl_radio_group(page, needle, want):
            filled += 1
    try:
        blob = page.evaluate(
            _with_walk("""() => {
              let t = '';
              walk(document, el => {
                if (el.tagName === 'SPL-RADIO-GROUP' || el.tagName === 'SR-QUESTION-FIELD-SELECT') {
                  t += ' ' + (el.innerText || '');
                }
              });
              return t;
            }""")
        ) or ""
    except Exception:
        blob = ""
    if re.search(r"docker|kubernetes|hands-on", blob, re.I) or re.search(r"docker|kubernetes", page_text(page), re.I):
        if click_spl_radio(page, "Yes"):
            filled += 1
    filled += check_spl_checkbox(page)
    if filled:
        print(f"  Filled {filled} SmartRecruiters screening control(s).", flush=True)
    return filled


def unstick_stuck_form(page, job: dict, resume: str) -> str:
    """After the same issue repeats, change tactics instead of clicking Next again."""
    print("  Same issue repeated 3 times. Changing tactics on this form.", flush=True)
    cancel_incomplete_editors(page)
    fill_email_fields(page)
    fill_identity(page)
    try:
        form_memory.fill_visible(page)
        form_memory.fill_india_state_typeahead(page)
    except Exception:
        pass
    try:
        upload_resume(page, resume)
    except Exception:
        pass
    fill_smartrecruiters_form(page, job)
    fill_oracle_form(page, job)
    fill_workday_form(page)
    ats_fill.fill_phenom_acknowledgment(page)
    ats_fill.fill_empty_dropdowns(page, form_memory.infer_answer)
    accept_terms(page)
    # Prefer the ATS Next/Submit, not Copilot Continue on an invalid form.
    if click_spl_button(page, "Submit") or click_spl_button(page, "Submit application"):
        page.wait_for_timeout(1500)
        if is_success(page):
            return "submitted"
        return "clicked"
    if click_spl_button(page, "Next") or click_spl_button(page, "Continue"):
        return "clicked"
    return click_next_or_submit(page)


def notify_needs_input(job: dict, page, fields: list[str] | None = None) -> None:
    """Tell the owner in the agent log that leftover fields need them."""
    company = job.get("company") or ""
    title = job.get("title") or ""
    url = ""
    try:
        url = page.url
    except Exception:
        url = job.get("apply_url") or ""
    fields = fields or required_field_issues(page)
    bullets = "\n".join(f"  - {f}" for f in fields) or "  - leftover required fields on this page"
    banner = (
        f"\n{'!' * 72}\n"
        f"  PAUSED — I filled what I can. Enter leftover fields in Desktop / Take control\n"
        f"  {company}: {title}\n"
        f"  {url}\n"
        f"{bullets}\n"
        f"  I will learn what you type and continue this same application.\n"
        f"{'!' * 72}\n"
    )
    print(banner, flush=True)
    path = ROOT / "data" / "applications" / "NEED_INPUT.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"- **NEED INPUT** {company} — {title}\n  {url}\n" + "".join(f"  - {f}\n" for f in fields)
    prev = path.read_text(encoding="utf-8") if path.exists() else "# Fields that need the owner\n\n"
    if url and url in prev and "NEED INPUT" in prev:
        return
    path.write_text(prev + line + "\n", encoding="utf-8")


def notify_submitted(job: dict, row: dict) -> None:
    """Print a clear submit notice and append it so this chat can report it."""
    company = job.get("company") or row.get("company") or ""
    title = job.get("title") or row.get("title") or ""
    url = row.get("final_url") or job.get("apply_url") or job.get("url") or ""
    ts = row.get("ts") or datetime.now(timezone.utc).isoformat()
    banner = (
        f"\n{'=' * 72}\n"
        f"  SUBMITTED — {company}: {title}\n"
        f"  {url}\n"
        f"{'=' * 72}\n"
    )
    print(banner, flush=True)
    SUBMITTED_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"- **{ts[:19]}Z** SUBMITTED **{company}** — {title}\n  {url}\n"
    prev = SUBMITTED_LOG.read_text(encoding="utf-8") if SUBMITTED_LOG.exists() else "# Submitted applications\n\n"
    if url and url in prev and company in prev:
        return
    SUBMITTED_LOG.write_text(prev + line, encoding="utf-8")


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


def on_application_form(page) -> bool:
    url = (page.url or "").lower()
    # SmartRecruiters listings are not the form until OneClick / publication apply.
    if "smartrecruiters.com" in url and "oneclick-ui" not in url and "/publication/" not in url:
        return False
    if any(x in url for x in ("/apply/email", "/easy-apply", "/apply/section/", "oneclick-ui", "/application", "stepname=")):
        if "indeed.com" not in url:
            return True
    try:
        if page.get_by_text("Apply Manually", exact=True).count():
            loc = page.get_by_text("Apply Manually", exact=True).first
            if loc.is_visible():
                return False
    except Exception:
        pass
    try:
        files = page.locator("input[type=file]")
        for i in range(min(files.count(), 4)):
            el = files.nth(i)
            if el.is_visible():
                return True
        emails = page.locator("input[type=email], input[name='email'], input[name='first_name']")
        for i in range(min(emails.count(), 8)):
            el = emails.nth(i)
            try:
                if not el.is_visible():
                    continue
                box = el.bounding_box() or {}
                if (box.get("width") or 0) > 80:
                    return True
            except Exception:
                continue
    except Exception:
        return False
    return False


def captcha_puzzle_visible(page) -> bool:
    try:
        blob = page_text(page)[:2500]
    except Exception:
        blob = ""
    if re.search(r"drag the shape|select all (the )?squares|click (the )?images", blob, re.I):
        return True
    try:
        for frame in page.frames:
            furl = (frame.url or "").lower()
            if "recaptcha" not in furl and "hcaptcha" not in furl:
                continue
            try:
                t = (frame.inner_text("body") or "")[:800]
            except Exception:
                continue
            if re.search(r"select all|drag the shape|click skip|squares with", t, re.I):
                return True
    except Exception:
        pass
    try:
        big = page.evaluate(
            """() => {
              const frs = document.querySelectorAll(
                'iframe[src*="bframe"], iframe[title*="recaptcha challenge" i], iframe[title*="hCaptcha challenge" i]'
              );
              for (const fr of frs) {
                const r = fr.getBoundingClientRect();
                const st = getComputedStyle(fr);
                if (st.visibility === 'hidden' || st.display === 'none' || Number(st.opacity) === 0) continue;
                if (r.width > 280 && r.height > 200) return true;
              }
              return false;
            }"""
        )
        if big:
            return True
    except Exception:
        pass
    try:
        loc = page.locator("iframe[title*='hCaptcha challenge' i], iframe[title*='hCaptcha' i]")
        n = loc.count()
        for i in range(min(n, 4)):
            el = loc.nth(i)
            if not el.is_visible():
                continue
            box = el.bounding_box() or {}
            if (box.get("width") or 0) > 280 and (box.get("height") or 0) > 140:
                return True
    except Exception:
        pass
    return False


def _xdotool_click(x: float, y: float) -> None:
    import subprocess
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":1")
    try:
        subprocess.run(
            ["xdotool", "search", "--onlyvisible", "--class", "Google-chrome", "windowactivate", "--sync"],
            env=env,
            timeout=2,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["xdotool", "mousemove", "--sync", str(int(x)), str(int(y)), "click", "1"],
            env=env,
            timeout=3,
            check=False,
        )
    except Exception:
        pass


def click_recaptcha_checkbox(page) -> bool:
    """Tick 'I'm not a robot' with a real mouse click. Image puzzles stay for the owner."""
    global _RECAPTCHA_CLICKS
    if captcha_puzzle_visible(page):
        return False
    if _RECAPTCHA_CLICKS >= 2:
        return True
    clicked = False
    try:
        info = page.evaluate(
            """() => {
              const frames = [...document.querySelectorAll(
                'iframe[src*="recaptcha"][src*="anchor"], iframe[title*="reCAPTCHA" i], iframe[title="reCAPTCHA"]'
              )];
              const vis = [];
              for (const el of frames) {
                const r = el.getBoundingClientRect();
                const st = getComputedStyle(el);
                if (st.visibility === 'hidden' || st.display === 'none' || st.opacity === '0') continue;
                if (r.width < 120 || r.height < 40 || r.width > 420) continue;
                vis.push({x: r.x, y: r.y, w: r.width, h: r.height});
              }
              return {
                boxes: vis,
                sx: window.screenX || 0,
                sy: window.screenY || 0,
                oh: window.outerHeight || 0,
                ih: window.innerHeight || 0,
              };
            }"""
        )
    except Exception:
        info = None
    boxes = (info or {}).get("boxes") or []
    if boxes:
        collapse_copilot_panel(page)
        b = boxes[0]
        chrome_top = max(0, int((info.get("oh") or 0) - (info.get("ih") or 0)))
        # Checkbox sits on the left of the 304x78 widget, not on the label text.
        screen_x = (info.get("sx") or 0) + b["x"] + min(28, max(18, (b["w"] or 80) * 0.12))
        screen_y = (info.get("sy") or 0) + chrome_top + b["y"] + (b["h"] or 74) / 2
        _xdotool_click(screen_x, screen_y)
        print("  Clicked reCAPTCHA I'm not a robot.", flush=True)
        _RECAPTCHA_CLICKS += 1
        try:
            page.wait_for_timeout(1600)
        except Exception:
            pass
        clicked = True
    if clicked:
        return True
    for frame in page.frames:
        try:
            furl = (frame.url or "").lower()
            if "recaptcha" not in furl or "anchor" not in furl:
                continue
            box = frame.locator("#recaptcha-anchor").first
            if not box.count():
                continue
            if (box.get_attribute("aria-checked") or "") == "true":
                continue
            box.click(timeout=2000, force=True)
            print("  Clicked reCAPTCHA I'm not a robot.", flush=True)
            page.wait_for_timeout(1500)
            return True
        except Exception:
            continue
    return False


def accept_terms(page) -> int:
    """Check terms/privacy boxes, including hidden Oracle/Workday checkboxes."""
    n = check_spl_checkbox(page)
    try:
        n = page.evaluate(
            """() => {
              const re = /terms|privacy|agree|consent|certify|disclaimer|i have read|you declare|acknowledg/i;
              let n = 0;
              const fire = (el) => {
                try { el.click(); } catch (e) {}
                if (el.tagName === 'INPUT' && el.type === 'checkbox') {
                  el.checked = true;
                  el.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
                  el.dispatchEvent(new Event('change', {bubbles: true, composed: true}));
                }
                n++;
              };
              const walk = (root) => {
                if (!root || !root.querySelectorAll) return;
                // spl-checkbox is handled by check_spl_checkbox() (Lit host.click()).
                for (const el of root.querySelectorAll('input[type=checkbox]')) {
                  if (el.closest && el.closest('spl-checkbox')) continue;
                  const wrap = el.closest('label') || el.parentElement || el;
                  const t = ((wrap.innerText || '') + ' ' + (el.getAttribute('aria-label') || '') + ' ' + (el.id || '') + ' ' + (el.name || ''));
                  if (!re.test(t)) continue;
                  if (el.checked) continue;
                  fire(el);
                }
                for (const el of root.querySelectorAll('*')) {
                  if (el.shadowRoot) walk(el.shadowRoot);
                }
              };
              walk(document);
              const honey = document.querySelector('input[name="honey-pot"], #honey-pot-1, input[aria-label="honeypot"]');
              if (honey && honey.value) { honey.value = ''; honey.dispatchEvent(new Event('input', {bubbles: true})); }
              return n;
            }"""
        ) or 0
    except Exception:
        n = 0
    def _legal_on() -> bool:
        try:
            return bool(
                page.evaluate(
                    "() => { const el = document.querySelector('#legal-disclaimer-checkbox'); return !!(el && el.checked); }"
                )
            )
        except Exception:
            return False
    if not _legal_on():
        try:
            box = page.locator(".apply-flow-input-checkbox__button, [class*='checkbox__button']").first
            if box.count() and box.is_visible():
                box.click(timeout=800, force=True)
                n += 1
        except Exception:
            pass
    if not _legal_on():
        for name in (
            "You declare that you have read and agree",
            "I agree with the terms and conditions",
            "I agree to the terms",
            "I have read and agree",
        ):
            if _legal_on():
                break
            try:
                loc = page.get_by_text(name, exact=False).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=800, force=True)
                    n += 1
                    page.wait_for_timeout(150)
            except Exception:
                continue
    if n:
        print(f"  Accepted {n} terms/privacy control(s).", flush=True)
    return n


def _foreign_or_parked_tab(url: str, job: dict | None = None, current: str = "") -> bool:
    """True if this tab is Gmail, a parked CAPTCHA, or another job's ATS."""
    u = (url or "").lower()
    cur = (current or "").lower()
    if any(x in u for x in ("mail.google.com", "accounts.google.com", "chrome://", "chrome-extension://")):
        return True
    if "linkedin.com/checkpoint" in u:
        return True
    if "login.icims.com" in u and "icims.com" not in cur:
        return True
    for parked in PARKED_CAPTCHA_URLS:
        p = (parked or "").lower()
        if not p:
            continue
        if p.split("?")[0] == u.split("?")[0] or (p in u) or (u and u in p):
            return True
    blob = ""
    if job:
        blob = (
            str(job.get("apply_url") or "")
            + " "
            + str(job.get("url") or "")
        ).lower()
    for host in (
        "oraclecloud.com",
        "myworkdayjobs",
        "avature.net",
        "smartrecruiters.com",
        "jobs.zf.com",
        "careers.amd.com",
        "schwabjobs.com",
        "jpmc.fa",
    ):
        if host in u and blob and host not in blob:
            return True
    return False


def recover_wrong_board(page, job: dict | None = None) -> bool:
    """Leave Indeed/LinkedIn intercepts on company-portal applies. Stay on aggregator Easy Apply."""
    if job and apply_now.is_aggregator_board(job):
        return False
    url = (page.url or "").lower()
    if job and _aggregator_host(job.get("apply_url") or job.get("url") or ""):
        return False
    if "indeed.com" in url or "linkedin.com/jobs" in url:
        print(f"  Left aggregator intercept {url[:80]}", flush=True)
        try:
            page.go_back(wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1200)
            return True
        except Exception:
            return False
    return False


def adopt_newest_page(page, before_ids: set[int] | None = None, job: dict | None = None):
    """Follow Apply that opened a new tab. Never jump to Gmail or leftover tabs."""
    try:
        ctx = page.context
    except Exception:
        return page
    opened = []
    for p in ctx.pages:
        try:
            if p.is_closed():
                continue
            if before_ids is not None and id(p) in before_ids:
                continue
            url = p.url or ""
            if "accounts.google.com" in url or url.startswith("chrome-extension://"):
                continue
            if "mail.google.com" in url:
                continue
            # Parked Schwab Auth0 is not the new Apply tab for Workday/DHL.
            if "login.icims.com" in url.lower() and "icims.com" not in (page.url or "").lower():
                continue
            if _foreign_or_parked_tab(url, job, page.url or ""):
                continue
            opened.append(p)
        except Exception:
            continue
    if opened:
        for p in reversed(opened):
            try:
                u = (p.url or "").lower()
            except Exception:
                continue
            if any(
                x in u
                for x in (
                    "myworkdayjobs",
                    "oraclecloud.com",
                    "avature.net",
                    "smartrecruiters.com",
                    "/apply",
                )
            ):
                return p
        return opened[-1]
    return page


def follow_apply_tab(page, job: dict | None = None):
    """Fill the ATS apply tab, not the careers listing that opened it.

    Never jump onto a parked CAPTCHA or another leftover's Oracle/Workday tab.
    """
    try:
        cur = (page.url or "").lower()
    except Exception:
        return page
    if any(
        x in cur
        for x in (
            "myworkdayjobs",
            "login.icims.com",
            "oraclecloud.com",
            "avature.net",
            "smartrecruiters.com",
            "/apply",
            "applymanually",
            "naukri.com/job-listings",
            "naukri.com/jobdescription",
        )
    ) and not _foreign_or_parked_tab(cur, job, cur):
        return page
    ctx = getattr(page, "context", None)
    if ctx is None:
        return page
    for p in reversed(list(ctx.pages)):
        try:
            if p.is_closed():
                continue
            u = (p.url or "").lower()
        except Exception:
            continue
        if _foreign_or_parked_tab(u, job, cur):
            continue
        if "login.icims.com" in u:
            if "icims.com" in cur or (job and "icims.com" in (
                (job.get("apply_url") or "") + (job.get("url") or "")
            ).lower()):
                return p
            continue
        if any(
            x in u
            for x in (
                "myworkdayjobs",
                "oraclecloud.com",
                "avature.net",
                "smartrecruiters.com",
            )
        ):
            return p
    return page


def fill_and_advance(page, job: dict, resume: str) -> str:
    """Fill Copilot + memory and click Next/Submit. Returns submitted|clicked|none."""
    _dismiss_native_file_dialog()
    dismiss_overlays(page)
    if captcha_puzzle_visible(page):
        return "captcha"
    click_recaptcha_checkbox(page)
    try:
        foundit_blob = (
            (page.url or "")
            + " "
            + str((job or {}).get("apply_url") or "")
            + " "
            + str((job or {}).get("url") or "")
        ).lower()
        if "foundit.in" in foundit_blob:
            fill_foundit_native_login(page)
    except Exception:
        pass
    click_google_account_chooser(page)
    if is_success(page) or simplify_copilot.submitted(page):
        return "submitted"
    recover_wrong_board(page, job)
    cancel_incomplete_editors(page)
    copilot_start = simplify_copilot.start_application(page)
    if copilot_start:
        page.wait_for_timeout(600)
    fill_identity(page)
    auth = try_portal_auth(page)
    if auth == "failed":
        return "auth_failed"
    fill_icims_login(page)
    try:
        ju = ((job or {}).get("apply_url") or (job or {}).get("url") or page.url or "").lower()
    except Exception:
        ju = (page.url or "").lower()
    if "icims.com" in ju and icims_auth0_blocked(page):
        return "stuck"
    click_dhl_apply_method(page)
    fill_leftover_dropdowns(page)
    apply_now.set_india_phone(page)
    fill_smartrecruiters_form(page, job)
    fill_oracle_form(page, job)
    fill_workday_form(page)
    ats_fill.fill_phenom_acknowledgment(page)
    ats_fill.fill_empty_dropdowns(page, form_memory.infer_answer)
    accept_terms(page)
    try:
        upload_resume(page, resume)
    except Exception:
        pass
    copilot_step = simplify_copilot.follow(page)
    if copilot_step == "submitted" or is_success(page):
        return "submitted"
    if copilot_step == "stuck":
        fill_workday_form(page)
        form_memory.fill_visible(page)
        step = click_next_or_submit(page)
        if step == "submitted" or is_success(page) or simplify_copilot.submitted(page):
            return "submitted"
        return step or "clicked"
    form_memory.fill_visible(page)
    form_memory.fill_india_state_typeahead(page)
    fill_smartrecruiters_form(page, job)
    fill_oracle_form(page, job)
    fill_workday_form(page)
    ats_fill.fill_phenom_acknowledgment(page)
    ats_fill.fill_empty_dropdowns(page, form_memory.infer_answer)
    accept_terms(page)
    if captcha_puzzle_visible(page):
        return "captcha"
    if not on_application_form(page):
        before = {id(p) for p in page.context.pages}
        click_apply_gate(page)
        page.wait_for_timeout(800)
        page = adopt_newest_page(page, before, job)
    step = click_next_or_submit(page)
    if step == "submitted" or is_success(page) or simplify_copilot.submitted(page):
        return "submitted"
    return step


def wait_for_human(page, job: dict, seconds: int, resume: str | None = None) -> dict:
    """Keep filling and submitting. Leave Chrome visible if a human CAPTCHA appears."""
    resume = resume or job.get("resume_path") or RESUME
    print(
        f"  Staying on this form until Submit (up to {seconds}s). "
        f"If a CAPTCHA appears, solve it in this agent's Desktop / Take control.",
        flush=True,
    )
    deadline = time.time() + seconds
    learned = 0
    notified_captcha = False
    notified_input = False
    stuck_required = 0
    last_fp = ""
    same_fp = 0
    unsticks = 0
    step = ""
    linkedin_checkpoint_hits = 0
    linkedin_signup_hits = 0
    try:
        hold_url = _stable_apply_url(page.url or "")
    except Exception:
        hold_url = ""
    url_hold_from = time.time()
    while time.time() < deadline:
        try:
            page = follow_apply_tab(page, job)
        except Exception:
            pass
        try:
            job_url = (job.get("apply_url") or job.get("url") or "").lower()
        except Exception:
            job_url = ""
        if OWNER_PRESENT and notified_input:
            # Hands off: learn only. Do not click or type while the owner fills.
            try:
                if is_success(page):
                    print("  Submitted. Learning this form for later runs.", flush=True)
                    return {
                        "ok": True,
                        "status": "SUBMITTED",
                        "note": "submitted after owner filled leftover fields",
                        "learned": learned,
                    }
            except Exception:
                pass
            try:
                changed = form_memory.remember(page, job) or []
                learned += len(changed)
            except Exception:
                pass
            page.wait_for_timeout(4000)
            continue
        try:
            page_u = (page.url or "").lower()
        except Exception:
            page_u = ""
        if icims_auth0_blocked(page) and (
            "icims.com" in job_url or "icims.com" in page_u
        ):
            if OWNER_PRESENT:
                if not notified_input:
                    notify_needs_input(
                        job,
                        page,
                        ["iCIMS Auth0 login — complete password / wait out the rate limit"],
                    )
                    notified_input = True
                print("  Paused on iCIMS Auth0. Complete login; I will learn and continue.", flush=True)
                page.wait_for_timeout(2000)
                continue
            print("  iCIMS Auth0 rate-limited. Next leftover.", flush=True)
            return {
                "ok": False,
                "status": "STUCK",
                "note": "iCIMS Auth0 rate-limited — retry later",
                "learned": learned,
            }
        try:
            changed = form_memory.remember(page, job) or []
            learned += len(changed)
        except Exception:
            pass
        click_google_account_chooser(page)
        if captcha_puzzle_visible(page):
            notify_captcha(job, page)
            if OWNER_PRESENT:
                if not notified_captcha:
                    print(
                        "  CAPTCHA visible. Solve it in Desktop / Take control. "
                        "I will wait on this form.",
                        flush=True,
                    )
                    notified_captcha = True
                page.wait_for_timeout(2500)
                continue
            print("  CAPTCHA parked. Opening the next leftover now.", flush=True)
            return {
                "ok": False,
                "status": "CAPTCHA",
                "note": "parked for owner to solve later",
                "learned": learned,
            }
        click_recaptcha_checkbox(page)
        if linkedin_account_restricted(page):
            persist_skip_all_linkedin()
            print("  LinkedIn account is restricted. Skipping remaining LinkedIn leftovers.", flush=True)
            return {
                "ok": False,
                "status": "CLOSED",
                "note": LINKEDIN_RESTRICTED_NOTE,
                "learned": learned,
            }
        if captcha_puzzle_visible(page):
            notify_captcha(job, page)
            if OWNER_PRESENT:
                if not notified_captcha:
                    print(
                        "  CAPTCHA visible. Solve it in Desktop / Take control. "
                        "I will wait on this form.",
                        flush=True,
                    )
                    notified_captcha = True
                page.wait_for_timeout(2500)
                continue
            print("  CAPTCHA parked. Opening the next leftover now.", flush=True)
            return {
                "ok": False,
                "status": "CAPTCHA",
                "note": "parked for owner to solve later",
                "learned": learned,
            }
        try:
            wall_url = (page.url or "").lower()
        except Exception:
            wall_url = ""
        if "linkedin.com/checkpoint" in wall_url:
            linkedin_checkpoint_hits += 1
            if linkedin_checkpoint_hits >= 12:
                notify_captcha(job, page)
                print("  LinkedIn security check parked. Opening the next leftover now.", flush=True)
                return {
                    "ok": False,
                    "status": "CAPTCHA",
                    "note": "parked LinkedIn checkpoint for owner",
                    "learned": learned,
                }
        elif any(x in wall_url for x in ("linkedin.com/signup", "cold-join")):
            linkedin_signup_hits += 1
            if linkedin_signup_hits >= 16:
                print("  LinkedIn Google sign-in did not finish. Next leftover.", flush=True)
                return {
                    "ok": False,
                    "status": "STUCK",
                    "note": "LinkedIn guest wall — Google chooser not completed",
                    "learned": learned,
                }
        try:
            step = fill_and_advance(page, job, resume)
            if step == "submitted" or is_success(page):
                if already_applied_visible(page):
                    print("  Already applied on this board. Next leftover.", flush=True)
                    return {
                        "ok": True,
                        "status": "SUBMITTED",
                        "note": "already applied",
                        "learned": learned,
                    }
                print("  Submitted. Learning this form for later runs.", flush=True)
                return {
                    "ok": True,
                    "status": "SUBMITTED",
                    "note": "submitted in headed Chrome (autofill + Copilot)",
                    "learned": learned,
                }
            if step == "auth_failed":
                print("  Portal login failed. Will close this tab and open the next leftover.", flush=True)
                return {
                    "ok": False,
                    "status": "AUTH_FAILED",
                    "note": "all portal passwords rejected or account locked",
                    "learned": learned,
                }
            if step == "captcha":
                notify_captcha(job, page)
                if OWNER_PRESENT:
                    if not notified_captcha:
                        print(
                            "  CAPTCHA visible. Solve it in Desktop / Take control. "
                            "I will wait on this form.",
                            flush=True,
                        )
                        notified_captcha = True
                    page.wait_for_timeout(2500)
                    continue
                print("  CAPTCHA parked. Opening the next leftover now.", flush=True)
                return {
                    "ok": False,
                    "status": "CAPTCHA",
                    "note": "parked for owner to solve later",
                    "learned": learned,
                }
            if step == "stuck" and icims_auth0_blocked(page) and (
                "icims.com" in job_url or "icims.com" in (page.url or "").lower()
            ):
                if OWNER_PRESENT:
                    if not notified_input:
                        notify_needs_input(
                            job,
                            page,
                            ["iCIMS Auth0 login — complete password / wait out the rate limit"],
                        )
                        notified_input = True
                    print("  Paused on iCIMS Auth0. Complete login; I will learn and continue.", flush=True)
                else:
                    print("  iCIMS Auth0 rate-limited. Next leftover.", flush=True)
                    return {
                        "ok": False,
                        "status": "STUCK",
                        "note": "iCIMS Auth0 rate-limited — retry later",
                        "learned": learned,
                    }
        except Exception:
            pass
        fp = form_fingerprint(page)
        if fp == last_fp:
            same_fp += 1
        else:
            same_fp = 0
            last_fp = fp
        if same_fp >= 3:
            step = unstick_stuck_form(page, job, resume)
            unsticks += 1
            same_fp = 0
            last_fp = form_fingerprint(page)
            if step == "submitted" or is_success(page):
                print("  Submitted after unstick. Learning this form for later runs.", flush=True)
                return {
                    "ok": True,
                    "status": "SUBMITTED",
                    "note": "submitted after unstick",
                    "learned": learned,
                }
            if unsticks >= 2:
                try:
                    loop_url = (page.url or "").lower()
                except Exception:
                    loop_url = ""
                if "linkedin.com/checkpoint" in loop_url:
                    notify_captcha(job, page)
                    print("  LinkedIn security check parked. Opening the next leftover now.", flush=True)
                    return {
                        "ok": False,
                        "status": "CAPTCHA",
                        "note": "parked LinkedIn checkpoint for owner",
                        "learned": learned,
                    }
                if OWNER_PRESENT:
                    req = required_field_issues(page) or [
                        "form is not advancing — fill remaining fields"
                    ]
                    if not notified_input:
                        notify_needs_input(job, page, req)
                        notified_input = True
                    print(
                        "  Paused clicks. Fill remaining fields; I will learn them and continue.",
                        flush=True,
                    )
                    unsticks = 0
                    page.wait_for_timeout(2500)
                    continue
                print("  Form is looping. Moving to the next leftover now.", flush=True)
                return {
                    "ok": False,
                    "status": "STUCK",
                    "note": "copilot/form loop — skipped to next job",
                    "learned": learned,
                }
        req = required_field_issues(page)
        if req:
            stuck_required += 1
            if stuck_required >= 2 and not notified_input:
                notify_needs_input(job, page, req)
                notified_input = True
                if not OWNER_PRESENT:
                    print("  Owner is away. Leftover fields remain — next job.", flush=True)
                    return {
                        "ok": False,
                        "status": "STUCK",
                        "note": "leftover fields; owner sleeping — next job",
                        "learned": learned,
                    }
                print(
                    "  Paused. Fill the leftover fields; I will learn them and continue.",
                    flush=True,
                )
        else:
            stuck_required = 0
            if notified_input and OWNER_PRESENT:
                notified_input = False
        try:
            now_url = _stable_apply_url(page.url or "")
        except Exception:
            now_url = hold_url
        if now_url != hold_url:
            hold_url = now_url
            url_hold_from = time.time()
        elif _ats_loop_host(now_url) and time.time() - url_hold_from > 30 and not OWNER_PRESENT:
            print("  ATS page did not advance. Next leftover.", flush=True)
            return {
                "ok": False,
                "status": "STUCK",
                "note": "ATS URL unchanged — next job",
                "learned": learned,
            }
        page.wait_for_timeout(1200)
    print(f"  Still no confirmation after {seconds}s. Learned {learned} field(s).", flush=True)
    if OWNER_PRESENT:
        leftover = required_field_issues(page)
        if leftover or notified_input:
            if not notified_input:
                notify_needs_input(job, page, leftover)
            return {
                "ok": False,
                "status": "NEED_INPUT",
                "note": f"paused for owner after {seconds}s; learned {learned} fields",
                "learned": learned,
            }
    return {
        "ok": False,
        "status": "WAITING_EXPIRED",
        "note": f"waited {seconds}s; learned {learned} fields",
        "learned": learned,
    }


def apply_one(page, job: dict, wait_seconds: int = 0, navigate: bool = True, allow_aggregators: bool = True) -> dict:
    global ICIMS_LOGIN_CLICKED, ICIMS_CONTINUE_CLICKS, ICIMS_PASSWORD_SUBMITS, FOUNDIT_AKAMAI_BLOCKED
    url = job.get("apply_url") or apply_now.apply_url(job) or job.get("url") or ""
    kind = classify_url(url, job, allow_aggregators=allow_aggregators)
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
    if google_password_create_parked(page) and any(
        x in (url or "").lower() for x in ("linkedin.com", "cutshort.io", "cutshort.com")
    ):
        row["status"] = "STUCK"
        row["note"] = "Google change-password parked — not creating a password"
        print("  Google change-password parked. Not creating a password. Next leftover.", flush=True)
        return row
    if "icims.com" not in (url or "").lower():
        ICIMS_LOGIN_CLICKED = False
        ICIMS_CONTINUE_CLICKS = 0
        ICIMS_PASSWORD_SUBMITS = 0
    else:
        ICIMS_PASSWORD_SUBMITS = 0

    resume = job.get("resume_path") or RESUME
    learned = 0
    try:
        if navigate:
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(800)
        else:
            page.wait_for_timeout(400)
        title0 = ""
        try:
            title0 = page.title() or ""
        except Exception:
            title0 = ""
        blob0 = page_text(page)[:2000]
        blocked = bool(re.search(
            r"access denied|don't have permission to access|errors\.edgesuite\.net",
            title0 + " " + blob0,
            re.I,
        ))
        if blocked and "foundit.in" in (url or page.url or "").lower():
            print("  Foundit Akamai challenge. Warming session from homepage...", flush=True)
            try:
                page.goto("https://www.foundit.in/", wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(10000)
                page.goto(url, wait_until="domcontentloaded", timeout=35000)
                page.wait_for_timeout(2500)
                title0 = page.title() or ""
                blob0 = page_text(page)[:2000]
                blocked = bool(re.search(
                    r"access denied|don't have permission to access|errors\.edgesuite\.net",
                    title0 + " " + blob0,
                    re.I,
                ))
            except Exception:
                blocked = True
            if not blocked:
                print("  Foundit challenge cleared.", flush=True)
        if blocked:
            row["status"] = "STUCK"
            row["final_url"] = page.url
            row["note"] = "board blocked this environment (access denied)"
            if "foundit.in" in (url or page.url or "").lower():
                FOUNDIT_AKAMAI_BLOCKED = True
                print("  Foundit still blocked after warmup. Skipping other Foundit leftovers this round.", flush=True)
            if not _aggregator_host(url or page.url or ""):
                apply_now.persist_skipped(row, row["note"])
            print("  Board blocked this environment. Next leftover.", flush=True)
            return row
        dismiss_overlays(page)
        try:
            if "foundit.in" in (url or "").lower() or "foundit.in" in (page.url or "").lower():
                fill_foundit_native_login(page)
        except Exception:
            pass
        copilot_start = simplify_copilot.start_application(page)
        if copilot_start:
            page.wait_for_timeout(800)
        closed = False
        try:
            closed = bool(
                page.get_by_text(re.compile(r"job has expired|no longer accepting applications", re.I)).count()
            )
        except Exception:
            closed = False
        blob = page_text(page)[:8000]
        if closed or re.search(
            r"page you are looking for doesn.?t exist|job (is )?no longer available|"
            r"this job has been closed|sorry, this job has expired|this job has expired|"
            r"no longer accepting applications|\b404\b",
            blob,
            re.I,
        ) or re.search(r"404|not found", page.title() or "", re.I):
            row["status"] = "CLOSED"
            row["final_url"] = page.url
            row["note"] = "job posting gone"
            apply_now.persist_applied(row, "closed posting — cannot submit")
            return row
        if linkedin_account_restricted(page):
            persist_skip_all_linkedin()
            row["status"] = "CLOSED"
            row["final_url"] = page.url
            row["note"] = LINKEDIN_RESTRICTED_NOTE
            print("  LinkedIn account is restricted. Skipping remaining LinkedIn leftovers.", flush=True)
            return row
        last_url = page.url
        same_url_hits = 0
        for _ in range(6):
            recover_wrong_board(page, job)
            dismiss_overlays(page)
            if is_success(page):
                row["ok"] = True
                row["status"] = "SUBMITTED"
                row["note"] = "already applied"
                row["final_url"] = page.url
                return row
            if on_application_form(page):
                # Still click Workday Apply Manually if that modal is up.
                try:
                    if page.get_by_text("Apply Manually", exact=True).first.is_visible():
                        click_apply_gate(page)
                        page.wait_for_timeout(1200)
                        continue
                except Exception:
                    pass
                break
            before = {id(p) for p in page.context.pages}
            hit = click_apply_gate(page)
            page.wait_for_timeout(1000)
            page = adopt_newest_page(page, before, job)
            if page.url == last_url:
                same_url_hits += 1
            else:
                same_url_hits = 0
                last_url = page.url
            if not hit or same_url_hits >= 3:
                break
        recover_wrong_board(page, job)
        if is_success(page):
            row["ok"] = True
            row["status"] = "SUBMITTED"
            row["note"] = "already applied"
            row["final_url"] = page.url
            return row
        if "naukri.com" in (url or "").lower():
            try:
                foot = page.get_by_role(
                    "button", name=re.compile(r"quick apply|company site|apply on|iimjobs", re.I)
                ).first
                nlabel = ((foot.inner_text() or "") if foot.count() else "").lower()
            except Exception:
                nlabel = ""
            if re.search(r"applied", nlabel):
                print("  Naukri footer shows already applied.", flush=True)
                row["ok"] = True
                row["status"] = "SUBMITTED"
                row["note"] = "already applied"
                row["final_url"] = page.url
                return row
            if naukri_external_apply_label(nlabel):
                print("  Naukri company-site / external apply. Next leftover.", flush=True)
                row["status"] = "STUCK"
                row["note"] = "Naukri company-site apply"
                row["final_url"] = page.url
                apply_now.persist_skipped(row, row["note"])
                return row

        fill_identity(page)
        auth = try_portal_auth(page)
        if auth == "failed":
            row["status"] = "AUTH_FAILED"
            row["note"] = "all portal passwords rejected or account locked"
            row["final_url"] = page.url
            pu = ""
            try:
                pu = (page.url or "").lower()
            except Exception:
                pu = ""
            parked_other = "login.icims.com" in pu and "icims.com" not in (url or "").lower()
            if parked_other:
                print("  Parked iCIMS login is not this job. Next leftover.", flush=True)
                row["status"] = "STUCK"
                row["note"] = "did not consume parked iCIMS Auth0 as this job"
            elif not _aggregator_host(url or page.url or ""):
                apply_now.persist_skipped(row, row["note"])
                print("  Skipping this job. Closing the tab and opening the next leftover.", flush=True)
            else:
                print("  Job-board login wall. Not marking skipped; next leftover.", flush=True)
            return row
        if "icims.com" in (url or "").lower() and icims_auth0_blocked(page) and not OWNER_PRESENT:
            print("  iCIMS Auth0 rate-limited. Next leftover.", flush=True)
            row["status"] = "STUCK"
            row["note"] = "iCIMS Auth0 rate-limited — retry later"
            row["final_url"] = page.url
            return row
        try:
            u = (page.url or "").lower()
        except Exception:
            u = ""
        if "passport.amazon.jobs" in u:
            notify_amazon_signin(job, page)
            row["status"] = "OWNER_SIGNIN"
            row["note"] = "Amazon sign-in parked for the owner; tab stays open"
            row["final_url"] = page.url
            return row
        apply_now.set_india_phone(page)
        try:
            upload_resume(page, resume)
        except Exception:
            pass
        simplify_copilot.autofill(page)
        form_memory.fill_visible(page)
        learned += len(form_memory.remember(page, job) or [])

        stuck_none = 0
        last_apply_url = ""
        same_apply = 0
        step = ""
        apply_hold = _stable_apply_url(page.url or "")
        apply_hold_from = time.time()
        for _ in range(6):
            try:
                page = follow_apply_tab(page, job)
            except Exception:
                pass
            dismiss_overlays(page)
            recover_wrong_board(page, job)
            if is_success(page) or simplify_copilot.submitted(page):
                row["ok"] = True
                row["status"] = "SUBMITTED"
                row["final_url"] = page.url
                row["note"] = row.get("note") or "Simplify Copilot"
                return row
            try:
                now_stable = _stable_apply_url(page.url or "")
            except Exception:
                now_stable = apply_hold
            if now_stable != apply_hold:
                apply_hold = now_stable
                apply_hold_from = time.time()
            elif (
                _ats_loop_host(now_stable)
                and time.time() - apply_hold_from > 30
                and not OWNER_PRESENT
            ):
                print("  ATS page did not advance. Next leftover.", flush=True)
                row["status"] = "STUCK"
                row["note"] = "ATS URL unchanged — next job"
                row["final_url"] = page.url
                return row
            step = fill_and_advance(page, job, resume)
            try:
                after_stable = _stable_apply_url(page.url or "")
            except Exception:
                after_stable = apply_hold
            if after_stable != apply_hold:
                apply_hold = after_stable
                apply_hold_from = time.time()
            elif (
                _ats_loop_host(after_stable)
                and time.time() - apply_hold_from > 30
                and not OWNER_PRESENT
            ):
                print("  ATS page did not advance. Next leftover.", flush=True)
                row["status"] = "STUCK"
                row["note"] = "ATS URL unchanged — next job"
                row["final_url"] = page.url
                return row
            if step == "submitted" or is_success(page):
                row["ok"] = True
                row["status"] = "SUBMITTED"
                row["final_url"] = page.url
                row["note"] = "Simplify Copilot"
                return row
            if step == "auth_failed":
                row["status"] = "AUTH_FAILED"
                row["note"] = "all portal passwords rejected or account locked"
                row["final_url"] = page.url
                if not _aggregator_host(url or page.url or ""):
                    apply_now.persist_skipped(row, row["note"])
                    print("  Skipping this job. Closing the tab and opening the next leftover.", flush=True)
                else:
                    print("  Job-board login wall. Not marking skipped; next leftover.", flush=True)
                return row
            if step == "captcha":
                notify_captcha(job, page)
                row["status"] = "CAPTCHA"
                row["note"] = "parked for owner to solve later"
                row["final_url"] = page.url
                print("  CAPTCHA parked. Opening the next leftover now.", flush=True)
                return row
            if step == "stuck":
                if (
                    "icims.com" in (url or "").lower()
                    and icims_auth0_blocked(page)
                    and not OWNER_PRESENT
                ):
                    print("  iCIMS Auth0 rate-limited. Next leftover.", flush=True)
                    row["status"] = "STUCK"
                    row["note"] = "iCIMS Auth0 rate-limited — retry later"
                    row["final_url"] = page.url
                    return row
                break
            try:
                now_url = page.url or ""
            except Exception:
                now_url = ""
            if now_url == last_apply_url:
                same_apply += 1
            else:
                same_apply = 0
                last_apply_url = now_url
            if same_apply >= 2:
                break
            if step == "none":
                stuck_none += 1
                if stuck_none >= 3:
                    break
            else:
                stuck_none = 0
            page.wait_for_timeout(400)

        if captcha_puzzle_visible(page):
            notify_captcha(job, page)
            if OWNER_PRESENT:
                print(
                    "  CAPTCHA visible. Solve it in Desktop / Take control — "
                    "I will wait on this form and submit after it clears.",
                    flush=True,
                )
                human = wait_for_human(page, job, wait_seconds or 1800, resume)
                row["final_url"] = page.url
                row["learned"] = learned + int(human.get("learned") or 0)
                if human.get("ok"):
                    row["ok"] = True
                    row["status"] = "SUBMITTED"
                    row["note"] = human.get("note") or "submitted after owner solved CAPTCHA"
                    return row
                row["ok"] = False
                row["status"] = human.get("status") or "CAPTCHA"
                row["note"] = human.get("note") or "CAPTCHA still visible after wait"
                return row
            row["status"] = "CAPTCHA"
            row["note"] = "parked for owner to solve later"
            row["final_url"] = page.url
            print("  CAPTCHA parked. Opening the next leftover now.", flush=True)
            return row

        stay = 15
        try:
            page = follow_apply_tab(page, job)
            u = (page.url or "").lower()
        except Exception:
            u = ""
        job_u = (url or "").lower()
        if any(x in u or x in job_u for x in ("applymanually", "/apply/", "icims.com", "avature.net", "myworkdayjobs", "oraclecloud", "smartrecruiters", "linkedin.com", "naukri.com", "indeed.com", "foundit.in", "instahyre", "cutshort")):
            stay = wait_seconds if wait_seconds else 90
        if "naukri.com" in u or "naukri.com" in job_u:
            stay = min(stay, 40) if not OWNER_PRESENT else stay
        if "instahyre.com/job-" in u:
            stay = min(stay, 25)
        if linkedin_account_restricted(page) or linkedin_blocked_now():
            stay = 0
        if "foundit.in" in u and not OWNER_PRESENT and ("/login" in u or "rio/login" in u):
            stay = min(stay, 12)
        if (
            icims_auth0_blocked(page)
            and ("icims.com" in u or "icims.com" in (url or "").lower())
            and not OWNER_PRESENT
        ):
            stay = 0
        if step == "stuck" and stay <= 15 and not OWNER_PRESENT and "naukri.com" not in job_u:
            stay = 0
        if OWNER_PRESENT and not stay:
            stay = wait_seconds if wait_seconds else 90
        if stay:
            human = wait_for_human(page, job, stay, resume)
            row["ok"] = human["ok"]
            row["status"] = human["status"]
            row["note"] = human["note"]
            learned += int(human.get("learned") or 0)
        else:
            row["status"] = "STUCK"
            row["note"] = "no page progress — next job"
        row["fields_learned"] = learned
        try:
            row["final_url"] = page.url
        except Exception:
            pass
        if row.get("status") == "AUTH_FAILED":
            if not _aggregator_host(url or row.get("final_url") or ""):
                apply_now.persist_skipped(row, row.get("note") or "all portal passwords rejected or account locked")
                print("  Skipping this job. Closing the tab and opening the next leftover.", flush=True)
        record_lesson(job, row, learned)
        return row
    except Exception as exc:
        if row.get("status") in {"SUBMITTED", "WAITING_EXPIRED", "CAPTCHA", "CLOSED", "AUTH_FAILED"}:
            row["note"] = (row.get("note") or "") + f" ({exc})"
            return row
        row["status"] = "ERROR"
        row["note"] = str(exc)[:280]
        try:
            row["final_url"] = page.url
        except Exception:
            pass
        try:
            human = wait_for_human(page, job, wait_seconds or 90, resume)
            if human.get("ok"):
                row.update({k: human[k] for k in ("ok", "status", "note")})
                row["final_url"] = page.url
        except Exception:
            pass
        return row


def public_queue(jobs: list[dict], allow_aggregators: bool = True) -> tuple[list[dict], list[dict]]:
    try_jobs = []
    blocked = []
    for job in jobs:
        url = job.get("apply_url") or apply_now.apply_url(job) or job.get("url") or ""
        job = dict(job)
        job["apply_url"] = url
        kind = classify_url(url, job, allow_aggregators=allow_aggregators)
        if kind == "TRY":
            try_jobs.append(job)
        else:
            blocked.append({
                **{k: job.get(k) for k in ("company", "title", "location", "url", "ats", "job_id")},
                "apply_url": url,
                "ok": False,
                "status": "OTHER_AUTOMATION" if kind == "OTHER_AUTOMATION" else "LOGIN_BLOCKED",
                "note": "held until leftover career-portal jobs are empty",
            })
    return try_jobs, blocked


def interleave_boards_and_career(jobs: list[dict], limit: int) -> list[dict]:
    """Other-board Easy Apply first (3:1), then a career portal. Do not stall on Workday."""
    career, boards = [], []
    for job in jobs:
        if apply_now.is_company_career_portal(job) and not apply_now.is_aggregator_board(job):
            career.append(job)
        else:
            boards.append(job)

    def career_rank(job: dict) -> int:
        u = ((job.get("apply_url") or job.get("url") or "") + "").lower()
        if "greenhouse" in u or "lever.co" in u or "ashbyhq.com" in u:
            return 0
        if "smartrecruiters.com" in u:
            return 1
        if "myworkdayjobs" in u:
            return 2
        return 5

    career.sort(key=career_rank)

    def board_rank(job: dict) -> int:
        u = ((job.get("apply_url") or job.get("url") or "") + "").lower()
        if "naukri.com" in u:
            return 0
        if "foundit.in" in u:
            return 1
        if "indeed.com" in u:
            return 2
        if "instahyre.com" in u or "cutshort" in u:
            return 8
        if "linkedin.com" in u:
            return 9
        return 5

    boards.sort(key=board_rank)
    if linkedin_blocked_now():
        boards = [
            j for j in boards
            if "linkedin.com" not in ((j.get("apply_url") or j.get("url") or "")).lower()
        ]
    if FOUNDIT_AKAMAI_BLOCKED:
        boards = [
            j for j in boards
            if "foundit.in" not in ((j.get("apply_url") or j.get("url") or "")).lower()
        ]
    out: list[dict] = []
    b = c = 0
    while len(out) < (limit or 10**9) and (b < len(boards) or c < len(career)):
        for _ in range(3):
            if b < len(boards) and len(out) < (limit or 10**9):
                out.append(boards[b])
                b += 1
        if c < len(career) and len(out) < (limit or 10**9):
            out.append(career[c])
            c += 1
    return out


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


def _cdp_up() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(CDP + "/json/version", timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_real_chrome() -> None:
    """Start Google Chrome as a normal desktop app on the rafi.success profile.

    Use /opt/google/chrome/chrome so the Cursor wrapper cannot force
    ~/.config/google-chrome. Load Simplify Copilot every time.
    """
    import subprocess

    os.environ.setdefault("DISPLAY", ":1")
    PROFILE.mkdir(parents=True, exist_ok=True)
    ext = simplify_copilot.ensure_extension()
    env = os.environ.copy()
    env["DISPLAY"] = os.environ.get("DISPLAY", ":1")
    # Drop wrapper-injected CHROME flags if any.
    env.pop("CHROME_WRAPPER", None)
    chrome_bin = CHROME if Path(CHROME).exists() else "/opt/google/chrome/chrome"
    cmd = [
        chrome_bin,
        f"--user-data-dir={PROFILE}",
        "--profile-directory=Default",
        "--remote-debugging-port=9222",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--start-maximized",
        f"--load-extension={ext}",
        "--disable-features=DisableLoadExtensionCommandLineSwitch",
        f"https://mail.google.com/",
    ]
    print(f"  Chrome bin {chrome_bin} profile {PROFILE} + Simplify Copilot", flush=True)
    subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(50):
        time.sleep(0.4)
        if _cdp_up():
            return
    raise RuntimeError("Chrome did not open CDP 9222 for the rafi.success@gmail.com profile")


def launch_context(pw, headed: bool):
    args = ["--no-sandbox", "--disable-dev-shm-usage"]
    if headed:
        os.environ.setdefault("DISPLAY", ":1")
        # Reuse the already-open rafi.success@gmail.com Chrome. Never spawn a second profile.
        if not _cdp_up():
            print(f"  Starting real Chrome for {PROFILE_EMAIL} at {PROFILE}", flush=True)
            start_real_chrome()
        print("  Connecting to open Chrome on CDP 9222...", flush=True)
        browser = pw.chromium.connect_over_cdp(CDP, timeout=25000)
        print("  CDP connected.", flush=True)
        context = browser.contexts[0]
        signed_in = False
        for p in list(context.pages):
            try:
                u = (p.url or "")
            except Exception:
                continue
            if (
                ("google.com" in u or "mail.google.com" in u)
                and "challenge" not in u
                and "signin" not in u
            ):
                signed_in = True
                break
        if not signed_in:
            login_page = next((p for p in context.pages if "accounts.google.com" in (p.url or "")), None)
            try:
                google_auth.sign_in_chrome(login_page or context.new_page())
            except Exception as exc:
                print(f"  Google sign-in skipped ({exc}).", flush=True)
        else:
            print("  Chrome already signed in; leaving Google tabs alone.", flush=True)
        try:
            google_auth.announce_2fa_on_pages(list(context.pages), force=True)
        except Exception:
            pass
        global GOOGLE_SIGNIN_BLOCKED
        if google_password_create_parked(context=context):
            GOOGLE_SIGNIN_BLOCKED = True
            print(
                "  Google change-password parked. Never creating a password. "
                "Skipping Naukri/LinkedIn/Indeed/Instahyre this round.",
                flush=True,
            )
        if OWNER_PRESENT or WATCH_OPEN:
            print("  Owner is present. Leaving open application tabs as they are.", flush=True)
        else:
            reset_chrome_tabs(context)
        print(f"  Using open Chrome profile {PROFILE_EMAIL} ({PROFILE}) + Simplify Copilot", flush=True)
        print(f"  One application at a time. Next job after submit, closed posting, or locked/rejected portal login.", flush=True)
        return None, context, None
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


def _keep_tab(url: str) -> bool:
    u = (url or "").lower()
    if u.startswith("chrome://") or u.startswith("chrome-extension://"):
        return True
    if any(x in u for x in ("www.google.com", "mail.google.com", "accounts.google.com")):
        return True
    if "linkedin.com/checkpoint" in u:
        return True
    if "login.icims.com" in u:
        return True
    if "passport.amazon.jobs" in u or u.rstrip("/").endswith("passport.amazon.jobs"):
        return True
    for parked in PARKED_CAPTCHA_URLS:
        p = (parked or "").lower()
        if p and (p in u or u in p or u.split("?")[0] == p.split("?")[0]):
            return True
    return False


def reset_chrome_tabs(context) -> None:
    """Close every application tab. Leave a single Google tab."""
    google = None
    for p in list(context.pages):
        try:
            if p.is_closed():
                continue
            u = p.url or ""
            if "www.google.com" in u:
                google = p
                break
        except Exception:
            continue
    if google is None:
        for p in list(context.pages):
            try:
                if _keep_tab(p.url) and "accounts.google.com" not in (p.url or ""):
                    google = p
                    break
            except Exception:
                continue
    for p in list(context.pages):
        if p is google:
            continue
        try:
            if p.is_closed():
                continue
            if _keep_tab(p.url):
                continue
            p.close()
        except Exception:
            continue
    try:
        if google and not google.is_closed():
            u = (google.url or "").lower()
            if "google.com" not in u and "mail.google.com" not in u:
                google.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=20000)
        elif not any(True for p in context.pages if not p.is_closed()):
            page = context.new_page()
            page.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=20000)
    except Exception:
        pass
    print("  Closed leftover apply tabs. Google/Gmail and parked CAPTCHA tabs stay open.", flush=True)


def close_apply_page(page) -> None:
    try:
        if page and not page.is_closed() and not _keep_tab(page.url):
            page.close()
    except Exception:
        pass


def apply_tab_count(context) -> int:
    n = 0
    for p in context.pages:
        try:
            if p.is_closed() or _keep_tab(p.url):
                continue
            n += 1
        except Exception:
            continue
    return n


def persist_existing_closed() -> None:
    if not RESULTS.exists():
        return
    try:
        rows = json.loads(RESULTS.read_text(encoding="utf-8"))
    except Exception:
        return
    for row in rows:
        if row.get("status") not in {"CLOSED", "AUTH_FAILED"}:
            continue
        if apply_now.is_applied(row):
            continue
        u = row.get("apply_url") or row.get("url") or row.get("final_url") or ""
        if row.get("status") == "AUTH_FAILED":
            if _aggregator_host(u):
                continue
            final = (row.get("final_url") or "").lower()
            apply = (row.get("apply_url") or row.get("url") or "").lower()
            if "login.icims.com" in final and "icims.com" not in apply:
                continue
        apply_now.persist_skipped(row, row.get("note") or "closed posting — cannot submit")


def pick_open_apply_page(context):
    """Prefer the live ATS form the owner can see. Never pick Gmail or parked LinkedIn CAPTCHA."""
    skip = (
        "linkedin.com/checkpoint", "recaptcha", "protechts.net",
        "mail.google.com", "accounts.google.com", "chrome://", "chrome-extension://",
        "omnibox-popup",
    )
    scored = []
    for p in list(context.pages):
        try:
            if p.is_closed():
                continue
            u = (p.url or "").lower()
        except Exception:
            continue
        if any(s in u for s in skip):
            continue
        score = 0
        on_form = False
        try:
            on_form = on_application_form(p)
        except Exception:
            on_form = False
        # Owner-present: a real apply form beats a login wall (Auth0 / iCIMS).
        if on_form and "login." not in u:
            score += 80
        if "avature.net" in u and ("register" in u or "apply" in u or "jobid=" in u):
            score += 90
        elif "myworkdayjobs.com" in u and "/apply" in u:
            score += 40
        elif "avature.net" in u:
            score += 25
        elif any(h in u for h in ("oraclecloud.com", "smartrecruiters.com", "greenhouse.io", "lever.co")):
            score += 20
        elif "/apply" in u:
            score += 10
        if "login.icims.com" in u:
            score += 15
        elif "icims.com" in u:
            score += 12
        if score:
            scored.append((score, p))
    scored.sort(key=lambda item: -item[0])
    return scored[0][1] if scored else None


def match_job_for_page(page, jobs: list[dict]) -> dict | None:
    """Map an already-open tab back to a leftover queue job."""
    try:
        url = (page.url or "").lower()
        title = (page.title() or "").lower()
    except Exception:
        url, title = "", ""
    blob = f"{url} {title}"

    def _job_blob(job: dict) -> str:
        return " ".join(
            str(job.get(k) or "")
            for k in ("company", "title", "apply_url", "url", "job_id")
        ).lower()

    if "icims.com" in url or "schwab" in blob:
        for job in jobs:
            jb = _job_blob(job)
            if "schwab" in jb and ("senior manager" in jb or "124090" in jb or "icims" in jb):
                return job
        for job in jobs:
            if "schwab" in _job_blob(job):
                return job
    for token in re.findall(r"r-\d+", blob):
        for job in jobs:
            if token in _job_blob(job):
                return job
    for job in jobs:
        ju = ((job.get("apply_url") or job.get("url") or "") + "").lower()
        if ju and ju.split("?")[0] in url:
            return job
    return None


def watch_open_application(wait_seconds: int) -> list[dict]:
    """Stay on the already-open apply tab: fill, learn, pause for leftover fields."""
    apply_now.BATCH = apply_now.load_all_discovered()
    form_memory.seed_from_learned()
    seed_parked_captcha_urls()
    queue = apply_now.queue()
    try_jobs, _ = public_queue(queue, allow_aggregators=True)
    leftovers = leftover_career_jobs(try_jobs)
    results: list[dict] = []
    with sync_playwright() as pw:
        browser, context, _page = launch_context(pw, headed=True)
        page = pick_open_apply_page(context)
        if page is None:
            print("  No open application tab to continue. Leaving Chrome as-is.", flush=True)
            return results
        job = match_job_for_page(page, leftovers) or {
            "company": (page.title() or "Open tab").split("|")[0].strip()[:80],
            "title": "ongoing application",
            "apply_url": page.url,
            "url": page.url,
        }
        print(
            f"\n=== Watching open application ===\n"
            f"  {job.get('company')}: {job.get('title')}\n"
            f"  {page.url}\n"
            f"  I will fill what I can, learn what you type, and pause on leftover fields.",
            flush=True,
        )
        try:
            job["resume_path"] = tailor_resume.for_job(job)
        except Exception:
            job["resume_path"] = RESUME
        row = apply_one(page, job, wait_seconds=wait_seconds, navigate=False)
        results.append(row)
        if row.get("ok") and row.get("status") == "SUBMITTED":
            note = (row.get("note") or "").lower()
            if "already applied" not in note:
                apply_now.persist_applied(row, row.get("note") or "cloud_apply submitted")
                notify_submitted(job, row)
        save_cloud(results)
        print(f"  {row.get('status')} ok={row.get('ok')} learned={row.get('fields_learned') or row.get('learned')} {row.get('final_url')}", flush=True)
        print("  Leaving rafi.success@gmail.com Chrome open.", flush=True)
    return results


def learn_open_application(seconds: int = 1800) -> list[dict]:
    """Hands-off: never click or type. Learn answers the owner enters on the open form."""
    apply_now.BATCH = apply_now.load_all_discovered()
    form_memory.seed_from_learned()
    seed_parked_captcha_urls()
    queue = apply_now.queue()
    try_jobs, _ = public_queue(queue, allow_aggregators=True)
    leftovers = leftover_career_jobs(try_jobs)
    results: list[dict] = []
    with sync_playwright() as pw:
        _browser, context, _page = launch_context(pw, headed=True)
        page = pick_open_apply_page(context)
        if page is None:
            print("  No open application tab to learn from.", flush=True)
            return results
        job = match_job_for_page(page, leftovers) or {
            "company": (page.title() or "Open tab").split("|")[0].strip()[:80],
            "title": "ongoing application",
            "apply_url": page.url,
            "url": page.url,
        }
        print(
            "  Hands off. I will NOT open tabs, click, or navigate.\n"
            "  Stay on your CAPTCHA tab and solve it. I only record filled fields.\n"
            f"  Watching: {job.get('company')}: {job.get('title')}\n"
            f"  {page.url}",
            flush=True,
        )
        skip = (
            "mail.google.com", "accounts.google.com", "chrome://",
            "chrome-extension://", "www.google.com",
        )
        learned = 0
        deadline = time.time() + max(seconds, 60)
        while time.time() < deadline:
            for p in list(context.pages):
                try:
                    if p.is_closed():
                        continue
                    u = (p.url or "").lower()
                except Exception:
                    continue
                if any(s in u for s in skip):
                    continue
                job_p = match_job_for_page(p, leftovers) or job
                try:
                    if is_success(p):
                        row = {
                            "company": job_p.get("company"),
                            "title": job_p.get("title"),
                            "apply_url": job_p.get("apply_url") or p.url,
                            "ok": True,
                            "status": "SUBMITTED",
                            "note": "submitted after owner filled leftover fields",
                            "final_url": p.url,
                            "learned": learned,
                        }
                        apply_now.persist_applied(row, row["note"])
                        notify_submitted(job_p, row)
                        results.append(row)
                        save_cloud(results)
                        print("  Submitted. Learned this form for later runs.", flush=True)
                except Exception:
                    pass
                try:
                    changed = form_memory.remember(p, job_p) or []
                    if changed:
                        learned += len(changed)
                        labels = [c.get("label") or "" for c in changed][:6]
                        print(
                            f"  Learned {len(changed)} field(s) on {job_p.get('company')}: {labels}",
                            flush=True,
                        )
                except Exception:
                    pass
            time.sleep(3)
        print(f"  Still learning-only after {seconds}s. Learned {learned} field(s).", flush=True)
        results.append({
            "company": job.get("company"),
            "title": job.get("title"),
            "ok": False,
            "status": "NEED_INPUT",
            "note": f"learn-only; learned {learned} fields",
            "final_url": page.url,
            "learned": learned,
        })
        save_cloud(results)
    return results


def mark_google_2fa_parked(context=None, page=None, force: bool = False) -> bool:
    """Park Naukri/LinkedIn/Indeed/Instahyre while a Google 2FA prompt is open.

    Always persist/print the tap number (and again if Google changes it) so
    the owner can select it on mobile. force=True at the start of every run.
    """
    global GOOGLE_2FA_PARKED
    pages = []
    if page is not None:
        pages = google_auth._all_browser_pages(page)
    elif context is not None:
        try:
            pages = list(context.pages)
        except Exception:
            pages = []
    number = google_auth.announce_2fa_on_pages(pages, force=force)
    if number:
        if not GOOGLE_2FA_PARKED:
            print(
                "  Google 2FA is parked (Nothing Phone / OnePlus). "
                "Skipping Naukri/LinkedIn/Indeed/Instahyre this session; "
                "career portals and Foundit continue.",
                flush=True,
            )
        GOOGLE_2FA_PARKED = True
        return True
    return GOOGLE_2FA_PARKED


def leftover_career_jobs(try_jobs: list[dict]) -> list[dict]:
    out = []
    applied_ids = {str(k) for k in apply_now.load_applied_ids()}
    for job in try_jobs:
        if apply_now.is_applied(job):
            continue
        keys = apply_now.job_match_keys(job)
        if keys & SESSION_SKIP_KEYS:
            continue
        u = ((job.get("apply_url") or job.get("url") or "") + "").lower()
        if any(jid.isdigit() and len(jid) >= 6 and jid.lower() in u for jid in applied_ids):
            continue
        # Owner 21 Aug 2026: skip remaining JPMC / Chase leftovers forever.
        if "jpmc.fa" in u or "jpmorgan" in u or "chasebank" in u:
            continue
        # Owner 21 Aug 2026: AMD iCIMS Auth0 rejected every stored portal password.
        if "careers.amd.com" in u or "login.icims.com" in u and "amd" in u:
            continue
        if linkedin_blocked_now() and "linkedin.com" in u:
            continue
        if GOOGLE_SIGNIN_BLOCKED and any(
            h in u for h in ("linkedin.com", "naukri.com", "indeed.com", "instahyre.com")
        ):
            continue
        if GOOGLE_2FA_PARKED and any(
            h in u for h in ("linkedin.com", "naukri.com", "indeed.com", "instahyre.com")
        ):
            continue
        if FOUNDIT_AKAMAI_BLOCKED and "foundit.in" in u:
            continue
        out.append(job)
    return out


def _naukri_leftover_n(jobs: list[dict]) -> int:
    return sum(
        1
        for j in jobs
        if "naukri.com" in ((j.get("apply_url") or j.get("url") or "")).lower()
    )


def _naukri_jobs_from_api_items(items: list) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("jobTitle") or ""
        company = item.get("companyName") or item.get("company") or "naukri"
        jid = str(item.get("jobId") or item.get("id") or "")
        link = (item.get("jdURL") or item.get("jdUrl") or "") + ""
        if link.startswith("/"):
            link = "https://www.naukri.com" + link
        if not link and jid:
            link = f"https://www.naukri.com/job-listings-{jid}"
        key = (link.split("?")[0] if link else "") or jid
        if not key or key in seen:
            continue
        seen.add(key)
        place_parts = []
        ph = item.get("placeholders")
        if isinstance(ph, list):
            place_parts.extend(str(p.get("label") or "") for p in ph if isinstance(p, dict))
        elif isinstance(ph, str):
            place_parts.append(ph)
        for extra in (item.get("jobLocation"), item.get("placeholdersType")):
            if extra:
                place_parts.append(str(extra))
        place = " ".join(x for x in place_parts if x) or "Hyderabad, India"
        if not re.search(r"hyderabad|telangana|remote|india", place, re.I):
            place = "Hyderabad, India"
        footer = str(
            item.get("footerPlaceholderLabel")
            or item.get("applyType")
            or ""
        )
        if re.search(r"company.?site|apply attempted|iimjobs|apply on (?!naukri)", footer, re.I):
            continue
        jobs.append({
            "company": company,
            "title": title,
            "location": place,
            "url": link,
            "apply_url": link,
            "ats": "Naukri",
            "job_id": jid,
        })
    return jobs


def _naukri_srp_url(slug: str, page_no: int) -> str:
    base = f"https://www.naukri.com/{slug}-jobs-in-hyderabad-secunderabad"
    if page_no <= 1:
        return base
    return f"{base}-{page_no}"


def _refresh_boards_no_browser() -> None:
    """When leftover Naukri/career is empty, pull more boards without a second Chrome."""
    print("  Leftover Naukri/career empty. No-browser discover_everywhere + hyd_gcc...", flush=True)
    try:
        import discover_everywhere
        discover_everywhere.main()
    except Exception as exc:
        print(f"  discover_everywhere failed ({exc}).", flush=True)
    try:
        import discover_hyd_gcc
        discover_hyd_gcc.main()
    except Exception as exc:
        print(f"  discover_hyd_gcc failed ({exc}).", flush=True)
    apply_now.BATCH = apply_now.load_all_discovered()


def discover_naukri_in_chrome(context) -> int:
    """Naukri in-page fetch 406s. Navigate logged-in SRPs and capture jobapi XHR."""
    import discover_more_sites as more

    slugs = (
        "senior-software-engineer",
        "lead-software-engineer",
        "principal-software-engineer",
        "staff-software-engineer",
        "technical-architect",
        "solution-architect",
        "software-architect",
        "dot-net",
        "dotnet",
        "dot-net-developer",
        "c-sharp",
        "full-stack",
        "backend-developer",
        "microservices",
        "technical-lead",
        "engineering-manager",
        "senior-backend-engineer",
        "net-architect",
        "azure",
        "kafka",
    )
    captured: list[dict] = []

    def _on_resp(resp) -> None:
        try:
            u = resp.url or ""
            if "naukri.com/jobapi" not in u or "search" not in u:
                return
            if resp.status != 200:
                print(f"  Naukri jobapi HTTP {resp.status} {u.split('?')[0][-40:]}", flush=True)
                return
            data = resp.json()
            rows = (data or {}).get("jobDetails") if isinstance(data, dict) else None
            if rows:
                captured.extend(rows)
                print(f"  Naukri jobapi captured {len(rows)} rows (total {len(captured)}).", flush=True)
        except Exception:
            pass

    page = context.new_page()
    page.on("response", _on_resp)
    try:
        for slug in slugs:
            empty_pages = 0
            for page_no in (1, 2, 3, 4):
                url = _naukri_srp_url(slug, page_no)
                before = len(captured)
                print(f"  Naukri SRP {slug} p{page_no}...", flush=True)
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    dismiss_overlays(page)
                    try:
                        page.wait_for_function(
                            """() => {
                              const t = (document.body && document.body.innerText) || '';
                              if (/quick apply|job-listings/i.test(t) && t.length > 400) return true;
                              return document.querySelectorAll('[class*="tuple"], [data-job-id], a[href*="job-listings"]').length > 3;
                            }""",
                            timeout=14000,
                        )
                    except Exception:
                        page.wait_for_timeout(2500)
                    try:
                        page.mouse.wheel(0, 1600)
                        page.wait_for_timeout(700)
                    except Exception:
                        pass
                except Exception as exc:
                    print(f"  Naukri SRP {slug} p{page_no} failed ({exc}).", flush=True)
                    empty_pages += 1
                    if empty_pages >= 2:
                        break
                    continue
                got = len(captured) - before
                print(f"  Naukri SRP {slug} p{page_no}: +{got} jobapi rows.", flush=True)
                if got < 4:
                    empty_pages += 1
                    if empty_pages >= 2 or got == 0:
                        break
                else:
                    empty_pages = 0
                time.sleep(0.25)
    finally:
        try:
            page.remove_listener("response", _on_resp)
        except Exception:
            pass
        close_apply_page(page)

    jobs = _naukri_jobs_from_api_items(captured)
    uniq: list[dict] = []
    seen_u: set[str] = set()
    for j in jobs:
        u = ((j.get("apply_url") or j.get("url") or "").split("?")[0]).lower()
        if not u or u in seen_u:
            continue
        seen_u.add(u)
        uniq.append(j)
    jobs = uniq
    if not jobs:
        print("  Naukri browser search found 0 Quick-apply cards.", flush=True)
        return 0
    more.merge_and_write(jobs)
    apply_now.BATCH = apply_now.load_all_discovered()
    n = _naukri_leftover_n(apply_now.queue())
    print(
        f"  Naukri browser discover: {len(captured)} jobapi rows, "
        f"{len(jobs)} Quick-apply unique, {n} leftover Naukri in queue.",
        flush=True,
    )
    return n


def main(limit: int = 12, headed: bool = False, wait_seconds: int = 0) -> list[dict]:
    global FOUNDIT_AKAMAI_BLOCKED
    apply_now.BATCH = apply_now.load_all_discovered()
    form_memory.seed_from_learned()
    seed_parked_captcha_urls()
    persist_existing_closed()
    queue = apply_now.queue()
    try_jobs, blocked_board = public_queue(queue, allow_aggregators=True)
    try_jobs = leftover_career_jobs(try_jobs)
    career_n = sum(
        1 for j in try_jobs
        if apply_now.is_company_career_portal(j) and not apply_now.is_aggregator_board(j)
    )
    board_n = len(try_jobs) - career_n
    print(
        f"Queue {len(queue)} | leftover career portals {career_n} | "
        f"leftover other-board {board_n} | skipped {len(blocked_board)}",
        flush=True,
    )
    if headed:
        print(f"Headed Chrome on DISPLAY={os.environ.get('DISPLAY', ':1')} — complete CAPTCHA/login in the desktop view.", flush=True)
    results: list[dict] = []

    pending = interleave_boards_and_career(try_jobs, limit)
    if OWNER_PRESENT:
        seen_career: set[str] = set()
        career_only: list[dict] = []
        for job in leftover_career_jobs(try_jobs):
            if not (
                apply_now.is_company_career_portal(job)
                and not apply_now.is_aggregator_board(job)
            ):
                continue
            u = ((job.get("apply_url") or job.get("url") or "").split("?")[0]).lower()
            m = re.search(r"/job/(\d+)|/jobs/(\d+)|jobid=(\d+)", u, re.I)
            key = next((g for g in (m.groups() if m else ()) if g), None) or u
            if key in seen_career:
                continue
            seen_career.add(key)
            career_only.append(job)
        pending = career_only[: limit or 80]
        print(
            f"Owner present: {len(pending)} unique career portals first "
            f"(Foundit/Naukri/LinkedIn held).",
            flush=True,
        )
    with sync_playwright() as pw:
        browser, context, page = launch_context(pw, headed)
        mark_google_2fa_parked(context=context, page=page, force=True)
        if OWNER_PRESENT:
            open_blob = " ".join(
                ((p.url or "") if not p.is_closed() else "")
                for p in list(context.pages)
            ).lower()

            def _open_rank(job: dict) -> int:
                u = ((job.get("apply_url") or job.get("url") or "")).lower()
                for token in re.findall(r"\d{7,}", u):
                    if token in open_blob:
                        return 0
                return 1

            pending.sort(key=_open_rank)
        if (
            not OWNER_PRESENT
            and not GOOGLE_SIGNIN_BLOCKED
            and _naukri_leftover_n(leftover_career_jobs(pending)) == 0
        ):
            print("  Searching Naukri in Chrome for Quick apply leftovers...", flush=True)
            discover_naukri_in_chrome(context)
            apply_now.BATCH = apply_now.load_all_discovered()
            queue = apply_now.queue()
            try_jobs, _blocked = public_queue(queue, allow_aggregators=True)
            try_jobs = leftover_career_jobs(try_jobs)
            pending = interleave_boards_and_career(try_jobs, limit)
            career_n = sum(
                1 for j in try_jobs
                if apply_now.is_company_career_portal(j) and not apply_now.is_aggregator_board(j)
            )
            print(
                f"  After Naukri search: leftover {len(try_jobs)} "
                f"({career_n} career, {_naukri_leftover_n(try_jobs)} Naukri).",
                flush=True,
            )
            if _naukri_leftover_n(try_jobs) == 0 and career_n == 0:
                _refresh_boards_no_browser()
                apply_now.BATCH = apply_now.load_all_discovered()
                queue = apply_now.queue()
                try_jobs, _blocked = public_queue(queue, allow_aggregators=True)
                try_jobs = leftover_career_jobs(try_jobs)
                pending = interleave_boards_and_career(try_jobs, limit)
                career_n = sum(
                    1 for j in try_jobs
                    if apply_now.is_company_career_portal(j) and not apply_now.is_aggregator_board(j)
                )
                print(
                    f"  After no-browser discover: leftover {len(try_jobs)} "
                    f"({career_n} career, {_naukri_leftover_n(try_jobs)} Naukri).",
                    flush=True,
                )
        # Rebuild after Google/LinkedIn/Foundit session flags are known so
        # Naukri-heavy first-80 slices do not hide Foundit/career leftovers.
        apply_now.BATCH = apply_now.load_all_discovered()
        queue = apply_now.queue()
        try_jobs, _blocked = public_queue(queue, allow_aggregators=True)
        try_jobs = leftover_career_jobs(try_jobs)
        pending = interleave_boards_and_career(try_jobs, limit)
        career_n = sum(
            1 for j in try_jobs
            if apply_now.is_company_career_portal(j) and not apply_now.is_aggregator_board(j)
        )
        print(
            f"  Session queue: leftover {len(try_jobs)} "
            f"({career_n} career, {_naukri_leftover_n(try_jobs)} Naukri).",
            flush=True,
        )
        for attempt in range(1, 4):
            leftover = interleave_boards_and_career(
                leftover_career_jobs(try_jobs), limit
            )
            if not leftover:
                break
            print(
                f"\n=== Apply leftover jobs ({len(leftover)}), other-boards mixed in ===",
                flush=True,
            )
            for i, job in enumerate(leftover, 1):
                mark_google_2fa_parked(context=context, page=page)
                print(f"\n[{i}/{len(leftover)}] {job.get('company')}: {job.get('title')}", flush=True)
                print("  Opening this application only. Will close it on submit, closed posting, or locked login.", flush=True)
                try:
                    job["resume_path"] = tailor_resume.for_job(job)
                    print(f"  Tailored: {tailor_resume.CURRENT.get('headline')}", flush=True)
                except Exception as exc:
                    job["resume_path"] = RESUME
                    print(f"  Tailor failed ({exc}); using architect resume.", flush=True)
                apply_url = (job.get("apply_url") or job.get("url") or "").lower()
                amazon_parked = any(
                    "passport.amazon.jobs" in ((p.url or "").lower())
                    for p in context.pages
                    if not p.is_closed()
                )
                if amazon_parked and "amazon.jobs" in apply_url:
                    print("  Amazon sign-in already parked. Leaving that tab; skipping this duplicate.", flush=True)
                    SESSION_SKIP_KEYS.update(apply_now.job_match_keys(job))
                    continue
                if linkedin_blocked_now() and "linkedin.com" in apply_url:
                    SESSION_SKIP_KEYS.update(apply_now.job_match_keys(job))
                    print("  LinkedIn restricted until 22 Aug 8:30 PM PDT. Next leftover.", flush=True)
                    continue
                linkedin_parked = any(
                    "linkedin.com/checkpoint" in ((p.url or "").lower())
                    for p in context.pages
                    if not p.is_closed()
                )
                if linkedin_parked and "linkedin.com" in apply_url:
                    print("  LinkedIn checkpoint already parked. Skipping other LinkedIn leftovers this round.", flush=True)
                    SESSION_SKIP_KEYS.update(apply_now.job_match_keys(job))
                    continue
                google_pw_create = google_password_create_parked(context=context)
                if google_pw_create and any(
                    x in apply_url for x in ("linkedin.com", "naukri.com", "indeed.com", "instahyre.com")
                ):
                    print("  Google change-password is parked. Not creating a password. Next leftover.", flush=True)
                    SESSION_SKIP_KEYS.update(apply_now.job_match_keys(job))
                    continue
                if any(x in apply_url for x in ("cutshort.io", "cutshort.com")):
                    print("  Cutshort login is blocked. Next leftover.", flush=True)
                    SESSION_SKIP_KEYS.update(apply_now.job_match_keys(job))
                    continue
                if FOUNDIT_AKAMAI_BLOCKED and "foundit.in" in apply_url:
                    print("  Foundit Akamai still blocking this Chrome session. Next leftover.", flush=True)
                    SESSION_SKIP_KEYS.update(apply_now.job_match_keys(job))
                    continue
                navigate = True
                if OWNER_PRESENT:
                    open_page = pick_open_apply_page(context)
                    if open_page is not None and match_job_for_page(open_page, [job]):
                        print("  Continuing the open tab so you can enter leftover fields.", flush=True)
                        page = open_page
                        navigate = False
                    else:
                        page = context.new_page()
                else:
                    for extra in list(context.pages):
                        close_apply_page(extra)
                    page = context.new_page()
                row = apply_one(page, job, wait_seconds=wait_seconds, navigate=navigate)
                results.append(row)
                SESSION_SKIP_KEYS.update(apply_now.job_match_keys(row) | apply_now.job_match_keys(job))
                if row.get("ok") and row.get("status") == "SUBMITTED":
                    apply_now.persist_applied(row, row.get("note") or "cloud_apply submitted")
                    note = (row.get("note") or "").lower()
                    if "already applied" in note:
                        print("  Already applied earlier. Closing this tab and moving on.", flush=True)
                    else:
                        notify_submitted(job, row)
                        print("  Submitted. Closing this tab and moving to the next application.", flush=True)
                    close_apply_page(page)
                elif row.get("status") == "CLOSED":
                    print("  Posting closed. Closing this tab and moving to the next application.", flush=True)
                    close_apply_page(page)
                elif row.get("status") == "AUTH_FAILED":
                    u = row.get("apply_url") or row.get("url") or row.get("final_url") or ""
                    if not apply_now.is_applied(row) and not _aggregator_host(u):
                        apply_now.persist_skipped(row, row.get("note") or "all portal passwords rejected or account locked")
                    print("  Portal login failed. Closing this tab and opening the next leftover.", flush=True)
                    close_apply_page(page)
                elif row.get("status") in KEEP_TAB_STATUSES:
                    print("  Left this tab open for you.", flush=True)
                    if OWNER_PRESENT:
                        print(
                            "  Owner is filling this application. Not starting another leftover.",
                            flush=True,
                        )
                        break
                    print("  Starting the next leftover.", flush=True)
                else:
                    print("  Could not finish this form. Moving to the next leftover.", flush=True)
                    close_apply_page(page)
                save_cloud(results)
                print(f"  {row.get('status')} ok={row.get('ok')} {row.get('final_url')}", flush=True)
                time.sleep(0.6)
            pending = leftover_career_jobs(pending)
        if headed:
            print("  Leaving rafi.success@gmail.com Chrome open.", flush=True)
        elif browser:
            browser.close()
        else:
            context.close()

    submitted = sum(1 for r in results if r.get("ok") and r.get("status") == "SUBMITTED")
    still = leftover_career_jobs(try_jobs)
    still_career = sum(
        1 for j in still
        if apply_now.is_company_career_portal(j) and not apply_now.is_aggregator_board(j)
    )
    print(
        f"\nCloud apply done. Submitted {submitted}. "
        f"Still leftover: {len(still)} ({still_career} career portals).",
        flush=True,
    )
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", help="Open visible Chrome on the cloud desktop")
    parser.add_argument(
        "--wait",
        type=int,
        default=None,
        help="Seconds to wait for human CAPTCHA/login/submit. 0 skips blocked jobs (cron default).",
    )
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument(
        "--until-submitted",
        type=int,
        default=0,
        help="Keep applying until this many NEW submits are logged (overnight).",
    )
    parser.add_argument(
        "--owner-present",
        action="store_true",
        help="Owner is filling leftover fields. Pause on NEED_INPUT; learn answers.",
    )
    parser.add_argument(
        "--watch-open",
        action="store_true",
        help="Continue the already-open apply tab only. Implies --owner-present.",
    )
    parser.add_argument(
        "--learn-only",
        action="store_true",
        help="Do not click or type. Learn answers the owner enters on the open tab.",
    )
    args = parser.parse_args()
    OWNER_PRESENT = bool(args.owner_present or args.watch_open or args.learn_only)
    WATCH_OPEN = bool(args.watch_open or args.learn_only)
    # Headed: wait for human CAPTCHA. Unattended cron can pass --wait 0.
    wait = (360 if args.headed else 0) if args.wait is None else args.wait
    if args.learn_only:
        learn_open_application(seconds=wait or 1800)
    elif args.watch_open:
        watch_open_application(wait_seconds=wait or 1800)
    elif args.until_submitted:
        def _submitted_n() -> int:
            if not SUBMITTED_LOG.exists():
                return 0
            return sum(
                1
                for line in SUBMITTED_LOG.read_text(encoding="utf-8").splitlines()
                if line.startswith("- **") and "SUBMITTED" in line
            )

        start = _submitted_n()
        goal = start + args.until_submitted
        print(
            f"Overnight apply until {args.until_submitted} new submits "
            f"(now {start}, goal {goal}).",
            flush=True,
        )
        idle = 0
        while _submitted_n() < goal:
            before = _submitted_n()
            main(limit=args.limit, headed=args.headed, wait_seconds=wait)
            after = _submitted_n()
            if after <= before:
                idle += 1
                print(f"  No new submit this round ({idle}). Continuing.", flush=True)
                if idle >= 8:
                    print("  Several empty rounds. Still looping leftover jobs.", flush=True)
                    idle = 0
            else:
                idle = 0
            print(f"  Submitted so far: {after - start} new / {after} total.", flush=True)
            # Empty leftover rounds: do not hammer Naukri jobapi.
            time.sleep(12 if after <= before else 2)
    else:
        main(limit=args.limit, headed=args.headed, wait_seconds=wait)
