"""Search preferred near-home campus companies for Hyderabad openings.

RMZ Nexity / Futura / Spire, Knowledge City / Park, Raheja Mindspace.
Merges hits into discovery JSON so apply_now.queue() can put them first.
"""
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
import discover_final as d
import discover_hyd_gcc as gcc
import discover_more_sites as more

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "data" / "preferred_campus_openings.md"

WD_URL = re.compile(
    r"https://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)",
    re.I,
)

# Extra Workday sites not listed as kind=workday on PORTALS.
EXTRA_WORKDAY = [
    ("https://accenture.wd3.myworkdayjobs.com/wday/cxs/accenture/AccentureCareers/jobs",
     "https://accenture.wd3.myworkdayjobs.com/en-US/AccentureCareers", "Accenture"),
    ("https://cognizant.wd1.myworkdayjobs.com/wday/cxs/cognizant/CognizantCareers/jobs",
     "https://cognizant.wd1.myworkdayjobs.com/en-US/CognizantCareers", "Cognizant"),
    ("https://deloitte.wd1.myworkdayjobs.com/wday/cxs/deloitte/DeloitteCareers/jobs",
     "https://deloitte.wd1.myworkdayjobs.com/en-US/DeloitteCareers", "Deloitte"),
    ("https://ibm.wd1.myworkdayjobs.com/wday/cxs/ibm/search/jobs",
     "https://ibm.wd1.myworkdayjobs.com/en-US/search", "IBM"),
    ("https://oracle.wd1.myworkdayjobs.com/wday/cxs/oracle/External/jobs",
     "https://oracle.wd1.myworkdayjobs.com/en-US/External", "Oracle"),
    ("https://verizon.wd1.myworkdayjobs.com/wday/cxs/verizon/External_Career_Site/jobs",
     "https://verizon.wd1.myworkdayjobs.com/en-US/External_Career_Site", "Verizon"),
    ("https://opentext.wd3.myworkdayjobs.com/wday/cxs/opentext/External/jobs",
     "https://opentext.wd3.myworkdayjobs.com/en-US/External", "OpenText"),
    ("https://parexel.wd1.myworkdayjobs.com/wday/cxs/parexel/PAREXEL_External/jobs",
     "https://parexel.wd1.myworkdayjobs.com/en-US/PAREXEL_External", "Parexel"),
    ("https://syneoshealth.wd1.myworkdayjobs.com/wday/cxs/syneoshealth/External/jobs",
     "https://syneoshealth.wd1.myworkdayjobs.com/en-US/External", "Syneos Health"),
    ("https://gevernova.wd1.myworkdayjobs.com/wday/cxs/gevernova/GE_Vernova_Careers/jobs",
     "https://gevernova.wd1.myworkdayjobs.com/en-US/GE_Vernova_Careers", "GE Vernova"),
]

PHENOM_HOSTS = [
    ("jobs.synchrony.com", "Synchrony"),
    ("jobs.ea.com", "Electronic Arts"),
    ("jobs.parexel.com", "Parexel"),
    ("jobs.arcelormittal.com", "ArcelorMittal"),
    ("careers.mcdonalds.com", "McDonalds"),
]

EIGHTFOLD_DOMAINS = [
    ("ea.com", "Electronic Arts"),
    ("cgi.com", "CGI"),
    ("mcdonalds.com", "McDonalds"),
    ("arcelormittal.com", "ArcelorMittal"),
    ("alterdomus.com", "Alter Domus"),
    ("providence.org", "Providence"),
    ("verizon.com", "Verizon"),
    ("parexel.com", "Parexel"),
    ("apple.com", "Apple"),
    ("kpmg.com", "KPMG"),
    ("microsoft.com", "Microsoft"),
    ("amgen.com", "Amgen"),
    ("novartis.com", "Novartis"),
    ("qualcomm.com", "Qualcomm"),
    ("broadcom.com", "Broadcom"),
    ("ibm.com", "IBM"),
    ("oracle.com", "Oracle"),
    ("wellsfargo.com", "Wells Fargo"),
    ("bankofamerica.com", "Bank of America"),
    ("hsbc.com", "HSBC"),
    ("thomsonreuters.com", "Thomson Reuters"),
    ("opentext.com", "OpenText"),
    ("cognizant.com", "Cognizant"),
    ("accenture.com", "Accenture"),
    ("persistent.com", "Persistent"),
    ("zensar.com", "Zensar"),
    ("syneoshealth.com", "Syneos Health"),
    ("deloitte.com", "Deloitte"),
    ("synchrony.com", "Synchrony"),
    ("gevernova.com", "GE Vernova"),
    ("techmahindra.com", "Tech Mahindra"),
]

GREENHOUSE = [
    ("darwinbox", "Darwinbox"),
    ("zenoti", "Zenoti"),
]

def _canonical_company(name: str) -> str:
    if apply_now.company_key(name) == "ge":
        return "GE Vernova"
    return name


def workday_from_url(url: str, company: str) -> tuple[str, str, str] | None:
    m = WD_URL.search(url or "")
    if not m:
        return None
    tenant, wd, site = m.group(1), m.group(2), m.group(3)
    api = f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    site_url = f"https://{tenant}.{wd}.myworkdayjobs.com/en-US/{site}"
    return api, site_url, _canonical_company(company)


def preferred_workday_targets() -> list[tuple[str, str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str, str]] = []
    for p in gcc.PORTALS:
        if not apply_now.is_preferred_campus_company(p.get("company") or ""):
            continue
        if p.get("api") and p.get("site"):
            row = (p["api"], p["site"], _canonical_company(p["company"]))
        else:
            inferred = workday_from_url(p.get("url") or "", p.get("company") or "")
            if not inferred:
                continue
            row = inferred
        key = (row[0], row[2])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    for api, site, company in EXTRA_WORKDAY:
        key = (api, company)
        if key in seen:
            continue
        if not apply_now.is_preferred_campus_company(company):
            continue
        seen.add(key)
        out.append((api, site, company))
    return out


def search_workday(jobs: list) -> None:
    for api, site, company in preferred_workday_targets():
        gcc.workday_search(api, site, company, jobs)


def search_phenom(jobs: list) -> None:
    done = set()
    for host, company in PHENOM_HOSTS:
        if host in done:
            continue
        done.add(host)
        gcc.smashfly_search(host, company, jobs)


def search_eightfold(jobs: list) -> None:
    print("  Eightfold preferred campuses", flush=True)
    before = len(jobs)
    for domain, company in EIGHTFOLD_DOMAINS:
        qs = (
            "https://app.eightfold.ai/api/apply/v2/jobs?"
            f"domain={domain}&location=Hyderabad&start=0&num=40"
        )
        data = gcc.get_json(qs)
        time.sleep(0.08)
        if not isinstance(data, dict):
            continue
        for item in data.get("positions") or data.get("data") or []:
            loc = item.get("location") or ""
            if isinstance(item.get("locations"), list):
                loc = " ".join(str(x) for x in item["locations"]) + " " + str(loc)
            jid = item.get("id") or item.get("ats_job_id") or ""
            url = item.get("canonicalPositionUrl") or item.get("apply_url") or item.get("url") or ""
            gcc.add_job(
                jobs, company, item.get("name") or item.get("title") or "",
                loc, url, "Eightfold", jid,
            )
    print(f"    +{len(jobs) - before} rows", flush=True)


def search_greenhouse(jobs: list) -> None:
    print("  Greenhouse preferred campuses", flush=True)
    before = len(jobs)
    for token, company in GREENHOUSE:
        data, status = discover_bulk.get_json(
            f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        )
        time.sleep(0.08)
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            loc = ""
            offices = item.get("offices") or []
            loc = " ".join(
                str(o.get("name") or o.get("location") or "") for o in offices if isinstance(o, dict)
            )
            loc = loc or str(item.get("location") or "")
            if isinstance(item.get("location"), dict):
                loc = item["location"].get("name") or loc
            gcc.add_job(
                jobs, company, item.get("title") or "", loc,
                item.get("absolute_url") or "", "Greenhouse", item.get("id") or "",
            )
    print(f"    +{len(jobs) - before} rows", flush=True)


def search_amazon(jobs: list) -> None:
    print("  Amazon.jobs Hyderabad", flush=True)
    before = len(jobs)
    for q in (
        "technical architect", "principal engineer", "staff engineer",
        "software architect", "technical lead", "engineering manager",
        "senior software engineer", "senior sde",
    ):
        qs = urllib.parse.urlencode({
            "base_query": q,
            "loc_query": "Hyderabad, Telangana, India",
            "result_limit": 50,
            "offset": 0,
        })
        data, _ = discover_bulk.get_json(f"https://www.amazon.jobs/en/search.json?{qs}")
        for item in (data or {}).get("jobs") or []:
            loc = f"{item.get('city_name', '')} {item.get('location', '')} {item.get('normalized_location', '')}"
            jid = item.get("id_icims") or item.get("id")
            gcc.add_job(
                jobs, "Amazon", item.get("title") or "", loc,
                f"https://www.amazon.jobs/en/jobs/{jid}", "Amazon", jid,
            )
        time.sleep(0.15)
    print(f"    +{len(jobs) - before} rows", flush=True)


def search_meta(jobs: list) -> None:
    print("  Meta careers Hyderabad", flush=True)
    before = len(jobs)
    qs = urllib.parse.urlencode({
        "q": "architect Hyderabad",
        "is_leadership": "0",
    })
    html = gcc.get_text(f"https://www.metacareers.com/jobs?{qs}", timeout=12)
    if html:
        for m in re.finditer(r'href="(/profile/job/[^"]+)"', html):
            path = m.group(1)
            url = "https://www.metacareers.com" + path.split("?")[0]
            slug = urllib.parse.unquote(path.rstrip("/").split("/")[-1])
            title = slug.replace("-", " ").title()
            gcc.add_job(jobs, "Meta", title, "Hyderabad, Telangana, India", url, "Meta", path)
    print(f"    +{len(jobs) - before} rows", flush=True)


def collect(jobs: list) -> list:
    """Append preferred-campus openings onto an existing job list."""
    print("Preferred campus career search...", flush=True)
    search_workday(jobs)
    more.microsoft(jobs)
    gcc.apple_search(jobs)
    search_amazon(jobs)
    search_phenom(jobs)
    search_eightfold(jobs)
    search_greenhouse(jobs)
    search_meta(jobs)
    print(f"Preferred campus raw rows now: {len(jobs)}", flush=True)
    return jobs


def _matches_named_company(name: str, found_keys: set[str], found_names: list[str]) -> bool:
    key = apply_now.company_key(name)
    if key in found_keys:
        return True
    return any(
        key and (key in apply_now.company_key(c) or apply_now.company_key(c) in key)
        for c in found_names
    )


def write_report(queue: list[dict]) -> list[dict]:
    preferred = [j for j in queue if apply_now.is_preferred_campus_job(j)]
    career = [j for j in preferred if int(j.get("portal_rank") or apply_now.portal_rank(j)) >= 50]
    boards = [j for j in preferred if j not in career]
    by_co = Counter(j.get("company") or "" for j in preferred)
    campuses = json.loads((ROOT / "data" / "preferred_campuses.json").read_text(encoding="utf-8"))
    names = [c.get("name") for c in campuses.get("companies") or [] if isinstance(c, dict)]
    found_keys = {apply_now.company_key(c) for c in by_co}
    found_names = list(by_co)
    missing = [n for n in names if not _matches_named_company(n, found_keys, found_names)]
    lines = [
        "# Preferred campus openings",
        "",
        f"Run date: {date.today().isoformat()}",
        "",
        "Live Hyderabad / near-home roles at RMZ Nexity, RMZ Futura, RMZ Spire, "
        "Knowledge City / Park, and Raheja Mindspace tenants.",
        "Company career leftovers are scored +50 and sorted first in `apply_now.queue()`.",
        "",
        f"**In-scope leftovers: {len(preferred)}** ({len(career)} career portal, "
        f"{len(boards)} board) across **{len(by_co)}** companies.",
        "",
        "## Career-portal leftovers (apply first)",
        "",
        "| # | Score | Company | Title | Location | Link |",
        "|---|------:|---------|-------|----------|------|",
    ]
    for i, j in enumerate(career, 1):
        lines.append(
            f"| {i} | {j.get('match_score') or 0} | {j.get('company')} | "
            f"{(j.get('title') or '')[:70]} | {(j.get('location') or '')[:40]} | {j.get('url') or ''} |"
        )
    if not career:
        lines.append("| | | none | | | |")
    lines += [
        "",
        "## Board leftovers (LinkedIn / Foundit / Naukri)",
        "",
        "| # | Score | Company | Title | Location | Link |",
        "|---|------:|---------|-------|----------|------|",
    ]
    for i, j in enumerate(boards[:60], 1):
        lines.append(
            f"| {i} | {j.get('match_score') or 0} | {j.get('company')} | "
            f"{(j.get('title') or '')[:70]} | {(j.get('location') or '')[:40]} | {j.get('url') or ''} |"
        )
    if not boards:
        lines.append("| | | none | | | |")
    if missing:
        lines += [
            "",
            "## No in-scope leftover found",
            "",
            "Searched, but no leftover architect / principal / staff / EM / senior software "
            "role in Hyderabad after applied/skip filters:",
            "",
        ]
        lines.extend(f"- {n}" for n in missing)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return preferred


def main() -> None:
    jobs: list = []
    collect(jobs)
    more.merge_and_write(jobs)
    apply_now.BATCH = apply_now.load_all_discovered()
    queue = apply_now.queue()
    preferred = write_report(queue)
    print(f"Queue {len(queue)}; preferred leftovers {len(preferred)}", flush=True)
    for j in preferred[:40]:
        print(
            f"  {j.get('match_score')} | {j.get('company')} | {j.get('title')} | "
            f"{j.get('location')} | {j.get('url')}",
            flush=True,
        )


if __name__ == "__main__":
    main()
