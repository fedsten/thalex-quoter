import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import cfg

# Module-level logger
log = logging.getLogger(__name__)

class QuoterLogger:
    """Dedicated logging class for the Thalex Quoter Bot"""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.log_path = None
        self.setup_csv_logging()
    
    def setup_csv_logging(self):
        """Setup CSV logging file"""
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_filename = f"csv_logs/market_maker_log_{timestamp_str}.csv"
        self.log_path = Path(__file__).resolve().parent / log_filename
        
        # Create csv_logs directory if it doesn't exist
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Write parameter header and data columns
        with self.log_path.open("w", newline="") as f:
            writer = csv.writer(f)
            # Write parameter section
            writer.writerow(["Parameter", "Value"])
            writer.writerow(["instrument", cfg.instrument])
            writer.writerow(["network", cfg.network.name])
            writer.writerow(["min_spread_bps", cfg.min_spread_bps])
            writer.writerow(["max_spread_bps", cfg.max_spread_bps])
            writer.writerow(["volatility_multiplier", cfg.volatility_multiplier])
            writer.writerow(["bid_fill_cooldown", cfg.bid_fill_cooldown])
            writer.writerow(["ask_fill_cooldown", cfg.ask_fill_cooldown])
            writer.writerow(["bid_fill_recovery", cfg.bid_fill_recovery])
            writer.writerow(["ask_fill_recovery", cfg.ask_fill_recovery])
            writer.writerow(["recovery_spread_multiplier", cfg.recovery_spread_multiplier])
            writer.writerow(["amend_threshold", cfg.amend_threshold])
            writer.writerow(["base_size", cfg.size])
            writer.writerow(["max_position", cfg.max_position])
            writer.writerow(["volatility_update_interval", cfg.volatility_update_interval])
            writer.writerow(["log_interval", cfg.log_interval])
            writer.writerow(["fee_rate_bps", cfg.fee_rate_bps])
            writer.writerow(["start_time", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")])
            writer.writerow([])  # Empty row as separator
            # Write data header
            writer.writerow([
                "timestamp", "mid_price", "position", "bid_spread", "ask_spread",
                "unrealised_pnl", "realised_pnl", "total_fees_paid",
                "volatility", "size_scale"
            ])
    
    def log_websocket_message(self, msg):
        """Log websocket messages based on verbose mode"""
        if self.verbose:
            log.info(f"[WEBSOCKET_RECEIVED] Raw message: {msg}")
        else:
            log.debug(f"[WEBSOCKET_RECEIVED] Raw message: {msg}")
    
    def log_notification(self, channel: str, notification):
        """Log notification messages based on verbose mode"""
        if self.verbose:
            log.info(f"[HANDLE_NOTIFICATION] channel={channel}, notification={notification}")
        else:
            log.debug(f"[HANDLE_NOTIFICATION] channel={channel}, notification={notification}")
    
    def log_orders_update(self, notification):
        """Log order updates based on verbose mode"""
        if self.verbose:
            log.info(f"[ORDERS_UPDATE] Received {len(notification)} order updates: {notification}")
        else:
            log.debug(f"[ORDERS_UPDATE] Received {len(notification)} order updates")
    
    def log_order_status(self, cid, status, order=None):
        """Log individual order status based on verbose mode"""
        if self.verbose:
            log.info(f"[ORDER_STATUS] client_order_id={cid}, status={status}, order={order}")
        else:
            log.debug(f"[ORDER_STATUS] client_order_id={cid}, status={status}")
    
    def log_portfolio_update(self, notification):
        """Log portfolio updates based on verbose mode"""
        if self.verbose:
            log.info(f"[PORTFOLIO_UPDATE] Received portfolio update: {notification}")
        else:
            log.debug(f"[PORTFOLIO_UPDATE] Received portfolio update")
    
    def log_position_update(self, position):
        """Log position updates based on verbose mode"""
        if self.verbose:
            log.info(f"[POSITION_UPDATE] Position updated to: {position}")
        else:
            log.debug(f"[POSITION_UPDATE] Position updated to: {position}")
    
    def log_trades_update(self, notification):
        """Log trades updates based on verbose mode"""
        if self.verbose:
            log.info(f"[TRADES_UPDATE] Received trades update: {notification}")
        else:
            log.debug(f"[TRADES_UPDATE] Received trades update")
    
    def log_account_summary(self, notification):
        """Log account summary updates based on verbose mode"""
        if self.verbose:
            log.info(f"[ACCOUNT_SUMMARY] Received account summary: {notification}")
        else:
            log.debug(f"[ACCOUNT_SUMMARY] Received account summary")
    
    def log_adjust_order(self, side, price, amount, client_order_id, is_open, confirmed=None):
        """Log order adjustment attempts based on verbose mode"""
        if self.verbose:
            log.info(f"[ADJUST_ORDER] side={side}, price={price}, amount={amount}, client_order_id={client_order_id}, is_open={is_open}, confirmed={confirmed}")
        else:
            log.debug(f"[ADJUST_ORDER] side={side}, price={price}, amount={amount}, client_order_id={client_order_id}, is_open={is_open}")
    
    def log_amend_attempt(self, client_order_id, side, amount, price):
        """Log amend attempts based on verbose mode"""
        if self.verbose:
            log.info(f"[AMEND_ATTEMPT] Amending order {client_order_id} for {side}: {amount:g} @ {price:.2f}")
        else:
            log.debug(f"[AMEND_ATTEMPT] Amending order {client_order_id} for {side}: {amount:g} @ {price:.2f}")
    
    def log_amend_success(self, client_order_id):
        """Log successful amends based on verbose mode"""
        if self.verbose:
            log.info(f"[AMEND_SUCCESS] Order {client_order_id} amended successfully")
        else:
            log.debug(f"[AMEND_SUCCESS] Order {client_order_id} amended successfully")
    
    def log_insert_attempt(self, side, price, amount, client_order_id, instrument_name):
        """Log insert attempts based on verbose mode"""
        if self.verbose:
            log.info(f"[INSERT_ATTEMPT] side={side}, price={price}, amount={amount}, client_order_id={client_order_id}, instrument={instrument_name}")
        else:
            log.debug(f"[INSERT_ATTEMPT] side={side}, price={price}, amount={amount}, client_order_id={client_order_id}, instrument={instrument_name}")
    
    def log_insert_success(self, client_order_id, side, amount, price):
        """Log successful inserts based on verbose mode"""
        if self.verbose:
            log.info(f"[INSERT_SUCCESS] Order inserted: {client_order_id} for {side} {amount:g} @ {price:.2f}")
        else:
            log.debug(f"[INSERT_SUCCESS] Order inserted: {client_order_id} for {side} {amount:g} @ {price:.2f}")
    
    def log_no_insert(self, side, price, amount, client_order_id, is_open):
        """Log when orders are not inserted based on verbose mode"""
        if self.verbose:
            log.info(f"[NO_INSERT] Not inserting order: side={side}, price={price}, amount={amount}, client_order_id={client_order_id}, is_open={is_open}")
        else:
            log.debug(f"[NO_INSERT] Not inserting order: side={side}, price={price}, amount={amount}, client_order_id={client_order_id}, is_open={is_open}")
    
    def log_result(self, result):
        """Log API results based on verbose mode"""
        if self.verbose:
            log.info(f"[RESULT] Received result: {result}")
        else:
            log.debug(f"[RESULT] Received result")
    
    def log_unknown_message(self, msg):
        """Log unknown message formats based on verbose mode"""
        if self.verbose:
            log.info(f"[UNKNOWN_MSG] Unknown message format: {msg}")
        else:
            log.debug(f"[UNKNOWN_MSG] Unknown message format: {msg}")
    
    def log_connection_test(self, message: str):
        """Log connection test messages"""
        log.info(f"[CONNECTION_TEST] {message}")
    
    def log_connection(self, message: str):
        """Log connection messages"""
        log.info(f"[CONNECTION] {message}")
    
    def log_auth(self, message: str):
        """Log authentication messages"""
        log.info(f"[AUTH] {message}")
    
    def log_subscription(self, message: str):
        """Log subscription messages"""
        log.info(f"[SUBSCRIPTION] {message}")
    
    def log_test(self, message: str):
        """Log test messages"""
        log.info(f"[TEST] {message}")
    
    def log_ticker(self, timestamp: str, mid_price: float):
        """Log ticker updates"""
        log.info(f"[TICKER] {timestamp} Mid = {mid_price:.2f}")
    
    def log_error(self, message: str, exc_info: bool = False):
        """Log error messages"""
        log.error(message, exc_info=exc_info)
    
    def log_warning(self, message: str):
        """Log warning messages"""
        log.warning(message)
    
    def log_info(self, message: str):
        """Log info messages"""
        log.info(message)
    
    def log_debug(self, message: str):
        """Log debug messages"""
        log.debug(message)
    
    def write_csv_log(self, timestamp: str, mid: Optional[float], position: Optional[float], 
                     last_bid_spread: Optional[float], last_ask_spread: Optional[float],
                     unrealised_pnl: Optional[float], realised_pnl: Optional[float],
                     total_fees_paid: float, current_volatility: Optional[float], size_scale: float):
        """Write data to CSV log file"""
        try:
            with self.log_path.open("a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    mid if mid is not None else "",
                    position if position is not None else "",
                    last_bid_spread if last_bid_spread is not None else "",
                    last_ask_spread if last_ask_spread is not None else "",
                    unrealised_pnl if unrealised_pnl is not None else "",
                    realised_pnl if realised_pnl is not None else "",
                    total_fees_paid,
                    current_volatility if current_volatility is not None else "",
                    size_scale
                ])
        except Exception as e:
            log.error(f"Error writing to CSV log: {e}")
    
    def log_state_summary(self, current_volatility: Optional[float], mid: Optional[float], 
                         position: Optional[float], last_bid_spread: Optional[float], 
                         last_ask_spread: Optional[float], unrealised_pnl: Optional[float], 
                         realised_pnl: Optional[float], total_fees_paid: float):
        """Log state summary for console output"""
        vol_str = f"{current_volatility:.2%}" if current_volatility is not None else "None"
        mid_str = f"{mid:.2f}" if mid is not None else "None"
        pos_str = f"{position:.3f}" if position is not None else "None"
        bid_spread_str = f"{last_bid_spread:.2f}" if last_bid_spread is not None else "None"
        ask_spread_str = f"{last_ask_spread:.2f}" if last_ask_spread is not None else "None"
        unrealised_pnl_str = f"{unrealised_pnl:.2f}" if unrealised_pnl is not None else "None"
        realised_pnl_str = f"{realised_pnl:.2f}" if realised_pnl is not None else "None"
        
        log.info(f"Current ATM Volatility (from Quoter): {vol_str}")
        log.info(f"Logged state - Mid: {mid_str}, Position: {pos_str}, "
               f"Bid spread: {bid_spread_str}bps, Ask spread: {ask_spread_str}bps, "
               f"Actual PnL (Unrealised/Realised): {unrealised_pnl_str}/{realised_pnl_str}, "
               f"Total fees: {total_fees_paid:.2f}") 