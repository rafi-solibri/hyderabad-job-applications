"""Finish remaining required fields (country + location) and resubmit."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
C = json.loads((ROOT / "data" / "candidate.json").read_text(encoding="utf-8"))
RESUME = str((ROOT / C["resumePath"]).resolve())
SHOTS = ROOT / "data" / "applications" / "screenshots"
RESULTS = ROOT / "data" / "applications" / "browser_results4.json"
REWARDS = (
    f"Current CTC {C['currentCtcLpa']} LPA (INR {C['currentCtcInr']}). "
    f"Expected CTC {C['expectedCtcLpa']} LPA (INR {C['expectedCtcInr']}). Notice: {C['noticePeriod']}."
)

JOBS = [
    {"company": "Crunchyroll", "title": "Staff Software Engineer",
     "apply_url": "https://job-boards.greenhouse.io/crunchyroll/jobs/8074590", "ats": "Greenhouse"},
    {"company": "Crunchyroll", "title": "Staff Software Engineer, AI/ML",
     "apply_url": "https://job-boards.greenhouse.io/crunchyroll/jobs/7985640", "ats": "Greenhouse"},
    {"company": "Zscaler", "title": "Sr. Staff SDE Java/Go",
     "apply_url": "https://job-boards.greenhouse.io/zscaler/jobs/5177393007", "ats": "Greenhouse"},
    {"company": "Inovalon", "title": "Staff SDE L5",
     "apply_url": "https://boards.greenhouse.io/embed/job_app?for=inovalon&token=7517648003", "ats": "Greenhouse"},
    {"company": "HighRadius", "title": "Java Architect",
     "apply_url": "https://boards.greenhouse.io/embed/job_app?for=highradius&token=7490280003", "ats": "Greenhouse"},
    {"company": "HighRadius", "title": "Forward Deployed Architect II",
     "apply_url": "https://boards.greenhouse.io/embed/job_app?for=highradius&token=7807746003", "ats": "Greenhouse"},
    {"company": "Keyloop", "title": "Principle Software Architect",
     "apply_url": "https://jobs.lever.co/keyloop/c2142ca2-378f-4868-b51d-a7819a1e4a9d/apply", "ats": "Lever"},
    {"company": "TTEC Digital", "title": "Principal Solution Architect - AWS",
     "apply_url": "https://jobs.lever.co/ttecdigital/0f413199-2e41-4325-92f3-902a577d039c/apply", "ats": "Lever"},
]


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def pick_india(page):
    # Phone country combobox and any Country field
    for sel in ["#country", "input[aria-label='Country']", "input[placeholder='Select a country']"]:
        loc = page.locator(sel).first
        if loc.count() == 0:
            continue
        try:
            loc.click()
            loc.fill("India")
            page.wait_for_timeout(400)
            page.locator("[role=option], li").filter(has_text=re.compile(r"^India$", re.I)).first.click(timeout=2000)
        except Exception:
            try:
                page.keyboard.press("Enter")
            except Exception:
                pass
    # intl-tel-input flag
    try:
        page.locator("button[aria-label='Select country'], .iti__selected-flag").first.click(timeout=800)
        page.locator("#iti-0__search-input, input[placeholder='Search']").first.fill("India")
        page.locator(".iti__country", has_text=re.compile(r"India")).first.click(timeout=1500)
    except Exception:
        pass


def fill_gh(page):
    page.locator("#first_name").fill(C["firstName"])
    page.locator("#last_name").fill(C["lastName"])
    page.locator("#email").fill(C["email"])
    pick_india(page)
    try:
        page.locator("#phone").fill(C["phoneNational"])
    except Exception:
        pass
    try:
        page.locator("#resume").set_input_files(RESUME)
    except Exception:
        page.locator("input[type=file]").first.set_input_files(RESUME)
    for loc in page.locator("input[id^='question_'], textarea[id^='question_']").all():
        try:
            if not loc.is_visible():
                continue
            aria = (loc.get_attribute("aria-label") or "").lower()
            if "linkedin" in aria:
                loc.fill(C["linkedIn"])
            elif "reward" in aria or "compensation" in aria:
                loc.fill(REWARDS)
            elif "city" in aria or "address" in aria or "residence" in aria:
                loc.fill("Hyderabad, Telangana, India")
            elif "legal first" in aria:
                loc.fill(C["firstName"])
            elif "legal last" in aria:
                loc.fill(C["lastName"])
            elif "current company" in aria:
                loc.fill(C["currentEmployer"])
            elif "current title" in aria:
                loc.fill(C["currentRole"])
        except Exception:
            pass
    answers = [
        (r"non-competition|non-compete", "No"),
        (r"immigration|sponsorship|work permit|visa", "No"),
        (r"legal right to work", "Yes"),
        (r"require a work permit", "No"),
        (r"worked for Zscaler", "No, I have never worked for Zscaler"),
        (r"how did you learn", "Zscaler Careers Page"),
        (r"on-call", "Yes"),
        (r"State of Residence", "Telangana"),
        (r"procurement or contract", "No"),
    ]
    for q, ans in answers:
        try:
            label = page.get_by_text(re.compile(q, re.I)).first
            if label.count() == 0:
                continue
            box = label.locator("xpath=following::input[1]")
            box.click()
            page.wait_for_timeout(300)
            page.locator("[role=option], li").filter(has_text=re.compile(rf"^{re.escape(ans)}$", re.I)).first.click()
        except Exception:
            continue
    for t in ("I Agree", "I agree"):
        try:
            page.get_by_text(t, exact=True).first.click(timeout=500)
        except Exception:
            pass
    for box in page.locator("input[type=checkbox]").all():
        try:
            if box.is_visible():
                box.check()
        except Exception:
            pass
    pick_india(page)


def fill_lever(page):
    for sel in ["button:has-text('dismiss')", "button:has-text('Accept')", "#onetrust-accept-btn-handler"]:
        try:
            page.locator(sel).first.click(timeout=600)
        except Exception:
            pass
    page.locator("input[name=name]").fill(C["fullName"])
    page.locator("input[name=email]").fill(C["email"])
    page.locator("input[name=phone]").fill(C["phone"])
    page.locator("input[name=org]").fill(C["currentEmployer"])
    page.locator("input[name='urls[LinkedIn]']").fill(C["linkedIn"])
    loc = page.locator("#location-input")
    loc.click()
    loc.fill("")
    loc.type("Hyderabad, India", delay=60)
    page.wait_for_timeout(1200)
    try:
        page.locator("div, li, button").filter(has_text=re.compile(r"Hyderabad", re.I)).first.click(timeout=2000)
    except Exception:
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
    page.locator("input[type=file]").first.set_input_files(RESUME)
    for q, ans in [
        (r"authorized to work|right to work|work eligibility", "Yes"),
        (r"visa|sponsorship", "No"),
        (r"at least 18", "Yes"),
        (r"education|certification|bachelor", "Yes"),
    ]:
        try:
            page.get_by_text(re.compile(q, re.I)).first.locator("xpath=ancestor::*[self::li or self::div][1]").get_by_text(ans, exact=True).first.click()
        except Exception:
            pass
    for q, val in [
        (r"document type|right to work document", "Indian Passport"),
        (r"AI Tools|Claude", "Yes. Claude and ChatGPT for architecture documentation and design exploration."),
        (r"expected.*salary|annual gross", "6000000 INR (60 LPA)"),
        (r"notice period", "Immediate"),
    ]:
        try:
            page.get_by_text(re.compile(q, re.I)).first.locator("xpath=following::input[1] | following::textarea[1]").first.fill(val)
        except Exception:
            pass
    for sel in page.locator("select").all():
        try:
            if "India" in sel.inner_html():
                sel.select_option(label="India")
        except Exception:
            pass


def success(page):
    if any(x in page.url.lower() for x in ("/thanks", "confirmation", "submitted")):
        return True
    return bool(re.search(
        r"thanks for (your )?appl|application (was |has been )?(submitted|received)|thank you for applying",
        page.inner_text("body"), re.I,
    ))


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1300})
        for job in JOBS:
            print(f"\n-> {job['company']}: {job['title']}", flush=True)
            slug = re.sub(r"[^a-z0-9]+", "-", f"r4-{job['company']}-{job['title']}".lower())[:70]
            try:
                page.goto(job["apply_url"], wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(1800)
                if job["ats"] == "Greenhouse":
                    fill_gh(page)
                else:
                    fill_lever(page)
                page.wait_for_timeout(600)
                before = shot(page, f"{slug}-before")
                page.locator("button:has-text('Submit application')").first.click()
                page.wait_for_timeout(6000)
                ok = success(page)
                after = shot(page, f"{slug}-after")
                row = {**job, "ok": ok, "status": "SUBMITTED" if ok else "NOT_CONFIRMED",
                       "url": page.url, "screenshot_before": before, "screenshot_after": after,
                       "confirmation": page.inner_text("body")[:300]}
            except Exception as e:
                row = {**job, "ok": False, "status": "ERROR", "note": str(e)[:400]}
            results.append(row)
            print(f"   {row.get('status')} ok={row.get('ok')} {row.get('note','')}", flush=True)
        browser.close()
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nVerified", sum(1 for r in results if r.get("ok")), "/", len(results))


if __name__ == "__main__":
    main()
