"""Cloud-browser apply: headed Chrome on DISPLAY, one job at a time.

Walks the existing ready-to-apply queue first. Signs into Google, uses
Simplify Copilot / Apply with LinkedIn, and skips only CAPTCHA walls.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import types
from datetime import date, datetime, timezone
from pathlib import Path

# apply_now imports Selenium wrappers we do not need in the cloud VM.
if "selenium" not in sys.modules:
    selenium = types.ModuleType("selenium")
    webdriver = types.ModuleType("selenium.webdriver")
    common = types.ModuleType("selenium.webdriver.common")
    by = types.ModuleType("selenium.webdriver.common.by")
    keys = types.ModuleType("selenium.webdriver.common.keys")
    support = types.ModuleType("selenium.webdriver.support")
    ui = types.ModuleType("selenium.webdriver.support.ui")

    class _By:
        CSS_SELECTOR = "css selector"
        XPATH = "xpath"
        ID = "id"
        NAME = "name"

    class _Keys:
        ENTER = "\n"
        TAB = "\t"
        ESCAPE = "\u001b"

    class _Select:
        def __init__(self, *a, **k):
            pass

        def select_by_visible_text(self, *a, **k):
            pass

    by.By = _By
    keys.Keys = _Keys
    ui.Select = _Select
    for name, mod in (
        ("selenium", selenium),
        ("selenium.webdriver", webdriver),
        ("selenium.webdriver.common", common),
        ("selenium.webdriver.common.by", by),
        ("selenium.webdriver.common.keys", keys),
        ("selenium.webdriver.support", support),
        ("selenium.webdriver.support.ui", ui),
    ):
        sys.modules[name] = mod

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

import apply_now
import form_memory
import tailor_resume

ROOT = Path(__file__).resolve().parent
C = json.loads((ROOT / "data" / "candidate.json").read_text(encoding="utf-8"))
LEARNED = json.loads((ROOT / "data" / "learned_answers.json").read_text(encoding="utf-8"))
RESUME_MASTER = str((ROOT / C["resumePath"]).resolve())
SHOTS = ROOT / "data" / "applications" / "screenshots"
RUN_RESULTS = ROOT / "data" / "applications" / "cloud_apply_results.json"
SKIPPED_PATH = ROOT / "data" / "skipped_jobs.json"
REPORT = ROOT / "DAILY_REPORT.md"
APPLICATIONS = ROOT / "APPLICATIONS.md"
PROFILE_DIR = ROOT / "data" / "browser_profile"
EXT_DIR = ROOT / "data" / "tools" / "simplify-ext"

FIRST = LEARNED.get("legalFirstName") or "Mohammed Abdul Rafi"
LAST = LEARNED.get("legalLastName") or "Ahmed"
FULL = C.get("fullName") or "Mohammed Abdul Rafi Ahmed"
EMAIL = C["email"]
PHONE = "8790251698"
LINKEDIN = C["linkedIn"]
COMPANY = C["currentEmployer"]
TITLE = C["currentRole"]
LINKEDIN_OK = False

SUCCESS_RE = re.compile(
    r"thanks for (your )?appl|application (was |has been )?(submitted|received)|"
    r"thank you for applying|we.?ve received your application|application received|"
    r"already applied|you previously applied|successfully submitted|"
    r"application submitted|application complete|we submitted your application",
    re.I,
)
LOGIN_RE = re.compile(
    r"sign in to continue|log in to continue|please (log|sign) in|"
    r"create an account|join now|sign in with|login to apply|"
    r"you need to (sign|log) in|authenticate to apply|"
    r"linkedin\.com/login|accounts\.google\.com/v3/signin|"
    r"sign in to linkedin|welcome back",
    re.I,
)
CAPTCHA_RE = re.compile(
    r"captcha|recaptcha|hcaptcha|i.?m not a robot|verify you are human|"
    r"unusual traffic|are you a robot|drag the shape|security check|"
    r"let.?s do a quick security check",
    re.I,
)
SIMPLIFY_RE = re.compile(r"^unused$", re.I)  # Simplify buttons are used on purpose now.

SKIP_TITLE = re.compile(
    r"salesforce|servicenow|\bsap\b|\bpega\b|guidewire|d365|dynamics 365|"
    r"spring boot|\bjava\b(?!script)|python|golang|\bgo\b|node\.?js|nodejs|"
    r"ruby on rails|\bror\b|\bruby\b|firmware|devops|devsecops|"
    r"site reliability|\bsre\b|blockchain|\bgis\b|\bbpo\b|call center|"
    r"oracle fusion|oracle erp|\berp\b|\bmes\b|netsuite|abap|"
    r"duck creek|mainframe|electrical|hvac|mechanical engineering|"
    r"linux bsp|device driver|rtl |asic |verification engineer|"
    r"wifi/ wireless|identity defense|snowflake|dbt core|"
    r"data engineer|data-only|machine learning|\bmlops\b|"
    r"hyperautomation|\brpa\b|uipath|android|\bios\b|"
    r"presales|pre-sales|account manager|civil \(|uk water|"
    r"tungsten|ami\b|smart metering|characterization|validation|"
    r"nand\b|physical design|embedded|pcie|layout engineer|"
    r"agentic ai|generative ai data|martech|"
    r"wms configuration|product data management|"
    r"quality engineering manager|data center electrical",
    re.I,
)
# Keep .NET jobs even if the skip regex would fire on a secondary word.
KEEP_DOTNET = re.compile(r"\.net|dotnet|c#|asp\.net", re.I)

SKIP_COMPANIES = {
    "pega", "salesforce", "servicenow", "tableau",
    "ttec", "ttecdigital", "ttecindiacustomersolutionsprivatelimited",
    "spectralconsultants", "vbeyondcorporation", "vbeyond",
    "careerpathsolutionsprivatelimited", "intraedge",
    "theedgepartnership", "theedgepartnership theedgeinasia",
    "michaelpage", "randstadenterprise", "talentiser",
    "diverselynxindiaprivatelimited", "kudzuinfotechprivatelimited",
    "augustainfotech", "aegantechnologiesprivatelimited",
}

HARD_SKIP_SUBSTRINGS = (
    "sap ", " sap", "salesforce", "servicenow", "pega", "guidewire",
    "oracle fusion", "oracle solution",
)


def company_key(name: str) -> str:
    return apply_now.company_key(name)


def stored_password(kind: str = "any") -> str:
    """Password from env secrets or a previous form fill. Never log the value."""
    if kind == "google":
        return os.environ.get("GOOGLE_PASSWORD") or os.environ.get("ACCOUNT_PASSWORD") or ""
    env = os.environ.get("LINKEDIN_PASSWORD") or os.environ.get("GOOGLE_PASSWORD") or ""
    if kind == "linkedin" and env:
        return env
    if env:
        return env
    mem = form_memory.load_memory().get("by_label") or {}
    for key, row in mem.items():
        if "password" not in key:
            continue
        val = str((row or {}).get("value") or "")
        if val and "@" not in val and len(val) >= 8:
            return val
    return ""


def _click_text(page, *labels, timeout=2500) -> bool:
    for label in labels:
        try:
            loc = page.get_by_role("button", name=re.compile(rf"^{re.escape(label)}$", re.I))
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=timeout)
                page.wait_for_timeout(800)
                return True
        except Exception:
            pass
        try:
            loc = page.get_by_text(re.compile(rf"^{re.escape(label)}$", re.I), exact=False)
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=timeout)
                page.wait_for_timeout(800)
                return True
        except Exception:
            pass
    return False


def google_signed_in(page) -> bool:
    url = (page.url or "").lower()
    try:
        text = body_text(page, 1500)
    except Exception:
        text = ""
    if "myaccount.google.com" in url:
        return True
    if "accounts.google.com" in url and re.search(r"choose an account|signed in as", text, re.I):
        return True
    if EMAIL.lower() in text.lower() and "sign in" not in text.lower()[:200]:
        if "myaccount" in url or "google.com" in url:
            return True
    return False


def login_google(page) -> bool:
    password = stored_password("google")
    if not password:
        print("  GOOGLE_PASSWORD secret not set. Skipping Google sign-in (saved form password is not Google's).", flush=True)
        return False
    print(f"  Signing into Google as {EMAIL}...", flush=True)
    try:
        page.goto(
            "https://accounts.google.com/ServiceLogin?hl=en&continue=https://myaccount.google.com/",
            wait_until="domcontentloaded",
            timeout=45000,
        )
    except Exception as exc:
        print(f"  Google login page failed to load: {exc}", flush=True)
        return False
    page.wait_for_timeout(1500)
    close_overlays(page)
    if "myaccount.google.com" in (page.url or "") and "signin" not in (page.url or "").lower():
        print("  Google session already active.", flush=True)
        return True
    # Account chooser
    try:
        acc = page.locator(f"[data-email='{EMAIL}'], div[data-identifier='{EMAIL}']").first
        if acc.count() and acc.is_visible():
            acc.click(timeout=2000)
            page.wait_for_timeout(1200)
    except Exception:
        pass
    try:
        email_box = page.locator("input[type='email'], input[name='identifier'], #identifierId").first
        if email_box.count() and email_box.is_visible():
            email_box.fill(EMAIL, timeout=3000)
            page.wait_for_timeout(400)
            if not _click_text(page, "Next", "Continue"):
                page.keyboard.press("Enter")
            page.wait_for_timeout(1800)
    except Exception:
        pass
    try:
        pw = page.locator("input[type='password'], input[name='Passwd']").first
        if pw.count() and pw.is_visible():
            pw.click()
            pw.fill(password, timeout=3000)
            page.wait_for_timeout(400)
            if not _click_text(page, "Next", "Continue"):
                page.keyboard.press("Enter")
            page.wait_for_timeout(2500)
    except Exception:
        pass
    for _ in range(8):
        close_overlays(page)
        _click_text(page, "Not now", "Skip", "I understand", "Don't use passkey", "Cancel", "Ask later", "No thanks")
        url = page.url or ""
        if "myaccount.google.com" in url and "signin" not in url.lower():
            print("  Google sign-in succeeded.", flush=True)
            shot(page, "google-signed-in")
            return True
        if re.search(r"2-step|two.?step|verify it.?s you|phone|authenticator|recovery", body_text(page, 2000), re.I):
            print("  Google asked for 2FA. Waiting up to 90s for it to clear...", flush=True)
            shot(page, "google-2fa")
            deadline = time.time() + 90
            while time.time() < deadline:
                page.wait_for_timeout(3000)
                if "myaccount.google.com" in (page.url or "") and "signin" not in (page.url or "").lower():
                    print("  Google sign-in succeeded after 2FA.", flush=True)
                    return True
            print("  Google 2FA still blocking.", flush=True)
            return False
        if re.search(r"couldn.?t sign you in|browser or app may not be secure|unusual activity", body_text(page, 2000), re.I):
            print("  Google blocked automated sign-in.", flush=True)
            shot(page, "google-blocked")
            return False
        page.wait_for_timeout(1000)
    print(f"  Google sign-in unfinished at {page.url}", flush=True)
    shot(page, "google-unfinished")
    return False


def login_linkedin(page) -> bool:
    password = stored_password("linkedin")
    print("  Signing into LinkedIn...", flush=True)
    try:
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=45000)
    except Exception as exc:
        print(f"  LinkedIn login page failed: {exc}", flush=True)
        return False
    page.wait_for_timeout(1500)
    close_overlays(page)
    if "feed" in (page.url or "") or "/in/" in (page.url or ""):
        print("  LinkedIn session already active.", flush=True)
        return True
    # Only use Google SSO when we have a working Google password.
    google_btn = None
    if stored_password("google"):
        for sel in (
            "button:has-text('Continue with Google')",
            "button:has-text('Sign in with Google')",
            "a:has-text('Continue with Google')",
            "a:has-text('Sign in with Google')",
        ):
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    google_btn = loc
                    break
            except Exception:
                continue
    if google_btn is not None:
        try:
            with page.expect_popup(timeout=5000) as pop:
                google_btn.click(timeout=2000)
            extra = pop.value
            extra.wait_for_timeout(1500)
            try:
                extra.locator(f"text={EMAIL}").first.click(timeout=2000)
            except Exception:
                pass
            extra.wait_for_timeout(2000)
        except Exception:
            try:
                google_btn.click(timeout=2000)
                page.wait_for_timeout(2000)
            except Exception:
                pass
    # Email + password
    if password and "login" in (page.url or ""):
        try:
            page.locator("input[type='email']").last.fill(EMAIL, timeout=3000)
        except Exception:
            try:
                page.locator("input[autocomplete*='username']").last.fill(EMAIL, timeout=2000)
            except Exception:
                pass
        try:
            page.locator("input[type='password']").last.fill(password, timeout=3000)
        except Exception:
            pass
        if not _click_text(page, "Sign in"):
            try:
                page.locator("button[type='submit']").first.click(timeout=2000)
            except Exception:
                page.keyboard.press("Enter")
        page.wait_for_timeout(3000)
    close_overlays(page)
    url = page.url or ""
    if any(x in url for x in ("/feed", "/in/", "linkedin.com/jobs")) and "login" not in url:
        print("  LinkedIn sign-in succeeded.", flush=True)
        shot(page, "linkedin-signed-in")
        return True
    # LinkedIn sometimes lands on challenge
    if "checkpoint" in url or "challenge" in url:
        print("  LinkedIn challenge/CAPTCHA. Skipping LinkedIn session.", flush=True)
        shot(page, "linkedin-challenge")
        return False
    print(f"  LinkedIn sign-in unfinished at {url}", flush=True)
    shot(page, "linkedin-unfinished")
    return False


def login_simplify(page) -> bool:
    print("  Opening Simplify so Copilot can use the Google session...", flush=True)
    try:
        page.goto("https://simplify.jobs/auth/sign-in", wait_until="domcontentloaded", timeout=40000)
    except Exception:
        try:
            page.goto("https://simplify.jobs/", wait_until="domcontentloaded", timeout=40000)
        except Exception as exc:
            print(f"  Simplify site failed: {exc}", flush=True)
            return False
    page.wait_for_timeout(1500)
    close_overlays(page)
    if re.search(r"dashboard|profile|copilot", page.url or "", re.I) and "sign-in" not in (page.url or ""):
        print("  Simplify session already active.", flush=True)
        return True
    for sel in (
        "button:has-text('Continue with Google')",
        "button:has-text('Sign in with Google')",
        "a:has-text('Continue with Google')",
        "a:has-text('Sign in with Google')",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                try:
                    with page.expect_popup(timeout=4000) as pop:
                        loc.click(timeout=2000)
                    extra = pop.value
                    extra.wait_for_timeout(1200)
                    extra.locator(f"text={EMAIL}").first.click(timeout=2500)
                    extra.wait_for_timeout(2000)
                except Exception:
                    loc.click(timeout=2000)
                    page.wait_for_timeout(1500)
                    try:
                        page.locator(f"text={EMAIL}").first.click(timeout=2500)
                    except Exception:
                        pass
                break
        except Exception:
            continue
    page.wait_for_timeout(2500)
    _click_text(page, "Allow", "Continue", "Accept")
    if "sign-in" not in (page.url or "").lower() or "simplify.jobs" in (page.url or ""):
        print(f"  Simplify auth page: {page.url}", flush=True)
        shot(page, "simplify-auth")
        return True
    return False


def click_simplify(page) -> bool:
    """Use Simplify Copilot controls when they appear."""
    for sel in (
        "button:has-text('Autofill this page')",
        "button:has-text('Autofill This Page')",
        "button:has-text('Autofill with Simplify')",
        "button:has-text('Apply with Simplify')",
        "button:has-text('Fill with Simplify')",
        "button:has-text('Autofill')",
        "#simplify-icon-apply",
        "#simplify-icon",
        "[id*='simplify' i]",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=1500)
                print(f"  Clicked Simplify: {sel}", flush=True)
                page.wait_for_timeout(2500)
                return True
        except Exception:
            continue
    try:
        page.keyboard.press("Alt+Shift+F")
        page.wait_for_timeout(1500)
    except Exception:
        pass
    return False


def load_skipped() -> dict:
    if not SKIPPED_PATH.exists():
        return {}
    try:
        data = json.loads(SKIPPED_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def persist_skipped(job: dict, reason: str) -> None:
    store = load_skipped()
    jid = str(job.get("job_id") or job.get("url") or "")
    store[jid or f"{company_key(job.get('company'))}|{job.get('title')}"] = {
        "company": job.get("company"),
        "title": job.get("title"),
        "url": job.get("url") or job.get("apply_url"),
        "reason": reason,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    SKIPPED_PATH.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def should_hard_skip(job: dict) -> str | None:
    title = job.get("title") or ""
    company = job.get("company") or ""
    ck = company_key(company)
    if ck in SKIP_COMPANIES or ck in apply_now.load_blocked():
        return f"blocked/staffing/skip-company:{company}"
    blob = f"{title} {company}".lower()
    if any(s in blob for s in HARD_SKIP_SUBSTRINGS) and not KEEP_DOTNET.search(title):
        return f"domain-skip:{title[:80]}"
    if SKIP_TITLE.search(title) and not KEEP_DOTNET.search(title):
        return f"title-skip:{title[:80]}"
    if re.search(r"python\s*&\s*\.net|\.net.*python|python.*\.net", title, re.I):
        return "python-mandatory-alongside-dotnet"
    loc = job.get("location") or ""
    if re.search(r"bangalore|bengaluru|pune|chennai|delhi|noida|gurgaon|gurugram", loc, re.I):
        if not re.search(r"hyderabad|telangana", loc, re.I):
            return f"wrong-city:{loc}"
    return None


def shot(page, name: str) -> str:
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{name}.png"
    try:
        page.screenshot(path=str(path), full_page=False)
    except Exception:
        pass
    return str(path)


def quiet_click(locator, timeout=1200) -> bool:
    try:
        if locator.count() == 0:
            return False
        loc = locator.first
        if not loc.is_visible():
            return False
        loc.click(timeout=timeout)
        return True
    except Exception:
        return False


def body_text(page, n=6000) -> str:
    try:
        return page.inner_text("body")[:n]
    except Exception:
        return ""


def close_overlays(page) -> None:
    """Close chat/cookie/message overlays before Next/Submit. Never Simplify."""
    selectors = [
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept all')",
        "button:has-text('Accept All')",
        "button:has-text('Accept cookies')",
        "button:has-text('I Accept')",
        "button:has-text('Got it')",
        "button:has-text('Not now')",
        "button:has-text('No thanks')",
        "button:has-text('Dismiss')",
        "button[aria-label='Dismiss']",
        "button[aria-label='Close']",
        "button[aria-label='close']",
        "button:has-text('×')",
        ".msg-overlay-bubble-header__control",
        "button.artdeco-modal__dismiss",
        "[data-test-modal-close-btn]",
        "button:has-text('Continue without')",
        "button:has-text('Skip for now')",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                label = (loc.inner_text() or loc.get_attribute("aria-label") or "")[:80]
                if SIMPLIFY_RE.search(label):
                    continue
                loc.click(timeout=700)
                page.wait_for_timeout(200)
        except Exception:
            continue
    # LinkedIn messaging overlay
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass


def is_login_wall(page) -> bool:
    url = (page.url or "").lower()
    text = body_text(page, 2500)
    if re.search(r"join linkedin|agree & join|already on linkedin", text, re.I):
        return True
    if "linkedin.com/checkpoint" in url or "linkedin.com/signup" in url:
        return True
    if "foundit.in" in url and re.search(r"login|register|sign in to apply", text, re.I):
        return True
    try:
        if page.locator("button:has-text('Easy Apply'), button:has-text('Apply with Simplify'), button:has-text('Apply with LinkedIn')").count():
            return False
    except Exception:
        pass
    if any(x in url for x in ("/uas/login", "auth0.com")):
        return True
    if "accounts.google.com" in url and "signin" in url:
        return True
    if "/login" in url and "linkedin.com/login" in url:
        return True
    if re.search(r"sign in to apply|join to apply|log in to apply|please sign in to continue", text, re.I):
        if "easy apply" in text.lower() or "apply with simplify" in text.lower():
            return False
        return True
    return False


def is_captcha(page) -> bool:
    text = body_text(page, 2500)
    if CAPTCHA_RE.search(text):
        return True
    try:
        if page.locator(
            "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], iframe[src*='arkoselabs'], "
            "iframe[src*='funcaptcha'], .g-recaptcha, [class*='captcha' i]"
        ).count():
            return True
    except Exception:
        pass
    return False


def is_success(page) -> bool:
    url = (page.url or "").lower()
    if any(x in url for x in ("/thanks", "/confirmation", "application-success", "submitted", "/thank-you")):
        return True
    text = body_text(page, 4000)
    if "error verifying" in text.lower():
        return False
    return bool(SUCCESS_RE.search(text))


def click_apply_entry(page) -> bool:
    click_simplify(page)
    for sel in [
        "button:has-text('Easy Apply')",
        "button:has-text('Apply with Simplify')",
        "a:has-text('Apply with Simplify')",
        "button:has-text('Apply with LinkedIn')",
        "a:has-text('Apply with LinkedIn')",
        "a:has-text('Apply on company website')",
        "a:has-text('Apply on company site')",
        "button:has-text('Apply on company website')",
        "button:has-text('Apply for this job')",
        "a:has-text('Apply for this job')",
        "button:has-text('Apply now')",
        "a:has-text('Apply now')",
        "button:has-text('Apply')",
        "a:has-text('Apply')",
        "input[value='Apply']",
    ]:
        try:
            loc = page.locator(sel).first
            if not loc.count() or not loc.is_visible():
                continue
            label = (loc.inner_text() or "")[:80]
            if re.search(r"upload|attach|browse|choose file", label, re.I):
                continue
            with page.expect_navigation(timeout=8000, wait_until="domcontentloaded") if "company web" in label.lower() else _null_ctx():
                loc.click(timeout=1500)
            page.wait_for_timeout(900)
            print(f"  Clicked apply control: {label or sel}", flush=True)
            return True
        except Exception:
            try:
                loc.click(timeout=1200)
                page.wait_for_timeout(900)
                return True
            except Exception:
                continue
    return False


class _null_ctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fill_core_fields(page) -> None:
    pairs = [
        ("input[name='first_name'], #first_name, input[autocomplete='given-name']", FIRST),
        ("input[name='last_name'], #last_name, input[autocomplete='family-name']", LAST),
        ("input[name='name'], #name, input[autocomplete='name']", FULL),
        ("input[name='email'], #email, input[type='email'], input[autocomplete='email']", EMAIL),
        ("input[name='phone'], #phone, input[type='tel'], input[autocomplete='tel']", PHONE),
        ("input[name='org'], input[name='company'], input[autocomplete='organization']", COMPANY),
        ("input[name='urls[LinkedIn]'], input[name='linkedin'], input[placeholder*='linkedin' i]", LINKEDIN),
        ("input[name='job_title'], input[name='title']", TITLE),
        ("#location-input, input[name='location'], input[placeholder*='Location' i]", "Hyderabad, India"),
        ("input[placeholder='Email' i], input[aria-label='Email']", EMAIL),
        ("input[placeholder='Number' i], input[aria-label='Number']", PHONE),
    ]
    for sel, value in pairs:
        try:
            loc = page.locator(sel).first
            if not loc.count() or not loc.is_visible():
                continue
            cur = ""
            try:
                cur = (loc.input_value() or "").strip()
            except Exception:
                cur = ""
            if cur and cur.lower() not in {"select", "select...", "choose"}:
                continue
            loc.fill(str(value), timeout=1500)
        except Exception:
            continue
    apply_now.set_india_phone(page)
    # iCIMS / Schwab privacy gate
    try:
        for sel, val in (("input[placeholder='Email']", EMAIL), ("input[placeholder='Number']", PHONE)):
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible() and not (loc.input_value() or "").strip():
                loc.fill(val, timeout=1500)
        cc = page.locator("select").filter(has_text=re.compile(r"phone country|make a selection", re.I)).first
        if cc.count():
            try:
                cc.select_option(label=re.compile(r"india", re.I), timeout=1200)
            except Exception:
                pass
        quiet_click(page.get_by_role("button", name=re.compile(r"acknowledge the privacy notice", re.I)), 1500)
    except Exception:
        pass


def upload_resume(page, path: str) -> bool:
    return bool(tailor_resume.upload(page, path))


def answer_yes_no(page) -> None:
    for q, ans in (
        (r"sponsor|visa|immigration|work permit required", "No"),
        (r"authorized to work|right to work|legally permitted|eligible to work|work authorization", "Yes"),
        (r"at least 18|18 years", "Yes"),
        (r"non-compet", "No"),
        (r"relocat", "No"),
        (r"previously applied|former employee|worked for", "No"),
        (r"notice", LEARNED.get("noticePeriod") or "Immediate"),
        (r"gender", "Male"),
    ):
        try:
            heading = page.get_by_text(re.compile(q, re.I)).first
            if not heading.count():
                continue
            scope = heading.locator("xpath=ancestor::*[self::fieldset or self::li or self::div][1]")
            quiet_click(scope.get_by_text(re.compile(rf"^{re.escape(ans)}$", re.I)), 800)
        except Exception:
            continue


def click_next_or_submit(page) -> str:
    close_overlays(page)
    click_simplify(page)
    for sel in [
        "button:has-text('Submit application')",
        "button:has-text('Submit Application')",
        "button:has-text('Submit with Simplify')",
        "input[type='submit'][value*='Submit']",
        "button[type='submit']:has-text('Submit')",
        "button:has-text('Submit')",
        "button:has-text('Send application')",
        "button:has-text('Review')",
        "button:has-text('Save and continue')",
        "button:has-text('Save & continue')",
        "button:has-text('Continue')",
        "button:has-text('Next')",
        "input[type='submit']",
    ]:
        try:
            loc = page.locator(sel).first
            if not loc.count() or not loc.is_visible() or not loc.is_enabled():
                continue
            label = (loc.inner_text() or loc.get_attribute("value") or "")[:80]
            if re.search(r"upload|attach|browse|choose file|resume builder", label, re.I):
                continue
            loc.click(timeout=1500)
            page.wait_for_timeout(1200)
            if re.search(r"submit|send application", label, re.I):
                return "submit"
            return "next"
        except Exception:
            continue
    return ""


def fill_and_advance(page, job: dict, resume_path: str, steps: int = 8) -> str:
    for _ in range(steps):
        close_overlays(page)
        click_simplify(page)
        if is_success(page):
            return "SUBMITTED"
        if is_captcha(page):
            return "CAPTCHA"
        if is_login_wall(page):
            return "LOGIN"
        fill_core_fields(page)
        upload_resume(page, resume_path)
        form_memory.fill_visible(page)
        answer_yes_no(page)
        form_memory.remember(page, job)
        action = click_next_or_submit(page)
        page.wait_for_timeout(900)
        if is_success(page):
            return "SUBMITTED"
        if not action:
            break
    if is_success(page):
        return "SUBMITTED"
    return "FORM_INCOMPLETE"


def resolve_apply_url(job: dict) -> str:
    url = job.get("apply_url") or apply_now.apply_url(job) or job.get("url") or ""
    if job.get("ats") == "Lever" and url and not url.rstrip("/").endswith("/apply"):
        if "jobs.lever.co" in url and "/apply" not in url:
            url = url.rstrip("/") + "/apply"
    return url


def apply_one(page, job: dict) -> dict:
    company = job.get("company") or ""
    title = job.get("title") or ""
    slug = re.sub(r"[^a-z0-9]+", "-", f"{company}-{title}".lower())[:55]
    url = resolve_apply_url(job)
    job["apply_url"] = url

    skip = should_hard_skip(job)
    if skip:
        persist_skipped(job, skip)
        return {**job, "ok": False, "status": "SKIPPED", "note": skip}

    host = url.lower()
    if not LINKEDIN_OK and any(h in host for h in ("linkedin.com", "foundit.in", "instahyre.com", "naukri.com")):
        persist_skipped(job, "login")
        return {**job, "ok": False, "status": "LOGIN", "note": "board requires login (Google session not available)", "final_url": url}

    try:
        job["resume_path"] = tailor_resume.for_job(job)
    except Exception as exc:
        job["resume_path"] = RESUME_MASTER
        print(f"  Resume tailor failed ({exc}); using master resume.", flush=True)
    resume_path = job["resume_path"]

    def _on_files(chooser):
        try:
            chooser.set_files(resume_path)
        except Exception:
            pass

    try:
        page.remove_listener("filechooser", getattr(page, "_rafi_file_handler", lambda *_: None))
    except Exception:
        pass
    page.on("filechooser", _on_files)
    page._rafi_file_handler = _on_files

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except PWTimeout:
        shot(page, f"{slug}-timeout")
        persist_skipped(job, "timeout")
        return {**job, "ok": False, "status": "TIMEOUT", "note": "navigation timeout", "final_url": page.url}
    except Exception as exc:
        persist_skipped(job, str(exc)[:180])
        return {**job, "ok": False, "status": "ERROR", "note": str(exc)[:300], "final_url": getattr(page, "url", "")}

    page.wait_for_timeout(1400)
    close_overlays(page)

    if is_success(page):
        apply_now.persist_applied(job, "already applied / confirmation on load")
        return {**job, "ok": True, "status": "SUBMITTED", "note": "already applied", "final_url": page.url}

    if is_captcha(page):
        shot(page, f"{slug}-captcha")
        persist_skipped(job, "captcha")
        return {**job, "ok": False, "status": "CAPTCHA", "note": "CAPTCHA blocked", "final_url": page.url}

    if is_login_wall(page):
        shot(page, f"{slug}-login")
        persist_skipped(job, "login")
        return {**job, "ok": False, "status": "LOGIN", "note": "login wall", "final_url": page.url}

    click_apply_entry(page)
    page.wait_for_timeout(1000)
    close_overlays(page)

    # Follow company-site tab if LinkedIn opened one
    try:
        if len(page.context.pages) > 1:
            page.context.pages[-1].bring_to_front()
            page = page.context.pages[-1]
    except Exception:
        pass

    if is_captcha(page):
        shot(page, f"{slug}-captcha")
        persist_skipped(job, "captcha")
        return {**job, "ok": False, "status": "CAPTCHA", "note": "CAPTCHA blocked", "final_url": page.url}
    if is_login_wall(page):
        shot(page, f"{slug}-login")
        persist_skipped(job, "login")
        return {**job, "ok": False, "status": "LOGIN", "note": "login wall", "final_url": page.url}

    ats = (job.get("ats") or "").lower()
    try:
        if "greenhouse" in ats or "greenhouse.io" in (page.url or ""):
            apply_now.fill_greenhouse(page, job)
        elif "lever" in ats or "jobs.lever.co" in (page.url or ""):
            apply_now.fill_lever(page)
    except Exception as exc:
        print(f"  ATS fill helper failed: {exc}", flush=True)

    status = fill_and_advance(page, job, resume_path)
    shot(page, f"{slug}-after")
    job["final_url"] = page.url

    if status == "SUBMITTED":
        apply_now.persist_applied({**job, "final_url": page.url}, "cloud chrome submitted")
        return {**job, "ok": True, "status": "SUBMITTED", "final_url": page.url, "note": "cloud chrome submitted"}
    if status in {"CAPTCHA", "LOGIN"}:
        persist_skipped(job, status.lower())
        return {**job, "ok": False, "status": status, "final_url": page.url, "note": status.lower()}
    if apply_now.is_verify_error(page):
        apply_now.block_company(company)
        persist_skipped(job, "verify-error")
        return {**job, "ok": False, "status": "VERIFY_ERROR", "final_url": page.url}

    persist_skipped(job, status)
    apply_now.log({"event": "cloud_apply", **{k: v for k, v in job.items() if k != "confirmation"}, "status": status, "ok": False})
    return {**job, "ok": False, "status": status, "final_url": page.url}


def write_reports(results: list[dict], queue_left: int) -> None:
    submitted = [r for r in results if r.get("ok") and r.get("status") == "SUBMITTED"]
    blocked = [r for r in results if r.get("status") in {"LOGIN", "CAPTCHA", "VERIFY_ERROR", "TIMEOUT"}]
    skipped = [r for r in results if r.get("status") == "SKIPPED"]
    incomplete = [r for r in results if r.get("status") not in {"SUBMITTED", "SKIPPED", "LOGIN", "CAPTCHA", "VERIFY_ERROR", "TIMEOUT"}]
    today = date.today().isoformat()
    lines = [
        f"# Daily job report — {today}",
        "",
        "Cloud run: headed Chrome apply on the existing ready-to-apply queue (one job at a time).",
        "",
        f"**Attempted:** {len(results)}",
        f"**Submitted:** {len(submitted)}",
        f"**Login/CAPTCHA blocked:** {len(blocked)}",
        f"**Policy skipped:** {len(skipped)}",
        f"**Form incomplete / other:** {len(incomplete)}",
        f"**Queue remaining after filters:** {queue_left}",
        "",
        "## Submitted",
        "",
        "| Company | Title | URL |",
        "|---------|-------|-----|",
    ]
    if submitted:
        for r in submitted:
            lines.append(f"| {r.get('company')} | {(r.get('title') or '')[:70]} | {r.get('final_url') or r.get('url') or ''} |")
    else:
        lines.append("| — | none this run | |")
    lines += [
        "",
        "## Blocked (login / CAPTCHA / verify / timeout)",
        "",
        "| Company | Title | Status | URL |",
        "|---------|-------|--------|-----|",
    ]
    for r in blocked[:40]:
        lines.append(
            f"| {r.get('company')} | {(r.get('title') or '')[:60]} | {r.get('status')} | {r.get('final_url') or r.get('url') or ''} |"
        )
    if not blocked:
        lines.append("| — | none | | |")
    lines += ["", "## Policy skipped (sample)", ""]
    for r in skipped[:25]:
        lines.append(f"- {r.get('company')}: {r.get('title')} — {r.get('note')}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    extra = [
        "",
        f"## Today ({date.today().strftime('%-d %b %Y')})",
        "",
        f"Cloud headed-Chrome apply. Submitted **{len(submitted)}**. "
        f"Blocked **{len(blocked)}** (login/CAPTCHA). Policy-skipped **{len(skipped)}**.",
        "",
    ]
    if submitted:
        extra.append("Submitted:")
        for r in submitted:
            extra.append(f"- {r.get('company')}: {r.get('title')}")
        extra.append("")
    text = APPLICATIONS.read_text(encoding="utf-8") if APPLICATIONS.exists() else ""
    marker = f"## Today ({date.today().strftime('%-d %b %Y')})"
    if marker not in text:
        APPLICATIONS.write_text(text.rstrip() + "\n" + "\n".join(extra), encoding="utf-8")


def rebuild_pending_queue(jobs: list[dict]) -> None:
    path = ROOT / "data" / "pending_queue.md"
    lines = [
        "# Pending apply queue",
        "",
        f"**{len(jobs)} jobs** left (best matches, 3 per company).",
        "",
        "| # | Score | Company | Title | Location | Link |",
        "|---|------:|---------|-------|----------|------|",
    ]
    for i, j in enumerate(jobs, 1):
        lines.append(
            f"| {i} | {j.get('match_score') or 0} | {j.get('company')} | "
            f"{(j.get('title') or '')[:70]} | {j.get('location') or ''} | {j.get('url') or j.get('apply_url') or ''} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    global LINKEDIN_OK
    form_memory.seed_from_learned()
    apply_now.C["firstName"] = FIRST
    apply_now.C["lastName"] = LAST
    apply_now.BATCH = apply_now.load_all_discovered()
    skipped_store = load_skipped()
    queue = []
    for job in apply_now.queue():
        jid = str(job.get("job_id") or job.get("url") or "")
        if jid in skipped_store:
            reason = str(skipped_store[jid].get("reason") or "")
            if reason.startswith(("title-skip", "domain-skip", "blocked", "python-", "wrong-city", "staffing", "captcha")):
                continue
        queue.append(job)

    submit_limit = int(os.environ.get("CLOUD_APPLY_SUBMIT_LIMIT", "50"))
    browser_limit = int(os.environ.get("CLOUD_APPLY_LIMIT", "80"))
    print(
        f"Ready-to-apply queue: {len(queue)}. "
        f"Browser attempts cap {browser_limit}, submit cap {submit_limit}.",
        flush=True,
    )
    results: list[dict] = []
    attempted = 0
    submitted = 0
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    ext = str(EXT_DIR) if (EXT_DIR / "manifest.json").exists() else ""

    with sync_playwright() as p:
        launch_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--window-size=1440,1100",
            "--disable-blink-features=AutomationControlled",
        ]
        if ext:
            launch_args += [f"--disable-extensions-except={ext}", f"--load-extension={ext}"]
            print(f"  Loading Simplify Copilot from {ext}", flush=True)
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            executable_path="/usr/bin/google-chrome",
            args=launch_args,
            ignore_default_args=["--enable-automation"],
            viewport={"width": 1440, "height": 1100},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            google_ok = login_google(page)
            # LinkedIn email/password trips a security checkpoint from this VM.
            # Only use LinkedIn after a working Google session (Continue with Google).
            linkedin_ok = login_linkedin(page) if google_ok else False
            simplify_ok = login_simplify(page) if google_ok else False
            LINKEDIN_OK = bool(linkedin_ok)
            print(
                f"  Sessions: google={google_ok} linkedin={linkedin_ok} simplify={simplify_ok}",
                flush=True,
            )
            for job in queue:
                if submitted >= submit_limit or attempted >= browser_limit:
                    break
                skip_reason = should_hard_skip(job)
                print(f"\n[{attempted + 1}] {job.get('company')}: {job.get('title')}", flush=True)
                if skip_reason:
                    persist_skipped(job, skip_reason)
                    row = {**job, "ok": False, "status": "SKIPPED", "note": skip_reason}
                    results.append(row)
                    print(f"  SKIPPED {skip_reason}", flush=True)
                    continue
                attempted += 1
                print(f"  {resolve_apply_url(job)}", flush=True)
                try:
                    row = apply_one(page, job)
                except Exception as exc:
                    row = {**job, "ok": False, "status": "ERROR", "note": str(exc)[:300]}
                    persist_skipped(job, str(exc)[:180])
                if row.get("status") == "LOGIN" and "board requires login" in str(row.get("note") or ""):
                    attempted -= 1
                    print(f"  {row.get('status')} {row.get('note')}", flush=True)
                    results.append(row)
                    continue
                results.append(row)
                if row.get("ok") and row.get("status") == "SUBMITTED":
                    submitted += 1
                print(f"  {row.get('status')} ok={row.get('ok')} {row.get('note') or ''}", flush=True)
                RUN_RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
                # Close extra tabs so we never batch-navigate.
                try:
                    pages = list(context.pages)
                    keep = pages[0]
                    for extra in pages[1:]:
                        extra.close()
                    page = keep
                except Exception:
                    page = context.new_page()
                time.sleep(0.6)
        finally:
            context.close()

    apply_now.BATCH = apply_now.load_all_discovered()
    leftover = apply_now.queue()
    rebuild_pending_queue(leftover)
    write_reports(results, len(leftover))
    submitted = sum(1 for r in results if r.get("ok"))
    print(f"\nDone. Submitted {submitted} / {len(results)}. Queue left: {len(leftover)}", flush=True)


if __name__ == "__main__":
    main()
