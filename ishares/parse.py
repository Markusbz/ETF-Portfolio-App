from __future__ import annotations
from pathlib import Path
from typing import Dict
import csv
import os

import pandas as pd
import numpy as np
from lxml import etree
from ..portfolio.currency_fetcher import fetch_currency_data
from .. import config
from .utils import get_logger

LOG = get_logger(__name__)
XML_NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
HOLDINGS_SKIPROWS = 7
PARSE_SHEET_NAMES = ["holdings", "historical", "distributions"]

# ------------------------- Main Façade -------------------------------------

class FundSheets:
    """
    Loads data from iShares' XML-based .xls files by converting worksheets to 
    temporary CSVs and then parsing them with pandas.
    """
    def __init__(self, xls_path: Path, fund_currency: str, portfolio_currency: str):
        self.xls_path = xls_path
        self.portfolio_currency = portfolio_currency
        self.fund_currency = fund_currency
        self.holdings: pd.DataFrame | None = None
        self.historical: pd.DataFrame | None = None
        self.distributions: pd.DataFrame | None = None
        self._parse_xls(xls_path)
        

    def _parse_xls(self, xls_path: Path):
        """Parses the XLS file and extracts data from its worksheets."""
        if not xls_path.exists():
            LOG.error(f"File {xls_path} does not exist.")
            return
        
        root = etree.fromstring(xls_path.read_text(encoding="utf‑8‑sig").encode(),
                              etree.XMLParser(recover=True))
        for ws in root.xpath(".//ss:Worksheet", namespaces=XML_NS):
            name = ws.get(f"{{{XML_NS['ss']}}}Name", "").lower()
            if name in PARSE_SHEET_NAMES:
                csv_path = xls_path.with_suffix('.csv')

                # Find all the <Row> elements within the worksheet's <Table>
                rows = ws.xpath("./ss:Table/ss:Row", namespaces=XML_NS)

                # Open the output file in write mode
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    csv_writer = csv.writer(f)
                    
                    # Iterate over each row element
                    for row_elem in rows:
                        row_data = []
                        # Find all <Cell> elements within the current row
                        cells = row_elem.xpath("./ss:Cell", namespaces=XML_NS)
                        
                        # Extract the text from the <Data> element of each cell
                        for cell_elem in cells:
                            # Use .// to find the <Data> tag, which may be nested
                            data_elements = cell_elem.xpath(".//ss:Data", namespaces=XML_NS)
                            if data_elements and data_elements[0].text is not None:
                                row_data.append(data_elements[0].text.strip())
                            else:
                                # Append an empty string for empty cells
                                row_data.append("")
                        
                        # Write the collected row data to the CSV file
                        csv_writer.writerow(row_data)

                if name == "holdings":
                    self.holdings = pd.read_csv(csv_path, skiprows=HOLDINGS_SKIPROWS, encoding="utf-8-sig")
                else:
                    if name == "historical":
                        self.historical = pd.read_csv(csv_path, encoding="utf-8-sig")
                        self.historical["As Of"] = self.historical["As Of"].str.replace("Sept", "Sep", case=False)
                        self.historical.columns = [str(c).strip() for c in self.historical.columns]

                        if "As Of" in self.historical.columns:
                            self.historical["As Of"] = pd.to_datetime(self.historical["As Of"], format="%d/%b/%Y", errors="coerce")
                    
                        for col in self.historical.columns:
                            if col not in ["As Of", "Currency"]:
                                self.historical[col] = pd.to_numeric(self.historical[col], errors='coerce')
                        
                        self.historical.rename(columns={"As Of": "date", "Currency":"currency"}, inplace=True)
                        self.historical.set_index("date", inplace=True)

                        self.historical = self.historical.join( fetch_currency_data(
                            fund_currency = self.fund_currency, 
                            portfolio_currency = self.portfolio_currency, 
                            start_date = min(self.historical.index), 
                            end_date = max(self.historical.index ) ) )
                        self.historical['fx_rate'].ffill(inplace=True)
                        self._calculate_returns(self.historical)
                        
                    elif name == "distributions":
                        self.distributions = pd.read_csv(csv_path, encoding="utf-8-sig")
                        self.distributions.columns = [str(c).strip() for c in self.distributions.columns]

                        date_cols = ["Record Date", "Ex-Date", "Payable Date"]
                        for col in date_cols:
                            if col in self.distributions.columns:
                                # Replace "Sept" with "Sep" before conversion
                                self.distributions[col] = self.distributions[col].str.replace("Sept", "Sep", case=False)
                                self.distributions[col] = pd.to_datetime(self.distributions[col], format="%d/%b/%Y", errors="coerce")

        os.remove(csv_path)

    @staticmethod
    def _calculate_returns(df: pd.DataFrame) -> None:
        if df is None or df.empty: return
        df.sort_index(ascending=False, inplace=True)
        
        fallback_return_series = None
        if "NAV" in df.columns:
            nav_series = df["NAV"]
            if "Ex-Dividends" in df.columns:
                ex_div = pd.to_numeric(df["Ex-Dividends"], errors='coerce').fillna(0)
                fallback_return_series = (nav_series + ex_div) / nav_series.shift(-1)
            else:
                fallback_return_series = nav_series / nav_series.shift(-1)
        
        primary_return_series = None
        if "Fund Return Series" in df.columns:
            primary_return_series = df["Fund Return Series"] / df["Fund Return Series"].shift(-1)
        elif "Share Class Return Series" in df.columns:
            primary_return_series = df["Share Class Return Series"] / df["Share Class Return Series"].shift(-1)

        final_return_series = None
        if primary_return_series is not None:
            final_return_series = primary_return_series.fillna(fallback_return_series)
        elif fallback_return_series is not None:
            final_return_series = fallback_return_series
        
        if final_return_series is not None:
            df["Return"] = final_return_series - 1
            df["Log Return"] = np.log(final_return_series)
            
            # --- Add CCY Adjusted Returns ---
            if 'fx_rate' in df.columns:
                fx_return_series = df['fx_rate'] / df['fx_rate'].shift(-1)
                ccy_adj_return_series = final_return_series * fx_return_series
                df['ccy_adj_return'] = ccy_adj_return_series - 1
                df['ccy_adj_log_return'] = np.log(ccy_adj_return_series)
            else:
                # If no fx_rate, ccy adjusted returns are the same as local returns
                df['ccy_adj_return'] = df['Return']
                df['ccy_adj_log_return'] = df['Log Return']
        else:
            LOG.warning("No valid columns found to calculate returns.")
            df["Return"] = np.nan
            df["Log Return"] = np.nan
            df['ccy_adj_return'] = np.nan
            df['ccy_adj_log_return'] = np.nan

        df.replace([np.inf, -np.inf], 0, inplace=True)