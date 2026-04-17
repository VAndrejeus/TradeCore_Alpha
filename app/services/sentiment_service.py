from __future__ import annotations

from typing import List

from app.models.market import Bar


class SentimentService:
    def score_price_reaction(self, bars: List[Bar]) -> float:
        if len(bars) < 2:
            return 0.0

        timeframe = bars[0].timeframe.lower()

        if timeframe == "1day":
            return self._score_swing_reaction(bars)

        return self._score_intraday_reaction(bars)

    def _score_intraday_reaction(self, bars: List[Bar]) -> float:
        if len(bars) < 2:
            return 0.0

        first = bars[0]
        last = bars[-1]

        if first.open <= 0:
            return 0.0

        move_pct = (last.close - first.open) / first.open
        score = 0.0

        if move_pct > 0.02:
            score += 15
        elif move_pct > 0.01:
            score += 10
        elif move_pct > 0.005:
            score += 5

        if move_pct < -0.01:
            score -= 10

        earlier_bars = bars[:-1]
        if earlier_bars:
            avg_volume = sum(bar.volume for bar in earlier_bars) / len(earlier_bars)
            if avg_volume > 0 and last.volume > avg_volume * 1.5:
                score += 5

        if last.close > last.open:
            score += 3

        return max(min(score, 25), 0.0)

    def _score_swing_reaction(self, bars: List[Bar]) -> float:
        if len(bars) < 3:
            return 0.0

        last = bars[-1]
        prev = bars[-2]
        first = bars[0]

        if prev.close <= 0 or first.close <= 0:
            return 0.0

        one_day_move = (last.close - prev.close) / prev.close
        multi_day_move = (last.close - first.close) / first.close

        score = 0.0

        if one_day_move > 0.03:
            score += 10
        elif one_day_move > 0.015:
            score += 7
        elif one_day_move > 0.005:
            score += 4

        if multi_day_move > 0.08:
            score += 8
        elif multi_day_move > 0.04:
            score += 5
        elif multi_day_move > 0.015:
            score += 3

        prior_bars = bars[:-1]
        avg_volume = sum(bar.volume for bar in prior_bars) / len(prior_bars)
        if avg_volume > 0 and last.volume > avg_volume * 1.25:
            score += 4

        if last.close > prev.high:
            score += 3
        elif last.close > prev.close:
            score += 2

        if last.close < prev.close and one_day_move < -0.02:
            score -= 8

        return max(min(score, 25), 0.0)