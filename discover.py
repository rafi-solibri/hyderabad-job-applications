"""Discover Hyderabad architect roles from official company career APIs."""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "discovered_jobs.json"
CTX = ssl.create_default_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

TITLE_RE = re.compile(
    r"architect|principal engineer|staff engineer|principal software|technical lead|"
    r"engineering lead|staff software|\.net lead|solution architect",
    re.I,
)
SKIP_RE = re.compile(
    r"intern|campus|graduate|firmware|hardware|rtl|asic|analog|rf |antenna|"
    r"sales engineer|account executive|recruiter|intern ",
    re.I,
)
HYD_RE = re.compile(
    r"hyderabad|gachibowli|madhapur|financial district|hitec|hitech|"
    r"nanakramguda|kondapur|raidurg|telangana",
    re.I,
)

GREENHOUSE = [
    "databricks", "snowflake", "twilio", "mongodb", "elastic", "confluent",
    "hashicorp", "paloaltonetworks", "crowdstrike", "okta", "splunk",
    "docusign", "zoom", "dropbox", "boxinc", "figma", "notion", "canva",
    "rippling", "toast", "doordash", "airbnb", "expedia", "paypal",
    "visa", "mastercard", "capitalone", "inovalon", "veeva", "iqvia",
    "thoughtworks", "gitlab", "github", "atlassian", "jfrog", "snyk",
    "wiz", "sentinelone", "zscaler", "cloudflare", "akamai", "contentful",
    "grafana", "datadog", "newrelic", "pagerduty", "launchdarkly",
    "crunchyroll", "liveperson", "ncrvoyix", "ncr", "adp", "stripe",
    "plaid", "brex", "affirm", "sofi", "robinhood", "coinbase",
    "block", "square", "intuit", "servicetitan", "uipath", "pega",
    "appian", "informatica", "cloudera", "palantir", "asana", "monday",
    "smartsheet", "zendesk", "freshworks", "hubspot", "salesloft",
    "gong", "outreach", "intercom", "airtable", "coda", "miro",
    "lucid", "notionlabs", "openai", "anthropic", "cohere",
    "scaleai", "huggingface", "weightsandbiases", "anyscale",
    "lamresearch", "appliedmaterials", "kla", "synopsys", "cadence",
    "ansys", "autodesk", "ptc", "siemens", "hexagon", "bentley",
    "trimble", "esri", "servicenow", "workday", "sap", "oracle",
    "adobe", "intuitinc", "broadridge", "factset", "spglobal",
    "moodys", "fitch", "morningstar", "blackrock", "statestreet",
    "bnymellon", "ssnc", "fiserv", "fisglobal", "worldpay",
    "firstdata", "ncrcorporation", "dieboldnixdorf", "toshibaglobal",
    "epson", "honeywell", "geaerospace", "gevernova", "gehealthcare",
    "siemenshealthineers", "philips", "medtronic", "bostonscientific",
    "abbott", "jnj", "pfizer", "novartis", "gsk", "astrazeneca",
    "amgen", "bms", "merck", "sanofi", "roche", "genentech",
    "optum", "unitedhealthgroup", "uhg", "cigna", "anthem", "elevance",
    "humana", "cvshealth", "changehealthcare", "cotiviti", "evolent",
    "agilon", "privia", "oscar", "brighthealth", "centene",
    "epam", "globallogic", "valuelabs", "valuemomentum", "persistent",
    "ltimindtree", "hexaware", "mphasis", "virtusa", "cognizant",
    "infosys", "wipro", "tcs", "hcltech", "techmahindra", "capgemini",
    "accenture", "ibm", "dell", "hp", "hpe", "cisco", "juniper",
    "arista", "vmware", "broadcom", "redhat", "nvidia", "amd",
    "intel", "qualcomm", "micron", "analogdevices", "ti", "nxp",
    "onsemi", "microchip", "western-digital", "seagate", "sandisk",
    "samsung", "lg", "sony", "panasonic", "bosch", "continental",
    "harman", "aptiv", "visteon", "valeo", "magna", "zf",
    "mercedesbenz", "bmw", "volkswagen", "hyundai", "kia",
    "renault", "nissan", "mahindra", "tatamotors",
    "wells-fargo", "jpmorgan", "jpmorganchase", "goldmansachs",
    "morganstanley", "bankofamerica", "citi", "barclays", "hsbc",
    "dbs", "standardchartered", "deutschebank", "ubsgroup", "credit-suisse",
    "charles-schwab", "fidelity", "vanguard", "invesco", "franklintempleton",
    "blackstone", "kkr", "carlyle", "apollo",
    "deloitte", "pwc", "ey", "kpmg", "genpact", "exlservice",
    "wiprodigital", "thoughtspot", "looker", "tableau", "qlik",
    "microstrategy", "sas", "teradata", "informatica",
    "uipathinc", "automationanywhere", "blueprism",
    "checkmarx", "veracode", "snykinc", "sonatype",
    "fortinet", "checkpoint", "paloalto", "crowdstrikeinc",
    "rapid7", "tenable", "qualys", "proofpoint", "mimecast",
    "ringcentral", "vonage", "messagebird", "sendgrid",
    "webex", "slack", "discord", "spotify", "netflix",
    "disney", "warnerbros", "paramount", "nbcuniversal",
    "walmart", "target", "costco", "homedepot", "lowes",
    "bestbuy", "macys", "nordstrom", "gapinc", "nike",
    "adidas", "underarmour", "lululemon",
    "uber", "lyft", "doordashinc", "instacart", "grubhub",
    "swiggy", "zomato", "phonepe", "paytm", "razorpay",
    "cred", "groww", "zerodha", "upstox",
    "flipkart", "myntra", "meesho", "nykaa",
    "ola", "olacabs", "rapido",
    "byjus", "unacademy", "vedantu",
    "freshworksinc", "zoho", "chargebee", "postman",
    "browserstack", "lambdatest", "browserbase",
    "mindtickle", "whatfix", "gupshup", "innovaccer",
    "o9solutions", "highradius", "ihealth", "practo",
    "pharmeasy", "1mg", "netmeds",
    "cyient", "hcl", "ltimindtreeinc",
    " PersistentSystems", "sonata", "maveric", "cigniti",
    "valueabs", "valueMomentum", "techmahindrainc",
    "brillio", "ltim", "mindtree", "larsentoubro",
    "ltts", "ltimind", "birlasoft", "niit",
    "hexawaretech", "mphasislimited", "sonatasoftware",
    "kpit", "tataelxsi", "tatacommunications",
    "jio", "reliancejio", "airtel", "vodafoneidea",
    "bsnl", "railtel",
]

LEVER = [
    "netflix", "spotify", "palantir", "anduril", "scaleai",
    "notion", "figma", "canva", "rippling", "brex", "plaid",
    "affirm", "robinhood", "coinbase", "stripe", "openai",
    "anthropic", "databricks", "snowflake", "confluent",
    "hashicorp", "elastic", "mongodb", "twilio", "okta",
    "docusign", "box", "dropbox", "zoom", "atlassian",
    "gitlab", "github", "jfrog", "snyk", "wiz",
    "crowdstrike", "paloaltonetworks", "zscaler", "cloudflare",
    "datadog", "newrelic", "pagerduty", "grafana",
    "uipath", "informatica", "thoughtworks", "epam",
    "globallogic", "ncr", "adp", "optum",
    "wellsfargo", "jpmorganchase", "goldmansachs",
    "deloitte", "accenture", "capgemini",
    "phonepe", "razorpay", "cred", "groww", "swiggy",
    "zomato", "flipkart", "meesho", "ola",
    "freshworks", "postman", "browserstack", "chargebee",
    "highradius", "innovaccer", "o9solutions", "whatfix",
    "mindtickle", "gupshup", "practo",
    "cyient", "ltimindtree", "hexaware", "mphasis",
    "virtusa", "persistent", "valuelabs",
]

ASHBY = [
    "openai", "anthropic", "notion", "linear", "vercel",
    "cursor", "anysphere", "rippling", "mercury", "brex",
    "ramp", "plain", "resend", "supabase", "neon",
]


def get_json(url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 25):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8", errors="replace")), resp.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception:
        return None, 0


def job(company, title, location, url, ats, job_id="", description=""):
    return {
        "company": company,
        "title": title.strip(),
        "location": (location or "").strip(),
        "url": url,
        "ats": ats,
        "job_id": str(job_id or ""),
        "description": (description or "")[:2000],
    }


def loc_ok(text: str) -> bool:
    return bool(HYD_RE.search(text or ""))


def title_ok(title: str) -> bool:
    if SKIP_RE.search(title or ""):
        return False
    return bool(TITLE_RE.search(title or ""))


def discover_amazon():
    jobs = []
    for q in ("technical architect", "principal engineer", "solutions architect", "staff engineer .NET"):
        qs = urllib.parse.urlencode({
            "base_query": q,
            "loc_query": "Hyderabad, Telangana, India",
            "result_limit": 50,
            "offset": 0,
        })
        data, _ = get_json(f"https://www.amazon.jobs/en/search.json?{qs}")
        if not data:
            continue
        for item in data.get("jobs") or []:
            title = item.get("title") or ""
            loc = f"{item.get('city_name','')} {item.get('location','')} {item.get('normalized_location','')}"
            if not loc_ok(loc) or not title_ok(title):
                continue
            jid = item.get("id_icims") or item.get("id")
            jobs.append(job(
                "Amazon", title, loc,
                f"https://www.amazon.jobs/en/jobs/{item.get('id_icims') or item.get('id')}",
                "Amazon", jid, item.get("description_short") or "",
            ))
        time.sleep(0.3)
    return jobs


def discover_microsoft():
    payload = json.dumps({
        "locale": "en_us",
        "domain": "https://jobs.careers.microsoft.com",
        "offset": 0,
        "query": "architect OR principal engineer",
        "filters": [
            {"field": "country", "values": ["India"]},
            {"field": "city", "values": ["Hyderabad"]},
        ],
        "limit": 50,
    }).encode()
    data, _ = get_json(
        "https://gcsservices.careers.microsoft.com/search/api/v1/search",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    jobs = []
    items = ((data or {}).get("operationResult") or {}).get("result") or {}
    for item in items.get("jobs") or []:
        title = item.get("title") or ""
        props = item.get("properties") or {}
        loc = " ".join(str(x) for x in [
            props.get("primaryLocation"),
            props.get("city"),
            " ".join(props.get("locations") or []),
        ])
        if not loc_ok(loc) or not title_ok(title):
            continue
        jid = item.get("jobId")
        slug = urllib.parse.quote(title.replace(" ", "-"))
        jobs.append(job(
            "Microsoft", title, loc,
            f"https://jobs.careers.microsoft.com/global/en/job/{jid}/{slug}",
            "Microsoft", jid, (item.get("description") or "")[:1500],
        ))
    return jobs


def discover_google():
    qs = urllib.parse.urlencode({
        "q": "architect OR principal engineer",
        "location": "Hyderabad, India",
        "page_size": 20,
    })
    data, _ = get_json(f"https://careers.google.com/api/v3/search/?{qs}")
    jobs = []
    for item in (data or {}).get("jobs") or []:
        title = ((item.get("title") or {}).get("text") if isinstance(item.get("title"), dict) else item.get("title")) or ""
        locs = " ".join(
            (l.get("display") or l.get("loc") or "")
            for l in (item.get("locations") or [])
        ) or str(item.get("location") or "")
        if not loc_ok(locs) or not title_ok(str(title)):
            continue
        jid = item.get("id") or item.get("job_id")
        jobs.append(job("Google", str(title), locs, item.get("apply_url") or f"https://www.google.com/about/careers/applications/jobs/results/{jid}", "Google", jid))
    return jobs


def discover_greenhouse():
    jobs = []
    for token in GREENHOUSE:
        data, status = get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            title = item.get("title") or ""
            loc = (item.get("location") or {}).get("name") or ""
            offices = " ".join(o.get("name", "") for o in (item.get("offices") or []))
            blob = f"{loc} {offices} {title}"
            if not loc_ok(blob) or not title_ok(title):
                continue
            jobs.append(job(
                token, title, loc or offices, item.get("absolute_url") or "",
                "Greenhouse", item.get("id"), token,
            ))
        time.sleep(0.05)
    return jobs


def discover_lever():
    jobs = []
    for company in LEVER:
        data, status = get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
        if status != 200 or not isinstance(data, list):
            continue
        for item in data:
            title = item.get("text") or ""
            cats = item.get("categories") or {}
            loc = " ".join(str(x) for x in [cats.get("location"), cats.get("allLocations"), item.get("country")])
            if isinstance(cats.get("allLocations"), list):
                loc = " ".join(cats.get("allLocations") or []) + " " + str(cats.get("location") or "")
            if not loc_ok(loc) or not title_ok(title):
                continue
            jobs.append(job(
                company, title, loc, item.get("hostedUrl") or item.get("applyUrl") or "",
                "Lever", item.get("id"),
            ))
        time.sleep(0.05)
    return jobs


def discover_ashby():
    jobs = []
    for company in ASHBY:
        data, status = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{company}")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            title = item.get("title") or ""
            loc = " ".join(
                (l.get("location") or l.get("name") or "")
                for l in (item.get("address") and [item.get("address")] or item.get("locations") or [])
            ) or str(item.get("location") or "")
            blob = f"{loc} {item.get('locationName','')} {json.dumps(item.get('locationInfo') or {})}"
            if not loc_ok(blob) or not title_ok(title):
                continue
            jobs.append(job(
                company, title, blob[:120], item.get("jobUrl") or "",
                "Ashby", item.get("id"),
            ))
    return jobs


def dedupe(jobs):
    seen = set()
    out = []
    for j in jobs:
        key = (j["company"].lower(), j["title"].lower(), re.sub(r"\W+", "", j["url"].lower())[:80])
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


def main():
    all_jobs = []
    for name, fn in [
        ("amazon", discover_amazon),
        ("microsoft", discover_microsoft),
        ("google", discover_google),
        ("greenhouse", discover_greenhouse),
        ("lever", discover_lever),
        ("ashby", discover_ashby),
    ]:
        print(f"Discovering {name}...", flush=True)
        try:
            found = fn()
        except Exception as e:
            print(f"  {name} failed: {e}", flush=True)
            found = []
        print(f"  {name}: {len(found)} matches", flush=True)
        all_jobs.extend(found)

    all_jobs = dedupe(all_jobs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(all_jobs, indent=2), encoding="utf-8")
    print(f"\nTotal unique jobs: {len(all_jobs)}")
    for j in all_jobs:
        print(f"- [{j['ats']}] {j['company']}: {j['title']} | {j['location']}")


if __name__ == "__main__":
    main()
