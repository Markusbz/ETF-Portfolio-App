from __future__ import annotations
import os, time, random, logging, json, re, html
from pathlib import Path
from typing import Iterable, Mapping, Any

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .utils import get_logger
from .. import config

LOG = get_logger(__name__)
ROOT_URL   = "https://www.ishares.com"
COOKIE_URL = f"{ROOT_URL}/uk/professional/en"
CACHE_DIR  = config.CACHE_DIR
CACHE_DIR.mkdir(parents=True, exist_ok=True)
GATE_RE = re.compile(r'direct-url-screen', re.I)

class IsharesSession:

    def __init__(
        self,
        chrome_binary: str | Path,
        chromedriver_path: str | Path,
        headless: bool = True,
        cache_dir: Path = CACHE_DIR,
    ):
        self.cache_dir = cache_dir
        self._req = requests.Session()

        # ── grab cookie via a quick Selenium spin‑up ──────────────────────────
        opts = webdriver.ChromeOptions()
        if headless:
            opts.add_argument("--headless=new")
        if chrome_binary:
            opts.binary_location = str(chrome_binary)

        self._driver = webdriver.Chrome(
            service=Service(str(chromedriver_path)), options=opts
        )

        self._driver.get(COOKIE_URL)
        self._driver.execute_script(
        "document.getElementById('onetrust-consent-sdk')?.remove();"
        )
        try:
            WebDriverWait(self._driver, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Continue"))
            ).click()
            LOG.info("Pressed 'Continue' – investor cookie set.")
        except Exception as exc:
            LOG.warning("Could not click 'Continue'. Maybe cookie already present? %s", exc)

        # transfer cookies from Selenium → requests
        for c in self._driver.get_cookies():
            self._req.cookies.set(c["name"], c["value"], domain=c.get("domain"))

    # --------------------------------------------------------------------- #
    # public helpers
    # --------------------------------------------------------------------- #
    
    def _get(self, url: str):
        """wrapper with a common timeout + redirects"""
        return self._req.get(url, timeout=30, allow_redirects=True)

    def _bypass_gate(self, html_text: str) -> str | None:
        """
        If we received the ‘direct‑url‑screen’, extract the hidden
        <a href=" … ?switchLocale=y&siteEntryPassthrough=true">Continue</a>
        and give that absolute URL back.
        """
        if not GATE_RE.search(html_text):
            return None
        soup = BeautifulSoup(html_text, "lxml")
        a    = soup.find("a", string=re.compile(r"\bContinue\b", re.I))
        return ROOT_URL + a["href"] if a and a.get("href") else None
    
    def xls_link_from_product_page(self, url: str) -> str:
        """
        Return the direct .xls download link.
        """
        # 1)  make sure we carry the query string BlackRock expects
        if "switchLocale" not in url:
            url = (
                url.rstrip("/")
                + "?switchLocale=y&siteEntryPassthrough=true"
            )

        resp = self._get(url)
        gate = self._bypass_gate(resp.text)
        if gate:
            LOG.debug("By‑passing gate for %s", url.rsplit("/", 1)[-1])
            resp = self._get(gate)

        soup  = BeautifulSoup(resp.text, "lxml")
        links = soup.select("a.icon-xls-export")
        if not links:
            raise RuntimeError(f"No XLS link found on {url}")

        # Prefer the workbook that ends in “…_fund&dataType=fund”
        href = next(
            (a["href"] for a in links if "_fund" in a["href"]),
            links[0]["href"],
        )
        return ROOT_URL + href

    def download_xls(self, xls_url: str, overwrite: bool = False) -> Path:
        """
        Fetch the XLS file behind *xls_url* and cache to disk.
        Returns the file path so downstream code can open it.
        """
        raw_name = xls_url.split("fileName=")[-1].split("&", 1)[0]
        fname    = Path(raw_name).with_suffix(".xls")
        dest  = self.cache_dir / fname

        if dest.exists() and not overwrite:
            LOG.debug("Cache hit – %s", dest.name)
            return dest

        LOG.info("Downloading %s ...", dest.name)
        r = self._req.get(xls_url, timeout=60)
        r.raise_for_status()
        dest.write_bytes(r.content)

        # naive throttling to be polite
        time.sleep(random.uniform(0.5, 1.5))
        return dest

    # --------------------------------------------------------------------- #
    # context‑manager plumbing
    # --------------------------------------------------------------------- #
    def close(self) -> None:
        self._driver.quit()
        self._req.close()

    def __enter__(self):  # noqa: D401
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()