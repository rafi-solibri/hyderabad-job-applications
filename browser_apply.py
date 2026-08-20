"""Fill public Greenhouse/Lever apply forms and verify submission."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
CANDIDATE = json.loads((ROOT / "data" / "candidate.json").read_text(encoding="utf-8"))
RESUME = str((ROOT / CANDIDATE["resumePath"]).resolve())
SHOTS = ROOT / "data" / "applications" / "screenshots"
RESULTS = ROOT / "data" / "applications" / "browser_results.json"
LOG = ROOT / "data" / "applications" / "log.jsonl"

JOBS = [
    {
        "company": "Keyloop",
        "title": "Principle Software Architect",
        "location": "Hyderabad",
        "apply_url": "https://jobs.lever.co/keyloop/c2142ca2-378f-4868-b51d-a7819a1e4a9d/apply",
        "ats": "Lever",
    },
    {
        "company": "Inovalon",
        "title": "Staff Software Development Engineer L5",
        "location": "Hyderabad",
        "apply_url": "https://job-boards.greenhouse.io/inovalon/jobs/7517648003",
        "ats": "Greenhouse",
    },
    {
        "company": "Crunchyroll",
        "title": "Staff Software Engineer",
        "location": "Hyderabad",
        "apply_url": "https://job-boards.greenhouse.io/crunchyroll/jobs/8074590",
        "ats": "Greenhouse",
    },
    {
        "company": "Zscaler",
        "title": "Sr. Staff Software Development Engineer - Java/Go + Distributed Systems",
        "location": "Hyderabad / Bangalore",
        "apply_url": "https://job-boards.greenhouse.io/zscaler/jobs/5177393007",
        "ats": "Greenhouse",
    },
    {
        "company": "HighRadius",
        "title": "Java Architect",
        "location": "Hyderabad (Financial District)",
        "apply_url": "https://job-boards.greenhouse.io/highradius/jobs/7490280003",
        "ats": "Greenhouse",
    },
    {
        "company": "HighRadius",
        "title": "Forward Deployed Architect II",
        "location": "Hyderabad (Financial District)",
        "apply_url": "https://job-boards.greenhouse.io/highradius/jobs/7807746003",
        "ats": "Greenhouse",
    },
    {
        "company": "Dun & Bradstreet",
        "title": "Principle Engineer – Java and Cloud",
        "location": "Hyderabad",
        "apply_url": "https://jobs.lever.co/dnb/d5c26842-0658-4101-93fe-18615b91d198/apply",
        "ats": "Lever",
    },
    {
        "company": "Cprime",
        "title": "ServiceNow Technical Architect",
        "location": "Hyderabad",
        "apply_url": "https://jobs.lever.co/cprime/5411042f-1539-4121-9b5b-11ec98878fcd/apply",
        "ats": "Lever",
    },
    {
        "company": "TTEC Digital",
        "title": "Principal Solution Architect - AWS",
        "location": "Hyderabad",
        "apply_url": "https://jobs.lever.co/ttecdigital/0f413199-2e41-4325-92f3-902a577d039c/apply",
        "ats": "Lever",
    },
    {
        "company": "Crunchyroll",
        "title": "Staff Software Engineer, AI/ML",
        "location": "Hyderabad",
        "apply_url": "https://job-boards.greenhouse.io/crunchyroll/jobs/7985640",
        "ats": "Greenhouse",
    },
]

SUCCESS_RE = re.compile(
    r"thank you|application (has been )?(received|submitted|sent)|successfully (submitted|applied)|we.?ve received your application|application complete",
    re.I,
)
CAPTCHA_RE = re.compile(r"captcha|recaptcha|hcaptcha|i.?m not a robot|verify you are human", re.I)


def log(event):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def shot(page, name: str) -> str:
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def dismiss(page):
    for sel in [
        "button:has-text('Accept')",
        "button:has-text('Accept all')",
        "button:has-text('Accept All')",
        "button:has-text('I agree')",
        "button:has-text('Got it')",
        "button:has-text('Close')",
        "#onetrust-accept-btn-handler",
        "button[aria-label='Close']",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=800):
                loc.click(timeout=800)
        except Exception:
            pass


def fill_by_label(page, patterns, value, exact=False):
    for pat in patterns:
        try:
            loc = page.get_by_label(pat, exact=exact)
            if loc.count() == 0:
                continue
            target = loc.first
            if not target.is_visible():
                continue
            name = (target.get_attribute("type") or "").lower()
            if name == "file":
                continue
            target.fill(value, timeout=2500)
            return True
        except Exception:
            continue
    return False


def fill_css(page, selectors, value):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0 or not loc.is_visible():
                continue
            loc.fill(value, timeout=2500)
            return True
        except Exception:
            pass
    return False


def set_file(page):
    inputs = page.locator("input[type='file']")
    n = inputs.count()
    uploaded = 0
    for i in range(n):
        try:
            el = inputs.nth(i)
            name = (el.get_attribute("name") or "") + " " + (el.get_attribute("id") or "")
            if "cover" in name.lower():
                continue
            el.set_input_files(RESUME)
            uploaded += 1
        except Exception:
            continue
    return uploaded


def answer_custom_fields(page):
    c = CANDIDATE
    mapping = [
        (["linkedin", "linked in"], c["linkedIn"]),
        (["website", "portfolio", "github"], c["linkedIn"]),
        (["current company", "current employer", "organization", "company name"], c["currentEmployer"]),
        (["current title", "current role", "job title"], c["currentRole"]),
        (["notice"], c["noticePeriod"]),
        (["current ctc", "current salary", "current compensation"], str(c["currentCtcInr"])),
        (["expected ctc", "expected salary", "desired salary", "salary expectation"], str(c["expectedCtcInr"])),
        (["years of experience", "total experience", "experience (years)"], str(c["yearsExperience"])),
        (["city"], c["city"]),
        (["state", "province"], c["state"]),
        (["country"], c["country"]),
        (["how did you hear", "hear about"], c["howHeard"]),
    ]
    labels = page.locator("label")
    count = min(labels.count(), 80)
    for i in range(count):
        try:
            text = (labels.nth(i).inner_text() or "").strip()
        except Exception:
            continue
        low = text.lower()
        value = None
        for keys, val in mapping:
            if any(k in low for k in keys):
                value = val
                break
        if not value:
            continue
        try:
            box = labels.nth(i).locator("xpath=following::input[1] | following::textarea[1]").first
            if box.count() and box.is_visible():
                t = (box.get_attribute("type") or "").lower()
                if t in {"file", "hidden", "checkbox", "radio", "submit"}:
                    continue
                box.fill(value, timeout=1500)
        except Exception:
            continue

    # Common selects
    for sel in page.locator("select").all():
        try:
            label = (sel.get_attribute("aria-label") or sel.get_attribute("name") or "").lower()
            html = sel.inner_html().lower()
            if "sponsor" in label or "visa" in label:
                sel.select_option(label=re.compile(r"^no$", re.I))
            elif "authoriz" in label or "right to work" in label:
                sel.select_option(label=re.compile(r"yes", re.I))
            elif "gender" in label:
                try:
                    sel.select_option(label=re.compile(r"male", re.I))
                except Exception:
                    sel.select_option(label=re.compile(r"decline|don't wish|prefer not", re.I))
            elif "hear" in label or "source" in label:
                if "career" in html or "website" in html:
                    sel.select_option(label=re.compile(r"career|website", re.I))
        except Exception:
            continue

    # Yes/No radios
    for label in page.locator("label").all()[:80]:
        try:
            text = (label.inner_text() or "").lower()
        except Exception:
            continue
        if any(k in text for k in ("sponsor", "visa")) and "no" in text and len(text) < 40:
            try:
                label.click(timeout=500)
            except Exception:
                pass


def click_apply_entry(page):
    for sel in [
        "a:has-text('Apply for this job')",
        "button:has-text('Apply for this job')",
        "a:has-text('Apply now')",
        "button:has-text('Apply now')",
        "a:has-text('Submit application')",
        "text=Apply for this job",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1000):
                loc.click()
                page.wait_for_timeout(800)
                return
        except Exception:
            continue


def submit(page):
    for sel in [
        "button:has-text('Submit application')",
        "input[type='submit'][value*='Submit']",
        "button[type='submit']:has-text('Submit')",
        "button:has-text('Submit')",
        "input[type='submit']",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1200):
                loc.click()
                return True
        except Exception:
            continue
    return False


def fill_common(page):
    c = CANDIDATE
    fill_by_label(page, ["First name", "First Name"], c["firstName"])
    fill_by_label(page, ["Last name", "Last Name"], c["lastName"])
    fill_by_label(page, ["Full name", "Name"], c["fullName"])
    fill_css(page, ["input[name='name']", "#name"], c["fullName"])
    fill_css(page, ["input[name='first_name']", "#first_name"], c["firstName"])
    fill_css(page, ["input[name='last_name']", "#last_name"], c["lastName"])
    fill_by_label(page, ["Email", "Email address"], c["email"])
    fill_css(page, ["input[name='email']", "input[type='email']", "#email"], c["email"])
    fill_by_label(page, ["Phone", "Phone number", "Mobile"], c["phone"])
    fill_css(page, ["input[name='phone']", "input[type='tel']", "#phone"], c["phone"])
    fill_by_label(page, ["Current company", "Company", "Organization"], c["currentEmployer"])
    fill_css(page, ["input[name='org']"], c["currentEmployer"])
    fill_by_label(page, ["LinkedIn", "LinkedIn Profile"], c["linkedIn"])
    fill_css(page, ["input[name='urls[LinkedIn]']", "input[name='linkedin']"], c["linkedIn"])
    fill_by_label(
        page,
        ["Additional information", "Comments", "Cover letter"],
        (
            f"Technical Architect with {c['yearsExperience']}+ years in .NET, cloud and distributed systems. "
            f"Hyderabad-based. Current CTC {c['currentCtcLpa']} LPA, expected {c['expectedCtcLpa']} LPA, "
            f"notice {c['noticePeriod']}. Targeting Madhapur / Gachibowli / Financial District."
        ),
    )
    uploaded = set_file(page)
    answer_custom_fields(page)
    return uploaded


def apply_one(page, job: dict) -> dict:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{job['company']}-{job['title']}".lower())[:60]
    page.goto(job["apply_url"], wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1500)
    dismiss(page)
    click_apply_entry(page)
    dismiss(page)
    page.wait_for_timeout(800)

    body = page.inner_text("body")[:4000]
    if CAPTCHA_RE.search(body):
        path = shot(page, f"{slug}-captcha")
        return {"ok": False, "status": "CAPTCHA", "screenshot": path, "note": "Human checkpoint required"}

    uploaded = fill_common(page)
    before = shot(page, f"{slug}-before")
    clicked = submit(page)
    page.wait_for_timeout(3500)
    after_text = page.inner_text("body")[:5000]
    after = shot(page, f"{slug}-after")
    ok = bool(SUCCESS_RE.search(after_text))
    return {
        "ok": ok,
        "status": "SUBMITTED" if ok else ("SUBMIT_CLICKED" if clicked else "FORM_INCOMPLETE"),
        "uploaded_resume": uploaded,
        "screenshot_before": before,
        "screenshot_after": after,
        "confirmation": after_text[:400],
        "url": page.url,
    }


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1100},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        for job in JOBS:
            print(f"\n-> {job['company']}: {job['title']}", flush=True)
            try:
                result = apply_one(page, job)
            except PWTimeout as e:
                result = {"ok": False, "status": "TIMEOUT", "note": str(e)[:300]}
            except Exception as e:
                result = {"ok": False, "status": "ERROR", "note": str(e)[:400]}
            row = {**job, **result}
            results.append(row)
            log({"event": "browser_apply", **row})
            print(f"   {row.get('status')} ok={row.get('ok')} {row.get('note','')}", flush=True)
            time.sleep(1)
        browser.close()

    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    submitted = [r for r in results if r.get("ok")]
    print(f"\nVerified submissions: {len(submitted)} / {len(results)}")


if __name__ == "__main__":
    main()
