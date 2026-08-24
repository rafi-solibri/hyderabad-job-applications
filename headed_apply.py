"""Visible-browser apply. Fills each form, then waits for you to solve CAPTCHA and submit."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

import form_memory

ROOT = Path(__file__).resolve().parent
C = json.loads((ROOT / "data" / "candidate.json").read_text(encoding="utf-8"))
RESUME = str((ROOT / C["resumePath"]).resolve())
SHOTS = ROOT / "data" / "applications" / "screenshots"
RESULTS = ROOT / "data" / "applications" / "headed_results.json"
LOG = ROOT / "data" / "applications" / "log.jsonl"
REWARDS = (
    f"Current CTC {C['currentCtcLpa']} LPA (INR {C['currentCtcInr']}). "
    f"Expected CTC {C['expectedCtcLpa']} LPA (INR {C['expectedCtcInr']}). "
    f"Notice: {C['noticePeriod']}."
)
WAIT_SECONDS = 180

JOBS = [
    {"company": "Crunchyroll", "title": "Staff Software Engineer",
     "url": "https://job-boards.greenhouse.io/crunchyroll/jobs/8074590", "ats": "Greenhouse"},
    {"company": "Crunchyroll", "title": "Staff Software Engineer, AI/ML",
     "url": "https://job-boards.greenhouse.io/crunchyroll/jobs/7985640", "ats": "Greenhouse"},
    {"company": "Inovalon", "title": "Staff Software Development Engineer L5",
     "url": "https://boards.greenhouse.io/embed/job_app?for=inovalon&token=7517648003", "ats": "Greenhouse"},
    {"company": "HighRadius", "title": "Java Architect",
     "url": "https://boards.greenhouse.io/embed/job_app?for=highradius&token=7490280003", "ats": "Greenhouse"},
    {"company": "HighRadius", "title": "Forward Deployed Architect II",
     "url": "https://boards.greenhouse.io/embed/job_app?for=highradius&token=7807746003", "ats": "Greenhouse"},
    {"company": "Zscaler", "title": "Sr. Staff SDE Java/Go + Distributed Systems",
     "url": "https://job-boards.greenhouse.io/zscaler/jobs/5177393007", "ats": "Greenhouse"},
    {"company": "Keyloop", "title": "Principle Software Architect",
     "url": "https://jobs.lever.co/keyloop/c2142ca2-378f-4868-b51d-a7819a1e4a9d/apply", "ats": "Lever"},
    {"company": "TTEC Digital", "title": "Principal Solution Architect - AWS",
     "url": "https://jobs.lever.co/ttecdigital/0f413199-2e41-4325-92f3-902a577d039c/apply", "ats": "Lever"},
]


def log(event):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / f"{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass
    return str(path)


def quiet_click(locator, timeout=1500):
    try:
        locator.click(timeout=timeout)
        return True
    except Exception:
        return False


def is_success(page) -> bool:
    try:
        url = page.url.lower()
        if any(x in url for x in ("/thanks", "confirmation", "submitted", "application-success")):
            return True
        text = page.inner_text("body")
        return bool(re.search(
            r"thanks for (your )?appl|application (was |has been )?(submitted|received)|thank you for applying|we.?ve received your application",
            text, re.I,
        ))
    except Exception:
        return False


def set_india_phone(page):
    try:
        quiet_click(page.locator(".iti__selected-flag, button[aria-label='Select country']").first, 1200)
        page.wait_for_timeout(250)
        quiet_click(page.locator("[data-country-code='in']").first, 2000)
    except Exception:
        pass
    try:
        page.locator("#phone").fill(C["phoneNational"], timeout=2000)
    except Exception:
        pass


def pick_dropdown(page, question, option):
    try:
        label = page.get_by_text(re.compile(question, re.I)).first
        if label.count() == 0:
            return
        box = label.locator("xpath=following::input[1]")
        quiet_click(box, 1200)
        page.wait_for_timeout(250)
        quiet_click(
            page.locator("[role=option], li").filter(has_text=re.compile(rf"^{re.escape(option)}$", re.I)).first,
            2000,
        )
    except Exception:
        pass


def fill_greenhouse(page):
    for eid, value in (
        ("first_name", C["firstName"]),
        ("last_name", C["lastName"]),
        ("email", C["email"]),
    ):
        try:
            page.locator(f"#{eid}").fill(value, timeout=2000)
        except Exception:
            pass
    set_india_phone(page)
    try:
        page.locator("#resume").set_input_files(RESUME, timeout=3000)
    except Exception:
        try:
            page.locator("input[type=file]").first.set_input_files(RESUME, timeout=3000)
        except Exception:
            pass
    for loc in page.locator("input[id^='question_'], textarea[id^='question_']").all():
        try:
            if not loc.is_visible():
                continue
            aria = (loc.get_attribute("aria-label") or "").lower()
            if "linkedin" in aria:
                loc.fill(C["linkedIn"], timeout=1500)
            elif "reward" in aria or "compensation" in aria:
                loc.fill(REWARDS, timeout=1500)
            elif "city" in aria or "address" in aria or "residence" in aria:
                loc.fill("Hyderabad, Telangana", timeout=1500)
            elif "legal first" in aria:
                loc.fill(C["firstName"], timeout=1500)
            elif "legal last" in aria:
                loc.fill(C["lastName"], timeout=1500)
            elif "current company" in aria:
                loc.fill(C["currentEmployer"], timeout=1500)
            elif "current title" in aria:
                loc.fill(C["currentRole"], timeout=1500)
        except Exception:
            continue
    for q, ans in (
        (r"non-competition|non-compete", "No"),
        (r"immigration|sponsorship|work permit|visa", "No"),
        (r"legal right to work", "Yes"),
        (r"require a work permit", "No"),
        (r"worked for Zscaler", "No, I have never worked for Zscaler"),
        (r"how did you learn", "Zscaler Careers Page"),
        (r"on-call", "Yes"),
        (r"State of Residence", "Telangana"),
        (r"procurement or contract", "No"),
    ):
        pick_dropdown(page, q, ans)
    for t in ("I Agree", "I agree"):
        quiet_click(page.get_by_text(t, exact=True).first, 600)
    for box in page.locator("input[type=checkbox]").all():
        try:
            if box.is_visible():
                box.check(timeout=400)
        except Exception:
            pass


def fill_lever(page):
    for sel in ("button:has-text('dismiss')", "button:has-text('Accept')", "#onetrust-accept-btn-handler"):
        quiet_click(page.locator(sel).first, 600)
    for name, value in (
        ("name", C["fullName"]),
        ("email", C["email"]),
        ("phone", C["phone"]),
        ("org", C["currentEmployer"]),
        ("urls[LinkedIn]", C["linkedIn"]),
    ):
        try:
            page.locator(f"input[name='{name}']").fill(value, timeout=2000)
        except Exception:
            pass
    try:
        loc = page.locator("#location-input")
        if loc.count():
            loc.fill("Hyderabad, India", timeout=2000)
            page.wait_for_timeout(800)
            quiet_click(page.locator("li, div").filter(has_text=re.compile(r"Hyderabad", re.I)).first, 1500)
            page.keyboard.press("Enter")
    except Exception:
        pass
    try:
        page.locator("input[type=file]").first.set_input_files(RESUME, timeout=3000)
    except Exception:
        pass
    for q, ans in (
        (r"authorized to work|right to work|work eligibility", "Yes"),
        (r"visa|sponsorship", "No"),
        (r"at least 18", "Yes"),
        (r"education|certification|bachelor", "Yes"),
    ):
        try:
            heading = page.get_by_text(re.compile(q, re.I)).first
            quiet_click(heading.locator("xpath=ancestor::*[self::li or self::div][1]").get_by_text(ans, exact=True).first, 1200)
        except Exception:
            pass
    for q, val in (
        (r"document type|right to work document", "Indian Passport"),
        (r"AI Tools|Claude", "Yes. Claude and ChatGPT for architecture documentation and design exploration."),
        (r"expected.*salary|annual gross", "6000000 INR (60 LPA)"),
        (r"notice period", "Immediate"),
    ):
        try:
            box = page.get_by_text(re.compile(q, re.I)).first.locator("xpath=following::input[1] | following::textarea[1]").first
            name = box.get_attribute("name") or ""
            if not name.startswith("urls["):
                box.fill(val, timeout=1500)
        except Exception:
            pass
    for sel in page.locator("select").all():
        try:
            if "India" in sel.inner_html():
                sel.select_option(label="India", timeout=1500)
        except Exception:
            pass


def wait_for_you(page, job) -> bool:
    print(
        f"\nYOUR TURN: {job['company']} — {job['title']}\n"
        "  1. Confirm phone country is India (+91)\n"
        "  2. Solve the CAPTCHA if it appears\n"
        "  3. Click Submit application\n"
        f"  Waiting up to {WAIT_SECONDS} seconds...\n",
        flush=True,
    )
    deadline = time.time() + WAIT_SECONDS
    while time.time() < deadline:
        if is_success(page):
            return True
        form_memory.remember(page, job)
        page.wait_for_timeout(2000)
    form_memory.remember(page, job)
    return is_success(page)


def apply_one(page, job, index, total):
    slug = re.sub(r"[^a-z0-9]+", "-", f"headed-{job['company']}-{job['title']}".lower())[:70]
    print(f"\n[{index}/{total}] Opening {job['company']}: {job['title']}", flush=True)
    page.goto(job["url"], wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1500)
    page.bring_to_front()
    if "couldn't find" in (page.inner_text("body")[:250].lower()):
        return {"ok": False, "status": "CLOSED"}
    if job["ats"] == "Greenhouse":
        fill_greenhouse(page)
    else:
        fill_lever(page)
    form_memory.apply_memory(page)
    shot(page, f"{slug}-filled")
    quiet_click(page.locator("button:has-text('Submit application')").first, 2000)
    ok = wait_for_you(page, job)
    shot(page, f"{slug}-after")
    return {
        "ok": ok,
        "status": "SUBMITTED" if ok else "WAITING_EXPIRED",
        "url": page.url,
        "confirmation": page.inner_text("body")[:300],
    }


def main():
    results = []
    print("Opening a visible Chrome window. Keep it in front and handle each CAPTCHA.", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        page = context.new_page()
        page.bring_to_front()
        for i, job in enumerate(JOBS, start=1):
            try:
                result = apply_one(page, job, i, len(JOBS))
            except Exception as e:
                result = {"ok": False, "status": "ERROR", "note": str(e)[:400]}
            row = {**job, **result}
            results.append(row)
            log({"event": "headed_apply", **row})
            print(f"   Result: {row.get('status')} ok={row.get('ok')}", flush=True)
        browser.close()
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    submitted = [r for r in results if r.get("ok")]
    print(f"\nDone. Verified submissions: {len(submitted)} / {len(results)}", flush=True)
    for r in results:
        print(f"- {r.get('status'):16} {r['company']}: {r['title']}", flush=True)


if __name__ == "__main__":
    main()
