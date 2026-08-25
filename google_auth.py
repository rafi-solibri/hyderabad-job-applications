"""Load Google login for rafi.success@gmail.com. Never print the password."""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EMAIL = "rafi.success@gmail.com"
ENV_PATHS = (ROOT / ".env", ROOT / "data" / ".secrets.env")
# Live prompt only. Gitignored — never commit this file.
TWO_FA_PATH = ROOT / "data" / "applications" / "GOOGLE_2FA.md"
_LAST_ANNOUNCED_2FA = ""


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


def extract_2fa_prompt_number(text: str) -> str:
    """Return the Google prompt number the owner must tap on the phone."""
    blob = text or ""
    m = re.search(r"tap\s+(\d{1,3})\s+on your phone", blob, re.I)
    if m:
        return m.group(1)
    m = re.search(r"then tap\s+(\d{1,3})", blob, re.I)
    if m:
        return m.group(1)
    m = re.search(r"then tap\s+(\d{1,3})\s+on your phone", blob, re.I)
    if m:
        return m.group(1)
    for line in blob.splitlines():
        s = line.strip()
        if re.fullmatch(r"\d{1,3}", s):
            return s
    return ""


def is_google_2fa_url(url: str) -> bool:
    u = (url or "").lower()
    if "accounts.google.com" not in u:
        return False
    if "changepassword" in u or "speedbump" in u:
        return False
    return "/challenge/" in u or "signin/challenge" in u


def write_2fa_notice(number: str) -> None:
    """Write the tap number so every run can post it in agent chat immediately."""
    TWO_FA_PATH.parent.mkdir(parents=True, exist_ok=True)
    TWO_FA_PATH.write_text(
        f"# Google 2FA\n\n"
        f"**Google 2FA number: {number}**\n\n"
        f"1. Open the Google prompt on Nothing Phone (3) or OnePlus 7 Pro.\n"
        f"2. Tap **Yes**.\n"
        f"3. Tap **{number}**.\n",
        encoding="utf-8",
    )


def print_2fa_banner(number: str) -> None:
    print(
        f"\n  ========================================\n"
        f"  GOOGLE_2FA_NUMBER={number}\n"
        f"  Google 2FA number to tap on your phone: {number}\n"
        f"  Tap Yes on Nothing Phone / OnePlus, then tap {number}.\n"
        f"  POST IN AGENT CHAT NOW: Google 2FA number: {number}\n"
        f"  ========================================\n",
        flush=True,
    )


def announce_2fa_number(page, force: bool = False) -> str:
    """Print and persist the on-screen Google 2FA number for the owner.

    Re-prints when the number is new or Google changes it. Set force=True
    at the start of every headed run so the chat always gets the number.
    """
    global _LAST_ANNOUNCED_2FA
    blob = ""
    try:
        blob = page.inner_text("body") or ""
    except Exception:
        blob = ""
    number = extract_2fa_prompt_number(blob)
    if not number:
        print(
            "  Google 2FA is on screen but the prompt number was not readable. "
            "Open Desktop / Take control and read the number.",
            flush=True,
        )
        return ""
    if number == _LAST_ANNOUNCED_2FA and not force:
        return number
    _LAST_ANNOUNCED_2FA = number
    write_2fa_notice(number)
    print_2fa_banner(number)
    return number


def announce_2fa_on_pages(pages, force: bool = False) -> str:
    """Scan Chrome pages for a Google 2FA prompt and announce the tap number."""
    for page in pages or []:
        try:
            if page is None or page.is_closed():
                continue
            if not is_google_2fa_url(page.url or ""):
                continue
        except Exception:
            continue
        try:
            number = announce_2fa_number(page, force=force)
        except Exception:
            number = ""
        if number:
            return number
    return ""


def fill_google_identifier_challenge(page) -> str:
    """Type rafi.success email on accounts.google.com identifier. Never log it."""
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "accounts.google.com" not in url and "naukri.com" not in url:
        return "skip"
    if "changepassword" in url or "speedbump" in url:
        return "skip"
    if "/challenge/" in url and "pwd" not in url and "password" not in url:
        return "skip"
    email = os.environ.get("GOOGLE_EMAIL") or EMAIL
    filled = False
    targets = [page]
    try:
        targets.extend(list(page.frames))
    except Exception:
        pass
    for target in targets:
        for sel in (
            "#identifierId",
            "input[type=email]",
            "input[name=identifier]",
            "input[autocomplete='username']",
            "input[id='identifierId']",
        ):
            try:
                loc = target.locator(sel).first
                if not loc.count():
                    continue
                loc.fill(email, timeout=4000)
                filled = True
                break
            except Exception:
                continue
        if filled:
            break
    if not filled:
        return "none"
    print("  Filled Google email on the sign-in identifier.", flush=True)
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
    if "/challenge/" in url and "pwd" not in url and "password" not in url:
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


def _all_browser_pages(page) -> list:
    """Popup Google windows can live in another CDP context. Walk every page."""
    seen: list = []
    ids: set[int] = set()
    ctx = getattr(page, "context", None)
    browser = getattr(ctx, "browser", None) if ctx is not None else None
    contexts = []
    if browser is not None:
        try:
            contexts = list(browser.contexts)
        except Exception:
            contexts = []
    if ctx is not None and ctx not in contexts:
        contexts.append(ctx)
    if not contexts and page is not None:
        return [page]
    for c in contexts:
        try:
            for p in c.pages:
                pid = id(p)
                if pid in ids:
                    continue
                ids.add(pid)
                seen.append(p)
        except Exception:
            continue
    if page is not None and id(page) not in ids:
        seen.append(page)
    return seen


def fill_google_password_challenges(page) -> int:
    """Fill identifier then password on every Google window. Never create a password."""
    pages = _all_browser_pages(page)
    for p in pages:
        try:
            if p.is_closed():
                continue
            u = (p.url or "").lower()
        except Exception:
            continue
        if "accounts.google.com" in u and ("changepassword" in u or "speedbump" in u):
            print("  Leaving Google change-password alone. Never creating a password.", flush=True)
            return 0
    n = 0
    for p in pages:
        try:
            if p.is_closed():
                continue
            if fill_google_identifier_challenge(p) == "ok":
                n += 1
        except Exception:
            continue
    for p in pages:
        try:
            if p.is_closed():
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
        announce_2fa_number(page)
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
        announce_2fa_number(page)
        return "2fa"
    print("  Google sign-in submitted for rafi.success@gmail.com.", flush=True)
    return "ok"
