"""Retry applications with exact Greenhouse field names and Lever required questions."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
C = json.loads((ROOT / "data" / "candidate.json").read_text(encoding="utf-8"))
RESUME = str((ROOT / C["resumePath"]).resolve())
QUESTIONS = json.loads((ROOT / "data" / "gh_questions.json").read_text(encoding="utf-8"))
SHOTS = ROOT / "data" / "applications" / "screenshots"
RESULTS = ROOT / "data" / "applications" / "browser_results2.json"
LOG = ROOT / "data" / "applications" / "log.jsonl"

REWARDS = (
    f"Current CTC {C['currentCtcLpa']} LPA (INR {C['currentCtcInr']}). "
    f"Expected CTC {C['expectedCtcLpa']} LPA (INR {C['expectedCtcInr']}). "
    f"Notice period: {C['noticePeriod']}."
)

JOBS = [
    {
        "company": "Crunchyroll",
        "title": "Staff Software Engineer",
        "location": "Hyderabad / Madhapur area",
        "apply_url": "https://job-boards.greenhouse.io/crunchyroll/jobs/8074590",
        "ats": "Greenhouse",
        "key": "crunchyroll:8074590",
    },
    {
        "company": "Crunchyroll",
        "title": "Staff Software Engineer, AI/ML",
        "location": "Hyderabad / Madhapur area",
        "apply_url": "https://job-boards.greenhouse.io/crunchyroll/jobs/7985640",
        "ats": "Greenhouse",
        "key": "crunchyroll:7985640",
    },
    {
        "company": "Zscaler",
        "title": "Sr. Staff Software Development Engineer - Java/Go + Distributed Systems",
        "location": "Hyderabad / Gachibowli",
        "apply_url": "https://job-boards.greenhouse.io/zscaler/jobs/5177393007",
        "ats": "Greenhouse",
        "key": "zscaler:5177393007",
    },
    {
        "company": "Inovalon",
        "title": "Staff Software Development Engineer L5",
        "location": "Hyderabad",
        "apply_url": "https://boards.greenhouse.io/embed/job_app?for=inovalon&token=7517648003",
        "ats": "Greenhouse",
        "key": "inovalon:7517648003",
    },
    {
        "company": "HighRadius",
        "title": "Java Architect",
        "location": "Hyderabad / Financial District",
        "apply_url": "https://boards.greenhouse.io/embed/job_app?for=highradius&token=7490280003",
        "ats": "Greenhouse",
        "key": "highradius:7490280003",
    },
    {
        "company": "HighRadius",
        "title": "Forward Deployed Architect II",
        "location": "Hyderabad / Financial District",
        "apply_url": "https://boards.greenhouse.io/embed/job_app?for=highradius&token=7807746003",
        "ats": "Greenhouse",
        "key": "highradius:7807746003",
    },
    {
        "company": "Keyloop",
        "title": "Principle Software Architect",
        "location": "Hyderabad",
        "apply_url": "https://jobs.lever.co/keyloop/c2142ca2-378f-4868-b51d-a7819a1e4a9d/apply",
        "ats": "Lever",
    },
    {
        "company": "TTEC Digital",
        "title": "Principal Solution Architect - AWS",
        "location": "Hyderabad",
        "apply_url": "https://jobs.lever.co/ttecdigital/0f413199-2e41-4325-92f3-902a577d039c/apply",
        "ats": "Lever",
    },
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


def dismiss(page):
    for sel in ["#onetrust-accept-btn-handler", "button:has-text('Accept all')", "button:has-text('Accept')", "button:has-text('dismiss')"]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=600):
                loc.click(timeout=600)
        except Exception:
            pass


def fill_name(scope, name, value):
    loc = scope.locator(f"[name='{name}']").first
    if loc.count() == 0:
        return False
    try:
        tag = loc.evaluate("el => el.tagName.toLowerCase()")
        typ = (loc.get_attribute("type") or "").lower()
        if typ == "file":
            loc.set_input_files(RESUME)
            return True
        if typ in {"checkbox", "radio"}:
            return False
        if tag == "select":
            return False
        loc.fill(str(value), timeout=2500)
        return True
    except Exception:
        return False


def select_name(scope, name, label=None, value=None):
    loc = scope.locator(f"select[name='{name}']").first
    if loc.count() == 0:
        return False
    try:
        if label is not None:
            loc.select_option(label=label, timeout=2500)
        else:
            loc.select_option(value=str(value), timeout=2500)
        return True
    except Exception:
        try:
            if label is not None:
                loc.select_option(label=re.compile(re.escape(label), re.I), timeout=2500)
                return True
        except Exception:
            return False
    return False


def check_name(scope, name, value=None):
    sel = f"input[name='{name}']"
    if value is not None:
        sel += f"[value='{value}']"
    loc = scope.locator(sel).first
    if loc.count() == 0:
        return False
    try:
        loc.check(timeout=2000)
        return True
    except Exception:
        try:
            loc.click(timeout=2000)
            return True
        except Exception:
            return False


def answer_from_label(label: str, values: list) -> tuple[str | None, str | None]:
    """Return (option_label, option_value) for a GH question."""
    q = label.lower()
    labels = [(str(v.get("label")), str(v.get("value"))) for v in values or []]

    def find(*needles):
        for lab, val in labels:
            if any(n in lab.lower() for n in needles):
                return lab, val
        return None, None

    if "first name" in q:
        return C["firstName"], None
    if "last name" in q:
        return C["lastName"], None
    if q.strip() == "email":
        return C["email"], None
    if q.strip() == "phone":
        return C["phone"], None
    if "linkedin" in q:
        return C["linkedIn"], None
    if q.strip() == "website":
        return None, None
    if "legal first" in q:
        return C["firstName"], None
    if "legal last" in q:
        return C["lastName"], None
    if "city of residence" in q or "primary residence" in q or "home address" in q:
        return "Hyderabad, Telangana, India", None
    if "state of residence" in q:
        return find("telangana")
    if "current company" in q:
        return C["currentEmployer"], None
    if "current title" in q:
        return C["currentRole"], None
    if "total rewards" in q:
        return REWARDS, None
    if "non-competition" in q or "non competition" in q:
        return find("no")
    if "immigration" in q or "sponsorship" in q or "work permit" in q or "visa" in q:
        return find("no")
    if "legal right to work" in q:
        return find("yes")
    if "never worked for zscaler" in " ".join(lab.lower() for lab, _ in labels) or "previously worked for zscaler" in q or "currently work for" in q:
        return find("never")
    if "how did you learn" in q or "hear about" in q:
        return find("zscaler careers", "careers page", "company") or find("google")
    if "i agree" in " ".join(lab.lower() for lab, _ in labels) and ("confidential" in q or "privacy" in q):
        return find("i agree")
    if "procurement" in q or "government employee" in q:
        return find("no")
    if "on-call" in q:
        return find("yes")
    return None, None


def fill_greenhouse(page, key: str):
    data = QUESTIONS[key]
    for q in data["questions"]:
        label = q.get("label") or ""
        for field in q.get("fields") or []:
            name = field.get("name")
            ftype = field.get("type") or ""
            values = field.get("values") or []
            if not name:
                continue
            if name in {"first_name"}:
                fill_name(page, name, C["firstName"])
            elif name in {"last_name"}:
                fill_name(page, name, C["lastName"])
            elif name in {"email"}:
                fill_name(page, name, C["email"])
            elif name in {"phone"}:
                fill_name(page, name, C["phone"])
            elif name in {"resume"}:
                fill_name(page, name, RESUME)
            elif name in {"cover_letter", "resume_text", "cover_letter_text"}:
                continue
            elif ftype in {"multi_value_single_select", "multi_value_multi_select"}:
                opt_label, opt_value = answer_from_label(label, values)
                if opt_label is None:
                    continue
                if not select_name(page, name, label=opt_label, value=opt_value):
                    check_name(page, name, opt_value)
                    # also click visible label
                    try:
                        page.get_by_label(opt_label, exact=True).first.click(timeout=800)
                    except Exception:
                        try:
                            page.get_by_text(opt_label, exact=True).first.click(timeout=800)
                        except Exception:
                            pass
            else:
                text, _ = answer_from_label(label, values)
                if text:
                    fill_name(page, name, text)
    # consent checkboxes often unlabeled
    for box in page.locator("input[type='checkbox']").all():
        try:
            name = (box.get_attribute("name") or "").lower()
            if "consent" in name or "agree" in name or "privacy" in name:
                box.check()
        except Exception:
            pass


def click_near_question(page, question_substr: str, option: str):
    try:
        q = page.get_by_text(re.compile(question_substr, re.I)).first
        if q.count() == 0:
            return False
        container = q.locator("xpath=ancestor::*[self::div or self::fieldset or self::li][1]")
        opt = container.get_by_text(option, exact=True).first
        if opt.count():
            opt.click(timeout=1500)
            return True
    except Exception:
        pass
    return False


def fill_lever(page):
    page.locator("input[name='name']").fill(C["fullName"])
    page.locator("input[name='email']").fill(C["email"])
    try:
        page.locator("input[name='phone']").fill(C["phone"])
    except Exception:
        pass
    try:
        page.locator("input[name='org']").fill(C["currentEmployer"])
    except Exception:
        pass
    linkedin = page.locator("input[name='urls[LinkedIn]']")
    if linkedin.count():
        linkedin.fill(C["linkedIn"])
    for loc_sel in ["input[name='location']", "input[placeholder*='location' i]", "input[name*='location' i]"]:
        loc = page.locator(loc_sel).first
        if loc.count():
            try:
                loc.fill("Hyderabad, Telangana, India")
            except Exception:
                pass
    resume = page.locator("input[type='file']").first
    if resume.count():
        resume.set_input_files(RESUME)

    # Required yes/no style questions
    pairs = [
        (r"at least 18", "Yes"),
        (r"right to work|authorized to work|work eligibility|legally eligible", "Yes"),
        (r"visa|sponsorship|require.*support", "No"),
        (r"education|certification|bachelor|degree", "Yes"),
        (r"non-competition|non compete", "No"),
    ]
    for q, ans in pairs:
        click_near_question(page, q, ans)

    # Text questions by label
    text_answers = [
        (r"current location", "Hyderabad, Telangana, India"),
        (r"right to work document|document type", "Indian Passport"),
        (r"AI Tools|Claude|ChatGPT", "Yes. I use Claude and ChatGPT for architecture documentation, design exploration, and code-review assistance."),
        (r"expected.*salary|salary expectation|annual gross", "6500000 INR (65 LPA)"),
        (r"notice period", "Immediate"),
        (r"additional information|comments", REWARDS + " Targeting Madhapur / Gachibowli / Financial District."),
    ]
    for q, val in text_answers:
        try:
            lab = page.get_by_text(re.compile(q, re.I)).first
            if lab.count() == 0:
                continue
            box = lab.locator("xpath=following::input[1] | following::textarea[1]").first
            if box.count():
                typ = (box.get_attribute("type") or "").lower()
                if typ in {"file", "hidden", "checkbox", "radio", "url"}:
                    continue
                name = box.get_attribute("name") or ""
                if name.startswith("urls["):
                    continue
                box.fill(val, timeout=1500)
        except Exception:
            continue

    # Native / custom selects
    for sel in page.locator("select").all():
        try:
            html = sel.inner_html()
            name = (sel.get_attribute("name") or "") + " " + (sel.get_attribute("aria-label") or "")
            blob = (name + html).lower()
            if "india" in html.lower() and ("location" in blob or "country" in blob):
                sel.select_option(label=re.compile(r"india", re.I))
            elif "male" in html.lower() and "gender" in blob:
                sel.select_option(label=re.compile(r"^male$", re.I))
            elif "hyderabad" in html.lower():
                sel.select_option(label=re.compile(r"hyderabad", re.I))
        except Exception:
            pass

    # Pronouns optional
    try:
        page.get_by_text("He/him", exact=True).first.click(timeout=500)
    except Exception:
        pass


def submit(page):
    for sel in [
        "button:has-text('Submit application')",
        "button[type='submit']:has-text('Submit')",
        "input[type='submit']",
        "button:has-text('Submit')",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1500):
                loc.scroll_into_view_if_needed()
                loc.click()
                return True
        except Exception:
            continue
    return False


def is_success(page) -> bool:
    url = page.url.lower()
    if any(x in url for x in ("/thanks", "confirmation", "application-success", "submitted")):
        return True
    try:
        text = page.inner_text("body")
    except Exception:
        return False
    # Avoid matching resume upload "Success!"
    if re.search(r"thanks for (your )?appl|application (was |has been )?(submitted|received)|we have received your application|thank you for applying", text, re.I):
        return True
    if page.locator("h1, h2").filter(has_text=re.compile(r"thank you", re.I)).count():
        return True
    return False


def apply_one(page, job):
    slug = re.sub(r"[^a-z0-9]+", "-", f"r2-{job['company']}-{job['title']}".lower())[:70]
    page.goto(job["apply_url"], wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(1800)
    dismiss(page)
    if "Sorry, we couldn't find" in (page.inner_text("body")[:400]):
        return {"ok": False, "status": "CLOSED", "note": "Job posting closed"}

    # Inovalon/HighRadius company wrappers
    for sel in ["text=Apply for this Position", "text=Apply for this job", "a:has-text('Apply')"]:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=600):
                loc.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

    frames = [page] + page.frames
    target = page
    for fr in frames:
        try:
            if fr.locator("input[name='first_name'], input[name='name'], input[name='email']").count():
                target = fr
                break
        except Exception:
            continue

    if job["ats"] == "Greenhouse":
        fill_greenhouse(target, job["key"])
    else:
        fill_lever(target)

    before = shot(page, f"{slug}-before")
    clicked = submit(target)
    page.wait_for_timeout(4000)
    ok = is_success(page)
    after = shot(page, f"{slug}-after")
    body = ""
    try:
        body = page.inner_text("body")[:500]
    except Exception:
        pass
    return {
        "ok": ok,
        "status": "SUBMITTED" if ok else ("SUBMIT_CLICKED" if clicked else "FORM_INCOMPLETE"),
        "screenshot_before": before,
        "screenshot_after": after,
        "url": page.url,
        "confirmation": body,
    }


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1200})
        page = context.new_page()
        for job in JOBS:
            print(f"\n-> {job['company']}: {job['title']}", flush=True)
            try:
                result = apply_one(page, job)
            except Exception as e:
                result = {"ok": False, "status": "ERROR", "note": str(e)[:400]}
            row = {**job, **result}
            results.append(row)
            log({"event": "browser_apply2", **row})
            print(f"   {row.get('status')} ok={row.get('ok')} {row.get('note','')}", flush=True)
        browser.close()
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nVerified", sum(1 for r in results if r.get("ok")), "/", len(results))


if __name__ == "__main__":
    main()
