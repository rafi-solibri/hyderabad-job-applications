from playwright.sync_api import sync_playwright
import json
from pathlib import Path

urls = [
    "https://job-boards.greenhouse.io/crunchyroll/jobs/8074590",
    "https://boards.greenhouse.io/embed/job_app?for=inovalon&token=7517648003",
    "https://jobs.lever.co/keyloop/c2142ca2-378f-4868-b51d-a7819a1e4a9d/apply",
]

script = """() => {
  const els = [...document.querySelectorAll('input, select, textarea, [role=combobox], button')];
  return els.slice(0, 120).map(el => ({
    tag: el.tagName,
    type: el.type || '',
    name: el.name || '',
    id: el.id || '',
    role: el.getAttribute('role') || '',
    aria: el.getAttribute('aria-label') || '',
    placeholder: el.placeholder || '',
    text: (el.innerText || '').slice(0, 80),
    visible: !!(el.offsetWidth || el.offsetHeight),
  }));
}"""

out = {}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    for url in urls:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2500)
        data = page.evaluate(script)
        frames = []
        for fr in page.frames:
            try:
                frames.append({"url": fr.url, "fields": fr.evaluate(script)})
            except Exception as e:
                frames.append({"url": fr.url, "error": str(e)})
        out[url] = {"page": data, "frames": frames, "title": page.title()}
        print(url, "page fields", len(data), "frames", len(frames))
    browser.close()

Path("data/form_dump.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
