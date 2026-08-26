"""Email rafi.success@gmail.com when the daily career-portal apply finishes.

Same delivery as the other daily automations (MyRepo Notification Job):
Resend API first (RESEND_API_KEY), then Gmail app-password SMTP, then Gmail
compose in the already-open rafi.success Chrome. Never print secrets.
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
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
SENT_LOG = ROOT / "data" / "applications" / "DAILY_EMAIL_SENT.json"
AGENT_URL = os.environ.get(
    "CURSOR_AGENT_URL",
    "https://cursor.com/automations/979f38ce-9c62-11f1-ba66-0e7d0216e441",
)


def _load_env() -> None:
    google_auth.load_all_env()
    google_auth.load_env_value("RESEND_API_KEY")
    google_auth.load_env_value("RESEND_FROM_EMAIL")
    google_auth.load_env_value("GOOGLE_PASSWORD")
    google_auth.load_env_value("GOOGLE_EMAIL")
    google_auth.load_env_value("GMAIL_APP_PASSWORD")
    google_auth.load_env_value("GOOGLE_APP_PASSWORD")
    google_auth.load_env_value("EMAIL_TO")
    global TO
    TO = os.environ.get("EMAIL_TO") or "rafi.success@gmail.com"


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


def _blocked_today(day: str) -> list[str]:
    if not RESULTS.exists():
        return []
    try:
        rows = json.loads(RESULTS.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if day not in str(row.get("ts") or ""):
            continue
        status = str(row.get("status") or "")
        if status not in {"AUTH_FAILED", "STUCK", "WAITING_EXPIRED"}:
            continue
        url = str(row.get("final_url") or row.get("apply_url") or row.get("url") or "")
        host = url.lower()
        # Skip noisy aggregator already-applied / browse-only rows.
        if any(h in host for h in ("naukri.com", "linkedin.com", "foundit.in", "indeed.com")):
            continue
        label = f"{row.get('company') or '?'} — {row.get('title') or '?'} ({status})"
        if label in seen:
            continue
        seen.add(label)
        out.append(f"- {label}")
        if len(out) >= 12:
            break
    return out


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
    blocked = _blocked_today(day)
    blocked_block = "\n".join(blocked) if blocked else "- none listed (career portals)"
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
        f"Blocked / stuck career portals today\n"
        f"{blocked_block}\n"
        f"\n"
        f"This is the 11:00 IST career-portal automation "
        f"(hyderabad-job-applications / cloud_apply.py).\n"
    )
    subject = f"Career portals — {day}"
    return subject, body


def _resend_error_text(raw: str) -> str:
    text = (raw or "").replace("\n", " ").strip()
    if len(text) > 800:
        text = text[:800] + "…"
    return text or "(empty body)"


def _send_resend_urllib(api_key: str, from_addr: str, subject: str, body: str, idem: str) -> str:
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
            "Idempotency-Key": idem,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
        return str(data.get("id") or "resend-ok")
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        print(f"  Resend HTTP {exc.code}: {_resend_error_text(err_body)}", flush=True)
        return ""
    except Exception as exc:
        print(f"  Resend urllib failed ({type(exc).__name__}).", flush=True)
        return ""


def _send_resend_curl(api_key: str, from_addr: str, subject: str, body: str, idem: str) -> str:
    """curl fallback — urllib is sometimes blocked by SSL inspection / CF."""
    payload = {
        "from": from_addr,
        "to": [TO],
        "subject": subject,
        "text": body,
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(payload, fh)
        payload_path = fh.name
    with tempfile.NamedTemporaryFile("w", suffix=".cfg", delete=False, encoding="utf-8") as cfg:
        # Keep the bearer token out of `ps` argv.
        cfg.write(f'header = "Authorization: Bearer {api_key}"\n')
        cfg.write('header = "Content-Type: application/json"\n')
        cfg.write(f'header = "Idempotency-Key: {idem}"\n')
        cfg_path = cfg.name
    try:
        proc = subprocess.run(
            [
                "curl", "-sS", "-w", "\nHTTP:%{http_code}",
                "-X", "POST", "https://api.resend.com/emails",
                "-K", cfg_path,
                "--data-binary", f"@{payload_path}",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = (proc.stdout or "").strip()
        if "HTTP:" not in out:
            err = (proc.stderr or "").strip().replace(api_key, "***")
            print(f"  Resend curl failed ({err or 'no output'}).", flush=True)
            return ""
        body_txt, _, status_line = out.rpartition("\nHTTP:")
        try:
            status = int(status_line.strip())
        except ValueError:
            print("  Resend curl: bad status line.", flush=True)
            return ""
        if status >= 400:
            print(f"  Resend HTTP {status}: {_resend_error_text(body_txt)}", flush=True)
            return ""
        data = json.loads(body_txt or "{}")
        return str(data.get("id") or "resend-ok")
    except Exception as exc:
        print(f"  Resend curl failed ({type(exc).__name__}).", flush=True)
        return ""
    finally:
        for path in (payload_path, cfg_path):
            try:
                os.unlink(path)
            except OSError:
                pass


def _send_resend(subject: str, body: str, day: str) -> str:
    api_key = os.environ.get("RESEND_API_KEY") or google_auth.load_env_value("RESEND_API_KEY")
    if not api_key:
        print("  RESEND_API_KEY missing (set the same secret the Notification Job uses).", flush=True)
        return ""
    from_addr = os.environ.get("RESEND_FROM_EMAIL") or DEFAULT_RESEND_FROM
    idem = f"career-portals/{day}"
    sent = _send_resend_urllib(api_key, from_addr, subject, body, idem)
    if sent:
        return sent
    return _send_resend_curl(api_key, from_addr, subject, body, idem)


def _send_gmail(subject: str, body: str) -> str:
    password = (
        google_auth.load_env_value("GMAIL_APP_PASSWORD")
        or google_auth.load_env_value("GOOGLE_APP_PASSWORD")
        or ""
    )
    used_app_password = bool(password)
    if not password:
        password = google_auth.load_google_password()
    email = os.environ.get("GOOGLE_EMAIL") or google_auth.EMAIL
    if not password or not email:
        print("  Gmail SMTP skipped (no GMAIL_APP_PASSWORD / GOOGLE_PASSWORD).", flush=True)
        return ""
    if not used_app_password:
        print(
            "  Gmail SMTP: account password usually fails with 2FA; "
            "prefer GMAIL_APP_PASSWORD or RESEND_API_KEY.",
            flush=True,
        )
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


def _gmail_signed_in(page) -> bool:
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "accounts.google.com" in url:
        return False
    if "mail.google.com/mail" in url:
        return True
    try:
        title = (page.title() or "").lower()
    except Exception:
        title = ""
    return "inbox" in title


def _click_gmail_send(page) -> bool:
    for sel in (
        'div[role="button"][aria-label^="Send"]',
        'div[role="button"][data-tooltip^="Send"]',
        'div[aria-label="Send ‪(Ctrl-Enter)‬"]',
    ):
        loc = page.locator(sel).first
        try:
            if loc.count() and loc.is_visible():
                loc.click(timeout=5000)
                return True
        except Exception:
            continue
    try:
        page.keyboard.press("Control+Enter")
        return True
    except Exception:
        return False


def _send_gmail_compose(context, subject: str, body: str) -> str:
    """Send from the already-open rafi.success Chrome. Never a second CDP client."""
    if context is None:
        return ""
    page = None
    try:
        page = context.new_page()
        params = urllib.parse.urlencode(
            {"view": "cm", "fs": "1", "tf": "1", "to": TO, "su": subject[:200]},
            quote_via=urllib.parse.quote,
        )
        page.goto(
            f"https://mail.google.com/mail/u/0/?{params}",
            wait_until="domcontentloaded",
            timeout=45000,
        )
        page.wait_for_timeout(2500)
        if not _gmail_signed_in(page):
            print("  Gmail compose: Chrome is not signed in as rafi.success@gmail.com.", flush=True)
            return ""
        body_el = page.locator('div[aria-label="Message Body"], div[role="textbox"]').first
        try:
            if body_el.count():
                body_el.click(timeout=5000)
                body_el.fill(body[:15000], timeout=8000)
        except Exception:
            try:
                page.keyboard.type(body[:4000], delay=0)
            except Exception:
                pass
        if not _click_gmail_send(page):
            print("  Gmail compose: Send button not found.", flush=True)
            return ""
        page.wait_for_timeout(2500)
        blob = ""
        try:
            blob = (page.inner_text("body") or "").lower()
        except Exception:
            pass
        if "couldn't send" in blob or "couldn’t send" in blob:
            print("  Gmail compose: send failed on page.", flush=True)
            return ""
        print("  Gmail compose sent.", flush=True)
        return "gmail-compose"
    except Exception as exc:
        print(f"  Gmail compose failed ({type(exc).__name__}).", flush=True)
        return ""
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass


def _send_gmail_compose_standalone(subject: str, body: str) -> str:
    """Drive Gmail in headed Chrome. CLI-only — not used while cloud_apply holds CDP."""
    import cloud_apply
    from playwright.sync_api import sync_playwright

    os.environ.setdefault("DISPLAY", ":1")
    if not cloud_apply._cdp_up():
        try:
            cloud_apply.start_real_chrome()
        except Exception as exc:
            print(f"  Gmail compose: Chrome did not start ({type(exc).__name__}).", flush=True)
            return ""
    else:
        print("  Gmail compose: using the already-open rafi.success Chrome.", flush=True)
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cloud_apply.CDP, timeout=25000)
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        if _gmail_signed_in(page) or "mail.google.com/mail" in (page.url or ""):
            return _send_gmail_compose(context, subject, body)
        status = google_auth.sign_in_chrome(page)
        if status == "2fa":
            print(
                "  Gmail compose waiting on Google 2FA. "
                "Tap Yes on Nothing Phone / OnePlus, then the on-screen number.",
                flush=True,
            )
            for _ in range(45):
                page.wait_for_timeout(2000)
                google_auth.announce_2fa_number(page)
                if _gmail_signed_in(page) or "mail.google.com/mail" in (page.url or ""):
                    status = "ok"
                    break
        if status not in {"ok"} and not _gmail_signed_in(page):
            print(f"  Gmail compose: Google sign-in is {status}.", flush=True)
            return ""
        return _send_gmail_compose(context, subject, body)


def _record_sent(day: str, sent: str) -> None:
    SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    SENT_LOG.write_text(
        json.dumps(
            {
                "day": day,
                "sent": sent,
                "to": TO,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def send(day: str | None = None, *, context=None, allow_start_chrome: bool = False) -> str:
    """Write the daily report and email it. Returns the send id or ''."""
    _load_env()
    day = day or _today_utc()
    subject, body = build_report(day)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(body, encoding="utf-8")
    print(f"  Daily email report written to {REPORT}", flush=True)

    sent = _send_resend(subject, body, day)
    if sent:
        print(f"  Emailed {TO} via Resend ({sent}).", flush=True)
        _record_sent(day, sent)
        return sent
    sent = _send_gmail(subject, body)
    if sent:
        print(f"  Emailed {TO} via Gmail SMTP.", flush=True)
        _record_sent(day, sent)
        return sent
    if context is not None:
        sent = _send_gmail_compose(context, subject, body)
        if sent:
            print(f"  Emailed {TO} via Gmail compose.", flush=True)
            _record_sent(day, sent)
            return sent
    elif allow_start_chrome:
        sent = _send_gmail_compose_standalone(subject, body)
        if sent:
            print(f"  Emailed {TO} via Gmail compose.", flush=True)
            _record_sent(day, sent)
            return sent
    print(
        f"\n  ========================================\n"
        f"  DAILY EMAIL NOT SENT to {TO}\n"
        f"  Set RESEND_API_KEY on this environment (same key as Notification Job).\n"
        f"  ========================================\n",
        flush=True,
    )
    return ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default=None, help="UTC date YYYY-MM-DD (default today)")
    parser.add_argument(
        "--allow-start-chrome",
        action="store_true",
        help="If Resend/SMTP fail, start headed Chrome and send via Gmail compose",
    )
    args = parser.parse_args()
    sent = send(args.day, allow_start_chrome=args.allow_start_chrome)
    if not sent:
        sys.exit(1)


if __name__ == "__main__":
    main()
