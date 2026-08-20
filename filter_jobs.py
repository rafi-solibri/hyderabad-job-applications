import json
import re
from pathlib import Path

jobs = json.loads(Path("data/discovered_jobs.json").read_text(encoding="utf-8"))
hyd = re.compile(
    r"hyderabad|gachibowli|madhapur|financial district|hitec city|hitech city|nanakramguda|kondapur|raidurg",
    re.I,
)
india = re.compile(r"\bindia\b|\bhyd\b|\btelangana\b", re.I)
real = [j for j in jobs if hyd.search(j.get("location") or "")]
india_jobs = [j for j in jobs if india.search(j.get("location") or "") and not hyd.search(j.get("location") or "")]
print("HYD location field:", len(real))
print("India but not HYD:", len(india_jobs))
print("--- HYD ---")
for j in real:
    print(f"{j['ats']}\t{j['company']}\t{j['title']}\t{j['location']}\t{j['url']}")
print("--- INDIA ---")
for j in india_jobs:
    print(f"{j['company']}\t{j['title']}\t{j['location']}\t{j['url']}")
Path("data/hyd_jobs.json").write_text(json.dumps(real, indent=2), encoding="utf-8")
Path("data/india_jobs.json").write_text(json.dumps(india_jobs, indent=2), encoding="utf-8")
