"""More Greenhouse / Lever / Ashby / SmartRecruiters boards for Hyderabad + Remote India."""
from __future__ import annotations

import json
import time
from collections import Counter
from datetime import date
from pathlib import Path

import apply_now
import discover_bulk
import discover_final as d
import discover_more_sites as more

ROOT = Path(__file__).resolve().parent

MORE_GH = [
    "atlassian", "asana", "airtable", "intercom", "zendesk",
    "hubspot", "shopify", "squareup", "block", "cashapp",
    "intuit", "adobe", "autodesk", "nvidia", "amd",
    "qualcomm", "arm", "broadcom", "marvell",
    "servicenow",  # filtered by title skip
    "workday", "oracle", "sap",
    "snowflake", "databricks", "dbt-labs", "fivetran",
    "airbyte", "census", "hightouch",
    "confluent", "elastic", "mongodb", "redisinc",
    "hashicorp", "gitlab", "github", "jfrog",
    "snyk", "wizio", "crowdstrike", "paloaltonetworks",
    "okta", "auth0", "duo",
    "datadog", "newrelic", "dynatrace", "splunk",
    "pagerduty", "opsgenie",
    "cloudflare", "fastly", "akamai",
    "twilio", "sendgrid", "messagebird",
    "stripe", "adyen", "checkoutcom",
    "paypal", "visa", "mastercard",
    "capitalone", "sofi", "affirm",
    "robinhood", "coinbase", "kraken",
    "ripple", "circle", "fireblocks",
    "openai", "anthropic", "cohere",
    "huggingface", "scaleai",
    "figma", "canva", "miro", "notionhq",
    "linear", "height", "shortcut",
    "vercel", "netlify", "render",
    "digitalocean", "linode",
    "heroku", "salesforceengineering",
    "publicissapient", "thoughtworks",
    "epam", "globallogic", "nagarro",
    "endava", "globant", "softserve",
    "luxoft", "tietoevry", "cgi",
    "hexaware", "mphasis", "virtusa",
    "ltimindtree", "cyient", "ltts",
    "kpit", "persistent", "valuelabs",
    "brillio", "sonatasoftware", "birlasoft",
    "quantiphi", "fractalanalytics", "tigeranalytics",
    "latenthview", "musigma",
    "o9solutions", "icertis", "zenoti",
    "whatfix", "gupshup", "yellowai",
    "observeai", "sprinklr",
    "freshworks", "chargebee", "chargebeeinc",
    "browserstack", "lambdatest",
    "postman", "konghq",
    "razorpay", "phonepe", "cred",
    "groww", "upstox", "zerodha",
    "payu", "cashfree", "juspay",
    "setu", "slice", "bharatpe",
    "swiggy", "zomato", "meesho",
    "myntra", "nykaa", "lenskart",
    "urbancompany", "nobroker",
    "ola", "rapido", "uber",
    "delhivery", "shadowfax",
    "policybazaar", "acko", "digitinsurance",
    "sharechat", "dream11", "games24x7",
    "mplgaming", "winzo",
    "unacademy", "vedantu", "upgrad",
    "scaler", "interviewbit",
    "hackerrank", "leetcode",
    "innovaccer", "practo", "1mg",
    "pharmeasy", "healthifyme",
    "curefit", "cultfit",
    "dunzo", "blinkit", "zeptonow",
    "bigbasket", "grofers",
    "walmartglobaltech", "walmart",
    "target", "bestbuy",
    "expedia", "bookingcom",
    "airbnb", "tripadvisor",
    "linkedin", "microsoft",
    "google", "meta",
    "amazon", "apple",
    "ibm", "cisco", "dell",
    "hp", "hpe", "intel",
    "micron", "broadcominc",
    "qualcommindia", "nvidiaindia",
    "honeywell", "siemens",
    "schneider-electric", "abb",
    "bosch", "continental",
    "philips", "gehealthcare",
    "medtronic", "bostonscientific",
    "amgen", "novartis", "pfizer",
    "gsk", "sanofi", "roche",
    "jnj", "abbott", "baxter",
    "optum", "unitedhealth",
    "iqvia", "veeva",
    "cotiviti", "changehealthcare",
    "inovalon", "highradius",
    "blackrock", "statestreet",
    "bnymellon", "invesco",
    "franklintempleton", "goldmansachs",
    "jpmorgan", "morganstanley",
    "barclays", "hsbc", "citi",
    "db", "ubs", "credit-suisse",
    "wells-fargo", "bankofamerica",
    "capitaloneindia",
    "fidelity", "vanguard",
    "factset", "bloomberg",
    "refinitiv", "spglobal",
    "moodys", "spglobalinc",
    "ssnc", "broadridge", "fiserv",
    "fis", "finastra", "temenos",
    "ncrvoyix", "ncr",
    "informatica", "opentext",
    "teradata", "sasinstitute",
    "alteryx", "tableau",
    "qlik", "microstrategy",
    "uipath", "automationanywhere",
    "blueprism", "ssc",
    "pega-systems", "appian",
    "mendix", "outsystems",
    "servicetitan", "procore",
    "autodeskconstruction",
    "bentley", "nemetschek",
    "graphisoft", "solibri",
    "spacewell", "allplan",
    "trimble", "esriinc",
    "hexagon", "autodesk",
    "ptc", "siemensplm",
    "ansys", "altair",
    "cadence", "synopsys",
    "mentor", "keysight",
    "nationalinstruments",
    "rockwell", "emerson",
    "honeywellprocess",
    "aveva", "aspentech",
    "seeq", "aveva-group",
]

MORE_LEVER = [
    "netflix", "spotify", "discord", "reddit",
    "pinterest", "snap", "twitter", "x",
    "lyft", "instacart", "doordash",
    "uber", "grab", "gojek",
    "palantir", "anduril", "scaleapi",
    "openai", "anthropic", "inflection",
    "characterai", "adept",
    "stripe", "plaid", "brex", "ramp",
    "mercury", "relays", "modern-treasury",
    "rippling", "deel", "remotecom",
    "oyster", "gusto", "hiive",
    "figma", "canva", "miro", "whimsical",
    "notion", "coda", "airtable",
    "retool", "appsmith",
    "vercel", "supabase", "planetscale",
    "neon", "railway", "render",
    "temporal", "inngest",
    "browserstack", "lambdatest",
    "postman", "hasura",
    "razorpay", "phonepe", "cred",
    "groww", "upstox",
    "swiggy", "zomato", "meesho",
    "sharechat", "dream11",
    "ola", "rapido",
    "policybazaar", "acko",
    "navi", "jupiter", "fi",
    "openfinancial", "setu",
    "cashfree", "juspay", "payu",
    "thoughtworks", "epam",
    "globallogic", "hexaware",
    "mphasis", "virtusa",
    "nagarro", "endava", "globant",
    "softserve", "luxoft",
    "publicissapient", "valtech",
    "accenture", "capgemini",
    "cognizant", "infosys",
    "wipro", "hcl", "tcs",
    "ltimindtree", "techmahindra",
    "persistent", "cyient",
    "kpit", "ltts",
    "quantiphi", "fractal",
    "tigeranalytics", "latenthview",
    "mu-sigma", "gramener",
    "o9", "icertis", "zenoti",
    "whatfix", "gupshup",
    "yellowai", "sprinklr",
    "freshworks", "chargebee",
    "darwinbox", "keka",
    "leadsquared", "exotel",
    "urbancompany", "nobroker",
    "housingcom", "magicbricks",
    "unacademy", "byjus",
    "vedantu", "upgrad",
    "scaler", "interviewbit",
    "hackerrank",
    "innovaccer", "practo",
    "1mg", "pharmeasy",
    "healthifyme", "curefit",
    "blinkit", "zeptonow",
    "bigbasket",
    "delhivery", "shadowfax",
    "bluedart",
    "ttecdigital", "ttec",
    "cprime", "keyloop",
    "redwoodsoftware",
    "highradius", "inovalon",
]

MORE_ASHBY = [
    "openai", "anthropic", "cohere",
    "mistral", "huggingface",
    "perplexity", "groq", "togetherai",
    "fireworksai", "modal", "replicate",
    "cursor", "anysphere", "windsurf",
    "cognition", "devin",
    "factory", "poolside",
    "vercel", "supabase", "neon",
    "planetscale", "convex",
    "clerk", "resend", "knock",
    "inngest", "trigger",
    "temporal", "hatchet",
    "dbt-labs", "hex", "omni",
    "preset", "lightdash",
    "posthog", "june", "amplitude",
    "plain", "pylon", "plainapp",
    "ashby", "gem", "greenhouse",
    "rippling", "deel", "remote",
    "mercury", "brex", "ramp",
    "linear", "height",
    "retool", "airplane",
    "census", "hightouch",
    "airbyte", "fivetran",
    "langfuse", "langchain",
    "pinecone", "weaviate", "qdrant",
    "wandb", "weightsandbiases",
    "scale", "labelbox",
    "snorkel", "appliedcompute",
]


def pull_gh(jobs, token):
    data, status = discover_bulk.get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    if status != 200 or not data:
        return 0
    n = 0
    for item in data.get("jobs") or []:
        loc = (item.get("location") or {}).get("name") or ""
        d.add(jobs, token, item.get("title") or "", loc, item.get("absolute_url") or "", "Greenhouse", item.get("id"))
        n += 1
    return n


def pull_lever(jobs, company):
    data, status = discover_bulk.get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
    if status != 200 or not isinstance(data, list):
        return 0
    n = 0
    for item in data:
        cats = item.get("categories") or {}
        loc = str(cats.get("location") or "")
        if isinstance(cats.get("allLocations"), list):
            loc = " ".join(str(x) for x in cats["allLocations"]) + " " + loc
        d.add(jobs, company, item.get("text") or "", loc, item.get("hostedUrl") or "", "Lever", item.get("id"))
        n += 1
    return n


def pull_ashby(jobs, token):
    data, status = discover_bulk.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
    if status != 200 or not data:
        return 0
    n = 0
    for item in data.get("jobs") or []:
        loc = item.get("location") or ""
        if isinstance(loc, dict):
            loc = " ".join(str(loc.get(k) or "") for k in ("location", "city", "region", "country"))
        if item.get("isRemote"):
            loc = (loc + " Remote").strip()
        d.add(jobs, token, item.get("title") or "", loc, item.get("jobUrl") or "", "Ashby", item.get("id"))
        n += 1
    return n


def main():
    jobs = []
    print("Extra Greenhouse boards...", flush=True)
    for token in MORE_GH:
        pull_gh(jobs, token)
        time.sleep(0.03)
    print("Extra Lever boards...", flush=True)
    for company in MORE_LEVER:
        pull_lever(jobs, company)
        time.sleep(0.03)
    print("Extra Ashby boards...", flush=True)
    for token in MORE_ASHBY:
        pull_ashby(jobs, token)
        time.sleep(0.03)
    print(f"Raw extra rows: {len(jobs)}", flush=True)
    more.merge_and_write(jobs)


if __name__ == "__main__":
    main()
