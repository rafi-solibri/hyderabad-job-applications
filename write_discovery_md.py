import json
from collections import Counter
from pathlib import Path

jobs = json.loads(Path("data/discovery_batch.json").read_text(encoding="utf-8"))
jobs = sorted(jobs, key=lambda j: (j["company"].lower(), j["title"]))
lines = [
    "# Discovery batch — Hyderabad target titles",
    "",
    "Run date: 2026-08-17",
    "",
    "## Counts",
    "",
    "| Metric | Count |",
    "|---|---|",
    f"| Matched unique (incl. already applied) | {len(jobs) + 6} |",
    f"| **Open jobs in this batch** | **{len(jobs)}** |",
    "| Already applied (excluded) | 6 |",
    "| Target range | 100-300 |",
    "",
    "Below 100 because Microsoft, Google, Infosys, Deloitte, Wells Fargo, JPMC, Salesforce, ServiceNow, Oracle, Cognizant, Wipro, and most Workday employers do not expose a public job-board API. Neighborhood names (Madhapur / Gachibowli / FD) almost never appear; portals list Hyderabad. Remote/hybrid Hyderabad included.",
    "",
    "Sources: official Greenhouse, Lever, Amazon.jobs, Micron/NVIDIA Workday.",
    "",
    "## By company",
    "",
]
for company, n in Counter(j["company"] for j in jobs).most_common():
    lines.append(f"- {company}: {n}")
lines += [
    "",
    "## Full open list",
    "",
    "| # | Company | Title | Location | Apply |",
    "|---|---|---|---|---|",
]
for i, job in enumerate(jobs, 1):
    url = job.get("url") or ""
    loc = (job.get("location") or "").replace("|", "/")[:50]
    title = (job.get("title") or "").replace("|", "/")
    lines.append(f"| {i} | {job['company']} | {title} | {loc} | {url} |")
Path("DISCOVERY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", len(jobs), "jobs")
