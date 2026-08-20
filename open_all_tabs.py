"""Open exactly one leftover job in Firefox. Never batch tabs. Never close Firefox."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import apply_now
import firefox_real

ROOT = Path(__file__).resolve().parent


def firefox_bin() -> str:
    return firefox_real.find_firefox() or r"C:\Users\MohammedAhmed\AppData\Local\Microsoft\WindowsApps\firefox.exe"


def next_job() -> dict | None:
    apply_now.BATCH = apply_now.load_all_discovered()
    jobs = apply_now.queue()
    return jobs[0] if jobs else None


def open_one(job: dict) -> None:
    url = job.get("apply_url") or job.get("url") or ""
    if job.get("ats") == "Lever" and url and not url.rstrip("/").endswith("/apply"):
        url = url.rstrip("/") + "/apply"
    ff = firefox_bin()
    print(f"Opening 1 tab only: {job.get('company')}: {job.get('title')}", flush=True)
    print(f"  {url}", flush=True)
    subprocess.Popen([ff, "-new-tab", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("  One tab requested. I will not open another until this one is done.", flush=True)


def main():
    job = next_job()
    if not job:
        print("No leftover target jobs to open.", flush=True)
        sys.exit(0)
    open_one(job)


if __name__ == "__main__":
    main()
