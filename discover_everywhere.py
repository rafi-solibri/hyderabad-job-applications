"""Search Naukri, Indeed, Instahyre, Foundit, Cutshort, Shine, Hirist, and more."""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import apply_now
import discover_bulk
import discover_final as d
import discover_more_sites as more

ROOT = Path(__file__).resolve().parent
CTX = ssl.create_default_context()
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
QUERIES = [
    "technical architect",
    "solution architect",
    "software architect",
    "principal engineer",
    "staff software engineer",
    "engineering manager",
    "technical lead",
    "senior software engineer",
    ".net architect",
    "lead software engineer",
    "principal software engineer",
    "staff engineer",
]


def fetch(url: str, data=None, headers=None, timeout=22):
    h = {
        "User-Agent": UA,
        "Accept": "application/json, text/xml, application/xml, text/html;q=0.8, */*;q=0.5",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            return text, resp.status, dict(resp.headers)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return body, e.code, {}
    except Exception as e:
        return str(e), 0, {}


def fetch_json(url: str, data=None, headers=None):
    text, status, _ = fetch(url, data=data, headers=headers)
    if status != 200 or not text:
        return None, status
    try:
        return json.loads(text), status
    except Exception:
        return None, status


def pull_instahyre(jobs):
    print("Instahyre...", flush=True)
    offset = 0
    seen = 0
    for _ in range(60):
        data, status = fetch_json(
            f"https://www.instahyre.com/api/v1/job_search/?offset={offset}&limit=50"
        )
        if status != 200 or not data:
            print(f"  stop at offset {offset} status {status}", flush=True)
            break
        rows = data.get("objects") or data.get("results") or []
        if not rows:
            break
        for item in rows:
            seen += 1
            locs = item.get("locations") or []
            place = " ".join(str(x) for x in locs) if isinstance(locs, list) else str(locs or "")
            emp = item.get("employer") if isinstance(item.get("employer"), dict) else {}
            company = emp.get("company_name") or item.get("company_name") or "instahyre"
            title = item.get("title") or item.get("candidate_title") or ""
            jid = item.get("id") or item.get("job_id") or ""
            link = item.get("public_url") or (f"https://www.instahyre.com/job-{jid}" if jid else "")
            d.add(jobs, company, title, place, link, "Instahyre", jid)
        offset += len(rows)
        if not (data.get("meta") or {}).get("next"):
            break
        time.sleep(0.07)
    print(f"  scanned {seen}", flush=True)


def pull_foundit(jobs):
    print("Foundit...", flush=True)
    cards = 0
    for q in QUERIES:
        slug = q.replace(" ", "-")
        start = 0
        for _ in range(3):
            qs = urllib.parse.urlencode({
                "limit": 20,
                "query": q,
                "locations": "Hyderabad",
                "experienceRanges": "8~20",
                "sort": 1,
                "start": start,
            })
            url = f"https://www.foundit.in/middleware/jobsearch?{qs}"
            data, status = fetch_json(
                url,
                headers={
                    "Referer": f"https://www.foundit.in/search/{slug}-jobs-in-hyderabad",
                    "Origin": "https://www.foundit.in",
                    "Content-Type": "application/json",
                },
            )
            if status != 200 or not data:
                print(f"  {q!r} start {start} status {status}", flush=True)
                break
            rows = (
                data.get("jobSearchResponse")
                or data.get("data")
                or data.get("jobList")
                or data.get("jobSearchResult")
                or []
            )
            if isinstance(rows, dict):
                rows = rows.get("data") or rows.get("jobs") or rows.get("jobDtoList") or []
            if not isinstance(rows, list) or not rows:
                # dump keys once
                if start == 0:
                    print(f"  {q!r} keys {list(data)[:12]}", flush=True)
                break
            cards += len(rows)
            for item in rows:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("jobTitle") or ""
                company = item.get("companyName") or item.get("company") or "foundit"
                loc = item.get("locations") or item.get("jobLocation") or item.get("location") or "Hyderabad"
                if isinstance(loc, list):
                    loc = " ".join(str(x.get("name") if isinstance(x, dict) else x) for x in loc)
                jid = str(item.get("jobId") or item.get("id") or "")
                link = item.get("seoUrl") or item.get("jobUrl") or item.get("applyUrl") or ""
                if not link and jid:
                    link = f"https://www.foundit.in/job/{jid}"
                d.add(jobs, company, title, str(loc), link, "Foundit", jid)
            start += 20
            time.sleep(0.2)
        time.sleep(0.15)
    print(f"  Foundit cards {cards}", flush=True)


def pull_indeed(jobs):
    print("Indeed India RSS...", flush=True)
    cards = 0
    for q in QUERIES:
        qs = urllib.parse.urlencode({"q": q, "l": "Hyderabad, Telangana"})
        text, status, _ = fetch(
            f"https://in.indeed.com/rss?{qs}",
            headers={"Accept": "application/rss+xml, application/xml, text/xml, */*"},
        )
        if status != 200 or not text or "<item" not in text.lower():
            print(f"  {q!r} status {status} bytes {len(text or '')}", flush=True)
            continue
        try:
            root = ET.fromstring(text)
        except Exception as e:
            print(f"  {q!r} xml {e}", flush=True)
            continue
        ns = {"a": "http://www.w3.org/2005/Atom"}
        items = root.findall("channel/item") or root.findall(".//{http://purl.org/rss/1.0/}item")
        if not items:
            items = list(root.iter("item"))
        for item in items:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = item.findtext("description") or ""
            loc = "Hyderabad, India"
            if re.search(r"remote|hyderabad|telangana|india", desc, re.I):
                loc = re.sub(r"<[^>]+>", " ", desc)[:80] + " Hyderabad India"
            company = ""
            m = re.search(r"-\s*([^-|]+)$", title)
            if m:
                company = m.group(1).strip()
                title = title[: m.start()].strip(" -|")
            jid = ""
            jm = re.search(r"[?&]jk=([a-z0-9]+)", link, re.I)
            if jm:
                jid = jm.group(1)
            cards += 1
            d.add(jobs, company or "indeed", title, loc, link, "Indeed", jid)
        time.sleep(0.2)
    print(f"  Indeed items {cards}", flush=True)


def pull_naukri(jobs):
    print("Naukri...", flush=True)
    cards = 0
    headers = {
        "appid": "109",
        "systemid": "Naukri",
        "Referer": "https://www.naukri.com/",
        "Origin": "https://www.naukri.com",
        "Accept": "application/json",
    }
    for q in QUERIES[:6]:
        qs = urllib.parse.urlencode({
            "noOfResults": 20,
            "urlType": "search_by_key_loc",
            "searchType": "adv",
            "keyword": q,
            "location": "hyderabad",
            "pageNo": 1,
            "experience": "10",
        })
        data, status = fetch_json(f"https://www.naukri.com/jobapi/v3/search?{qs}", headers=headers)
        print(f"  api {q!r} status {status}", flush=True)
        if status == 200 and data:
            for item in data.get("jobDetails") or []:
                cards += 1
                loc = item.get("placeholders")
                place = "Hyderabad, India"
                if isinstance(loc, list):
                    place = " ".join(str(p.get("label") or "") for p in loc if isinstance(p, dict)) or place
                elif isinstance(loc, str):
                    place = loc
                jid = item.get("jobId") or ""
                link = item.get("jdURL") or ""
                if link and link.startswith("/"):
                    link = "https://www.naukri.com" + link
                d.add(jobs, item.get("companyName") or "naukri", item.get("title") or "", place, link, "Naukri", jid)
            time.sleep(0.3)
            continue
        slug = q.replace(" ", "-")
        html, hstatus, _ = fetch(
            f"https://www.naukri.com/{slug}-jobs-in-hyderabad",
            headers={"Accept": "text/html", "Referer": "https://www.naukri.com/"},
        )
        print(f"  html {q!r} status {hstatus} bytes {len(html or '')}", flush=True)
        if hstatus == 200 and html:
            for m in re.finditer(
                r'"title"\s*:\s*"([^"]{8,80})".{0,400}?"companyName"\s*:\s*"([^"]+)".{0,400}?"jdURL"\s*:\s*"([^"]+)"',
                html,
                re.S,
            ):
                cards += 1
                title, company, link = m.group(1), m.group(2), m.group(3)
                if link.startswith("/"):
                    link = "https://www.naukri.com" + link
                d.add(jobs, company, title, "Hyderabad, India", link, "Naukri", link[-12:])
        time.sleep(0.4)
    print(f"  Naukri cards {cards}", flush=True)


def pull_cutshort(jobs):
    print("Cutshort...", flush=True)
    cards = 0
    for q in ("architect", "staff engineer", "principal engineer", "senior software engineer"):
        qs = urllib.parse.urlencode({"q": f"{q} hyderabad"})
        for url in (
            f"https://cutshort.io/api/jobs?search={urllib.parse.quote(q + ' hyderabad')}",
            f"https://cutshort.io/explore/jobs?{qs}",
            f"https://cutshort.io/profile/jobs?search={urllib.parse.quote(q)}&location=hyderabad",
        ):
            text, status, hdrs = fetch(url, headers={"Referer": "https://cutshort.io/"})
            ctype = (hdrs.get("Content-Type") or "")
            print(f"  {url.split('?')[0][-24:]} {q!r} {status} {ctype[:24]}", flush=True)
            if status != 200 or not text:
                continue
            data = None
            try:
                data = json.loads(text)
            except Exception:
                data = None
            rows = []
            if isinstance(data, dict):
                rows = data.get("jobs") or data.get("data") or data.get("results") or []
            elif isinstance(data, list):
                rows = data
            for item in rows if isinstance(rows, list) else []:
                if not isinstance(item, dict):
                    continue
                cards += 1
                d.add(
                    jobs,
                    item.get("company_name") or item.get("company") or "cutshort",
                    item.get("title") or item.get("job_title") or "",
                    str(item.get("location") or item.get("city") or "Hyderabad"),
                    item.get("url") or item.get("apply_url") or "",
                    "Cutshort",
                    item.get("id") or item.get("_id") or "",
                )
            for m in re.finditer(r'href="(/job/[^"]+)"[^>]*>([^<]{8,90})', text):
                cards += 1
                d.add(jobs, "cutshort", m.group(2).strip(), "Hyderabad, India", "https://cutshort.io" + m.group(1), "Cutshort", m.group(1))
            if rows or cards:
                break
        time.sleep(0.2)
    print(f"  Cutshort cards {cards}", flush=True)


def pull_shine(jobs):
    print("Shine...", flush=True)
    cards = 0
    for q in QUERIES[:6]:
        qs = urllib.parse.urlencode({"q": q, "loc": "hyderabad", "minexp": 10})
        data, status = fetch_json(
            f"https://www.shine.com/api/v2/search/advance/?{qs}",
            headers={"Referer": "https://www.shine.com/", "Accept": "application/json"},
        )
        print(f"  {q!r} status {status}", flush=True)
        if status != 200 or not data:
            continue
        rows = data.get("results") or data.get("jobs") or data.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("jobs") or rows.get("results") or []
        for item in rows if isinstance(rows, list) else []:
            if not isinstance(item, dict):
                continue
            cards += 1
            jid = item.get("id") or item.get("jobId") or ""
            link = item.get("url") or item.get("seoUrl") or (f"https://www.shine.com/jobs/{jid}" if jid else "")
            d.add(
                jobs,
                item.get("company") or item.get("companyName") or "shine",
                item.get("title") or item.get("jobTitle") or "",
                item.get("location") or item.get("city") or "Hyderabad, India",
                link,
                "Shine",
                jid,
            )
        time.sleep(0.2)
    print(f"  Shine cards {cards}", flush=True)


def pull_hirist(jobs):
    print("Hirist...", flush=True)
    cards = 0
    for q in QUERIES[:6]:
        qs = urllib.parse.urlencode({"keyword": q, "location": "hyderabad", "exp": 10})
        data, status = fetch_json(
            f"https://www.hirist.tech/j/api/v1/search?{qs}",
            headers={"Referer": "https://www.hirist.tech/", "Accept": "application/json"},
        )
        print(f"  {q!r} status {status}", flush=True)
        if status != 200 or not data:
            continue
        rows = data.get("jobs") or data.get("data") or data.get("results") or []
        if isinstance(data, list):
            rows = data
        for item in rows if isinstance(rows, list) else []:
            if not isinstance(item, dict):
                continue
            cards += 1
            loc = item.get("location") or item.get("locations") or "Hyderabad"
            if isinstance(loc, list):
                loc = " ".join(str(x) for x in loc)
            jid = item.get("id") or item.get("jobId") or ""
            link = item.get("url") or f"https://www.hirist.tech/j/{jid}"
            d.add(jobs, item.get("company") or item.get("companyName") or "hirist", item.get("title") or "", str(loc), link, "Hirist", jid)
        time.sleep(0.2)
    print(f"  Hirist cards {cards}", flush=True)


def pull_timesjobs(jobs):
    print("TimesJobs...", flush=True)
    cards = 0
    for q in QUERIES[:5]:
        qs = urllib.parse.urlencode({
            "searchType": "personalizedSearch",
            "from": "submit",
            "txtKeywords": q,
            "txtLocation": "Hyderabad",
            "cboWorkExp1": "10",
        })
        html, status, _ = fetch(
            f"https://www.timesjobs.com/candidate/job-search.html?{qs}",
            headers={"Accept": "text/html", "Referer": "https://www.timesjobs.com/"},
        )
        print(f"  {q!r} status {status} bytes {len(html or '')}", flush=True)
        if status != 200 or not html:
            continue
        for m in re.finditer(
            r'<h2>\s*<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{8,90})\s*</a>.*?<h3[^>]*>([^<]{2,80})',
            html,
            re.S | re.I,
        ):
            cards += 1
            d.add(jobs, m.group(3).strip(), m.group(2).strip(), "Hyderabad, India", m.group(1).strip(), "TimesJobs", "")
        time.sleep(0.3)
    print(f"  TimesJobs cards {cards}", flush=True)


def pull_remote_boards(jobs):
    print("Remote OK / Remotive / WWR...", flush=True)
    data, status = fetch_json("https://remoteok.com/api")
    n = 0
    if status == 200 and isinstance(data, list):
        for item in data:
            if not isinstance(item, dict) or not item.get("position"):
                continue
            loc = f"{item.get('location') or ''} {item.get('country') or ''} Remote"
            d.add(jobs, item.get("company") or "remoteok", item.get("position") or "", loc, item.get("url") or item.get("apply_url") or "", "RemoteOK", item.get("id") or item.get("slug") or "")
            n += 1
    print(f"  RemoteOK rows {n} status {status}", flush=True)

    data, status = fetch_json("https://remotive.com/api/remote-jobs?category=software-dev")
    n = 0
    rows = (data or {}).get("jobs") if isinstance(data, dict) else []
    for item in rows or []:
        loc = f"{item.get('candidate_required_location') or ''} Remote"
        d.add(jobs, item.get("company_name") or "remotive", item.get("title") or "", loc, item.get("url") or "", "Remotive", item.get("id") or "")
        n += 1
    print(f"  Remotive rows {n} status {status}", flush=True)

    text, status, _ = fetch("https://weworkremotely.com/categories/remote-programming-jobs.rss")
    n = 0
    if status == 200 and text and "<item" in text:
        for item in ET.fromstring(text).iter("item"):
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            desc = item.findtext("description") or ""
            loc = "Remote"
            if re.search(r"india|hyderabad|telangana", title + desc, re.I):
                loc = "Remote India"
            d.add(jobs, "weworkremotely", title, loc, link, "WWR", link[-20:])
            n += 1
    print(f"  WWR items {n} status {status}", flush=True)


def pull_linkedin_guest(jobs):
    print("LinkedIn guest search...", flush=True)
    cards = 0
    for q in QUERIES[:3]:
        qs = urllib.parse.urlencode({
            "keywords": q,
            "location": "Hyderabad, Telangana, India",
            "f_TPR": "r2592000",
            "position": 1,
            "pageNum": 0,
        })
        html, status, _ = fetch(
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{qs}",
            headers={"Accept": "text/html", "Referer": "https://www.linkedin.com/jobs/search/"},
        )
        print(f"  {q!r} status {status} bytes {len(html or '')}", flush=True)
        if status != 200 or not html:
            continue
        for m in re.finditer(
            r'href="(https://[^\"]+/jobs/view/[^\"]+)"[^>]*>\s*([^<]{8,90})',
            html,
        ):
            cards += 1
            d.add(jobs, "linkedin", m.group(2).strip(), "Hyderabad, India", m.group(1).split("?")[0], "LinkedIn", "")
        time.sleep(2.5)
    print(f"  LinkedIn cards {cards}", flush=True)


def main():
    jobs = []
    pull_instahyre(jobs)
    pull_foundit(jobs)
    pull_indeed(jobs)
    pull_naukri(jobs)
    pull_cutshort(jobs)
    pull_shine(jobs)
    pull_hirist(jobs)
    pull_timesjobs(jobs)
    pull_remote_boards(jobs)
    pull_linkedin_guest(jobs)
    print(f"Everywhere raw matched rows: {len(jobs)}", flush=True)
    more.merge_and_write(jobs)
    apply_now.BATCH = apply_now.load_all_discovered()
    q = apply_now.queue()
    print(f"PENDING {len(q)}", flush=True)
    for j in q[:25]:
        print(f"  {j.get('company')} | {j.get('title')} | {j.get('location')} | {j.get('ats')}", flush=True)


if __name__ == "__main__":
    main()
