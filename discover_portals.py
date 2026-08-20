"""Find Hyderabad / Remote-India architect-lead roles on company career portals (Workday)."""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CTX = ssl.create_default_context()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36"
HYD = re.compile(r"hyderabad|telangana|\bhyd\b", re.I)
REMOTE_IN = re.compile(r"(remote|wfh|work from home).{0,40}india|india.{0,40}(remote|wfh)", re.I)
TITLE = re.compile(
    r"technical architect|solution.?s? architect|software architect|cloud architect|"
    r"application architect|\.net architect|principal (software |tech )?engineer|"
    r"staff (software )?engineer|senior staff|technical lead|engineering manager|"
    r"lead (software|engineer|developer)|senior (software|backend|full.?stack|\.net)",
    re.I,
)
SKIP = re.compile(
    r"devops|devsecops|\bsre\b|site reliability|sales engineer|customer engineering|"
    r"layout|embedded|pcie|firmware|rtl |asic |intern|salesforce|servicenow|"
    r"\bsap\b|\bpega\b|guidewire|java\)|java architect|verification engineer",
    re.I,
)
SEARCHES = [
    "Hyderabad architect",
    "Hyderabad principal engineer",
    "Hyderabad staff engineer",
    "Hyderabad senior software",
    "India remote architect",
]
SITES = [
    ("https://micron.wd1.myworkdayjobs.com/wday/cxs/micron/External/jobs", "https://micron.wd1.myworkdayjobs.com/en-US/External", "Micron"),
    ("https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs", "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite", "NVIDIA"),
    ("https://qualcomm.wd5.myworkdayjobs.com/wday/cxs/qualcomm/External/jobs", "https://qualcomm.wd5.myworkdayjobs.com/en-US/External", "Qualcomm"),
    ("https://amd.wd1.myworkdayjobs.com/wday/cxs/amd/careers/jobs", "https://amd.wd1.myworkdayjobs.com/en-US/careers", "AMD"),
    ("https://intel.wd1.myworkdayjobs.com/wday/cxs/intel/external/jobs", "https://intel.wd1.myworkdayjobs.com/en-US/external", "Intel"),
    ("https://cisco.wd5.myworkdayjobs.com/wday/cxs/cisco/cisco_careers/jobs", "https://cisco.wd5.myworkdayjobs.com/en-US/cisco_careers", "Cisco"),
    ("https://dell.wd1.myworkdayjobs.com/wday/cxs/dell/External/jobs", "https://dell.wd1.myworkdayjobs.com/en-US/External", "Dell"),
    ("https://adp.wd5.myworkdayjobs.com/wday/cxs/adp/External/jobs", "https://adp.wd5.myworkdayjobs.com/en-US/External", "ADP"),
    ("https://optum.wd5.myworkdayjobs.com/wday/cxs/optum/OptumCareers/jobs", "https://optum.wd5.myworkdayjobs.com/en-US/OptumCareers", "Optum"),
    ("https://walmart.wd5.myworkdayjobs.com/wday/cxs/walmart/WalmartExternal/jobs", "https://walmart.wd5.myworkdayjobs.com/en-US/WalmartExternal", "Walmart"),
    ("https://jpmorgan.wd5.myworkdayjobs.com/wday/cxs/jpmorgan/jpmcjobs/jobs", "https://jpmorgan.wd5.myworkdayjobs.com/en-US/jpmcjobs", "JPMorgan"),
    ("https://wellsfargo.wd5.myworkdayjobs.com/wday/cxs/wellsfargo/External/jobs", "https://wellsfargo.wd5.myworkdayjobs.com/en-US/External", "WellsFargo"),
    ("https://honeywell.wd1.myworkdayjobs.com/wday/cxs/honeywell/External/jobs", "https://honeywell.wd1.myworkdayjobs.com/en-US/External", "Honeywell"),
    ("https://siemens.wd3.myworkdayjobs.com/wday/cxs/siemens/External/jobs", "https://siemens.wd3.myworkdayjobs.com/en-US/External", "Siemens"),
    ("https://philips.wd3.myworkdayjobs.com/wday/cxs/philips/jobs-and-careers/jobs", "https://philips.wd3.myworkdayjobs.com/en-US/jobs-and-careers", "Philips"),
    ("https://ibm.wd1.myworkdayjobs.com/wday/cxs/ibm/search/jobs", "https://ibm.wd1.myworkdayjobs.com/en-US/search", "IBM"),
    ("https://adobe.wd5.myworkdayjobs.com/wday/cxs/adobe/external_experienced/jobs", "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced", "Adobe"),
    ("https://intuit.wd1.myworkdayjobs.com/wday/cxs/intuit/IntuitCareers/jobs", "https://intuit.wd1.myworkdayjobs.com/en-US/IntuitCareers", "Intuit"),
    ("https://mastercard.wd1.myworkdayjobs.com/wday/cxs/mastercard/CorporateCareers/jobs", "https://mastercard.wd1.myworkdayjobs.com/en-US/CorporateCareers", "Mastercard"),
    ("https://visa.wd1.myworkdayjobs.com/wday/cxs/visa/Visa/jobs", "https://visa.wd1.myworkdayjobs.com/en-US/Visa", "Visa"),
    ("https://paypal.wd1.myworkdayjobs.com/wday/cxs/paypal/jobs/jobs", "https://paypal.wd1.myworkdayjobs.com/en-US/jobs", "PayPal"),
    ("https://uber.wd1.myworkdayjobs.com/wday/cxs/uber/UberJobs/jobs", "https://uber.wd1.myworkdayjobs.com/en-US/UberJobs", "Uber"),
    ("https://barclays.wd3.myworkdayjobs.com/wday/cxs/barclays/External_Career_Site_Barclays/jobs", "https://barclays.wd3.myworkdayjobs.com/en-US/External_Career_Site_Barclays", "Barclays"),
    ("https://citi.wd5.myworkdayjobs.com/wday/cxs/citi/2/jobs", "https://citi.wd5.myworkdayjobs.com/en-US/2", "Citi"),
    ("https://goldmansachs.wd1.myworkdayjobs.com/wday/cxs/goldmansachs/External/jobs", "https://goldmansachs.wd1.myworkdayjobs.com/en-US/External", "GoldmanSachs"),
    ("https://morganstanley.wd1.myworkdayjobs.com/wday/cxs/morganstanley/external/jobs", "https://morganstanley.wd1.myworkdayjobs.com/en-US/external", "MorganStanley"),
    ("https://broadridge.wd1.myworkdayjobs.com/wday/cxs/broadridge/Careers/jobs", "https://broadridge.wd1.myworkdayjobs.com/en-US/Careers", "Broadridge"),
    ("https://thomsonreuters.wd1.myworkdayjobs.com/wday/cxs/thomsonreuters/External_Career_Site/jobs", "https://thomsonreuters.wd1.myworkdayjobs.com/en-US/External_Career_Site", "ThomsonReuters"),
    ("https://spglobal.wd1.myworkdayjobs.com/wday/cxs/spglobal/SPGlobal_Careers/jobs", "https://spglobal.wd1.myworkdayjobs.com/en-US/SPGlobal_Careers", "SPGlobal"),
    ("https://fiserv.wd5.myworkdayjobs.com/wday/cxs/fiserv/FISERVCAREERS/jobs", "https://fiserv.wd5.myworkdayjobs.com/en-US/FISERVCAREERS", "Fiserv"),
    ("https://experian.wd5.myworkdayjobs.com/wday/cxs/experian/Experian_Careers/jobs", "https://experian.wd5.myworkdayjobs.com/en-US/Experian_Careers", "Experian"),
    ("https://ukg.wd1.myworkdayjobs.com/wday/cxs/ukg/UKGCareers/jobs", "https://ukg.wd1.myworkdayjobs.com/en-US/UKGCareers", "UKG"),
    ("https://workday.wd5.myworkdayjobs.com/wday/cxs/workday/Workday/jobs", "https://workday.wd5.myworkdayjobs.com/en-US/Workday", "WorkdayInc"),
    ("https://snowflake.wd1.myworkdayjobs.com/wday/cxs/snowflake/Snowflake/jobs", "https://snowflake.wd1.myworkdayjobs.com/en-US/Snowflake", "Snowflake"),
    ("https://paloaltonetworks.wd1.myworkdayjobs.com/wday/cxs/paloaltonetworks/External/jobs", "https://paloaltonetworks.wd1.myworkdayjobs.com/en-US/External", "PaloAlto"),
    ("https://nutanix.wd1.myworkdayjobs.com/wday/cxs/nutanix/NutanixCareers/jobs", "https://nutanix.wd1.myworkdayjobs.com/en-US/NutanixCareers", "Nutanix"),
    ("https://netapp.wd1.myworkdayjobs.com/wday/cxs/netapp/External/jobs", "https://netapp.wd1.myworkdayjobs.com/en-US/External", "NetApp"),
    ("https://broadcom.wd1.myworkdayjobs.com/wday/cxs/broadcom/External_Career/jobs", "https://broadcom.wd1.myworkdayjobs.com/en-US/External_Career", "Broadcom"),
    ("https://bosch.wd1.myworkdayjobs.com/wday/cxs/bosch/External/jobs", "https://bosch.wd1.myworkdayjobs.com/en-US/External", "Bosch"),
    ("https://abb.wd3.myworkdayjobs.com/wday/cxs/abb/External/jobs", "https://abb.wd3.myworkdayjobs.com/en-US/External", "ABB"),
    ("https://schneider.wd3.myworkdayjobs.com/wday/cxs/schneider/External/jobs", "https://schneider.wd3.myworkdayjobs.com/en-US/External", "Schneider"),
    ("https://ge.wd5.myworkdayjobs.com/wday/cxs/ge/GE_ExternalCareer/jobs", "https://ge.wd5.myworkdayjobs.com/en-US/GE_ExternalCareer", "GE"),
    ("https://statestreet.wd1.myworkdayjobs.com/wday/cxs/statestreet/Global/jobs", "https://statestreet.wd1.myworkdayjobs.com/en-US/Global", "StateStreet"),
    ("https://bnymellon.wd1.myworkdayjobs.com/wday/cxs/bnymellon/BNY/jobs", "https://bnymellon.wd1.myworkdayjobs.com/en-US/BNY", "BNYMellon"),
    ("https://blackrock.wd1.myworkdayjobs.com/wday/cxs/blackrock/BlackRock_External_Career_US/jobs", "https://blackrock.wd1.myworkdayjobs.com/en-US/BlackRock_External_Career_US", "BlackRock"),
    ("https://franklintempleton.wd5.myworkdayjobs.com/wday/cxs/franklintempleton/FTCareers/jobs", "https://franklintempleton.wd5.myworkdayjobs.com/en-US/FTCareers", "FranklinTempleton"),
    ("https://factset.wd1.myworkdayjobs.com/wday/cxs/factset/FactSetCareers/jobs", "https://factset.wd1.myworkdayjobs.com/en-US/FactSetCareers", "FactSet"),
    ("https://moodys.wd1.myworkdayjobs.com/wday/cxs/moodys/MoodysCareers/jobs", "https://moodys.wd1.myworkdayjobs.com/en-US/MoodysCareers", "Moodys"),
    ("https://ssnc.wd1.myworkdayjobs.com/wday/cxs/ssnc/SSNC/jobs", "https://ssnc.wd1.myworkdayjobs.com/en-US/SSNC", "SSNC"),
    ("https://fisglobal.wd5.myworkdayjobs.com/wday/cxs/fisglobal/FIS_Careers/jobs", "https://fisglobal.wd5.myworkdayjobs.com/en-US/FIS_Careers", "FIS"),
    ("https://equifax.wd5.myworkdayjobs.com/wday/cxs/equifax/Equifax/jobs", "https://equifax.wd5.myworkdayjobs.com/en-US/Equifax", "Equifax"),
    ("https://transunion.wd5.myworkdayjobs.com/wday/cxs/transunion/TransUnion/jobs", "https://transunion.wd5.myworkdayjobs.com/en-US/TransUnion", "TransUnion"),
    ("https://fico.wd1.myworkdayjobs.com/wday/cxs/fico/FICO/jobs", "https://fico.wd1.myworkdayjobs.com/en-US/FICO", "FICO"),
    ("https://nasdaq.wd1.myworkdayjobs.com/wday/cxs/nasdaq/Nasdaq_Careers/jobs", "https://nasdaq.wd1.myworkdayjobs.com/en-US/Nasdaq_Careers", "Nasdaq"),
    ("https://lseg.wd3.myworkdayjobs.com/wday/cxs/lseg/LSEG/jobs", "https://lseg.wd3.myworkdayjobs.com/en-US/LSEG", "LSEG"),
    ("https://aon.wd1.myworkdayjobs.com/wday/cxs/aon/aoncareers/jobs", "https://aon.wd1.myworkdayjobs.com/en-US/aoncareers", "Aon"),
    ("https://wtw.wd1.myworkdayjobs.com/wday/cxs/wtw/WTW_Careers/jobs", "https://wtw.wd1.myworkdayjobs.com/en-US/WTW_Careers", "WTW"),
    ("https://analog.wd1.myworkdayjobs.com/wday/cxs/analog/External/jobs", "https://analog.wd1.myworkdayjobs.com/en-US/External", "AnalogDevices"),
    ("https://nxp.wd3.myworkdayjobs.com/wday/cxs/nxp/careers/jobs", "https://nxp.wd3.myworkdayjobs.com/en-US/careers", "NXP"),
    ("https://westerndigital.wd5.myworkdayjobs.com/wday/cxs/westerndigital/WesternDigital/jobs", "https://westerndigital.wd5.myworkdayjobs.com/en-US/WesternDigital", "WesternDigital"),
    ("https://cadence.wd1.myworkdayjobs.com/wday/cxs/cadence/External_Careers/jobs", "https://cadence.wd1.myworkdayjobs.com/en-US/External_Careers", "Cadence"),
    ("https://ansys.wd1.myworkdayjobs.com/wday/cxs/ansys/Ansys/jobs", "https://ansys.wd1.myworkdayjobs.com/en-US/Ansys", "Ansys"),
    ("https://amat.wd1.myworkdayjobs.com/wday/cxs/amat/External/jobs", "https://amat.wd1.myworkdayjobs.com/en-US/External", "AppliedMaterials"),
    ("https://kla.wd1.myworkdayjobs.com/wday/cxs/kla/KLA/jobs", "https://kla.wd1.myworkdayjobs.com/en-US/KLA", "KLA"),
    ("https://kpmg.wd1.myworkdayjobs.com/wday/cxs/kpmg/External/jobs", "https://kpmg.wd1.myworkdayjobs.com/en-US/External", "KPMG"),
]


def get_json(url, data=None):
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": UA, "Accept": "application/json", "Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def loc_ok(loc: str) -> bool:
    loc = loc or ""
    if HYD.search(loc):
        return True
    return bool(REMOTE_IN.search(loc))


def main():
    jobs = []
    seen = set()
    for api, site, company in SITES:
        print(f"  {company}", flush=True)
        for q in SEARCHES:
            payload = json.dumps({"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": q}).encode()
            data = get_json(api, data=payload)
            time.sleep(0.15)
            if not data:
                continue
            for item in data.get("jobPostings") or []:
                title = (item.get("title") or "").strip()
                loc = item.get("locationsText") or ""
                path = item.get("externalPath") or ""
                if not title or not path or SKIP.search(title) or not TITLE.search(title) or not loc_ok(loc):
                    continue
                url = site.rstrip("/") + path
                m = re.search(r"(JR\d+|[A-Z]{2,}\d{4,})", path, re.I)
                jid = m.group(1) if m else path.rstrip("/").split("/")[-1]
                key = (company.lower(), title.lower(), path)
                if key in seen:
                    continue
                seen.add(key)
                jobs.append({
                    "company": company,
                    "title": title,
                    "location": loc,
                    "url": url,
                    "ats": "Workday",
                    "job_id": jid,
                    "title_score": 80,
                    "location_score": 15,
                    "score": 95,
                    "already_applied": False,
                })
    existing = []
    batch_path = ROOT / "data" / "discovery_batch.json"
    if batch_path.exists():
        existing = json.loads(batch_path.read_text(encoding="utf-8"))
    by_key = {}
    for row in existing + jobs:
        by_key[(row.get("company", "").lower(), row.get("title", "").lower(), row.get("job_id") or row.get("url", "")[:80])] = row
    merged = list(by_key.values())
    merged.sort(key=lambda j: (-int(j.get("score") or 0), j.get("company"), j.get("title")))
    batch_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"Portal matches added: {len(jobs)}. Batch now {len(merged)}.", flush=True)
    for j in jobs[:25]:
        print(f"  {j['company']}: {j['title'][:70]} | {j['location'][:40]}", flush=True)


if __name__ == "__main__":
    main()
