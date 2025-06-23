import asyncio
import json
import logging
import websockets
from typing import Optional, Callable, Any

from thalex.thalex import Thalex, Network
import keys
from config import cfg
from quoter_logger import QuoterLogger

# Module-level logger
log = logging.getLogger(__name__)

class WebSocketHandler:
    """Dedicated websocket handler for managing connections and message processing"""
    
    def __init__(self, tlx: Thalex, logger: QuoterLogger, notification_handler: Callable):
        self.tlx = tlx
        self.logger = logger
        self.notification_handler = notification_handler
        self.message_queue = asyncio.Queue()
        self.receiver_task = None
        self.is_running = False
        self.authenticated = asyncio.Event()  # Event to signal authentication status
    
    async def connect_and_authenticate(self):
        """Connect to Thalex and authenticate"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.logger.log_info(f"Starting quote loop - attempting connection (attempt {attempt + 1}/{max_retries})...")
                
                if not self.tlx.connected():
                    self.logger.log_connection("Connecting to Thalex...")
                    await self.tlx.connect()
                    self.logger.log_connection("Connected successfully")
                else:
                    self.logger.log_connection("Already connected")
                
                # Wait a moment for connection to stabilize
                await asyncio.sleep(1)
                
                self.logger.log_auth("Attempting login...")
                await self.tlx.login(keys.key_ids[cfg.network], keys.private_keys[cfg.network])
                self.logger.log_auth("Login successful")
                
                # Wait a moment for authentication to complete
                await asyncio.sleep(1)
                
                self.logger.log_subscription("Setting up subscriptions...")
                await self.tlx.set_cancel_on_disconnect(6)
                await self.tlx.private_subscribe(["session.orders", "account.portfolio", "trades"])
                self.logger.log_subscription("Subscriptions set up successfully")

                self.authenticated.set()  # Signal that we are authenticated
                return True
                
            except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.WebSocketException) as e:
                self.authenticated.clear()  # Signal that we are no longer authenticated
                self.logger.log_error(f"Connection issue during setup (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                else:
                    return False
                    
            except Exception as e:
                self.authenticated.clear()  # Signal that we are no longer authenticated
                self.logger.log_error(f"Error during connection and authentication (attempt {attempt + 1}/{max_retries}): {e}", exc_info=True)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return False
        
        self.authenticated.clear()
        return False
    
    async def test_connection(self, instrument_name: str):
        """Test the connection and authentication"""
        try:
            self.logger.log_connection_test("Testing connection...")
            
            # Test basic connection
            if not self.tlx.connected():
                self.logger.log_error("[CONNECTION_TEST] Not connected!")
                return False
            
            self.logger.log_connection_test("Connection OK")
            
            # Test authentication by requesting account summary
            self.logger.log_connection_test("Testing authentication with account summary...")
            await self.tlx.account_summary()
            
            # Test instrument validity
            self.logger.log_connection_test(f"Testing instrument validity: {instrument_name}")
            await self.tlx.instrument(instrument_name)
            
            # Wait a bit for responses
            await asyncio.sleep(3)
            
            self.logger.log_connection_test("Authentication and instrument test completed")
            return True
            
        except Exception as e:
            self.logger.log_error(f"[CONNECTION_TEST] Error: {e}", exc_info=True)
            return False
    
    async def websocket_receiver(self):
        """Single coroutine responsible for receiving all websocket messages"""
        self.logger.log_info("Starting websocket receiver...")
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        while self.is_running:
            try:
                # This loop now only receives. Reconnection is handled by exceptions.
                if not self.tlx.connection_healthy() or not self.authenticated.is_set():
                    raise websockets.exceptions.ConnectionClosedError(None, "Connection unhealthy or not authenticated")

                log.debug("Waiting for websocket message...")
                msg = await self.tlx.receive()
                self.logger.log_websocket_message(msg)
                await self.message_queue.put(msg)
                consecutive_errors = 0  # Reset error counter on successful message
                
            except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.WebSocketException) as e:
                self.authenticated.clear()
                consecutive_errors += 1
                self.logger.log_error(f"WebSocket connection issue (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.log_error("Max consecutive connection errors reached, stopping receiver.")
                    await self.message_queue.put(None)
                    break

                self.logger.log_info("Attempting to reconnect and re-authenticate...")
                try:
                    # Attempt to fully reconnect and re-authenticate
                    await self.connect_and_authenticate()
                    if self.authenticated.is_set():
                        self.logger.log_info("Re-authentication successful.")
                        consecutive_errors = 0
                    else:
                        self.logger.log_error("Re-authentication failed. Retrying...")
                        await asyncio.sleep(5) # Wait before next retry
                except Exception as recon_e:
                    self.logger.log_error(f"Error during re-authentication attempt: {recon_e}")
                    await asyncio.sleep(5) # Wait before next retry

            except Exception as e:
                consecutive_errors += 1
                self.logger.log_error(f"Unexpected error in websocket receiver (attempt {consecutive_errors}/{max_consecutive_errors}): {e}", exc_info=True)
                
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.log_error("Max consecutive errors reached, stopping receiver")
                    await self.message_queue.put(None)
                    break
                
                await asyncio.sleep(2)
        
        self.logger.log_info("WebSocket receiver stopped")
    
    async def process_message(self, msg: Any) -> bool:
        """Process a single websocket message"""
        try:
            if isinstance(msg, str):
                msg = json.loads(msg)
            log.debug(f"Processing message: {msg.get('channel_name', 'unknown')}")
        except json.JSONDecodeError as e:
            self.logger.log_error(f"Failed to parse message: {e}")
            return True  # Continue processing

        if "channel_name" in msg:
            await self.notification_handler(msg["channel_name"], msg["notification"])
        elif "result" in msg:
            result = msg.get("result")
            self.logger.log_result(result)
            # Handle account summary response
            if isinstance(result, dict) and "account_number" in result:
                await self.notification_handler("account.summary", {"result": result})
            # Handle ticker response
            elif result is not None and "best_bid_price" in result and "best_ask_price" in result:
                await self.notification_handler("ticker", result)
            else:
                log.debug(f"Received result without price data: {result}")
        elif "error" in msg:
            self.logger.log_error(f"[ERROR] Received error from exchange: {msg}")
            # Pass the error notification up to be handled
            if "error" in msg:
                await self.notification_handler("error", msg["error"])
        else:
            self.logger.log_unknown_message(msg)
        
        return True  # Continue processing
    
    async def start_message_processing(self):
        """Start the main message processing loop"""
        self.is_running = True
        self.receiver_task = asyncio.create_task(self.websocket_receiver())
        
        self.logger.log_info("Entering main message processing loop...")
        while self.is_running:
            try:
                log.debug("Waiting for message from queue...")
                msg = await self.message_queue.get()
                if msg is None:
                    self.logger.log_error("Received None message from queue - receiver error")
                    break

                should_continue = await self.process_message(msg)
                if not should_continue:
                    break

            except websockets.exceptions.ConnectionClosedError as e:
                self.logger.log_error(f"WebSocket connection closed: {e}")
                break
            except Exception as e:
                self.logger.log_error(f"Error processing message: {e}", exc_info=True)
                continue
        
        self.logger.log_info("Main message loop ended")
    
    async def stop(self):
        """Stop the websocket handler"""
        self.is_running = False
        if self.receiver_task and not self.receiver_task.done():
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.log_error(f"Error cancelling receiver task: {e}")
    
    async def cleanup(self):
        """Clean up websocket connections"""
        try:
            await self.stop()
            
            # Handle session cancellation and disconnect
            if hasattr(self.tlx, 'ws') and self.tlx.ws and not self.tlx.ws.closed:
                try:
                    await self.tlx.cancel_session()
                except websockets.exceptions.ConnectionClosedError:
                    self.logger.log_warning("Connection already closed during cleanup")
                except Exception as e:
                    self.logger.log_error(f"Error during session cancellation: {e}")
                finally:
                    try:
                        await self.tlx.disconnect()
                    except Exception as e:
                        self.logger.log_error(f"Error during disconnect: {e}")
            
        except Exception as e:
            self.logger.log_error(f"Error during cleanup: {e}")
    
    async def ticker_loop(self, instrument_name: str):
        """Periodic loop to request ticker updates"""
        self.logger.log_info("Starting ticker loop...")
        while self.is_running:
            try:
                await self.authenticated.wait()  # Wait until authenticated

                # Log before making the request
                log.debug(f"About to request ticker for {instrument_name}")
                
                # Make the request with explicit error handling
                try:
                    await self.tlx.ticker(instrument_name)
                    log.debug("Ticker request completed successfully")
                except websockets.exceptions.ConnectionClosedError as e:
                    self.logger.log_error(f"Ticker loop: WebSocket connection closed during ticker request: {e}")
                    self.authenticated.clear()  # Connection is lost, clear the event
                except Exception as e:
                    self.logger.log_error(f"Ticker loop: Unexpected error during ticker request: {e}", exc_info=True)
                    self.authenticated.clear()  # Assume connection issue
                
            except Exception as e:
                self.logger.log_error(f"Ticker loop: Fatal error in loop: {e}", exc_info=True)
                # Wait a bit longer on error
                await asyncio.sleep(5)
                continue
            
            await asyncio.sleep(1)
    
    async def account_summary_loop(self):
        """Periodic loop to request account summary updates"""
        while self.is_running:
            try:
                await self.authenticated.wait()  # Wait until authenticated
                await self.tlx.account_summary()
            except websockets.exceptions.ConnectionClosedError as e:
                self.logger.log_error(f"Account summary loop: WebSocket connection closed: {e}")
                self.authenticated.clear()  # Connection is lost, clear the event
            except Exception as e:
                self.logger.log_error(f"Error in account summary loop: {e}")
                self.authenticated.clear()  # Assume connection issue
            await asyncio.sleep(5)  # Update every 5 seconds 