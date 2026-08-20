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
# One application tab only. Open the next job only after a successful submit
# (or a closed/404 posting that cannot be submitted).
MAX_OPEN_APPLICATIONS = 1

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


def is_success(page) -> bool:
    url = (page.url or "").lower()
    # Mid-wizard URLs are not a submit confirmation.
    if any(x in url for x in ("/apply/section/", "/apply/email", "/apply/form", "stepname=")):
        return False
    if any(x in url for x in ("/thanks", "/confirmation", "application-success", "/thank-you", "/thankyou")):
        return True
    return bool(SUCCESS_RE.search(page_text(page)[:3000]))


def fill_identity(page) -> None:
    pairs = [
        ("input[name='name'], input[name='full_name'], #name", C["fullName"]),
        ("input[name='first_name'], #first_name, input[autocomplete='given-name']", C["firstName"]),
        ("input[name='last_name'], #last_name, input[autocomplete='family-name']", C["lastName"]),
        ("input[name='email'], #email, input[type=email], input[name='primary-email']", C["email"]),
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


CLICK_APPLY_GATE_JS = r"""() => {
  const skipRe = /tailor resume|resume builder|search for jobs|refer a friend|join our talent|talent network|sign in|log in|cookie|privacy|withdraw|save job|share|follow|indeed|linkedin|facebook|twitter|xing|wechat|glassdoor|google plus/i;
  const ranked = [
    /^apply manually$/i,
    /^autofill with resume$/i,
    /^start application$/i,
    /^apply for this job$/i,
    /^apply now$/i,
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
    return r.width > 8 && r.height > 8 && st.visibility !== 'hidden' && st.display !== 'none';
  };
  const candidates = [];
  const collect = (root) => {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('button, a, [role="button"], input[type=button], input[type=submit]').forEach((el) => {
      if (!visible(el)) return;
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
    if (skipRe.test(t) || /indeed|linkedin|naukri|glassdoor/.test(href + ' ' + t)) continue;
    return fire(el, t || 'apply-link');
  }
  return '';
}"""


SKIP_APPLY_LABEL = re.compile(
    r"indeed|linkedin|glassdoor|naukri|tailor resume|resume builder|share|"
    r"refer|save job|talent network|facebook|twitter",
    re.I,
)


def click_apply_gate(page) -> str:
    """Click Apply / Start application / Apply Manually. Never Tailor Resume or Indeed."""
    try:
        hit = page.evaluate(CLICK_APPLY_GATE_JS) or ""
    except Exception:
        hit = ""
    if hit and not SKIP_APPLY_LABEL.search(hit):
        print(f"  Clicked '{hit}'.", flush=True)
        page.wait_for_timeout(1200)
        if re.match(r"^apply( now)?$", hit.strip(), re.I):
            for name in ("Apply Manually", "Start Application", "Autofill with Resume"):
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
        "Start application",
        "Start Application",
        "Start applying",
        "Easy Apply",
        "Apply as a guest",
        "Continue without an account",
        "Apply",
    ):
        exact = name in ("Apply", "Apply now", "Apply Now")
        for role in ("button", "link"):
            try:
                loc = page.get_by_role(role, name=name, exact=exact).first
                if not loc.count() or not loc.is_visible():
                    continue
                text = (loc.inner_text() or name)
                if SKIP_APPLY_LABEL.search(text) or SIMPLIFY_RE.search(text):
                    continue
                loc.click(timeout=1500, force=True)
                print(f"  Clicked '{text.strip()[:40]}'.", flush=True)
                page.wait_for_timeout(1800)
                return text.strip()[:40]
            except Exception:
                continue
    return ""


def click_next_or_submit(page) -> str:
    """Click one navigation control. Returns clicked|submitted|none."""
    dismiss_overlays(page)
    if is_success(page):
        return "submitted"
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
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible() and loc.is_enabled():
                text = loc.inner_text() or loc.get_attribute("value") or loc.get_attribute("aria-label") or ""
                if SIMPLIFY_RE.search(text) or SKIP_APPLY_LABEL.search(text):
                    continue
                loc.click(timeout=2000)
                page.wait_for_timeout(1800)
                return "submitted" if is_success(page) else "clicked"
        except Exception:
            continue
    for sel in (
        "[data-automation-id='bottom-navigation-next-button']",
        "button:has-text('Next')",
        "button:has-text('Continue')",
        "button:has-text('Save and continue')",
        "button:has-text('Save & Continue')",
        "button:has-text('Review')",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible() and loc.is_enabled():
                text = loc.inner_text() or loc.get_attribute("aria-label") or ""
                if SIMPLIFY_RE.search(text) or SKIP_APPLY_LABEL.search(text):
                    continue
                loc.click(timeout=2000)
                page.wait_for_timeout(1400)
                return "clicked"
        except Exception:
            continue
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
    banner = (
        f"\n{'!' * 72}\n"
        f"  CAPTCHA — please solve it now in Desktop / Take control\n"
        f"  {company}: {title}\n"
        f"  {url}\n"
        f"  After you solve it I will continue this same application.\n"
        f"{'!' * 72}\n"
    )
    print(banner, flush=True)
    path = ROOT / "data" / "applications" / "CAPTCHA.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"- **NEED CAPTCHA** {company} — {title}\n  {url}\n"
    prev = path.read_text(encoding="utf-8") if path.exists() else "# CAPTCHA — owner action needed\n\n"
    if url and url in prev:
        return
    path.write_text(prev + line, encoding="utf-8")


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
    if any(x in url for x in ("/apply/email", "/apply", "oneclick-ui", "/application", "stepname=")):
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
        if page.locator("input[type=file]").count():
            return True
        if page.locator("input[type=email], input[name='email'], input[name='first_name']").count():
            return True
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


def accept_terms(page) -> int:
    """Check terms/privacy boxes, including hidden Oracle/Workday checkboxes."""
    n = 0
    try:
        n = page.evaluate(
            """() => {
              const re = /terms|privacy|agree|consent|certify|disclaimer|i have read/i;
              let n = 0;
              for (const el of document.querySelectorAll('input[type=checkbox]')) {
                const wrap = el.closest('label') || el.parentElement || el;
                const t = ((wrap.innerText || '') + ' ' + (el.getAttribute('aria-label') || '') + ' ' + (el.id || '') + ' ' + (el.name || ''));
                if (!re.test(t)) continue;
                if (el.checked) continue;
                try { el.click(); n++; } catch (e) {}
                if (!el.checked) {
                  el.checked = true;
                  el.dispatchEvent(new Event('input', {bubbles: true}));
                  el.dispatchEvent(new Event('change', {bubbles: true}));
                  n++;
                }
              }
              const honey = document.querySelector('input[name="honey-pot"], #honey-pot-1, input[aria-label="honeypot"]');
              if (honey && honey.value) { honey.value = ''; honey.dispatchEvent(new Event('input', {bubbles: true})); }
              return n;
            }"""
        ) or 0
    except Exception:
        n = 0
    for name in (
        "I agree with the terms and conditions",
        "I agree to the terms",
        "I have read and agree",
    ):
        try:
            loc = page.get_by_text(name, exact=False).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=800, force=True)
                n += 1
        except Exception:
            continue
    try:
        box = page.locator(".apply-flow-input-checkbox__button, [class*='checkbox__button']").first
        if box.count() and box.is_visible():
            box.click(timeout=800, force=True)
            n += 1
    except Exception:
        pass
    if n:
        print(f"  Accepted {n} terms/privacy control(s).", flush=True)
    return n


def recover_wrong_board(page) -> bool:
    """Leave Indeed/LinkedIn apply intercepts and return to the company form."""
    url = (page.url or "").lower()
    if "indeed.com" in url or "linkedin.com/jobs" in url:
        print(f"  Left aggregator intercept {url[:80]}", flush=True)
        try:
            page.go_back(wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1200)
            return True
        except Exception:
            return False
    return False


def adopt_newest_page(page, before_ids: set[int] | None = None):
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
            opened.append(p)
        except Exception:
            continue
    if opened:
        return opened[-1]
    return page


def fill_and_advance(page, job: dict, resume: str) -> str:
    """Fill Copilot + memory and click Next/Submit. Returns submitted|clicked|none."""
    dismiss_overlays(page)
    if is_success(page) or simplify_copilot.submitted(page):
        return "submitted"
    recover_wrong_board(page)
    copilot_start = simplify_copilot.start_application(page)
    if copilot_start:
        page.wait_for_timeout(600)
    fill_identity(page)
    apply_now.set_india_phone(page)
    accept_terms(page)
    try:
        upload_resume(page, resume)
    except Exception:
        pass
    copilot_step = simplify_copilot.follow(page)
    if copilot_step == "submitted" or is_success(page):
        return "submitted"
    form_memory.fill_visible(page)
    form_memory.fill_india_state_typeahead(page)
    accept_terms(page)
    if captcha_puzzle_visible(page):
        return "captcha"
    if not on_application_form(page):
        before = {id(p) for p in page.context.pages}
        click_apply_gate(page)
        page.wait_for_timeout(800)
        page = adopt_newest_page(page, before)
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
    while time.time() < deadline:
        try:
            changed = form_memory.remember(page, job) or []
            learned += len(changed)
        except Exception:
            pass
        if captcha_puzzle_visible(page):
            if not notified_captcha:
                notify_captcha(job, page)
                notified_captcha = True
            # Keep this tab open while the owner solves the puzzle.
            deadline = max(deadline, time.time() + 90)
            page.wait_for_timeout(3000)
            continue
        if notified_captcha:
            print("  CAPTCHA cleared. Continuing this same application.", flush=True)
            notified_captcha = False
        try:
            step = fill_and_advance(page, job, resume)
            if step == "submitted" or is_success(page):
                print("  Submitted. Learning this form for later runs.", flush=True)
                return {
                    "ok": True,
                    "status": "SUBMITTED",
                    "note": "submitted in headed Chrome (autofill + Copilot)",
                    "learned": learned,
                }
            if step == "captcha":
                if not notified_captcha:
                    notify_captcha(job, page)
                    notified_captcha = True
                deadline = max(deadline, time.time() + 90)
                page.wait_for_timeout(3000)
                continue
        except Exception:
            pass
        page.wait_for_timeout(2000)
    print(f"  Still no confirmation after {seconds}s. Learned {learned} field(s).", flush=True)
    return {
        "ok": False,
        "status": "WAITING_EXPIRED",
        "note": f"waited {seconds}s; learned {learned} fields",
        "learned": learned,
    }


def apply_one(page, job: dict, wait_seconds: int = 0, navigate: bool = True) -> dict:
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
        if navigate:
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
            page.wait_for_timeout(1800)
        else:
            page.wait_for_timeout(400)
        dismiss_overlays(page)
        copilot_start = simplify_copilot.start_application(page)
        if copilot_start:
            page.wait_for_timeout(800)
        blob = page_text(page)[:2500]
        if re.search(r"page you are looking for doesn.?t exist|job (is )?no longer available|this job has been closed|\b404\b", blob, re.I) or re.search(r"404|not found", page.title() or "", re.I):
            row["status"] = "CLOSED"
            row["final_url"] = page.url
            row["note"] = "job posting gone"
            apply_now.persist_applied(row, "closed posting — cannot submit")
            return row
        last_url = page.url
        same_url_hits = 0
        for _ in range(6):
            recover_wrong_board(page)
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
            page = adopt_newest_page(page, before)
            if page.url == last_url:
                same_url_hits += 1
            else:
                same_url_hits = 0
                last_url = page.url
            if not hit or same_url_hits >= 3:
                break
        recover_wrong_board(page)
        if is_success(page):
            row["ok"] = True
            row["status"] = "SUBMITTED"
            row["note"] = "already applied"
            row["final_url"] = page.url
            return row

        fill_identity(page)
        apply_now.set_india_phone(page)
        try:
            upload_resume(page, resume)
        except Exception:
            pass
        simplify_copilot.autofill(page)
        form_memory.fill_visible(page)
        learned += len(form_memory.remember(page, job) or [])

        stuck_none = 0
        for _ in range(14):
            dismiss_overlays(page)
            recover_wrong_board(page)
            if is_success(page) or simplify_copilot.submitted(page):
                row["ok"] = True
                row["status"] = "SUBMITTED"
                row["final_url"] = page.url
                row["note"] = row.get("note") or "Simplify Copilot"
                return row
            step = fill_and_advance(page, job, resume)
            if step == "submitted" or is_success(page):
                row["ok"] = True
                row["status"] = "SUBMITTED"
                row["final_url"] = page.url
                row["note"] = "Simplify Copilot"
                return row
            if step == "none" or step == "captcha":
                stuck_none += 1
                if step == "captcha":
                    break
                if stuck_none >= 3:
                    break
            else:
                stuck_none = 0
            page.wait_for_timeout(700)

        # Stay on the live form. User solves CAPTCHA in the cloud desktop.
        stay = wait_seconds if wait_seconds else 360
        if captcha_puzzle_visible(page):
            stay = max(stay, 360)
            notify_captcha(job, page)
        human = wait_for_human(page, job, stay, resume)
        row["ok"] = human["ok"]
        row["status"] = human["status"]
        row["note"] = human["note"]
        learned += int(human.get("learned") or 0)
        row["fields_learned"] = learned
        try:
            row["final_url"] = page.url
        except Exception:
            pass
        record_lesson(job, row, learned)
        return row
    except Exception as exc:
        if row.get("status") in {"SUBMITTED", "WAITING_EXPIRED", "CAPTCHA", "CLOSED"}:
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
        browser = pw.chromium.connect_over_cdp(CDP)
        context = browser.contexts[0]
        signed_in = any(
            ("google.com" in (p.url or "") or "mail.google.com" in (p.url or ""))
            and "challenge" not in (p.url or "")
            and "signin" not in (p.url or "")
            for p in context.pages
        )
        if not signed_in:
            login_page = next((p for p in context.pages if "accounts.google.com" in (p.url or "")), None)
            try:
                google_auth.sign_in_chrome(login_page or context.new_page())
            except Exception as exc:
                print(f"  Google sign-in skipped ({exc}).", flush=True)
        else:
            print("  Chrome already signed in; leaving Google tabs alone.", flush=True)
        reset_chrome_tabs(context)
        print(f"  Using open Chrome profile {PROFILE_EMAIL} ({PROFILE}) + Simplify Copilot", flush=True)
        print(f"  One application at a time. Next job only after a successful submit.", flush=True)
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
    return any(x in u for x in ("www.google.com", "mail.google.com", "accounts.google.com"))


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
            if not p.is_closed():
                p.close()
        except Exception:
            continue
    try:
        if google and not google.is_closed():
            google.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=20000)
        elif context.pages:
            pass
        else:
            page = context.new_page()
            page.goto("https://www.google.com/", wait_until="domcontentloaded", timeout=20000)
    except Exception:
        pass
    print("  Closed all application tabs. Fresh Google tab only.", flush=True)


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
        if row.get("status") == "CLOSED" and not apply_now.is_applied(row):
            apply_now.persist_applied(row, row.get("note") or "closed posting — cannot submit")


def leftover_career_jobs(try_jobs: list[dict]) -> list[dict]:
    out = []
    for job in try_jobs:
        if apply_now.is_applied(job):
            continue
        out.append(job)
    return out


def main(limit: int = 12, headed: bool = False, wait_seconds: int = 0) -> list[dict]:
    apply_now.BATCH = apply_now.load_all_discovered()
    form_memory.seed_from_learned()
    persist_existing_closed()
    queue = apply_now.queue()
    try_jobs, blocked_board = public_queue(queue)
    try_jobs = leftover_career_jobs(try_jobs)
    print(
        f"Queue {len(queue)} | leftover career portals {len(try_jobs)} | "
        f"other-board automations {len(blocked_board)}",
        flush=True,
    )
    if headed:
        print(f"Headed Chrome on DISPLAY={os.environ.get('DISPLAY', ':1')} — complete CAPTCHA/login in the desktop view.", flush=True)
    results: list[dict] = []
    if not headed:
        results.extend(blocked_board[:8])

    # Retry incomplete career-portal jobs until submitted or closed.
    pending = try_jobs[:limit] if limit else try_jobs
    with sync_playwright() as pw:
        browser, context, page = launch_context(pw, headed)
        for attempt in range(1, 4):
            leftover = leftover_career_jobs(pending)
            if not leftover:
                break
            print(
                f"\n=== Apply one at a time: {len(leftover)} leftover career-portal job(s) ===",
                flush=True,
            )
            for i, job in enumerate(leftover, 1):
                print(f"\n[{i}/{len(leftover)}] {job.get('company')}: {job.get('title')}", flush=True)
                print("  Opening this application only. Will not open another until it is submitted.", flush=True)
                try:
                    job["resume_path"] = tailor_resume.for_job(job)
                    print(f"  Tailored: {tailor_resume.CURRENT.get('headline')}", flush=True)
                except Exception as exc:
                    job["resume_path"] = RESUME
                    print(f"  Tailor failed ({exc}); using architect resume.", flush=True)
                for extra in list(context.pages):
                    close_apply_page(extra)
                page = context.new_page()
                stay = wait_seconds if wait_seconds else 360
                row = apply_one(page, job, wait_seconds=stay, navigate=True)
                while row.get("status") not in {"SUBMITTED", "CLOSED"}:
                    print(
                        f"  Still not submitted ({row.get('status')}). "
                        f"Keeping this one application open. Not starting another.",
                        flush=True,
                    )
                    try:
                        if page.is_closed():
                            page = context.new_page()
                            row = apply_one(page, job, wait_seconds=stay, navigate=True)
                        else:
                            row = apply_one(page, job, wait_seconds=stay, navigate=False)
                    except Exception as exc:
                        print(f"  Retrying same application after error: {exc}", flush=True)
                        try:
                            if page.is_closed():
                                page = context.new_page()
                        except Exception:
                            page = context.new_page()
                        row = apply_one(page, job, wait_seconds=stay, navigate=True)
                results.append(row)
                if row.get("ok") and row.get("status") == "SUBMITTED":
                    apply_now.persist_applied(row, row.get("note") or "cloud_apply submitted")
                    notify_submitted(job, row)
                    print("  Submitted. Closing this tab and moving to the next application.", flush=True)
                elif row.get("status") == "CLOSED":
                    print("  Posting closed. Closing this tab and moving to the next application.", flush=True)
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
    still = leftover_career_jobs(try_jobs[:limit] if limit else try_jobs)
    print(
        f"\nCloud apply done. Submitted {submitted}. "
        f"Still leftover career-portal jobs: {len(still)}.",
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
    args = parser.parse_args()
    # Headed: wait for human CAPTCHA. Unattended cron can pass --wait 0.
    wait = (360 if args.headed else 0) if args.wait is None else args.wait
    main(limit=args.limit, headed=args.headed, wait_seconds=wait)
