import pandas as pd
import numpy as np
import requests
import datetime
import pandas_datareader.data as web
import xml.etree.ElementTree as ET

class PortfolioBackteser:
    def __init__(self, portfolio_weights: pd.Series, asset_returns: pd.DataFrame, rebalancing_period: str, portfolio_currency: str):
        self.portfolio_weights = portfolio_weights
        self.asset_returns = asset_returns
        self.rebalancing_period = rebalancing_period
        self.portfolio_currency = portfolio_currency
        self.risk_free_rate = (self.get_risk_free_rate(currency=portfolio_currency, maturity='overnight') or 0.0) / 100.0
        self.portfolio_return_series = self.calculate_portfolio_return_timeseries()

    def calculate_portfolio_return_timeseries(self) -> pd.Series:
        """
        Calculate the portfolio return time series based on the portfolio weights and asset returns.
        """
        returns_np = self.asset_returns.to_numpy()
        weights_np = self.portfolio_weights.to_numpy()
        n_days, n_assets = returns_np.shape

        if self.rebalancing_period == "d":
            portfolio_return = self.portfolio_weights.dot(self.asset_returns.T)
            return portfolio_return

        period_markers_map = {
            'w': self.asset_returns.index.isocalendar().week,
            'bw': (self.asset_returns.index - self.asset_returns.index[0]).days // 14,
            'm': self.asset_returns.index.month,
            'q': self.asset_returns.index.quarter,
            'sa': (self.asset_returns.index.month - 1) // 6,
            'y': self.asset_returns.index.year
        }
        if self.rebalancing_period not in period_markers_map:
            raise ValueError("rebalancing_period must be one of 'w', 'bw', 'm', 'q', 'sa', 'y'")
        
        period_markers = period_markers_map[self.rebalancing_period].to_numpy()
        
        portfolio_returns_np = np.empty(n_days)
        current_weights_np = np.copy(weights_np)
        
        for i in range(n_days):
            day_return = np.sum(current_weights_np * returns_np[i])
            portfolio_returns_np[i] = day_return

            if i < n_days - 1:
                if period_markers[i+1] != period_markers[i]:
                    current_weights_np = np.copy(weights_np)
                else:
                    new_values = current_weights_np * (1 + returns_np[i])
                    total_value = np.sum(new_values)
                    if total_value != 0:
                        current_weights_np = new_values / total_value

        return pd.Series(portfolio_returns_np, index=self.asset_returns.index)

    def _calculate_period_stats(self, returns_period: pd.Series) -> dict:
        """Helper to calculate stats for a given period of returns."""
        if returns_period.empty or len(returns_period) < 2:
            return {'return': np.nan, 'std_dev': np.nan, 'sharpe': np.nan}

        total_return = (1 + returns_period).prod() - 1

        annualized_std = returns_period.std() * np.sqrt(252)

        num_years = len(returns_period) / 252.0
        annualized_return = ((1 + total_return) ** (1 / num_years)) - 1 if num_years > 1 else total_return

        adj_rf = (self.risk_free_rate + 1) ** 1/ num_years - 1 if num_years > 1 else self.risk_free_rate
        excess_return = annualized_return - adj_rf
        sharpe_ratio = excess_return / annualized_std if annualized_std > 0 else np.nan
        
        return {
            'return': total_return,
            'std_dev': annualized_std,
            'sharpe': sharpe_ratio
        }

    def calculate_statistics(self) -> dict:
        """Calculates performance statistics for various time windows."""
        stats = {}
        # Sort chronologically for calculations
        returns = self.portfolio_return_series.sort_index(ascending=True)
        first_date = returns.index.min()
        end_date = returns.index.max()

        # Define periods using pandas DateOffset for accurate calendar math
        periods = {
            "30 Days": pd.DateOffset(days=30),
            "3 Months": pd.DateOffset(months=3),
            "6 Months": pd.DateOffset(months=6),
            "1 Year": pd.DateOffset(years=1),
            "2 Years": pd.DateOffset(years=2),
            "3 Years": pd.DateOffset(years=3),
            "5 Years": pd.DateOffset(years=5),
            "7 Years": pd.DateOffset(years=7),
            "10 Years": pd.DateOffset(years=10),
        }

        for name, offset in periods.items():
            start_date = end_date - offset
            if start_date < first_date:
                stats[name] = {'return': np.nan, 'std_dev': np.nan, 'sharpe': np.nan}
                continue
            period_returns = returns[start_date:]
            if not period_returns.empty:
                stats[name] = self._calculate_period_stats(period_returns)
            else:
                stats[name] = {'return': np.nan, 'std_dev': np.nan, 'sharpe': np.nan}
        
        first_date_str = datetime.datetime.strftime(first_date, "%d-%m-%Y")
        end_date_str = datetime.datetime.strftime(end_date, "%d-%m-%Y")
        stats[f"Since Inception ({first_date_str} - {end_date_str})"] = self._calculate_period_stats(returns)
        
        return stats

    def get_snb_rate_from_rss(self, rate_name='SARON'):
        url = "https://www.snb.ch/public/en/rss/interestRates"
        try:
            response = requests.get(url); response.raise_for_status(); root = ET.fromstring(response.content)
            namespaces = {'cb': 'http://www.cbwiki.net/wiki/index.php/Specification_1.2/'}
            for item in root.findall('.//item'):
                if item.find(f'cb:statistics/cb:interestRate/cb:rateName', namespaces).text == rate_name:
                    value_str = item.find(f'cb:statistics/cb:interestRate/cb:observation/cb:value', namespaces).text
                    return float(value_str)
            return None
        except Exception as e:
            print(f"Error with SNB RSS feed: {e}"); return None

    def get_risk_free_rate(self, currency='USD', maturity='overnight'):
        if currency == 'CHF': return self.get_snb_rate_from_rss()
        fred_series_map = {
            'USD': {'overnight': 'DFF'}, 'EUR': {'overnight': 'ECBESTRVOL'},
            'GBP': {'overnight': 'IUDSOIA'}, 'JPY': {'overnight': 'IRSTCI01JPM156N'},
            'SGD': {'overnight': 'IRSTCI01SGM156N'},
        }
        if currency in fred_series_map and maturity in fred_series_map[currency]:
            series_id = fred_series_map[currency][maturity]
            try:
                end_date = datetime.date.today(); start_date = end_date - datetime.timedelta(days=365)
                rate_data = web.DataReader(series_id, 'fred', start_date, end_date)
                return rate_data[series_id].ffill().iloc[-1]
            except Exception as e:
                print(f"Could not retrieve data for {currency} from FRED: {e}"); return None
        else:
            print(f"Rate for {currency} with maturity '{maturity}' is not available."); return None