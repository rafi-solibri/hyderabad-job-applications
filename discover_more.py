"""Second-pass discovery for Hyderabad-only career portals."""
from __future__ import annotations

import json
import re
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

CTX = ssl.create_default_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"
HYD = re.compile(r"hyderabad|gachibowli|madhapur|financial district|nanakramguda|kondapur|raidurg", re.I)
TITLE = re.compile(r"architect|principal engineer|staff engineer|principal software|technical lead|staff software", re.I)
SKIP = re.compile(r"intern|sales engineer|account executive|recruiter|firmware|hardware", re.I)

LEVER = [
    "keyloop", "dnb", "cprime", "ttecdigital", "ncrvoyix", "adp",
    "highradius", "inovalon", "crunchyroll", "zscaler",
    "phonepe", "razorpay", "swiggy", "zomato", "flipkart", "meesho",
    "freshworks", "postman", "browserstack", "chargebee",
    "innovaccer", "o9solutions", "whatfix", "mindtickle", "gupshup",
    "practo", "cyient", "ltimindtree", "hexaware", "mphasis",
    "virtusa", "persistent", "valuelabs", "epam", "globallogic",
    "broadridge", "factset", "spglobal", "cotiviti", "optum",
    "wellsfargo", "jpmorganchase", "goldmansachs", "bankofamerica",
    "hsbc", "barclays", "dbs", "invesco", "franklintempleton",
    "deloitte", "pwc", "ey", "kpmg", "capgemini", "accenture",
    "cognizant", "infosys", "wipro", "hcltech", "techmahindra",
    "servicenow", "salesforce", "oracle", "sap", "adobe",
    "nvidia", "qualcomm", "amd", "micron", "intel", "cisco",
    "pega", "uipath", "informatica", "opentext",
    "ncr", "dieboldnixdorf", "fiserv", "fis",
    "genpact", "exl", "brillio", "sonata", "birlasoft",
    "kpit", "tataelxsi", "ltts", "cyientinc",
]

GH = [
    "highradius", "inovalon", "crunchyroll", "zscaler", "ncrvoyix",
    "phonepe", "razorpay", "swiggy", "zomato", "flipkart",
    "freshworks", "postman", "browserstack", "chargebee",
    "innovaccer", "o9solutions", "whatfix", "mindtickle", "gupshup",
    "practo", "cyient", "persistent", "valuelabs", "epam",
    "broadridge", "factset", "cotiviti", "pega", "uipath",
    "ncr", "adp", "optum", "servicenow", "salesforce",
    "nvidia", "qualcomm", "amd", "micron",
    "brillio", "sonatasoftware", "birlasoft", "kpit",
    "ltts", "hexaware", "mphasis", "virtusa",
    "thoughtworks", "globallogic", "informatica",
    "opentext", "teradata", "sas",
    "invesco", "franklintempleton", "blackrock",
    "statestreet", "bnymellon", "ssnc",
]


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace")), resp.status
    except Exception as e:
        return None, 0


def ok(title, loc):
    blob = f"{title} {loc}"
    return bool(HYD.search(blob) and TITLE.search(title) and not SKIP.search(title))


def main():
    jobs = []
    for token in GH:
        data, status = get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        if status != 200 or not data:
            continue
        for item in data.get("jobs") or []:
            title = item.get("title") or ""
            loc = (item.get("location") or {}).get("name") or ""
            if not ok(title, loc):
                continue
            jobs.append({
                "company": token, "title": title, "location": loc,
                "url": item.get("absolute_url") or "", "ats": "Greenhouse",
                "job_id": str(item.get("id") or ""), "board": token,
            })
        print(f"GH {token}: scanned", flush=True)

    for company in LEVER:
        data, status = get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
        if status != 200 or not isinstance(data, list):
            continue
        for item in data:
            title = item.get("text") or ""
            cats = item.get("categories") or {}
            loc = str(cats.get("location") or "")
            if isinstance(cats.get("allLocations"), list):
                loc = " ".join(cats["allLocations"]) + " " + loc
            if not ok(title, loc):
                continue
            jobs.append({
                "company": company, "title": title, "location": loc,
                "url": item.get("hostedUrl") or "", "ats": "Lever",
                "job_id": item.get("id") or "", "board": company,
            })
        print(f"LV {company}: scanned", flush=True)

    # Microsoft
    payload = json.dumps({
        "locale": "en_us",
        "domain": "https://jobs.careers.microsoft.com",
        "offset": 0,
        "searchText": "architect",
        "filters": [
            {"field": "country", "term": "India"},
            {"field": "city", "term": "Hyderabad"},
        ],
        "limit": 40,
    }).encode()
    req = urllib.request.Request(
        "https://gcsservices.careers.microsoft.com/search/api/v1/search",
        data=payload,
        headers={"User-Agent": UA, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=25) as resp:
            ms = json.loads(resp.read().decode())
        items = ((ms.get("operationResult") or {}).get("result") or {}).get("jobs") or []
        print(f"MS jobs raw: {len(items)}", flush=True)
        for item in items:
            title = item.get("title") or ""
            props = item.get("properties") or {}
            loc = str(props.get("primaryLocation") or props.get("city") or "")
            if not ok(title, loc) and not (HYD.search(loc) and TITLE.search(title)):
                continue
            jid = item.get("jobId")
            jobs.append({
                "company": "Microsoft", "title": title, "location": loc,
                "url": f"https://jobs.careers.microsoft.com/global/en/job/{jid}",
                "ats": "Microsoft", "job_id": str(jid),
            })
    except Exception as e:
        print("MS failed", e, flush=True)

    Path("data/more_jobs.json").write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    print("MORE", len(jobs))
    for j in jobs:
        print(f"{j['ats']}\t{j['company']}\t{j['title']}\t{j['location']}\t{j['url']}")


if __name__ == "__main__":
    main()
