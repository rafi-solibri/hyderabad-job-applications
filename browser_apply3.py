"""Apply using visible Greenhouse IDs and Lever field names."""
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
RESULTS = ROOT / "data" / "applications" / "browser_results3.json"
LOG = ROOT / "data" / "applications" / "log.jsonl"
REWARDS = (
    f"Current CTC {C['currentCtcLpa']} LPA (INR {C['currentCtcInr']}). "
    f"Expected CTC {C['expectedCtcLpa']} LPA (INR {C['expectedCtcInr']}). "
    f"Notice: {C['noticePeriod']}."
)

JOBS = [
    {"company": "Crunchyroll", "title": "Staff Software Engineer", "location": "Hyderabad",
     "apply_url": "https://job-boards.greenhouse.io/crunchyroll/jobs/8074590", "ats": "Greenhouse"},
    {"company": "Crunchyroll", "title": "Staff Software Engineer, AI/ML", "location": "Hyderabad",
     "apply_url": "https://job-boards.greenhouse.io/crunchyroll/jobs/7985640", "ats": "Greenhouse"},
    {"company": "Zscaler", "title": "Sr. Staff SDE Java/Go Distributed Systems", "location": "Hyderabad",
     "apply_url": "https://job-boards.greenhouse.io/zscaler/jobs/5177393007", "ats": "Greenhouse"},
    {"company": "Inovalon", "title": "Staff Software Development Engineer L5", "location": "Hyderabad",
     "apply_url": "https://boards.greenhouse.io/embed/job_app?for=inovalon&token=7517648003", "ats": "Greenhouse"},
    {"company": "HighRadius", "title": "Java Architect", "location": "Financial District, Hyderabad",
     "apply_url": "https://boards.greenhouse.io/embed/job_app?for=highradius&token=7490280003", "ats": "Greenhouse"},
    {"company": "HighRadius", "title": "Forward Deployed Architect II", "location": "Financial District, Hyderabad",
     "apply_url": "https://boards.greenhouse.io/embed/job_app?for=highradius&token=7807746003", "ats": "Greenhouse"},
    {"company": "Keyloop", "title": "Principle Software Architect", "location": "Hyderabad",
     "apply_url": "https://jobs.lever.co/keyloop/c2142ca2-378f-4868-b51d-a7819a1e4a9d/apply", "ats": "Lever"},
    {"company": "TTEC Digital", "title": "Principal Solution Architect - AWS", "location": "Hyderabad",
     "apply_url": "https://jobs.lever.co/ttecdigital/0f413199-2e41-4325-92f3-902a577d039c/apply", "ats": "Lever"},
]


def log(event):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def fill_id(page, eid, value):
    loc = page.locator(f"#{eid}")
    if loc.count() == 0:
        return False
    try:
        loc.first.fill(str(value), timeout=2500)
        return True
    except Exception:
        return False


def attach_resume(page):
    for eid in ("resume",):
        loc = page.locator(f"#{eid}")
        if loc.count():
            try:
                loc.first.set_input_files(RESUME)
                return True
            except Exception:
                pass
    loc = page.locator("input[type='file']").first
    if loc.count():
        try:
            loc.set_input_files(RESUME)
            return True
        except Exception:
            return False
    return False


def open_dropdown_and_pick(page, eid, option):
    box = page.locator(f"#{eid}")
    if box.count() == 0:
        return False
    try:
        box.first.click(timeout=2000)
        page.wait_for_timeout(400)
        opt = page.locator("[role='option'], li, button").filter(has_text=re.compile(rf"^{re.escape(option)}$", re.I)).first
        if opt.count():
            opt.click(timeout=2000)
            return True
        page.get_by_text(option, exact=True).last.click(timeout=2000)
        return True
    except Exception:
        return False


def fill_greenhouse(page):
    fill_id(page, "first_name", C["firstName"])
    fill_id(page, "last_name", C["lastName"])
    fill_id(page, "email", C["email"])
    fill_id(page, "phone", C["phoneNational"])
    attach_resume(page)
    # LinkedIn / rewards / city by aria or id prefix
    for loc in page.locator("input[id^='question_'], textarea[id^='question_']").all():
        try:
            if not loc.is_visible():
                continue
            eid = loc.get_attribute("id") or ""
            aria = (loc.get_attribute("aria-label") or "").lower()
            typ = (loc.get_attribute("type") or "").lower()
            if typ in {"checkbox", "radio", "file", "hidden"}:
                continue
            if "linkedin" in aria:
                loc.fill(C["linkedIn"])
            elif "reward" in aria or "compensation" in aria or "salary" in aria:
                loc.fill(REWARDS)
            elif "city" in aria or "residence" in aria or "address" in aria:
                loc.fill("Hyderabad, Telangana, India")
            elif "legal first" in aria:
                loc.fill(C["firstName"])
            elif "legal last" in aria:
                loc.fill(C["lastName"])
            elif "current company" in aria:
                loc.fill(C["currentEmployer"])
            elif "current title" in aria:
                loc.fill(C["currentRole"])
            elif "website" in aria:
                continue
            else:
                # custom comboboxes have empty aria
                role = loc.get_attribute("role") or ""
                if role == "combobox" or typ == "text" and not loc.input_value():
                    # try opening as dropdown if it has a sibling toggle
                    pass
        except Exception:
            continue

    # Known dropdowns by nearby label text
    dropdown_answers = [
        (r"non-competition|non-compete|non competition", "No"),
        (r"immigration|sponsorship|work permit|visa", "No"),
        (r"legal right to work", "Yes"),
        (r"require a work permit", "No"),
        (r"currently work for|previously worked for Zscaler", "No, I have never worked for Zscaler"),
        (r"how did you learn", "Zscaler Careers Page"),
        (r"on-call", "Yes"),
        (r"State of Residence", "Telangana"),
        (r"procurement or contract", "No"),
        (r"Sex|Gender", "Male"),
    ]
    for q, ans in dropdown_answers:
        try:
            label = page.get_by_text(re.compile(q, re.I)).first
            if label.count() == 0:
                continue
            container = label.locator("xpath=ancestor::*[contains(@class,'field') or contains(@class,'question') or self::div][1]")
            control = container.locator("input, [role=combobox], button").first
            if control.count() == 0:
                control = label.locator("xpath=following::input[1]")
            control.click(timeout=1500)
            page.wait_for_timeout(350)
            page.locator("[role='option'], li").filter(has_text=re.compile(rf"^{re.escape(ans)}$", re.I)).first.click(timeout=2000)
        except Exception:
            continue

    # I Agree checkboxes
    for text in ("I Agree", "I agree"):
        try:
            page.get_by_text(text, exact=True).first.click(timeout=800)
        except Exception:
            pass
    for box in page.locator("input[type=checkbox]").all():
        try:
            if box.is_visible():
                box.check(timeout=500)
        except Exception:
            pass


def fill_lever(page):
    page.locator("input[name='name']").fill(C["fullName"])
    page.locator("input[name='email']").fill(C["email"])
    page.locator("input[name='phone']").fill(C["phone"])
    page.locator("input[name='org']").fill(C["currentEmployer"])
    page.locator("input[name='urls[LinkedIn]']").fill(C["linkedIn"])
    loc = page.locator("#location-input")
    if loc.count():
        loc.fill("Hyderabad, Telangana, India")
        page.wait_for_timeout(900)
        try:
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
        except Exception:
            pass
        try:
            page.locator("ul li, .dropdown li, [class*='result']").filter(has_text=re.compile("Hyderabad", re.I)).first.click(timeout=1500)
        except Exception:
            pass
    attach_resume(page)

    # Radios: pick by following label text
    radio_rules = [
        (r"at least 18", "Yes"),
        (r"authorized to work|right to work|work eligibility|legally eligible", "Yes"),
        (r"visa|sponsorship", "No"),
        (r"education|certification|bachelor", "Yes"),
    ]
    for q, ans in radio_rules:
        try:
            heading = page.get_by_text(re.compile(q, re.I)).first
            if heading.count() == 0:
                continue
            block = heading.locator("xpath=ancestor::*[self::li or self::div or self::fieldset][1]")
            block.get_by_text(ans, exact=True).first.click(timeout=1200)
        except Exception:
            continue

    text_rules = [
        (r"right to work document|document type", "Indian Passport"),
        (r"AI Tools|Claude", "Yes. Claude and ChatGPT for architecture documentation, design exploration, and code review assistance."),
        (r"expected.*salary|annual gross|salary expectation", "6000000 INR (60 LPA)"),
        (r"notice period", "Immediate"),
    ]
    for q, val in text_rules:
        try:
            heading = page.get_by_text(re.compile(q, re.I)).first
            if heading.count() == 0:
                continue
            box = heading.locator("xpath=following::input[@type='text' or not(@type)][1] | following::textarea[1]").first
            if box.count():
                name = box.get_attribute("name") or ""
                if name.startswith("urls["):
                    continue
                box.fill(val)
        except Exception:
            continue

    # Country select -> India
    for sel in page.locator("select").all():
        try:
            html = sel.inner_html()
            if "Afghanistan" in html and "India" in html:
                sel.select_option(label="India")
        except Exception:
            pass
    try:
        page.locator("#useNameOnlyPronounsOption").check()
    except Exception:
        pass


def submit(page):
    btn = page.locator("button:has-text('Submit application'), input[type=submit]").first
    if btn.count() == 0:
        btn = page.get_by_role("button", name=re.compile(r"submit", re.I)).first
    btn.scroll_into_view_if_needed()
    btn.click()
    return True


def is_success(page):
    url = page.url.lower()
    if any(x in url for x in ("/thanks", "confirmation", "submitted")):
        return True
    text = page.inner_text("body")
    return bool(re.search(
        r"thanks for (your )?appl|application (was |has been )?(submitted|received)|thank you for applying|we.?ve received your application",
        text, re.I,
    ))


def apply_one(page, job):
    slug = re.sub(r"[^a-z0-9]+", "-", f"r3-{job['company']}-{job['title']}".lower())[:70]
    page.goto(job["apply_url"], wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(2000)
    if "couldn't find" in page.inner_text("body")[:300].lower():
        return {"ok": False, "status": "CLOSED"}
    if job["ats"] == "Greenhouse":
        fill_greenhouse(page)
    else:
        fill_lever(page)
    page.wait_for_timeout(800)
    before = shot(page, f"{slug}-before")
    # Check empty required
    empty = []
    for eid in ("first_name", "last_name", "email"):
        loc = page.locator(f"#{eid}")
        if loc.count() and not (loc.input_value() or "").strip():
            empty.append(eid)
    submit(page)
    page.wait_for_timeout(4500)
    ok = is_success(page)
    after = shot(page, f"{slug}-after")
    return {
        "ok": ok,
        "status": "SUBMITTED" if ok else "NOT_CONFIRMED",
        "empty_before_submit": empty,
        "screenshot_before": before,
        "screenshot_after": after,
        "url": page.url,
        "confirmation": page.inner_text("body")[:350],
    }


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        for job in JOBS:
            print(f"\n-> {job['company']}: {job['title']}", flush=True)
            try:
                result = apply_one(page, job)
            except Exception as e:
                result = {"ok": False, "status": "ERROR", "note": str(e)[:400]}
            row = {**job, **result}
            results.append(row)
            log({"event": "browser_apply3", **row})
            print(f"   {row.get('status')} ok={row.get('ok')} empty={row.get('empty_before_submit')} {row.get('note','')}", flush=True)
        browser.close()
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nVerified", sum(1 for r in results if r.get("ok")), "/", len(results))


if __name__ == "__main__":
    main()
