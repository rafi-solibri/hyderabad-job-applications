"""Headed apply for the open discovery batch. Greenhouse first, then Lever."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import firefox_real
import form_memory
import tailor_resume
from sel_page import SelPage

ROOT = Path(__file__).resolve().parent
C = json.loads((ROOT / "data" / "candidate.json").read_text(encoding="utf-8"))
RESUME = str((ROOT / C["resumePath"]).resolve())
DISCOVERY_FILES = [
    ROOT / "data" / "discovery_final.json",
    ROOT / "data" / "discovery_batch.json",
    ROOT / "data" / "discovery_all_matched.json",
    ROOT / "data" / "location_only_jobs.json",
    ROOT / "data" / "all_hub_jobs.json",
    ROOT / "data" / "senior_hub_jobs.json",
    ROOT / "data" / "discovered_jobs.json",
    ROOT / "data" / "hyd_jobs.json",
    ROOT / "data" / "more_jobs.json",
]
BATCH: list[dict] = []
LEARNED = json.loads((ROOT / "data" / "learned_answers.json").read_text(encoding="utf-8"))
QUESTIONS = {}
_qpath = ROOT / "data" / "remaining_questions.json"
if _qpath.exists():
    QUESTIONS = json.loads(_qpath.read_text(encoding="utf-8"))
RESULTS = ROOT / "data" / "applications" / "apply_now_results.json"
LOG = ROOT / "data" / "applications" / "log.jsonl"
WAIT_SECONDS = 600
REWARDS = LEARNED["totalRewards"]
MAX_PER_COMPANY = 3
SKIP_COMPANIES = {
    "pega", "salesforce", "servicenow",
    "ttecdigital", "ttec",
    "spectralconsultants",
    "amazonfilters", "amazonrailings", "amazonwood",
}
BLOCKED_PATH = ROOT / "data" / "blocked_companies.json"
SKIP_IDS = {
    "8074590", "7985640", "7517648003", "7490280003", "7807746003", "5177393007",
    "7807811003", "7807736003", "4129751009", "7522392003", "7676828003", "4243672009",
    "8026651", "7707598003", "7820052003", "7687216003", "7990093", "7551943003",
    "4052876009", "7702188003", "8026531", "6529471003", "5177391007",
    "c2142ca2-378f-4868-b51d-a7819a1e4a9d",
    "fba5b3ae-3033-4386-9e47-849afcfb80c9",
    "46f13005-0ccd-48de-ac16-507d6bb0272e",
    "f40228f0-6806-4ecc-8e92-3e2a89741120",
    "7644471",  # Twilio Principal SWE
    "7825552003",  # Zenoti Lead Full Stack
    "7996776",  # Twilio Principal L5
    "8627761002",  # GitLab Solutions Architect
    "8631175002",  # GitLab Threat Intelligence
    "7825089",  # Twilio Software Architect L6
    "8530855002",  # Databricks Staff FDE
    "8514960002",  # GitLab Staff Infrastructure Security
    "7966928",  # Twilio Tech Lead / Sr Principal L6
    "8054153",  # Coinbase Staff SWE Customer Admin — leftovers never completed
    "JR85571",  # Micron Product Engineering — no Submit / leftover
    "JR84932",  # Micron NAND FA — hardware FA, not software
    "R025606-3",  # Broadcom Senior Software Architect — user submitted
    "Senior-Software-Architect_R025606-3",
    "10403400",  # Amazon Principal SWE DEX — confirmation in amazon_results.json
    "10486766",  # Amazon Principal SWE Shipping
    "10488478",  # Amazon Senior SDE AZA
    "10486367",  # Amazon Senior SDE AZA
    "10484739",  # Amazon Senior SDE Global Logistics
    "7996770",  # Twilio Staff L4 — company already 4/4; leftover, not a new apply
    "8007449",  # Twilio Senior/Staff Applied Research — company already 4/4
    "Principal-Software-Engineer_R69840",  # Medtronic Principal SWE — already applied
    "R69840",
    "Principal-Solution-Architect_R-216344",  # Amgen PSA — Workday already applied
    "R-216344",
    "Principal-Solution-Architect_R-216678",  # Amgen PSA — submitted 19 Aug
    "R-216678",
    "7741187",  # Coinbase EM Customer Experience AI — user submitted
    "Software-Engineering-Mgr_R71759-1",  # Medtronic SEM — applied 18 Aug
    "R71759-1",
    "Software-Engineering-Mgr_R71760-1",  # Medtronic SEM — applied 18 Aug
    "R71760-1",
    "Specialist-Technical-Architect_R-234472",  # Amgen Specialist TA — Application Received
    "R-234472",
    "6001255004",  # ClickHouse Principal SWE Postgres — user applied
    "7775223003",  # Sezzle Senior SWE India — user applied
    "93a8f528-ea6d-4554-a73b-e9fb736a3a6c",  # TTEC Genesys Principal Implementation Consultant
    "5989606004",  # ClickHouse Senior SWE Postgres — user applied
    "7818352003",  # Fivetran Staff SWE dbt core — user applied
    "Senior-Hyperautomation-Solution-Architect_R58263-1",  # RPA / hyperautomation — skip
    "R58263-1",
}

APPLIED_PATH = ROOT / "data" / "applied_ids.json"


def log(event):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def quiet_click(locator, timeout=1500):
    try:
        locator.click(timeout=timeout)
        return True
    except Exception:
        return False


VERIFY_ERROR_RE = re.compile(
    r"error verifying|there was an error|unable to (submit|verify)|"
    r"application could not be|something went wrong submitting|please try again",
    re.I,
)


def load_blocked() -> set[str]:
    blocked = set(SKIP_COMPANIES)
    if BLOCKED_PATH.exists():
        try:
            blocked.update(company_key(x) for x in json.loads(BLOCKED_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return blocked


def block_company(name: str) -> None:
    key = company_key(name)
    blocked = load_blocked()
    blocked.add(key)
    BLOCKED_PATH.parent.mkdir(parents=True, exist_ok=True)
    BLOCKED_PATH.write_text(json.dumps(sorted(blocked), indent=2), encoding="utf-8")
    print(f"  Skipping {name}: form shows an error after fill. Rest of this company skipped.", flush=True)


def is_verify_error(page) -> bool:
    try:
        text = page.inner_text("body")
        if "error verifying" in text.lower():
            return True
        return bool(re.search(r"there was an error verifying your application", text, re.I))
    except Exception:
        return False


def is_success(page) -> bool:
    try:
        url = page.url.lower()
        if any(x in url for x in ("/thanks", "confirmation", "submitted", "application-success")):
            return True
        text = page.inner_text("body")
        if "error verifying" in text.lower():
            return False
        return bool(re.search(
            r"thanks for (your )?appl|application (was |has been )?(submitted|received)|thank you for applying|"
            r"we.?ve received your application|application received|already applied|you previously applied|"
            r"successfully submitted|we submitted your application|applied with simplify|application submitted",
            text, re.I,
        ))
    except Exception:
        return False


WORKDAY_SITES = {
    "micron": "https://micron.wd1.myworkdayjobs.com/en-US/External",
    "nvidia": "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite",
    "qualcomm": "https://qualcomm.wd5.myworkdayjobs.com/en-US/External",
    "amd": "https://amd.wd1.myworkdayjobs.com/en-US/careers",
    "intel": "https://intel.wd1.myworkdayjobs.com/en-US/external",
    "cisco": "https://cisco.wd5.myworkdayjobs.com/en-US/cisco_careers",
    "dell": "https://dell.wd1.myworkdayjobs.com/en-US/External",
    "adp": "https://adp.wd5.myworkdayjobs.com/en-US/External",
    "optum": "https://optum.wd5.myworkdayjobs.com/en-US/OptumCareers",
    "walmart": "https://walmart.wd5.myworkdayjobs.com/en-US/WalmartExternal",
    "jpmorgan": "https://jpmorgan.wd5.myworkdayjobs.com/en-US/jpmcjobs",
    "wellsfargo": "https://wellsfargo.wd5.myworkdayjobs.com/en-US/External",
    "honeywell": "https://honeywell.wd1.myworkdayjobs.com/en-US/External",
    "siemens": "https://siemens.wd3.myworkdayjobs.com/en-US/External",
    "philips": "https://philips.wd3.myworkdayjobs.com/en-US/jobs-and-careers",
}


def apply_url(job: dict) -> str:
    ats = job.get("ats")
    company = (job.get("company") or "").lower()
    jid = str(job.get("job_id") or "")
    url = job.get("url") or ""
    if ats == "Greenhouse" and jid:
        if company in {"highradius", "inovalon"}:
            return f"https://boards.greenhouse.io/embed/job_app?for={company}&token={jid}"
        return f"https://job-boards.greenhouse.io/{company}/jobs/{jid}"
    if ats == "Lever" and jid and company:
        return f"https://jobs.lever.co/{company}/{jid}/apply"
    if ats == "Amazon" and jid:
        return f"https://account.amazon.jobs/en-US/applicant/jobs/{jid}/apply"
    if ats == "SmartRecruiters" and jid:
        slug = job.get("company") or company
        return f"https://jobs.smartrecruiters.com/{slug}/{jid}"
    if ats == "Workday":
        if url.startswith("http"):
            return url
        base = WORKDAY_SITES.get(company)
        if base and url.startswith("/"):
            return base.rstrip("/") + url
    return url


def reload_learned():
    global LEARNED, REWARDS
    LEARNED = form_memory.load_learned() or LEARNED
    REWARDS = LEARNED.get("totalRewards", REWARDS)
    return LEARNED


def answer_for_label(label: str, values: list) -> str | None:
    remembered = form_memory.lookup(label)
    if remembered:
        return remembered
    q = (label or "").lower()
    L = LEARNED
    labels = [str(v.get("label")) for v in values or [] if isinstance(v, dict)]

    def pick(*needles):
        for lab in labels:
            if any(n in lab.lower() for n in needles):
                return lab
        return None

    if "preferred first" in q:
        return L["preferredFirstName"]
    if "legal first" in q or q.strip() == "first name":
        return L["legalFirstName"]
    if "legal last" in q or q.strip() == "last name":
        return L["legalLastName"]
    if "notice" in q:
        return L["noticePeriod"]
    if "start date" in q:
        return L["desiredStartDate"]
    if "desired annual salary" in q or "salary" in q or "reward" in q or "compensation" in q:
        return L["desiredAnnualSalary"] if "desired" in q or "salary" in q else L["totalRewards"]
    if "linkedin" in q:
        return L["linkedin"]
    if "current company" in q:
        return L["currentCompany"]
    if "current title" in q:
        return L["currentTitle"]
    if "city of residence" in q:
        return L["cityOfResidence"]
    if "state of residence" in q:
        return pick("telangana") or L["stateOfResidence"]
    if "home address" in q or "city, state" in q or "current city" in q or "primary residence" in q:
        return L["currentCityStateCountry"]
    if "additional information" in q:
        return L["additionalInfo"]
    if "non-competition" in q or "non-compete" in q:
        return pick("no") or "No"
    if "onsite" in q and "three days" in q:
        return pick("yes") or "Yes"
    if "on-call" in q:
        return pick("yes") or "Yes"
    if "legally permitted" in q or "legal right to work" in q:
        return pick("yes") or "Yes"
    if "most accurately fits your situation" in q or "authorized to work permanently" in q:
        return pick("permanently", "authorized to work permanently")
    if "visa" in q or "sponsorship" in q or "immigration" in q or "work permit" in q:
        return pick("no") or "No"
    if "how did you learn" in q:
        return pick("zscaler careers", "careers page") or pick("google")
    if "never worked for zscaler" in " ".join(labels).lower() or "previously worked for zscaler" in q:
        return pick("never")
    if "i agree" in " ".join(labels).lower() and ("confidential" in q or "privacy" in q):
        return pick("i agree")
    if "procurement" in q or "government employee" in q:
        return pick("no") or "No"
    return None


def set_india_phone(page):
    """Set India + 8790251698 once. Do not touch the field if it is already correct."""
    try:
        page.evaluate(
            """() => {
              const phone = document.querySelector("#phone, input[type=tel], input[name='phone']");
              const digits = (phone && phone.value || "").replace(/\\D/g, "");
              const alreadyIn = !!document.querySelector(
                ".iti__selected-flag[title*='India'], .iti__flag.iti__in, [data-country-code='in'].iti__active, [aria-label*='India']"
              );
              if (alreadyIn && (digits === "8790251698" || digits.endsWith("8790251698"))) {
                if (phone) phone.blur();
                return;
              }
              const flag = document.querySelector(".iti__selected-flag, button[aria-label='Select country']");
              if (flag && !alreadyIn) flag.click();
              const india = document.querySelector("li.iti__country[data-country-code='in']");
              if (india) { india.scrollIntoView(); india.click(); }
              if (phone && digits !== "8790251698") {
                phone.value = "8790251698";
                phone.dispatchEvent(new Event("input", {bubbles: true}));
                phone.dispatchEvent(new Event("change", {bubbles: true}));
              }
              if (phone) phone.blur();
            }"""
        )
    except Exception:
        pass


def fill_named(page, name: str, value: str, ftype: str, values: list):
    if not name or value is None:
        return
    try:
        loc = page.locator(f"#{name}, [name='{name}']").first
        if loc.count():
            cur = (loc.input_value() or "").strip()
            if cur and cur.lower() not in {"select", "select...", "choose"}:
                return
    except Exception:
        pass
    if ftype in {"multi_value_single_select", "multi_value_multi_select"}:
        try:
            sel = page.locator(f"select[name='{name}'], select#{name}").first
            if sel.count():
                sel.select_option(label=value, timeout=1500)
                return
        except Exception:
            pass
        box = page.locator(f"#{name}, input[name='{name}']").first
        quiet_click(box, 800)
        page.wait_for_timeout(200)
        quiet_click(page.locator("[role=option], li").filter(has_text=re.compile(rf"^{re.escape(value)}$", re.I)).first, 1500)
        if "agree" in value.lower():
            quiet_click(page.get_by_text(value, exact=True).first, 600)
        return
    try:
        page.locator(f"#{name}").fill(str(value), timeout=1500)
    except Exception:
        try:
            page.locator(f"[name='{name}']").first.fill(str(value), timeout=1500)
        except Exception:
            pass


def fill_greenhouse(page, job=None):
    reload_learned()
    for eid, value in (("first_name", C["firstName"]), ("last_name", C["lastName"]), ("email", C["email"])):
        try:
            loc = page.locator(f"#{eid}").first
            if loc.count() and not (loc.input_value() or "").strip():
                loc.fill(value, timeout=2000)
        except Exception:
            pass
    set_india_phone(page)
    tailor_resume.upload(page, (job or {}).get("resume_path") or tailor_resume.CURRENT.get("path") or RESUME)

    key = f"{(job or {}).get('company')}:{(job or {}).get('job_id')}"
    spec = QUESTIONS.get(key) or {}
    for q in spec.get("questions") or []:
        label = q.get("label") or ""
        for field in q.get("fields") or []:
            name = field.get("name") or ""
            ftype = field.get("type") or ""
            values = field.get("values") or []
            if name in {"first_name", "last_name", "email", "phone", "resume", "cover_letter", "resume_text", "cover_letter_text"}:
                continue
            value = answer_for_label(label, values)
            if value:
                fill_named(page, name, value, ftype, values)

    for loc in page.locator("input[id^='question_'], textarea[id^='question_']").all():
        try:
            if not loc.is_visible():
                continue
            if loc.input_value():
                continue
            aria = (loc.get_attribute("aria-label") or "").lower()
            value = answer_for_label(aria, [])
            if value:
                loc.fill(value, timeout=1200)
        except Exception:
            continue
    for q, ans in (
        (r"non-competition|non-compete", "No"),
        (r"immigration|sponsorship|work permit|visa", "No"),
        (r"legally permitted|legal right to work", "Yes"),
        (r"authorized to work permanently|most accurately fits", "I am authorized to work permanently in the country"),
        (r"onsite.*three days", "Yes"),
        (r"worked for Zscaler", "No, I have never worked for Zscaler"),
        (r"how did you learn", "Zscaler Careers Page"),
        (r"on-call", "Yes"),
        (r"State of Residence", "Telangana"),
        (r"notice period", LEARNED["noticePeriod"]),
        (r"procurement or contract", "No"),
    ):
        try:
            label = page.get_by_text(re.compile(q, re.I)).first
            if label.count() == 0:
                continue
            quiet_click(label.locator("xpath=following::input[1]"), 1000)
            page.wait_for_timeout(200)
            quiet_click(
                page.locator("[role=option], li").filter(has_text=re.compile(re.escape(ans), re.I)).first,
                1500,
            )
        except Exception:
            pass
    for t in ("I Agree", "I agree"):
        quiet_click(page.get_by_text(t, exact=True).first, 400)


def fill_lever(page):
    for sel in ("button:has-text('dismiss')", "button:has-text('Accept')", "#onetrust-accept-btn-handler"):
        quiet_click(page.locator(sel).first, 500)
    for name, value in (
        ("name", C["fullName"]),
        ("email", C["email"]),
        ("phone", "8790251698"),
        ("org", C["currentEmployer"]),
        ("urls[LinkedIn]", C["linkedIn"]),
    ):
        try:
            loc = page.locator(f"input[name='{name}']").first
            if loc.count() and not (loc.input_value() or "").strip():
                loc.fill(value, timeout=1500)
        except Exception:
            pass
    try:
        loc = page.locator("#location-input")
        if loc.count():
            loc.fill("Hyderabad, India", timeout=1500)
            page.wait_for_timeout(700)
            page.keyboard.press("Enter")
    except Exception:
        pass
    tailor_resume.upload(page, tailor_resume.CURRENT.get("path") or RESUME)
    set_india_phone(page)
    for q, ans in (
        (r"at least 18", "Yes"),
        (r"authorized to work|right to work|eligibility to work", "Yes"),
        (r"education|certification|bachelor", "Yes"),
        (r"visa|sponsorship", "No"),
    ):
        try:
            heading = page.get_by_text(re.compile(q, re.I)).first
            quiet_click(
                heading.locator("xpath=ancestor::*[self::li or self::div][1]").get_by_text(ans, exact=True).first,
                1000,
            )
        except Exception:
            pass


def company_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def load_applied_ids() -> dict:
    if not APPLIED_PATH.exists():
        return {}
    try:
        data = json.loads(APPLIED_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def job_match_keys(job: dict) -> set[str]:
    """All ids that should mark this posting as already applied."""
    keys: set[str] = set()
    jid = str(job.get("job_id") or "").strip()
    if jid:
        keys.add(jid)
        tail = jid.split("_")[-1]
        if tail:
            keys.add(tail)
    for url in (job.get("url"), job.get("apply_url"), job.get("final_url")):
        if not url:
            continue
        text = str(url)
        for m in re.finditer(r"(?:jobs/|token=|gh_jid=|jid=|/job/)(\d{6,}|[a-f0-9-]{20,})", text, re.I):
            keys.add(m.group(1))
        for m in re.finditer(r"(R-?\d{4,}(?:-\d+)?)", text):
            keys.add(m.group(1))
    ck = company_key(job.get("company"))
    title = re.sub(r"\s+", " ", (job.get("title") or "").strip().lower())
    if ck and title:
        keys.add(f"{ck}|{title}")
    return {k for k in keys if k}


def is_applied(job: dict) -> bool:
    if job.get("already_applied"):
        return True
    skipped = set(SKIP_IDS) | set(load_applied_ids())
    return bool(job_match_keys(job) & skipped)


def _write_applied_store(store: dict) -> None:
    APPLIED_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPLIED_PATH.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def persist_applied(job: dict, note: str = "") -> dict:
    """Record a submitted job so discovery and the queue never reopen it."""
    jid = str(job.get("job_id") or "")
    meta = {
        "company": job.get("company"),
        "title": job.get("title"),
        "job_id": jid,
        "url": job.get("url") or job.get("apply_url") or job.get("final_url") or "",
        "note": note or job.get("note") or "submitted",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    store = load_applied_ids()
    for key in job_match_keys(job) or ({jid} if jid else set()):
        SKIP_IDS.add(key)
        store[key] = meta
    if store:
        _write_applied_store(store)
    row = {
        **{k: job.get(k) for k in ("company", "title", "location", "url", "ats", "job_id", "apply_url")},
        "ok": True,
        "status": "SUBMITTED",
        "note": note or "submitted",
        "final_url": job.get("final_url") or job.get("url") or "",
    }
    save_results([row])
    log({"event": "apply_now", **{k: v for k, v in row.items() if k != "confirmation"}})
    return row


_APPLIED_SYNCED = False


def sync_applied_store() -> dict:
    """Fill applied_ids.json from SKIP_IDS, result files, and the apply log."""
    global _APPLIED_SYNCED
    store = load_applied_ids()
    if _APPLIED_SYNCED and store:
        return store
    lookup: dict[str, dict] = {}
    for path in DISCOVERY_FILES:
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for job in rows:
            if isinstance(job, dict):
                for key in job_match_keys(job):
                    lookup[key] = job

    def put(job: dict, note: str) -> None:
        meta = {
            "company": job.get("company"),
            "title": job.get("title"),
            "job_id": str(job.get("job_id") or ""),
            "url": job.get("url") or job.get("apply_url") or job.get("final_url") or "",
            "note": note,
            "ts": job.get("ts") or datetime.now(timezone.utc).isoformat(),
        }
        for key in job_match_keys(job):
            SKIP_IDS.add(key)
            store.setdefault(key, meta)

    for jid in list(SKIP_IDS):
        put(lookup.get(jid) or {"job_id": jid}, "backfill from skip list")
    result_files = [
        RESULTS,
        ROOT / "data" / "applications" / "headed_results.json",
        ROOT / "data" / "applications" / "amazon_results.json",
        ROOT / "data" / "applications" / "browser_results.json",
        ROOT / "data" / "applications" / "browser_results2.json",
        ROOT / "data" / "applications" / "browser_results3.json",
        ROOT / "data" / "applications" / "browser_results5.json",
    ]
    for path in result_files:
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if _applied_job_id(row) or str(row.get("status") or "") == "SUBMITTED" or row.get("ok"):
                put(row, str(row.get("note") or row.get("status") or "submitted"))
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if _applied_job_id(row) or str(row.get("status") or "") == "SUBMITTED" or row.get("ok"):
                put(row, str(row.get("note") or "log"))
    _write_applied_store(store)
    _APPLIED_SYNCED = True
    return store


def submitted_by_company() -> dict[str, set[str]]:
    counts: dict[str, set[str]] = {}

    def add_count(company: str, job: dict, jid: str = "") -> None:
        ck = company_key(company)
        if not ck:
            return
        title = re.sub(r"\s+", " ", (job.get("title") or "").strip().lower())
        primary = str(job.get("job_id") or jid or "").strip()
        if "|" in primary:
            primary = ""
        key = f"{ck}|{title}" if title else primary
        if key:
            counts.setdefault(ck, set()).add(key)

    for jid, meta in load_applied_ids().items():
        if not isinstance(meta, dict):
            continue
        if "|" in str(jid) and not (meta.get("job_id") or meta.get("title")):
            continue
        add_count(meta.get("company"), meta, str(meta.get("job_id") or jid))
    result_files = [
        RESULTS,
        ROOT / "data" / "applications" / "headed_results.json",
        ROOT / "data" / "applications" / "amazon_results.json",
        ROOT / "data" / "applications" / "browser_results.json",
        ROOT / "data" / "applications" / "browser_results2.json",
        ROOT / "data" / "applications" / "browser_results3.json",
        ROOT / "data" / "applications" / "browser_results5.json",
    ]
    for path in result_files:
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            jid = _applied_job_id(row)
            if jid:
                add_count(row.get("company"), row, jid)
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            jid = _applied_job_id(row)
            if jid:
                add_count(row.get("company"), row, jid)
    return counts


def _applied_job_id(row: dict) -> str:
    url = str(row.get("final_url") or row.get("url") or row.get("apply_url") or "")
    confirmed = bool(
        row.get("ok")
        or row.get("status") == "SUBMITTED"
        or "confirmation" in url.lower()
        or "already applied" in str(row.get("status") or "").lower()
    )
    if not confirmed:
        return ""
    jid = str(row.get("job_id") or "")
    if jid:
        return jid
    m = re.search(r"(?:jobs/|token=|gh_jid=)(\d{6,}|[a-f0-9-]{20,})", url)
    return m.group(1) if m else ""


def save_results(rows: list[dict]) -> None:
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


def load_all_discovered() -> list[dict]:
    """Use every saved discovery file, not only the last overwritten batch."""
    seen: set[tuple[str, str]] = set()
    jobs: list[dict] = []
    for path in DISCOVERY_FILES:
        if not path.exists():
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for job in rows:
            jid = str(job.get("job_id") or "")
            key = (
                company_key(job.get("company")),
                jid or str(job.get("url") or job.get("apply_url") or "")[:80],
            )
            if not key[1] or key in seen:
                continue
            seen.add(key)
            jobs.append(job)
    return jobs


def queue() -> list[dict]:
    sync_applied_store()
    used = submitted_by_company()
    skipped_ids = set(SKIP_IDS)
    skipped_ids.update(load_applied_ids())
    for ids in used.values():
        skipped_ids.update(ids)
    jobs = []
    planned: dict[str, int] = {}
    for job in BATCH:
        jid = str(job.get("job_id") or "")
        company = company_key(job.get("company"))
        if is_applied(job) or jid in skipped_ids:
            continue
        if company in load_blocked():
            continue
        title = (job.get("title") or "").lower()
        if re.search(
            r"devops|devsecops|site reliability|\bsre\b|sales engineer|"
            r"customer engineering|it automation|machine learning|\bmlops\b|"
            r"layout|embedded|pcie|firmware|rtl |asic |verification engineer|"
            r"structural modeling|process modeling|hbm layout|\bnand\b|"
            r"product engineering|failure analysis|\bfa\b|physical design|"
            r"synthesis|tech ops|rack manufacturing|\bai engineer\b|\bssd\b|\bnvm|"
            r"hyperautomation|\brpa\b|uipath|automation anywhere|"
            r"machine learning|\bandroid\b|\bios\b|data engineering|"
            r"\bjava\b|spring boot|d365|dynamics 365|\bappian\b|drupal|"
            r"bangkok|gurugram based|relocation provided|"
            r"civil \(|uk water|linux kernel|device driver|"
            r"\baem\b|\bboomi\b",
            title,
        ):
            continue
        if not re.search(
            r"architect|principal|staff|technical lead|engineering manager|"
            r"lead (software|engineer|developer)|senior (software|backend|full.?stack|\.net|sde|solution)|"
            r"sde ?[iii23]|software development engineer|sr\.? software|"
            r"manager,? software development|senior manager software|sr\.? manager software",
            title,
        ):
            continue
        loc = job.get("location") or ""
        if re.search(r"bangalore|bengaluru|pune|chennai|delhi|noida|gurgaon|gurugram", loc, re.I):
            if not re.search(r"hyderabad|telangana", loc, re.I):
                continue
        if not re.search(r"hyderabad|telangana", loc, re.I):
            if not (re.search(r"remote|wfh|work from home", loc, re.I) and re.search(r"\bindia\b", loc, re.I)):
                continue
        row = dict(job)
        row["apply_url"] = apply_url(job)
        row["match_score"] = match_score(row)
        jobs.append(row)
    return pick_best_per_company(jobs, used)


def match_score(job: dict) -> int:
    """Higher = closer to Rafi's architect / .NET / cloud / lead profile."""
    title = (job.get("title") or "").lower()
    loc = (job.get("location") or "").lower()
    ats = (job.get("ats") or "")
    score = 10
    if re.search(r"\.net|dotnet|c#|azure", title):
        score += 40
    if re.search(r"technical architect|solution.?s? architect|software architect|cloud architect|application architect|backend architect|full.?stack architect", title):
        score += 36
    elif re.search(r"principal (software |tech )?(engineer|architect)|principal swe|principal sde", title):
        score += 30
    elif re.search(r"senior staff|staff (software )?engineer|staff swe|staff sde", title):
        score += 22
    elif re.search(r"technical lead|engineering manager|lead software|lead (engineer|developer)", title):
        score += 20
    elif re.search(r"senior (software|backend|full.?stack|\.net|sde)|sde ?[iii3]|sr\.? software", title):
        score += 8
    if re.search(r"microservices|distributed|kafka|aws|azure|cloud|architect", title):
        score += 8
    if re.search(r"hyderabad|telangana|gachibowli|madhapur|nanakramguda|hitec|hitech", loc):
        score += 16
    elif re.search(r"remote", loc) and re.search(r"india", loc):
        score += 10
    if ats in {"Workday", "Greenhouse", "Lever", "Ashby", "Amazon"}:
        score += 10
    elif ats in {"Foundit", "Indeed", "Naukri"}:
        score -= 6
    if re.search(r"python|frontend|front end|security architect|quality|hvac|electrical|civil|oracle fusion|wms|verification", title):
        score -= 20
    if re.search(r"ai solution|gen ai|machine learning|data engineer", title):
        score -= 16
    return score


def pick_best_per_company(jobs: list[dict], used: dict[str, set] | None = None) -> list[dict]:
    """Keep only the best leftover slots per company (cap minus already applied)."""
    used = used or {}
    jobs = sorted(jobs, key=lambda j: (-int(j.get("match_score") or match_score(j)), j.get("title") or ""))
    planned: dict[str, int] = {}
    seen_titles: set[str] = set()
    chosen: list[dict] = []
    for job in jobs:
        company = company_key(job.get("company"))
        title_key = company + "|" + re.sub(r"\s+", " ", (job.get("title") or "").strip().lower())
        if title_key in seen_titles:
            continue
        room = MAX_PER_COMPANY - len(used.get(company, set())) - planned.get(company, 0)
        if room <= 0:
            continue
        seen_titles.add(title_key)
        chosen.append(job)
        planned[company] = planned.get(company, 0) + 1
    chosen.sort(key=lambda j: (-int(j.get("match_score") or 0), j.get("company") or "", j.get("title") or ""))
    return chosen


def main():
    global BATCH
    BATCH = load_all_discovered()
    form_memory.seed_from_learned()
    jobs = queue()[:1]
    if not jobs:
        print("No leftover target jobs to open.", flush=True)
        return
    used = submitted_by_company()
    print(f"Applying {len(jobs)} jobs in Firefox profile rafi.success@gmail.com + Simplify Copilot.", flush=True)
    print("This profile is used for every application.", flush=True)
    for company, ids in sorted(used.items()):
        print(f"  already {company}: {len(ids)}/{MAX_PER_COMPANY}", flush=True)
    results = []
    blocked = load_blocked()
    driver = firefox_real.launch_driver()
    page = SelPage(driver)
    try:
        for i, job in enumerate(jobs, 1):
            company = company_key(job.get("company"))
            if company in blocked:
                print(f"\n[{i}/{len(jobs)}] {job['company']}: {job['title']}", flush=True)
                print("  SKIPPED: company blocked after a submit error.", flush=True)
                continue
            print(f"\n[{i}/{len(jobs)}] {job['company']}: {job['title']}", flush=True)
            try:
                try:
                    job["resume_path"] = tailor_resume.for_job(job)
                    print(f"  Tailored resume: {job['resume_path']}", flush=True)
                    print(f"  Headline: {tailor_resume.CURRENT.get('headline')}", flush=True)
                except Exception as exc:
                    job["resume_path"] = RESUME
                    print(f"  Resume tailor failed ({exc}); using master resume.", flush=True)
                firefox_real.open_new_tab(page, job["apply_url"])
                page.wait_for_timeout(1400)
                page.bring_to_front()
                firefox_real.click_apply_now(page)
                firefox_real.focus_apply_tab(page)
                for _ in range(5):
                    if firefox_real.click_start_gate(page):
                        break
                    page.wait_for_timeout(1200)
                body = page.inner_text("body")[:400].lower()
                if "couldn't find" in body or "404" in page.title().lower():
                    row = {**job, "ok": False, "status": "CLOSED"}
                elif re.search(r"already applied|you previously applied|application already", body):
                    print("  SKIPPED: already applied.", flush=True)
                    row = {**job, "ok": True, "status": "SUBMITTED", "note": "already applied"}
                else:
                    firefox_real.watch_copilot(page)
                    firefox_real.trigger_simplify(page)
                    print("  Copilot Autofill this page ran once. Filling leftover empties from profile and memory once.", flush=True)
                    page.wait_for_timeout(4000)
                    if job["ats"] == "Greenhouse":
                        fill_greenhouse(page, job)
                    elif job["ats"] == "Lever":
                        fill_lever(page)
                    tailor_resume.upload(page, job.get("resume_path"))
                    form_memory.fill_visible(page)
                    form_memory.remember(page, job)
                    submitted = False
                    for _ in range(5):
                        firefox_real.watch_copilot(page)
                        if is_success(page) or firefox_real.copilot_says_submitted(page):
                            submitted = True
                            break
                        step = firefox_real.follow_copilot(page)
                        if step == "submitted":
                            submitted = True
                            break
                        if step == "clicked":
                            form_memory.fill_visible(page)
                            form_memory.remember(page, job)
                            continue
                        break
                    empty = firefox_real.empty_required_count(page)
                    if empty and not submitted:
                        print(
                            f"  {empty} required field(s) still empty. Fill those yourself. I will stay on this page until you submit.",
                            flush=True,
                        )
                    if is_verify_error(page):
                        block_company(job["company"])
                        blocked.add(company)
                        row = {**job, "ok": False, "status": "VERIFY_ERROR", "final_url": page.url}
                    elif submitted or is_success(page) or firefox_real.copilot_says_submitted(page):
                        print("  Submitted. Moving to the next job now.", flush=True)
                        row = {**job, "ok": True, "status": "SUBMITTED", "final_url": page.url}
                    else:
                        if empty == 0 and firefox_real.click_submit(page):
                            print("  Submit clicked once. I will not click it again.", flush=True)
                        if is_success(page) or firefox_real.copilot_says_submitted(page):
                            print("  Submitted. Moving to the next job now.", flush=True)
                            row = {**job, "ok": True, "status": "SUBMITTED", "final_url": page.url}
                        elif is_verify_error(page):
                            form_memory.remember(page, job)
                            block_company(job["company"])
                            blocked.add(company)
                            row = {**job, "ok": False, "status": "VERIFY_ERROR", "final_url": page.url}
                        else:
                            print(
                                f"  Waiting up to {WAIT_SECONDS}s for you to submit. I will not leave this application.",
                                flush=True,
                            )
                            deadline = time.time() + WAIT_SECONDS
                            ok = False
                            while time.time() < deadline:
                                firefox_real.watch_copilot(page)
                                if is_success(page) or firefox_real.copilot_says_submitted(page):
                                    ok = True
                                    break
                                if firefox_real.follow_copilot(page) == "submitted":
                                    ok = True
                                    break
                                if is_verify_error(page):
                                    break
                                form_memory.remember(page, job)
                                page.wait_for_timeout(2000)
                            form_memory.remember(page, job)
                            if ok:
                                print("  Submitted. Moving to the next job now.", flush=True)
                            else:
                                print("  Still no submit confirmation. Staying on this page; not opening the next job.", flush=True)
                            row = {**job, "ok": ok, "status": "SUBMITTED" if ok else "WAITING_EXPIRED", "final_url": page.url}
                            if not ok:
                                break
            except Exception as e:
                row = {**job, "ok": False, "status": "ERROR", "note": str(e)[:300]}
            results.append(row)
            if row.get("ok") and str(row.get("status") or "") == "SUBMITTED":
                persist_applied(row, row.get("note") or "apply_now submitted")
            else:
                log({"event": "apply_now", **{k: v for k, v in row.items() if k != "confirmation"}})
                save_results(results)
            print(f"  {row.get('status')} ok={row.get('ok')}", flush=True)
    finally:
        print("  Firefox is still open with your profile. I will not close it.", flush=True)
    submitted = sum(1 for r in results if r.get("ok"))
    print(f"\nDone. Submitted {submitted} / {len(results)}", flush=True)


if __name__ == "__main__":
    main()
