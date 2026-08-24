"""Final Hyderabad / Remote-India discovery: career portals + job boards."""
from __future__ import annotations

import json
import re
import time
import urllib.parse
from collections import Counter
from datetime import date
from pathlib import Path

import apply_now
import discover_bulk
import discover_portals

ROOT = Path(__file__).resolve().parent

# Yesterday's target titles, plus Solution Architect / EM / .NET from the profile.
TARGET_PHRASES = [
    "technical architect",
    "principal engineer",
    "principal software engineer",
    "staff software engineer",
    "staff engineer",
    "senior staff engineer",
    "principal architect",
    "software architect",
    "cloud architect",
    "application architect",
    "backend architect",
    "full stack architect",
    "fullstack architect",
    "technical lead",
    "lead software engineer",
    "engineering lead",
    "senior engineering manager",
    "engineering manager",
    "senior backend engineer",
    "senior software engineer",
    "senior .net developer",
    "senior fullstack developer",
    "senior full stack developer",
    "solutions architect",
    "solution architect",
    ".net architect",
    "lead .net",
    "senior architect",
    "senior sde",
    "staff sde",
    "principal sde",
    "sde iii",
    "sde 3",
    "software development engineer iii",
    "sr. software",
    "sr software",
    "senior software development",
    "software development engineer iii",
    "software development engineer - iii",
    "lead software",
    "manager, software development",
    "manager software development",
    "sr manager, software",
    "sr manager software",
    "sr. manager, software",
    "sr. manager software",
    "senior manager, software",
    "senior manager software",
]

SKIP_TITLE = re.compile(
    r"intern|internship|campus|graduate trainee|apprentice|recruiter|"
    r"account executive|sales specialist|sales manager|inside sales|sales engineer|"
    r"customer engineering|firmware|rtl |asic |analog |antenna|hardware design|"
    r"devops|devsecops|\bsre\b|site reliability|mlops|"
    r"salesforce|servicenow|guidewire|\bpega\b|sitecore|mean stack|"
    r"blockchain|gis\b|esri|mandarin|biztalk|"
    r"layout|embedded|pcie|\bnand\b|physical design|synthesis|verification engineer|"
    r"hbm |product engineering|failure analysis|"
    r"java architect|java developer|\(java\)|java/go|"
    r"python sde|sourcing recruiter|finops|paid search|product trainer|"
    r"deal desk|procurement|quality analyst|"
    r"hyperautomation|\brpa\b|uipath|automation anywhere|"
    r"\bssd\b|\bnvm\b|nvmqra|qra test|"
    r"\bandroid\b|\bios\b|data engineering|"
    r"\bjava\b|spring boot|d365|dynamics 365|\bappian\b|drupal|"
    r"bangkok|gurugram based|relocation provided|"
    r"civil \(|uk water|linux kernel|device driver|"
    r"\baem\b|\bboomi\b|"
    r"specialist|manual testing|\bqa\b",
    re.I,
)
SKIP_LOW_CTC = re.compile(
    r"\b(1[5-9]|2\d|3\d|4[0-5])\s*[-–]?\s*(lpa|lakh|lacs)\b|"
    r"\b(15|20|25|30|35|40|45)\s*lacs?\b",
    re.I,
)
OTHER_CITY = re.compile(r"bangalore|bengaluru|pune|chennai|delhi|noida|gurgaon|gurugram|mumbai", re.I)
BLOCKED = {
    "pega", "salesforce", "servicenow",
    "ttec", "ttecdigital",
    "spectralconsultants",
    "amazonfilters", "amazonrailings", "amazonwood",
}


def title_ok(title: str) -> bool:
    t = (title or "").lower()
    if not t or SKIP_TITLE.search(t):
        return False
    return any(p in t for p in TARGET_PHRASES)


def loc_ok(location: str) -> bool:
    loc = location or ""
    if OTHER_CITY.search(loc) and not discover_bulk.HYD.search(loc):
        return False
    if discover_bulk.HYD.search(loc):
        return True
    return bool(
        re.search(r"remote|work from home|\bwfh\b|hybrid", loc, re.I)
        and re.search(r"\bindia\b|telangana", loc, re.I)
    )


def company_blocked(name: str) -> bool:
    raw = (name or "").strip()
    if not raw or raw.startswith("*"):
        return True
    key = apply_now.company_key(raw)
    if re.search(r"consultant|consultancy|staffing|recruit", raw, re.I):
        return True
    return key in BLOCKED or key in apply_now.load_blocked()


def add(jobs, company, title, location, url, ats, job_id="", extra=""):
    if not title_ok(title) or not loc_ok(location):
        return
    blob = f"{title} {location} {extra}"
    if SKIP_LOW_CTC.search(blob):
        return
    if company_blocked(company):
        return
    jobs.append({
        "company": company,
        "title": (title or "").strip(),
        "location": (location or "").strip(),
        "url": url or "",
        "ats": ats,
        "job_id": str(job_id or ""),
        "already_applied": False,
    })


def main():
    jobs = []
    print("Greenhouse boards...", flush=True)
    for token in discover_bulk.GH:
        data, status = discover_bulk.get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            loc = (item.get("location") or {}).get("name") or ""
            add(jobs, token, item.get("title") or "", loc, item.get("absolute_url") or "", "Greenhouse", item.get("id"))
        time.sleep(0.02)

    print("Lever boards...", flush=True)
    for company in discover_bulk.LEVER:
        data, status = discover_bulk.get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
        if status != 200 or not isinstance(data, list):
            continue
        for item in data:
            cats = item.get("categories") or {}
            loc = str(cats.get("location") or "")
            if isinstance(cats.get("allLocations"), list):
                loc = " ".join(str(x) for x in cats["allLocations"]) + " " + loc
            add(jobs, company, item.get("text") or "", loc, item.get("hostedUrl") or "", "Lever", item.get("id"))
        time.sleep(0.02)

    print("Ashby boards...", flush=True)
    for token in (
        "ramp", "mercury", "linear", "vercel", "supabase", "deel",
        "gusto", "checkr", "launchdarkly", "statsig", "sentry",
        "fivetran", "dbt", "hex", "airbyte", "brex", "plaid",
        "anthropic", "posthog", "webflow",
    ):
        data, status = discover_bulk.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            loc = item.get("location") or ""
            if isinstance(loc, dict):
                loc = " ".join(str(loc.get(k) or "") for k in ("location", "city", "region", "country"))
            if item.get("isRemote"):
                loc = f"{loc} Remote"
            add(jobs, token, item.get("title") or "", loc, item.get("jobUrl") or "", "Ashby", item.get("id"))
        time.sleep(0.03)

    print("Amazon.jobs...", flush=True)
    for q in (
        "technical architect", "principal engineer", "staff engineer",
        "software architect", "technical lead", "engineering manager",
        "senior software engineer", "senior sde", ".NET architect",
    ):
        qs = urllib.parse.urlencode({
            "base_query": q,
            "loc_query": "Hyderabad, Telangana, India",
            "result_limit": 100,
            "offset": 0,
        })
        data, _ = discover_bulk.get_json(f"https://www.amazon.jobs/en/search.json?{qs}")
        for item in (data or {}).get("jobs") or []:
            loc = f"{item.get('city_name','')} {item.get('location','')} {item.get('normalized_location','')}"
            jid = item.get("id_icims") or item.get("id")
            add(jobs, "Amazon", item.get("title") or "", loc, f"https://www.amazon.jobs/en/jobs/{jid}", "Amazon", jid)
        time.sleep(0.2)

    print("Workday career portals...", flush=True)
    for api, site, company in discover_portals.SITES:
        print(f"  {company}", flush=True)
        for q in (
            "Hyderabad architect",
            "Hyderabad principal engineer",
            "Hyderabad staff engineer",
            "Hyderabad senior software",
            "Hyderabad technical lead",
        ):
            payload = json.dumps({"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": q}).encode()
            data = discover_portals.get_json(api, data=payload)
            time.sleep(0.12)
            if not data:
                continue
            for item in data.get("jobPostings") or []:
                title = (item.get("title") or "").strip()
                loc = item.get("locationsText") or ""
                path = item.get("externalPath") or ""
                if not path:
                    continue
                add(jobs, company, title, loc, site.rstrip("/") + path, "Workday", path.rstrip("/").split("/")[-1])

    apply_now.sync_applied_store()
    used = apply_now.submitted_by_company()
    applied_ids = set(apply_now.SKIP_IDS) | set(apply_now.load_applied_ids())
    for ids in used.values():
        applied_ids.update(ids)

    seen = set()
    unique = []
    for j in jobs:
        key = (apply_now.company_key(j["company"]), str(j["job_id"] or j["url"])[:80])
        if key in seen:
            continue
        seen.add(key)
        jid = str(j.get("job_id") or "")
        ck = apply_now.company_key(j["company"])
        j["already_applied"] = apply_now.is_applied(j) or bool(jid and jid in applied_ids)
        j["company_applied_count"] = len(used.get(ck, set()))
        unique.append(j)

    for j in unique:
        j["match_score"] = apply_now.match_score(j)
    unique.sort(key=lambda j: (j.get("already_applied"), -int(j.get("match_score") or 0), j["company"].lower()))
    open_jobs = [j for j in unique if not j["already_applied"]]
    apply_queue = apply_now.pick_best_per_company(open_jobs, used)
    chosen_keys = {
        (apply_now.company_key(j.get("company")), str(j.get("job_id") or j.get("url") or "")[:80])
        for j in apply_queue
    }
    for j in open_jobs:
        key = (apply_now.company_key(j.get("company")), str(j.get("job_id") or j.get("url") or "")[:80])
        j["over_cap"] = key not in chosen_keys
    apply_queue.sort(key=lambda j: (-int(j.get("match_score") or 0), j.get("company") or "", j.get("title") or ""))

    (ROOT / "data" / "discovery_final.json").write_text(json.dumps(unique, indent=2), encoding="utf-8")
    (ROOT / "data" / "discovery_batch.json").write_text(json.dumps(apply_queue, indent=2), encoding="utf-8")

    lines = [
        "# Final discovery — Hyderabad / Remote India",
        "",
        f"Run date: {date.today().isoformat()}",
        "",
        "Sources: company career portals (Workday, Amazon.jobs) and job boards (Greenhouse, Lever, Ashby).",
        "Titles: yesterday's list (Architect / Principal / Staff / Tech Lead / EM / Senior Software-Backend-Full Stack-.NET).",
        "Location: Hyderabad hubs or Remote/Hybrid India. CTC 60 LPA preferred; unknown CTC kept. Known 15–45 LPA dropped.",
        "",
        "## Counts",
        "",
        f"- Matched unique: **{len(unique)}**",
        f"- Already applied: **{sum(1 for j in unique if j['already_applied'])}**",
        f"- Open and in-scope: **{len(open_jobs)}**",
        f"- Ready to apply (best matches, under 3/company, not blocked): **{len(apply_queue)}**",
        "",
        "By source (open): " + ", ".join(f"{k} {v}" for k, v in Counter(j['ats'] for j in open_jobs).most_common()),
        "",
        "By company (open): " + ", ".join(f"{k} {v}" for k, v in Counter(j['company'] for j in open_jobs).most_common(20)),
        "",
        "## Ready to apply",
        "",
        "| # | Company | Title | Location | Source | Link |",
        "|---|---------|-------|----------|--------|------|",
    ]
    for i, j in enumerate(apply_queue, 1):
        url = j.get("url") or ""
        lines.append(
            f"| {i} | {j['company']} | {j['title'][:70]} | {j['location'][:42]} | {j['ats']} | {url} |"
        )
    if not apply_queue:
        lines.append("| | *(none under cap)* | | | | |")
    lines.extend(["", "## Open but company already at 4 applications", ""])
    over = [j for j in open_jobs if j.get("over_cap")]
    if not over:
        lines.append("None.")
    else:
        for j in over:
            lines.append(f"- {j['company']}: {j['title']} — {j['location']}")
    (ROOT / "DISCOVERY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nMatched unique: {len(unique)}")
    print(f"Already applied: {sum(1 for j in unique if j['already_applied'])}")
    print(f"Open: {len(open_jobs)}")
    print(f"Ready to apply: {len(apply_queue)}")
    print("By ATS (open):", dict(Counter(j["ats"] for j in open_jobs)))
    print("Top companies (open):", Counter(j["company"] for j in open_jobs).most_common(12))
    for i, j in enumerate(apply_queue[:40], 1):
        print(f"{i:2} {j['ats'][:10]:10} {j['company'][:16]:16} {j['title'][:58]:58} {j['location'][:36]}")


if __name__ == "__main__":
    main()
