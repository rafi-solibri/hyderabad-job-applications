"""Submit Greenhouse apps with explicit India (+91) phone country."""
from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
C = json.loads((ROOT / "data" / "candidate.json").read_text(encoding="utf-8"))
RESUME = str((ROOT / C["resumePath"]).resolve())
SHOTS = ROOT / "data" / "applications" / "screenshots"
RESULTS = ROOT / "data" / "applications" / "browser_results5.json"
REWARDS = (
    f"Current CTC {C['currentCtcLpa']} LPA (INR {C['currentCtcInr']}). "
    f"Expected CTC {C['expectedCtcLpa']} LPA (INR {C['expectedCtcInr']}). Notice: {C['noticePeriod']}."
)

JOBS = [
    {"company": "Crunchyroll", "title": "Staff Software Engineer",
     "url": "https://job-boards.greenhouse.io/crunchyroll/jobs/8074590"},
    {"company": "Crunchyroll", "title": "Staff Software Engineer, AI/ML",
     "url": "https://job-boards.greenhouse.io/crunchyroll/jobs/7985640"},
    {"company": "Inovalon", "title": "Staff SDE L5",
     "url": "https://boards.greenhouse.io/embed/job_app?for=inovalon&token=7517648003"},
    {"company": "HighRadius", "title": "Java Architect",
     "url": "https://boards.greenhouse.io/embed/job_app?for=highradius&token=7490280003"},
    {"company": "HighRadius", "title": "Forward Deployed Architect II",
     "url": "https://boards.greenhouse.io/embed/job_app?for=highradius&token=7807746003"},
    {"company": "Zscaler", "title": "Sr. Staff SDE Java/Go",
     "url": "https://job-boards.greenhouse.io/zscaler/jobs/5177393007"},
]


def set_india(page):
    try:
        page.locator(".iti__selected-flag, button[aria-label='Select country']").first.click(timeout=1500)
        page.wait_for_timeout(300)
        page.locator("[data-country-code='in']").first.click(timeout=2000)
        return True
    except Exception:
        return False


def fill(page):
    page.locator("#first_name").fill(C["firstName"])
    page.locator("#last_name").fill(C["lastName"])
    page.locator("#email").fill(C["email"])
    set_india(page)
    page.locator("#phone").fill("8790251698")
    page.locator("#resume").set_input_files(RESUME)
    for loc in page.locator("input[id^='question_'], textarea[id^='question_']").all():
        if not loc.is_visible():
            continue
        aria = (loc.get_attribute("aria-label") or "").lower()
        if "linkedin" in aria:
            loc.fill(C["linkedIn"])
        elif "reward" in aria or "compensation" in aria:
            loc.fill(REWARDS)
        elif "city" in aria or "address" in aria or "residence" in aria:
            loc.fill("Hyderabad, Telangana")
        elif "legal first" in aria:
            loc.fill(C["firstName"])
        elif "legal last" in aria:
            loc.fill(C["lastName"])
        elif "current company" in aria:
            loc.fill(C["currentEmployer"])
        elif "current title" in aria:
            loc.fill(C["currentRole"])
    for q, ans in [
        (r"non-competition|non-compete", "No"),
        (r"immigration|sponsorship|work permit|visa", "No"),
        (r"legal right to work", "Yes"),
        (r"require a work permit", "No"),
        (r"worked for Zscaler", "No, I have never worked for Zscaler"),
        (r"how did you learn", "Zscaler Careers Page"),
        (r"on-call", "Yes"),
        (r"State of Residence", "Telangana"),
        (r"procurement or contract", "No"),
    ]:
        try:
            page.get_by_text(re.compile(q, re.I)).first.locator("xpath=following::input[1]").click()
            page.wait_for_timeout(250)
            page.locator("[role=option], li").filter(has_text=re.compile(rf"^{re.escape(ans)}$", re.I)).first.click()
        except Exception:
            pass
    for t in ("I Agree", "I agree"):
        try:
            page.get_by_text(t, exact=True).first.click(timeout=400)
        except Exception:
            pass
    for box in page.locator("input[type=checkbox]").all():
        try:
            if box.is_visible():
                box.check()
        except Exception:
            pass


def ok(page):
    return bool(re.search(
        r"thanks for (your )?appl|application (was |has been )?(submitted|received)|thank you for applying",
        page.inner_text("body"), re.I,
    )) or any(x in page.url.lower() for x in ("/thanks", "confirmation", "submitted"))


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1200})
        for job in JOBS:
            print("->", job["company"], job["title"], flush=True)
            slug = re.sub(r"[^a-z0-9]+", "-", f"r5-{job['company']}-{job['title']}".lower())[:60]
            page.goto(job["url"], wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1600)
            fill(page)
            page.wait_for_timeout(400)
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / f"{slug}-before.png"), full_page=True)
            page.locator("button:has-text('Submit application')").first.click()
            page.wait_for_timeout(5000)
            success = ok(page)
            page.screenshot(path=str(SHOTS / f"{slug}-after.png"), full_page=True)
            row = {**job, "ok": success, "url_after": page.url, "text": page.inner_text("body")[:250]}
            results.append(row)
            print("   ", success, page.url, flush=True)
        browser.close()
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("Verified", sum(1 for r in results if r["ok"]), "/", len(results))


if __name__ == "__main__":
    main()
