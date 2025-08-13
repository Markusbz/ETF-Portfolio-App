ETF Portfolio Constructor & Analyzer
This is an API-key free app to monitor your ETF-Portfolio. There are quite a few services out there that provide very good solutions for managing and analyzing ETF-Portfolios which usually cost money and/or are not very flexible, or require you to set up multiple accounts to get API-keys. So I built my own! 😊

For now only iShares is supported. I will try to add additional ETF-Providers later on!

[The app after starting it up.](https://i.imgur.com/rRsgqfw.png)

Key Features
Fund Universe Scraper: Scrapes and parses the full list of all iShares ETFs, including currency, hedging and distribution policy

Portfolio Construction: An interface to search, filter, and add ETFs to your portfolio, either by percentage weight or number of shares.

Detailed Data Aggregation: Downloads detailed fund data, including historical performance and full holdings, directly from the fund provider, returns are parsed, adjusted for distributions and potential currency conversions.

Consolidated Holdings View: Aggregates the underlying holdings of all ETFs in your portfolio to give you a true picture of your exposure to individual securities and sectors.

Advanced Backtesting Engine:

Tests your portfolio's performance over historical periods.

Supports various rebalancing strategies (daily, weekly, monthly, none, etc.).

Calculates key performance metrics like total return, annualized standard deviation, and Sharpe ratio for multiple time windows.

Sharpe Ratio Optimization: Implements the SLSQP (Sequential Least Squares Programming) optimization algorithm to find the optimal portfolio weights that maximize the Sharpe ratio (no leverage, no shorting, can be adjusted/changed in code).

Performance Comparison: Provides a clear, side-by-side comparison of your original portfolio's performance against the optimized version, including a visual chart of their cumulative returns.

How to Use
1. Edit the config file
Using the app will require a chromium based browser (I recommend [Brave](https://brave.com/)) and a chromedriver, which for your browser version (stable versions can be found here: https://googlechromelabs.github.io/chrome-for-testing/). Adjust the path to your browser executable and the chromedriver in the config, before starting the app. Also specify data directories if you wish.

```python
# In config.py
BRAVE_BROWSER_PATH = r"C:\Path\To\Your\Browser\Application\brave.exe"
CHROMEDRIVER_PATH = r"C:\Path\To\Your\ChromeDriver\chromedriver.exe"
```


2. Building a Portfolio
Launch the App: Run the main application file.
```python
from etf_portfolio_app.ui.portfolio_app import FundSelectorApp

if __name__ == "__main__":
    FundSelectorApp().mainloop()
```

At the first start-up

Select Portfolio Currency: At the top left of the window, choose the base currency for your portfolio analysis.

Find ETFs: On the "Portfolio Builder" tab, use the search bar and provider dropdown to find the ETFs you're interested in (searching for names and tickers both work, after selecting, use dynamic dropdowns for hedging and distribution policy).

Add to Portfolio:

Select an ETF from the list on the left.

Choose its specific currency and distribution type from the middle panel.

Select whether you want to add it by "percent" or "shares".

[Searching and selecting MSCI World ETF.](https://i.imgur.com/EjaZBAV.png)

Click "Add to Portfolio" and enter the desired amount.

The fund will appear in the portfolio list on the right.

Save Your Portfolio: Once you've added all your funds, click "Save Portfolio" to save your selections to a .csv file. You can load it later using the "Load Portfolio" button.

3. Downloading Data
Navigate to Data Center: Go to the "Data Center" tab.

Download Data: Click the "Download Portfolio Fund Data" button. The app will fetch the detailed historical performance and holdings for every ETF in your current portfolio. This may take a few minutes.

Save/Load Data: You can save the downloaded data to a local folder for offline access and faster loading in the future (the loaded data should include the positions that are currently loaded in on the portfolio builder tab).

[Overview of data download.](https://i.imgur.com/rw7G2FG.png)

4. Analyzing and Optimizing
Navigate to Dashboard: Go to the "Portfolio Dashboard" tab.

Refresh Data: Click "Refresh Dashboard Data" to see your consolidated holdings and total portfolio value.

[Consolidated Top Holdings.](https://i.imgur.com/ZpRDLEq.png)

Run Backtest & Optimization:

In the "Performance Backtest & Optimization" section, select your desired rebalancing frequency from the dropdown.

Click "Run Backtest & Optimize".

The application will calculate and display a side-by-side comparison of your original portfolio's performance versus the new, Sharpe-ratio-optimized portfolio (Standard deviation and sharpe are calculated is annualized).

[Backtesting overview.](https://i.imgur.com/YgqSqs1.png)

A new browser window will open with an interactive chart comparing the cumulative returns of both portfolios.

[Backtesting graph.](https://i.imgur.com/EzaBTHy.png)

Thanks for stopping by, I hope it is useful! ☺️