# NSE India Stock Info Fetcher

This script fetches live data for the **NIFTY 500** list from the National Stock Exchange (NSE) and allows for historical performance comparisons using the official daily **Bhavcopy** reports.

## Prerequisites

Ensure you are using the project's virtual environment:
```powershell
.\venv\Scripts\python nse_stock_info.py [options]
```

## How to Run the Script

Because this project uses a Virtual Environment (`venv`) to keep its dependencies (like `pandas` and `nsepython`) isolated, you should run the script using the Python executable located inside the `venv` folder.

### On Windows (PowerShell/CMD):
Always prefix your command with `.\venv\Scripts\python`. 

**Example Live Snapshot:**
```powershell
.\venv\Scripts\python nse_stock_info.py
```

---

## Usage & Options

### 1. Live Snapshot (Default)
To see current live prices without any comparison, run:
```powershell
.\venv\Scripts\python nse_stock_info.py
```

### 2. Historical Comparison (`-c` or `--compare`)
Use the `-c` flag followed by a timeframe or a specific date. The script will find the closest valid trading day and compare the current price against the closing price of that day.

#### Predefined Timeframes:
| Command | Description |
| :--- | :--- |
| `-c 1d` | Compare against 1 day ago |
| `-c 1w` | Compare against 1 week ago |
| `-c 2w` | Compare against 2 weeks ago |
| `-c 1m` | Compare against 1 month ago |
| `-c 6m` | Compare against 6 months ago |
| `-c ytd` | Compare against Year-To-Date (Jan 1st) |
| `-c 1y` | Compare against 1 year ago |

**Example (1 month ago):**
```powershell
.\venv\Scripts\python nse_stock_info.py -c 1m
```

#### Custom Date:
You can provide any specific date in `YYYY-MM-DD` format. If the market was closed on that date, the script will automatically search backwards to find the most recent trading day.
```powershell
.\venv\Scripts\python nse_stock_info.py -c 2024-01-15
```

### 3. Export to CSV (`--csv`)
To save the full 500-stock report to a file, add the `--csv` flag. This will generate a file named `nse_output.csv`.
```powershell
.\venv\Scripts\python nse_stock_info.py -c 1w --csv
```

> [!IMPORTANT]
> **Windows Permission Note:** If `nse_output.csv` is currently open in Excel or another program, the script will fail with an error because it cannot overwrite the file. Close the CSV file before running the script with the `--csv` flag.

## How the Comparison Works
1. **Live Data**: Fetches the current live price for all 500 stocks.
2. **Historical Data**: Downloads the **Bhavcopy** (Daily Price List) for your target date.
3. **Smart Fallback**: If a stock didn't trade on your specific target date (e.g., it was halted), the script automatically searches older records *just for that specific stock* until it finds its last valid closing price.
4. **Result**: Calculates the `Change %` between the two points.
