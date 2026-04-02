# NSE India Stock Performance Tool

This script fetches live data for the **NIFTY 500** index from the National Stock Exchange (NSE) and compares historical stock performance using the official daily **Bhavcopy** reports. It runs entirely through an interactive terminal — no command-line arguments needed.

---

## Prerequisites

- **Python 3.8+**
- A virtual environment (`venv`) is recommended to keep dependencies isolated.

### Setting Up the Virtual Environment

```powershell
# Create the virtual environment (one-time setup)
python -m venv venv

# Activate it
.\venv\Scripts\Activate

# Install dependencies
.\venv\Scripts\pip install -r requirements.txt
```

### Dependencies (requirements.txt)

| Library       | Purpose                                    |
|---------------|--------------------------------------------|
| `requests`    | HTTP session management for NSE API        |
| `pandas`      | Data manipulation, merging, and CSV export |
| `nsepython`   | Downloading daily Bhavcopy files from NSE  |

---

## How to Run

```powershell
.\venv\Scripts\python nse_stock_info.py
```

The script will guide you through two interactive prompts:

### Step 1: Choose the End Date

You'll be asked which day to use as the **end point** of your comparison.

```
What day do you want to do the comparison?
1. Present day (2026-04-02)
2. Custom date
Choose option (1-2):
```

| Option         | What it does                                            |
|----------------|---------------------------------------------------------|
| **1 (Present)**| Uses today's live snapshot prices from NSE              |
| **2 (Custom)** | You enter a specific date in `YYYY-MM-DD` format        |

### Step 2: Choose the Start Date (Comparison Period)

Next, choose how far back to compare:

```
How do you want to compare?
1. Days
2. Weeks
3. Months
4. Years
5. YTD
6. Custom date
Choose option (1-6):
```

| Option        | What happens next                                                |
|---------------|------------------------------------------------------------------|
| **1. Days**   | Asks: *"How many Days ago?"* — enter a number (e.g., `5`)       |
| **2. Weeks**  | Asks: *"How many Weeks ago?"* — enter a number (e.g., `2`)      |
| **3. Months** | Asks: *"How many Months ago?"* — enter a number (e.g., `6`)     |
| **4. Years**  | Asks: *"How many Years ago?"* — enter a number (e.g., `1`)      |
| **5. YTD**    | Automatically compares against January 1st of the end date year |
| **6. Custom** | You enter a specific start date in `YYYY-MM-DD` format          |

### Example Session

```
=== NSE India Stock Performance Tool ===

What day do you want to do the comparison?
1. Present day (2026-04-02)
2. Custom date
Choose option (1-2): 1

How do you want to compare?
1. Days
2. Weeks
3. Months
4. Years
5. YTD
6. Custom date
Choose option (1-6): 4
Enter how many Years ago you want to compare to 2026-04-02: 1

Comparing 2025-04-02 vs 2026-04-02...
```

---

## Output

### Terminal

The top 20 stocks by performance are printed to the terminal:

```
--- PERFORMANCE SUMMARY (Top 20) ---
Name                          Code       Start_Price  End_Price  Change_%
                    NIFTY 500  NIFTY 500      NaN     20968.95      NaN
  GE Vernova T&D India Limited    GVT&D   1496.10     3832.20   156.15
  ...
```

### CSV Export (`nse_output.csv`)

A full report of all 500+ stocks is **automatically** saved to `nse_output.csv` on every run.

#### CSV Columns

| Column              | Description                                                         |
|---------------------|---------------------------------------------------------------------|
| **Name**            | Company name                                                        |
| **Code**            | NSE trading symbol                                                  |
| **Open**            | Today's opening price (from live snapshot)                           |
| **High**            | Today's high price                                                  |
| **Low**             | Today's low price                                                   |
| **Prev_Close**      | Previous day's closing price                                        |
| **No_of_Trades**    | Total number of trades (volume)                                     |
| **Turnover**        | Total traded value in ₹                                             |
| **Industry**        | Sector/industry classification                                      |
| **End_Price**       | Closing price on the chosen End Date                                |
| **End_Date_Actual** | The actual date used for the end price (may differ on weekends)     |
| **Start_Price**     | Closing price on the chosen Start Date                              |
| **Start_Date_Actual** | The actual date used for the start price (may differ on weekends) |
| **Change_%**        | Percentage change from Start to End price                           |
| **Alert**           | Notes on date fallbacks, missing data, or backfilling               |

### Sort Order

The output (both terminal and CSV) is sorted in this order:

1. **NIFTY 500 index** — Always pinned as the first row for an overall market summary.
2. **By Change_% (descending)** — Biggest gainers at the top.
3. **By End_Price (descending)** — Stocks with no Change_% but a valid End Price.
4. **Alphabetically by Name** — Stocks with no price data at all appear last.

---

## How the Comparison Works

1. **Live Snapshot**: Fetches the current live data (Open, High, Low, Close, Volume, etc.) for all Nifty 500 stocks from the NSE API.
2. **Bhavcopy Lookup**: Downloads the official **Bhavcopy** (daily price report) for both your Start Date and End Date.
3. **Smart Fallback (up to 30 days)**: If the market was closed on a chosen date (weekend, holiday), the script automatically searches **up to 30 days backwards** to find the nearest valid trading day.
4. **Per-Stock Backfill**: If a specific stock wasn't traded on a given day (e.g., suspended, newly listed), the script individually searches older Bhavcopies for just that stock and records the actual date used.
5. **Calculation**: Computes `Change_%` between Start Price and End Price.

---

## Alert Column Meanings

| Alert Message                                     | Meaning                                                    |
|---------------------------------------------------|------------------------------------------------------------|
| `Target was YYYY-MM-DD, but used YYYY-MM-DD`      | The requested date was a non-trading day; nearest date used |
| `Start price from YYYY-MM-DD`                     | This stock's start price came from an individually older date |
| `End price from YYYY-MM-DD`                       | This stock's end price came from an individually older date |
| `No start data (likely not listed yet)`            | Stock was not listed on the start date                      |
| `No end data found`                               | Could not find any end price for this stock                 |
| `No data found for either date`                   | Stock missing from both dates                               |
| `Index row - no individual bhavcopy data`          | The NIFTY 500 index summary row                             |

---

## Important Notes

> [!IMPORTANT]
> **Close Excel before running!** If `nse_output.csv` is open in Excel (or any other program), the script will not be able to overwrite it. Make sure to close the file before the script finishes.

> [!NOTE]
> **Months and Years are approximate.** "1 Month" = 30 days, "1 Year" = 365 days. For exact date comparisons, use the **Custom date** option.
