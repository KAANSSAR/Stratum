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
    (up to 30 days) until it finds the most recent valid file.
    """
    for i in range(30):
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
    
    # Search backwards for up to 30 calendar days
    for _ in range(30):
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

def get_validated_input(prompt, valid_options=None, is_date=False):
    """
    Helper to get validated input from the user.
    """
    while True:
        user_input = input(prompt).strip()
        if is_date:
            try:
                return datetime.strptime(user_input, '%Y-%m-%d').date()
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
                continue
        
        if valid_options:
            if user_input in valid_options:
                return user_input
            print(f"Invalid option. Please choose from {', '.join(valid_options)}.")
            continue
        
        return user_input

def main():
    """
    Main execution flow:
    1. Interactive terminal prompts for End Date and Start Date.
    2. Fetch current live data (snapshot) for metadata.
    3. Fetch Bhavcopies for End Date (if historical) and Start Date.
    4. Calculate percentage change.
    5. Print top 20 symbols and always export to CSV.
    """
    print("\n=== NSE India Stock Performance Tool ===\n")

    # Prompt 1: End Date selection
    today = datetime.today().date()
    print(f"What day do you want to do the comparison?")
    print(f"1. Present day ({today})")
    print("2. Custom date")
    end_choice = get_validated_input("Choose option (1-2): ", ['1', '2'])

    if end_choice == '1':
        target_end_date = today
        is_end_today = True
    else:
        target_end_date = get_validated_input("Enter End Date (YYYY-MM-DD): ", is_date=True)
        is_end_today = False

    # Prompt 2: Comparison Period selection
    print("\nHow do you want to compare?")
    print("1. Days")
    print("2. Weeks")
    print("3. Months")
    print("4. Years")
    print("5. YTD")
    print("6. Custom date")
    comp_choice = get_validated_input("Choose option (1-6): ", ['1', '2', '3', '4', '5', '6'])

    target_start_date = None
    if comp_choice == '5':
        target_start_date = datetime(target_end_date.year, 1, 1).date()
    elif comp_choice == '6':
        target_start_date = get_validated_input("Enter Start Date (YYYY-MM-DD): ", is_date=True)
    else:
        units = ""
        if comp_choice == '1': units = "Days"
        elif comp_choice == '2': units = "Weeks"
        elif comp_choice == '3': units = "Months"
        else: units = "Years"
        
        count_str = get_validated_input(f"Enter how many {units} ago you want to compare to {target_end_date}: ")
        try:
            count = int(count_str)
            if comp_choice == '1': target_start_date = target_end_date - timedelta(days=count)
            elif comp_choice == '2': target_start_date = target_end_date - timedelta(weeks=count)
            elif comp_choice == '3': target_start_date = target_end_date - timedelta(days=30*count)
            else: target_start_date = target_end_date - timedelta(days=365*count)
        except ValueError:
            print("Invalid number. Defaulting to 1 unit ago.")
            if comp_choice == '1': target_start_date = target_end_date - timedelta(days=1)
            elif comp_choice == '2': target_start_date = target_end_date - timedelta(weeks=1)
            elif comp_choice == '3': target_start_date = target_end_date - timedelta(days=30)
            else: target_start_date = target_end_date - timedelta(days=365)

    print(f"\nComparing {target_start_date} vs {target_end_date}...")

    # Step 1: Get metadata and live prices (if end is today)
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
            'Snapshot_Price': item.get('lastPrice'),
            'Prev_Close': item.get('previousClose'),
            'No_of_Trades': item.get('totalTradedVolume'),
            'Turnover': item.get('totalTradedValue'),
            'Industry': item.get('meta', {}).get('industry', 'N/A'),
        })
    df = pd.DataFrame(rows)

    # Step 2: Fetch Prices for End Date (with per-stock fallback)
    actual_end_date_str = ""
    if is_end_today:
        # Use snapshot prices as the base; track the date per-stock
        df['End_Price'] = df['Snapshot_Price']
        actual_end_date_str = today.strftime('%Y-%m-%d')
        df['End_Date_Actual'] = actual_end_date_str

        # Find stocks where the snapshot had no price
        missing_end_mask = df['End_Price'].isnull()
        missing_end_syms = set(df.loc[missing_end_mask, 'Code'].tolist())

        if missing_end_syms:
            print(f"Notice: {len(missing_end_syms)} stocks missing from live snapshot. Fetching from latest bhavcopy...")
            valid_end, end_bhav = fetch_bhavcopy_with_fallback(today)
            if valid_end and end_bhav is not None:
                for sym in list(missing_end_syms):
                    match = end_bhav[end_bhav['SYMBOL'] == sym]
                    if not match.empty:
                        df.loc[df['Code'] == sym, 'End_Price'] = match.iloc[0][' CLOSE_PRICE']
                        df.loc[df['Code'] == sym, 'End_Date_Actual'] = valid_end.strftime('%Y-%m-%d')
                        missing_end_syms.discard(sym)

                # If still missing, backfill further
                if missing_end_syms:
                    fill_end = fill_missing_bhavcopy_prices(missing_end_syms, valid_end)
                    for sym, res in fill_end.items():
                        if res['price'] is not None:
                            df.loc[df['Code'] == sym, 'End_Price'] = res['price']
                            df.loc[df['Code'] == sym, 'End_Date_Actual'] = datetime.strptime(res['date'], '%d-%m-%Y').strftime('%Y-%m-%d') if res['date'] else None
    else:
        print(f"Fetching historical prices for End Date: {target_end_date}...")
        valid_end, end_bhav = fetch_bhavcopy_with_fallback(target_end_date)
        if not valid_end:
            print("Error: Could not find any trade records for the End Date.")
            return
        actual_end_date_str = valid_end.strftime('%Y-%m-%d')

        end_prices = []
        missing_end = set()
        for sym in symbols:
            match = end_bhav[end_bhav['SYMBOL'] == sym]
            if not match.empty:
                end_prices.append({'Code': sym, 'End_Price': match.iloc[0][' CLOSE_PRICE'], 'End_Date_Actual': actual_end_date_str})
            else:
                missing_end.add(sym)

        if missing_end:
            print(f"Notice: {len(missing_end)} stocks missing from end day. Backfilling...")
            fill_end = fill_missing_bhavcopy_prices(missing_end, valid_end)
            for sym, res in fill_end.items():
                end_prices.append({
                    'Code': sym,
                    'End_Price': res['price'],
                    'End_Date_Actual': datetime.strptime(res['date'], '%d-%m-%Y').strftime('%Y-%m-%d') if res['date'] else None
                })

        end_df = pd.DataFrame(end_prices)
        df = df.merge(end_df, on='Code', how='left')

    # Always remove Snapshot_Price — End_Price is the only price column needed
    df.drop(columns=['Snapshot_Price'], inplace=True, errors='ignore')

    # Step 3: Fetch Prices for Start Date (with per-stock fallback)
    print(f"Fetching historical prices for Start Date: {target_start_date}...")
    valid_start, start_bhav = fetch_bhavcopy_with_fallback(target_start_date)
    if not valid_start:
        print("Error: Could not find any trade records for the Start Date.")
        return
    actual_start_date_str = valid_start.strftime('%Y-%m-%d')

    start_prices = []
    missing_start = set()
    for sym in symbols:
        match = start_bhav[start_bhav['SYMBOL'] == sym]
        if not match.empty:
            start_prices.append({'Code': sym, 'Start_Price': match.iloc[0][' CLOSE_PRICE'], 'Start_Date_Actual': actual_start_date_str})
        else:
            missing_start.add(sym)

    if missing_start:
        print(f"Notice: {len(missing_start)} stocks missing from start day. Backfilling...")
        fill_start = fill_missing_bhavcopy_prices(missing_start, valid_start)
        for sym, res in fill_start.items():
            start_prices.append({
                'Code': sym,
                'Start_Price': res['price'],
                'Start_Date_Actual': datetime.strptime(res['date'], '%d-%m-%Y').strftime('%Y-%m-%d') if res['date'] else None
            })

    start_df = pd.DataFrame(start_prices)
    df = df.merge(start_df, on='Code', how='left')

    # Step 4: Calculations
    df['End_Price'] = pd.to_numeric(df['End_Price'], errors='coerce')
    df['Start_Price'] = pd.to_numeric(df['Start_Price'], errors='coerce')

    # Calculate Change % only where both prices exist
    mask_both = df['End_Price'].notnull() & df['Start_Price'].notnull()
    df.loc[mask_both, 'Change_%'] = ((df.loc[mask_both, 'End_Price'] - df.loc[mask_both, 'Start_Price']) / df.loc[mask_both, 'Start_Price'] * 100).round(2)

    # Alert Column Logic
    df['Alert'] = ""

    # 1. Global Fallback Alert (if the main start date was adjusted for everyone)
    if actual_start_date_str != target_start_date.strftime('%Y-%m-%d'):
        df['Alert'] = f"Target was {target_start_date}, but used {actual_start_date_str}"

    # 2. Individual backfill alerts for start date
    backfilled_start = df['Start_Date_Actual'].notnull() & (df['Start_Date_Actual'] != actual_start_date_str)
    df.loc[backfilled_start, 'Alert'] = df.loc[backfilled_start, 'Start_Date_Actual'].apply(lambda x: f"Start price from {x}")

    # 3. Individual backfill alerts for end date
    backfilled_end = df['End_Date_Actual'].notnull() & (df['End_Date_Actual'] != actual_end_date_str)
    df.loc[backfilled_end, 'Alert'] = df.loc[backfilled_end, 'End_Date_Actual'].apply(lambda x: f"End price from {x}")

    # 4. Missing Data Alert (Never found a price at all)
    missing_start_mask = df['Start_Price'].isnull()
    missing_end_mask = df['End_Price'].isnull()
    df.loc[missing_start_mask, 'Alert'] = "No start data (likely not listed yet)"
    df.loc[missing_end_mask, 'Alert'] = "No end data found"
    df.loc[missing_start_mask & missing_end_mask, 'Alert'] = "No data found for either date"

    # Special case for the Index row
    df.loc[df['Code'].str.contains('NIFTY'), 'Alert'] = "Index row - no individual bhavcopy data"

    # Step 5: Sort and Output
    # Pull out the NIFTY 500 index row to pin it at the top
    nifty_row = df[df['Code'].str.contains('NIFTY')]
    rest = df[~df['Code'].str.contains('NIFTY')]

    # Tier 1: Has Change_% → sort by Change_% descending
    tier1 = rest[rest['Change_%'].notnull()].sort_values('Change_%', ascending=False)
    # Tier 2: No Change_% but has End_Price → sort by End_Price descending
    tier2 = rest[rest['Change_%'].isnull() & rest['End_Price'].notnull()].sort_values('End_Price', ascending=False)
    # Tier 3: No Change_% and no End_Price → sort alphabetically by Name
    tier3 = rest[rest['Change_%'].isnull() & rest['End_Price'].isnull()].sort_values('Name')

    df = pd.concat([nifty_row, tier1, tier2, tier3], ignore_index=True)

    print("\n--- PERFORMANCE SUMMARY (Top 20) ---")
    cols = ['Name', 'Code', 'Start_Price', 'End_Price', 'Change_%']

    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)

    print(df[cols].head(20).to_string(index=False, justify='left'))
    print(f"\nProcessed {len(df)} symbols.")

    # Always export to CSV
    try:
        df.to_csv('nse_output.csv', index=False)
        print(f"\nSUCCESS: Full report exported to nse_output.csv")
        print(f"Comparison: {actual_start_date_str} to {actual_end_date_str}")
    except PermissionError:
        print("\nERROR: Could not save CSV! Please close 'nse_output.csv' if it is open in another program.")



if __name__ == '__main__':
    main()

