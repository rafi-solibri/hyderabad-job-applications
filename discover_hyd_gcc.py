"""Hyderabad GCC / product career portals — Madhapur, Gachibowli, Financial District.

Searches official company sites (Phenom/SmashFly, Workday, Eightfold, Apple)
that were missing from ATS-slug discovery (e.g. schwabjobs.com).
"""
from __future__ import annotations

import html as htmlmod
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import apply_now
import discover_final as d
import discover_more_sites as more
import discover_portals

ROOT = Path(__file__).resolve().parent
CTX = ssl.create_default_context()
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# Official career sites for companies with Hyd campuses (Hitec / Madhapur /
# Gachibowli / Financial District / Nanakramguda / Raidurg / Kondapur).
# kind: smashfly | workday | eightfold | apple | custom | listed
PORTALS = [
    # --- Financial District / Nanakramguda / Gachibowli banks & markets ---
    {"company": "Charles Schwab", "url": "https://www.schwabjobs.com/", "hub": "Financial District", "kind": "smashfly", "host": "www.schwabjobs.com"},
    {"company": "Charles Schwab India", "url": "https://www.schwabjobs.com/India", "hub": "Financial District", "kind": "smashfly", "host": "www.schwabjobs.com"},
    {"company": "Fidelity", "url": "https://jobs.fidelity.com/", "hub": "Gachibowli / FD", "kind": "smashfly", "host": "jobs.fidelity.com"},
    {"company": "Vanguard", "url": "https://www.vanguardjobs.com/", "hub": "Gachibowli", "kind": "smashfly", "host": "www.vanguardjobs.com"},
    {"company": "Vanguard India", "url": "https://vanguard.in/", "hub": "Gachibowli", "kind": "listed"},
    {"company": "American Express", "url": "https://jobs.americanexpress.com/", "hub": "Gachibowli / FD", "kind": "smashfly", "host": "jobs.americanexpress.com"},
    {"company": "DTCC", "url": "https://careers.dtcc.com/", "hub": "Financial District", "kind": "smashfly", "host": "careers.dtcc.com"},
    {"company": "State Street", "url": "https://statestreet.wd1.myworkdayjobs.com/en-US/Global", "hub": "Financial District", "kind": "workday", "api": "https://statestreet.wd1.myworkdayjobs.com/wday/cxs/statestreet/Global/jobs", "site": "https://statestreet.wd1.myworkdayjobs.com/en-US/Global"},
    {"company": "BNY Mellon", "url": "https://bnymellon.wd1.myworkdayjobs.com/en-US/BNY", "hub": "Financial District", "kind": "workday", "api": "https://bnymellon.wd1.myworkdayjobs.com/wday/cxs/bnymellon/BNY/jobs", "site": "https://bnymellon.wd1.myworkdayjobs.com/en-US/BNY"},
    {"company": "BlackRock", "url": "https://blackrock.wd1.myworkdayjobs.com/en-US/BlackRock_External_Career_US", "hub": "Gachibowli / FD", "kind": "workday", "api": "https://blackrock.wd1.myworkdayjobs.com/wday/cxs/blackrock/BlackRock_External_Career_US/jobs", "site": "https://blackrock.wd1.myworkdayjobs.com/en-US/BlackRock_External_Career_US"},
    {"company": "Invesco", "url": "https://careers.invesco.com/", "hub": "Financial District", "kind": "smashfly", "host": "careers.invesco.com"},
    {"company": "Franklin Templeton", "url": "https://franklintempleton.wd5.myworkdayjobs.com/en-US/FTCareers", "hub": "Financial District", "kind": "workday", "api": "https://franklintempleton.wd5.myworkdayjobs.com/wday/cxs/franklintempleton/FTCareers/jobs", "site": "https://franklintempleton.wd5.myworkdayjobs.com/en-US/FTCareers"},
    {"company": "Synchrony", "url": "https://jobs.synchrony.com/", "hub": "Gachibowli", "kind": "smashfly", "host": "jobs.synchrony.com"},
    {"company": "UBS", "url": "https://jobs.ubs.com/", "hub": "Financial District", "kind": "smashfly", "host": "jobs.ubs.com"},
    {"company": "DBS", "url": "https://careers.dbs.com/", "hub": "Financial District", "kind": "custom"},
    {"company": "ANZ", "url": "https://careers.anz.com/", "hub": "Gachibowli", "kind": "custom"},
    {"company": "Macquarie", "url": "https://www.macquarie.com/careers.html", "hub": "Gachibowli", "kind": "custom"},
    {"company": "Nomura", "url": "https://www.nomuraholdings.com/careers/", "hub": "Financial District", "kind": "custom"},
    {"company": "Societe Generale", "url": "https://careers.societegenerale.com/", "hub": "Financial District", "kind": "custom"},
    {"company": "BNP Paribas", "url": "https://group.bnpparibas/en/careers", "hub": "Financial District", "kind": "custom"},
    {"company": "Wells Fargo", "url": "https://wellsfargo.wd5.myworkdayjobs.com/en-US/External", "hub": "Financial District", "kind": "existing"},
    {"company": "JPMorgan", "url": "https://jpmorgan.wd5.myworkdayjobs.com/en-US/jpmcjobs", "hub": "Financial District", "kind": "existing"},
    {"company": "Bank of America", "url": "https://bankofamerica.wd1.myworkdayjobs.com/en-US/External_Careers", "hub": "Financial District", "kind": "existing"},
    {"company": "Goldman Sachs", "url": "https://goldmansachs.wd1.myworkdayjobs.com/en-US/External", "hub": "Financial District", "kind": "existing"},
    {"company": "Morgan Stanley", "url": "https://morganstanley.wd1.myworkdayjobs.com/en-US/external", "hub": "Financial District", "kind": "existing"},
    {"company": "Citi", "url": "https://citi.wd5.myworkdayjobs.com/en-US/2", "hub": "Financial District", "kind": "existing"},
    {"company": "Barclays", "url": "https://barclays.wd3.myworkdayjobs.com/en-US/External_Career_Site_Barclays", "hub": "Financial District", "kind": "existing"},
    {"company": "HSBC", "url": "https://hsbc.wd3.myworkdayjobs.com/en-US/External", "hub": "RMZ Nexity / Knowledge City / FD", "kind": "existing"},
    {"company": "Deutsche Bank", "url": "https://db.wd3.myworkdayjobs.com/en-US/ExternalCareerSite", "hub": "Financial District", "kind": "existing"},
    {"company": "Standard Chartered", "url": "https://standardchartered.wd3.myworkdayjobs.com/en-US/Careers", "hub": "Financial District", "kind": "existing"},
    {"company": "Capital One", "url": "https://capitalone.wd1.myworkdayjobs.com/en-US/Capital_One", "hub": "Gachibowli", "kind": "existing"},
    {"company": "Visa", "url": "https://visa.wd1.myworkdayjobs.com/en-US/Visa", "hub": "Financial District", "kind": "existing"},
    {"company": "Mastercard", "url": "https://mastercard.wd1.myworkdayjobs.com/en-US/CorporateCareers", "hub": "Financial District", "kind": "existing"},
    {"company": "PayPal", "url": "https://paypal.wd1.myworkdayjobs.com/en-US/jobs", "hub": "Gachibowli", "kind": "existing"},
    {"company": "Broadridge", "url": "https://broadridge.wd1.myworkdayjobs.com/en-US/Careers", "hub": "Financial District", "kind": "existing"},
    {"company": "FactSet", "url": "https://factset.wd1.myworkdayjobs.com/en-US/FactSetCareers", "hub": "Financial District", "kind": "workday", "api": "https://factset.wd1.myworkdayjobs.com/wday/cxs/factset/FactSetCareers/jobs", "site": "https://factset.wd1.myworkdayjobs.com/en-US/FactSetCareers"},
    {"company": "S&P Global", "url": "https://spglobal.wd1.myworkdayjobs.com/en-US/SPGlobal_Careers", "hub": "Financial District", "kind": "existing"},
    {"company": "Thomson Reuters", "url": "https://thomsonreuters.wd1.myworkdayjobs.com/en-US/External_Career_Site", "hub": "Financial District", "kind": "existing"},
    {"company": "Moodys", "url": "https://moodys.wd1.myworkdayjobs.com/en-US/MoodysCareers", "hub": "Financial District", "kind": "workday", "api": "https://moodys.wd1.myworkdayjobs.com/wday/cxs/moodys/MoodysCareers/jobs", "site": "https://moodys.wd1.myworkdayjobs.com/en-US/MoodysCareers"},
    {"company": "SS&C", "url": "https://ssnc.wd1.myworkdayjobs.com/en-US/SSNC", "hub": "Financial District", "kind": "workday", "api": "https://ssnc.wd1.myworkdayjobs.com/wday/cxs/ssnc/SSNC/jobs", "site": "https://ssnc.wd1.myworkdayjobs.com/en-US/SSNC"},
    {"company": "FIS", "url": "https://fisglobal.wd5.myworkdayjobs.com/en-US/FIS_Careers", "hub": "Financial District", "kind": "workday", "api": "https://fisglobal.wd5.myworkdayjobs.com/wday/cxs/fisglobal/FIS_Careers/jobs", "site": "https://fisglobal.wd5.myworkdayjobs.com/en-US/FIS_Careers"},
    {"company": "Fiserv", "url": "https://fiserv.wd5.myworkdayjobs.com/en-US/FISERVCAREERS", "hub": "Financial District", "kind": "existing"},
    {"company": "Experian", "url": "https://experian.wd5.myworkdayjobs.com/en-US/Experian_Careers", "hub": "Gachibowli", "kind": "existing"},
    {"company": "Equifax", "url": "https://equifax.wd5.myworkdayjobs.com/en-US/Equifax", "hub": "Gachibowli", "kind": "workday", "api": "https://equifax.wd5.myworkdayjobs.com/wday/cxs/equifax/Equifax/jobs", "site": "https://equifax.wd5.myworkdayjobs.com/en-US/Equifax"},
    {"company": "TransUnion", "url": "https://transunion.wd5.myworkdayjobs.com/en-US/TransUnion", "hub": "Gachibowli", "kind": "workday", "api": "https://transunion.wd5.myworkdayjobs.com/wday/cxs/transunion/TransUnion/jobs", "site": "https://transunion.wd5.myworkdayjobs.com/en-US/TransUnion"},
    {"company": "FICO", "url": "https://fico.wd1.myworkdayjobs.com/en-US/FICO", "hub": "Gachibowli", "kind": "workday", "api": "https://fico.wd1.myworkdayjobs.com/wday/cxs/fico/FICO/jobs", "site": "https://fico.wd1.myworkdayjobs.com/en-US/FICO"},
    {"company": "Nasdaq", "url": "https://nasdaq.wd1.myworkdayjobs.com/en-US/Nasdaq_Careers", "hub": "Financial District", "kind": "workday", "api": "https://nasdaq.wd1.myworkdayjobs.com/wday/cxs/nasdaq/Nasdaq_Careers/jobs", "site": "https://nasdaq.wd1.myworkdayjobs.com/en-US/Nasdaq_Careers"},
    {"company": "ICE", "url": "https://careers.ice.com/", "hub": "Financial District", "kind": "smashfly", "host": "careers.ice.com"},
    {"company": "LSEG", "url": "https://lseg.wd3.myworkdayjobs.com/en-US/LSEG", "hub": "Financial District", "kind": "workday", "api": "https://lseg.wd3.myworkdayjobs.com/wday/cxs/lseg/LSEG/jobs", "site": "https://lseg.wd3.myworkdayjobs.com/en-US/LSEG"},
    {"company": "Aon", "url": "https://aon.wd1.myworkdayjobs.com/en-US/aoncareers", "hub": "Financial District", "kind": "workday", "api": "https://aon.wd1.myworkdayjobs.com/wday/cxs/aon/aoncareers/jobs", "site": "https://aon.wd1.myworkdayjobs.com/en-US/aoncareers"},
    {"company": "WTW", "url": "https://wtw.wd1.myworkdayjobs.com/en-US/WTW_Careers", "hub": "Financial District", "kind": "workday", "api": "https://wtw.wd1.myworkdayjobs.com/wday/cxs/wtw/WTW_Careers/jobs", "site": "https://wtw.wd1.myworkdayjobs.com/en-US/WTW_Careers"},
    {"company": "ADP", "url": "https://adp.wd5.myworkdayjobs.com/en-US/External", "hub": "Gachibowli / Hitec", "kind": "existing"},
    {"company": "UKG", "url": "https://ukg.wd1.myworkdayjobs.com/en-US/UKGCareers", "hub": "Gachibowli", "kind": "existing"},
    {"company": "Workday", "url": "https://workday.wd5.myworkdayjobs.com/en-US/Workday", "hub": "Gachibowli", "kind": "existing"},
    # --- Big tech ---
    {"company": "Microsoft", "url": "https://jobs.careers.microsoft.com/", "hub": "Gachibowli / Hitec", "kind": "existing"},
    {"company": "Google", "url": "https://careers.google.com/", "hub": "Gachibowli / Financial District", "kind": "existing"},
    {"company": "Amazon", "url": "https://www.amazon.jobs/", "hub": "Financial District / Hitec", "kind": "existing"},
    {"company": "Apple", "url": "https://jobs.apple.com/", "hub": "RMZ Nexity / Knowledge City", "kind": "apple"},
    {"company": "Meta", "url": "https://www.metacareers.com/", "hub": "Gachibowli", "kind": "custom"},
    {"company": "LinkedIn", "url": "https://careers.linkedin.com/", "hub": "Gachibowli", "kind": "custom"},
    {"company": "Uber", "url": "https://uber.wd1.myworkdayjobs.com/en-US/UberJobs", "hub": "Gachibowli", "kind": "existing"},
    {"company": "Walmart", "url": "https://walmart.wd5.myworkdayjobs.com/en-US/WalmartExternal", "hub": "Financial District", "kind": "existing"},
    # --- Semiconductor / hardware GCCs ---
    {"company": "Qualcomm", "url": "https://qualcomm.wd5.myworkdayjobs.com/en-US/External", "hub": "Hitec / Madhapur", "kind": "existing"},
    {"company": "NVIDIA", "url": "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite", "hub": "Financial District", "kind": "existing"},
    {"company": "AMD", "url": "https://amd.wd1.myworkdayjobs.com/en-US/careers", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Intel", "url": "https://intel.wd1.myworkdayjobs.com/en-US/external", "hub": "Hitec", "kind": "existing"},
    {"company": "Micron", "url": "https://micron.wd1.myworkdayjobs.com/en-US/External", "hub": "Financial District", "kind": "existing"},
    {"company": "Broadcom", "url": "https://broadcom.wd1.myworkdayjobs.com/en-US/External_Career", "hub": "Hitec", "kind": "existing"},
    {"company": "Analog Devices", "url": "https://analog.wd1.myworkdayjobs.com/en-US/External", "hub": "Hitec", "kind": "workday", "api": "https://analog.wd1.myworkdayjobs.com/wday/cxs/analog/External/jobs", "site": "https://analog.wd1.myworkdayjobs.com/en-US/External"},
    {"company": "Texas Instruments", "url": "https://careers.ti.com/", "hub": "Hitec / Gachibowli", "kind": "custom"},
    {"company": "NXP", "url": "https://nxp.wd3.myworkdayjobs.com/en-US/careers", "hub": "Hitec", "kind": "workday", "api": "https://nxp.wd3.myworkdayjobs.com/wday/cxs/nxp/careers/jobs", "site": "https://nxp.wd3.myworkdayjobs.com/en-US/careers"},
    {"company": "Western Digital", "url": "https://westerndigital.wd5.myworkdayjobs.com/en-US/WesternDigital", "hub": "Hitec", "kind": "workday", "api": "https://westerndigital.wd5.myworkdayjobs.com/wday/cxs/westerndigital/WesternDigital/jobs", "site": "https://westerndigital.wd5.myworkdayjobs.com/en-US/WesternDigital"},
    {"company": "Samsung", "url": "https://www.samsungcareers.com/", "hub": "Hitec", "kind": "custom"},
    {"company": "Synopsys", "url": "https://sjobs.brassring.com/TGnewUI/Search/Home/Home?partnerid=25235&siteid=5359", "hub": "Hitec / Madhapur", "kind": "custom"},
    {"company": "Cadence", "url": "https://cadence.wd1.myworkdayjobs.com/en-US/External_Careers", "hub": "Hitec", "kind": "workday", "api": "https://cadence.wd1.myworkdayjobs.com/wday/cxs/cadence/External_Careers/jobs", "site": "https://cadence.wd1.myworkdayjobs.com/en-US/External_Careers"},
    {"company": "Ansys", "url": "https://ansys.wd1.myworkdayjobs.com/en-US/Ansys", "hub": "Hitec / Gachibowli", "kind": "workday", "api": "https://ansys.wd1.myworkdayjobs.com/wday/cxs/ansys/Ansys/jobs", "site": "https://ansys.wd1.myworkdayjobs.com/en-US/Ansys"},
    {"company": "Applied Materials", "url": "https://amat.wd1.myworkdayjobs.com/en-US/External", "hub": "Hitec", "kind": "workday", "api": "https://amat.wd1.myworkdayjobs.com/wday/cxs/amat/External/jobs", "site": "https://amat.wd1.myworkdayjobs.com/en-US/External"},
    {"company": "Lam Research", "url": "https://careers.lamresearch.com/", "hub": "Hitec", "kind": "custom"},
    {"company": "KLA", "url": "https://kla.wd1.myworkdayjobs.com/en-US/KLA", "hub": "Hitec", "kind": "workday", "api": "https://kla.wd1.myworkdayjobs.com/wday/cxs/kla/KLA/jobs", "site": "https://kla.wd1.myworkdayjobs.com/en-US/KLA"},
    # --- Enterprise software / cloud ---
    {"company": "Cisco", "url": "https://cisco.wd5.myworkdayjobs.com/en-US/cisco_careers", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Dell", "url": "https://dell.wd1.myworkdayjobs.com/en-US/External", "hub": "Hitec", "kind": "existing"},
    {"company": "IBM", "url": "https://ibm.wd1.myworkdayjobs.com/en-US/search", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Oracle", "url": "https://oracle.wd1.myworkdayjobs.com/en-US/External", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Adobe", "url": "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Intuit", "url": "https://intuit.wd1.myworkdayjobs.com/en-US/IntuitCareers", "hub": "Gachibowli", "kind": "existing"},
    {"company": "Red Hat", "url": "https://redhat.wd5.myworkdayjobs.com/en-US/jobs", "hub": "Gachibowli", "kind": "existing"},
    {"company": "VMware", "url": "https://vmware.wd1.myworkdayjobs.com/en-US/External", "hub": "Hitec", "kind": "existing"},
    {"company": "Nutanix", "url": "https://nutanix.wd1.myworkdayjobs.com/en-US/NutanixCareers", "hub": "Hitec", "kind": "existing"},
    {"company": "NetApp", "url": "https://netapp.wd1.myworkdayjobs.com/en-US/External", "hub": "Hitec", "kind": "existing"},
    {"company": "Palo Alto Networks", "url": "https://paloaltonetworks.wd1.myworkdayjobs.com/en-US/External", "hub": "Gachibowli", "kind": "existing"},
    {"company": "Snowflake", "url": "https://snowflake.wd1.myworkdayjobs.com/en-US/Snowflake", "hub": "Gachibowli", "kind": "existing"},
    {"company": "Databricks", "url": "https://www.databricks.com/company/careers", "hub": "Gachibowli", "kind": "existing"},
    {"company": "SAP", "url": "https://jobs.sap.com/", "hub": "Gachibowli / Hitec", "kind": "custom"},
    {"company": "ServiceNow", "url": "https://careers.servicenow.com/", "hub": "Gachibowli", "kind": "listed", "note": "titles skipped"},
    {"company": "Salesforce", "url": "https://careers.salesforce.com/", "hub": "Gachibowli", "kind": "listed", "note": "titles skipped"},
    {"company": "Coupa", "url": "https://www.coupa.com/careers", "hub": "Gachibowli", "kind": "existing"},
    {"company": "Infor", "url": "https://careers.infor.com/", "hub": "Hitec", "kind": "custom"},
    {"company": "Teradata", "url": "https://careers.teradata.com/", "hub": "Hitec", "kind": "custom"},
    {"company": "Informatica", "url": "https://careers.informatica.com/", "hub": "Hitec / Gachibowli", "kind": "custom"},
    {"company": "OpenText", "url": "https://careers.opentext.com/", "hub": "Hitec", "kind": "custom"},
    {"company": "SAS", "url": "https://www.sas.com/en_us/careers.html", "hub": "Hitec", "kind": "custom"},
    {"company": "Autodesk", "url": "https://autodesk.wd1.myworkdayjobs.com/en-US/Ext", "hub": "Hitec", "kind": "existing"},
    # --- Healthcare / insurance GCCs ---
    {"company": "Optum", "url": "https://optum.wd5.myworkdayjobs.com/en-US/OptumCareers", "hub": "Financial District", "kind": "existing"},
    {"company": "UnitedHealth", "url": "https://careers.unitedhealthgroup.com/", "hub": "Financial District", "kind": "existing"},
    {"company": "Cotiviti", "url": "https://careers.cotiviti.com/", "hub": "Hitec / Gachibowli", "kind": "smashfly", "host": "careers.cotiviti.com"},
    {"company": "Inovalon", "url": "https://www.inovalon.com/company/careers/", "hub": "Hitec", "kind": "existing"},
    {"company": "HighRadius", "url": "https://www.highradius.com/careers/", "hub": "Madhapur / Hitec", "kind": "existing"},
    {"company": "Innovaccer", "url": "https://innovaccer.com/careers", "hub": "Hitec", "kind": "existing"},
    {"company": "Medtronic", "url": "https://medtronic.wd1.myworkdayjobs.com/en-US/MedtronicCareers", "hub": "Hitec", "kind": "existing"},
    {"company": "Amgen", "url": "https://amgen.wd1.myworkdayjobs.com/en-US/Careers", "hub": "RMZ Nexity / RMZ Spire", "kind": "existing"},
    {"company": "Novartis", "url": "https://novartis.wd3.myworkdayjobs.com/en-US/careers", "hub": "Hitec", "kind": "existing"},
    {"company": "Pfizer", "url": "https://pfizer.wd1.myworkdayjobs.com/en-US/PfizerCareers", "hub": "Hitec", "kind": "existing"},
    {"company": "GSK", "url": "https://gsk.wd5.myworkdayjobs.com/en-US/GSKCareers", "hub": "Hitec", "kind": "existing"},
    {"company": "J&J", "url": "https://johnsonandjohnson.wd5.myworkdayjobs.com/en-US/jnj", "hub": "Hitec", "kind": "existing"},
    {"company": "Philips", "url": "https://philips.wd3.myworkdayjobs.com/en-US/jobs-and-careers", "hub": "Hitec", "kind": "existing"},
    # --- Consulting / IT services with large Hyd campuses ---
    {"company": "Accenture", "url": "https://www.accenture.com/in-en/careers", "hub": "Hitec / Gachibowli / FD", "kind": "existing"},
    {"company": "Deloitte", "url": "https://deloitte.wd1.myworkdayjobs.com/en-US/DeloitteCareers", "hub": "RMZ Futura / Raheja Mindspace / FD", "kind": "existing"},
    {"company": "PwC", "url": "https://pwc.wd3.myworkdayjobs.com/en-US/External_Careers", "hub": "Financial District", "kind": "existing"},
    {"company": "EY", "url": "https://ey.wd1.myworkdayjobs.com/en-US/EYCareers", "hub": "Financial District", "kind": "existing"},
    {"company": "KPMG", "url": "https://kpmg.wd1.myworkdayjobs.com/en-US/External", "hub": "RMZ Nexity / Knowledge City", "kind": "workday", "api": "https://kpmg.wd1.myworkdayjobs.com/wday/cxs/kpmg/External/jobs", "site": "https://kpmg.wd1.myworkdayjobs.com/en-US/External"},
    {"company": "Cognizant", "url": "https://careers.cognizant.com/", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Infosys", "url": "https://www.infosys.com/careers/", "hub": "Gachibowli / Pocharam", "kind": "existing"},
    {"company": "Wipro", "url": "https://careers.wipro.com/", "hub": "Gachibowli / Manikonda", "kind": "existing"},
    {"company": "TCS", "url": "https://www.tcs.com/careers", "hub": "Gachibowli / Deccan Park", "kind": "custom"},
    {"company": "HCLTech", "url": "https://www.hcltech.com/careers", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Tech Mahindra", "url": "https://careers.techmahindra.com/", "hub": "Hitec / Madhapur", "kind": "existing"},
    {"company": "Capgemini", "url": "https://www.capgemini.com/careers/", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "LTIMindtree", "url": "https://www.ltimindtree.com/careers/", "hub": "Hitec", "kind": "existing"},
    {"company": "Genpact", "url": "https://www.genpact.com/careers", "hub": "Hitec / Gachibowli", "kind": "custom"},
    {"company": "Hexaware", "url": "https://hexaware.com/careers/", "hub": "Hitec", "kind": "existing"},
    {"company": "Mphasis", "url": "https://www.mphasis.com/home/careers.html", "hub": "Hitec", "kind": "existing"},
    {"company": "Virtusa", "url": "https://www.virtusa.com/careers", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Persistent", "url": "https://www.persistent.com/careers/", "hub": "Hitec", "kind": "existing"},
    {"company": "Cyient", "url": "https://www.cyient.com/careers", "hub": "Hitec / Madhapur", "kind": "existing"},
    {"company": "ValueLabs", "url": "https://www.valuelabs.com/careers/", "hub": "Hitec / Madhapur", "kind": "custom"},
    {"company": "EPAM", "url": "https://www.epam.com/careers", "hub": "Gachibowli", "kind": "existing"},
    {"company": "GlobalLogic", "url": "https://www.globallogic.com/careers/", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Thoughtworks", "url": "https://www.thoughtworks.com/careers", "hub": "Gachibowli", "kind": "existing"},
    {"company": "Nagarro", "url": "https://www.nagarro.com/en/careers", "hub": "Hitec", "kind": "existing"},
    {"company": "Publicis Sapient", "url": "https://careers.publicissapient.com/", "hub": "Hitec", "kind": "existing"},
    # --- Industrial / auto / energy ---
    {"company": "Honeywell", "url": "https://honeywell.wd1.myworkdayjobs.com/en-US/External", "hub": "Gachibowli / Hitec", "kind": "existing"},
    {"company": "Siemens", "url": "https://siemens.wd3.myworkdayjobs.com/en-US/External", "hub": "Gachibowli", "kind": "existing"},
    {"company": "GE Vernova", "url": "https://ge.wd5.myworkdayjobs.com/en-US/GE_ExternalCareer", "hub": "Raheja Mindspace", "kind": "existing"},
    {"company": "Bosch", "url": "https://bosch.wd1.myworkdayjobs.com/en-US/External", "hub": "Gachibowli", "kind": "existing"},
    {"company": "ABB", "url": "https://abb.wd3.myworkdayjobs.com/en-US/External", "hub": "Hitec", "kind": "existing"},
    {"company": "Schneider", "url": "https://schneider.wd3.myworkdayjobs.com/en-US/External", "hub": "Hitec", "kind": "existing"},
    {"company": "Cummins", "url": "https://cummins.wd5.myworkdayjobs.com/en-US/External", "hub": "Hitec", "kind": "existing"},
    {"company": "Eaton", "url": "https://eaton.wd1.myworkdayjobs.com/en-US/EatonExternal", "hub": "Hitec", "kind": "existing"},
    # --- Product / India HQ in Hyd hubs ---
    {"company": "Freshworks", "url": "https://www.freshworks.com/company/careers/", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Zoho", "url": "https://careers.zoho.com/", "hub": "listed (Chennai-primary)", "kind": "existing"},
    {"company": "Flipkart", "url": "https://www.flipkartcareers.com/", "hub": "Hitec", "kind": "existing"},
    {"company": "Darwinbox", "url": "https://darwinbox.com/careers", "hub": "Hitec / Madhapur", "kind": "existing"},
    {"company": "Keka", "url": "https://www.keka.com/careers", "hub": "Hitec / Madhapur", "kind": "existing"},
    {"company": "Icertis", "url": "https://www.icertis.com/careers/", "hub": "Hitec", "kind": "existing"},
    {"company": "o9 Solutions", "url": "https://o9solutions.com/careers/", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Sprinklr", "url": "https://www.sprinklr.com/careers/", "hub": "Hitec", "kind": "custom"},
    {"company": "Prodapt", "url": "https://www.prodapt.com/careers/", "hub": "Hitec", "kind": "custom"},
    {"company": "SenecaGlobal", "url": "https://www.senecaglobal.com/careers/", "hub": "Hitec / Madhapur", "kind": "custom"},
    {"company": "Infor India", "url": "https://careers.infor.com/", "hub": "Hitec", "kind": "listed"},
    {"company": "Arcesium", "url": "https://www.arcesium.com/careers", "hub": "Financial District / Gachibowli", "kind": "custom"},
    {"company": "Blue Yonder", "url": "https://blueyonder.com/careers", "hub": "Hitec / Gachibowli", "kind": "existing"},
    {"company": "Cubic", "url": "https://www.cubic.com/careers", "hub": "Hitec", "kind": "custom"},
    # --- Preferred near-home campuses: RMZ Nexity / Futura / Knowledge City / Raheja ---
    {"company": "Electronic Arts", "url": "https://jobs.ea.com/", "hub": "RMZ Nexity / Knowledge City", "kind": "custom"},
    {"company": "CGI", "url": "https://www.cgi.com/en/careers", "hub": "RMZ Nexity / RMZ Futura", "kind": "custom"},
    {"company": "McDonalds", "url": "https://careers.mcdonalds.com/", "hub": "RMZ Nexity", "kind": "custom"},
    {"company": "ArcelorMittal", "url": "https://jobs.arcelormittal.com/", "hub": "RMZ Nexity", "kind": "custom"},
    {"company": "Alter Domus", "url": "https://alterdomus.com/careers/", "hub": "RMZ Nexity", "kind": "custom"},
    {"company": "Providence", "url": "https://www.providence.org/careers", "hub": "RMZ Nexity", "kind": "custom"},
    {"company": "People Tech", "url": "https://www.peopletech.com/careers/", "hub": "RMZ Futura", "kind": "custom"},
    {"company": "Verizon", "url": "https://www.verizon.com/about/careers", "hub": "Raheja Mindspace", "kind": "custom"},
    {"company": "Parexel", "url": "https://jobs.parexel.com/", "hub": "Raheja Mindspace", "kind": "custom"},
    {"company": "Syneos Health", "url": "https://www.syneoshealth.com/careers", "hub": "Raheja Mindspace", "kind": "custom"},
    {"company": "Colruyt", "url": "https://www.colruytgroup.com/en/careers", "hub": "Raheja Mindspace", "kind": "custom"},
    {"company": "Hyundai Mobis", "url": "https://www.mobis.com/en/careers", "hub": "Raheja Mindspace", "kind": "custom"},
]

EIGHTFOLD_EXTRA = [
    "dtcc.com", "ice.com", "nasdaq.com", "lseg.com", "refinitiv.com",
    "aon.com", "wtwco.com", "equifax.com", "transunion.com", "fico.com",
    "ssctech.com", "fisglobal.com", "factset.com", "moodys.com",
    "invesco.com", "franklintempleton.com", "vanguard.com",
    "ubs.com", "dbs.com", "macquarie.com", "nomura.com",
    "societegenerale.com", "bnpparibas.com", "anz.com",
    "apple.com", "ti.com", "nxp.com", "westerndigital.com",
    "synopsys.com", "cadence.com", "ansys.com", "appliedmaterials.com",
    "lamresearch.com", "kla.com", "cotiviti.com", "highradius.com",
    "valuelabs.com", "genpact.com", "tcs.com", "kpmg.com",
    "arcesium.com", "sprinklr.com",
    "ea.com", "cgi.com", "mcdonalds.com", "arcelormittal.com",
    "alterdomus.com", "providence.org", "verizon.com", "parexel.com",
]

JOB_HREF = re.compile(
    r'href="((?:https://[^"]+)?/job/[^"]+)"',
    re.I,
)
FACET_HYD = re.compile(
    r'FacetTerm=(\d+)[^"\']{0,120}Hyderabad|Hyderabad[^"\']{0,120}FacetTerm=(\d+)',
    re.I,
)
REQ_ID = re.compile(r"(20\d{2}-\d{5,}|JR-?\d+|[A-Z]{2,}\d{4,})", re.I)


def get_text(url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 10) -> str:
    h = {"User-Agent": UA, "Accept": "text/html,application/json,*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def get_json(url: str, data: bytes | None = None, headers: dict | None = None):
    raw = get_text(url, data=data, headers=headers)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def abs_url(host: str, href: str) -> str:
    href = htmlmod.unescape(href).split("?")[0].rstrip("/")
    if href.startswith("http"):
        return href
    return f"https://{host}{href}"


def loc_from_path(href: str) -> str:
    m = re.search(r"/job/([^/]+)/", href, re.I)
    if not m:
        return ""
    return m.group(1).replace("-", " ").title()


def add_job(jobs, company, title, location, url, ats, job_id=""):
    title = htmlmod.unescape(re.sub(r"\s+", " ", title or "")).strip()
    location = htmlmod.unescape(re.sub(r"\s+", " ", location or "")).strip()
    if not title or not url:
        return
    if not location:
        location = loc_from_path(url) or "Hyderabad, Telangana"
    if re.search(r"hyderabad|telangana|india", location, re.I) is None and "/hyderabad/" in url.lower():
        location = "Hyderabad, Telangana, India"
    d.add(jobs, company, title, location, url, ats, job_id)


def smashfly_parse(html: str, host: str, company: str, jobs: list, force_hyd: bool = False):
    for m in JOB_HREF.finditer(html):
        href = m.group(1)
        url = abs_url(host, href)
        slug = urllib.parse.unquote(url.rstrip("/").split("/")[-3] if "/job/" in url else "")
        title = slug.replace("-", " ").title() if slug else ""
        # Prefer nearby heading text
        start = max(0, m.start() - 200)
        chunk = html[m.start(): m.start() + 400]
        tm = re.search(r">([^<]{8,120})</a>", chunk)
        if tm:
            title = htmlmod.unescape(tm.group(1)).strip()
        loc = loc_from_path(href)
        if force_hyd or "hyderabad" in href.lower() or "hyderabad" in loc.lower():
            loc = loc or "Hyderabad, Telangana, India"
            if "hyderabad" not in loc.lower():
                loc = f"{loc} Hyderabad, Telangana, India"
        elif not re.search(r"hyderabad|telangana|india|remote", loc, re.I):
            continue
        jid = ""
        rm = REQ_ID.search(chunk) or REQ_ID.search(url)
        if rm:
            jid = rm.group(1)
        if not jid:
            jid = url.rstrip("/").split("/")[-1]
        add_job(jobs, company, title, loc, url, "Phenom", jid)


def smashfly_search(host: str, company: str, jobs: list):
    print(f"  Phenom {company} {host}", flush=True)
    before = len(jobs)
    for path in ("/India", "/search-jobs/Hyderabad"):
        html = get_text(f"https://{host}{path}", timeout=12)
        if html:
            smashfly_parse(html, host, company, jobs, force_hyd=True)
        time.sleep(0.08)

    html = get_text(f"https://{host}/search-jobs", timeout=12)
    terms = set()
    if html:
        smashfly_parse(html, host, company, jobs, force_hyd=False)
        for m in FACET_HYD.finditer(html):
            terms.add(m.group(1) or m.group(2))

    qs_base = (
        "ActiveFacetID=0&RecordsPerPage=50&Distance=50&RadiusUnitType=0"
        "&Keywords=&Location=&ShowRadius=False&CustomFacetName="
        "&SearchResultsModuleName=Search+Results&SearchFiltersModuleName=Search+Filters"
        "&SortCriteria=0&SortDirection=0&SearchType=5"
    )
    for term in list(terms)[:2]:
        url = f"https://{host}/search-jobs/results?{qs_base}&FacetTerm={term}&FacetType=2&CurrentPage=1"
        data = get_json(
            url,
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        blob = str((data or {}).get("results") or "") if isinstance(data, dict) else ""
        if blob:
            smashfly_parse(blob, host, company, jobs, force_hyd=True)
        time.sleep(0.08)
    print(f"    +{len(jobs) - before} rows", flush=True)


def workday_search(api: str, site: str, company: str, jobs: list):
    print(f"  Workday {company}", flush=True)
    before = len(jobs)
    ok = False
    for q in ("Hyderabad architect", "Hyderabad senior software", "Hyderabad engineering manager"):
        payload = json.dumps({"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": q}).encode()
        data = get_json(api, data=payload, headers={"Content-Type": "application/json", "Accept": "application/json"})
        time.sleep(0.08)
        if not isinstance(data, dict):
            if not ok:
                print("    skip (no API)", flush=True)
                return
            continue
        ok = True
        for item in data.get("jobPostings") or []:
            path = item.get("externalPath") or ""
            if not path:
                continue
            add_job(
                jobs, company, item.get("title") or "", item.get("locationsText") or "",
                site.rstrip("/") + path, "Workday", path.rstrip("/").split("/")[-1],
            )
    print(f"    +{len(jobs) - before} rows", flush=True)


def apple_search(jobs: list):
    print("  Apple jobs.apple.com", flush=True)
    before = len(jobs)
    url = "https://jobs.apple.com/api/v1/search"
    for q in ("architect Hyderabad", "principal engineer Hyderabad", "staff engineer Hyderabad",
              "technical lead Hyderabad", "engineering manager Hyderabad", "senior software Hyderabad"):
        payload = json.dumps({
            "query": q,
            "filters": {"locations": [{"id": "location-india"}]},
            "page": 1,
            "locale": "en-us",
        }).encode()
        data = get_json(url, data=payload, headers={"Content-Type": "application/json", "Accept": "application/json"})
        rows = []
        if isinstance(data, dict):
            res = data.get("res") or data.get("searchResults") or data
            if isinstance(res, dict):
                rows = res.get("searchResults") or res.get("jobs") or []
            elif isinstance(res, list):
                rows = res
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            title = item.get("postingTitle") or item.get("title") or ""
            locs = item.get("locations") or []
            loc = " ".join(
                (x.get("name") if isinstance(x, dict) else str(x)) for x in locs
            ) or str(item.get("location") or "")
            jid = item.get("positionId") or item.get("id") or ""
            link = item.get("postingUrl") or (f"https://jobs.apple.com/en-us/details/{jid}" if jid else "")
            add_job(jobs, "Apple", title, loc, link, "Apple", jid)
        time.sleep(0.2)
    print(f"    +{len(jobs) - before} rows", flush=True)


def eightfold_search(jobs: list):
    print("  Extra Eightfold Hyd GCCs", flush=True)
    before = len(jobs)
    for domain in EIGHTFOLD_EXTRA:
        qs = (
            "https://app.eightfold.ai/api/apply/v2/jobs?"
            f"domain={domain}&location=Hyderabad&start=0&num=40"
        )
        data = get_json(qs)
        time.sleep(0.08)
        if not isinstance(data, dict):
            continue
        for item in data.get("positions") or data.get("data") or []:
            loc = item.get("location") or ""
            if isinstance(item.get("locations"), list):
                loc = " ".join(str(x) for x in item["locations"]) + " " + str(loc)
            jid = item.get("id") or item.get("ats_job_id") or ""
            url = item.get("canonicalPositionUrl") or item.get("apply_url") or item.get("url") or ""
            add_job(jobs, domain.split(".")[0], item.get("name") or item.get("title") or "", loc, url, "Eightfold", jid)
    print(f"    +{len(jobs) - before} rows", flush=True)


def write_portal_list(live: dict[str, int]):
    rows = []
    seen = set()
    for p in PORTALS:
        key = (p["company"].lower(), p["url"])
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "company": p["company"],
            "url": p["url"],
            "hub": p.get("hub") or "",
            "kind": p.get("kind") or "",
            "note": p.get("note") or "",
            "matched_jobs": live.get(p["company"], live.get(p.get("host", ""), 0)),
        })
    (ROOT / "data" / "hyd_career_portals.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )
    lines = [
        "# Hyderabad company career portals",
        "",
        "Official career sites for GCCs and product companies in **Madhapur / HITEC City, Gachibowli, and Financial District** (plus Nanakramguda, Raidurg, Kondapur).",
        "These are now in the discovery catalog. `existing` = already searched via Workday/GH/Lever; others were added this run.",
        "",
        f"**{len(rows)} portals**",
        "",
        "| Company | Hub | Career site | Status |",
        "|---------|-----|-------------|--------|",
    ]
    for r in rows:
        status = r["kind"]
        if r.get("note"):
            status = f"{status} ({r['note']})"
        lines.append(f"| {r['company']} | {r['hub']} | {r['url']} | {status} |")
    (ROOT / "data" / "hyd_career_portals.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_pending(queue: list[dict]):
    lines = [
        "# Pending apply queue",
        "",
        f"**{len(queue)} jobs** left (best matches, 3 per company).",
        "",
        "| # | Score | Company | Title | Location | Link |",
        "|---|------:|---------|-------|----------|------|",
    ]
    for i, j in enumerate(queue, 1):
        lines.append(
            f"| {i} | {j.get('match_score') or 0} | {j.get('company')} | "
            f"{(j.get('title') or '')[:70]} | {(j.get('location') or '')[:40]} | {j.get('url') or ''} |"
        )
    (ROOT / "data" / "pending_queue.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    jobs = []
    seen_wd = {(a, c) for a, _, c in discover_portals.SITES}

    print("Hyderabad GCC career portals...", flush=True)
    smashfly_done = set()
    apple_done = False
    for p in PORTALS:
        kind = p.get("kind")
        if kind == "smashfly" and p.get("host"):
            host = p["host"]
            if host in smashfly_done:
                continue
            smashfly_done.add(host)
            smashfly_search(host, p["company"].replace(" India", ""), jobs)
        elif kind == "workday" and p.get("api") and p.get("site"):
            key = (p["api"], p["company"])
            if key in seen_wd:
                continue
            seen_wd.add(key)
            workday_search(p["api"], p["site"], p["company"], jobs)
        elif kind == "apple" and not apple_done:
            apple_done = True
            apple_search(jobs)

    eightfold_search(jobs)
    print(f"New GCC raw rows: {len(jobs)}", flush=True)

    import discover_preferred_campuses
    discover_preferred_campuses.collect(jobs)

    live = {}
    for j in jobs:
        live[j.get("company") or ""] = live.get(j.get("company") or "", 0) + 1
    write_portal_list(live)

    catalog = json.loads((ROOT / "data" / "all_portals.json").read_text(encoding="utf-8"))
    catalog["hyd_career_portals"] = json.loads((ROOT / "data" / "hyd_career_portals.json").read_text(encoding="utf-8"))
    (ROOT / "data" / "all_portals.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    more.merge_and_write(jobs)
    batch = json.loads((ROOT / "data" / "discovery_batch.json").read_text(encoding="utf-8"))
    write_pending(batch)
    schwab = [j for j in jobs if "schwab" in (j.get("company") or "").lower()]
    print(f"Schwab matched in-scope: {len(schwab)}", flush=True)
    for j in schwab[:20]:
        print(f"  {j.get('title')[:70]} | {j.get('location')[:40]} | {j.get('url')}", flush=True)


if __name__ == "__main__":
    main()
