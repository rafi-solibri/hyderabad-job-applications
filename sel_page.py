"""Playwright-like page wrapper around Selenium Firefox."""
from __future__ import annotations

import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select


class SelLocator:
    def __init__(self, driver, css=None, xpath=None, text=None, elements=None):
        self.driver = driver
        self.css = css
        self.xpath = xpath
        self.text = text
        self._elements = elements

    def _find(self):
        if self._elements is not None:
            return self._elements
        try:
            if self.css:
                return self.driver.find_elements(By.CSS_SELECTOR, self.css)
            if self.xpath:
                return self.driver.find_elements(By.XPATH, self.xpath)
            if self.text:
                return self.driver.find_elements(By.XPATH, f"//*[contains(., {json_str(self.text)})]")
        except Exception:
            return []
        return []

    @property
    def first(self):
        els = self._find()
        return SelLocator(self.driver, elements=els[:1] if els else [])

    def count(self):
        return len(self._find())

    def all(self):
        return [SelLocator(self.driver, elements=[el]) for el in self._find()]

    def is_visible(self):
        els = self._find()
        return bool(els and els[0].is_displayed())

    def click(self, timeout=2000):
        els = self._find()
        if not els:
            raise RuntimeError("not found")
        els[0].click()
        return True

    def fill(self, value, timeout=2000):
        els = self._find()
        if not els:
            raise RuntimeError("not found")
        el = els[0]
        el.click()
        el.clear()
        el.send_keys(value)

    def input_value(self):
        els = self._find()
        return (els[0].get_attribute("value") or "") if els else ""

    def get_attribute(self, name):
        els = self._find()
        return els[0].get_attribute(name) if els else None

    def select_option(self, label=None, timeout=2000):
        els = self._find()
        if not els:
            raise RuntimeError("not found")
        Select(els[0]).select_by_visible_text(label)

    def locator(self, css):
        return SelLocator(self.driver, css=css)

    def filter(self, has_text=None):
        els = []
        for el in self._find():
            if has_text is None or has_text.search(el.text or ""):
                els.append(el)
        return SelLocator(self.driver, elements=els)

    def get_by_text(self, pattern, exact=False):
        return self.driver_page().get_by_text(pattern, exact=exact)  # unused

    def check(self, timeout=300):
        els = self._find()
        if els and not els[0].is_selected():
            els[0].click()


def json_str(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


class SelPage:
    def __init__(self, driver):
        self.driver = driver
        self.keyboard = self

    @property
    def url(self):
        return self.driver.current_url

    def title(self):
        return self.driver.title

    def goto(self, url, wait_until=None, timeout=45000):
        self.driver.set_page_load_timeout(timeout / 1000)
        self.driver.get(url)

    def wait_for_timeout(self, ms):
        time.sleep(ms / 1000)

    def bring_to_front(self):
        self.driver.switch_to.window(self.driver.current_window_handle)

    def inner_text(self, selector="body"):
        try:
            return self.driver.find_element(By.CSS_SELECTOR, selector).text
        except Exception:
            return self.driver.find_element(By.TAG_NAME, "body").text

    def evaluate(self, script, arg=None):
        js = script.strip()
        if arg is None:
            if js.startswith("()"):
                return self.driver.execute_script("return (" + js + ")()")
            return self.driver.execute_script("return " + js)
        if js.startswith("(") or js.startswith("()"):
            return self.driver.execute_script("return (" + js + ")(arguments[0])", arg)
        return self.driver.execute_script("return " + js, arg)

    def locator(self, selector):
        if selector.startswith("text=") or selector.startswith("xpath="):
            return SelLocator(self.driver, xpath=selector.split("=", 1)[-1])
        if ":has-text(" in selector:
            text = re.search(r":has-text\('([^']+)'\)", selector)
            tag = selector.split(":")[0] or "*"
            if text:
                return SelLocator(
                    self.driver,
                    xpath=f"//{tag}[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.group(1).lower()}')]",
                )
        return SelLocator(self.driver, css=selector)

    def get_by_text(self, pattern, exact=False):
        text = pattern.pattern if hasattr(pattern, "pattern") else str(pattern)
        text = text.replace("\\", "")[:60]
        if exact:
            return SelLocator(self.driver, xpath=f"//*[normalize-space()={json_str(text)}]")
        return SelLocator(
            self.driver,
            xpath=f"//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), {json_str(text.lower())})]",
        )

    def get_by_label(self, pattern):
        text = pattern.pattern if hasattr(pattern, "pattern") else str(pattern)
        text = re.sub(r"[\\^$.*+?()\\[\\]{}|]", "", text)[:40]
        return SelLocator(
            self.driver,
            xpath=f"//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), {json_str(text.lower())})]/following::input[1] | //label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), {json_str(text.lower())})]/following::textarea[1]",
        )

    def press(self, key):
        if key == "Enter":
            self.driver.switch_to.active_element.send_keys(Keys.ENTER)
