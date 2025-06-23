import asyncio
import json
import logging
import socket
import sys
import time
import argparse
from datetime import datetime, timezone
from typing import Optional

import websockets
import thalex
from thalex.thalex import Direction, Thalex, Network
import keys
from volatility_monitor import get_atm_volatility as volatility_monitor_get_atm_volatility
from pnl import get_pnl  # Import the new PnL function
from config import cfg
from utils import round_to_tick, round_size, calculate_fee_amount
from quoter_logger import QuoterLogger
from websocket_handler import WebSocketHandler
from notification_handler import NotificationHandler

# Module-level logger
log = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Thalex Quoter Bot')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Enable verbose logging (default: False)')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Disable verbose logging (default: False)')
    return parser.parse_args()

class Quoter:
    def __init__(self, tlx: Thalex, instrument_name: str, volatility: float, log_interval: int = None, vol_update_interval: int = None, verbose: bool = True):
        self.tlx = tlx
        self.instrument_name = instrument_name
        self.volatility = volatility
        self.log_interval = log_interval or cfg.log_interval
        self.vol_update_interval = vol_update_interval or cfg.volatility_update_interval
        self.verbose = verbose  # Control logging verbosity
        
        # Setup logging
        self.logger = QuoterLogger(verbose=verbose)
        
        # Setup notification handler with callbacks
        self.notification_handler = NotificationHandler(
            logger=self.logger,
            instrument_name=instrument_name,
            on_order_update=self._on_order_update,
            on_position_update=self._on_position_update,
            on_trade_update=self._on_trade_update,
            on_pnl_update=self._on_pnl_update,
            on_ticker_update=self._on_ticker_update,
            on_exchange_error=self._on_exchange_error
        )
        
        # Setup websocket handler
        self.websocket_handler = WebSocketHandler(tlx, self.logger, self.notification_handler.handle_notification)
        
        # State variables
        self.mid: Optional[float] = None
        self.quotes = {}
        self.position: Optional[float] = None
        self.last_bid_spread = None
        self.last_ask_spread = None
        self.current_volatility: Optional[float] = volatility  # Initialize with constructor parameter
        self.last_volatility_update = 0
        self.pnl_log_counter = 0  # Counter for PnL terminal logging
        
        # Account state
        self.unrealised_pnl: Optional[float] = None
        self.realised_pnl: Optional[float] = None
        self.total_fees_paid = 0.0  # Track total fees paid in session
        self.last_account_update = 0
        
        # Cooldown state
        self.last_bid_fill_time: Optional[float] = None
        self.last_ask_fill_time: Optional[float] = None
        self.bid_cooldown_until: Optional[float] = None
        self.ask_cooldown_until: Optional[float] = None
        
        # Recovery state
        self.bid_recovery_until: Optional[float] = None
        self.ask_recovery_until: Optional[float] = None
        
        # Desync recovery state
        self.recovering_from_desync = False

    async def _on_exchange_error(self, error_data: dict):
        """Callback for handling exchange-level errors."""
        message = error_data.get("message", "")
        if "order not found" in message and not self.recovering_from_desync:
            log.error("Received 'order not found' error. State desynchronization detected.")
            asyncio.create_task(self.recover_from_state_desync())

    async def recover_from_state_desync(self):
        """Cancel all orders and reset internal state to recover from desync."""
        self.recovering_from_desync = True
        log.warning("====== RECOVERY MODE INITIATED ======")
        log.warning("Cancelling all orders to resynchronize state...")

        try:
            await self.tlx.cancel_all()
            log.info("cancel_all request sent successfully.")

            # Clear local order cache
            self.quotes.clear()
            log.warning("Local order cache cleared.")
            
            # Allow some time for cancellation notifications to be processed
            await asyncio.sleep(2) 
            
        except Exception as e:
            log.error(f"Error during desync recovery: {e}", exc_info=True)
        finally:
            log.warning("====== RECOVERY MODE CONCLUDED ======")
            self.recovering_from_desync = False

    # Notification callback methods
    def _on_order_update(self, client_order_id: str, order_data: dict):
        """Callback for order updates"""
        order = order_data["order"]
        status = order_data["status"]
        
        # Update local state with the latest order information
        self.quotes[client_order_id] = order
        
        # Handle fills and update cooldowns
        if status == "filled":
            fill_time = order_data["fill_time"]
            fee_amount = order_data["fee_amount"]
            self.total_fees_paid += fee_amount
            
            if str(client_order_id) == str(cfg.quote_ids["bid"][0]):
                self.last_bid_fill_time = fill_time
                self.bid_cooldown_until = fill_time + cfg.bid_fill_cooldown
                self.bid_recovery_until = fill_time + cfg.bid_fill_cooldown + cfg.bid_fill_recovery
                log.info(f"Bid fill detected, cooldown until {self.bid_cooldown_until}, recovery until {self.bid_recovery_until}")
            elif str(client_order_id) == str(cfg.quote_ids["ask"][0]):
                self.last_ask_fill_time = fill_time
                self.ask_cooldown_until = fill_time + cfg.ask_fill_cooldown
                self.ask_recovery_until = fill_time + cfg.ask_fill_cooldown + cfg.ask_fill_recovery
                log.info(f"Ask fill detected, cooldown until {self.ask_cooldown_until}, recovery until {self.ask_recovery_until}")

    def _on_position_update(self, position: float):
        """Callback for position updates"""
        self.position = position

    def _on_trade_update(self):
        """Callback for trade updates"""
        if self.mid is not None:
            asyncio.create_task(self.update_quotes(self.mid))

    def _on_pnl_update(self, unrealised_pnl: Optional[float], realised_pnl: Optional[float]):
        """Callback for PnL updates"""
        self.unrealised_pnl = unrealised_pnl
        self.realised_pnl = realised_pnl

    def _on_ticker_update(self, mid_price: float, best_bid: Optional[float], best_ask: Optional[float]):
        """Callback for ticker updates"""
        asyncio.create_task(self.update_quotes(mid_price, best_bid, best_ask))

    async def refresh_order_status(self, client_order_id: str):
        """Refresh the status of a specific order from the exchange"""
        try:
            # Request order status from exchange
            await self.tlx.order_status(client_order_id=int(client_order_id))
        except Exception as e:
            log.debug(f"Could not refresh order status for {client_order_id}: {e}")

    def dump_order_states(self):
        """Debug method to dump the current state of all orders"""
        log.info("=== CURRENT ORDER STATES ===")
        for cid, order in self.quotes.items():
            status = order.get("status", "unknown")
            price = order.get("price", "unknown")
            direction = order.get("direction", "unknown")
            log.info(f"Order {cid}: status='{status}', price={price}, direction={direction}")
        log.info("=== END ORDER STATES ===")

    async def update_volatility_loop(self):
        while True:
            try:
                atm_vol = volatility_monitor_get_atm_volatility()
                if atm_vol is not None:
                    self.current_volatility = atm_vol
                    self.last_volatility_update = time.time()
                    log.info(f"Updated ATM Volatility (from monitor) to: {self.current_volatility:.2%}")
                else:
                    log.warning("volatility_monitor.get_atm_volatility() returned None; volatility not updated.")
            except Exception as e:
                log.error(f"Error updating volatility: {e}")
            await asyncio.sleep(self.vol_update_interval)

    async def log_loop(self):
        while True:
            try:
                # Get current timestamp
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                
                # Get PnL values using the new method right before logging
                pnl_result = get_pnl()
                if pnl_result:
                    self.unrealised_pnl, self.realised_pnl = pnl_result
                    log.debug(f"Updated PnL in log_loop - Actual: {self.unrealised_pnl}, {self.realised_pnl}")
                else:
                    self.logger.log_warning("Failed to get PnL values from account summary endpoint")
                
                # Calculate current size scale
                if self.current_volatility is not None:
                    size_scale = 1 / (1 + self.current_volatility * cfg.volatility_multiplier)
                else:
                    size_scale = 1.0
                
                # Write to CSV using the logger
                self.logger.write_csv_log(
                    timestamp=timestamp,
                    mid=self.mid,
                    position=self.position,
                    last_bid_spread=self.last_bid_spread,
                    last_ask_spread=self.last_ask_spread,
                    unrealised_pnl=self.unrealised_pnl,
                    realised_pnl=self.realised_pnl,
                    total_fees_paid=self.total_fees_paid,
                    current_volatility=self.current_volatility,
                    size_scale=size_scale
                )
                
                # Log state summary using the logger
                self.logger.log_state_summary(
                    current_volatility=self.current_volatility,
                    mid=self.mid,
                    position=self.position,
                    last_bid_spread=self.last_bid_spread,
                    last_ask_spread=self.last_ask_spread,
                    unrealised_pnl=self.unrealised_pnl,
                    realised_pnl=self.realised_pnl,
                    total_fees_paid=self.total_fees_paid
                )
                
            except Exception as e:
                self.logger.log_error(f"Error in log_loop: {e}")
                
            await asyncio.sleep(self.log_interval)

    async def update_quotes(self, new_mid, best_bid: Optional[float] = None, best_ask: Optional[float] = None):
        if self.position is None:
            return

        current_time = time.time()
        
        # Check if sides are in cooldown or recovery
        bid_in_cooldown = self.bid_cooldown_until is not None and current_time < self.bid_cooldown_until
        ask_in_cooldown = self.ask_cooldown_until is not None and current_time < self.ask_cooldown_until
        bid_in_recovery = self.bid_recovery_until is not None and current_time < self.bid_recovery_until and not bid_in_cooldown
        ask_in_recovery = self.ask_recovery_until is not None and current_time < self.ask_recovery_until and not ask_in_cooldown
        
        # Debug logging for recovery state
        if bid_in_recovery or ask_in_recovery:
            log.info(f"Recovery state - Bid cooldown until: {self.bid_cooldown_until}, recovery until: {self.bid_recovery_until}, "
                    f"Ask cooldown until: {self.ask_cooldown_until}, recovery until: {self.ask_recovery_until}, "
                    f"Current time: {current_time}")
            log.info(f"Recovery flags - Bid in recovery: {bid_in_recovery}, Ask in recovery: {ask_in_recovery}")
        elif self.bid_recovery_until is not None or self.ask_recovery_until is not None:
            # Log when recovery periods are set but not currently active
            log.debug(f"Recovery periods set - Bid recovery until: {self.bid_recovery_until}, Ask recovery until: {self.ask_recovery_until}, Current time: {current_time}")
        
        if bid_in_cooldown and ask_in_cooldown:
            log.info("Both sides in cooldown, skipping quote update")
            return

        # Calculate base spread using volatility
        if self.current_volatility is not None:
            base_spread = cfg.min_spread_bps + (cfg.max_spread_bps - cfg.min_spread_bps) * self.current_volatility * cfg.volatility_multiplier
        else:
            base_spread = cfg.min_spread_bps

        # Position-based spread adjustment
        P = self.position
        clamped_P = max(min(P, cfg.max_position), -cfg.max_position)
        position_factor = (abs(clamped_P) / cfg.max_position) ** 2
        
        bid_spread = base_spread * (1 + position_factor) if P > 0 else base_spread
        ask_spread = base_spread * (1 + position_factor) if P < 0 else base_spread
        
        # Apply recovery multiplier if in recovery period
        if bid_in_recovery:
            original_bid_spread = bid_spread
            bid_spread *= cfg.recovery_spread_multiplier
            log.info(f"Bid in recovery period, applying {cfg.recovery_spread_multiplier}x spread multiplier: {original_bid_spread:.2f}bps -> {bid_spread:.2f}bps")
        if ask_in_recovery:
            original_ask_spread = ask_spread
            ask_spread *= cfg.recovery_spread_multiplier
            log.info(f"Ask in recovery period, applying {cfg.recovery_spread_multiplier}x spread multiplier: {original_ask_spread:.2f}bps -> {ask_spread:.2f}bps")

        self.last_bid_spread = bid_spread
        self.last_ask_spread = ask_spread

        if self.current_volatility is not None:
            log.info(f"Spread components - Base: {cfg.min_spread_bps:.2f}bps, "
                    f"Volatility: {self.current_volatility:.4%}, "
                    f"Base spread: {base_spread:.2f}bps, "
                    f"Position factor: {position_factor:.2f}, "
                    f"Final spreads - Bid: {bid_spread:.2f}bps, Ask: {ask_spread:.2f}bps")

        bid_price = round_to_tick(new_mid - (bid_spread / 10000 * new_mid))
        ask_price = round_to_tick(new_mid + (ask_spread / 10000 * new_mid))
        
        # Market crossing protection - ensure we don't cross the market
        if best_bid is not None and bid_price >= best_bid:
            bid_price = round_to_tick(best_bid - cfg.price_tick)  # One tick below best bid
            log.info(f"Adjusted bid price to avoid crossing market: {bid_price:.2f} (best_bid: {best_bid:.2f})")
        
        if best_ask is not None and ask_price <= best_ask:
            ask_price = round_to_tick(best_ask + cfg.price_tick)  # One tick above best ask
            log.info(f"Adjusted ask price to avoid crossing market: {ask_price:.2f} (best_ask: {best_ask:.2f})")

        # Adjust size based on volatility
        if self.current_volatility is not None:
            size_scale = 1 / (1 + self.current_volatility * cfg.volatility_multiplier)
        else:
            size_scale = 1.0
        
        adjusted_size = cfg.size * size_scale
        
        # Stop quoting on sides that would exceed MAX_POSITION
        if self.position >= cfg.max_position:
            bid_size = 0  # Stop quoting bids when at max long position
            ask_size = round_size(max(min(adjusted_size, cfg.max_position + self.position), 0))
            log.info(f"At max long position ({self.position:.3f}), stopping bid quotes")
        elif self.position <= -cfg.max_position:
            bid_size = round_size(max(min(adjusted_size, cfg.max_position - self.position), 0))
            ask_size = 0  # Stop quoting asks when at max short position
            log.info(f"At max short position ({self.position:.3f}), stopping ask quotes")
        else:
            bid_size = round_size(max(min(adjusted_size, cfg.max_position - self.position), 0))
            ask_size = round_size(max(min(adjusted_size, cfg.max_position + self.position), 0))

        print(f"[QUOTE INFO] Position: {self.position:.4f}, "
              f"Bid: {bid_price:.2f} (spread: {bid_spread:.2f}bps, size: {bid_size:g})"
              f"{' [COOLDOWN]' if bid_in_cooldown else ' [RECOVERY]' if bid_in_recovery else ''}; "
              f"Ask: {ask_price:.2f} (spread: {ask_spread:.2f}bps, size: {ask_size:g})"
              f"{' [COOLDOWN]' if ask_in_cooldown else ' [RECOVERY]' if ask_in_recovery else ''}", flush=True)

        self.mid = new_mid

        # Handle cooldown and recovery logic
        if bid_in_cooldown:
            # Cancel existing bid quote using the proper cancel method
            await self.cancel_order_if_exists(str(cfg.quote_ids["bid"][0]), "bid")
        else:
            # Quote normally (including during recovery with increased spread)
            await self.adjust_order(Direction.BUY, bid_price, bid_size, str(cfg.quote_ids["bid"][0]))
            
        if ask_in_cooldown:
            # Cancel existing ask quote using the proper cancel method
            await self.cancel_order_if_exists(str(cfg.quote_ids["ask"][0]), "ask")
        else:
            # Quote normally (including during recovery with increased spread)
            await self.adjust_order(Direction.SELL, ask_price, ask_size, str(cfg.quote_ids["ask"][0]))

    async def adjust_order(self, side, price, amount, client_order_id):
        confirmed = self.quotes.get(client_order_id, {})
        status = confirmed.get("status", "")
        is_open = status in ["open", "partially_filled"]

        # Debug: Log the current state of this order
        log.debug(f"[ORDER_STATE] {side} order {client_order_id}: status='{status}', is_open={is_open}, confirmed={confirmed}")

        self.logger.log_adjust_order(side, price, amount, client_order_id, is_open, confirmed)
        
        # Convert client_order_id to integer for the API
        client_order_id_int = int(client_order_id)
        
        if is_open:
            if amount == 0 or abs(confirmed.get("price", 0) - price) > cfg.amend_threshold:
                print(f"Amending order {client_order_id} for {side} to {amount:g} @ {price:.2f}", flush=True)
                try:
                    self.logger.log_amend_attempt(client_order_id, side, amount, price)
                    await self.tlx.amend(
                        amount=amount,
                        price=price,
                        client_order_id=client_order_id_int,
                    )
                    self.logger.log_amend_success(client_order_id)
                except Exception as e:
                    # If we get "order not found", the order was already filled or cancelled
                    if "order not found" in str(e).lower():
                        log.debug(f"Order {client_order_id} not found during amend (likely already filled/cancelled)")
                        # Update local state and try to insert a new order if amount > 0
                        self.quotes[client_order_id] = {"status": "unknown", "price": price, "direction": side}
                        
                        # Debug: Dump all order states when we get this error
                        self.dump_order_states()
                        
                        if amount > 0:
                            await self._insert_new_order(side, price, amount, client_order_id, client_order_id_int)
                        return  # Stop trying to amend this order
                    else:
                        self.logger.log_error(f"Error amending order {client_order_id} for {side}: {e}", exc_info=True)
        elif amount > 0:
            await self._insert_new_order(side, price, amount, client_order_id, client_order_id_int)
        else:
            self.logger.log_no_insert(side, price, amount, client_order_id, is_open)
    
    async def _insert_new_order(self, side, price, amount, client_order_id, client_order_id_int):
        """Helper method to insert a new order"""
        print(f"Inserting order {client_order_id} for {side}: {amount:g} @ {price:.2f}", flush=True)
        self.logger.log_insert_attempt(side, price, amount, client_order_id, self.instrument_name)
        try:
            await self.tlx.insert(
                amount=amount,
                price=price,
                direction=side,
                instrument_name=self.instrument_name,
                client_order_id=client_order_id_int,
                label=cfg.order_label,
            )
            self.logger.log_insert_success(client_order_id, side, amount, price)
            self.quotes[client_order_id] = {"status": "open", "price": price, "direction": side}
        except Exception as e:
            self.logger.log_error(f"Error inserting order {client_order_id} for {side}: {e}", exc_info=True)

    async def cancel_order_if_exists(self, client_order_id: str, side: str):
        """Cancel an order if it exists and is open"""
        confirmed = self.quotes.get(client_order_id, {})
        status = confirmed.get("status", "")
        
        # Don't try to cancel orders that are already filled, cancelled, or don't exist
        if status in ["filled", "cancelled"]:
            log.debug(f"{side.capitalize()} order {client_order_id} already {status}, no cancellation needed")
            return
        
        # If we have no status or unknown status, try to refresh it first
        if status in ["", "unknown"]:
            log.debug(f"Refreshing status for {side} order {client_order_id}")
            await self.refresh_order_status(client_order_id)
            # Wait a bit for the response
            await asyncio.sleep(0.1)
            # Re-check the status
            confirmed = self.quotes.get(client_order_id, {})
            status = confirmed.get("status", "")
        
        # Only try to cancel if we think the order is open
        if status in ["open", "partially_filled"]:
            log.info(f"Cancelling {side} order {client_order_id} due to cooldown")
            try:
                # Convert client_order_id to integer for the API
                client_order_id_int = int(client_order_id)
                await self.tlx.cancel(client_order_id=client_order_id_int)
                # Update local state to reflect cancellation
                self.quotes[client_order_id] = {"status": "cancelled", "price": confirmed.get("price"), "direction": confirmed.get("direction")}
            except Exception as e:
                # If we get "order not found", the order was already filled or cancelled
                if "order not found" in str(e).lower():
                    log.debug(f"{side.capitalize()} order {client_order_id} not found (likely already filled/cancelled)")
                    # Update local state to reflect that the order is no longer active
                    self.quotes[client_order_id] = {"status": "unknown", "price": confirmed.get("price"), "direction": confirmed.get("direction")}
                else:
                    log.error(f"Error cancelling {side} order during cooldown: {e}")
        else:
            log.debug(f"{side.capitalize()} order {client_order_id} not open (status: {status}), no cancellation needed")

    async def quote(self):
        max_retries = 3
        retry_delay = 1  # seconds
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Connect and authenticate using websocket handler
                if not await self.websocket_handler.connect_and_authenticate():
                    self.logger.log_error("[CONNECTION] Failed to connect and authenticate!")
                    raise Exception("Connection and authentication failed")
                
                # Test connection and authentication
                self.logger.log_test("Testing connection and authentication...")
                if not await self.websocket_handler.test_connection(self.instrument_name):
                    self.logger.log_error("[TEST] Connection test failed! Check your credentials and network.")
                    raise Exception("Connection test failed")
                self.logger.log_test("Connection test passed!")

                # Start background tasks
                log.info("Starting background tasks...")
                vol_task = asyncio.create_task(self.update_volatility_loop())
                log_task = asyncio.create_task(self.log_loop())
                ticker_task = asyncio.create_task(self.websocket_handler.ticker_loop(self.instrument_name))
                account_summary_task = asyncio.create_task(self.websocket_handler.account_summary_loop())
                log.info("Background tasks started")

                # Start message processing using websocket handler
                await self.websocket_handler.start_message_processing()

                log.info("Main message loop ended, cleaning up tasks...")

                # Cleanup background tasks
                for task in [vol_task, log_task, ticker_task, account_summary_task]:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            log.error(f"Error cancelling task: {e}")

                await asyncio.gather(vol_task, log_task, ticker_task, account_summary_task, return_exceptions=True)

            except Exception as e:
                log.error(f"Fatal error in quote loop: {e}", exc_info=True)
            
            # Handle reconnection
            retry_count += 1
            if retry_count < max_retries:
                log.info(f"Connection lost. Retrying in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                log.error("Max retries reached. Giving up.")
                break

        # Final cleanup
        await self.websocket_handler.cleanup()

async def main():
    # Parse arguments to determine logging level
    args = parse_arguments()
    
    # Determine verbose mode (default to False/quiet)
    verbose = args.verbose
    if args.quiet:
        verbose = False
    
    if verbose:
        logging.basicConfig(level=logging.INFO)
        print("Starting Thalex Quoter Bot in VERBOSE mode...")
    else:
        logging.basicConfig(level=logging.WARNING)
        print("Starting Thalex Quoter Bot in QUIET mode...")
        print("Use --verbose or -v for detailed logging")
    
    quoter = None
    while True:  # Outer retry loop
        try:
            tlx = thalex.Thalex(network=cfg.network)
            quoter = Quoter(tlx, cfg.instrument, 0.0, verbose=verbose)
            await quoter.quote()
        except KeyboardInterrupt:
            log.info("Quoter stopped by user")
            break
        except Exception as e:
            log.error(f"Fatal error in main loop: {e}")
            await asyncio.sleep(5)  # Wait before restarting
            continue
        finally:
            if quoter:
                try:
                    await quoter.websocket_handler.cleanup()
                except Exception as e:
                    log.error(f"Error during final cleanup: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 