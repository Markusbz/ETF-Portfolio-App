# ETF Portfolio Constructor & Analyzer 📈

This is an API-key free app to monitor your ETF Portfolio. There are quite a few services out there that provide very good solutions for managing and analyzing ETF-Portfolios which usually cost money and/or are not very flexible, or require you to set up multiple accounts to get API-keys. So I built my own! 😊

For now, only iShares is supported. I will try to add additional ETF-Providers later on!

![The app after starting it up.](https://i.imgur.com/rRsgqfw.png)

---

## 🚀 Key Features

- **Fund Universe Scraper**: Scrapes and parses the full list of all iShares ETFs, including currency, hedging, and distribution policy.
- **Portfolio Construction**: An interface to search, filter, and add ETFs to your portfolio, either by percentage weight or number of shares.
- **Detailed Data Aggregation**: Downloads detailed fund data, including historical performance and full holdings, directly from the fund provider. Returns are parsed, adjusted for distributions, and handled for potential currency conversions.
- **Consolidated Holdings View**: Aggregates the underlying holdings of all ETFs in your portfolio to give you a true picture of your exposure to individual securities and sectors.
- **Advanced Backtesting Engine**:
    - Tests your portfolio's performance over historical periods.
    - Supports various rebalancing strategies (daily, weekly, monthly, none, etc.).
    - Calculates key performance metrics like total return, annualized standard deviation, and Sharpe ratio for multiple time windows.
- **Sharpe Ratio Optimization**: Implements the SLSQP (Sequential Least Squares Programming) optimization algorithm to find the optimal portfolio weights that maximize the Sharpe ratio (no leverage, no shorting).
- **Performance Comparison**: Provides a clear, side-by-side comparison of your original portfolio's performance against the optimized version, including a visual chart of their cumulative returns.

---

## 🛠️ How to Use

### 1. Edit the Config File
Using the app requires a Chromium-based browser (I recommend [Brave](https://brave.com/)) and a corresponding ChromeDriver. You can find stable versions here: [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/).

Before starting, adjust the paths to your browser executable and the ChromeDriver in the `config.py` file. You can also specify different data directories if you wish.

```python
# In config.py
BRAVE_BROWSER_PATH = r"C:\Path\To\Your\Browser\Application\brave.exe"
CHROMEDRIVER_PATH = r"C:\Path\To\Your\ChromeDriver\chromedriver.exe"
```

### 2. Building a Portfolio
Launch the app:
```python
from etf_portfolio_app.ui.portfolio_app import FundSelectorApp

if __name__ == "__main__":
    FundSelectorApp().mainloop()
```

- **Select Portfolio Currency**: At the top left of the window, choose the base currency for your portfolio analysis.
- **Find ETFs**: On the "Portfolio Builder" tab, use the search bar and provider dropdown to find ETFs. You can search by name or ticker.
- **Add to Portfolio**:
    1. Select an ETF from the list on the left.
    2. Choose its specific currency, hedging, and distribution type from the middle panel.
    3. Select whether to add it by "percent" or "shares".
    4. Click "Add to Portfolio" and enter the desired amount. The fund will appear in the portfolio list on the right.

![Searching and selecting MSCI World ETF.](https://i.imgur.com/EjaZBAV.png)

- **Save Your Portfolio**: Once you've added all your funds, click "Save Portfolio" to save your selections to a `.csv` file. You can load it later using the "Load Portfolio" button.

### 3. Downloading Data

- **Navigate to Data Center**: Go to the "Data Center" tab.
- **Download Data**: Click "Download Portfolio Fund Data". The app will fetch the detailed historical performance and holdings for every ETF in your current portfolio. This may take a few minutes.
- **Save/Load Data**: You can save the downloaded data to a local folder for offline access and faster loading in the future.

![Overview of data download.](https://i.imgur.com/rw7G2FG.png)

### 4. Analyzing and Optimizing

- **Navigate to Dashboard**: Go to the "Portfolio Dashboard" tab.
- **Refresh Data**: Click "Refresh Dashboard Data" to see your consolidated holdings and total portfolio value.

![Consolidated Top Holdings.](https://i.imgur.com/ZpRDLEq.png)

- **Run Backtest & Optimization**:
    1. In the "Performance Backtest & Optimization" section, select your desired rebalancing frequency.
    2. Click "Run Backtest & Optimize".
    3. The application will calculate and display a side-by-side comparison of your original portfolio's performance versus the new, Sharpe-ratio-optimized portfolio.

![Backtesting overview.](https://i.imgur.com/YgqSqs1.png)

A new browser window will open with an interactive chart comparing the cumulative returns of both portfolios.

![Backtesting graph.](https://i.imgur.com/EzaBTHy.png)

---

Thanks for stopping by, I hope it is useful! ☺️
