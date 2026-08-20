"""ATS fill helpers ported from open-source apply engines.

Sources (MIT / public patterns), adapted for this Playwright + Copilot runner:
- Dropdown strategies: https://github.com/devdattatalele/auto-apply (lib/fields.mjs)
- React native value setter: same idea as Job App Filler / ats-autofill-engine

Do not launch a second browser or a second autofill extension — Simplify Copilot
already owns the Chrome profile. These helpers fill leftover fields Copilot misses.
"""
from __future__ import annotations

import re

NATIVE_SET_JS = """(el, value) => {
  if (!el) return false;
  const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype
    : window.HTMLInputElement.prototype;
  const desc = Object.getOwnPropertyDescriptor(proto, 'value');
  if (desc && desc.set) desc.set.call(el, value);
  else el.value = value;
  el.dispatchEvent(new Event('input', {bubbles: true, composed: true}));
  el.dispatchEvent(new Event('change', {bubbles: true, composed: true}));
  try { el.dispatchEvent(new Event('blur', {bubbles: true})); } catch (e) {}
  return true;
}"""

OPTION_SELECTORS = (
    '[role="option"]',
    ".select__option",
    ".select2-results__option",
    "li[class*='option']",
    ".dropdown-item",
    "div[data-value]",
    "[class*='MenuItem']",
    ".cx-select__list-item",
    ".oj-listbox-result-label",
)


def fuzzy_score(needle: str, haystack: str) -> float:
    a = (needle or "").lower().strip()
    b = (haystack or "").lower().strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if b.startswith(a) or a.startswith(b) or a in b or b in a:
        return 0.8
    aw, bw = a.split(), b.split()
    if not aw or not bw:
        return 0.0
    overlap = sum(1 for w in aw if any(w in x or x in w for x in bw))
    return overlap / max(len(aw), len(bw)) * 0.6


def native_fill(locator, value: str) -> bool:
    """Fill a React/controlled input so the ATS state actually updates."""
    try:
        locator.evaluate(NATIVE_SET_JS, str(value))
        return True
    except Exception:
        return False


def handle_dropdown(page, locator, value: str) -> bool:
    """Native select, type-to-filter, click-scan, then keyboard. From auto-apply."""
    if not value:
        return False
    try:
        if not locator.count():
            return False
        el = locator.first
        tag = (el.evaluate("n => (n.tagName || '').toLowerCase()") or "")
        if tag == "select":
            try:
                el.select_option(label=value, timeout=800)
                return True
            except Exception:
                try:
                    el.select_option(value=value, timeout=800)
                    return True
                except Exception:
                    pass
        el.scroll_into_view_if_needed(timeout=1500)
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        el.click(timeout=2000, force=True)
        page.wait_for_timeout(250)
        try:
            el.fill("")
            el.type(str(value)[:18], delay=35)
            page.wait_for_timeout(600)
        except Exception:
            pass
        if _click_best_option(page, value):
            return True
        try:
            page.keyboard.press("Escape")
            el.click(timeout=1500, force=True)
            page.wait_for_timeout(500)
        except Exception:
            pass
        if _click_best_option(page, value):
            return True
        for _ in range(12):
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(60)
            try:
                focused = page.locator(
                    ".select__option--is-focused, [role='option'][aria-selected='true']"
                ).first
                if focused.count():
                    text = (focused.inner_text() or "").strip()
                    if fuzzy_score(value, text) >= 0.5:
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(250)
                        return True
            except Exception:
                pass
        page.keyboard.press("Enter")
        return bool((el.input_value() or "").strip())
    except Exception:
        return False


def _click_best_option(page, value: str) -> bool:
    best = None
    best_score = 0.29
    for sel in OPTION_SELECTORS:
        try:
            loc = page.locator(sel)
            n = min(loc.count(), 40)
        except Exception:
            continue
        for i in range(n):
            opt = loc.nth(i)
            try:
                if not opt.is_visible():
                    continue
                text = (opt.inner_text() or "").strip()
            except Exception:
                continue
            if not text or len(text) > 90 or text.lower() == "no options":
                continue
            score = fuzzy_score(value, text)
            if score > best_score:
                best_score = score
                best = opt
    if best is None:
        return False
    try:
        best.click(timeout=1500, force=True)
        page.wait_for_timeout(250)
        return True
    except Exception:
        return False


def fill_empty_dropdowns(page, infer) -> int:
    """Fill visible empty selects / comboboxes using inferred answers."""
    filled = 0
    try:
        boxes = page.evaluate(
            """() => [...document.querySelectorAll('select, input[role=combobox], [role=combobox]')]
              .map(el => {
                const r = el.getBoundingClientRect();
                const lab = el.id ? document.querySelector('label[for="'+el.id+'"]') : null;
                const wrap = el.closest('label, fieldset, [class*=question], li, div');
                const q = ((lab && lab.innerText) || (wrap && (wrap.querySelector('label,legend')||{}).innerText) || el.getAttribute('aria-label') || el.name || '')
                  .replace(/\\s+/g,' ').trim().slice(0,180);
                let value = '';
                if (el.tagName === 'SELECT') {
                  const opt = el.options[el.selectedIndex];
                  value = ((opt && opt.text) || el.value || '').trim();
                } else value = (el.value || el.innerText || '').trim();
                return {id: el.id, name: el.name, q, value, vis: r.width>8 && r.height>8, tag: el.tagName};
              }).filter(x => x.vis)"""
        ) or []
    except Exception:
        return 0
    for box in boxes:
        cur = (box.get("value") or "").strip()
        if cur and cur.lower() not in {"select", "select...", "choose", ""}:
            continue
        want = infer(box.get("q") or "", [])
        if not want:
            continue
        sel = f'[id="{box["id"]}"]' if box.get("id") else f'[name="{box.get("name")}"]'
        try:
            loc = page.locator(sel).first
            if loc.count() and handle_dropdown(page, loc, want):
                filled += 1
        except Exception:
            continue
    if filled:
        print(f"  Filled {filled} dropdown(s) with open-source ATS handlers.", flush=True)
    return filled


def fill_phenom_acknowledgment(page) -> int:
    """Phenom loops Copilot Next until the applicant-acknowledgment boxes are checked."""
    try:
        url = (page.url or "").lower()
    except Exception:
        url = ""
    if "phenom" not in url and "thermofisher" not in url and "stepname=" not in url:
        return 0
    n = 0
    try:
        n = page.evaluate(
            """() => {
              let n = 0;
              const re = /acknowledg|agree|consent|certify|i have read|terms|privacy/i;
              for (const el of document.querySelectorAll('input[type=checkbox]')) {
                const wrap = el.closest('label') || el.parentElement || el;
                const t = ((wrap.innerText || '') + ' ' + (el.getAttribute('aria-label') || '') + ' ' + (el.id || ''));
                if (!re.test(t) || el.checked) continue;
                el.checked = true;
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
                try { wrap.click(); } catch (e) {}
                n++;
              }
              return n;
            }"""
        ) or 0
    except Exception:
        n = 0
    if n:
        print(f"  Checked {n} Phenom acknowledgment box(es).", flush=True)
    return n
