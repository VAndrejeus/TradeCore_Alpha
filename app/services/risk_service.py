from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.models.market import Bar


@dataclass(slots=True)
class PositionPlan:
    account_size: float
    risk_per_trade_pct: float
    max_position_pct: float
    dollar_risk: float
    risk_per_share: float
    shares_by_risk: int
    shares_by_capital: int
    shares_final: int
    capital_required: float
    atr_value: float
    atr_stop: float
    stop_method: str


class RiskService:
    def build_position_plan(
        self,
        entry: float,
        stop: float,
        account_size: float,
        risk_per_trade_pct: float,
        max_position_pct: float,
        bars: List[Bar] | None = None,
        atr_multiple: float = 1.5,
        use_atr_stop: bool = True,
    ) -> PositionPlan | None:
        if entry <= 0 or stop <= 0 or account_size <= 0:
            return None

        atr_value = 0.0
        atr_stop = stop
        stop_method = "price_structure"

        if use_atr_stop and bars:
            atr_value = self.calculate_atr(bars, period=5)
            if atr_value > 0:
                candidate_stop = entry - (atr_value * atr_multiple)

                if candidate_stop > 0:
                    # Only use ATR if it's reasonably close to structure
                    distance_structure = entry - stop
                    distance_atr = entry - candidate_stop

                    if 0.5 <= (distance_atr / distance_structure) <= 1.5:
                        atr_stop = candidate_stop
                        stop_method = "atr"

        if stop_method == "atr":
            final_stop = max(stop, atr_stop)
        else:
            final_stop = stop

        risk_per_share = entry - final_stop
        if risk_per_share <= 0:
            return None

        dollar_risk = account_size * risk_per_trade_pct
        max_position_dollars = account_size * max_position_pct

        shares_by_risk = int(dollar_risk // risk_per_share)
        shares_by_capital = int(max_position_dollars // entry)
        shares_final = min(shares_by_risk, shares_by_capital)

        if shares_final <= 0:
            return None

        capital_required = shares_final * entry

        return PositionPlan(
            account_size=account_size,
            risk_per_trade_pct=risk_per_trade_pct,
            max_position_pct=max_position_pct,
            dollar_risk=dollar_risk,
            risk_per_share=risk_per_share,
            shares_by_risk=shares_by_risk,
            shares_by_capital=shares_by_capital,
            shares_final=shares_final,
            capital_required=capital_required,
            atr_value=atr_value,
            atr_stop=final_stop if stop_method == "atr" else 0.0,
            stop_method=stop_method,
        )

    def calculate_atr(self, bars: List[Bar], period: int = 5) -> float:
        if len(bars) < 2:
            return 0.0

        recent_bars = bars[-(period + 1):]
        if len(recent_bars) < 2:
            return 0.0

        true_ranges: list[float] = []

        for idx in range(1, len(recent_bars)):
            current_bar = recent_bars[idx]
            previous_bar = recent_bars[idx - 1]

            high_low = current_bar.high - current_bar.low
            high_prev_close = abs(current_bar.high - previous_bar.close)
            low_prev_close = abs(current_bar.low - previous_bar.close)

            true_range = max(high_low, high_prev_close, low_prev_close)
            true_ranges.append(true_range)

        if not true_ranges:
            return 0.0

        return sum(true_ranges) / len(true_ranges)