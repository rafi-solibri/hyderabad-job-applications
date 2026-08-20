"""Daily cloud pipeline: discover Hyd jobs, filter, tailor resumes, write report.

Does not open Firefox or submit applications (no browser session in cloud).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import apply_now
import discover_hyd_gcc
import tailor_resume

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "DAILY_REPORT.md"


def main() -> None:
    print("Daily Hyderabad discovery...", flush=True)
    discover_hyd_gcc.main()
    apply_now.BATCH = apply_now.load_all_discovered()
    queue = apply_now.queue()
    tailored = []
    for job in queue[:20]:
        try:
            path = tailor_resume.for_job(job)
            tailored.append({**job, "resume_path": path, "headline": tailor_resume.CURRENT.get("headline")})
            print(f"  tailored {job.get('company')}: {job.get('title')}", flush=True)
        except Exception as exc:
            print(f"  tailor skip {job.get('company')}: {exc}", flush=True)
    lines = [
        f"# Daily job report — {date.today().isoformat()}",
        "",
        "Cloud run: discovery + resume tailoring only. Apply on the Windows Firefox profile (Simplify Copilot).",
        "",
        f"**Ready to apply (best matches, 3 per company): {len(queue)}**",
        f"**Resumes tailored this run: {len(tailored)}**",
        "",
        "| # | Score | Company | Title | Tailored headline | Link |",
        "|---|------:|---------|-------|-------------------|------|",
    ]
    for i, j in enumerate(queue[:40], 1):
        extra = next((t for t in tailored if t.get("job_id") == j.get("job_id")), {})
        lines.append(
            f"| {i} | {j.get('match_score') or 0} | {j.get('company')} | "
            f"{(j.get('title') or '')[:60]} | {(extra.get('headline') or '')[:50]} | {j.get('url') or ''} |"
        )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT} — {len(queue)} queued, {len(tailored)} tailored.", flush=True)


if __name__ == "__main__":
    main()
