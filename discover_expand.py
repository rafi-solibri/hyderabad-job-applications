"""Second discovery pass: more titles, more official boards, Amazon pagination."""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

CTX = ssl.create_default_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"
HYD = re.compile(r"hyderabad|telangana|\bhyd\b|madhapur|gachibowli|financial district|raidurg|mindspace|knowledge city|hite[c]?c", re.I)
SKIP = re.compile(r"intern|internship|campus|graduate trainee|apprentice|recruiter|account executive|inside sales", re.I)
TITLE = re.compile(
    r"technical architect|principal (software |tech )?engineer|principal architect|"
    r"staff (software )?engineer|senior staff|software architect|cloud architect|"
    r"application architect|backend architect|full.?stack architect|solutions? architect|"
    r"technical lead|lead software|engineering lead|engineering manager|"
    r"senior (backend |software |full.?stack )?(engineer|developer)|"
    r"senior \.net|lead \.net|\.net (architect|lead|developer)|"
    r"sde ?[iii3]|sde3|software development engineer|"
    r"sr\.? (software|backend|full.?stack)|lead engineer|lead developer|"
    r"principal sde|staff sde|senior sde",
    re.I,
)
APPLIED = {
    ("crunchyroll", "staff software engineer"),
    ("crunchyroll", "staff software engineer, ai/ml"),
    ("inovalon", "staff software development engineer l5"),
    ("highradius", "java architect"),
    ("zscaler", "sr. staff software development engineer - java/go + distributed systems"),
    ("keyloop", "principle software architect"),
}
EXTRA_GH = [
    "redwoodsoftware", "highspot", "matillion", "ncrvoyix", "ukg", "workday",
    "servicenow", "salesforce", "twilio", "mongodb", "elastic", "confluent",
    "databricks", "snowflake", "okta", "splunk", "docusign", "atlassian",
    "gitlab", "datadog", "newrelic", "pagerduty", "cloudflare", "crowdstrike",
    "zscaler", "snyk", "jfrog", "hashicorp", "paloaltonetworks",
    "freshworks", "postman", "browserstack", "chargebee", "whatfix",
    "mindtickle", "innovaccer", "o9solutions", "gupshup", "highradius",
    "inovalon", "crunchyroll", "phonepe", "razorpay", "swiggy", "zomato",
    "flipkart", "meesho", "practo", "cyient", "persistent", "epam",
    "broadridge", "factset", "cotiviti", "pega", "uipath", "thoughtworks",
    "globallogic", "informatica", "opentext", "invesco", "blackrock",
    "ssnc", "hexaware", "mphasis", "virtusa", "brillio", "kpit", "ltts",
    "nvidia", "qualcomm", "amd", "micron", "adobe", "intuit", "autodesk",
    "veeva", "iqvia", "appian", "liveperson", "vonage", "veracode",
    "contentful", "grafana", "boxinc", "dropbox", "zoom", "doordash",
    "airbnb", "expedia", "paypal", "visa", "mastercard", "capitalone",
    "stripe", "coinbase", "sofi", "plaid", "affirm", "robinhood",
    "asana", "intercom", "airtable", "anthropic", "openai",
    "ncr", "adp", "optum", "unitedhealthgroup",
]
EXTRA_LEVER = [
    "highspot", "matillion", "redwood", "ttecdigital", "keyloop", "dnb",
    "cprime", "ncrvoyix", "meesho", "freshworks", "mindtickle",
    "phonepe", "razorpay", "swiggy", "zomato", "flipkart", "postman",
    "browserstack", "chargebee", "innovaccer", "whatfix", "gupshup",
    "practo", "cyient", "epam", "globallogic", "valuelabs", "persistent",
    "hexaware", "mphasis", "virtusa", "broadridge", "factset", "cotiviti",
    "wellsfargo", "jpmorganchase", "goldmansachs", "deloitte", "kpmg",
    "capgemini", "accenture", "cognizant", "infosys", "wipro",
    "techmahindra", "hcltech", "ltimindtree", "genpact", "brillio",
    "pega", "uipath", "ncr", "adp", "optum", "thoughtworks",
    "databricks", "snowflake", "mongodb", "elastic", "twilio", "okta",
    "atlassian", "gitlab", "datadog", "crowdstrike", "zscaler",
    "cloudflare", "newrelic", "pagerduty", "grafana", "confluent",
    "hashicorp", "docusign", "netflix", "spotify", "palantir",
    "rippling", "brex", "plaid", "affirm", "robinhood", "coinbase",
    "notion", "figma", "canva", "doordash",
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


def keep(title, location) -> bool:
    if SKIP.search(title or ""):
        return False
    if not HYD.search(location or ""):
        return False
    return bool(TITLE.search(title or ""))


def row(company, title, location, url, ats, job_id=""):
    return {
        "company": company,
        "title": (title or "").strip(),
        "location": (location or "").strip(),
        "url": url or "",
        "ats": ats,
        "job_id": str(job_id or ""),
        "already_applied": (company.lower(), (title or "").strip().lower()) in APPLIED,
    }


def main():
    jobs = []
    existing = json.loads(Path("data/discovery_all_matched.json").read_text(encoding="utf-8"))
    jobs.extend(existing)

    print("Extra Greenhouse...", flush=True)
    for token in EXTRA_GH:
        data, status = get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        if status != 200 or not data:
            continue
        n = 0
        for item in data.get("jobs") or []:
            loc = (item.get("location") or {}).get("name") or ""
            title = item.get("title") or ""
            if keep(title, loc):
                jobs.append(row(token, title, loc, item.get("absolute_url") or "", "Greenhouse", item.get("id")))
                n += 1
        if n:
            print(f"  GH {token}: {n}", flush=True)
        time.sleep(0.02)

    print("Extra Lever...", flush=True)
    for company in EXTRA_LEVER:
        data, status = get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
        if status != 200 or not isinstance(data, list):
            continue
        n = 0
        for item in data:
            cats = item.get("categories") or {}
            loc = str(cats.get("location") or "")
            if isinstance(cats.get("allLocations"), list):
                loc = " ".join(str(x) for x in cats["allLocations"]) + " " + loc
            title = item.get("text") or ""
            if keep(title, loc):
                jobs.append(row(company, title, loc, item.get("hostedUrl") or "", "Lever", item.get("id")))
                n += 1
        if n:
            print(f"  LV {company}: {n}", flush=True)
        time.sleep(0.02)

    print("Amazon pagination...", flush=True)
    for q in ("software engineer", "software development engineer", "architect", "technical lead"):
        for offset in (0, 100, 200):
            qs = urllib.parse.urlencode({
                "base_query": q,
                "loc_query": "Hyderabad, Telangana, India",
                "result_limit": 100,
                "offset": offset,
            })
            data, _ = get_json(f"https://www.amazon.jobs/en/search.json?{qs}")
            hits = 0
            for item in (data or {}).get("jobs") or []:
                loc = f"{item.get('city_name','')} {item.get('location','')}"
                title = item.get("title") or ""
                if keep(title, loc):
                    jid = item.get("id_icims") or item.get("id")
                    jobs.append(row("Amazon", title, loc, f"https://www.amazon.jobs/en/jobs/{jid}", "Amazon", jid))
                    hits += 1
            print(f"  Amazon q={q!r} offset={offset}: +{hits}", flush=True)
            if not (data or {}).get("jobs"):
                break
            time.sleep(0.25)

    # Known extra postings from search
    extras = [
        row("redwoodsoftware", "Principal Software Engineer", "Hyderabad, Telangana, India",
            "https://job-boards.greenhouse.io/redwoodsoftware/jobs/4243672009", "Greenhouse", "4243672009"),
        row("highspot", "Principal Software Development Engineer", "India - Hyderabad",
            "https://jobs.lever.co/highspot/b7c1a8d2-2301-482d-9099-67d1ac8827da", "Lever", "b7c1a8d2-2301-482d-9099-67d1ac8827da"),
        row("matillion", "Principal Software Engineer - Release Engineering", "Hyderabad",
            "https://jobs.lever.co/matillion/497016aa-9df1-48fe-be3b-0fae3b5d2581", "Lever", "497016aa-9df1-48fe-be3b-0fae3b5d2581"),
    ]
    jobs.extend(extras)

    seen = set()
    unique = []
    for j in jobs:
        key = (j["company"].lower(), j["title"].lower(), str(j.get("job_id") or j.get("url", "")[:80]))
        if key in seen:
            continue
        seen.add(key)
        unique.append(j)

    open_jobs = [j for j in unique if not j.get("already_applied")]
    batch = open_jobs[:300]
    Path("data/discovery_batch.json").write_text(json.dumps(batch, indent=2), encoding="utf-8")
    Path("data/discovery_all_matched.json").write_text(json.dumps(unique, indent=2), encoding="utf-8")
    print(f"\nMatched unique: {len(unique)}")
    print(f"Open batch: {len(batch)}")
    print("By ATS:", dict(Counter(j["ats"] for j in batch)))
    print("Top companies:", Counter(j["company"] for j in batch).most_common(20))
    for i, j in enumerate(batch[:30], 1):
        print(f"{i:2} {j['company'][:18]:18} {j['title'][:64]:64} {j['location'][:36]}")


if __name__ == "__main__":
    main()
