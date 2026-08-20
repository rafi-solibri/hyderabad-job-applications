"""Visible-browser apply for TTEC Digital only."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
C = json.loads((ROOT / "data" / "candidate.json").read_text(encoding="utf-8"))
RESUME = str((ROOT / C["resumePath"]).resolve())
SHOTS = ROOT / "data" / "applications" / "screenshots"
RESULTS = ROOT / "data" / "applications" / "ttec_result.json"
LOG = ROOT / "data" / "applications" / "log.jsonl"
URL = "https://jobs.lever.co/ttecdigital/0f413199-2e41-4325-92f3-902a577d039c/apply"
WAIT_SECONDS = 240


def log(event):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def quiet_click(locator, timeout=1500):
    try:
        locator.click(timeout=timeout)
        return True
    except Exception:
        return False


def is_success(page) -> bool:
    try:
        url = page.url.lower()
        if any(x in url for x in ("/thanks", "confirmation", "submitted")):
            return True
        text = page.inner_text("body")
        if "error verifying" in text.lower():
            return False
        return bool(re.search(
            r"thanks for (your )?appl|application (was |has been )?(submitted|received)|thank you for applying",
            text, re.I,
        ))
    except Exception:
        return False


def fill(page):
    for sel in ("button:has-text('dismiss')", "button:has-text('Accept')", "#onetrust-accept-btn-handler"):
        quiet_click(page.locator(sel).first, 600)
    for name, value in (
        ("name", C["fullName"]),
        ("email", C["email"]),
        ("phone", C["phone"]),
        ("org", C["currentEmployer"]),
        ("urls[LinkedIn]", C["linkedIn"]),
    ):
        try:
            page.locator(f"input[name='{name}']").fill(value, timeout=2000)
        except Exception:
            pass
    try:
        loc = page.locator("#location-input")
        if loc.count():
            loc.fill("Hyderabad, India", timeout=2000)
            page.wait_for_timeout(900)
            quiet_click(page.locator("li, div").filter(has_text=re.compile(r"Hyderabad", re.I)).first, 1500)
            page.keyboard.press("Enter")
    except Exception:
        pass
    try:
        page.locator("input[type=file]").first.set_input_files(RESUME, timeout=3000)
    except Exception:
        pass
    for q, ans in (
        (r"at least 18", "Yes"),
        (r"authorized to work|right to work|work eligibility|proof of identity|eligibility to work", "Yes"),
        (r"education|certification|bachelor", "Yes"),
        (r"visa|sponsorship", "No"),
    ):
        try:
            heading = page.get_by_text(re.compile(q, re.I)).first
            quiet_click(
                heading.locator("xpath=ancestor::*[self::li or self::div][1]").get_by_text(ans, exact=True).first,
                1200,
            )
        except Exception:
            pass
    for q, val in (
        (r"document type|right to work document", "Indian Passport"),
        (r"expected.*salary|annual gross", "6500000 INR (65 LPA)"),
        (r"notice period", "Immediate"),
    ):
        try:
            box = page.get_by_text(re.compile(q, re.I)).first.locator(
                "xpath=following::input[1] | following::textarea[1]"
            ).first
            name = box.get_attribute("name") or ""
            if not name.startswith("urls["):
                box.fill(val, timeout=1500)
        except Exception:
            pass
    try:
        for sel in page.locator("select").all():
            try:
                html = sel.inner_html()
                if "India" in html:
                    sel.select_option(label="India", timeout=1500)
                elif "Male" in html and "Female" in html:
                    sel.select_option(label=re.compile(r"^Male$", re.I), timeout=1500)
            except Exception:
                pass
    except Exception:
        pass


def main():
    print("Opening TTEC Digital in a visible window.", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        page = browser.new_context(no_viewport=True).new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)
        page.bring_to_front()
        fill(page)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / "ttec-retry-filled.png"), full_page=True)
        print(
            "\nYOUR TURN: TTEC Digital — Principal Solution Architect - AWS\n"
            "  1. Confirm phone and location\n"
            "  2. Solve the CAPTCHA / verification\n"
            "  3. Click Submit application\n"
            f"  Waiting up to {WAIT_SECONDS} seconds...\n",
            flush=True,
        )
        deadline = time.time() + WAIT_SECONDS
        while time.time() < deadline:
            if is_success(page):
                break
            page.wait_for_timeout(2000)
        ok = is_success(page)
        page.screenshot(path=str(SHOTS / "ttec-retry-after.png"), full_page=True)
        row = {
            "company": "TTEC Digital",
            "title": "Principal Solution Architect - AWS",
            "ok": ok,
            "status": "SUBMITTED" if ok else "NOT_CONFIRMED",
            "url": page.url,
            "confirmation": page.inner_text("body")[:400],
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        RESULTS.write_text(json.dumps(row, indent=2), encoding="utf-8")
        log({"event": "ttec_retry", **row})
        print(f"Result: {row['status']} ok={ok}", flush=True)
        if ok:
            print(row["confirmation"][:200], flush=True)
        else:
            print("No confirmation page. You can still submit in the open window.", flush=True)
            page.wait_for_timeout(30000)
        browser.close()


if __name__ == "__main__":
    main()
