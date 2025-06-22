#!/usr/bin/env python3

import json
import logging
import os
import sys
import jwt
import time
import requests
from datetime import datetime, timezone
from typing import Optional, Tuple

# Add thalex-perp directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
thalex_perp_dir = os.path.join(script_dir, 'thalex-perp')
sys.path.append(thalex_perp_dir)

import thalex
from thalex.thalex import Network
import keys  # Now this will import from thalex-perp/keys.py
from config import cfg

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_auth_token(key_id: str, private_key: str) -> str:
    """Generate JWT token for authentication"""
    return jwt.encode(
        {"iat": time.time()},
        private_key,
        algorithm="RS512",
        headers={"kid": key_id},
    )

def get_pnl() -> Optional[Tuple[float, float]]:
    """
    Get both unrealised and realised PnL values from account summary endpoint
    
    Returns:
        Tuple of (unrealised_pnl, realised_pnl) if successful, None if there was an error
    """
    # Get authentication credentials from config
    network = cfg.network
    key_id = keys.key_ids[network]
    private_key = keys.private_keys[network]
    
    # Generate auth token
    token = get_auth_token(key_id, private_key)
    
    # Set up headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Make request to account summary endpoint
    if network == Network.TEST:
        url = "https://testnet.thalex.com/api/v2/private/account_summary"
    else:
        url = "https://thalex.com/api/v2/private/account_summary"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for non-200 status codes
        
        data = response.json()
        if "result" in data:
            result = data["result"]
            unrealised_pnl = result.get("unrealised_pnl", 0)
            realised_pnl = result.get("session_realised_pnl", 0)
            
            # Log values if running as main script
            if __name__ == "__main__":
                logger.info(f"Unrealised PnL: {unrealised_pnl:.2f}")
                logger.info(f"Session Realised PnL: {realised_pnl:.2f}")
            
            return unrealised_pnl, realised_pnl
        else:
            logger.error(f"Unexpected response format: {data}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error making request: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding response: {e}")
        return None

if __name__ == "__main__":
    # Example usage when run as script
    result = get_pnl()
    if result:
        unrealised, realised = result
        print(f"Unrealised PnL: {unrealised:.2f}")
        print(f"Realised PnL: {realised:.2f}") 