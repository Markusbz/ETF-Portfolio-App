from __future__ import annotations
import datetime as dt, json, os, threading, queue
from pathlib import Path
from typing import Callable
import time

import pandas as pd
from .fund_list import etf_list_getter
from .. import config

_CACHE = config.CACHE_DIR / "universe.parquet"
_CACHE.parent.mkdir(parents=True, exist_ok=True)


def _scrape(headless: bool = True,
            browser_binary_path: str = None,
            chrome_driver_path: str = None) -> pd.DataFrame:
    getter = etf_list_getter(
        browser_binary_path,
        chrome_driver_path
    )
    if not headless:
        getter.options.arguments.remove("--headless=new")
    getter.get_etf_list()

    return getter.fund_data


def load_or_scrape(force: bool = False,
                   on_progress: Callable[[float], None] | None = None,
                    browser_binary_path: str = None,
                    chrome_driver_path: str = None
                   ) -> pd.DataFrame:
    """
    Return a DataFrame with the investment universe.

    * If a cached file exists and is <5 days old → load it.
    * Otherwise scrape with Selenium (updates *on_progress* every ~½ s).
    """
    if _CACHE.exists() and not force:
        age = dt.datetime.now() - dt.datetime.fromtimestamp(_CACHE.stat().st_mtime)
        if age < dt.timedelta(days=5):
            return pd.read_parquet(_CACHE)

    q: queue.Queue[float] = queue.Queue()

    def _worker():
        done = threading.Event()

        def _run_scrape():
            try:
                df = _scrape(headless=True,
                            browser_binary_path=browser_binary_path,
                            chrome_driver_path=chrome_driver_path)
                df.to_parquet(_CACHE, index=False)
                print(f"Saved universe to {_CACHE}")
                q.put(df)
            finally:
                done.set()

        threading.Thread(target=_run_scrape, daemon=True).start()

        i = 0
        #dummy progress
        while not done.is_set():
            q.put(min(i / 60, 0.98))
            time.sleep(0.5)
            i += 1

        q.put(1.0)                              # 100 %


    threading.Thread(target=_worker, daemon=True).start()

    if on_progress is None:                   # blocking mode (tests, CLI)
        while True:
            val = q.get()
            if isinstance(val, pd.DataFrame):
                return val
    else:
        def _poll():
            while not q.empty():
                val = q.get_nowait()
                if isinstance(val, float):
                    on_progress(val)
                else:
                    on_progress(1.0)
                    on_progress(val)
                    return
            on_progress(None)
        return _poll