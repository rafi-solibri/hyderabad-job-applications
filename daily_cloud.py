"""Daily cloud pipeline: discover Hyd jobs, filter, tailor resumes, write report.

Does not submit applications. The Candidate job applications automation must
also run cloud_apply.py --headed (see APPLY.md).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import apply_now
import discover_hyd_gcc
import tailor_resume

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "DAILY_REPORT.md"


def _load_apply_rows() -> list[dict]:
    rows: list[dict] = []
    for name in ("cloud_results.json", "apply_now_results.json"):
        path = ROOT / "data" / "applications" / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, list):
            rows.extend(r for r in data if isinstance(r, dict))
    return rows


def main() -> None:
    print("Working existing ready-to-apply queue (no board search yet)...", flush=True)
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

    print("Existing queue processed. Discovering new Hyderabad / Remote-India jobs...", flush=True)
    discover_hyd_gcc.main()
    apply_now.BATCH = apply_now.load_all_discovered()
    queue = apply_now.queue()
    for job in queue[:20]:
        if any(t.get("job_id") == job.get("job_id") for t in tailored):
            continue
        try:
            path = tailor_resume.for_job(job)
            tailored.append({**job, "resume_path": path, "headline": tailor_resume.CURRENT.get("headline")})
            print(f"  tailored {job.get('company')}: {job.get('title')}", flush=True)
        except Exception as exc:
            print(f"  tailor skip {job.get('company')}: {exc}", flush=True)

    applied_rows = _load_apply_rows()
    today = date.today().isoformat()
    today_applied = [
        r for r in applied_rows
        if str(r.get("status") or "") == "SUBMITTED" and today in str(r.get("ts") or r.get("note") or "")
    ]
    if not today_applied:
        today_applied = [r for r in applied_rows if str(r.get("status") or "") == "SUBMITTED"][-8:]
    blocked = [
        r for r in applied_rows
        if str(r.get("status") or "") in {"LOGIN_BLOCKED", "CAPTCHA", "VERIFY_ERROR", "INCOMPLETE", "ERROR"}
    ]
    lines = [
        f"# Daily job report — {today}",
        "",
        "Cloud run: existing queue first (company career portals, then tailored resumes), then discovery.",
        "Naukri / LinkedIn / Indeed / Cutshort / Foundit / Instahyre are last — other automations cover those boards.",
        "",
        f"**Ready to apply (best matches, no per-company cap): {len(queue)}**",
        f"**Resumes tailored this run: {len(tailored)}**",
        f"**Submitted this run / recent: {len(today_applied)}**",
        f"**Blocked or incomplete (login/CAPTCHA/form): {len(blocked)}**",
        "",
        "## Applied",
        "",
        "| Company | Title | Status | Link |",
        "|---------|-------|--------|------|",
    ]
    for r in today_applied[:20]:
        lines.append(
            f"| {r.get('company')} | {(r.get('title') or '')[:60]} | {r.get('status')} | "
            f"{r.get('final_url') or r.get('url') or ''} |"
        )
    if not today_applied:
        lines.append("| — | none confirmed this run | — | — |")
    lines += [
        "",
        "## Blocked / skipped (sample)",
        "",
        "| Company | Title | Status | Note |",
        "|---------|-------|--------|------|",
    ]
    for r in blocked[-15:]:
        lines.append(
            f"| {r.get('company')} | {(r.get('title') or '')[:50]} | {r.get('status')} | "
            f"{(r.get('note') or '')[:40]} |"
        )
    if not blocked:
        lines.append("| — | — | — | — |")
    lines += [
        "",
        "## Ready queue",
        "",
        "| # | Portal | Score | Company | Title | Tailored headline | Link |",
        "|---|--------|------:|---------|-------|-------------------|------|",
    ]
    for i, j in enumerate(queue[:40], 1):
        extra = next((t for t in tailored if t.get("job_id") == j.get("job_id")), {})
        rank = j.get("portal_rank")
        if rank is None:
            rank = apply_now.portal_rank(j)
        portal = "career" if int(rank) >= 100 else ("other" if int(rank) >= 50 else "board")
        lines.append(
            f"| {i} | {portal} | {j.get('match_score') or 0} | {j.get('company')} | "
            f"{(j.get('title') or '')[:60]} | {(extra.get('headline') or '')[:50]} | {j.get('url') or ''} |"
        )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT} — {len(queue)} queued, {len(tailored)} tailored.", flush=True)


if __name__ == "__main__":
    main()
