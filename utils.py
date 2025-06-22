import logging
from typing import Optional
from config import cfg

# Module-level logger
log = logging.getLogger(__name__)


def round_to_tick(value: float) -> float:
    """Round a price value to the nearest tick size."""
    return cfg.price_tick * round(value / cfg.price_tick)


def round_size(size: float) -> float:
    """Round a size value to the nearest size tick."""
    return cfg.size_tick * round(size / cfg.size_tick)


def calculate_fee_amount(amount: float, price: float) -> float:
    """Calculate the fee amount for a trade."""
    fee_rate = cfg.fee_rate_bps / 10000  # Convert bps to decimal
    return abs(amount * price * fee_rate)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min(value, max_val), min_val) 