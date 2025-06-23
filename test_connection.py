#!/usr/bin/env python3
"""
Simple connection test script for Thalex WebSocket API
"""

import asyncio
import logging
import sys
import time

# Add the current directory to a new path to import modules
sys.path.insert(0, '.')

import thalex
from thalex.thalex import Network
from keys import key_ids, private_keys
from config import cfg

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

async def test_connection():
    """Test basic WebSocket connection and authentication"""
    log.info("Starting connection test...")
    
    try:
        # Create Thalex instance
        log.info(f"Creating Thalex instance for network: {cfg.network}")
        tlx = thalex.Thalex(network=cfg.network)
        
        # Test connection
        log.info("Testing WebSocket connection...")
        await tlx.connect()
        log.info("✓ WebSocket connection established")
        
        # Check connection health
        log.info(f"Connection healthy: {tlx.connection_healthy()}")
        log.info(f"Connection state: {tlx.ws.state if tlx.ws else 'None'}")
        
        # Wait a moment
        await asyncio.sleep(2)
        
        # Test authentication
        log.info("Testing authentication...")
        await tlx.login(key_ids[cfg.network], private_keys[cfg.network])
        log.info("✓ Authentication successful")
        
        # Wait for any authentication response
        await asyncio.sleep(2)
        
        # Test a simple API call
        log.info("Testing account summary request...")
        await tlx.account_summary()
        log.info("✓ Account summary request sent")
        
        # Wait for response
        await asyncio.sleep(3)
        
        # Test receiving messages
        log.info("Testing message reception...")
        try:
            # Try to receive a message with timeout
            msg = await asyncio.wait_for(tlx.receive(), timeout=5.0)
            log.info(f"✓ Received message: {msg}")
        except asyncio.TimeoutError:
            log.warning("No message received within 5 seconds (this might be normal)")
        except Exception as e:
            log.error(f"Error receiving message: {e}")
        
        # Clean up
        log.info("Cleaning up...")
        await tlx.disconnect()
        log.info("✓ Disconnected successfully")
        
        log.info("Connection test completed successfully!")
        
    except Exception as e:
        log.error(f"Connection test failed: {e}", exc_info=True)
        return False
    
    return True

async def test_continuous_connection():
    """Test continuous connection with message receiving"""
    log.info("Starting continuous connection test...")
    
    try:
        tlx = thalex.Thalex(network=cfg.network)
        
        # Connect and authenticate
        await tlx.connect()
        await tlx.login(key_ids[cfg.network], private_keys[cfg.network])
        
        log.info("Starting continuous message reception (30 seconds)...")
        start_time = time.time()
        
        while time.time() - start_time < 30:
            try:
                if not tlx.connection_healthy():
                    log.error("Connection lost during test")
                    break
                
                msg = await asyncio.wait_for(tlx.receive(), timeout=5.0)
                log.info(f"Received: {msg}")
                
            except asyncio.TimeoutError:
                log.debug("No message received in 5 seconds")
            except Exception as e:
                log.error(f"Error during continuous test: {e}")
                break
        
        await tlx.disconnect()
        log.info("Continuous connection test completed")
        
    except Exception as e:
        log.error(f"Continuous connection test failed: {e}", exc_info=True)

if __name__ == "__main__":
    print("Thalex WebSocket Connection Test")
    print("=" * 40)
    
    # Run basic connection test
    success = asyncio.run(test_connection())
    
    if success:
        print("\nBasic connection test PASSED")
        
        # Ask if user wants to run continuous test
        response = input("\nRun continuous connection test? (y/n): ")
        if response.lower() == 'y':
            asyncio.run(test_continuous_connection())
    else:
        print("\nBasic connection test FAILED")
        sys.exit(1) 