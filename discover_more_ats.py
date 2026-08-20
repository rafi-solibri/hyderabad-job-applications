"""More ATS portals: Recruitee, Breezy, BambooHR, Personio, Eightfold, extra Workday/GH."""
from __future__ import annotations

import json
import time
from pathlib import Path

import apply_now
import discover_bulk
import discover_final as d
import discover_more_sites as more
import discover_portals

ROOT = Path(__file__).resolve().parent

RECRUITEE = [
    "postman", "browserstack", "freshworks", "chargebee", "whatfix",
    "gupshup", "yellowai", "zenoti", "icertis", "o9",
    "darwinbox", "keka", "leadsquared", "exotel",
    "razorpay", "cashfree", "juspay", "setu",
    "groww", "upstox", "dhan",
    "swiggy", "zomato", "meesho",
    "urbancompany", "nobroker",
    "acko", "policybazaar",
    "innovaccer", "practo",
    "browserstackinc", "hasura",
    "dhiwise", "cutshort",
    "nium", "rapyd",
    "browserling",
]

BREEZY = [
    "postman", "freshworks", "chargebee", "browserstack",
    "whatfix", "gupshup", "yellowai",
    "zenoti", "icertis",
    "thoughtworks", "nagarro", "endava",
    "globant", "softserve", "luxoft",
    "persistent", "hexaware", "mphasis",
    "virtusa", "valuelabs", "brillio",
    "sonata", "birlasoft", "cyient",
    "kpit", "ltts",
    "quantiphi", "fractal", "tigeranalytics",
    "highradius", "o9solutions",
]

BAMBOO = [
    "browserstack", "freshworks", "chargebee", "postman",
    "whatfix", "gupshup", "zenoti",
    "darwinbox", "keka",
    "persistent", "hexaware",
    "nagarro", "endava", "globant",
    "highradius", "innovaccer",
]

PERSONIO = [
    "personio", "celonis", "n26", "trade-republic",
    "contentful", "adjust", "sumup",
    "deliveryhero", "hellofresh",
    "zalando", "aboutyou",
    "flix", "getyourguide",
    "taxfix", "raisin",
    "wefox", "clark",
]

EIGHTFOLD = [
    "jpmorganchase.com", "microsoft.com", "cisco.com", "ibm.com",
    "oracle.com", "adobe.com", "intuit.com",
    "paypal.com", "visa.com", "mastercard.com", "americanexpress.com",
    "capitalone.com", "wellsfargo.com", "bankofamerica.com",
    "citi.com", "hsbc.com", "barclays.com",
    "morganstanley.com", "goldmansachs.com",
    "blackrock.com", "statestreet.com", "bnymellon.com",
    "fidelity.com", "schwab.com",
    "deloitte.com", "accenture.com", "infosys.com",
    "wipro.com", "cognizant.com", "capgemini.com",
    "hcltech.com", "techmahindra.com", "ltimindtree.com",
    "mphasis.com", "persistent.com",
    "nvidia.com", "intel.com", "amd.com", "qualcomm.com",
    "broadcom.com", "micron.com",
    "honeywell.com", "siemens.com", "philips.com",
    "ge.com", "medtronic.com", "amgen.com",
    "walmart.com", "target.com", "bestbuy.com",
    "fedex.com", "ups.com",
    "verizon.com", "att.com",
    "comcast.com", "disney.com",
    "nike.com", "starbucks.com",
    "pepsico.com", "unilever.com",
    "shell.com", "bp.com",
]

MORE_GH = [
    "tesla", "spacex", "rivian", "lucidmotors",
    "nike", "starbucks", "disneyanimation",
    "comcast", "nbcu",
    "verizon", "att",
    "target", "bestbuy", "homedepot", "lowes",
    "fedex", "ups", "dhl",
    "airbnb", "bookingcom", "expedia",
    "linkedin", "microsoftcareers",
    "amazon", "apple",
    "meta", "facebook",
    "netflix", "spotify",
    "uber", "lyft",
    "doordash", "instacart",
    "square", "block", "cashapp",
    "stripe", "adyen", "checkout",
    "shopify", "woocommerce",
    "salesforce",  # title-filtered
    "servicenow",
    "workdayinc",
    "okta", "auth0", "pingidentity",
    "crowdstrike", "paloaltonetworks", "fortinet",
    "zscaler", "cloudflare",
    "datadog", "newrelic", "dynatrace", "splunk",
    "snowflake", "databricks", "dbtlabs",
    "mongodb", "elastic", "confluent",
    "hashicorp", "gitlab", "github",
    "atlassian", "asana", "mondaycom",
    "smartsheet", "airtable",
    "figma", "canva", "miro",
    "notion", "coda",
    "twilio", "sendgrid", "messagebird",
    "plivo", "vonage",
    "zoom", "webex",
    "slack", "discord",
    "reddit", "pinterest",
    "snapchat", "tiktok",
    "bytedance",
    "walmartlabs", "walmartglobaltech",
    "targettech",
    "capitaloneindia",
    "jpmc", "jpmorganchase",
    "goldmansachs", "morganstanley",
    "barclays", "hsbc", "citi",
    "wellsfargo", "bankofamerica",
    "americanexpress",
    "visa", "mastercard", "paypal",
    "fiserv", "fis", "broadridge",
    "ssnc", "finastra", "temenos",
    "informatica", "opentext", "teradata",
    "sas", "alteryx", "qlik",
    "uipath", "automationanywhere",
    "appian", "pega",
    "mendix", "outsystems",
    "servicetitan", "procore",
    "autodesk", "bentley",
    "trimble", "hexagon",
    "ptc", "siemensdigital",
    "ansys", "altair", "cadence", "synopsys",
    "honeywell", "siemens", "abb", "schneider",
    "bosch", "continental", "valeo",
    "philips", "gehealthcare", "siemenshealthineers",
    "medtronic", "bostonscientific", "abbott",
    "amgen", "novartis", "pfizer", "gsk", "roche",
    "jnj", "bayer", "sanofi",
    "optum", "unitedhealth", "cvshealth",
    "iqvia", "veeva", "cotiviti",
    "highradius", "inovalon",
    "freshworks", "zoho", "chargebee",
    "browserstack", "lambdatest", "postman",
    "razorpay", "phonepe", "paytm",
    "swiggy", "zomato", "meesho",
    "flipkart", "myntra", "nykaa",
    "ola", "rapido", "uberindia",
    "delhivery", "shadowfax",
    "policybazaar", "acko",
    "unacademy", "byjus", "upgrad",
    "scaler", "interviewbit", "hackerrank",
    "innovaccer", "practo", "1mg",
    "thoughtworks", "epam", "globallogic",
    "nagarro", "endava", "globant",
    "softserve", "luxoft", "cgi",
    "hexaware", "mphasis", "virtusa",
    "ltimindtree", "techmahindra",
    "persistent", "cyient", "ltts", "kpit",
    "valuelabs", "brillio", "sonatasoftware",
    "quantiphi", "fractalanalytics",
    "o9solutions", "icertis", "zenoti",
    "whatfix", "gupshup", "yellowai",
    "sprinklr", "freshdesk",
    "publicissapient", "valtech",
    "tcs", "infosys", "wipro", "hcl",
    "cognizant", "capgemini", "accenture",
    "deloitte", "ey", "pwc", "kpmg",
    "ibm", "oracle", "sap",
    "redhat", "vmware", "nutanix",
    "netapp", "purestorage",
    "dell", "hpe", "hp",
    "cisco", "juniper", "arista",
    "nvidia", "amd", "intel", "qualcomm",
    "arm", "broadcom", "marvell", "micron",
    "tesco", "sainsburys",
    "unilever", "p-and-g", "pepsico",
    "nestle", "cocacola",
    "airbus", "boeing", "lockheed",
    "rtx", "northrop", "bae",
    "cummins", "eaton", "caterpillar",
    "ford", "gm", "stellantis",
    "toyota", "hyundai",
]

MORE_WORKDAY = [
    ("https://tesco.wd3.myworkdayjobs.com/wday/cxs/tesco/TescoCareers/jobs", "https://tesco.wd3.myworkdayjobs.com/en-US/TescoCareers", "Tesco"),
    ("https://target.wd5.myworkdayjobs.com/wday/cxs/target/TargetCareers/jobs", "https://target.wd5.myworkdayjobs.com/en-US/TargetCareers", "Target"),
    ("https://homedepot.wd5.myworkdayjobs.com/wday/cxs/homedepot/THD_Careers/jobs", "https://homedepot.wd5.myworkdayjobs.com/en-US/THD_Careers", "HomeDepot"),
    ("https://lowes.wd5.myworkdayjobs.com/wday/cxs/lowes/Lowes/jobs", "https://lowes.wd5.myworkdayjobs.com/en-US/Lowes", "Lowes"),
    ("https://nike.wd1.myworkdayjobs.com/wday/cxs/nike/EXTERNALCAREERS/jobs", "https://nike.wd1.myworkdayjobs.com/en-US/EXTERNALCAREERS", "Nike"),
    ("https://starbucks.wd1.myworkdayjobs.com/wday/cxs/starbucks/External/jobs", "https://starbucks.wd1.myworkdayjobs.com/en-US/External", "Starbucks"),
    ("https://disney.wd5.myworkdayjobs.com/wday/cxs/disney/disneycareer/jobs", "https://disney.wd5.myworkdayjobs.com/en-US/disneycareer", "Disney"),
    ("https://comcast.wd5.myworkdayjobs.com/wday/cxs/comcast/Comcast_Careers/jobs", "https://comcast.wd5.myworkdayjobs.com/en-US/Comcast_Careers", "Comcast"),
    ("https://verizon.wd5.myworkdayjobs.com/wday/cxs/verizon/External/jobs", "https://verizon.wd5.myworkdayjobs.com/en-US/External", "Verizon"),
    ("https://att.wd1.myworkdayjobs.com/wday/cxs/att/ExtCareers/jobs", "https://att.wd1.myworkdayjobs.com/en-US/ExtCareers", "ATT"),
    ("https://fedex.wd1.myworkdayjobs.com/wday/cxs/fedex/FX/jobs", "https://fedex.wd1.myworkdayjobs.com/en-US/FX", "FedEx"),
    ("https://ups.wd1.myworkdayjobs.com/wday/cxs/ups/UPSJOBS/jobs", "https://ups.wd1.myworkdayjobs.com/en-US/UPSJOBS", "UPS"),
    ("https://lockheedmartin.wd1.myworkdayjobs.com/wday/cxs/lockheedmartin/external/jobs", "https://lockheedmartin.wd1.myworkdayjobs.com/en-US/external", "Lockheed"),
    ("https://rtx.wd1.myworkdayjobs.com/wday/cxs/rtx/RTX/jobs", "https://rtx.wd1.myworkdayjobs.com/en-US/RTX", "RTX"),
    ("https://northropgrumman.wd5.myworkdayjobs.com/wday/cxs/northropgrumman/External/jobs", "https://northropgrumman.wd5.myworkdayjobs.com/en-US/External", "Northrop"),
    ("https://baesystems.wd3.myworkdayjobs.com/wday/cxs/baesystems/BAE_EXTERNAL/jobs", "https://baesystems.wd3.myworkdayjobs.com/en-US/BAE_EXTERNAL", "BAE"),
    ("https://leidos.wd1.myworkdayjobs.com/wday/cxs/leidos/External/jobs", "https://leidos.wd1.myworkdayjobs.com/en-US/External", "Leidos"),
    ("https://ford.wd5.myworkdayjobs.com/wday/cxs/ford/Ford/jobs", "https://ford.wd5.myworkdayjobs.com/en-US/Ford", "Ford"),
    ("https://gm.wd5.myworkdayjobs.com/wday/cxs/gm/External/jobs", "https://gm.wd5.myworkdayjobs.com/en-US/External", "GM"),
    ("https://toyota.wd1.myworkdayjobs.com/wday/cxs/toyota/ToyotaSales/jobs", "https://toyota.wd1.myworkdayjobs.com/en-US/ToyotaSales", "Toyota"),
    ("https://hyundai.wd1.myworkdayjobs.com/wday/cxs/hyundai/hyundai_careers/jobs", "https://hyundai.wd1.myworkdayjobs.com/en-US/hyundai_careers", "Hyundai"),
    ("https://caterpillar.wd5.myworkdayjobs.com/wday/cxs/caterpillar/External/jobs", "https://caterpillar.wd5.myworkdayjobs.com/en-US/External", "Caterpillar"),
    ("https://techmahindra.wd3.myworkdayjobs.com/wday/cxs/techmahindra/TechMahindra/jobs", "https://techmahindra.wd3.myworkdayjobs.com/en-US/TechMahindra", "TechMahindra"),
    ("https://mphasis.wd3.myworkdayjobs.com/wday/cxs/mphasis/MphasisCareers/jobs", "https://mphasis.wd3.myworkdayjobs.com/en-US/MphasisCareers", "Mphasis"),
    ("https://persistent.wd1.myworkdayjobs.com/wday/cxs/persistent/Persistent_Careers/jobs", "https://persistent.wd1.myworkdayjobs.com/en-US/Persistent_Careers", "Persistent"),
    ("https://hexaware.wd3.myworkdayjobs.com/wday/cxs/hexaware/Hexaware/jobs", "https://hexaware.wd3.myworkdayjobs.com/en-US/Hexaware", "Hexaware"),
    ("https://virtusa.wd1.myworkdayjobs.com/wday/cxs/virtusa/Virtusa/jobs", "https://virtusa.wd1.myworkdayjobs.com/en-US/Virtusa", "Virtusa"),
    ("https://cyient.wd3.myworkdayjobs.com/wday/cxs/cyient/Cyient/jobs", "https://cyient.wd3.myworkdayjobs.com/en-US/Cyient", "Cyient"),
    ("https://kpit.wd3.myworkdayjobs.com/wday/cxs/kpit/KPIT/jobs", "https://kpit.wd3.myworkdayjobs.com/en-US/KPIT", "KPIT"),
    ("https://ltts.wd3.myworkdayjobs.com/wday/cxs/ltts/LTTS/jobs", "https://ltts.wd3.myworkdayjobs.com/en-US/LTTS", "LTTS"),
    ("https://nagarro.wd3.myworkdayjobs.com/wday/cxs/nagarro/Nagarro/jobs", "https://nagarro.wd3.myworkdayjobs.com/en-US/Nagarro", "Nagarro"),
    ("https://epam.wd5.myworkdayjobs.com/wday/cxs/epam/EPAM/jobs", "https://epam.wd5.myworkdayjobs.com/en-US/EPAM", "EPAM"),
    ("https://thoughtworks.wd1.myworkdayjobs.com/wday/cxs/thoughtworks/Thoughtworks/jobs", "https://thoughtworks.wd1.myworkdayjobs.com/en-US/Thoughtworks", "Thoughtworks"),
    ("https://publicissapient.wd5.myworkdayjobs.com/wday/cxs/publicissapient/PS_Careers/jobs", "https://publicissapient.wd5.myworkdayjobs.com/en-US/PS_Careers", "PublicisSapient"),
    ("https://amadeus.wd3.myworkdayjobs.com/wday/cxs/amadeus/Amadeus/jobs", "https://amadeus.wd3.myworkdayjobs.com/en-US/Amadeus", "Amadeus"),
    ("https://sabre.wd1.myworkdayjobs.com/wday/cxs/sabre/Sabre/jobs", "https://sabre.wd1.myworkdayjobs.com/en-US/Sabre", "Sabre"),
    ("https://airtel.wd3.myworkdayjobs.com/wday/cxs/airtel/Airtel/jobs", "https://airtel.wd3.myworkdayjobs.com/en-US/Airtel", "Airtel"),
    ("https://jio.wd3.myworkdayjobs.com/wday/cxs/jio/JioCareers/jobs", "https://jio.wd3.myworkdayjobs.com/en-US/JioCareers", "Jio"),
    ("https://hdfcbank.wd3.myworkdayjobs.com/wday/cxs/hdfcbank/HDFC/jobs", "https://hdfcbank.wd3.myworkdayjobs.com/en-US/HDFC", "HDFC"),
    ("https://icicibank.wd3.myworkdayjobs.com/wday/cxs/icicibank/ICICI/jobs", "https://icicibank.wd3.myworkdayjobs.com/en-US/ICICI", "ICICI"),
    ("https://axisbank.wd3.myworkdayjobs.com/wday/cxs/axisbank/Axis/jobs", "https://axisbank.wd3.myworkdayjobs.com/en-US/Axis", "Axis"),
    ("https://flipkart.wd3.myworkdayjobs.com/wday/cxs/flipkart/Flipkart/jobs", "https://flipkart.wd3.myworkdayjobs.com/en-US/Flipkart", "Flipkart"),
    ("https://myntra.wd3.myworkdayjobs.com/wday/cxs/myntra/Myntra/jobs", "https://myntra.wd3.myworkdayjobs.com/en-US/Myntra", "Myntra"),
    ("https://swiggy.wd3.myworkdayjobs.com/wday/cxs/swiggy/Swiggy/jobs", "https://swiggy.wd3.myworkdayjobs.com/en-US/Swiggy", "Swiggy"),
    ("https://zomato.wd3.myworkdayjobs.com/wday/cxs/zomato/Zomato/jobs", "https://zomato.wd3.myworkdayjobs.com/en-US/Zomato", "Zomato"),
    ("https://phonepe.wd3.myworkdayjobs.com/wday/cxs/phonepe/PhonePe/jobs", "https://phonepe.wd3.myworkdayjobs.com/en-US/PhonePe", "PhonePe"),
    ("https://paytm.wd3.myworkdayjobs.com/wday/cxs/paytm/Paytm/jobs", "https://paytm.wd3.myworkdayjobs.com/en-US/Paytm", "Paytm"),
    ("https://razorpay.wd3.myworkdayjobs.com/wday/cxs/razorpay/Razorpay/jobs", "https://razorpay.wd3.myworkdayjobs.com/en-US/Razorpay", "Razorpay"),
    ("https://zoho.wd3.myworkdayjobs.com/wday/cxs/zoho/Zoho/jobs", "https://zoho.wd3.myworkdayjobs.com/en-US/Zoho", "Zoho"),
    ("https://freshworks.wd1.myworkdayjobs.com/wday/cxs/freshworks/Freshworks/jobs", "https://freshworks.wd1.myworkdayjobs.com/en-US/Freshworks", "Freshworks"),
]


def pull_recruitee(jobs):
    print("Recruitee...", flush=True)
    for slug in RECRUITEE:
        data, status = discover_bulk.get_json(f"https://{slug}.recruitee.com/api/offers")
        if status != 200 or not data:
            continue
        for item in data.get("offers") or []:
            loc = " ".join(str(x) for x in (
                item.get("location"), item.get("city"), item.get("country"),
                "Remote" if item.get("remote") else "",
            ) if x)
            url = item.get("careers_url") or item.get("url") or ""
            d.add(jobs, slug, item.get("title") or "", loc, url, "Recruitee", item.get("slug") or item.get("id"))
        time.sleep(0.04)


def pull_breezy(jobs):
    print("Breezy...", flush=True)
    for slug in BREEZY:
        data, status = discover_bulk.get_json(f"https://{slug}.breezy.hr/json")
        if status != 200 or not isinstance(data, list):
            continue
        for item in data:
            loc = item.get("location") or {}
            if isinstance(loc, dict):
                place = " ".join(str(loc.get(k) or "") for k in ("city", "country", "name"))
            else:
                place = str(loc)
            if item.get("is_remote") or str(item.get("type") or "").lower() == "remote":
                place = f"{place} Remote"
            d.add(jobs, slug, item.get("name") or "", place, item.get("url") or "", "Breezy", item.get("id"))
        time.sleep(0.04)


def pull_bamboo(jobs):
    print("BambooHR...", flush=True)
    for slug in BAMBOO:
        data, status = discover_bulk.get_json(f"https://{slug}.bamboohr.com/careers/list")
        if status != 200 or not data:
            continue
        rows = data.get("result") or data.get("meta") or data
        if isinstance(rows, dict):
            rows = rows.get("jobs") or rows.get("result") or []
        if not isinstance(rows, list):
            continue
        for item in rows:
            loc = " ".join(str(x) for x in (
                item.get("locationLabel"), item.get("location"), item.get("city"), item.get("state"),
            ) if x)
            jid = item.get("id") or item.get("jobOpeningId") or ""
            url = item.get("jobOpeningShareUrl") or f"https://{slug}.bamboohr.com/careers/{jid}"
            d.add(jobs, slug, item.get("jobOpeningName") or item.get("title") or "", loc, url, "BambooHR", jid)
        time.sleep(0.05)


def pull_personio(jobs):
    print("Personio...", flush=True)
    for slug in PERSONIO:
        data, status = discover_bulk.get_json(f"https://{slug}.jobs.personio.de/search.json")
        if status != 200 or not isinstance(data, list):
            continue
        for item in data:
            office = item.get("office") or {}
            loc = " ".join(str(x) for x in (
                office.get("city") if isinstance(office, dict) else office,
                office.get("country") if isinstance(office, dict) else "",
                item.get("schedule"),
            ) if x)
            jid = item.get("id") or ""
            url = item.get("url") or f"https://{slug}.jobs.personio.de/job/{jid}"
            d.add(jobs, slug, item.get("name") or "", loc, url, "Personio", jid)
        time.sleep(0.05)


def pull_eightfold(jobs):
    print("Eightfold...", flush=True)
    for domain in EIGHTFOLD:
        qs = (
            f"https://app.eightfold.ai/api/apply/v2/jobs?"
            f"domain={domain}&location=Hyderabad&start=0&num=30"
        )
        data, status = discover_bulk.get_json(qs)
        if status != 200 or not data:
            continue
        for item in data.get("positions") or data.get("data") or []:
            loc = " ".join(str(x) for x in (
                item.get("location"), item.get("locations"),
                " ".join(item.get("locations") or []) if isinstance(item.get("locations"), list) else "",
            ) if x)
            jid = item.get("id") or item.get("ats_job_id") or ""
            url = item.get("canonicalPositionUrl") or item.get("apply_url") or item.get("url") or ""
            d.add(jobs, domain.split(".")[0], item.get("name") or item.get("title") or "", loc, url, "Eightfold", jid)
        time.sleep(0.08)


def pull_gh(jobs):
    print("More Greenhouse slugs...", flush=True)
    seen = set(discover_bulk.GH) | set(more.EXTRA_GH)
    for token in MORE_GH:
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


def pull_workday(jobs):
    print("More Workday GCCs...", flush=True)
    existing = {(a, c) for a, _, c in discover_portals.SITES} | {(a, c) for a, _, c in more.MORE_WORKDAY}
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


def main():
    jobs = []
    pull_recruitee(jobs)
    pull_breezy(jobs)
    pull_bamboo(jobs)
    pull_personio(jobs)
    pull_eightfold(jobs)
    pull_gh(jobs)
    pull_workday(jobs)
    print(f"New ATS raw rows: {len(jobs)}", flush=True)
    more.merge_and_write(jobs)


if __name__ == "__main__":
    main()
