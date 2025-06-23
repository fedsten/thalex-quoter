# Thalex Quoter

A market making bot for the Thalex exchange, providing automated quoting for perpetual futures.

## Setup

### 1. Virtual Environment
The project includes a virtual environment. To activate it:

```bash
# Option 1: Use the activation script
source activate.sh

# Option 2: Manual activation
source venv/bin/activate
```

### 2. Dependencies
All dependencies are already installed in the virtual environment. If you need to reinstall:

```bash
pip install -r requirements.txt
```

### 3. Configuration
Edit `config.py` to customize your trading parameters:
- `network`: Choose between `Network.TEST` or `Network.PROD`
- `instrument`: Trading instrument (default: "BTC-PERPETUAL")
- `min_spread_bps` / `max_spread_bps`: Spread range in basis points
- `size`: Base order size
- `max_position`: Maximum position size

### 4. Authentication
**Important**: The `keys.py` file is gitignored for security. You need to create it:

```bash
# Copy the template and fill in your API keys
cp keys_template.py keys.py
```

Then edit `keys.py` with your Thalex API credentials:
- Get API keys from: https://testnet.thalex.com/exchange/user/api (TEST)
- Get API keys from: https://thalex.com/exchange/user/api (PROD)

## Usage

### Main Quoter
Run the main market making bot:

```bash
python not_so_simple_quoter.py
```

### Verbose Mode
For detailed logging and debugging:

```bash
python not_so_simple_quoter.py --verbose
```

### Quiet Mode
For minimal logging:

```bash
python not_so_simple_quoter.py --quiet
```

## Features

- **Automated Market Making**: Provides continuous bid/ask quotes
- **Volatility-Based Spreads**: Adjusts spreads based on market volatility
- **Position Management**: Automatically adjusts quotes based on current position
- **Cooldown Management**: Prevents rapid requoting after fills
- **Recovery Periods**: Gradually returns to normal spreads after cooldowns
- **Comprehensive Logging**: CSV logs with detailed trading data
- **PnL Tracking**: Real-time profit/loss monitoring
- **WebSocket Integration**: Real-time market data and order updates
- **Error Recovery**: Automatic reconnection and error handling

## File Structure

```
thalex-quoter/
├── not_so_simple_quoter.py   # Main quoter implementation
├── config.py                 # Configuration settings
├── keys_template.py          # Template for API keys
├── keys.py                   # API authentication keys (gitignored)
├── requirements.txt          # Python dependencies
├── pyproject.toml           # Project configuration
├── venv/                     # Virtual environment
├── csv_logs/                 # Trading logs
├── activate.sh               # Environment activation script
├── BOT_BEHAVIOR.md          # Detailed bot behavior documentation
└── README.md                 # This file
```

## Logging

The bot creates detailed CSV logs in the `csv_logs/` directory with timestamps. Logs include:
- Mid price, position, spreads
- Unrealized and realized PnL
- Total fees paid
- Volatility and size scaling

## Safety Features

- **Position Limits**: Automatic position size management
- **Spread Limits**: Configurable minimum/maximum spreads
- **Cooldown Periods**: Prevents excessive requoting after fills
- **Recovery Periods**: Gradual return to normal spreads
- **Market Crossing Protection**: Prevents crossing the market
- **Error Handling**: Robust error recovery and reconnection

## Development

To modify the quoter logic, edit `not_so_simple_quoter.py`. The main class `Quoter` contains all the market making logic.
