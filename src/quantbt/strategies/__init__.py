"""Strategy implementations. Importing this package registers every built-in strategy."""

from . import (  # noqa: F401  (imported for registration side effects)
    bollinger_w,
    buy_and_hold,
    dual_thrust,
    ema_macd,
    heikin_ashi,
    london_breakout,
    macd,
    pair_trading,
    parabolic_sar,
    rsi_head_shoulders,
    shooting_star,
)
from .base import (
    IntradayStrategy,
    PairStrategy,
    PositionStrategy,
    Strategy,
    available_strategies,
    create_strategy,
    get_strategy_class,
    register,
)

__all__ = [
    "IntradayStrategy",
    "PairStrategy",
    "PositionStrategy",
    "Strategy",
    "available_strategies",
    "create_strategy",
    "get_strategy_class",
    "register",
]
