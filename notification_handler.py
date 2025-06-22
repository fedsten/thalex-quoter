import logging
import time
from typing import Optional, Any, Callable
from datetime import datetime, timezone

from config import cfg
from utils import calculate_fee_amount

log = logging.getLogger(__name__)

class NotificationHandler:
    def __init__(self, logger, instrument_name: str, 
                 on_order_update: Callable[[str, dict], None],
                 on_position_update: Callable[[float], None],
                 on_trade_update: Callable[[], None],
                 on_pnl_update: Callable[[Optional[float], Optional[float]], None],
                 on_ticker_update: Callable[[float, Optional[float], Optional[float]], None]):
        """
        Initialize the notification handler.
        
        Args:
            logger: Logger instance for logging notifications
            instrument_name: The instrument being traded
            on_order_update: Callback when order status changes
            on_position_update: Callback when position changes
            on_trade_update: Callback when trades occur
            on_pnl_update: Callback when PnL values change
            on_ticker_update: Callback when ticker data arrives
        """
        self.logger = logger
        self.instrument_name = instrument_name
        self.on_order_update = on_order_update
        self.on_position_update = on_position_update
        self.on_trade_update = on_trade_update
        self.on_pnl_update = on_pnl_update
        self.on_ticker_update = on_ticker_update

    async def handle_notification(self, channel: str, notification: Any):
        """Handle incoming websocket notifications"""
        self.logger.log_notification(channel, notification)
        
        if channel == "session.orders":
            await self._handle_orders_update(notification)
        elif channel == "account.portfolio":
            await self._handle_portfolio_update(notification)
        elif channel == "trades":
            await self._handle_trades_update(notification)
        elif channel == "account.summary":
            await self._handle_account_summary(notification)
        elif channel == "ticker":
            await self._handle_ticker_update(notification)

    async def _handle_orders_update(self, notification: list):
        """Handle session.orders channel updates"""
        self.logger.log_orders_update(notification)
        
        for order in notification:
            cid = order.get("client_order_id")
            status = order.get("status")
            self.logger.log_order_status(cid, status, order)
            
            # Debug: Log all order status updates
            log.debug(f"[ORDER_UPDATE] Order {cid}: status='{status}', order={order}")
            
            if cid:
                # Calculate fee impact for fills
                if status == "filled":
                    current_time = time.time()
                    fee_amount = calculate_fee_amount(order.get("amount", 0), order.get("price", 0))
                    
                    # Call the order update callback with fill information
                    self.on_order_update(str(cid), {
                        "status": status,
                        "order": order,
                        "fill_time": current_time,
                        "fee_amount": fee_amount
                    })
                else:
                    # Call the order update callback for non-fill updates
                    self.on_order_update(str(cid), {
                        "status": status,
                        "order": order
                    })
                
                # Log any status changes for debugging
                if status in ["cancelled", "rejected"]:
                    log.info(f"Order {cid} {status}")

    async def _handle_portfolio_update(self, notification: list):
        """Handle account.portfolio channel updates"""
        self.logger.log_portfolio_update(notification)
        
        try:
            position = next(p for p in notification if p["instrument_name"] == self.instrument_name)["position"]
            self.logger.log_position_update(position)
            self.on_position_update(position)
        except StopIteration:
            # No position found for this instrument, keep current position
            self.logger.log_warning(f"[POSITION_NOT_FOUND] No position found for {self.instrument_name}")
            # Don't call on_position_update since we don't have a new position

    async def _handle_trades_update(self, notification: dict):
        """Handle trades channel updates"""
        self.logger.log_trades_update(notification)
        
        for trade in notification.get("trades", []):
            if trade["instrument"] == self.instrument_name and trade["label"] == cfg.order_label:
                # Call the trade update callback
                self.on_trade_update()
                break

    async def _handle_account_summary(self, notification: dict):
        """Handle account.summary channel updates"""
        self.logger.log_account_summary(notification)
        
        if isinstance(notification, dict) and "result" in notification:
            result = notification["result"]
            unrealised_pnl = result.get("unrealised_pnl")
            realised_pnl = result.get("session_realised_pnl")
            
            log.debug(f"Updated PnL values - Actual: {unrealised_pnl}, {realised_pnl}")
            
            # Call the PnL update callback
            self.on_pnl_update(unrealised_pnl, realised_pnl)

    async def _handle_ticker_update(self, notification: dict):
        """Handle ticker channel updates"""
        if isinstance(notification, dict) and "best_bid_price" in notification and "best_ask_price" in notification:
            best_bid = notification["best_bid_price"]
            best_ask = notification["best_ask_price"]
            mid_price = (best_bid + best_ask) / 2
            
            self.logger.log_ticker(datetime.now(timezone.utc).strftime('%d/%m/%y %H:%M:%S'), mid_price)
            
            # Call the ticker update callback
            self.on_ticker_update(mid_price, best_bid, best_ask) 