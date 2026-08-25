"""Email rafi.success@gmail.com when the daily career-portal apply finishes.

Same delivery as the other daily automations (MyRepo Notification Job):
Resend API first (RESEND_API_KEY), then Gmail SMTP from gitignored .env.
Never print the API key or password.
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

import google_auth

ROOT = Path(__file__).resolve().parent
TO = os.environ.get("EMAIL_TO") or "rafi.success@gmail.com"
FROM_NAME = "Career portals"
DEFAULT_RESEND_FROM = "Job Status <onboarding@resend.dev>"
SUBMITTED_LOG = ROOT / "data" / "applications" / "SUBMITTED.md"
RESULTS = ROOT / "data" / "applications" / "cloud_results.json"
REPORT = ROOT / "data" / "applications" / "DAILY_EMAIL.md"
AGENT_URL = os.environ.get(
    "CURSOR_AGENT_URL",
    "https://cursor.com/automations/979f38ce-9c62-11f1-ba66-0e7d0216e441",
)


def _load_env() -> None:
    google_auth.load_env_value("RESEND_API_KEY")
    google_auth.load_env_value("RESEND_FROM_EMAIL")
    google_auth.load_env_value("GOOGLE_PASSWORD")
    google_auth.load_env_value("GOOGLE_EMAIL")
    google_auth.load_env_value("EMAIL_TO")


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _submitted_today(day: str) -> list[str]:
    if not SUBMITTED_LOG.exists():
        return []
    lines = SUBMITTED_LOG.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    pending = ""
    for line in lines:
        if line.startswith("- **") and "SUBMITTED" in line:
            pending = line
        elif pending and line.strip().startswith("http"):
            if day in pending:
                out.append(f"{pending}\n  {line.strip()}")
            pending = ""
        elif line.startswith("- **"):
            pending = ""
    return out


def _status_counts(day: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not RESULTS.exists():
        return counts
    try:
        rows = json.loads(RESULTS.read_text(encoding="utf-8"))
    except Exception:
        return counts
    if not isinstance(rows, list):
        return counts
    for row in rows:
        if not isinstance(row, dict):
            continue
        ts = str(row.get("ts") or "")
        if day not in ts:
            continue
        status = str(row.get("status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    return counts


def build_report(day: str | None = None) -> tuple[str, str]:
    day = day or _today_utc()
    submitted = _submitted_today(day)
    counts = _status_counts(day)
    leftover_career = leftover_boards = None
    try:
        import apply_now
        import cloud_apply

        apply_now.BATCH = apply_now.load_all_discovered()
        queue = apply_now.queue()
        try_jobs, _ = cloud_apply.public_queue(queue, allow_aggregators=True)
        try_jobs = cloud_apply.leftover_career_jobs(try_jobs)
        leftover_career = sum(
            1
            for j in try_jobs
            if apply_now.is_company_career_portal(j)
            and not apply_now.is_aggregator_board(j)
        )
        leftover_boards = len(try_jobs) - leftover_career
    except Exception:
        pass

    count_txt = ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "no rows logged today"
    leftover_txt = "n/a"
    if leftover_career is not None:
        leftover_txt = f"{leftover_career} career / {leftover_boards} other-board"

    submitted_block = "\n".join(submitted) if submitted else "- none today"
    body = (
        f"Daily Hyderabad career-portal apply — {day}\n"
        f"\n"
        f"Submitted today: {len(submitted)}\n"
        f"Today's apply statuses: {count_txt}\n"
        f"Still leftover: {leftover_txt}\n"
        f"Expected CTC: 60 LPA | Current: 52 LPA | Notice: Immediate\n"
        f"Agent: {AGENT_URL}\n"
        f"\n"
        f"Submitted\n"
        f"{submitted_block}\n"
        f"\n"
        f"This is the 11:00 IST career-portal automation "
        f"(hyderabad-job-applications / cloud_apply.py).\n"
    )
    subject = f"Career portals — {day}"
    return subject, body


def _send_resend(subject: str, body: str) -> str:
    api_key = os.environ.get("RESEND_API_KEY") or google_auth.load_env_value("RESEND_API_KEY")
    if not api_key:
        return ""
    from_addr = os.environ.get("RESEND_FROM_EMAIL") or DEFAULT_RESEND_FROM
    payload = json.dumps({
        "from": from_addr,
        "to": [TO],
        "subject": subject,
        "text": body,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        return str(data.get("id") or "resend-ok")
    except urllib.error.HTTPError as exc:
        print(f"  Resend HTTP {exc.code}.", flush=True)
        return ""
    except Exception as exc:
        print(f"  Resend failed ({type(exc).__name__}).", flush=True)
        return ""


def _send_gmail(subject: str, body: str) -> str:
    password = google_auth.load_google_password()
    email = os.environ.get("GOOGLE_EMAIL") or google_auth.EMAIL
    if not password or not email:
        return ""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{email}>"
    msg["To"] = TO
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.starttls(context=ctx)
            smtp.login(email, password)
            smtp.sendmail(email, [TO], msg.as_string())
        return "gmail-smtp"
    except Exception as exc:
        print(f"  Gmail SMTP failed ({type(exc).__name__}).", flush=True)
        return ""


def send(day: str | None = None) -> str:
    """Write the daily report and email it. Returns the send id or ''."""
    _load_env()
    subject, body = build_report(day)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(body, encoding="utf-8")
    print(f"  Daily email report written to {REPORT}", flush=True)
    sent = _send_resend(subject, body)
    if sent:
        print(f"  Emailed {TO} via Resend ({sent}).", flush=True)
        return sent
    sent = _send_gmail(subject, body)
    if sent:
        print(f"  Emailed {TO} via Gmail SMTP.", flush=True)
        return sent
    print(
        f"  Could not email {TO}. Set RESEND_API_KEY (same as other daily automations) "
        "in gitignored .env or the environment.",
        flush=True,
    )
    return ""


def main() -> None:
    send()


if __name__ == "__main__":
    main()
