"""Keep LinkedIn Easy Apply under LinkedIn's abuse limits.

The 30 Aug 2026 restriction blamed high-volume *profile data* access via a
third-party tool/extension. This module:

- honors the stated lift time (session-skip only — never persist-skip leftovers)
- caps Easy Apply volume per run and per calendar day
- spaces LinkedIn applies so the next run does not look like a scrape
- forbids Copilot and /in/ profile navigation on LinkedIn
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
GUARD_PATH = ROOT / "data" / "linkedin_guard.json"

# 30 Aug 2026 7:43 PM PDT = 31 Aug 2026 02:43 UTC
DEFAULT_RESTRICTED_UNTIL = datetime(2026, 8, 31, 2, 43, tzinfo=timezone.utc)
PER_RUN = 12
PER_DAY = 15
MIN_GAP_SEC = 90

LIFT_RE = re.compile(
    r"(?:restriction will be lifted|lifted on)\s+(?:on\s+)?"
    r"([A-Za-z]+ \d{1,2}, \d{4}),?\s*(\d{1,2}:\d{2}\s*[AP]M)\s*(PDT|PST|UTC|IST|GMT)?",
    re.I,
)

_STATE: dict | None = None
_RUN_COUNT = 0
_LAST_APPLY_MONO = 0.0


def is_linkedin_url(url: str) -> bool:
    return "linkedin.com" in (url or "").lower()


def is_linkedin_job(job: dict | None, url: str = "") -> bool:
    blob = " ".join(
        [
            url,
            str((job or {}).get("apply_url") or ""),
            str((job or {}).get("url") or ""),
            str((job or {}).get("ats") or ""),
        ]
    ).lower()
    return "linkedin.com" in blob or blob.strip() == "linkedin"


def is_profile_url(url: str) -> bool:
    u = (url or "").lower()
    return "linkedin.com/in/" in u or "linkedin.com/recruiter/" in u


def _empty_state() -> dict:
    return {
        "restricted_until": DEFAULT_RESTRICTED_UNTIL.isoformat(),
        "note": "LinkedIn temporarily restricted until 2026-08-30 7:43 PM PDT",
        "day": "",
        "day_count": 0,
        "last_apply_ts": "",
        "copilot_on_linkedin": False,
        "per_run": PER_RUN,
        "per_day": PER_DAY,
        "min_gap_sec": MIN_GAP_SEC,
    }


def load() -> dict:
    global _STATE
    if _STATE is not None:
        return _STATE
    data = _empty_state()
    if GUARD_PATH.exists():
        try:
            raw = json.loads(GUARD_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update(raw)
        except Exception:
            pass
    _STATE = data
    return _STATE


def save(state: dict | None = None) -> None:
    global _STATE
    data = state or load()
    _STATE = data
    GUARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    GUARD_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _parse_until(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def restricted_until() -> datetime:
    return _parse_until(str(load().get("restricted_until") or "")) or DEFAULT_RESTRICTED_UNTIL


def blocked_now() -> bool:
    return datetime.now(timezone.utc) < restricted_until()


def restriction_note() -> str:
    until = restricted_until()
    note = str(load().get("note") or "").strip()
    if note:
        return note
    return f"LinkedIn restricted until {until.isoformat()}"


def parse_lift_time(blob: str) -> datetime | None:
    m = LIFT_RE.search(blob or "")
    if not m:
        return None
    stamp = f"{m.group(1)} {m.group(2)}"
    zone = (m.group(3) or "PDT").upper()
    try:
        naive = datetime.strptime(stamp.replace("  ", " ").strip(), "%B %d, %Y %I:%M %p")
    except ValueError:
        try:
            naive = datetime.strptime(stamp.replace("  ", " ").strip(), "%b %d, %Y %I:%M %p")
        except ValueError:
            return None
    tz_map = {
        "PDT": ZoneInfo("America/Los_Angeles"),
        "PST": ZoneInfo("America/Los_Angeles"),
        "IST": ZoneInfo("Asia/Kolkata"),
        "UTC": timezone.utc,
        "GMT": timezone.utc,
    }
    local = naive.replace(tzinfo=tz_map.get(zone, ZoneInfo("America/Los_Angeles")))
    return local.astimezone(timezone.utc)


def mark_restricted(blob: str = "", note: str | None = None) -> datetime:
    until = parse_lift_time(blob) or restricted_until()
    now = datetime.now(timezone.utc)
    if until <= now:
        until = max(until, now)
    state = load()
    state["restricted_until"] = until.isoformat()
    state["note"] = note or (
        f"LinkedIn temporarily restricted until {until.isoformat()} — session-skip only"
    )
    save(state)
    print(f"  LinkedIn session-skip until {until.isoformat()} (do not persist-skip leftovers).", flush=True)
    return until


def _today_key() -> str:
    return datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()


def _roll_day(state: dict) -> dict:
    today = _today_key()
    if state.get("day") != today:
        state["day"] = today
        state["day_count"] = 0
    return state


def remaining_today() -> int:
    state = _roll_day(load())
    left = max(0, int(state.get("per_day") or PER_DAY) - int(state.get("day_count") or 0))
    save(state)
    return left


def remaining_this_run() -> int:
    per_run = int(load().get("per_run") or PER_RUN)
    return max(0, min(per_run - _RUN_COUNT, remaining_today()))


def should_skip_apply() -> tuple[bool, str]:
    if blocked_now():
        return True, restriction_note()
    if remaining_this_run() <= 0:
        return True, f"LinkedIn Easy Apply cap reached ({PER_RUN}/run, {PER_DAY}/day)"
    return False, ""


def wait_before_apply() -> None:
    global _LAST_APPLY_MONO
    gap = int(load().get("min_gap_sec") or MIN_GAP_SEC)
    if _LAST_APPLY_MONO <= 0:
        return
    elapsed = time.monotonic() - _LAST_APPLY_MONO
    remain = gap - elapsed
    if remain > 1:
        print(f"  LinkedIn pace: waiting {int(remain)}s before the next Easy Apply.", flush=True)
        time.sleep(remain)


def record_attempt() -> None:
    global _RUN_COUNT, _LAST_APPLY_MONO
    _RUN_COUNT += 1
    _LAST_APPLY_MONO = time.monotonic()
    state = _roll_day(load())
    state["day_count"] = int(state.get("day_count") or 0) + 1
    state["last_apply_ts"] = datetime.now(timezone.utc).isoformat()
    save(state)


def allow_copilot() -> bool:
    return bool(load().get("copilot_on_linkedin"))
