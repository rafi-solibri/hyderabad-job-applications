"""Drive the real Mozilla Firefox profile (Simplify + rafi.success@gmail.com)."""
from __future__ import annotations

import os
import shutil
import ssl
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "data" / "tools"
USER_PROFILE = Path.home() / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles" / "1f3myy1c.default-release"
GECKO_URL = "https://github.com/mozilla/geckodriver/releases/download/v0.36.0/geckodriver-v0.36.0-win64.zip"


def geckodriver_path() -> str:
    TOOLS.mkdir(parents=True, exist_ok=True)
    exe = TOOLS / "geckodriver.exe"
    if exe.exists():
        return str(exe)
    print("  Downloading geckodriver...", flush=True)
    zpath = TOOLS / "geckodriver.zip"
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(GECKO_URL, context=ctx, timeout=90) as resp:
        zpath.write_bytes(resp.read())
    with zipfile.ZipFile(zpath) as zf:
        zf.extract("geckodriver.exe", TOOLS)
    return str(exe)


def find_firefox() -> str | None:
    candidates = []
    try:
        out = subprocess.check_output(
            [
                "powershell", "-NoProfile", "-Command",
                "Get-AppxPackage Mozilla.Firefox | Select-Object -ExpandProperty InstallLocation",
            ],
            text=True,
            timeout=30,
        ).strip()
        if out:
            for p in Path(out).rglob("firefox.exe"):
                if p.is_file() and p.stat().st_size > 50_000:
                    candidates.append(p)
    except Exception:
        pass
    for p in (
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Mozilla Firefox" / "firefox.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Mozilla Firefox" / "firefox.exe",
        Path.home() / "AppData" / "Local" / "Mozilla Firefox" / "firefox.exe",
        Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "firefox.exe",
    ):
        candidates.append(p)
    which = shutil.which("firefox.exe") or shutil.which("firefox")
    if which:
        candidates.append(Path(which))
    for p in candidates:
        try:
            if p.is_file() and p.stat().st_size > 50_000:
                return str(p)
        except Exception:
            continue
    return None


def close_firefox() -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Process firefox -ErrorAction SilentlyContinue | Stop-Process -Force"],
        timeout=20,
    )
    time.sleep(2)
    lock = USER_PROFILE / "parent.lock"
    if lock.exists():
        try:
            lock.unlink()
        except Exception:
            pass


def _marionette_ports() -> list[int]:
    try:
        out = subprocess.check_output(
            [
                "powershell", "-NoProfile", "-Command",
                "Get-Process firefox -ErrorAction SilentlyContinue | ForEach-Object {"
                " Get-NetTCPConnection -OwningProcess $_.Id -State Listen -ErrorAction SilentlyContinue"
                "} | Select-Object -ExpandProperty LocalPort -Unique",
            ],
            text=True,
            timeout=25,
        )
    except Exception:
        return []
    ports = []
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            ports.append(int(line))
    return ports


def attach_existing_driver():
    """Drive the already-open Firefox. Never kills the browser."""
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service

    ports = _marionette_ports()
    print(f"  Trying to attach to open Firefox (marionette ports: {ports or 'none'}).", flush=True)
    last_err = None
    for port in ports or [2828]:
        try:
            service = Service(
                geckodriver_path(),
                service_args=["--connect-existing", "--marionette-port", str(port)],
            )
            driver = webdriver.Firefox(options=Options(), service=service)
            print(f"  Attached to open Firefox on port {port}.", flush=True)
            return driver
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Could not attach to open Firefox: {last_err}")


def open_new_tab(page, url: str) -> None:
    driver = page.driver
    before = list(driver.window_handles)
    driver.execute_script("window.open(arguments[0], '_blank')", url)
    page.wait_for_timeout(1500)
    after = list(driver.window_handles)
    opened = [h for h in after if h not in before]
    driver.switch_to.window(opened[-1] if opened else after[-1])
    print(f"  Opened next application in a new tab: {url[:90]}", flush=True)


def launch_new_driver():
    """Start Mozilla Firefox with the rafi.success profile. Never headless."""
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service

    if not USER_PROFILE.exists():
        raise RuntimeError(f"Firefox profile not found: {USER_PROFILE}")
    options = Options()
    binary = find_firefox()
    if binary:
        options.binary_location = binary
        print(f"  Starting Mozilla Firefox: {binary}", flush=True)
    else:
        print("  Starting Mozilla Firefox from PATH.", flush=True)
    options.add_argument("-profile")
    options.add_argument(str(USER_PROFILE))
    driver = webdriver.Firefox(options=options, service=Service(geckodriver_path()))
    try:
        driver.maximize_window()
    except Exception:
        pass
    print("  Mozilla Firefox is open.", flush=True)
    return driver


def launch_driver():
    if not USER_PROFILE.exists():
        raise RuntimeError(f"Firefox profile not found: {USER_PROFILE}")

    try:
        return attach_existing_driver()
    except Exception as e:
        print(f"  Could not attach to an already-open Firefox ({e}). Starting Mozilla now.", flush=True)
        return launch_new_driver()


CLICK_LABEL_JS = """(want) => {
  const needle = String(want || '').toLowerCase();
  const visible = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 4 && r.height > 4 && r.bottom > 0 && r.right > 0;
  };
  const labelOf = (el) => ((el.innerText || el.value || el.getAttribute('aria-label') || el.title || '') + '').replace(/\\s+/g, ' ').trim();
  const fire = (el) => {
    const btn = el.closest('button, [role="button"], a') || el;
    const r = btn.getBoundingClientRect();
    const x = r.left + r.width / 2;
    const y = r.top + r.height / 2;
    for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
      btn.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window, clientX: x, clientY: y}));
    }
    try { btn.click(); } catch (e) {}
  };
  const collect = (root, out) => {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('button, a, [role="button"], span, div, p, li').forEach((el) => {
      out.push(el);
      if (el.shadowRoot) collect(el.shadowRoot, out);
    });
    if (root.shadowRoot) collect(root.shadowRoot, out);
  };
  const pick = (root) => {
    const nodes = [];
    collect(root, nodes);
    const hits = [];
    for (const el of nodes) {
      const t = labelOf(el);
      if (!t || t.length > 70 || !t.toLowerCase().includes(needle) || !visible(el)) continue;
      const tag = (el.tagName || '').toLowerCase();
      const role = (el.getAttribute('role') || '').toLowerCase();
      const clickable = tag === 'button' || role === 'button' || tag === 'a' ? 0 : 1;
      const right = el.getBoundingClientRect().left > window.innerWidth * 0.45 ? 0 : 1;
      hits.push({el, t, clickable, right, len: t.length});
    }
    hits.sort((a, b) => a.clickable - b.clickable || a.right - b.right || a.len - b.len);
    if (!hits.length) return '';
    fire(hits[0].el);
    return hits[0].t;
  };
  let found = pick(document);
  if (found) return found;
  for (const frame of document.querySelectorAll('iframe')) {
    try {
      found = pick(frame.contentDocument);
      if (found) return found;
    } catch (e) {}
  }
  return '';
}"""

EMPTY_REQUIRED_JS = """() => {
  const vis = (el) => !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
  let n = 0;
  for (const el of document.querySelectorAll('input, select, textarea')) {
    if (!vis(el) || el.disabled || el.type === 'hidden' || el.type === 'submit' || el.type === 'file') continue;
    const req = el.required || el.getAttribute('aria-required') === 'true';
    if (!req) continue;
    if (el.type === 'checkbox' || el.type === 'radio') {
      const name = el.name;
      const group = name ? document.querySelectorAll(`input[name="${name}"]`) : [el];
      if (![...group].some((x) => x.checked)) n += 1;
      continue;
    }
    if (!(el.value || '').trim()) n += 1;
  }
  const msgs = [...document.querySelectorAll('p, span, div, li')].filter((el) =>
    /this field is required|is required|can't be blank|cannot be blank/i.test((el.innerText || '').trim())
    && (el.innerText || '').trim().length < 80
    && vis(el)
  );
  return n + msgs.length;
}"""

CLICK_FILL_PAGE_JS = """() => {
  const fire = (el) => {
    const btn = el.closest('button, [role="button"], a') || el;
    const r = btn.getBoundingClientRect();
    const x = r.left + Math.max(r.width / 2, 2);
    const y = r.top + Math.max(r.height / 2, 2);
    for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
      btn.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window, clientX: x, clientY: y}));
    }
    try { btn.click(); } catch (e) {}
  };
  const labelOf = (el) => ((el.innerText || el.value || el.getAttribute('aria-label') || el.title || '') + '').replace(/\\s+/g, ' ').trim().toLowerCase();
  const isAgain = (el) => /run autofill again|autofill again/.test(labelOf(el) + ' ' + (el.id || ''));
  const isFillPage = (el) => {
    const t = labelOf(el);
    const aria = (el.getAttribute('aria-label') || '').toLowerCase();
    const id = (el.id || '').toLowerCase();
    if (isAgain(el)) return false;
    return (
      t.includes('autofill this page') ||
      t.includes('auto-fill this page') ||
      t.includes('autofill this form') ||
      aria === 'autofill this page' ||
      id === 'fill-button'
    );
  };
  const walk = (root) => {
    if (!root) return '';
    if (root.getElementById) {
      const byId = root.getElementById('fill-button');
      if (byId && !isAgain(byId)) { fire(byId); return 'fill-button'; }
    }
    const q = root.querySelectorAll ? root.querySelectorAll('button, a, [role="button"], [aria-label], [id], span, div') : [];
    for (const el of q) {
      if (isFillPage(el)) { fire(el); return el.getAttribute('aria-label') || el.id || el.innerText.trim().slice(0, 40); }
      if (el.shadowRoot) {
        const hit = walk(el.shadowRoot);
        if (hit) return hit;
      }
    }
    if (root.shadowRoot) {
      const hit = walk(root.shadowRoot);
      if (hit) return hit;
    }
    return '';
  };
  let found = walk(document);
  if (found) return found;
  for (const frame of document.querySelectorAll('iframe')) {
    try {
      found = walk(frame.contentDocument);
      if (found) return found;
    } catch (e) {}
  }
  return '';
}"""

OPEN_COPILOT_JS = """() => {
  const ids = ['simplify-icon', 'simplify-icon-apply', 'sabre-apply-lightning'];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el) { el.click(); return id; }
  }
  const nodes = document.querySelectorAll('button, [role="button"], img, svg, div, span');
  for (const el of nodes) {
    const t = ((el.getAttribute('aria-label') || el.id || el.title || el.innerText || '') + '').toLowerCase();
    if ((t.includes('simplify') || t.includes('copilot')) && t.length < 40 && !t.includes('autofill again')) {
      (el.closest('button, [role="button"]') || el).click();
      return t.slice(0, 40);
    }
  }
  return '';
}"""

COPILOT_STATE_JS = """() => {
  const doneRe = /application submitted|application already submitted|successfully submitted|we submitted your application|applied with simplify/i;
  const actRe = /continue with application|accept and continue|create account|create account & autofill|create account and autofill|sign in and autofill|sign in to simplify|log in to autofill|start applying|start application|autofill with resume|autofill this page|save and continue|^continue$|^next$|submit application|^submit$/i;
  const skipRe = /enable ai|request autofill|hide until|cover letter|upload &|unlimited resumes|^apply now$|^apply$/i;
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 4 && r.height > 4;
  };
  const labelOf = (el) => ((el.innerText || el.value || el.getAttribute('aria-label') || '') + '').replace(/\\s+/g, ' ').trim();
  const out = {done: '', action: '', actions: []};
  const walk = (root) => {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('button, a, [role="button"], span, div, p, h1, h2, h3').forEach((el) => {
      const t = labelOf(el);
      if (!t || t.length > 80) return;
      if (!out.done && doneRe.test(t)) out.done = t.slice(0, 80);
      if (el.tagName && /BUTTON|A/.test(el.tagName) && visible(el) && actRe.test(t) && !skipRe.test(t) && t.length < 48) {
        out.actions.push(t);
        if (!out.action) out.action = t;
      }
      if (el.shadowRoot) walk(el.shadowRoot);
    });
  };
  walk(document);
  return out;
}"""


def watch_copilot(page) -> None:
    """Keep the Simplify Copilot panel in view."""
    opened = page.evaluate(OPEN_COPILOT_JS) or ""
    if opened:
        print(f"  Watching Copilot ({opened}).", flush=True)
        page.wait_for_timeout(600)


def copilot_state(page) -> dict:
    try:
        return page.evaluate(COPILOT_STATE_JS) or {}
    except Exception:
        return {}


def copilot_says_submitted(page) -> bool:
    st = copilot_state(page)
    msg = st.get("done") or ""
    if msg:
        print(f"  Copilot shows submitted: {msg}", flush=True)
        return True
    return False


def follow_copilot(page) -> str:
    """Watch Copilot and click Create account / Continue / similar once if needed.

    Returns 'submitted', 'clicked', or ''.
    """
    watch_copilot(page)
    st = copilot_state(page)
    if st.get("done"):
        print(f"  Copilot shows submitted: {st['done']}", flush=True)
        return "submitted"
    action = st.get("action") or ""
    if action:
        hit = _click_label_everywhere(page, (action,))
        if hit:
            print(f"  Copilot needs '{hit}'. Clicked it.", flush=True)
            page.wait_for_timeout(3000)
            return "clicked"
    if click_start_gate(page):
        return "clicked"
    return ""


SUBMIT_JS = """() => {
  const re = /submit application|submit your application|send application|^submit$|submit \\*?$/i;
  const nodes = [...document.querySelectorAll('button, input[type=submit], [role=button], a')];
  const hit = nodes.find(el => {
    const t = ((el.innerText || el.value || el.getAttribute('aria-label') || '') + '').replace(/\\s+/g, ' ').trim();
    if (!re.test(t) || t.length > 40) return false;
    const r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  });
  if (!hit) return '';
  hit.scrollIntoView({block: 'center'});
  hit.click();
  return (hit.innerText || hit.value || 'Submit').trim().slice(0, 40);
}"""


def _xpath_click_label(driver, needle: str) -> str:
    from selenium.webdriver.common.by import By

    q = needle.lower().replace("'", "")
    xpath = (
        "//*[contains(translate(normalize-space(.), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
        f"'{q}')]"
    )
    try:
        els = driver.find_elements(By.XPATH, xpath)
    except Exception:
        return ""
    best = None
    best_len = 10**9
    best_text = ""
    for el in els:
        try:
            if not el.is_displayed():
                continue
            t = " ".join(
                (
                    el.text
                    or el.get_attribute("aria-label")
                    or el.get_attribute("title")
                    or ""
                ).split()
            )
            if q not in t.lower() or len(t) > 70:
                continue
            if len(t) < best_len:
                best, best_len, best_text = el, len(t), t
        except Exception:
            continue
    if not best:
        return ""
    try:
        from selenium.webdriver.common.action_chains import ActionChains

        ActionChains(driver).move_to_element(best).pause(0.2).click().perform()
        return best_text
    except Exception:
        try:
            best.click()
            return best_text
        except Exception:
            try:
                driver.execute_script("arguments[0].click()", best)
                return best_text
            except Exception:
                return ""


def _click_label_everywhere(page, labels: tuple[str, ...]) -> str:
    for label in labels:
        found = page.evaluate(CLICK_LABEL_JS, label) or ""
        if found:
            return found
    driver = page.driver
    try:
        driver.switch_to.default_content()
    except Exception:
        pass
    for label in labels:
        found = _xpath_click_label(driver, label)
        if found:
            return found
    try:
        frames = driver.find_elements("css selector", "iframe, frame")
    except Exception:
        frames = []
    for frame in frames:
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            for label in labels:
                found = _xpath_click_label(driver, label)
                if found:
                    driver.switch_to.default_content()
                    return found
        except Exception:
            pass
        finally:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
    return ""


def empty_required_count(page) -> int:
    try:
        return int(page.evaluate(EMPTY_REQUIRED_JS) or 0)
    except Exception:
        return 0


def _send_autofill_hotkey(page) -> None:
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys

    try:
        page.bring_to_front()
    except Exception:
        pass
    ActionChains(page.driver).key_down(Keys.ALT).key_down(Keys.SHIFT).send_keys("f").key_up(Keys.SHIFT).key_up(Keys.ALT).perform()
    print("  Sent Alt+Shift+F to run Autofill this page.", flush=True)


def trigger_simplify(page) -> bool:
    """Click Autofill this page once. Do not click Run Autofill Again."""
    page.wait_for_timeout(2500)
    opened = page.evaluate(OPEN_COPILOT_JS) or ""
    if opened:
        print(f"  Opened Copilot ({opened}).", flush=True)
        page.wait_for_timeout(1500)
    hit = ""
    for _ in range(6):
        hit = page.evaluate(CLICK_FILL_PAGE_JS) or _click_label_everywhere(
            page,
            (
                "Autofill this page",
                "Autofill This Page",
                "Autofill this form",
                "Autofill with Resume",
            ),
        )
        if hit:
            break
        page.wait_for_timeout(1000)
    if hit:
        print(f"  Clicked Copilot '{hit}'.", flush=True)
        page.wait_for_timeout(5000)
        return True
    print("  Autofill this page button not in page DOM yet. Using Copilot shortcut.", flush=True)
    _send_autofill_hotkey(page)
    page.wait_for_timeout(5000)
    hit = page.evaluate(CLICK_FILL_PAGE_JS) or ""
    if hit:
        print(f"  Clicked Copilot '{hit}'.", flush=True)
        page.wait_for_timeout(4000)
        return True
    return False


APPLY_NOW_LABELS = (
    "Apply now",
    "Apply Now",
    "Apply for this job",
    "Apply for this Job",
    "Start application",
    "Start Application",
)


def focus_apply_tab(page) -> bool:
    """Use the newest Greenhouse/Lever apply tab instead of the listing tab."""
    driver = page.driver
    handles = list(driver.window_handles)
    if not handles:
        return False
    current = driver.current_window_handle
    best = None
    for handle in handles:
        try:
            driver.switch_to.window(handle)
            url = (driver.current_url or "").lower()
        except Exception:
            continue
        if any(x in url for x in ("job-boards.greenhouse.io", "boards.greenhouse.io", "jobs.lever.co", "/confirmation")):
            if "/jobs/" in url or "job_app" in url or "/apply" in url or "confirmation" in url:
                best = handle
    if best:
        driver.switch_to.window(best)
        print(f"  Switched to apply tab: {page.url[:90]}", flush=True)
        return True
    if len(handles) > 1:
        driver.switch_to.window(handles[-1])
        if driver.current_window_handle != current:
            print(f"  Switched to newest tab: {page.url[:90]}", flush=True)
            return True
    try:
        driver.switch_to.window(current)
    except Exception:
        driver.switch_to.window(handles[-1])
    return False


def click_apply_now(page) -> bool:
    """Click Apply now once and follow the tab it opens."""
    before = list(page.driver.window_handles)
    hit = _click_label_everywhere(page, APPLY_NOW_LABELS)
    if not hit:
        hit = _click_label_everywhere(page, ("Apply",))
        if hit and "apply" not in hit.lower():
            hit = ""
        if hit and len(hit) > 24:
            hit = ""
    if hit:
        print(f"  Clicked '{hit}'.", flush=True)
        page.wait_for_timeout(3000)
        after = list(page.driver.window_handles)
        opened = [h for h in after if h not in before]
        if opened:
            page.driver.switch_to.window(opened[-1])
            print(f"  Switched to the tab opened by Apply: {page.url[:90]}", flush=True)
        else:
            focus_apply_tab(page)
        click_start_gate(page)
        return True
    click_start_gate(page)
    return focus_apply_tab(page)


START_GATE_LABELS = (
    "Autofill with Resume",
    "Autofill this page",
    "Start Application",
    "Start applying",
    "Create account",
    "Continue with application",
    "Apply Manually",
)


def click_start_gate(page) -> bool:
    """Workday/Copilot often shows Autofill with Resume or Start Application after Apply."""
    hit = _click_label_everywhere(page, START_GATE_LABELS)
    if hit:
        print(f"  Clicked start gate '{hit}'.", flush=True)
        page.wait_for_timeout(4000)
        return True
    return False


def click_submit(page) -> bool:
    label = page.evaluate(SUBMIT_JS) or ""
    if not label:
        label = _click_label_everywhere(
            page,
            ("Submit application", "Submit Application", "Submit your application"),
        )
    if label:
        print(f"  Clicked '{label}'.", flush=True)
        page.wait_for_timeout(2000)
        return True
    return False
