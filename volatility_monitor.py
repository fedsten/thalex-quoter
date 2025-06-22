import json
import logging
import requests
import time
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# API endpoints
BASE_URL = "https://testnet.thalex.com/api/v2"
INSTRUMENTS_URL = f"{BASE_URL}/public/all_instruments"
INDEX_PRICE_URL = f"{BASE_URL}/public/index"
TICKER_URL = f"{BASE_URL}/public/ticker"

def get_atm_volatility(network: str = "test") -> Optional[float]:
    """
    Get the ATM volatility (average IV of the closest call and put) for the nearest expiry.
    Returns the average IV as a float, or None if not available.
    """
    try:
        # Fetch instruments
        logging.info("Fetching list of instruments...")
        response = requests.get(INSTRUMENTS_URL)
        response.raise_for_status()
        data = response.json()
        
        if not isinstance(data, dict) or 'result' not in data:
            logging.error("Invalid instruments response format")
            return None
            
        instruments = data['result']
        if not isinstance(instruments, list):
            logging.error("Instruments result is not a list")
            return None
            
        logging.info(f"Successfully fetched {len(instruments)} instruments")
        
        # Fetch index price
        logging.info("Fetching BTCUSD index price...")
        response = requests.get(f"{INDEX_PRICE_URL}?underlying=BTCUSD")
        response.raise_for_status()
        data = response.json()
        
        if not isinstance(data, dict) or 'result' not in data:
            logging.error("Invalid index price response format")
            return None
            
        current_price = float(data['result']['price'])
        logging.info(f"Current BTCUSD price: ${current_price:,.2f}")
        
        # Filter options and group by expiry
        options = [i for i in instruments if i.get('type') == 'option' and i.get('underlying') == 'BTCUSD']
        logging.info(f"Found {len(options)} option instruments")
        
        # Group options by expiry
        options_by_expiry: Dict[str, List[Dict]] = {}
        for opt in options:
            expiry = opt.get('expiry_date')
            if expiry:
                if expiry not in options_by_expiry:
                    options_by_expiry[expiry] = []
                options_by_expiry[expiry].append(opt)
        
        # Filter and sort future expiries
        now = datetime.now(timezone.utc)
        future_expiries = [
            expiry for expiry in options_by_expiry.keys()
            if datetime.strptime(expiry, "%Y-%m-%d").replace(tzinfo=timezone.utc) > now
        ]
        sorted_expiries = sorted(future_expiries)
        if not sorted_expiries:
            logging.error("No future option expiries found")
            return None
        
        # Get nearest expiry options
        nearest_expiry = sorted_expiries[0]
        nearest_options = options_by_expiry[nearest_expiry]
        
        # Find closest call and put
        closest_call = None
        closest_put = None
        min_call_diff = float('inf')
        min_put_diff = float('inf')
        
        for opt in nearest_options:
            strike = float(opt['strike_price'])
            diff = abs(strike - current_price)
            
            if opt['option_type'] == 'call' and diff < min_call_diff:
                min_call_diff = diff
                closest_call = opt
            elif opt['option_type'] == 'put' and diff < min_put_diff:
                min_put_diff = diff
                closest_put = opt
        
        if not closest_call or not closest_put:
            logging.error("Could not find closest call and put options")
            return None
        
        logging.info(f"Closest call instrument_name: {closest_call['instrument_name']}")
        logging.info(f"Closest put instrument_name: {closest_put['instrument_name']}")
        
        # Get tickers for closest options
        def get_ticker(instrument_name: str) -> Optional[Dict]:
            try:
                response = requests.get(f"{TICKER_URL}?instrument_name={instrument_name}")
                response.raise_for_status()
                data = response.json()
                if isinstance(data, dict) and 'result' in data:
                    return data['result']
                return None
            except Exception as e:
                logging.error(f"Error fetching ticker for {instrument_name}: {e}")
                return None
        
        # Get tickers with retry logic
        max_retries = 3
        retry_delay = 1  # seconds
        
        call_ticker = None
        put_ticker = None
        
        for _ in range(max_retries):
            call_ticker = get_ticker(closest_call['instrument_name'])
            put_ticker = get_ticker(closest_put['instrument_name'])
            
            if call_ticker and put_ticker:
                logging.info(f"Call ticker data: {call_ticker}")
                logging.info(f"Put ticker data: {put_ticker}")
                break
                
            time.sleep(retry_delay)
            retry_delay *= 2
        
        if not call_ticker or not put_ticker:
            logging.error("Failed to get tickers for closest options")
            return None
            
        # Calculate average IV
        call_iv = float(call_ticker.get('iv', 0))
        put_iv = float(put_ticker.get('iv', 0))
        
        logging.info(f"Call IV: {call_iv}, Put IV: {put_iv}")
        
        if call_iv <= 0 or put_iv <= 0:
            logging.error("Invalid implied volatility values")
            return None
            
        avg_iv = (call_iv + put_iv) / 2
        logging.info(f"Average IV (ATM Volatility): {avg_iv:.2%}")
        
        return avg_iv
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Error in get_atm_volatility: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in get_atm_volatility: {e}")
        return None

if __name__ == "__main__":
    volatility = get_atm_volatility()
    if volatility is not None:
        print(f"ATM Volatility: {volatility:.2%}")
    else:
        print("Failed to get ATM volatility") 