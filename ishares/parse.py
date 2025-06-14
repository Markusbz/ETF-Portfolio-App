from __future__ import annotations
from pathlib import Path
from typing  import Dict

import pandas as pd
import numpy as np
from lxml    import etree
from .utils import get_logger

LOG = get_logger(__name__)
XML_NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}

# ───────────────────────── low‑level helpers ──────────────────────────────
def _is_xml_workbook(fp: Path) -> bool:
    head = fp.read_bytes()[:512].lstrip().lower()
    return head.startswith(b"<?xml") or head.startswith(b"<?mso-application")

def _clean(txt: str) -> str:
    return " ".join(txt.replace("\xa0", " ").split())

def _xml_rows(ws) -> list[list[str]]:
    """Return every row as list[str] – honour ss:Index gaps when present."""
    rows = []
    for row in ws.xpath("./ss:Table/ss:Row", namespaces=XML_NS):
        out, next_col = [], 1
        for cell in row.xpath("./ss:Cell", namespaces=XML_NS):
            idx = cell.get(f"{{{XML_NS['ss']}}}Index")
            if idx:
                out.extend([""] * (int(idx) - next_col))
                next_col = int(idx)
            text = _clean("".join(cell.xpath(".//text()")))
            out.append(text)
            next_col += 1
        rows.append(out)
    return rows

def _uniquify(names) -> list[str]:
    seen, out = {}, []
    for n in (n if n else "_blank" for n in names):
        if n in seen:
            seen[n] += 1
            n = f"{n}_{seen[n]}"
        else:
            seen[n] = 0
        out.append(n)
    return out

def _maybe_cast(col: pd.Series) -> pd.Series:
    if col.name == "Issuer Ticker":
        for i, ticker in enumerate(col):
            try:
                col[i] = str(int(ticker)).strip()
            except (ValueError, TypeError):
                col[i] = str(ticker).strip()
        return col

    if col.dtype != object:
        return col
    
    c = pd.to_numeric(col.str.replace(",", "", regex=False), errors="coerce")
    if c.notna().any():
        return c

    d = pd.to_datetime(col, format="%d/%b/%Y",
                       errors="coerce", dayfirst=True)
    return d if d.notna().any() else col

# ───────────────────── XML workbook → DataFrames ─────────────────────────
def _find_header_idx(rows: list[list[str]], sheet: str) -> int:
    """
    Heuristic: for ‘historical’/‘performance’ the header is the
    *first* row whose first cell starts with “As Of” (case‑insensitive).
    For everything else we default to the 8‑th row for Holdings, 0 otherwise.
    """
    if sheet in {"historical", "performance"}:
        for i, r in enumerate(rows):
            if r and r[0].strip().lower().startswith("as of"):
                return i
        return 0                                        # fallback
    return 7 if sheet == "holdings" else 0              # old rules

def _xml_to_frames(fp: Path) -> Dict[str, pd.DataFrame]:
    root   = etree.fromstring(fp.read_text(encoding="utf‑8‑sig").encode(),
                              etree.XMLParser(recover=True))
    frames: Dict[str, pd.DataFrame] = {}

    for ws in root.xpath(".//ss:Worksheet", namespaces=XML_NS):
        name  = ws.get(f"{{{XML_NS['ss']}}}Name", "").lower()
        rows  = _xml_rows(ws)
        if not rows:
            continue

        hdr    = _find_header_idx(rows, name)
        df_raw = pd.DataFrame(rows).dropna(how="all", axis=1)

        headers       = _uniquify(df_raw.iloc[hdr])

        tidy          = df_raw.iloc[hdr + 1:].reset_index(drop=True)
        
        tidy.columns  = headers
        tidy          = tidy.apply(_maybe_cast).dropna(how="all", axis=1)
        
        if "As Of" in tidy.columns:
            tidy["As Of"] = pd.to_datetime(tidy["As Of"])
            tidy = tidy.set_index("As Of")

        frames[name]  = tidy

    return frames

# ─────────────────────────── main façade ─────────────────────────────────
class FundSheets:
    """
    Loads the ‘Holdings’, ‘Historical/Performance’, ‘Distributions’ sheets
    into tidy DataFrames with sensible dtypes.
    """

    def __init__(self, xls_path: Path):
        self.xls_path = xls_path

        sheets = (_xml_to_frames(xls_path) if _is_xml_workbook(xls_path)
                  else self._try_biff_then_xml(xls_path))

        self.holdings = self._fix_shifted_names(sheets["holdings"].copy())

        if "historical" in sheets:
            self.historical = sheets["historical"]
            self._calculate_returns(self.historical)

        else:
            self.historical = sheets.get("performance")

        self.distributions = sheets.get("distributions")

    # ---------------- helper utilities ------------------------------------
    @staticmethod
    def _try_biff_then_xml(fp: Path) -> Dict[str, pd.DataFrame]:
        try:
            xls = pd.ExcelFile(fp, engine="xlrd")
            return {s.lower(): xls.parse(s) for s in xls.sheet_names}
        except Exception:
            return _xml_to_frames(fp)

    @staticmethod
    def _fix_shifted_names(df: pd.DataFrame) -> pd.DataFrame:

        if "Issuer Ticker" in df.columns:
            def _fmt(x):
                if pd.isna(x):
                    return pd.NA

                if isinstance(x, (int, float)):
                    return str(int(x))
                return str(x).strip()

            df["Issuer Ticker"] = df["Issuer Ticker"].map(_fmt)

        return df
    
    @staticmethod
    def _calculate_returns(df: pd.DataFrame) -> None:
        df.sort_index(ascending=False, inplace=True)
        if "Fund Return Series" in df.columns:
            return_series = df["Fund Return Series"]/df["Fund Return Series"].shift(-1)
            df["Return"] = return_series - 1
            df["Log Return"] = np.log(return_series)

        elif "Share Class Return Series" in df.columns:
            return_series = df["Share Class Return Series"]/df["Share Class Return Series"].shift(-1)
            df["Return"] = return_series - 1
            df["Log Return"] = np.log(return_series)
        else:
            if "Ex-Dividends" in df.columns:
                df["Ex-Dividends"].fillna(0, inplace=True)
                return_series = (df["NAV"]+df["Ex-Dividends"])/df["NAV"].shift(-1)
                df["Return"] = return_series - 1
                df["Log Return"] = np.log(return_series)
            else:
                return_series = df["NAV"]/df["NAV"].shift(-1)
                df["Return"] = return_series - 1
                df["Log Return"] = np.log(return_series)

    @property
    def ticker(self) -> str:
        return self.xls_path.stem.split("_")[0].split("-")[-1].upper()

    def __repr__(self):
        return f"<FundSheets {self.ticker} — {self.xls_path.name}>"
    
