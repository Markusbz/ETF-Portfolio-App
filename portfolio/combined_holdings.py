import pandas as pd
import numpy as np

def _calculate_portfolio_weights(portfolio: pd.DataFrame, detailed_fund_data: dict) -> dict:
    if "shares" in portfolio.columns:
        abs_value_dict = {
            ticker: detailed_fund_data[ticker]["historical"].iloc[0]["NAV"] *
            portfolio.loc[portfolio["ticker"] == ticker, "shares"].values[0]
            for ticker in portfolio["ticker"]
        }
        total = sum(abs_value_dict.values())
        relative_value_dict = { ticker: abs_value_dict[ticker]/total for ticker in abs_value_dict.keys() }

    else:
        relative_value_dict = dict()
        for row in portfolio.index:
            relative_value_dict[portfolio.iloc[row]["ticker"]] = portfolio.iloc[row]["weight"]/100

    return relative_value_dict

def calculate_combined_holdings(portfolio: pd.DataFrame, detailed_fund_data: dict) -> pd.DataFrame:
    """
    Calculate combined holdings for a portfolio based on detailed fund data.
    
    Args:
        portfolio (pd.DataFrame): DataFrame containing the portfolio holdings.
        detailed_fund_data (dict): Dictionary containing detailed fund data with keys as fund tickers.
        
    Returns:
        pd.DataFrame: DataFrame with combined holdings.
    """
    combined_holdings = pd.DataFrame()
    weights = _calculate_portfolio_weights(portfolio, detailed_fund_data)
    for ticker in detailed_fund_data.keys():
        try:
            ticker_data = detailed_fund_data[ticker]["holdings"][["Issuer Ticker", "Name", "Sector", "Weight (%)"]]
            ticker_data.rename(columns={"Weight (%)": "Weight"}, inplace=True)
            print(ticker_data)
            ticker_data["Weight"] *= weights[ticker]
            combined_holdings = pd.concat( [
                combined_holdings,
                ticker_data
                ], ignore_index=True)
            
        except KeyError as e:

            print(f"KeyError for ticker {ticker}: {e}")
            continue

    combined_holdings = combined_holdings.groupby(
        ["Issuer Ticker", "Sector"], as_index=False).agg({"Weight": "sum", "Name": "first"})
    
    result_df = combined_holdings.sort_values(
        by=["Weight"], ascending=False, inplace=False)
    print(f"Type of result_df in calculate_combined_holdings: {type(result_df)}") # DEBUG
    print(result_df.head() if not result_df.empty else "Result_df is empty") # DEBUG
    return result_df
    