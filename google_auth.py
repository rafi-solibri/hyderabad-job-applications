"""Load Google login for rafi.success@gmail.com. Never print the password."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EMAIL = "rafi.success@gmail.com"
ENV_PATHS = (ROOT / ".env", ROOT / "data" / ".secrets.env")


def load_google_password() -> str:
    if os.environ.get("GOOGLE_PASSWORD"):
        return os.environ["GOOGLE_PASSWORD"]
    for path in ENV_PATHS:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = val.strip().strip("'").strip('"')
            if key.strip() == "GOOGLE_PASSWORD" and val:
                os.environ["GOOGLE_PASSWORD"] = val
                return val
            if key.strip() == "GOOGLE_EMAIL" and val:
                os.environ.setdefault("GOOGLE_EMAIL", val)
    return ""


def sign_in_chrome(page) -> str:
    """Fill Google Chrome sync sign-in. Returns ok|2fa|blocked|missing."""
    password = load_google_password()
    if not password:
        print("  Google password not in .env / GOOGLE_PASSWORD; cannot auto sign-in.", flush=True)
        return "missing"
    email = os.environ.get("GOOGLE_EMAIL") or EMAIL
    page.goto(
        "https://accounts.google.com/signin/chrome/sync?ssp=1&continue=https://mail.google.com/",
        wait_until="domcontentloaded",
        timeout=45000,
    )
    page.wait_for_timeout(1200)
    blob = ""
    try:
        blob = (page.inner_text("body") or "")[:1200]
    except Exception:
        pass
    if "rafi.success@gmail.com" in blob and "2-step" in blob.lower():
        print("  Google 2FA already waiting on the phone.", flush=True)
        return "2fa"
    if "inbox" in (page.title() or "").lower() or "mail.google.com/mail" in (page.url or ""):
        print("  Chrome already signed in as rafi.success@gmail.com.", flush=True)
        return "ok"
    for sel in ("#identifierId", "input[type=email]", "input[name=identifier]"):
        loc = page.locator(sel).first
        try:
            if loc.count() and loc.is_visible():
                loc.fill(email, timeout=5000)
                break
        except Exception:
            continue
    nxt = page.get_by_role("button", name="Next")
    try:
        if nxt.count() and nxt.first.is_visible():
            nxt.first.click(timeout=4000)
            page.wait_for_timeout(2000)
    except Exception:
        pass
    for sel in ("input[name=Passwd]", "input[type=password]", "input[name=password]"):
        loc = page.locator(sel).first
        try:
            if loc.count() and loc.is_visible():
                loc.fill(password, timeout=5000)
                break
        except Exception:
            continue
    nxt = page.get_by_role("button", name="Next")
    try:
        if nxt.count() and nxt.first.is_visible():
            nxt.first.click(timeout=4000)
            page.wait_for_timeout(3500)
    except Exception:
        pass
    try:
        blob = (page.inner_text("body") or "")[:1200]
    except Exception:
        blob = ""
    url = page.url or ""
    if "wrong password" in blob.lower() or "couldn’t sign you in" in blob.lower() or "not secure" in blob.lower():
        print("  Google sign-in blocked.", flush=True)
        return "blocked"
    if "2-step" in blob.lower() or "check your" in blob.lower() or "/challenge/" in url:
        print("  Google 2FA: approve on the phone, then applies continue.", flush=True)
        return "2fa"
    print("  Google sign-in submitted for rafi.success@gmail.com.", flush=True)
    return "ok"
