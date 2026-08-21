"""Load Google login for rafi.success@gmail.com. Never print the password."""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EMAIL = "rafi.success@gmail.com"
ENV_PATHS = (ROOT / ".env", ROOT / "data" / ".secrets.env")


def load_env_value(key: str) -> str:
    if os.environ.get(key):
        return os.environ[key]
    for path in ENV_PATHS:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, val = line.split("=", 1)
            val = val.strip().strip("'").strip('"')
            if name.strip() == key and val:
                os.environ[key] = val
                return val
            if name.strip() == "GOOGLE_EMAIL" and val:
                os.environ.setdefault("GOOGLE_EMAIL", val)
    return ""


def load_google_password() -> str:
    return load_env_value("GOOGLE_PASSWORD")


def fill_google_password_challenge(page) -> str:
    """Type the Google password on accounts.google.com challenge/pwd. Never log it."""
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "accounts.google.com" not in url:
        return "skip"
    if "changepassword" in url or "speedbump" in url:
        return "skip"
    password = load_google_password()
    if not password:
        return "missing"
    filled = False
    for sel in ("input[name=Passwd]", "input[type=password]", "input[name=password]", "#password"):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.fill(password, timeout=4000)
                filled = True
                break
        except Exception:
            continue
    if not filled:
        return "none"
    print("  Filled Google password on the sign-in challenge.", flush=True)
    try:
        nxt = page.get_by_role("button", name=re.compile(r"^next$", re.I)).first
        if nxt.count() and nxt.is_visible():
            nxt.click(timeout=3000)
    except Exception:
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass
    try:
        page.wait_for_timeout(1200)
    except Exception:
        pass
    return "ok"


def fill_google_change_password(page) -> str:
    """Do not create or change a Google password. Owner continues leftover applies."""
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "accounts.google.com" not in url:
        return "skip"
    if "changepassword" not in url and "speedbump" not in url:
        return "skip"
    print("  Leaving Google change-password alone. Continuing other leftovers.", flush=True)
    return "skip"


def fill_google_password_challenges(page) -> int:
    """Fill every open Google password challenge (Foundit/Cutshort SSO popups)."""
    ctx = getattr(page, "context", None)
    pages = list(ctx.pages) if ctx is not None else [page]
    n = 0
    for p in pages:
        try:
            if p.is_closed():
                continue
            if fill_google_change_password(p) == "ok":
                n += 1
                continue
            if fill_google_password_challenge(p) == "ok":
                n += 1
        except Exception:
            continue
    return n


def load_portal_password() -> str:
    """Career-site Create Account / Sign In password. Never print it."""
    passwords = load_portal_passwords()
    return passwords[0] if passwords else ""


def load_portal_passwords() -> list[str]:
    """Primary plus fallbacks. Never print the values."""
    out: list[str] = []
    for key in ("APPLY_ACCOUNT_PASSWORD", "PORTAL_PASSWORD"):
        val = load_env_value(key)
        if val and val not in out:
            out.append(val)
    extra = load_env_value("APPLY_ACCOUNT_PASSWORD_FALLBACKS")
    if extra:
        for part in extra.split(","):
            item = part.strip().strip("'").strip('"')
            if item and item not in out:
                out.append(item)
    return out


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
