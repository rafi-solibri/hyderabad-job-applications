"""Launch Mozilla Firefox with the user's profile and trigger Simplify autofill."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APPLY_PROFILE = ROOT / "data" / "firefox_apply_profile"
USER_PROFILE = Path.home() / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles" / "1f3myy1c.default-release"
STORE_FIREFOX = Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "firefox.exe"
SIMPLIFY_AMO = "https://addons.mozilla.org/en-US/firefox/addon/simplify-jobs/"


def _copy_user_profile() -> None:
    if APPLY_PROFILE.exists() and any(APPLY_PROFILE.iterdir()):
        return
    APPLY_PROFILE.mkdir(parents=True, exist_ok=True)
    if not USER_PROFILE.exists():
        return
    ignore = shutil.ignore_patterns(
        "cache2", "startupCache", "shader-cache", "thumbnails", "offlineCache",
        "parent.lock", "lock", "sessionstore-backups", "*.sqlite-wal", "*.sqlite-shm",
    )
    try:
        shutil.copytree(USER_PROFILE, APPLY_PROFILE, dirs_exist_ok=True, ignore=ignore)
        print("  Copied your Firefox profile (rafi.success@gmail.com) for this session.", flush=True)
    except Exception as e:
        print(f"  Could not copy full Firefox profile ({e}). Using a dedicated apply profile.", flush=True)


def launch_firefox(playwright):
    """Open headed Firefox. Prefer the real Mozilla install, then Playwright Firefox."""
    _copy_user_profile()
    kwargs = {
        "headless": False,
        "viewport": None,
        "ignore_https_errors": True,
    }
    if STORE_FIREFOX.exists():
        try:
            return playwright.firefox.launch_persistent_context(
                str(APPLY_PROFILE),
                executable_path=str(STORE_FIREFOX),
                **kwargs,
            )
        except Exception as e:
            print(f"  Store Firefox launch failed ({e}). Using Playwright Firefox.", flush=True)
    return playwright.firefox.launch_persistent_context(str(APPLY_PROFILE), **kwargs)


def trigger_simplify(page) -> bool:
    """Wait for Simplify to scan, then click its Autofill control if it appears."""
    page.wait_for_timeout(2800)
    clicked = False
    for sel in (
        "button:has-text('Autofill')",
        "button:has-text('Fill with Simplify')",
        "button:has-text('Simplify Autofill')",
        "button:has-text('Apply with Simplify')",
        "[class*='simplify' i] button",
        "[id*='simplify' i]",
        "[data-testid*='simplify' i]",
        "text=Autofill with Simplify",
    ):
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=1500)
                clicked = True
                page.wait_for_timeout(1800)
                break
        except Exception:
            continue
    if clicked:
        print("  Clicked Simplify autofill.", flush=True)
    else:
        print("  Waiting for Simplify to fill fields. Click the Simplify icon if it does not start.", flush=True)
        page.wait_for_timeout(4000)
    return clicked


def ensure_simplify(page) -> None:
    """Open the Simplify add-on page if the extension is not filling yet."""
    try:
        has_ext = page.evaluate(
            """() => !!(document.querySelector('[class*="simplify" i], [id*="simplify" i], [data-simplify]'))"""
        )
    except Exception:
        has_ext = False
    if has_ext:
        return
    print("  Opening Simplify add-on page. Click Add to Firefox, then return here.", flush=True)
    try:
        page.goto(SIMPLIFY_AMO, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(8000)
    except Exception:
        pass
