"""Drive Simplify Copilot in the rafi.success@gmail.com Chrome profile.

Always open Copilot and click Autofill this page. Never click Tailor Resume
or Resume Builder.
"""
from __future__ import annotations

import io
import re
import struct
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXT_DIR = ROOT / "data" / "tools" / "simplify-ext"
EXT_ID = "pbanhockgagggenencehbnadejlgchfc"
SKIP_RE = r"tailor resume|resume builder|run autofill again|autofill again|enable ai|cover letter"

OPEN_COPILOT_JS = """() => {
  const ids = ['simplify-icon', 'simplify-icon-apply', 'sabre-apply-lightning', 'fill-button'];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el) { el.click(); return id; }
  }
  const nodes = document.querySelectorAll('button, [role="button"], img, svg, div, span');
  for (const el of nodes) {
    const t = ((el.getAttribute('aria-label') || el.id || el.title || el.innerText || '') + '').toLowerCase();
    if ((t.includes('simplify') || t.includes('copilot')) && t.length < 40
        && !t.includes('autofill again') && !t.includes('tailor') && !t.includes('resume builder')) {
      (el.closest('button, [role="button"]') || el).click();
      return t.slice(0, 40);
    }
  }
  return '';
}"""

CLICK_COPILOT_START_JS = """() => {
  const skip = /tailor resume|resume builder|run autofill again|cover letter/i;
  const fire = (el, label) => {
    const btn = el.closest('button, a, [role="button"]') || el;
    btn.scrollIntoView({block: 'center'});
    try { btn.click(); } catch (e) {}
    return label;
  };
  const byId = document.getElementById('start-application-button');
  if (byId) return fire(byId, byId.getAttribute('aria-label') || 'Start Application');
  const want = /^(start application|apply now|continue application)$/i;
  const hits = [];
  const walk = (root) => {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('button, a, [role="button"]').forEach((el) => {
      const t = ((el.innerText || el.getAttribute('aria-label') || el.id || '') + '').replace(/\\s+/g, ' ').trim();
      if (!t || t.length > 48 || skip.test(t)) return;
      const r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 8) return;
      if (want.test(t) && r.left > window.innerWidth * 0.55) {
        const rank = /^start application$/i.test(t) ? 0 : /^apply now$/i.test(t) ? 1 : 2;
        hits.push({el, t, rank});
      }
    });
    root.querySelectorAll('*').forEach((el) => { if (el.shadowRoot) walk(el.shadowRoot); });
  };
  walk(document);
  hits.sort((a, b) => a.rank - b.rank);
  if (hits.length) return fire(hits[0].el, hits[0].t);
  return '';
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
  const isSkip = (el) => /tailor resume|resume builder|run autofill again|autofill again/.test(labelOf(el) + ' ' + (el.id || ''));
  const isFillPage = (el) => {
    const t = labelOf(el);
    const aria = (el.getAttribute('aria-label') || '').toLowerCase();
    const id = (el.id || '').toLowerCase();
    if (isSkip(el)) return false;
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
      if (byId && !isSkip(byId)) { fire(byId); return 'fill-button'; }
    }
    const q = root.querySelectorAll ? root.querySelectorAll('button, a, [role="button"], [aria-label], [id], span, div') : [];
    for (const el of q) {
      if (isFillPage(el)) { fire(el); return el.getAttribute('aria-label') || el.id || (el.innerText || '').trim().slice(0, 40); }
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

COPILOT_STATE_JS = """() => {
  const doneRe = /application submitted|application already submitted|successfully submitted|we submitted your application|applied with simplify/i;
  const actRe = /continue with application|continue application|accept and continue|create account|create account & autofill|create account and autofill|sign in and autofill|sign in to simplify|log in to autofill|start applying|start application|autofill with resume|autofill this page|save and continue|^continue$|^next$|submit application|^submit$/i;
  const skipRe = /enable ai|request autofill|hide until|cover letter|upload &|unlimited resumes|^apply now$|^apply$|tailor resume|resume builder|run autofill again/i;
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
        const r = el.getBoundingClientRect();
        if (r.left < window.innerWidth * 0.55) return;
        if (/^(create account|sign in|log in)$/i.test(t)) return;
        out.actions.push(t);
        if (!out.action) out.action = t;
      }
      if (el.shadowRoot) walk(el.shadowRoot);
    });
  };
  walk(document);
  return out;
}"""


def ensure_extension() -> Path:
    """Download Simplify Copilot CRX into data/tools/simplify-ext if needed."""
    manifest = EXT_DIR / "manifest.json"
    if manifest.exists():
        return EXT_DIR
    EXT_DIR.mkdir(parents=True, exist_ok=True)
    url = (
        "https://clients2.google.com/service/update2/crx"
        "?response=redirect&prodversion=148.0.7778.96&acceptformat=crx3"
        f"&x=id%3D{EXT_ID}%26installsource%3Dondemand%26uc"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Chrome/148.0.0.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    if data[:4] != b"Cr24":
        raise RuntimeError(f"Simplify CRX magic was {data[:8]!r}")
    header_size = struct.unpack("<I", data[8:12])[0]
    zdata = data[12 + header_size :]
    with zipfile.ZipFile(io.BytesIO(zdata)) as zf:
        zf.extractall(EXT_DIR)
    print(f"  Installed Simplify Copilot into {EXT_DIR}", flush=True)
    return EXT_DIR


def watch(page) -> str:
    try:
        opened = page.evaluate(OPEN_COPILOT_JS) or ""
    except Exception:
        opened = ""
    if opened:
        print(f"  Watching Simplify Copilot ({opened}).", flush=True)
        page.wait_for_timeout(600)
    return opened


def start_application(page) -> str:
    """Click Copilot Start Application / Apply Now on the right. Never Tailor Resume."""
    watch(page)
    hit = ""
    try:
        hit = page.evaluate(CLICK_COPILOT_START_JS) or ""
    except Exception:
        hit = ""
    if not hit:
        try:
            loc = page.locator("#start-application-button")
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=2000)
                hit = "Start Application"
        except Exception:
            pass
    if hit:
        print(f"  Simplify Copilot: clicked '{hit}'.", flush=True)
        page.wait_for_timeout(2500)
        return hit
    return ""


def autofill(page) -> bool:
    """Click Autofill this page once. Never Tailor Resume / Resume Builder."""
    page.wait_for_timeout(1800)
    watch(page)
    page.wait_for_timeout(1200)
    hit = ""
    for _ in range(6):
        try:
            hit = page.evaluate(CLICK_FILL_PAGE_JS) or ""
        except Exception:
            hit = ""
        if hit:
            break
        page.wait_for_timeout(900)
    if hit:
        print(f"  Simplify Copilot: clicked '{hit}'.", flush=True)
        page.wait_for_timeout(4500)
        return True
    print("  Simplify Copilot: Autofill this page not in DOM; sending Alt+Shift+F.", flush=True)
    try:
        page.keyboard.press("Alt+Shift+KeyF")
    except Exception:
        try:
            page.keyboard.down("Alt")
            page.keyboard.down("Shift")
            page.keyboard.press("f")
            page.keyboard.up("Shift")
            page.keyboard.up("Alt")
        except Exception:
            pass
    page.wait_for_timeout(4000)
    try:
        hit = page.evaluate(CLICK_FILL_PAGE_JS) or ""
    except Exception:
        hit = ""
    if hit:
        print(f"  Simplify Copilot: clicked '{hit}'.", flush=True)
        page.wait_for_timeout(3500)
        return True
    return False


def state(page) -> dict:
    try:
        return page.evaluate(COPILOT_STATE_JS) or {}
    except Exception:
        return {}


def on_apply_wizard(page) -> bool:
    try:
        url = (page.url or "").lower()
    except Exception:
        return False
    return any(x in url for x in ("/apply/section/", "/apply/email", "/apply/form", "stepname="))


def submitted(page) -> bool:
    if on_apply_wizard(page):
        return False
    st = state(page)
    msg = st.get("done") or ""
    if msg:
        print(f"  Simplify Copilot shows submitted: {msg}", flush=True)
        return True
    return False


def follow(page) -> str:
    """Click Copilot Continue / Create account / Submit. Skip Tailor Resume."""
    watch(page)
    st = state(page)
    if st.get("done") and not on_apply_wizard(page):
        print(f"  Simplify Copilot shows submitted: {st['done']}", flush=True)
        return "submitted"
    actions = [a for a in (st.get("actions") or []) if a]
    action = (st.get("action") or "").strip()
    for preferred in (
        "Start Application",
        "Continue Application",
        "Continue with application",
        "Submit application",
        "Submit Application",
        "Submit",
    ):
        if any(preferred.lower() == a.lower() for a in actions):
            action = next(a for a in actions if a.lower() == preferred.lower())
            break
    if action:
        low = action.lower()
        if "tailor" in low or "resume builder" in low:
            print(f"  Skipping Copilot '{action}'.", flush=True)
            return ""
        if re.fullmatch(r"create account|sign in|log in", low) or (
            low.startswith("create account") and "autofill" not in low
        ):
            print(f"  Skipping ATS '{action}' (portal auth is handled separately).", flush=True)
            return ""
        if low in {"next", "continue", "continue application"}:
            try:
                url = (page.url or "").lower()
            except Exception:
                url = ""
            if "stepname=applicantacknowledgment" in url or "stepname=acknowledg" in url:
                print(f"  Skipping Copilot '{action}' on acknowledgment — ATS checkboxes first.", flush=True)
                return ""
            try:
                blocked = page.locator(
                    "spl-input.ng-invalid, .c-spl-form-field--invalid, "
                    "spl-button[aria-label*='Cancel adding' i]"
                ).count()
            except Exception:
                blocked = 0
            if blocked:
                print(f"  Skipping Copilot '{action}' until leftover invalid fields are fixed.", flush=True)
                return ""
        exact = len(action) <= 16
        try:
            loc = page.get_by_role("button", name=action, exact=exact).first
            if not loc.count():
                loc = page.get_by_text(action, exact=exact).first
            if loc.count():
                loc.click(timeout=2000)
                print(f"  Simplify Copilot needs '{action}'. Clicked it.", flush=True)
                page.wait_for_timeout(2500)
                return "clicked"
        except Exception:
            pass
    return ""
