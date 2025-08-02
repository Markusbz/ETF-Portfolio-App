import yfinance as yf
from datetime import timedelta
import pandas as pd
import numpy as np

def fetch_currency_data(fund_currency: str, portfolio_currency: str, start_date: str, end_date: str) -> yf.Ticker:
    """
    Fetch currency data for the specified fund and portfolio currencies.

    Args:
        fund_curremcy (str): The currency of the fund.
        portfolio_currency (str): The currency of the portfolio.
        start_date (str): The start date for fetching data.
        end_date (str): The end date for fetching data.

    Returns:
        yf.Ticker: A yfinance Ticker object containing the currency data.
    """
    if fund_currency == portfolio_currency:
        date_range = pd.date_range(start=start_date, end=end_date, freq="D").tz_localize(None)
        return pd.DataFrame(np.zeros(len(date_range))+1, index=date_range, columns=["fx_rate"])

    ticker_symbol = f"{fund_currency}{portfolio_currency}=X"
    ticker = yf.Ticker(ticker_symbol)
    ticker_data = ticker.history(start=start_date-timedelta(days=1), end=end_date+timedelta(days=1), interval="1d")

    if ticker_data.empty:
        raise ValueError(f"No data found for {ticker_symbol} between {start_date} and {end_date}")
    
    ticker_data.rename(columns={"Close": "fx_rate"}, inplace=True)
    ticker_data.index = ticker_data.index.tz_localize(None)

    return ticker_data["fx_rate"]