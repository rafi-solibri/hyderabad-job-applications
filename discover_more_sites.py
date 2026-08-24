"""Extra portals: Microsoft, Google, SmartRecruiters, Workable, more Workday/GH/Ashby."""
from __future__ import annotations

import json
import time
import urllib.parse
from collections import Counter
from datetime import date
from pathlib import Path

import apply_now
import discover_bulk
import discover_final as d
import discover_portals

ROOT = Path(__file__).resolve().parent

EXTRA_GH = [
    "anduril", "spacelift", "temporalio", "hashicorp", "clickhouse",
    "planetscale", "neon", "cockroachlabs", "yugabyte", "pingcap",
    "redis", "redislabs", "datastax", "scylladb", "singleStore",
    "starburst", "dremio", "imply", "firebolt", "rockset",
    "census", "hightouch", "rudderstack", "segment", "amplitude",
    "mixpanel", "heap", "pendo", "fullstory", "logrocket",
    "hotjar", "contentsquare", "quantummetric",
    "gong", "outreach", "salesloft", "apolloio", "6sense",
    "demandbase", "zoominfo", "clearbit",
    "navan", "expensify", "brex", "ramp", "melio",
    "billcom", "tipalti", "airbase", "ziphq",
    "ironclad", "docusign", "hellosign", "pandadoc",
    "notionhq", "coda", "roamresearch",
    "retool", "appsmith", "tooljet",
    "n8n", "zapier", "make", "trayio",
    "temporal", "prefab", "launchdarkly",
    "splitio", "unleash", "configcat",
    "snyk", "semgrep", "socket", "endorsed",
    "wiz", "orca", "lacework", "aqua",
    "sysdig", "rapid7", "tenable", "qualys",
    "crowdstrike", "sentinelone",
    "cloudflare", "fastly", "edgio",
    "twilio", "messagebird", "plivo",
    "freshdesk", "freshworks", "zoho",
    "keka", "greytip", "darwinbox",
    "leadsquared", "exotel", "knowlarity",
    "browserstack", "lambdatest", "saucelabs",
    "testsigma", "accelq",
    "postman", "insomnia", "konghq",
    "gravitee", "tyk",
    "hasura", "supabase", "appwrite", "nhost",
    "vercel", "netlify", "render", "flyio",
    "digitalocean", "linode", "vultr",
    "ovh", "hetzner",
    "uipath", "automationanywhere", "blueprism",
    "ssnc", "broadridge", "fiserv",
    "nium", "rapyd", "checkout", "adyen",
    "airwallex", "wise", "revolut",
    "monzo", "nubank", "klarna",
    "afterpay", "sezzle",
    "shopify", "bigcommerce", "magento",
    "woocommerce", "sfcc",
    "unity", "unreal", "epicgames",
    "roblox", "discord", "reddit",
    "pinterest", "snap", "spotify",
    "soundcloud", "deezer",
    "bookingcom", "agoda", "makemytrip",
    "goibibo", "ixigo", "yatra",
    "oyorooms", "treebo",
    "swiggy", "zomato", "eatclub",
    "dunzo", "shadowfax", "delhivery",
    "bluedart", "ecomexpress",
    "policybazaar", "acko", "digit",
    "coverfox",
    "zerodha", "groww", "upstox", "angelone",
    "5paisa", "icicidirect",
    "phonepe", "googlepay", "bharatpe",
    "paytm", "mobikwik", "freecharge",
    "cred", "slice", "uni",
    "meesho", "myntra", "ajio", "nykaa",
    "firstcry", "purplle",
    "lenskart", "pearmona",
    "urbancompany", "housejoy",
    "nobroker", "housing", "magicbricks",
    "99acres",
    "unacademy", "byjus", "vedantu",
    "upgrad", "simplilearn",
    "scaler", "interviewbit",
    "hackerrank", "leetcode", "codechef",
    "geeksforgeeks",
    "freshworksinc", "chargebeeinc",
    "whatfixinc", "gupshupinc",
    "yellowaiinc", "observeaiinc",
    "sprinklrinc", "freshdeskinc",
]

EXTRA_LEVER = [
    "netflix", "spotify", "palantir", "stripe",
    "lyft", "instacart", "doordash",
    "brex", "plaid", "affirm", "robinhood",
    "notion", "figma", "canva", "miro",
    "rippling", "deel", "remote",
    "oyster", "gusto",
    "anduril", "shieldai",
    "scaleai", "adept", "cohere",
    "mistral", "huggingface",
    "weightsandbiases", "wandb",
    "langchain", "pinecone",
    "weaviate", "qdrant",
    "browserstack", "lambdatest",
    "postman", "hasura",
    "razorpay", "phonepe", "cred",
    "meesho", "sharechat",
    "dream11", "mpl",
    "swiggy", "zomato",
    "ola", "rapido",
    "policybazaar", "acko",
    "groww", "upstox",
    "navi", "jupiter",
    "niyo", "fi",
    "open", "razorpayx",
    "setu", "cashfree",
    "juspay", "payu",
    "thoughtworks", "epam",
    "globallogic", " Persistent",
    "hexaware", "mphasis",
    "virtusa", "ltimindtree",
    "wipro", "infosys",
    "tcs", "hcltech",
    "cognizant", "capgemini",
    "accenture", "deloitte",
    "kpmg", "ey",
    "pwc", "mckinsey",
    "bcg", "bain",
    "publicis", "dentsu",
    "wpp", "havas",
    "endava", "globant",
    "softserve", "nagarro",
    "tietoevry", "cgi",
    "atos", "soprasteria",
    "luxoft", "epam-systems",
]

EXTRA_ASHBY = [
    "cursor", "anysphere", "windsurf",
    "perplexity", "groq", "together",
    "fireworks", "modal", "replicate",
    "huggingface", "wandb",
    "langchain", "langfuse",
    "pinecone", "weaviate",
    "resend", "clerk",
    "planetscale", "neon",
    "temporal", "inngest",
    "triggerdev", "render",
    "fly", "railway",
    "retool", "airplane",
    "census", "hightouch",
    "dbt", "hex",
    "omni", "preset",
    "metabase", "lightdash",
    "posthog", "june",
    "plain", "pylon",
    "plain.com",
    "ashby", "gem",
    "greenhouse", "lever",
    "wellfound", "otta",
    "ripple", "circle",
    "anchorage", "fireblocks",
    "chainalysis", "elliptic",
    "opensea", "blur",
    "magiceden",
]

SR = [
    "Ericsson", "Nokia", "BoschGroup", "SiemensEnergy",
    "Capgemini", "PublicisGroupe", "Thales", "SchneiderElectric",
    "Vodafone", "Orange", "DeutscheTelekom",
    "Continental", "Valeo", "Forvia",
    "LOreal", "Unilever", "Nestle", "Danone",
    "IKEA", "Decathlon", "Adidas", "Puma",
    "ASML", "NXP", "Infineon", "STMicroelectronics",
    "Flex", "Jabil",
    "CGI", "Atos", "SopraSteria", "Nagarro",
    "Endava", "Globant", "SoftServe", "Luxoft",
    "Tietoevry", "Wipro", "HCLTechnologies",
    "TechMahindra", "LTIMindtree", "Mphasis",
    "PersistentSystems", "EPAM", "Cognizant",
    "Accenture", "Deloitte", "EY", "PwC", "KPMG",
    "BNPParibas", "SocieteGenerale", "AXA", "Allianz",
    "Airbus", "Safran", "ThalesGroup",
    "Michelin", "Renault", "Stellantis",
    "Philips", "Medtronic",
    "Novartis", "Sanofi", "GSK",
    "Amadeus", "Sabre",
    "PublicisSapient", "Valtech",
    "Thoughtworks", "ThoughtWorks",
    "Infosys", "TCS", "TataConsultancyServices",
    "Mahindra", "TechM",
    "Airtel", "Jio", "Reliance",
    "HDFCBank", "ICICIBank", "AxisBank",
    "Kotak", "YesBank",
    "SBI", "BajajFinserv",
]

WORKABLE = [
    "browserstack", "freshworks", "chargebee", "postman",
    "razorpay", "phonepe", "swiggy", "zoho",
    "darwinbox", "keka", "leadsquared",
    "whatfix", "gupshup", "yellowai",
    "zenoti", "icertis", "o9solutions",
    "persistent", "valuelabs", "brillio",
    "sonata", "birlasoft", "hexaware",
    "mphasis", "virtusa", "ltimindtree",
    "cyient", "ltts", "kpit",
    "quantiphi", "fractal", "tigeranalytics",
    " Latentview", "mu-sigma",
    "thoughtworks", "epam",
]

MORE_WORKDAY = [
    ("https://accenture.wd3.myworkdayjobs.com/wday/cxs/accenture/AccentureCareers/jobs", "https://accenture.wd3.myworkdayjobs.com/en-US/AccentureCareers", "Accenture"),
    ("https://cognizant.wd1.myworkdayjobs.com/wday/cxs/cognizant/CognizantCareers/jobs", "https://cognizant.wd1.myworkdayjobs.com/en-US/CognizantCareers", "Cognizant"),
    ("https://capgemini.wd3.myworkdayjobs.com/wday/cxs/capgemini/Capgemini/jobs", "https://capgemini.wd3.myworkdayjobs.com/en-US/Capgemini", "Capgemini"),
    ("https://infosys.wd1.myworkdayjobs.com/wday/cxs/infosys/Infosys_Careers/jobs", "https://infosys.wd1.myworkdayjobs.com/en-US/Infosys_Careers", "Infosys"),
    ("https://wipro.wd3.myworkdayjobs.com/wday/cxs/wipro/careers/jobs", "https://wipro.wd3.myworkdayjobs.com/en-US/careers", "Wipro"),
    ("https://hcltech.wd3.myworkdayjobs.com/wday/cxs/hcltech/HCLTechCareers/jobs", "https://hcltech.wd3.myworkdayjobs.com/en-US/HCLTechCareers", "HCLTech"),
    ("https://ltimindtree.wd3.myworkdayjobs.com/wday/cxs/ltimindtree/Careers/jobs", "https://ltimindtree.wd3.myworkdayjobs.com/en-US/Careers", "LTIMindtree"),
    ("https://deloitte.wd1.myworkdayjobs.com/wday/cxs/deloitte/DeloitteCareers/jobs", "https://deloitte.wd1.myworkdayjobs.com/en-US/DeloitteCareers", "Deloitte"),
    ("https://ey.wd1.myworkdayjobs.com/wday/cxs/ey/EYCareers/jobs", "https://ey.wd1.myworkdayjobs.com/en-US/EYCareers", "EY"),
    ("https://pwc.wd3.myworkdayjobs.com/wday/cxs/pwc/External_Careers/jobs", "https://pwc.wd3.myworkdayjobs.com/en-US/External_Careers", "PwC"),
    ("https://ibm.wd1.myworkdayjobs.com/wday/cxs/ibm/search/jobs", "https://ibm.wd1.myworkdayjobs.com/en-US/search", "IBM"),
    ("https://oracle.wd1.myworkdayjobs.com/wday/cxs/oracle/External/jobs", "https://oracle.wd1.myworkdayjobs.com/en-US/External", "Oracle"),
    ("https://redhat.wd5.myworkdayjobs.com/wday/cxs/redhat/jobs/jobs", "https://redhat.wd5.myworkdayjobs.com/en-US/jobs", "RedHat"),
    ("https://vmware.wd1.myworkdayjobs.com/wday/cxs/vmware/External/jobs", "https://vmware.wd1.myworkdayjobs.com/en-US/External", "VMware"),
    ("https://capitalone.wd1.myworkdayjobs.com/wday/cxs/capitalone/Capital_One/jobs", "https://capitalone.wd1.myworkdayjobs.com/en-US/Capital_One", "CapitalOne"),
    ("https://autodesk.wd1.myworkdayjobs.com/wday/cxs/autodesk/Ext/jobs", "https://autodesk.wd1.myworkdayjobs.com/en-US/Ext", "Autodesk"),
    ("https://booking.wd3.myworkdayjobs.com/wday/cxs/booking/BookingCareers/jobs", "https://booking.wd3.myworkdayjobs.com/en-US/BookingCareers", "Booking"),
    ("https://expedia.wd5.myworkdayjobs.com/wday/cxs/expedia/Expedia_Group/jobs", "https://expedia.wd5.myworkdayjobs.com/en-US/Expedia_Group", "Expedia"),
    ("https://marriott.wd1.myworkdayjobs.com/wday/cxs/marriott/MarriottJobsandCareers/jobs", "https://marriott.wd1.myworkdayjobs.com/en-US/MarriottJobsandCareers", "Marriott"),
    ("https://pepsico.wd1.myworkdayjobs.com/wday/cxs/pepsico/PepsiCo/jobs", "https://pepsico.wd1.myworkdayjobs.com/en-US/PepsiCo", "PepsiCo"),
    ("https://unilever.wd3.myworkdayjobs.com/wday/cxs/unilever/Unilever/jobs", "https://unilever.wd3.myworkdayjobs.com/en-US/Unilever", "Unilever"),
    ("https://shell.wd3.myworkdayjobs.com/wday/cxs/shell/ShellCareers/jobs", "https://shell.wd3.myworkdayjobs.com/en-US/ShellCareers", "Shell"),
    ("https://bp.wd3.myworkdayjobs.com/wday/cxs/bp/Careers/jobs", "https://bp.wd3.myworkdayjobs.com/en-US/Careers", "BP"),
    ("https://airbus.wd3.myworkdayjobs.com/wday/cxs/airbus/job-board/jobs", "https://airbus.wd3.myworkdayjobs.com/en-US/job-board", "Airbus"),
    ("https://cummins.wd5.myworkdayjobs.com/wday/cxs/cummins/External/jobs", "https://cummins.wd5.myworkdayjobs.com/en-US/External", "Cummins"),
    ("https://eaton.wd1.myworkdayjobs.com/wday/cxs/eaton/EatonExternal/jobs", "https://eaton.wd1.myworkdayjobs.com/en-US/EatonExternal", "Eaton"),
    ("https://johnsonandjohnson.wd5.myworkdayjobs.com/wday/cxs/johnsonandjohnson/jnj/jobs", "https://johnsonandjohnson.wd5.myworkdayjobs.com/en-US/jnj", "JNJ"),
    ("https://gsk.wd5.myworkdayjobs.com/wday/cxs/gsk/GSKCareers/jobs", "https://gsk.wd5.myworkdayjobs.com/en-US/GSKCareers", "GSK"),
    ("https://novartis.wd3.myworkdayjobs.com/wday/cxs/novartis/careers/jobs", "https://novartis.wd3.myworkdayjobs.com/en-US/careers", "Novartis"),
    ("https://pfizer.wd1.myworkdayjobs.com/wday/cxs/pfizer/PfizerCareers/jobs", "https://pfizer.wd1.myworkdayjobs.com/en-US/PfizerCareers", "Pfizer"),
    ("https://amgen.wd1.myworkdayjobs.com/wday/cxs/amgen/Careers/jobs", "https://amgen.wd1.myworkdayjobs.com/en-US/Careers", "Amgen"),
    ("https://medtronic.wd1.myworkdayjobs.com/wday/cxs/medtronic/MedtronicCareers/jobs", "https://medtronic.wd1.myworkdayjobs.com/en-US/MedtronicCareers", "Medtronic"),
    ("https://db.wd3.myworkdayjobs.com/wday/cxs/db/ExternalCareerSite/jobs", "https://db.wd3.myworkdayjobs.com/en-US/ExternalCareerSite", "DeutscheBank"),
    ("https://hsbc.wd3.myworkdayjobs.com/wday/cxs/hsbc/External/jobs", "https://hsbc.wd3.myworkdayjobs.com/en-US/External", "HSBC"),
    ("https://standardchartered.wd3.myworkdayjobs.com/wday/cxs/standardchartered/Careers/jobs", "https://standardchartered.wd3.myworkdayjobs.com/en-US/Careers", "StandardChartered"),
    ("https://bankofamerica.wd1.myworkdayjobs.com/wday/cxs/bankofamerica/External_Careers/jobs", "https://bankofamerica.wd1.myworkdayjobs.com/en-US/External_Careers", "BankOfAmerica"),
]


def microsoft(jobs):
    print("Microsoft careers...", flush=True)
    url = "https://gcsservices.careers.microsoft.com/search/api/v1/search"
    for q in ("architect Hyderabad", "principal engineer Hyderabad", "staff engineer Hyderabad",
              "technical lead Hyderabad", "senior software engineer Hyderabad"):
        payload = json.dumps({
            "searchText": q,
            "filters": [
                {"field": "country", "term": "India", "selected": True},
            ],
            "top": 50,
        }).encode()
        data, status = discover_bulk.get_json(url, data=payload, headers={"Content-Type": "application/json"})
        ops = (((data or {}).get("operationResult") or {}).get("result") or {})
        for item in ops.get("jobs") or []:
            props = item.get("properties") or item
            title = item.get("title") or props.get("title") or ""
            loc = " ".join(str(x) for x in (
                props.get("primaryLocation"),
                props.get("city"),
                props.get("state"),
                props.get("country"),
            ) if x)
            jid = item.get("jobId") or item.get("id") or ""
            link = f"https://jobs.careers.microsoft.com/global/en/job/{jid}" if jid else ""
            d.add(jobs, "Microsoft", title, loc, link, "Microsoft", jid)
        time.sleep(0.25)


def google(jobs):
    print("Google careers...", flush=True)
    for q in ("architect", "principal engineer", "staff software engineer", "technical lead", "senior software engineer"):
        qs = urllib.parse.urlencode({"q": q, "location": "Hyderabad, India", "page_size": 20})
        data, status = discover_bulk.get_json(f"https://careers.google.com/api/v3/search/?{qs}")
        for item in (data or {}).get("jobs") or []:
            locs = item.get("locations") or []
            loc = " ".join(
                (x.get("display") if isinstance(x, dict) else str(x)) for x in locs
            ) or str(item.get("location") or "")
            title = item.get("title") or ""
            jid = item.get("id") or item.get("job_id") or ""
            link = item.get("apply_url") or item.get("canonical_url") or f"https://www.google.com/about/careers/applications/jobs/results/{jid}"
            d.add(jobs, "Google", title, loc, link, "Google", jid)
        time.sleep(0.25)


def smartrecruiters(jobs):
    print("SmartRecruiters...", flush=True)
    for cid in SR:
        for offset in (0, 100):
            url = f"https://api.smartrecruiters.com/v1/companies/{cid}/postings?country=in&limit=100&offset={offset}"
            data, status = discover_bulk.get_json(url)
            if status != 200 or not data:
                break
            rows = data.get("content") or []
            if not rows:
                break
            for item in rows:
                loc = item.get("location") or {}
                city = loc.get("city") or ""
                region = loc.get("region") or ""
                country = loc.get("country") or loc.get("countryCode") or ""
                remote = "Remote" if item.get("remote") or (item.get("location") or {}).get("remote") else ""
                place = f"{city} {region} {country} {remote}"
                title = item.get("name") or item.get("title") or ""
                jid = item.get("id") or item.get("uuid") or ""
                ref = (item.get("ref") or item.get("postingUrl")
                       or f"https://jobs.smartrecruiters.com/{cid}/{jid}")
                d.add(jobs, cid, title, place, ref, "SmartRecruiters", jid)
            if len(rows) < 100:
                break
            time.sleep(0.05)
        time.sleep(0.05)


def workable(jobs):
    print("Workable...", flush=True)
    for token in WORKABLE:
        token = token.strip()
        if not token:
            continue
        data, status = discover_bulk.get_json(f"https://apply.workable.com/api/v1/widget/accounts/{token}")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            loc = " ".join(str(x) for x in (
                item.get("city"), item.get("state"), item.get("country"),
                item.get("location"), "Remote" if item.get("telecommuting") else "",
            ) if x)
            d.add(jobs, token, item.get("title") or "", loc, item.get("url") or "", "Workable", item.get("shortcode") or item.get("id"))
        time.sleep(0.05)


def extra_boards(jobs):
    print("Extra Greenhouse...", flush=True)
    seen = set(discover_bulk.GH)
    for token in EXTRA_GH:
        if token in seen:
            continue
        seen.add(token)
        data, status = discover_bulk.get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            loc = (item.get("location") or {}).get("name") or ""
            d.add(jobs, token, item.get("title") or "", loc, item.get("absolute_url") or "", "Greenhouse", item.get("id"))
        time.sleep(0.02)

    print("Extra Lever...", flush=True)
    seen = set(discover_bulk.LEVER)
    for company in EXTRA_LEVER:
        company = company.strip()
        if not company or company in seen:
            continue
        seen.add(company)
        data, status = discover_bulk.get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
        if status != 200 or not isinstance(data, list):
            continue
        for item in data:
            cats = item.get("categories") or {}
            loc = str(cats.get("location") or "")
            if isinstance(cats.get("allLocations"), list):
                loc = " ".join(str(x) for x in cats["allLocations"]) + " " + loc
            d.add(jobs, company, item.get("text") or "", loc, item.get("hostedUrl") or "", "Lever", item.get("id"))
        time.sleep(0.02)

    print("Extra Ashby...", flush=True)
    for token in EXTRA_ASHBY:
        data, status = discover_bulk.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            loc = item.get("location") or ""
            if isinstance(loc, dict):
                loc = " ".join(str(loc.get(k) or "") for k in ("location", "city", "region", "country"))
            if item.get("isRemote"):
                loc = f"{loc} Remote"
            d.add(jobs, token, item.get("title") or "", loc, item.get("jobUrl") or "", "Ashby", item.get("id"))
        time.sleep(0.03)


def extra_workday(jobs):
    print("More Workday portals...", flush=True)
    existing = {(a, c) for a, _, c in discover_portals.SITES}
    for api, site, company in MORE_WORKDAY:
        if (api, company) in existing:
            continue
        print(f"  {company}", flush=True)
        payload = json.dumps({
            "appliedFacets": {}, "limit": 20, "offset": 0,
            "searchText": "Hyderabad architect",
        }).encode()
        data = discover_portals.get_json(api, data=payload)
        time.sleep(0.12)
        if not data:
            continue
        for item in data.get("jobPostings") or []:
            path = item.get("externalPath") or ""
            if not path:
                continue
            d.add(
                jobs, company, item.get("title") or "", item.get("locationsText") or "",
                site.rstrip("/") + path, "Workday", path.rstrip("/").split("/")[-1],
            )


def merge_and_write(jobs):
    apply_now.sync_applied_store()
    used = apply_now.submitted_by_company()
    applied_ids = set(apply_now.SKIP_IDS) | set(apply_now.load_applied_ids())
    for ids in used.values():
        applied_ids.update(ids)
    existing = []
    for path in (ROOT / "data" / "discovery_final.json", ROOT / "data" / "discovery_batch.json"):
        if path.exists():
            try:
                existing.extend(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass
    seen = set()
    unique = []
    for j in existing + jobs:
        if not isinstance(j, dict):
            continue
        if not d.title_ok(j.get("title") or "") or not d.loc_ok(j.get("location") or ""):
            continue
        if d.company_blocked(j.get("company")):
            continue
        jid = str(j.get("job_id") or "")
        key = (apply_now.company_key(j.get("company")), jid or str(j.get("url") or "")[:80])
        if key in seen:
            continue
        seen.add(key)
        row = dict(j)
        row["already_applied"] = apply_now.is_applied(row) or bool(jid and jid in applied_ids)
        unique.append(row)
    for j in unique:
        j["match_score"] = apply_now.match_score(j)
    unique.sort(key=lambda j: (j.get("already_applied"), -int(j.get("match_score") or 0), (j.get("company") or "").lower()))
    open_jobs = [j for j in unique if not j.get("already_applied")]
    queue = apply_now.pick_best_per_company(open_jobs, used)
    chosen_keys = {
        (apply_now.company_key(j.get("company")), str(j.get("job_id") or j.get("url") or "")[:80])
        for j in queue
    }
    for j in open_jobs:
        key = (apply_now.company_key(j.get("company")), str(j.get("job_id") or j.get("url") or "")[:80])
        j["over_cap"] = key not in chosen_keys
    queue.sort(key=lambda j: (-int(j.get("match_score") or 0), j.get("company") or "", j.get("title") or ""))
    (ROOT / "data" / "discovery_final.json").write_text(json.dumps(unique, indent=2), encoding="utf-8")
    (ROOT / "data" / "discovery_batch.json").write_text(json.dumps(queue, indent=2), encoding="utf-8")
    lines = [
        "# Expanded discovery — more portals",
        "",
        f"Run date: {date.today().isoformat()}",
        "",
        "Added Microsoft, Google, SmartRecruiters, Workable, extra Greenhouse/Lever/Ashby boards, and more Workday career sites.",
        "Same filters: yesterday’s titles, Hyderabad or Remote/Hybrid India, 60 LPA (unknown CTC kept).",
        "",
        f"- Unique in-scope: **{len(unique)}**",
        f"- Already applied: **{sum(1 for j in unique if j.get('already_applied'))}**",
        f"- Open: **{len(open_jobs)}**",
        f"- Ready to apply (best matches, under 3/company): **{len(queue)}**",
        "",
        "By source (open): " + ", ".join(f"{k} {v}" for k, v in Counter(j.get('ats') for j in open_jobs).most_common()),
        "",
        "## Ready to apply",
        "",
        "| # | Company | Title | Location | Source | Link |",
        "|---|---------|-------|----------|--------|------|",
    ]
    for i, j in enumerate(queue, 1):
        lines.append(
            f"| {i} | {j.get('company')} | {(j.get('title') or '')[:68]} | {(j.get('location') or '')[:40]} | {j.get('ats')} | {j.get('url') or ''} |"
        )
    if not queue:
        lines.append("| | none | | | | |")
    lines.extend(["", "## Open but at company cap", ""])
    over = [j for j in open_jobs if j.get("over_cap")]
    lines.append("None." if not over else "\n".join(
        f"- {j.get('company')}: {j.get('title')} — {j.get('url')}" for j in over
    ))
    (ROOT / "DISCOVERY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nUnique {len(unique)} open {len(open_jobs)} ready {len(queue)}")
    print("Open ATS", dict(Counter(j.get("ats") for j in open_jobs)))
    print("Open companies", Counter(j.get("company") for j in open_jobs).most_common(20))
    for i, j in enumerate(queue[:50], 1):
        print(f"{i:2} {j.get('ats')} | {j.get('company')} | {(j.get('title') or '')[:60]} | {(j.get('location') or '')[:32]}")


def main():
    jobs = []
    microsoft(jobs)
    google(jobs)
    extra_boards(jobs)
    smartrecruiters(jobs)
    workable(jobs)
    extra_workday(jobs)
    print(f"New raw rows before merge/filter: {len(jobs)}", flush=True)
    merge_and_write(jobs)


if __name__ == "__main__":
    main()
