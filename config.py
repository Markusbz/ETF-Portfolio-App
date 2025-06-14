import os
from pathlib import Path

# -----------------------------------------------------------------------------
# CORE APPLICATION CONFIGURATION
# -----------------------------------------------------------------------------

# --- Browser & Driver Paths ---
# Please ensure these paths point to your actual browser executable and the
# corresponding WebDriver executable.
BRAVE_BROWSER_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
CHROMEDRIVER_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\chromedriver.exe"

# --- Data & Caching Directories ---
# The base directory for all application data, caches, and saved files.
# Defaults to a 'data' folder in the current working directory.
DATA_DIR = Path(os.getenv("PORTFOLIO_APP_DATA", "./data")).expanduser()

# Specific subdirectories for raw downloads and cached data.
RAW_DATA_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
TEMP_DIR = DATA_DIR / "temp" # For temporary files like HTML charts

# Create these directories when the config is loaded to ensure they exist.
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)


# --- Fund Provider Prefixes ---
# Used to correctly parse the fund name from its full name string.
PROVIDER_PREFIXES = {
    "ishares", "vanguard", "spdr", "xtrackers", "lyxor",
    "invesco", "ubs", "amundi", "wisdomtree",
}
FUND_LIST_UPDATE_PERIOD = "6m"

# --- Dashboard Settings ---
# Number of top holdings to display in the dashboard table.
TOP_N_HOLDINGS = 200

print(f"Config loaded. Data directory set to: {DATA_DIR.resolve()}")
