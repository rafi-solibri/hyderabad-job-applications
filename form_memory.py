"""Learn answers from forms and fill later applications with profile + memory."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MEMORY_PATH = ROOT / "data" / "field_memory.json"
LEARNED_PATH = ROOT / "data" / "learned_answers.json"
CANDIDATE_PATH = ROOT / "data" / "candidate.json"

SKIP_STORE_LABELS = re.compile(
    r"password|captcha|honeypot|"
    r"^(search|yes|no|i agree|select|choose)$",
    re.I,
)
NOISE_VALUES = {
    "", "select", "select...", "choose", "on", "please select", "cursor",
    "last year", "communication", "infrastructure",
}

LIST_FIELDS_JS = """() => {
  const items = [];
  const seen = new Set();
  const questionLabel = (el) => {
    let label = el.getAttribute('aria-label') || el.getAttribute('placeholder') || '';
    if (!label && el.id) {
      const forLab = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (forLab) label = forLab.innerText;
    }
    const wrap = el.closest('fieldset, [class*="question" i], [class*="Question"], [data-test-id], li, .field, label, [role="group"]');
    if (wrap) {
      const t = wrap.querySelector('legend, label, [class*="label" i], h2, h3, h4, p, span');
      const text = (t && t.innerText) || wrap.innerText;
      if (text && text.trim().length > (label || '').length) label = text;
    }
    if (!label) {
      const prev = el.previousElementSibling;
      if (prev) label = prev.innerText;
    }
    return String(label || '').replace(/\\s+/g, ' ').trim().slice(0, 220);
  };
  const nodes = document.querySelectorAll('input, textarea, select, [role="combobox"], [contenteditable="true"]');
  for (const el of nodes) {
    const type = (el.getAttribute('type') || el.tagName).toLowerCase();
    if (['hidden', 'file', 'submit', 'button', 'password', 'image'].includes(type)) continue;
    if (el.offsetWidth === 0 && el.offsetHeight === 0 && type !== 'checkbox' && type !== 'radio') continue;
    let value = '';
    let options = [];
    if (type === 'checkbox' || type === 'radio') {
      if (!el.checked) {
        const lab = questionLabel(el);
        if (!lab || seen.has(lab.toLowerCase() + '|empty')) continue;
        seen.add(lab.toLowerCase() + '|empty');
        items.push({label: lab, value: '', name: el.name || el.id || '', type, options: []});
        continue;
      }
      const own = (el.closest('label') && el.closest('label').innerText) || el.value || 'Yes';
      value = String(own).replace(/\\s+/g, ' ').trim();
    } else if (el.tagName === 'SELECT') {
      const opt = el.options[el.selectedIndex];
      value = ((opt && opt.text) || el.value || '').trim();
      options = Array.from(el.options).map(o => (o.text || '').trim()).filter(Boolean).slice(0, 30);
    } else if (el.getAttribute('role') === 'combobox') {
      value = (el.innerText || el.value || '').trim();
    } else {
      value = (el.value || el.innerText || '').trim();
    }
    value = String(value).replace(/\\s+/g, ' ').trim().slice(0, 800);
    const label = questionLabel(el);
    if (!label || label.length < 2) continue;
    const key = label.toLowerCase() + '|' + (el.id || el.name || '');
    if (seen.has(key)) continue;
    seen.add(key);
    items.push({label, value, name: el.name || el.id || '', type, options});
  }
  return items;
}"""


def load_candidate() -> dict:
    if CANDIDATE_PATH.exists():
        return json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    return {}


def load_learned() -> dict:
    if LEARNED_PATH.exists():
        return json.loads(LEARNED_PATH.read_text(encoding="utf-8"))
    return {}


def load_memory() -> dict:
    if MEMORY_PATH.exists():
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    return {"by_label": {}, "history": []}


def save_memory(mem: dict) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(mem, indent=2, ensure_ascii=False), encoding="utf-8")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _answers() -> dict:
    c = load_candidate()
    L = load_learned()
    return {
        "fullName": c.get("fullName") or "Mohammed Abdul Rafi Ahmed",
        "firstName": L.get("legalFirstName") or c.get("firstName") or "Mohammed Abdul Rafi",
        "lastName": L.get("legalLastName") or c.get("lastName") or "Ahmed",
        "preferred": L.get("preferredFirstName") or "Rafi",
        "email": c.get("email") or "rafi.success@gmail.com",
        "phone": "8790251698",
        "linkedin": c.get("linkedIn") or L.get("linkedin"),
        "city": "Hyderabad",
        "state": "Telangana",
        "country": "India",
        "location": "Hyderabad, Telangana, India",
        "locationShort": "Hyderabad, IND",
        "company": c.get("currentEmployer") or "Nemetschek",
        "title": c.get("currentRole") or "Principal Analyst (Technical Architect)",
        "years": "15",
        "notice": "Immediate",
        "noticeDays": "0",
        "start": "Immediate / ASAP",
        "currentCtc": "5200000",
        "expectedCtc": "6500000",
        "salaryText": L.get("desiredAnnualSalary") or "6500000 INR (65 LPA)",
        "dob": "16/01/1989",
        "dobUs": "01/16/1989",
        "dobIso": "1989-01-16",
        "gender": "Male",
        "school": "Acharya Nagarjuna University",
        "degree": "B.Tech",
        "field": "Information Technology",
        "gradYear": "2010",
        "eduStart": "2006",
        "howHeard": "Company Careers Website",
        "rtw": "Indian Passport",
        "race": "Asian (Not Hispanic or Latino)",
        "veteran": "I am not a protected veteran",
        "disability": "No, I do not have a disability and have not had one in the past",
        "pitch": L.get("additionalInfo") or (
            "Technical Architect, 15+ years, .NET / cloud / distributed systems. "
            "Hyderabad-based. Immediate joiner. Current 52 LPA, expected 65 LPA."
        ),
        "ai": (
            "Yes. I use Claude and ChatGPT for architecture documentation, design "
            "exploration, and reviewing trade-offs. I verify all technical decisions myself."
        ),
        "initiative": (
            "At Nemetschek I led architecture of a .NET Core microservices platform on AWS/Azure "
            "with Kafka and Kubernetes, from design through production for Solibri/Spacewell. "
            "I set service boundaries, CI/CD, and observability so multiple teams could ship independently."
        ),
        "outsideExpertise": (
            "I owned cloud and Kubernetes rollout for a product team while my core background is "
            "application architecture. I partnered with platform engineers and delivered a production "
            "environment without blocking the product roadmap."
        ),
        "noAuthority": (
            "I aligned multiple product and platform teams on a shared API and release plan without "
            "direct reporting lines, using architecture reviews and a written decision log to keep delivery on track."
        ),
        "changingReqs": (
            "When requirements kept shifting, I time-boxed discovery, published a thin walking-skeleton "
            "architecture, and re-planned every sprint so the team always had a stable next increment."
        ),
        "linux": (
            "Production Linux on AWS/Azure Kubernetes clusters for .NET microservices. I owned service "
            "design, deployment topology, and production readiness, working with platform engineers on the nodes."
        ),
        "cloudSecurity": (
            "I have designed and reviewed AWS and Azure architectures with private networking, IAM least "
            "privilege, secrets management, and centralized logging. About 8 years using these controls on product platforms."
        ),
        "awsYes": "Yes. Production AWS and Azure for .NET microservices, Kubernetes, and event-driven systems.",
    }


def infer_answer(label: str, options: list[str] | None = None) -> str | None:
    q = norm(label)
    if not q or len(q) < 3:
        return None
    if q in {"yes", "no", "search", "password"}:
        return None
    if "last working day" in q or ("serving" in q and "notice" in q):
        return None
    mem = load_memory()["by_label"]
    if q in mem:
        val = (mem[q].get("value") or "").strip()
        if val and norm(val) not in NOISE_VALUES and val.lower() != "cursor":
            return val
    tokens = set(re.findall(r"[a-z0-9]{3,}", q))
    best_val = None
    best_score = 0.58
    for stored, row in mem.items():
        val = (row.get("value") or "").strip()
        if not val or norm(val) in NOISE_VALUES or val.lower() == "cursor":
            continue
        if len(stored) > 12 and (stored in q or q in stored):
            return val
        other = set(re.findall(r"[a-z0-9]{3,}", stored))
        if not tokens or not other:
            continue
        score = len(tokens & other) / len(tokens | other)
        if score > best_score:
            best_score = score
            best_val = val
    if best_val:
        return best_val

    a = _answers()
    options = options or []

    def pick(*needles):
        for opt in options:
            low = opt.lower()
            if any(n in low for n in needles):
                return opt
        return None

    if "united states" in q or "u.s." in q or "us citizen" in q:
        if "authoriz" in q or "eligible" in q or "right to work" in q:
            return pick("no") or "No"
        if "sponsor" in q:
            return pick("no") or "No"
    if any(x in q for x in ("sponsor", "visa", "immigration", "work permit required")):
        return pick("no") or "No"
    if any(x in q for x in ("authoriz", "right to work", "legally permitted", "eligible to work", "work eligibility")):
        return pick("yes", "citizen", "permanently") or "Yes"
    if "previously employed" in q or "previously applied" in q or "worked here" in q or "worked for" in q:
        return pick("no") or "No"
    if "applied here before" in q or "applied before" in q:
        return pick("no") or "No"
    if "senior government" in q or re.search(r"\bsgo\b", q):
        return pick("no") or "No"
    if "securities industry" in q:
        return pick("no") or "No"
    if "alongside" in q or "maintain your employment" in q or "self employed" in q:
        return pick("no") or "No"
    if "rescinded" in q:
        return pick("no") or "No"
    if "covenant" in q or "non-solicit" in q:
        return pick("no") or "No"
    if "work permit" in q:
        return pick("yes") or "Yes"
    if "nationality" in q:
        return pick("indian", "india") or "Indian"
    if "citizenship" in q:
        return pick("indian", "india") or "Indian"
    if "rsu" in q:
        return "0"
    if "non-compet" in q or "noncompet" in q:
        return pick("no") or "No"
    if "relocat" in q:
        return pick("no") or "No"
    if "disability" in q:
        return pick("do not have a disability", "no") or a["disability"]
    if "veteran" in q:
        return pick("not a protected veteran", "no") or a["veteran"]
    if "race" in q or "ethnicity" in q:
        return pick("asian") or a["race"]
    if q.strip() == "gender" or q.startswith("gender"):
        return pick("male") or a["gender"]
    if "notice" in q:
        return pick("available immediately", "immediate") or a["notice"]
    if "proficiency" in q:
        return pick("expert", "advanced") or "Expert"
    if "hands-on" in q and any(x in q for x in ("docker", "kubernetes", "k8s")):
        return pick("yes") or "Yes"
    if "when can you start" in q or "start date" in q or "available to start" in q or "joining" in q:
        return a["start"]
    if ("last" in q or "current" in q) and any(x in q for x in ("ctc", "salary", "compensation", "pay")):
        return a["currentCtc"]
    if any(x in q for x in ("expected ctc", "desired annual", "salary expectation", "expected salary", "compensation expect")):
        return a["salaryText"]
    if "salary" in q or "ctc" in q or "compensation" in q:
        return a["salaryText"]
    if "linkedin" in q:
        return a["linkedin"]
    if "current company" in q or "current employer" in q or q in {"company", "employer", "organization"}:
        return a["company"]
    if "current title" in q or "current role" in q or "job title" in q:
        return a["title"]
    if "years of experience" in q or "total experience" in q or "how many years" in q:
        if options:
            plus = []
            for opt in options:
                m = re.search(r"(\d+)\+", opt)
                if m:
                    plus.append((int(m.group(1)), opt))
            if plus:
                years = int(re.sub(r"\D", "", a["years"]) or "15")
                chosen = None
                for n, opt in sorted(plus):
                    if years >= n:
                        chosen = opt
                if chosen:
                    return chosen
            for needle in ("12+", "10+", "9+", "8-12", "8+", "5-8"):
                hit = pick(needle)
                if hit:
                    return hit
        if "cloud security" in q:
            return "8"
        if "aws" in q or "azure" in q or ".net" in q or "cloud" in q:
            return "10"
        return a["years"]
    if "date of birth" in q or q == "dob" or "birth date" in q:
        return a["dob"]
    if "university" in q or "college" in q or "school name" in q or "institution" in q:
        return a["school"]
    if "degree" in q or "highest education" in q or "qualification" in q:
        return pick("bachelor", "b.tech", "btech") or "B.Tech"
    if "field of study" in q or "specialization" in q or "major" in q:
        return a["field"]
    if "graduation" in q or "year of passing" in q or "passed out" in q:
        return a["gradYear"]
    if "how did you" in q or "how did you hear" in q or "how did you learn" in q:
        return pick("career site", "career", "company website", "website") or a["howHeard"]
    if "please specify" in q:
        return pick("career", "company", "dtcc.com", "website") or a["howHeard"]
    if "right to work document" in q or "document type" in q:
        return pick("passport", "indian") or a["rtw"]
    if "city of residence" in q or (q == "city") or "current city" in q:
        return a["city"]
    if (
        "state of residence" in q
        or q in {"state", "state *", "region2", "region", "province"}
        or (q.startswith("state") and "statement" not in q and "united states" not in q)
    ):
        return pick("telangana") or a["state"]
    if q == "country" or "country of residence" in q or "country/region" in q:
        return pick("india") or a["country"]
    if "primary residence" in q or "home address" in q or "current location" in q or "city and state" in q:
        return a["location"] if "ind" not in q else a["locationShort"]
    if "preferred first" in q or "preferred name" in q:
        return a["preferred"]
    if "legal first" in q or q.strip() in {"first name", "first name *", "first name ✱"}:
        return a["firstName"]
    if "legal last" in q or q.strip() in {"last name", "last name *", "last name ✱"}:
        return a["lastName"]
    if "full name" in q or q.strip() in {"name", "name *", "name ✱"}:
        return a["fullName"]
    if "email" in q:
        return a["email"]
    if "phone" in q or "mobile" in q:
        return a["phone"]
    if "18" in q and "older" in q:
        return pick("yes") or "Yes"
    if "background check" in q or "drug test" in q:
        return pick("yes") or "Yes"
    if "relative" in q or "conflict of interest" in q:
        return pick("no") or "No"
    if "onsite" in q or "hybrid" in q or "office" in q:
        return pick("yes") or "Yes"
    if "ai tool" in q or "claude" in q or "chatgpt" in q:
        return a["ai"]
    if "technical initiative" in q or "concept to delivery" in q:
        return a["initiative"]
    if "outside your primary" in q or "outside your" in q and "expertise" in q:
        return a["outsideExpertise"]
    if "no formal authority" in q:
        return a["noAuthority"]
    if "unclear" in q or "constantly changing" in q:
        return a["changingReqs"]
    if "linux" in q:
        return a["linux"]
    if "cloud security" in q or "cspm" in q:
        return a["cloudSecurity"]
    if "experience with aws" in q or "aws or azure" in q:
        return a["awsYes"]
    if "additional information" in q or "cover letter" in q or "why do you want" in q or "tell us about yourself" in q:
        try:
            import tailor_resume
            if tailor_resume.CURRENT.get("cover"):
                return tailor_resume.CURRENT["cover"]
        except Exception:
            pass
        return a["pitch"]
    if options:
        for prefer in ("yes", "india", "hyderabad", "telangana", "immediate", "male", "no"):
            hit = pick(prefer)
            if hit and prefer in ("yes", "india", "hyderabad", "telangana", "immediate", "male"):
                if "sponsor" in q or "visa" in q:
                    continue
                return hit
    return None


def snapshot(page) -> list[dict]:
    try:
        return page.evaluate(LIST_FIELDS_JS) or []
    except Exception:
        return []


def remember(page, job: dict | None = None) -> list[dict]:
    items = snapshot(page)
    if not items:
        return []
    mem = load_memory()
    changed = []
    for item in items:
        label = item.get("label") or ""
        value = (item.get("value") or "").strip()
        bare = re.sub(r"[*✱]", "", label).strip()
        name = (item.get("name") or "").lower()
        if SKIP_STORE_LABELS.search(bare) or SKIP_STORE_LABELS.search(name):
            continue
        if norm(value) in NOISE_VALUES:
            continue
        if value.lower() == "cursor" or (value.isdigit() and len(value) > 8):
            continue
        if len(label) > 160 and "select ..." in norm(label):
            continue
        key = norm(label)
        prev = mem["by_label"].get(key) or {}
        if prev.get("value") == value:
            continue
        mem["by_label"][key] = {
            "label": label[:180],
            "value": value,
            "count": int(prev.get("count") or 0) + 1,
            "name": item.get("name") or prev.get("name") or "",
            "updated": datetime.now(timezone.utc).isoformat(),
            "source": "form",
        }
        changed.append({"label": label[:180], "value": value})
    if changed:
        mem["history"].append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "company": (job or {}).get("company"),
            "title": (job or {}).get("title"),
            "fields": changed[:40],
        })
        mem["history"] = mem["history"][-80:]
        save_memory(mem)
        print(f"  Learned {len(changed)} new/changed field(s).", flush=True)
    return changed


def lookup(label: str) -> str | None:
    return infer_answer(label)


def _fill_one(page, field: dict, value: str) -> bool:
    name = field.get("name") or ""
    label = field.get("label") or ""
    ftype = (field.get("type") or "").lower()
    try:
        if ftype in {"checkbox", "radio"} or field.get("options"):
            if quiet_option(page, label, value):
                return True
        if name:
            loc = page.locator(f"#{name}, [name='{name}']").first
            if loc.count():
                tag = (loc.evaluate("el => el.tagName") or "").lower()
                if tag == "select":
                    loc.select_option(label=value, timeout=800)
                    return True
                try:
                    import ats_fill
                    if ats_fill.native_fill(loc, str(value)):
                        return True
                except Exception:
                    pass
                loc.fill(str(value), timeout=800)
                return True
        box = page.get_by_label(re.compile(re.escape(label[:50]), re.I)).first
        if box.count():
            try:
                import ats_fill
                if (box.evaluate("el => (el.tagName||'').toLowerCase()") or "") == "select" or box.get_attribute("role") == "combobox":
                    if ats_fill.handle_dropdown(page, box, str(value)):
                        return True
                if ats_fill.native_fill(box, str(value)):
                    return True
            except Exception:
                pass
            box.fill(str(value), timeout=800)
            return True
    except Exception:
        return False
    return False


def quiet_option(page, question: str, answer: str) -> bool:
    try:
        heading = page.get_by_text(re.compile(re.escape(question[:60]), re.I)).first
        if heading.count():
            scope = heading.locator("xpath=ancestor::*[self::fieldset or self::li or self::div][1]")
            opt = scope.get_by_text(re.compile(rf"^{re.escape(answer)}$", re.I)).first
            if opt.count():
                opt.click(timeout=800)
                return True
        page.locator("select").filter(has_text=re.compile(question[:30], re.I)).first.select_option(label=answer, timeout=800)
        return True
    except Exception:
        return False


def apply_memory(page) -> int:
    return fill_visible(page)


def fill_visible(page) -> int:
    filled = 0
    email = _answers()["email"]
    try:
        loc = page.locator("input[type=email], #confirm-email-input, input[id*='email' i], input[name*='email' i]")
        for i in range(min(loc.count(), 8)):
            el = loc.nth(i)
            try:
                if not el.is_visible():
                    continue
                cur = (el.input_value() or "").strip()
                if cur.lower() == email.lower():
                    continue
                target = el
                try:
                    tag = (el.evaluate("n => (n.tagName || '').toLowerCase()") or "")
                except Exception:
                    tag = ""
                if tag not in {"input", "textarea"}:
                    inner = el.locator("input:not([type=hidden]), textarea").first
                    if inner.count():
                        target = inner
                target.scroll_into_view_if_needed(timeout=1200)
                target.fill(email, timeout=1500)
                filled += 1
            except Exception:
                continue
    except Exception:
        pass
    fields = snapshot(page)
    for field in fields:
        label = field.get("label") or ""
        name = (field.get("name") or "").lower()
        current = (field.get("value") or "").strip()
        if (
            name in {"region2", "region", "state", "province"}
            or re.search(r"\bstate\b", label, re.I)
        ) and current.upper() in {"TG", "TS", "AP"}:
            # Oracle/India typeaheads store full names; TG/TS return no results.
            current = ""
        if current and norm(current) not in NOISE_VALUES:
            continue
        value = infer_answer(label, field.get("options") or [])
        if not value:
            continue
        if _fill_one(page, field, value):
            filled += 1
            continue
        try:
            page.evaluate(
                """({label, value}) => {
                  const nodes = document.querySelectorAll('input, textarea, select');
                  for (const el of nodes) {
                    const type = (el.type || '').toLowerCase();
                    if (['hidden','file','submit','button','password'].includes(type)) continue;
                    let lab = el.getAttribute('aria-label') || '';
                    const wrap = el.closest('fieldset, [class*="question" i], li, label, [role="group"]');
                    if (wrap) lab = ((wrap.querySelector('legend,label,h3,p') || {}).innerText || wrap.innerText || lab);
                    lab = String(lab || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    if (!lab || !lab.includes(String(label).toLowerCase().slice(0, 40))) continue;
                    if (el.tagName === 'SELECT') {
                      const cur = ((el.options[el.selectedIndex] || {}).text || el.value || '').trim();
                      if (cur && cur.toLowerCase() !== 'select') return false;
                      for (const opt of el.options) {
                        if ((opt.text || '').toLowerCase().includes(String(value).toLowerCase())) {
                          el.value = opt.value;
                          el.dispatchEvent(new Event('change', {bubbles: true}));
                          return true;
                        }
                      }
                    } else if (type === 'radio' || type === 'checkbox') {
                      if (el.checked) return false;
                      const labId = (el.getAttribute('aria-labelledby') || '').split(' ')[0];
                      const lab = labId ? document.getElementById(labId) : (el.closest('label') || document.querySelector('label[for="'+el.id+'"]'));
                      const t = ((lab && lab.innerText) || el.value || '').toLowerCase();
                      if (t.includes(String(value).toLowerCase()) || t === String(value).toLowerCase()) {
                        if (lab) lab.click(); else el.click();
                        return true;
                      }
                    } else {
                      if ((el.value || '').trim()) return false;
                      const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
                      const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                      if (desc && desc.set) desc.set.call(el, value); else el.value = value;
                      el.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
                      el.dispatchEvent(new Event('change', {bubbles: true, composed: true}));
                      return true;
                    }
                  }
                  return false;
                }""",
                {"label": label[:80], "value": value},
            )
            filled += 1
        except Exception:
            continue
    if filled:
        print(f"  Auto-filled {filled} field(s) from profile and learned answers.", flush=True)
    return filled


def fill_india_state_typeahead(page) -> str:
    """Oracle State comboboxes reject TG/TS. Search Telangana, then Andhra Pradesh."""
    try:
        loc = page.locator(
            'input[name="region2"], input[name="region"], input[name="state"]'
        ).first
        if not loc.count() or not loc.is_visible():
            return ""
    except Exception:
        return ""
    try:
        current = (loc.input_value() or "").strip()
    except Exception:
        current = ""
    if current.lower() in {"telangana", "andhra pradesh"}:
        return current
    chosen = ""
    for query in ("Telangana", "Andhra Pradesh"):
        try:
            loc.scroll_into_view_if_needed()
            loc.click(timeout=2000)
            loc.fill("")
            loc.type(query, delay=50)
            page.wait_for_timeout(900)
            loc.press("ArrowDown")
            page.wait_for_timeout(150)
            loc.press("Enter")
            page.wait_for_timeout(400)
            chosen = (loc.input_value() or "").strip()
        except Exception:
            chosen = ""
        if chosen.lower() in {"telangana", "andhra pradesh"}:
            print(f"  State typeahead selected {chosen}.", flush=True)
            return chosen
    return chosen


def auto_complete(page, job: dict | None = None, steps: int = 6) -> int:
    """Fill this page, save answers, then click Next through the wizard."""
    total = 0
    for _ in range(steps):
        total += fill_visible(page)
        remember(page, job)
        clicked = False
        for sel in (
            "button:has-text('Next')",
            "button:has-text('Continue')",
            "button:has-text('Save and continue')",
            "button:has-text('Save & continue')",
        ):
            try:
                btn = page.locator(sel).first
                if btn.count() and btn.is_visible():
                    btn.click(timeout=1200)
                    page.wait_for_timeout(1000)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            break
        page.wait_for_timeout(600)
    return total


def seed_from_learned() -> None:
    cleanup_bad_memory()
    a = _answers()
    mem = load_memory()
    now = datetime.now(timezone.utc).isoformat()
    seeds = {
        "notice period": a["notice"],
        "desired start date": a["start"],
        "desired annual salary": a["salaryText"],
        "current company": a["company"],
        "current title": a["title"],
        "linkedin url": a["linkedin"],
        "city of residence": a["city"],
        "right to work document": a["rtw"],
        "gender": a["gender"],
        "what is your experience with ai tools like claude?": a["ai"],
        "do you have any experience with aws": a["awsYes"],
    }
    changed = False
    for label, value in seeds.items():
        key = norm(label)
        prev = mem["by_label"].get(key) or {}
        if norm(prev.get("value") or "") in NOISE_VALUES or not prev:
            mem["by_label"][key] = {
                "label": label,
                "value": value,
                "count": max(int(prev.get("count") or 0), 1),
                "name": prev.get("name") or "",
                "updated": now,
                "source": "seed",
            }
            changed = True
    if changed:
        save_memory(mem)


def cleanup_bad_memory() -> None:
    mem = load_memory()
    cleaned = {}
    removed = 0
    for key, row in mem.get("by_label", {}).items():
        val = norm(row.get("value") or "")
        lab = norm(row.get("label") or key)
        if val in NOISE_VALUES or val == "cursor":
            removed += 1
            continue
        if lab in {"yes", "no", "i agree"}:
            removed += 1
            continue
        cleaned[key] = row
    if removed:
        mem["by_label"] = cleaned
        save_memory(mem)
        print(f"  Removed {removed} bad remembered answers.", flush=True)
