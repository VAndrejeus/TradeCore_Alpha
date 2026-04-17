from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any


@dataclass(slots=True)
class Quote:
    symbol: str
    bid: float
    ask: float
    bid_size: Optional[int]
    ask_size: Optional[int]
    ts: datetime
    source: str


@dataclass(slots=True)
class Trade:
    symbol: str
    price: float
    size: int
    ts: datetime
    source: str


@dataclass(slots=True)
class Bar:
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    ts: datetime
    source: str


@dataclass(slots=True)
class CatalystEvent:
    symbol: str
    event_id: str
    ts: datetime
    headline: str
    summary: str
    category: str
    raw_sentiment: Optional[float]
    source: str
    url: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PillarScores:
    catalyst: float
    sentiment: float
    fundamentals: float
    technicals: float

    @property
    def total(self) -> float:
        return self.catalyst + self.sentiment + self.fundamentals + self.technicals


@dataclass(slots=True)
class TradeIdea:
    symbol: str
    ts: datetime
    setup_type: str
    scores: PillarScores
    entry: float
    stop: float
    target_1: float
    target_2: float
    thesis: str
    invalidation: str
    catalyst_summary: str
    confidence: str
    status: str = "candidate"

    @property
    def risk_per_share(self) -> float:
        return max(self.entry - self.stop, 0.0)

    @property
    def reward_1_per_share(self) -> float:
        return max(self.target_1 - self.entry, 0.0)

    @property
    def reward_2_per_share(self) -> float:
        return max(self.target_2 - self.entry, 0.0)

    @property
    def rr_target_1(self) -> float:
        risk = self.risk_per_share
        if risk <= 0:
            return 0.0
        return self.reward_1_per_share / risk

    @property
    def rr_target_2(self) -> float:
        risk = self.risk_per_share
        if risk <= 0:
            return 0.0
        return self.reward_2_per_share / risk