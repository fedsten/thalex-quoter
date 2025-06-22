# Thalex Quoter Bot — Full Behavioural Documentation

## What This Bot Does NOT Do

- **No Risk Management on Positions**: This bot does NOT implement any risk management logic on positions. There are no stop losses, take profits, or automatic position reductions. The bot will continue quoting and managing orders according to its logic, regardless of open position size, PnL, or market conditions, except for the configured max position limit.
- **No Liquidation Protection**: The bot does not monitor margin or liquidation risk. It assumes the user is responsible for monitoring account health.
- **No Hedging or Cross-Venue Management**: The bot does not hedge positions on other venues or instruments.
- **No Manual Intervention Logic**: There is no built-in way to manually flatten, pause, or intervene in the bot's trading logic from within the bot itself.

---

# Thalex Quoter Bot — Full Behavioural Documentation

## Overview

The Thalex Quoter is an automated market making bot for the Thalex exchange, designed to provide continuous bid/ask quotes on perpetual futures. It dynamically adjusts its quoting strategy based on market volatility, position, and recent fills, and logs all relevant trading and risk data.

---

## 1. Initialization & Configuration

- **Configuration** is loaded from `config.py` (instrument, network, spreads, size, cooldowns, etc).
- **API keys** are loaded from `keys.py`.
- **Volatility** is initialized from the constructor argument and updated periodically from an external monitor.
- **Logging**: On startup, a new CSV log file is created in `csv_logs/` with a header describing all parameters and data columns.

---

## 2. Main Event Loop

- The bot connects to Thalex via WebSocket and subscribes to:
  - `session.orders` (order status updates)
  - `account.portfolio` (position updates)
  - `trades` (trade notifications)
- It also starts background tasks for:
  - Volatility updates
  - Periodic logging
  - Ticker polling (for best bid/ask)
  - Account summary polling

---

## 3. Quoting Logic

### 3.1. Quote Calculation

- **Mid Price**: Calculated as the average of best bid and best ask from the order book.
- **Spread Calculation**:
  - `base_spread = min_spread_bps + (max_spread_bps - min_spread_bps) * clamped_volatility * volatility_multiplier`
  - Volatility is clamped to 100% to prevent excessive spreads.
- **Position Adjustment**:
  - The spread is increased quadratically as the position approaches `max_position`.
  - If position is positive, bid spread is increased; if negative, ask spread is increased.
- **Recovery State**:
  - After a fill, the relevant side enters a cooldown, then a recovery period with a wider spread (`recovery_spread_multiplier`).
- **Market Crossing Protection**:
  - The bot never quotes a bid above the best bid or an ask below the best ask.

### 3.2. Size Calculation

- **Size Scaling**: Order size is scaled down as volatility increases.
- **Position Limits**: If at max long, no bids are quoted; if at max short, no asks are quoted.

### 3.3. Order Management

- **Insert/Amend/Cancel**:
  - If an order is open and the new price differs by more than `amend_threshold`, it is amended.
  - If the new size is zero, the order is cancelled.
  - If no order exists and size > 0, a new order is inserted.
- **Order IDs**: All order IDs are strings, unique per side.

---

## 4. State Management

- **Position**: Updated from `account.portfolio` messages.
- **Order State**: Tracked in a local dictionary, updated from `session.orders`.
- **Cooldowns**: After a fill, the relevant side enters a cooldown and then a recovery period.
- **Fees**: Total fees paid are tracked and logged.

---

## 5. Volatility Handling

- **Initial Value**: Set from the constructor.
- **Updates**: Periodically fetched from an external volatility monitor.
- **Usage**: Directly affects spread and size scaling.

---

## 6. Logging

- **CSV Logging**: Every `log_interval` seconds, the bot logs:
  - Timestamp, mid price, position, bid/ask spreads, unrealized/realized PnL, total fees, volatility, size scale.
- **Console Logging**: Key events (fills, cooldowns, recovery, errors) are logged to the console.
- **[QUOTE INFO]**: Each quote update prints:
  ```
  [QUOTE INFO] Position: <pos>, Bid: <bid_price> (spread: <bid_spread>bps, size: <bid_size>); Ask: <ask_price> (spread: <ask_spread>bps, size: <ask_size>)
  ```
  with cooldown/recovery flags as appropriate.

---

## 7. PnL Tracking

- **REST Endpoint**: Periodically fetches account summary for realized/unrealized PnL.
- **WebSocket**: Also updates PnL from account summary messages.

---

## 8. Error Handling & Recovery

- **WebSocket Errors**: On connection loss, the bot attempts to reconnect with exponential backoff.
- **Task Cleanup**: On shutdown or error, all background tasks are cancelled and the session is closed cleanly.
- **Exception Logging**: All exceptions are logged with stack traces for debugging.

---

## 9. Safety Features

- **Position Limits**: Never exceeds `max_position` in either direction.
- **Spread Limits**: Spreads are always within configured min/max.
- **Cooldowns**: Prevents rapid requoting after fills.
- **Market Crossing Protection**: Never crosses the book.

---

## 10. Extensibility

- **Configurable**: All trading parameters are in `config.py`.
- **Modular**: Utility functions for rounding, fee calculation, and volatility are in `utils.py` and `volatility_monitor.py`.
- **PnL Calculation**: Can be extended to support more advanced analytics.

---

## 11. Example Log Output

```
[QUOTE INFO] Position: 0.120, Bid: 104895.00 (spread: 0.80bps, size: 0.01); Ask: 104905.00 (spread: 0.80bps, size: 0.01)
2025-06-19 10:52:02 - INFO - Spread components - Base: 0.50bps, Volatility: 30.29%, Base spread: 0.80bps, Position factor: 0.18, Final spreads - Bid: 0.95bps, Ask: 0.80bps
2025-06-19 10:52:02 - INFO - Logged state - Mid: 104900.00, Position: 0.120, Bid spread: 0.80bps, Ask spread: 0.80bps, Actual PnL (Unrealised/Realised): 12.34/5.67, Total fees: 0.25
```

---

## 12. Shutdown & Cleanup

- On exit (manual or error), all orders are cancelled, the session is closed, and all background tasks are stopped.

---

## 13. Limitations

- **No Order Book Depth Awareness**: Only best bid/ask are used for quoting.
- **No Advanced Inventory Management**: Position-based spread adjustment is quadratic, but not predictive.
- **No Hedging**: The bot does not hedge on other venues.

---

## 14. Customization

- To change quoting logic, edit the `update_quotes` method in `not_so_simple_quoter.py`.
- To add new risk checks, modify the relevant sections in the same file.

---

**For further details, see the code in `not_so_simple_quoter.py`, `config.py`, and `utils.py`.** 