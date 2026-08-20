"""Count Hyderabad-hub jobs from company career APIs."""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

CTX = ssl.create_default_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"

AREA = re.compile(
    r"madhapur|gachibowli|financial district|nanakramguda|raidurg|kondapur|"
    r"hitec city|hitech city|hitec|hitech",
    re.I,
)
HYD = re.compile(r"hyderabad|telangana|\bhyd\b", re.I)
SKIP_JUNIOR = re.compile(r"intern|internship|campus|graduate trainee|apprentice", re.I)
SENIOR = re.compile(
    r"architect|principal|staff engineer|staff software|technical lead|"
    r"engineering lead|solution architect|solutions architect|\.net|technical architect",
    re.I,
)

GH = [
    "highradius", "inovalon", "crunchyroll", "zscaler", "ncrvoyix", "adp",
    "phonepe", "razorpay", "swiggy", "zomato", "flipkart", "meesho",
    "freshworks", "postman", "browserstack", "chargebee", "innovaccer",
    "o9solutions", "whatfix", "mindtickle", "gupshup", "practo",
    "cyient", "persistent", "valuelabs", "epam", "broadridge", "factset",
    "cotiviti", "pega", "uipath", "thoughtworks", "globallogic",
    "informatica", "opentext", "teradata", "sas", "invesco",
    "franklintempleton", "blackrock", "statestreet", "bnymellon",
    "ssnc", "hexaware", "mphasis", "virtusa", "brillio", "sonatasoftware",
    "birlasoft", "kpit", "ltts", "databricks", "snowflake", "twilio",
    "mongodb", "elastic", "confluent", "okta", "splunk", "docusign",
    "zoom", "atlassian", "gitlab", "github", "jfrog", "snyk", "wiz",
    "crowdstrike", "cloudflare", "datadog", "newrelic", "pagerduty",
    "servicenow", "salesforce", "nvidia", "qualcomm", "amd", "micron",
    "stripe", "coinbase", "intuit", "adobe", "autodesk",
]

LEVER = [
    "keyloop", "dnb", "cprime", "ttecdigital", "ncrvoyix", "meesho",
    "freshworks", "mindtickle", "phonepe", "razorpay", "swiggy",
    "zomato", "flipkart", "postman", "browserstack", "chargebee",
    "innovaccer", "whatfix", "gupshup", "practo", "cyient",
    "ltimindtree", "hexaware", "mphasis", "virtusa", "persistent",
    "valuelabs", "epam", "globallogic", "broadridge", "factset",
    "cotiviti", "wellsfargo", "jpmorganchase", "goldmansachs",
    "deloitte", "kpmg", "capgemini", "accenture", "cognizant",
    "infosys", "wipro", "hcltech", "techmahindra", "servicenow",
    "salesforce", "oracle", "nvidia", "qualcomm", "amd", "micron",
    "pega", "uipath", "ncr", "genpact", "brillio", "sonata",
]

WORKDAY = [
    ("https://micron.wd1.myworkdayjobs.com/wday/cxs/micron/External/jobs", "Micron"),
    ("https://qualcomm.wd5.myworkdayjobs.com/wday/cxs/qualcomm/External/jobs", "Qualcomm"),
    ("https://amd.wd1.myworkdayjobs.com/wday/cxs/amd/careers/jobs", "AMD"),
    ("https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs", "NVIDIA"),
    ("https://oracle.wd5.myworkdayjobs.com/wday/cxs/oracle/External/jobs", "Oracle"),
    ("https://walmart.wd5.myworkdayjobs.com/wday/cxs/walmart/WalmartExternal/jobs", "Walmart"),
    ("https://wellsfargo.wd1.myworkdayjobs.com/wday/cxs/wellsfargo/External/jobs", "Wells Fargo"),
]


def get_json(url, data=None, headers=None, timeout=18):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace")), resp.status
    except Exception:
        return None, 0


def loc_bucket(text: str) -> str:
    t = text or ""
    if AREA.search(t):
        return "named_hub"
    if HYD.search(t):
        return "hyderabad"
    return ""


def add(jobs, company, title, location, url, ats, job_id=""):
    bucket = loc_bucket(f"{location} {title}")
    if not bucket:
        return
    jobs.append({
        "company": company,
        "title": (title or "").strip(),
        "location": (location or "").strip(),
        "url": url or "",
        "ats": ats,
        "job_id": str(job_id or ""),
        "bucket": bucket,
        "senior": bool(SENIOR.search(title or "")) and not SKIP_JUNIOR.search(title or ""),
        "skip_junior": bool(SKIP_JUNIOR.search(title or "")),
    })


def main():
    jobs = []
    print("Scanning Greenhouse...", flush=True)
    for token in GH:
        data, status = get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            loc = (item.get("location") or {}).get("name") or ""
            add(jobs, token, item.get("title") or "", loc, item.get("absolute_url") or "", "Greenhouse", item.get("id"))
        time.sleep(0.02)

    print("Scanning Lever...", flush=True)
    for company in LEVER:
        data, status = get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
        if status != 200 or not isinstance(data, list):
            continue
        for item in data:
            cats = item.get("categories") or {}
            loc = str(cats.get("location") or "")
            if isinstance(cats.get("allLocations"), list):
                loc = " ".join(cats["allLocations"]) + " " + loc
            add(jobs, company, item.get("text") or "", loc, item.get("hostedUrl") or "", "Lever", item.get("id"))
        time.sleep(0.02)

    print("Scanning Amazon...", flush=True)
    for q in ("", "engineer", "architect", "manager"):
        qs = urllib.parse.urlencode({
            "base_query": q,
            "loc_query": "Hyderabad, Telangana, India",
            "result_limit": 100,
            "offset": 0,
        })
        data, _ = get_json(f"https://www.amazon.jobs/en/search.json?{qs}")
        for item in (data or {}).get("jobs") or []:
            loc = f"{item.get('city_name','')} {item.get('location','')}"
            jid = item.get("id_icims") or item.get("id")
            add(jobs, "Amazon", item.get("title") or "", loc, f"https://www.amazon.jobs/en/jobs/{jid}", "Amazon", jid)

    print("Scanning Workday samples...", flush=True)
    payload = json.dumps({"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "Hyderabad"}).encode()
    for url, company in WORKDAY:
        data, status = get_json(url, data=payload, headers={"Content-Type": "application/json", "Accept": "application/json"})
        if status != 200 or not data:
            continue
        for item in (data.get("jobPostings") or []):
            loc = item.get("locationsText") or item.get("location") or ""
            title = item.get("title") or ""
            ext = item.get("externalPath") or ""
            add(jobs, company, title, loc, ext, "Workday")

    # Dedupe
    seen = set()
    unique = []
    for j in jobs:
        key = (j["company"].lower(), j["title"].lower(), j["job_id"] or j["url"][:80])
        if key in seen:
            continue
        seen.add(key)
        unique.append(j)

    named = [j for j in unique if j["bucket"] == "named_hub"]
    hyd = [j for j in unique if j["bucket"] == "hyderabad"]
    all_hub = named + hyd
    applyable = [j for j in all_hub if not j["skip_junior"]]
    senior = [j for j in applyable if j["senior"]]

    out = {
        "named_hub_exact": len(named),
        "hyderabad_listed": len(hyd),
        "all_in_scope": len(all_hub),
        "excluding_interns": len(applyable),
        "senior_architect_subset": len(senior),
        "by_company_all": Counter(j["company"] for j in applyable).most_common(),
        "by_ats": Counter(j["ats"] for j in applyable),
    }
    Path("data/job_counts.json").write_text(json.dumps({
        **{k: v for k, v in out.items() if k not in ("by_company_all", "by_ats")},
        "by_company_all": out["by_company_all"],
        "by_ats": dict(out["by_ats"]),
    }, indent=2), encoding="utf-8")
    Path("data/all_hub_jobs.json").write_text(json.dumps(applyable, indent=2), encoding="utf-8")
    Path("data/senior_hub_jobs.json").write_text(json.dumps(senior, indent=2), encoding="utf-8")

    print("\nCOUNTS")
    print("Exact Madhapur/Gachibowli/FD/HITEC text:", out["named_hub_exact"])
    print("Listed as Hyderabad (typical career-portal wording):", out["hyderabad_listed"])
    print("All in-scope unique jobs:", out["all_in_scope"])
    print("To apply (exclude intern/campus):", out["excluding_interns"])
    print("Senior/architect subset:", out["senior_architect_subset"])
    print("By ATS:", dict(out["by_ats"]))
    print("Top companies:")
    for name, n in out["by_company_all"][:20]:
        print(f"  {n:4} {name}")


if __name__ == "__main__":
    main()
