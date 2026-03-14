import argparse
import requests
import json
import pandas as pd
from datetime import datetime, timedelta
import time
import urllib.parse

class NSEFetcher:
    """
    Handles HTTP sessions and requests to the NSE website.
    Maintains cookies and headers to bypass simple anti-scraping measures.
    """
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://www.nseindia.com"
        # Standard browser headers required by NSE to accept requests
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.initialized = False

    def init_session(self):
        """
        Initializes the session by hitting the NSE homepage to collect initial cookies.
        """
        try:
            # Step 1: Hit home page for basic cookies with explicit headers
            self.session.get(self.base_url, headers=self.headers, timeout=15)
            self.initialized = True
        except:
            self.initialized = True

    def get_data(self, url, referer=None):
        """
        Fetches JSON data from a specific API endpoint. Includes retry logic and jitter
        to handle rate limiting or temporary blocking.
        """
        if not self.initialized:
            self.init_session()
        
        headers = self.headers.copy()
        headers["Referer"] = referer if referer else f"{self.base_url}/market-data/live-equity-market"
        headers["X-Requested-With"] = "XMLHttpRequest"
        if "api" in url:
            headers["Accept"] = "*/*"
        
        for attempt in range(5):
            try:
                # Add small jitter to avoid rate limits
                if attempt > 0: time.sleep(random.uniform(1, 3))
                
                response = self.session.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 403:
                    # 403 Forbidden: NSE session might have expired, try resetting
                    time.sleep(2)
                    self.session.get(self.base_url, headers=self.headers, timeout=15)
                else:
                    time.sleep(1)
            except:
                time.sleep(1)
        return None

import concurrent.futures
import random

fetcher = NSEFetcher()

import nsepython

def get_snapshot():
    """
    Fetches the current live prices for all stocks in the NIFTY 500 index.
    """
    print("Fetching Nifty 500 snapshot...")
    url = f"{fetcher.base_url}/api/equity-stockIndices?index=NIFTY%20500"
    data = fetcher.get_data(url)
    if not data or 'data' not in data: return []
    return data['data']

def calculate_target_date(compare_str):
    """
    Parses strings like '1w', '1m' or 'YYYY-MM-DD' into a Python date object.
    Used to set the 'Target Date' for historical comparison.
    """
    today = datetime.today().date()
    if compare_str == '1d': return today - timedelta(days=1)
    if compare_str == '1w': return today - timedelta(days=7)
    if compare_str == '2w': return today - timedelta(days=14)
    if compare_str == '1m': return today - timedelta(days=30)
    if compare_str == '6m': return today - timedelta(days=180)
    if compare_str == 'ytd': return datetime(today.year, 1, 1).date()
    if compare_str == '1y': return today - timedelta(days=365)
    
    try:
        return datetime.strptime(compare_str, '%Y-%m-%d').date()
    except ValueError:
        print("Invalid format. Use 1d, 1w, 2w, 1m, 6m, ytd, 1y, or YYYY-MM-DD")
        exit(1)

def fetch_bhavcopy_with_fallback(target_date):
    """
    Attempts to fetch the daily Bhavcopy (market snapshot file) for the given date. 
    If the market was closed (weekend/holiday), it loops backwards day-by-day 
    (up to 10 days) until it find the most recent valid file.
    """
    for i in range(10):
        test_dt = target_date - timedelta(days=i)
        date_str = test_dt.strftime('%d-%m-%Y')
        try:
            # get_bhavcopy throws an exception if the file doesn't exist (e.g., market closed)
            df_bhav = nsepython.get_bhavcopy(date_str)
            if df_bhav is not None and not df_bhav.empty:
                return test_dt, df_bhav
        except Exception:
            pass # File not found for this date, keep looping backwards
    return None, None

def fill_missing_bhavcopy_prices(missing_symbols, start_date):
    """
    For stocks that might be missing from a specific day's Bhavcopy (e.g. they weren't traded), 
    this scans older daily files specifically for those stocks until it finds their last price.
    """
    results = {sym: {'price': None, 'date': None} for sym in missing_symbols}
    current_date = start_date - timedelta(days=1)
    
    # Search backwards for up to 14 calendar days
    for _ in range(14):
        if not missing_symbols:
            break # Found all of them
            
        date_str = current_date.strftime('%d-%m-%Y')
        try:
            df_bhav = nsepython.get_bhavcopy(date_str)
            if df_bhav is not None and not df_bhav.empty:
                # Check if any of our missing symbols are in this older Bhavcopy
                for sym in list(missing_symbols):
                    match = df_bhav[df_bhav['SYMBOL'] == sym]
                    if not match.empty:
                        # Found it! Get the close price and record the specific date
                        close_price = match.iloc[0][' CLOSE_PRICE']
                        results[sym] = {'price': close_price, 'date': date_str}
                        missing_symbols.remove(sym)
        except Exception:
            pass # Market was closed this day, skip
            
        current_date -= timedelta(days=1)
        
    return results

def main():
    """
    Main execution flow:
    1. Parse command line arguments.
    2. Fetch current live data (snapshot).
    3. If -c is provided, fetch historical Bhavcopies and compare prices.
    4. Calculate percentage change.
    5. Print top 20 symbols and optionally export to CSV.
    """
    parser = argparse.ArgumentParser(description="NSE India Stock Info fetcher")
    parser.add_argument('-c', '--compare', type=str, help="Comparison timeframe (1w, 1m, ytd, or YYYY-MM-DD)")
    parser.add_argument('--csv', action='store_true', help="Export to CSV")
    args = parser.parse_args()

    # Step 1: Get current live Snapshot
    snapshot_data = get_snapshot()
    if not snapshot_data:
        print("Error: Could not fetch snapshot. NSE might be blocking the request.")
        return

    rows = []
    symbols = []
    for item in snapshot_data:
        sym = item.get('symbol')
        if not sym: continue
        symbols.append(sym)
        rows.append({
            'Name': item.get('meta', {}).get('companyName', sym),
            'Code': sym,
            'Open': item.get('open'),
            'High': item.get('dayHigh'),
            'Low': item.get('dayLow'),
            'Close': item.get('lastPrice'),
            'Prev_Close': item.get('previousClose'),
            'Trades': item.get('totalTradedVolume'),
            'Turnover': item.get('totalTradedValue'),
            'Industry': item.get('meta', {}).get('industry', 'N/A')
        })
        
    df = pd.DataFrame(rows)

    # Step 2: Handle Comparison Target
    if args.compare:
        target_date = calculate_target_date(args.compare)
        target_str = target_date.strftime('%Y-%m-%d')
        print(f"Comparing against Target: {target_str}")
        
        print("Fetching historical Bhavcopy snapshot... (this takes ~1 second)")
        valid_date, bhav_df = fetch_bhavcopy_with_fallback(target_date)
        
        hist_rows = []
        alerts_flag = False
        
        if valid_date is not None:
            valid_date_str = valid_date.strftime('%Y-%m-%d')
            
            # Did we have to fallback to find the master Bhavcopy?
            global_fallback_alert = ""
            if valid_date != target_date:
                global_fallback_alert = f"Substituting {target_str} with {valid_date_str}"
                alerts_flag = True

            missing_symbols = set()
            
            # First pass: map everything from the master Bhavcopy
            for sym in symbols:
                match = bhav_df[bhav_df['SYMBOL'] == sym]
                if not match.empty:
                    # nsepython get_bhavcopy usually has space-prefixed column names: ' CLOSE_PRICE'
                    close_price = match.iloc[0][' CLOSE_PRICE']
                    hist_rows.append({
                        'Code': sym, 
                        'Comp_Date': valid_date_str, 
                        'Comp_Price': close_price, 
                        'Alert': global_fallback_alert
                    })
                else:
                    # The stock wasn't in the Bhavcopy today
                    missing_symbols.add(sym)
                    
            # Second pass: recursively find older prices for any missing individual stocks
            if missing_symbols:
                print(f"Notice: {len(missing_symbols)} stocks had no data on {valid_date_str}. Searching older records for them...")
                missing_results = fill_missing_bhavcopy_prices(missing_symbols, valid_date)
                
                for sym, result in missing_results.items():
                    if result['price'] is not None:
                        # Convert their specific date back to YYYY-MM-DD for reporting
                        dt = datetime.strptime(result['date'], '%d-%m-%Y')
                        fmt_date = dt.strftime('%Y-%m-%d')
                        hist_rows.append({
                            'Code': sym,
                            'Comp_Date': fmt_date,
                            'Comp_Price': result['price'],
                            'Alert': f"Stock didn't trade on {valid_date_str}. Used older price from {fmt_date}."
                        })
                        alerts_flag = True
                    else:
                        hist_rows.append({
                            'Code': sym,
                            'Comp_Date': None,
                            'Comp_Price': None,
                            'Alert': "No recent trade data found."
                        })
            
            # Step 3: Merge and calculate change percentages
            hist_df = pd.DataFrame(hist_rows)
            df = df.merge(hist_df, on='Code', how='left')
            
            df['Comp_Price'] = pd.to_numeric(df['Comp_Price'], errors='coerce')
            df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
            df['Change_%'] = ((df['Close'] - df['Comp_Price']) / df['Comp_Price'] * 100).round(2)
            
            if alerts_flag:
                print("\n*** Notice: Holiday/weekend substitutions made. See 'Alert' column for details. ***\n")
        else:
            print("Error: Could not retrieve ANY historical Bhavcopy for the target week.")
            return

    # Step 4: Output Table
    print("\n--- PERFORMANCE SUMMARY (Top 20) ---")
    cols = ['Name', 'Code', 'Close', 'Prev_Close', 'Trades']
    if args.compare: cols += ['Comp_Price', 'Change_%']
    
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    
    print(df[cols].head(20).to_string(index=False, justify='left'))
    print(f"\nProcessed {len(df)} symbols.")
    
    # Step 5: Export to CSV
    if args.csv:
        try:
            df.to_csv('nse_output.csv', index=False)
            print("\nSUCCESS: Full report exported to nse_output.csv")
        except PermissionError:
            print("\nERROR: Could not save CSV! Please close 'nse_output.csv' if it is open in another program.")

if __name__ == '__main__':
    main()
