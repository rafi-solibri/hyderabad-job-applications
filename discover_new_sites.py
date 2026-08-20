"""New websites: Instahyre, Naukri, YC, Cutshort, Teamtailor, Freshteam, more SR/Workable/GH."""
from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path

import apply_now
import discover_bulk
import discover_final as d
import discover_more_sites as more

ROOT = Path(__file__).resolve().parent

NAUKRI_HEADERS = {
    "appid": "109",
    "systemid": "Naukri",
    "Accept": "application/json",
    "Referer": "https://www.naukri.com/",
}

NAUKRI_QUERIES = [
    "technical architect",
    "solution architect",
    "software architect",
    "principal engineer",
    "staff software engineer",
    "engineering manager",
    "technical lead",
    "senior software engineer",
    ".net architect",
    "lead software engineer",
]

SR_MORE = [
    "Genpact", "WNS", "EXLService", "Firstsource",
    "Mphasis", "Hexaware", "Virtusa", "Cyient",
    "LTTS", "KPIT", "PersistentSystems",
    "SonataSoftware", "Birlasoft", "ValueLabs",
    "Brillio", "Coforge", "Mastek",
    "Zensar", "NIIT", "Newgen",
    "TataElxsi", "TataTechnologies",
    "Mahindra", "TechMahindra",
    "LarsenAndToubro", "LTIMindtree",
    "Sasken", "QuEST", "HCL",
    "Mindtree", "BirlaSoft",
    "UST", "UstGlobal", "CitiusTech",
    "Icertis", "HighRadius", "o9Solutions",
    "Freshworks", "ZohoCorporation",
    "BrowserStack", "Postman",
    "Razorpay", "PhonePe", "Paytm",
    "Swiggy", "Zomato", "Meesho",
    "Flipkart", "Myntra", "Nykaa",
    "OlaCabs", "OlaElectric",
    "AtherEnergy", "Bounce",
    "Delhivery", "EcomExpress",
    "Policybazaar", "ACKO",
    "DigitInsurance", "GoDigit",
    "Unacademy", "PhysicsWallah",
    "upGrad", "Scaler",
    "Innovaccer", "Practo",
    "Tata1mg", "PharmEasy",
    "HealthifyMe", "Curefit",
    "ShareChat", "Dream11",
    "Games24x7", "Nazara",
    "InMobi", "Glance",
    "Dailyhunt", "VerSe",
    "CarDekho", "Spinny", "Cars24",
    "CarWale", "BikeWale",
    "Housing", "NoBroker",
    "Magicbricks", "99acres",
    "UrbanCompany", "Housejoy",
    "BigBasket", "Blinkit", "Zepto",
    "Dunzo", "Shadowfax",
    "Shiprocket", "Porter",
    "ElasticRun", "Loadshare",
    "Jumbotail", "Udaan",
    "OfBusiness", "InfraMarket",
    "Ninjacart", "DeHaat",
    "AbsoluteFoods", "Licious",
    "FreshToHome",
    "JupiterMoney", "FiMoney", "Navi",
    "KreditBee", "MoneyView",
    "Lendingkart", "Indifi",
    "Slice", "UniCards",
    "BharatPe", "MobiKwik",
    "Freecharge", "PayU",
    "Cashfree", "Juspay", "Setu",
    "Groww", "Upstox", "Dhan",
    "AngelOne", "Zerodha",
    "HDFCBank", "ICICIBank", "AxisBank",
    "KotakMahindra", "YesBank",
    "IDFCFirst", "FederalBank",
    "SBI", "BankOfBaroda",
    "BajajFinserv", "BajajFinance",
    "MahindraFinance",
    "TataAIG", "ICICILombard",
    "RelianceJio", "Airtel", "Vi",
    "TataCommunications",
    "Lenskart", "FirstCry", "Purplle",
    "Mamaearth", "Honasa",
    "BoAt", "Noise",
    "Titan", "Tanishq",
    "AsianPaints", "Pidilite",
    "Ultratech", "Adani",
    "RelianceIndustries",
    "TataSteel", "JSW",
    "MahindraGroup",
    "HeroMotocorp", "BajajAuto",
    "TVSMotor", "AshokLeyland",
    "MarutiSuzuki", "TataMotors",
    "HyundaiMotor",
    "SiemensIndia", "ABBIndia",
    "SchneiderIndia", "BoschIndia",
    "HoneywellIndia", "GEIndia",
    "PhilipsIndia", "MedtronicIndia",
    "NovartisIndia", "PfizerIndia",
    "GSKIndia", "SanofiIndia",
    "DrReddys", "SunPharma", "Cipla",
    "Biocon", "DivisLabs",
    "Aurobindo", "Lupin",
    "ApolloHospitals", "Fortis",
    "ManipalHospitals",
    "TCS", "Infosys", "Wipro",
    "Cognizant", "Capgemini", "Accenture",
    "IBMIndia", "OracleIndia",
    "SAPIndia", "MicrosoftIndia",
    "AmazonIndia", "GoogleIndia",
    "AdobeIndia", "IntelIndia",
    "QualcommIndia", "NvidiaIndia",
    "AMDIndia", "MicronIndia",
    "CiscoIndia", "DellIndia",
    "HPEIndia", "JuniperIndia",
]

WORKABLE_MORE = [
    "zepto", "blinkit", "bigbasket",
    "spinny", "cars24", "cardekho",
    "shiprocket", "porter",
    "physicswallah", "classplus",
    "leadschool", "infinitylearn",
    "licious", "freshtohome",
    "jumbotail", "ninjacart",
    "ofbusiness", "inframarket",
    "elasticrun", "loadshare",
    "udaan", "jio",
    "airtel", "vi",
    "lenskart", "firstcry",
    "mamaearth", "boat",
    "ultrahuman", "healthifyme",
    "cultfit", "curefit",
    "jupiter", "fi", "navi",
    "kreditbee", "moneyview",
    "slice", "unicards",
    "dhan", "angelone",
    "inshorts", "dailyhunt",
    "sharechat", "moj",
    "dream11", "mpl",
    "winzo", "rummy",
    "carwale", "bikewale",
    "housingcom", "magicbricks",
    "nobrokerhood",
    "urbanclap", "urbancompany",
    "practo", "1mg",
    "pharmeasy", "orangehealth",
    "titan", "tanishq",
    "boatlifestyle", "noise",
    "ather", "olaelectric",
    "ultraviolette", "simpleenergy",
    "bounce", "yulu",
    "rapido", "nammayatri",
    "redbus", "abhibus",
    "makemytrip", "goibibo",
    "ixigo", "yatra",
    "oyorooms", "treebo",
    "fabhotels", "eazydiner",
    "dineout", "zomato",
    "swiggyinstamart",
]

TEAMTAILOR = [
    "klarna", "n26", "revolut",
    "sumup", "checkout",
    "contentful", "adjust",
    "celonis", "personio",
    "deliveryhero", "hellofresh",
    "zalando", "aboutyou",
    "flixbus", "getyourguide",
    "taxfix", "raisin",
    "infobip", "messagebird",
    "vinted", "wise",
]

FRESHTEAM = [
    "freshworks", "chargebee", "whatfix",
    "gupshup", "yellowai", "zenoti",
    "icertis", "o9solutions",
    "browserstack", "postman",
    "darwinbox", "keka",
    "leadsquared", "exotel",
    "highradius", "innovaccer",
]

GH_INDIA = [
    "zepto", "zeptonow", "blinkit",
    "bigbasket", "grofers",
    "spinny", "cars24", "cardekho",
    "carwale", "bikewale",
    "shiprocket", "porterin", "porter",
    "physicswallah", "pw",
    "classplus", "leadschool",
    "licious", "freshtohome",
    "jumbotail", "ninjacart",
    "ofbusiness", "inframarket",
    "elasticrun", "udaan",
    "ultrahuman", "tangerine",
    "atherenergy", "olaelectric",
    "rapido", "nammayatri",
    "redbus", "makemytrip",
    "goibibo", "ixigo",
    "oyorooms", "treebo",
    "lenskart", "firstcry",
    "mamaearth", "honasa",
    "boat", "noise",
    "jupiter", "fimoney", "navi",
    "kreditbee", "moneyview",
    "slice", "unicards",
    "dhan", "angelone",
    "inshorts", "dailyhunt",
    "sharechat", "mojapp",
    "dream11", "mplgaming",
    "winzo", "nazara",
    "housing", "nobroker",
    "magicbricks", "ninety9acres",
    "urbancompany", "urbanclap",
    "orangehealth", "onemg",
    "pharmeasy", "practo",
    "healthifyme", "cultfit",
    "titancompany", "asianpaints",
    "pidilite", "ultratech",
    "adanigroup", "reliance",
    "tatasteel", "jsw",
    "mahindra", "heromotocorp",
    "bajajauto", "tvsmotor",
    "marutisuzuki", "tatamotors",
    "drreddys", "sunpharma", "cipla",
    "biocon", "divislabs",
    "apollohospitals", "fortis",
    "manipal", "practohealth",
    "ust", "citiustech",
    "coforge", "zensar", "mastek",
    "newgensoft", "sasken",
    "tataelxsi", "tatatechnologies",
    "larsentoubro", "lntecc",
    "genpact", "wns", "exl",
    "firstsource", "teleperformance",
    "concentrix", "sutherland",
    "taskus", "alorica",
]


def pull_instahyre(jobs):
    print("Instahyre...", flush=True)
    offset = 0
    seen = 0
    for _ in range(40):
        url = f"https://www.instahyre.com/api/v1/job_search/?offset={offset}&limit=50"
        data, status = discover_bulk.get_json(url)
        if status != 200 or not data:
            print(f"  status {status} at offset {offset}", flush=True)
            break
        rows = data.get("objects") or data.get("results") or []
        if not rows:
            break
        for item in rows:
            seen += 1
            locs = item.get("locations") or []
            if isinstance(locs, list):
                place = " ".join(str(x) for x in locs)
            else:
                place = str(locs or item.get("locations_raw") or "")
            title = item.get("title") or item.get("candidate_title") or ""
            company = (item.get("employer") or {}).get("company_name") if isinstance(item.get("employer"), dict) else item.get("company_name")
            jid = item.get("id") or item.get("job_id") or ""
            link = item.get("public_url") or (f"https://www.instahyre.com/job-{jid}" if jid else "")
            d.add(jobs, company or "instahyre", title, place, link, "Instahyre", jid)
        nxt = (data.get("meta") or {}).get("next")
        offset += len(rows)
        if not nxt:
            break
        time.sleep(0.08)
    print(f"  scanned {seen} Instahyre rows", flush=True)


def pull_naukri(jobs):
    print("Naukri...", flush=True)
    ok = 0
    for q in NAUKRI_QUERIES:
        for page in (1, 2, 3):
            qs = urllib.parse.urlencode({
                "noOfResults": 20,
                "urlType": "search_by_key_loc",
                "searchType": "adv",
                "keyword": q,
                "location": "hyderabad",
                "pageNo": page,
                "k": q,
                "l": "hyderabad",
                "experience": "10",
            })
            data, status = discover_bulk.get_json(
                f"https://www.naukri.com/jobapi/v3/search?{qs}",
                headers=NAUKRI_HEADERS,
            )
            if status != 200 or not data:
                print(f"  {q!r} page {page} status {status}", flush=True)
                break
            rows = data.get("jobDetails") or []
            if not rows:
                break
            ok += len(rows)
            for item in rows:
                place = " ".join(str(x) for x in (
                    item.get("placeholders") and "",
                    item.get("jobLocation"),
                    item.get("placeholders") if isinstance(item.get("placeholders"), str) else "",
                    " ".join(
                        str(p.get("label") or "")
                        for p in (item.get("placeholders") or [])
                        if isinstance(p, dict)
                    ),
                    item.get("footerPlaceholderLabel") or "",
                ) if x)
                title = item.get("title") or item.get("jobTitle") or ""
                company = item.get("companyName") or item.get("company") or "naukri"
                jid = item.get("jobId") or item.get("id") or ""
                link = item.get("jdURL") or (f"https://www.naukri.com/job-listings-{jid}" if jid else "")
                if link and link.startswith("/"):
                    link = "https://www.naukri.com" + link
                d.add(jobs, company, title, place or "Hyderabad, India", link, "Naukri", jid)
            time.sleep(0.25)
        time.sleep(0.2)
    print(f"  Naukri raw cards {ok}", flush=True)


def pull_yc(jobs):
    print("YC Work at a Startup...", flush=True)
    url = (
        "https://www.workatastartup.com/api/wk/jobs?"
        "demographic=any&hasEquity=any&hasSalary=any&industry=any"
        "&interviewProcess=any&jobType=any&remote=any&role=eng"
        "&role=eng-management&sortBy=created_desc&usa=any"
    )
    data, status = discover_bulk.get_json(url)
    rows = []
    if isinstance(data, dict):
        rows = data.get("jobs") or data.get("data") or []
    elif isinstance(data, list):
        rows = data
    print(f"  status {status} rows {len(rows) if isinstance(rows, list) else 0}", flush=True)
    if not isinstance(rows, list):
        return
    for item in rows:
        company = item.get("company_name") or (item.get("company") or {}).get("name") or "yc"
        title = item.get("title") or item.get("role") or ""
        loc = " ".join(str(x) for x in (
            item.get("location"),
            item.get("pretty_location"),
            "Remote" if item.get("remote") else "",
            item.get("country"),
        ) if x)
        jid = item.get("id") or ""
        link = item.get("url") or f"https://www.workatastartup.com/jobs/{jid}"
        d.add(jobs, company, title, loc, link, "YC", jid)


def pull_cutshort(jobs):
    print("Cutshort...", flush=True)
    for q in ("architect hyderabad", "staff engineer hyderabad", "principal engineer hyderabad"):
        qs = urllib.parse.urlencode({"search": q, "page": 1})
        data, status = discover_bulk.get_json(f"https://cutshort.io/api/jobs?{qs}")
        print(f"  {q!r} status {status}", flush=True)
        if status != 200 or not data:
            continue
        rows = data.get("jobs") or data.get("data") or data.get("results") or []
        if isinstance(data, list):
            rows = data
        if not isinstance(rows, list):
            continue
        for item in rows:
            loc = str(item.get("location") or item.get("city") or "")
            d.add(
                jobs,
                item.get("company") or item.get("company_name") or "cutshort",
                item.get("title") or item.get("job_title") or "",
                loc,
                item.get("url") or item.get("apply_url") or "",
                "Cutshort",
                item.get("id") or item.get("_id") or "",
            )
        time.sleep(0.15)


def pull_teamtailor(jobs):
    print("Teamtailor...", flush=True)
    for slug in TEAMTAILOR:
        data, status = discover_bulk.get_json(f"https://{slug}.teamtailor.com/jobs.json")
        if status != 200 or not data:
            continue
        rows = data if isinstance(data, list) else data.get("jobs") or data.get("data") or []
        if not isinstance(rows, list):
            continue
        for item in rows:
            attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else item
            loc = " ".join(str(x) for x in (
                attrs.get("locations") if not isinstance(attrs.get("locations"), list) else "",
                " ".join(
                    str((x or {}).get("name") or x)
                    for x in (attrs.get("locations") or [])
                    if x
                ),
                attrs.get("remote_status"),
                attrs.get("location"),
            ) if x)
            url = attrs.get("url") or item.get("links", {}).get("careersite-job-url") or ""
            d.add(jobs, slug, attrs.get("title") or item.get("title") or "", loc, url, "Teamtailor", item.get("id") or attrs.get("internal-name"))
        time.sleep(0.05)


def pull_freshteam(jobs):
    print("Freshteam...", flush=True)
    for slug in FRESHTEAM:
        data, status = discover_bulk.get_json(f"https://{slug}.freshteam.com/jobs")
        if status != 200 or not data:
            continue
        rows = data if isinstance(data, list) else data.get("jobs") or []
        if not isinstance(rows, list):
            continue
        for item in rows:
            loc = " ".join(str(x) for x in (
                item.get("location"), item.get("city"), item.get("country"),
                "Remote" if item.get("remote") else "",
            ) if x)
            d.add(jobs, slug, item.get("title") or "", loc, item.get("url") or "", "Freshteam", item.get("id"))
        time.sleep(0.05)


def pull_sr(jobs):
    print("More SmartRecruiters...", flush=True)
    for cid in SR_MORE:
        url = f"https://api.smartrecruiters.com/v1/companies/{cid}/postings?country=in&limit=100&offset=0"
        data, status = discover_bulk.get_json(url)
        if status != 200 or not data:
            continue
        for item in data.get("content") or []:
            loc = item.get("location") or {}
            place = f"{loc.get('city','')} {loc.get('region','')} {loc.get('country','') or loc.get('countryCode','')}"
            if item.get("remote"):
                place += " Remote"
            title = item.get("name") or item.get("title") or ""
            jid = item.get("id") or item.get("uuid") or ""
            ref = item.get("ref") or item.get("postingUrl") or f"https://jobs.smartrecruiters.com/{cid}/{jid}"
            d.add(jobs, cid, title, place, ref, "SmartRecruiters", jid)
        time.sleep(0.04)


def pull_workable(jobs):
    print("More Workable...", flush=True)
    for token in WORKABLE_MORE:
        data, status = discover_bulk.get_json(f"https://apply.workable.com/api/v1/widget/accounts/{token}")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            loc = " ".join(str(x) for x in (
                item.get("city"), item.get("state"), item.get("country"),
                item.get("location"), "Remote" if item.get("telecommuting") else "",
            ) if x)
            d.add(jobs, token, item.get("title") or "", loc, item.get("url") or "", "Workable", item.get("shortcode") or item.get("id"))
        time.sleep(0.04)


def pull_gh(jobs):
    print("India product Greenhouse...", flush=True)
    for token in GH_INDIA:
        data, status = discover_bulk.get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            loc = (item.get("location") or {}).get("name") or ""
            d.add(jobs, token, item.get("title") or "", loc, item.get("absolute_url") or "", "Greenhouse", item.get("id"))
        time.sleep(0.02)


def pull_amazon_more(jobs):
    print("Amazon.jobs extra queries...", flush=True)
    for q in (
        "solution architect", "solutions architect", "principal sde",
        "staff sde", "sde iii", "sde iii .net", "software architect",
        "application architect", "backend architect", "lead sde",
        "senior sde", "engineering manager software",
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
            d.add(jobs, "Amazon", item.get("title") or "", loc, f"https://www.amazon.jobs/en/jobs/{jid}", "Amazon", jid)
        time.sleep(0.15)


def main():
    jobs = []
    pull_instahyre(jobs)
    pull_naukri(jobs)
    pull_yc(jobs)
    pull_cutshort(jobs)
    pull_teamtailor(jobs)
    pull_freshteam(jobs)
    pull_sr(jobs)
    pull_workable(jobs)
    pull_gh(jobs)
    pull_amazon_more(jobs)
    print(f"New-site raw matched rows: {len(jobs)}", flush=True)
    more.merge_and_write(jobs)


if __name__ == "__main__":
    main()
