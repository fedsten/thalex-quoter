from dataclasses import dataclass
from thalex.thalex import Network


@dataclass(frozen=True)
class QuoterConfig:
    # Network and instrument settings
    network: Network = Network.TEST
    instrument: str = "BTC-PERPETUAL"
    order_label: str = "simple_quoter"
    
    # Price and size ticks
    price_tick: float = 1.0  # USD
    size_tick: float = 0.001  # Contracts
    
    # Spread parameters
    min_spread_bps: float = 0.5  # Minimum spread in basis points
    max_spread_bps: float = 2.5  # Maximum spread in basis points
    volatility_multiplier: float = 0.5  # How much to adjust spread based on volatility
    
    # Cooldown parameters
    bid_fill_cooldown: float = 5.0  # seconds to wait after a bid fill before requoting bid side
    ask_fill_cooldown: float = 5.0  # seconds to wait after an ask fill before requoting ask side
    
    # Recovery parameters
    bid_fill_recovery: float = 30.0  # seconds after cooldown with increased spread
    ask_fill_recovery: float = 30.0  # seconds after cooldown with increased spread
    recovery_spread_multiplier: float = 3.0  # multiply normal spread by this factor during recovery
    
    # Order management
    amend_threshold: int = 5  # USD
    size: float = 0.01
    max_position: float = 0.3
    
    # Update intervals
    volatility_update_interval: int = 300  # Update volatility every 5 minutes
    log_interval: int = 5
    
    # Fee settings
    fee_rate_bps: float = 2.5  # 2.5 basis points = 0.00025
    
    # Quote IDs
    quote_ids: dict = None
    
    def __post_init__(self):
        if self.quote_ids is None:
            object.__setattr__(self, 'quote_ids', {
                "bid": [1001],
                "ask": [1002]
            })


# Global configuration instance
cfg = QuoterConfig() 