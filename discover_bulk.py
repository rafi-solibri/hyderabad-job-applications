"""Bulk-discover 100-300 Hyderabad tech jobs from official career/ATS feeds."""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CTX = ssl.create_default_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"

PRIORITY_TITLES = [
    "technical architect", "principal engineer", "principal software engineer",
    "staff software engineer", "staff engineer", "senior staff engineer",
    "principal architect", "software architect", "cloud architect",
    "application architect", "backend architect", "full stack architect",
    "fullstack architect", "technical lead", "lead software engineer",
    "engineering lead", "senior engineering manager", "senior backend engineer",
    "senior software engineer", "senior .net developer", "senior full stack developer",
    "senior fullstack developer", "solutions architect", "solution architect",
    "lead engineer", "principal software", "staff sde", "senior sde",
    ".net architect", "lead .net", "senior architect",
]
SKIP = re.compile(
    r"intern|internship|campus|graduate trainee|apprentice|recruiter|"
    r"account executive|sales specialist|sales manager|inside sales|"
    r"firmware|rtl |asic |analog |antenna|hardware design|"
    r"devops|devsecops|\bsre\b|site reliability|"
    r"salesforce|servicenow|guidewire|\bpega\b|sitecore|mean stack|"
    r"blockchain|gis\b|esri|mandarin|biztalk",
    re.I,
)
HYD = re.compile(
    r"hyderabad|telangana|\bhyd\b|madhapur|gachibowli|financial district|"
    r"nanakramguda|raidurg|kondapur|hite[c]?c|hitech|mindspace|"
    r"knowledge city|knowledge park|raheja",
    re.I,
)
HUB = re.compile(
    r"madhapur|gachibowli|financial district|nanakramguda|raidurg|"
    r"hite[c]?c city|hitech city|mindspace|knowledge city|knowledge park|raheja",
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
    "franklintempleton", "blackrock", "statestreet", "bnymellon", "ssnc",
    "hexaware", "mphasis", "virtusa", "brillio", "sonatasoftware",
    "birlasoft", "kpit", "ltts", "databricks", "snowflake", "twilio",
    "mongodb", "elastic", "confluent", "okta", "splunk", "docusign",
    "zoom", "atlassian", "gitlab", "github", "jfrog", "snyk", "wiz",
    "crowdstrike", "cloudflare", "datadog", "newrelic", "pagerduty",
    "servicenow", "salesforce", "nvidia", "qualcomm", "amd", "micron",
    "stripe", "coinbase", "intuit", "adobe", "autodesk", "ncr",
    "liveperson", "contentful", "grafana", "hashicorp", "paloaltonetworks",
    "sentinelone", "akamai", "boxinc", "dropbox", "figma", "notion",
    "canva", "rippling", "toast", "doordash", "airbnb", "expedia",
    "paypal", "visa", "mastercard", "capitalone", "veeva", "iqvia",
    "appian", "asana", "intercom", "airtable", "anthropic", "openai",
    "scaleai", "esri", "veracode", "vonage", "sofi", "plaid", "affirm",
    "robinhood", "block", "servicetitan", "cloudera", "palantir",
    "darwinbox", "yellowai", "observeai", "zenoti", "icertis", "coupa",
    "e2open", "blueyonder", "kinaxis", "manhattan", "jda", "o9",
    "walmart", "uber", "ola", "cred", "groww", "zerodha", "upstox",
    "payu", "cashfree", "juspay", "setu", "slice", "bharatpe",
    "sharechat", "dream11", "games24x7", "quantiphi", "fractal",
    "coforge", "ltts", "cyientdlm", "oracle", "workday", "cisco",
    "intel", "dell", "hp", "honeywell", "siemens", "schneider",
    "optum", "unitedhealth", "iqvia", "veeva", "philips", "medtronic",
    "novartis", "gsk", "pfizer", "amgen", "boehringer",
    "thomsonreuters", "wolterskluwer", "spglobal", "moodys", "fitch",
    "experian", "transunion", "equifax", "fico",
    "invesco", "ssctech", "fiserv", "fisglobal", "worldpay", "ncr",
    "veritas", "commvault", "netapp", "purestorage", "nutanix",
    "vmware", "broadcom", "redhat", "progress", "tibco", "mulesoft",
    "boomi", "informatica", "talend", "alteryx", "qlik", "tableau",
    "microstrategy", "sasinstitute", "teradata",
    "thoughtspot", "fivetran", "dbtlabs", "airbytehq", "hextechnologies",
    "hubspot", "zendesk", "braze", "klaviyo", "iterable",
    "shopify", "squarespace", "webflow", "pinterest", "reddit",
    "discord", "roblox", "lyft", "instacart", "deel", "gusto",
    "checkr", "sentry", "launchdarkly", "statsig", "posthog",
    "sprinklr", "nium", "adyen", "airwallex", "wise", "klarna",
    "calendly", "miro", "qualtrics", "ukg", "toasttab",
    "revolut", "checkoutcom", "clerkdev", "supabase", "vercel",
]
LEVER = [
    "keyloop", "dnb", "cprime", "ttecdigital", "ncrvoyix", "meesho",
    "freshworks", "mindtickle", "phonepe", "razorpay", "swiggy", "zomato",
    "flipkart", "postman", "browserstack", "chargebee", "innovaccer",
    "whatfix", "gupshup", "practo", "cyient", "ltimindtree", "hexaware",
    "mphasis", "virtusa", "persistent", "valuelabs", "epam", "globallogic",
    "broadridge", "factset", "cotiviti", "wellsfargo", "jpmorganchase",
    "goldmansachs", "deloitte", "kpmg", "capgemini", "accenture",
    "cognizant", "infosys", "wipro", "hcltech", "techmahindra",
    "servicenow", "salesforce", "oracle", "nvidia", "qualcomm", "amd",
    "micron", "pega", "uipath", "ncr", "genpact", "brillio", "sonata",
    "netflix", "spotify", "palantir", "notion", "figma", "canva",
    "rippling", "brex", "plaid", "affirm", "robinhood", "coinbase",
    "databricks", "snowflake", "confluent", "hashicorp", "elastic",
    "mongodb", "twilio", "okta", "docusign", "atlassian", "gitlab",
    "crowdstrike", "zscaler", "cloudflare", "datadog", "newrelic",
    "pagerduty", "grafana", "thoughtworks", "adp", "optum",
]
APPLIED = {
    ("crunchyroll", "staff software engineer"),
    ("crunchyroll", "staff software engineer, ai/ml"),
    ("inovalon", "staff software development engineer l5"),
    ("highradius", "java architect"),
    ("zscaler", "sr. staff software development engineer - java/go + distributed systems"),
    ("keyloop", "principle software architect"),
}


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


def title_rank(title: str) -> int:
    t = (title or "").lower()
    if SKIP.search(t):
        return 0
    for i, phrase in enumerate(PRIORITY_TITLES):
        if phrase in t:
            return 100 - i
    if re.search(r"\b(architect|principal|staff|lead|senior)\b", t) and re.search(
        r"engineer|developer|architect|\.net|backend|full.?stack", t
    ):
        return 20
    return 0


def loc_ok(location: str) -> bool:
    loc = location or ""
    if HYD.search(loc):
        return True
    if re.search(r"remote|work from home|\bwfh\b|anywhere", loc, re.I) and re.search(
        r"\bindia\b|telangana", loc, re.I
    ):
        return True
    return False


def loc_bonus(location: str) -> int:
    loc = location or ""
    score = 0
    if HUB.search(loc):
        score += 30
    if re.search(r"remote", loc, re.I) and HYD.search(loc):
        score += 10
    if re.search(r"hybrid", loc, re.I) and HYD.search(loc):
        score += 10
    if HYD.search(loc):
        score += 15
    return score


def add(jobs, company, title, location, url, ats, job_id=""):
    rank = title_rank(title)
    if rank <= 0 or not loc_ok(location):
        return
    jobs.append({
        "company": company,
        "title": (title or "").strip(),
        "location": (location or "").strip(),
        "url": url or "",
        "ats": ats,
        "job_id": str(job_id or ""),
        "title_score": rank,
        "location_score": loc_bonus(location),
        "score": rank + loc_bonus(location),
        "already_applied": (company.lower(), (title or "").strip().lower()) in APPLIED,
    })


def main():
    jobs = []
    print("Greenhouse...", flush=True)
    for token in GH:
        data, status = get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            loc = (item.get("location") or {}).get("name") or ""
            add(jobs, token, item.get("title") or "", loc, item.get("absolute_url") or "", "Greenhouse", item.get("id"))
        time.sleep(0.02)

    print("Lever...", flush=True)
    for company in LEVER:
        data, status = get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
        if status != 200 or not isinstance(data, list):
            continue
        for item in data:
            cats = item.get("categories") or {}
            loc = str(cats.get("location") or "")
            if isinstance(cats.get("allLocations"), list):
                loc = " ".join(str(x) for x in cats["allLocations"]) + " " + loc
            commitment = str(cats.get("commitment") or "")
            loc = f"{loc} {commitment}"
            add(jobs, company, item.get("text") or "", loc, item.get("hostedUrl") or "", "Lever", item.get("id"))
        time.sleep(0.02)

    print("Ashby...", flush=True)
    for token in (
        "ramp", "mercury", "linear", "vercel", "supabase", "clerk",
        "perplexityai", "togetherai", "groq", "huggingface",
        "wandb", "pinecone", "posthog", "webflow", "deel",
        "remote", "gusto", "checkr", "launchdarkly", "statsig",
        "sentry", "fivetran", "dbt", "hex", "airbyte",
        "brex", "plaid", "anthropic", "resend", "cal",
    ):
        data, status = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            loc = item.get("location") or ""
            if isinstance(loc, dict):
                loc = " ".join(str(loc.get(k) or "") for k in ("location", "city", "region", "country", "address"))
            if item.get("isRemote"):
                loc = f"{loc} Remote"
            add(
                jobs,
                token,
                item.get("title") or "",
                loc,
                item.get("jobUrl") or item.get("applyUrl") or "",
                "Ashby",
                item.get("id") or item.get("jobId") or "",
            )
        time.sleep(0.03)

    print("Amazon...", flush=True)
    for q in (
        "technical architect", "principal engineer", "staff engineer",
        "senior software engineer", "software architect", "technical lead",
        ".NET", "backend",
    ):
        qs = urllib.parse.urlencode({
            "base_query": q,
            "loc_query": "Hyderabad, Telangana, India",
            "result_limit": 100,
            "offset": 0,
        })
        data, _ = get_json(f"https://www.amazon.jobs/en/search.json?{qs}")
        for item in (data or {}).get("jobs") or []:
            loc = f"{item.get('city_name','')} {item.get('location','')} {item.get('normalized_location','')}"
            jid = item.get("id_icims") or item.get("id")
            add(jobs, "Amazon", item.get("title") or "", loc, f"https://www.amazon.jobs/en/jobs/{jid}", "Amazon", jid)
        time.sleep(0.2)

    print("Workday samples...", flush=True)
    payload = json.dumps({"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "Hyderabad engineer"}).encode()
    workday = [
        ("https://micron.wd1.myworkdayjobs.com/wday/cxs/micron/External/jobs", "Micron"),
        ("https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs", "NVIDIA"),
        ("https://qualcomm.wd5.myworkdayjobs.com/wday/cxs/qualcomm/External/jobs", "Qualcomm"),
        ("https://amd.wd1.myworkdayjobs.com/wday/cxs/amd/careers/jobs", "AMD"),
        ("https://intel.wd1.myworkdayjobs.com/wday/cxs/intel/external/jobs", "Intel"),
        ("https://cisco.wd5.myworkdayjobs.com/wday/cxs/cisco/cisco_careers/jobs", "Cisco"),
        ("https://dell.wd1.myworkdayjobs.com/wday/cxs/dell/External/jobs", "Dell"),
        ("https://adp.wd5.myworkdayjobs.com/wday/cxs/adp/External/jobs", "ADP"),
        ("https://optum.wd5.myworkdayjobs.com/wday/cxs/optum/OptumCareers/jobs", "Optum"),
        ("https://walmart.wd5.myworkdayjobs.com/wday/cxs/walmart/WalmartExternal/jobs", "Walmart"),
        ("https://jpmorgan.wd5.myworkdayjobs.com/wday/cxs/jpmorgan/jpmcjobs/jobs", "JPMorgan"),
        ("https://wellsfargo.wd5.myworkdayjobs.com/wday/cxs/wellsfargo/External/jobs", "WellsFargo"),
        ("https://servicenow.wd1.myworkdayjobs.com/wday/cxs/servicenow/now-careers/jobs", "ServiceNow"),
    ]
    for url, company in workday:
        data, status = get_json(url, data=payload, headers={"Content-Type": "application/json"})
        if status != 200 or not data:
            continue
        for item in data.get("jobPostings") or []:
            loc = item.get("locationsText") or ""
            add(jobs, company, item.get("title") or "", loc, item.get("externalPath") or "", "Workday")

    seen = set()
    unique = []
    for j in jobs:
        key = (j["company"].lower(), j["title"].lower(), j["job_id"] or j["url"][:80])
        if key in seen:
            continue
        seen.add(key)
        unique.append(j)
    unique.sort(key=lambda j: (-j["score"], j["company"], j["title"]))

    open_jobs = [j for j in unique if not j["already_applied"]]
    # Keep 100-300
    batch = open_jobs[:300]
    Path("data/discovery_batch.json").write_text(json.dumps(batch, indent=2), encoding="utf-8")
    Path("data/discovery_all_matched.json").write_text(json.dumps(unique, indent=2), encoding="utf-8")

    print(f"\nMatched unique: {len(unique)}")
    print(f"Already applied in match set: {sum(1 for j in unique if j['already_applied'])}")
    print(f"Open and ranked: {len(open_jobs)}")
    print(f"This discovery batch (cap 300): {len(batch)}")
    print("By ATS:", dict(Counter(j["ats"] for j in batch)))
    print("Top companies:", Counter(j["company"] for j in batch).most_common(15))
    print("\nTOP 40")
    for i, j in enumerate(batch[:40], 1):
        print(f"{i:2} [{j['score']:3}] {j['company'][:16]:16} {j['title'][:62]:62} {j['location'][:40]}")


if __name__ == "__main__":
    main()
