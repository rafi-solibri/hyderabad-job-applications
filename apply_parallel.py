"""Apply pending jobs in Firefox with at most 3 job tabs at once."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import apply_now
import firefox_real
import form_memory
from sel_page import SelPage

MAX_TABS = 3
ROOT = Path(__file__).resolve().parent
FF_STUB = Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "firefox.exe"


def firefox_bin() -> str:
    if FF_STUB.exists():
        return str(FF_STUB)
    return firefox_real.find_firefox() or str(FF_STUB)


def job_url(job: dict) -> str:
    url = job.get("apply_url") or apply_now.apply_url(job) or job.get("url") or ""
    if job.get("ats") == "Lever" and url and not url.rstrip("/").endswith("/apply"):
        url = url.rstrip("/") + "/apply"
    return url


def open_tab(url: str, first: bool) -> None:
    ff = firefox_bin()
    args = [ff]
    if first:
        args += ["-marionette", "-profile", str(firefox_real.USER_PROFILE), url]
    else:
        args += ["-new-tab", url]
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def mark_submitted(job: dict, page) -> dict:
    row = {
        **job,
        "ok": True,
        "status": "SUBMITTED",
        "final_url": getattr(page, "url", "") or "",
    }
    apply_now.save_results([row])
    apply_now.log({"event": "apply_now", **{k: v for k, v in row.items() if k != "confirmation"}})
    apply_now.SKIP_IDS.add(str(job.get("job_id") or ""))
    print(f"  NOTED SUBMITTED: {job.get('company')}: {job.get('title')}", flush=True)
    return row


def work_slot(page, job: dict) -> str:
    """Fill/Copilot this tab. Returns submitted|verify|open."""
    if apply_now.is_success(page) or firefox_real.copilot_says_submitted(page):
        return "submitted"
    if apply_now.is_verify_error(page):
        return "verify"
    body = ""
    try:
        body = page.inner_text("body")[:400].lower()
    except Exception:
        pass
    if "couldn't find" in body or "404" in (page.title() or "").lower():
        return "closed"
    if "already applied" in body or "you previously applied" in body:
        return "submitted"
    # Do not call click_apply_now/focus_apply_tab — those jump to another job's tab.
    firefox_real._click_label_everywhere(page, firefox_real.APPLY_NOW_LABELS)
    for _ in range(3):
        if firefox_real.click_start_gate(page):
            break
        page.wait_for_timeout(800)
    firefox_real.watch_copilot(page)
    firefox_real.trigger_simplify(page)
    page.wait_for_timeout(2500)
    if job.get("ats") == "Greenhouse":
        apply_now.fill_greenhouse(page, job)
    elif job.get("ats") == "Lever":
        apply_now.fill_lever(page)
    form_memory.fill_visible(page)
    form_memory.remember(page, job)
    step = firefox_real.follow_copilot(page)
    if step == "submitted" or apply_now.is_success(page) or firefox_real.copilot_says_submitted(page):
        return "submitted"
    if apply_now.is_verify_error(page):
        return "verify"
    empty = firefox_real.empty_required_count(page)
    if empty == 0 and firefox_real.click_submit(page):
        page.wait_for_timeout(2000)
        if apply_now.is_success(page) or firefox_real.copilot_says_submitted(page):
            return "submitted"
    if empty:
        print(f"  {empty} required empty on {job.get('title')}. Leaving tab open.", flush=True)
    return "open"


def handle_url(driver, handle: str) -> str:
    try:
        driver.switch_to.window(handle)
        return (driver.current_url or "").split("?")[0].rstrip("/")
    except Exception:
        return ""


def match_job(url: str, job: dict) -> bool:
    jurl = job_url(job).split("?")[0].rstrip("/")
    jid = str(job.get("job_id") or "")
    if jid and jid in url:
        return True
    return jurl and (jurl in url or url in jurl)


def main() -> None:
    apply_now.BATCH = apply_now.load_all_discovered()
    form_memory.seed_from_learned()
    pending = apply_now.queue()
    if not pending:
        print("No pending jobs.", flush=True)
        return
    print(f"Applying {len(pending)} pending jobs, max {MAX_TABS} tabs at a time.", flush=True)
    idx = 0
    open_jobs: list[dict] = []
    while idx < len(pending) and len(open_jobs) < MAX_TABS:
        job = pending[idx]
        idx += 1
        url = job_url(job)
        print(f"  Open [{len(open_jobs)+1}/{MAX_TABS}] {job.get('company')}: {job.get('title')}", flush=True)
        print(f"    {url}", flush=True)
        open_tab(url, first=not open_jobs)
        open_jobs.append(job)
        time.sleep(3 if len(open_jobs) == 1 else 2.2)

    driver = None
    page = None
    try:
        time.sleep(6)
        driver = firefox_real.attach_existing_driver()
        page = SelPage(driver)
    except Exception as e:
        print(f"  Could not attach ({e}). Three job tabs are open. I will not close Firefox.", flush=True)
        print("  Use Copilot on those tabs. I will not steal focus or minimize apps.", flush=True)
        return

    slots: dict[str, dict] = {}
    worked: set[str] = set()
    results: list[dict] = []
    deadline = time.time() + 1800
    last_pass = 0.0

    def refresh_slots() -> None:
        for handle in list(driver.window_handles):
            url = handle_url(driver, handle)
            if handle in slots:
                continue
            for job in open_jobs:
                if match_job(url, job):
                    slots[handle] = job
                    break

    refresh_slots()
    print(f"  Attached. Tracking {len(slots)} job tab(s).", flush=True)

    while open_jobs and time.time() < deadline:
        refresh_slots()
        progressed = False
        for handle in list(driver.window_handles):
            job = slots.get(handle)
            if not job:
                continue
            try:
                driver.switch_to.window(handle)
            except Exception:
                continue
            key = str(job.get("job_id") or job.get("url"))
            if key not in worked:
                print(f"\n  Working: {job.get('company')}: {job.get('title')}", flush=True)
                status = work_slot(page, job)
                worked.add(key)
            else:
                status = "submitted" if (
                    apply_now.is_success(page) or firefox_real.copilot_says_submitted(page)
                ) else ("verify" if apply_now.is_verify_error(page) else "open")
                if status == "open":
                    step = firefox_real.follow_copilot(page)
                    if step == "submitted":
                        status = "submitted"
                    elif step == "clicked":
                        form_memory.fill_visible(page)
            if status == "submitted":
                results.append(mark_submitted(job, page))
                open_jobs = [j for j in open_jobs if j is not job]
                slots.pop(handle, None)
                try:
                    driver.close()
                except Exception:
                    pass
                progressed = True
                if idx < len(pending) and len(open_jobs) < MAX_TABS:
                    nxt = pending[idx]
                    idx += 1
                    url = job_url(nxt)
                    print(f"  Slot free. Opening {nxt.get('company')}: {nxt.get('title')}", flush=True)
                    open_tab(url, first=False)
                    open_jobs.append(nxt)
                    time.sleep(2.2)
                    worked.discard(str(nxt.get("job_id") or nxt.get("url")))
                break
            if status == "verify":
                apply_now.block_company(job.get("company") or "")
                print(f"  VERIFY_ERROR: {job.get('company')}: {job.get('title')}", flush=True)
                open_jobs = [j for j in open_jobs if j is not job]
                slots.pop(handle, None)
                progressed = True
                if idx < len(pending) and len(open_jobs) < MAX_TABS:
                    nxt = pending[idx]
                    idx += 1
                    print(f"  Slot free. Opening {nxt.get('company')}: {nxt.get('title')}", flush=True)
                    open_tab(job_url(nxt), first=False)
                    open_jobs.append(nxt)
                    time.sleep(2.2)
                break
            if status == "closed":
                print(f"  CLOSED listing: {job.get('title')}", flush=True)
                open_jobs = [j for j in open_jobs if j is not job]
                slots.pop(handle, None)
                progressed = True
                break
        if not progressed:
            if time.time() - last_pass > 20:
                titles = ", ".join(j.get("title", "")[:40] for j in open_jobs)
                print(f"  Waiting on open tabs: {titles}", flush=True)
                last_pass = time.time()
            time.sleep(3)

    print("  Firefox stays open. I will not close it.", flush=True)
    print(f"Done. Submitted {sum(1 for r in results if r.get('ok'))} this run.", flush=True)


if __name__ == "__main__":
    main()
