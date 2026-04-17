from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from app.models.market import Bar, CatalystEvent, PillarScores, TradeIdea


class SignalService:
    def generate_trade_idea(
        self,
        symbol: str,
        events: List[CatalystEvent],
        bars: List[Bar],
        sentiment_score: float,
        catalyst_service,
    ) -> TradeIdea | None:
        if not events or len(bars) < 5:
            return None

        timeframe = bars[0].timeframe.lower()

        for event in events:
            event.category = getattr(event, "category", "other") or "other"

        best_event = max(events, key=lambda e: catalyst_service.score_event_strength(e))
        catalyst_score = catalyst_service.score_event_strength(best_event)
        stack_bonus = self._compute_catalyst_stack_bonus(events, catalyst_service)

        if timeframe == "1day":
            return self._generate_swing_trade_idea(
                symbol=symbol,
                best_event=best_event,
                catalyst_score=catalyst_score,
                stack_bonus=stack_bonus,
                bars=bars,
                sentiment_score=sentiment_score,
            )

        return self._generate_intraday_trade_idea(
            symbol=symbol,
            best_event=best_event,
            catalyst_score=catalyst_score,
            stack_bonus=stack_bonus,
            bars=bars,
            sentiment_score=sentiment_score,
        )

    def get_trigger_price(self, bars: List[Bar], setup_type: str) -> float | None:
        if len(bars) < 2:
            return None

        timeframe = bars[0].timeframe.lower()

        if timeframe == "1day":
            return self._get_swing_trigger_price(bars, setup_type)

        return self._get_intraday_trigger_price(bars, setup_type)

    def _generate_intraday_trade_idea(
        self,
        symbol: str,
        best_event: CatalystEvent,
        catalyst_score: float,
        stack_bonus: float,
        bars: List[Bar],
        sentiment_score: float,
    ) -> TradeIdea | None:
        recent_bars = bars[-5:]
        last_bar = recent_bars[-1]
        prior_bars = recent_bars[:-1]

        recent_low = min(bar.low for bar in recent_bars)
        prior_high = max(bar.high for bar in prior_bars)
        avg_volume = sum(bar.volume for bar in recent_bars) / len(recent_bars)
        avg_range = sum((bar.high - bar.low) for bar in recent_bars) / len(recent_bars)

        technical_score = 0.0
        base_setup = ""

        breakout_trigger = prior_high * 0.9975
        reclaim_trigger = prior_high * 0.9925

        if last_bar.close >= breakout_trigger:
            base_setup = "breakout"
            technical_score += 12
            if last_bar.close > prior_high:
                technical_score += 4
        elif last_bar.close >= reclaim_trigger:
            base_setup = "reclaim"
            technical_score += 8
        elif last_bar.close > recent_low * 1.01:
            base_setup = "watch"
            technical_score += 4
        else:
            return None

        if last_bar.close > last_bar.open:
            technical_score += 3

        if avg_volume > 0 and last_bar.volume >= avg_volume:
            technical_score += 3

        if avg_range > 0 and (last_bar.high - last_bar.low) >= avg_range:
            technical_score += 2

        entry = last_bar.close
        stop = recent_low * 0.995

        return self._build_trade_idea(
            symbol=symbol,
            best_event=best_event,
            catalyst_score=catalyst_score,
            sentiment_score=sentiment_score,
            technical_score=technical_score,
            stack_bonus=stack_bonus,
            base_setup=base_setup,
            entry=entry,
            stop=stop,
            timeframe_label="intraday",
        )

    def _generate_swing_trade_idea(
        self,
        symbol: str,
        best_event: CatalystEvent,
        catalyst_score: float,
        stack_bonus: float,
        bars: List[Bar],
        sentiment_score: float,
    ) -> TradeIdea | None:
        recent_bars = bars[-5:]
        last_bar = recent_bars[-1]
        prior_bars = recent_bars[:-1]

        recent_low = min(bar.low for bar in recent_bars)
        prior_high = max(bar.high for bar in prior_bars)
        avg_volume = sum(bar.volume for bar in recent_bars) / len(recent_bars)

        technical_score = 0.0
        base_setup = ""

        breakout_trigger = prior_high * 0.995
        reclaim_trigger = prior_high * 0.985

        if last_bar.close >= breakout_trigger:
            base_setup = "breakout"
            technical_score += 11
            if last_bar.close > prior_high:
                technical_score += 4
        elif last_bar.close >= reclaim_trigger:
            base_setup = "reclaim"
            technical_score += 8
        elif last_bar.close > recent_low * 1.03:
            base_setup = "watch"
            technical_score += 5
        else:
            return None

        if last_bar.close > last_bar.open:
            technical_score += 2

        if avg_volume > 0 and last_bar.volume >= avg_volume:
            technical_score += 2

        if last_bar.close > prior_bars[-1].close:
            technical_score += 2

        entry = last_bar.close
        stop = recent_low * 0.99

        return self._build_trade_idea(
            symbol=symbol,
            best_event=best_event,
            catalyst_score=catalyst_score,
            sentiment_score=sentiment_score,
            technical_score=technical_score,
            stack_bonus=stack_bonus,
            base_setup=base_setup,
            entry=entry,
            stop=stop,
            timeframe_label="swing",
        )

    def _build_trade_idea(
        self,
        symbol: str,
        best_event: CatalystEvent,
        catalyst_score: float,
        sentiment_score: float,
        technical_score: float,
        stack_bonus: float,
        base_setup: str,
        entry: float,
        stop: float,
        timeframe_label: str,
    ) -> TradeIdea | None:
        if entry <= 0 or stop <= 0:
            return None

        risk = entry - stop
        if risk <= 0:
            return None

        target_1 = entry + (risk * 2.0)
        target_2 = entry + (risk * 3.0)
        total_score = catalyst_score + sentiment_score + technical_score + stack_bonus

        if total_score < 25:
            return None

        status = self._determine_status(
            total_score=total_score,
            catalyst_score=catalyst_score,
            sentiment_score=sentiment_score,
            technical_score=technical_score,
            stack_bonus=stack_bonus,
            timeframe_label=timeframe_label,
        )

        setup_type = self._format_setup_type(
            timeframe_label=timeframe_label,
            base_setup=base_setup,
            status=status,
        )

        if total_score >= 60:
            confidence = "high"
        elif total_score >= 45:
            confidence = "medium"
        else:
            confidence = "low"

        scores = PillarScores(
            catalyst=catalyst_score,
            sentiment=sentiment_score,
            fundamentals=0.0,
            technicals=technical_score,
        )

        thesis = (
            f"{best_event.headline} | "
            f"Catalyst {catalyst_score:.1f}/35, "
            f"Sentiment {sentiment_score:.1f}/25, "
            f"Technicals {technical_score:.1f}/20, "
            f"Stack {stack_bonus:.1f}, "
            f"Mode {timeframe_label}"
        )

        return TradeIdea(
            symbol=symbol,
            ts=datetime.now(timezone.utc),
            setup_type=setup_type,
            scores=scores,
            entry=entry,
            stop=stop,
            target_1=target_1,
            target_2=target_2,
            thesis=thesis,
            invalidation="Price loses recent support or momentum confirmation fails",
            catalyst_summary=best_event.headline,
            confidence=confidence,
            status=status,
        )

    def _determine_status(
        self,
        total_score: float,
        catalyst_score: float,
        sentiment_score: float,
        technical_score: float,
        stack_bonus: float,
        timeframe_label: str,
    ) -> str:
        if total_score >= 55 and catalyst_score >= 20:
            return "ready"

        if timeframe_label == "swing":
            if (
                catalyst_score >= 16
                and sentiment_score >= 7
                and technical_score >= 10
                and stack_bonus >= 4
                and total_score >= 42
            ):
                return "ready"

            if (
                catalyst_score >= 14
                and sentiment_score >= 4
                and technical_score >= 8
                and total_score >= 32
            ):
                return "watch"

            return "reject"

        if (
            catalyst_score >= 17
            and sentiment_score >= 10
            and technical_score >= 13
            and stack_bonus >= 4
            and total_score >= 46
        ):
            return "ready"

        if (
            catalyst_score >= 15
            and sentiment_score >= 8
            and technical_score >= 10
            and total_score >= 35
        ):
            return "watch"

        return "reject"

    def _format_setup_type(
        self,
        timeframe_label: str,
        base_setup: str,
        status: str,
    ) -> str:
        if timeframe_label == "swing":
            if status == "ready":
                if base_setup == "breakout":
                    return "swing_breakout_ready"
                if base_setup == "reclaim":
                    return "swing_reclaim_ready"
                return "swing_ready"

            if status == "watch":
                if base_setup == "breakout":
                    return "swing_breakout_watch"
                if base_setup == "reclaim":
                    return "swing_reclaim_watch"
                return "swing_watch"

            return "swing_reject"

        if status == "ready":
            if base_setup == "breakout":
                return "intraday_breakout_ready"
            if base_setup == "reclaim":
                return "intraday_reclaim_ready"
            return "intraday_ready"

        if status == "watch":
            if base_setup == "breakout":
                return "intraday_breakout_watch"
            if base_setup == "reclaim":
                return "intraday_reclaim_watch"
            return "intraday_watch"

        return "intraday_reject"

    def _get_intraday_trigger_price(self, bars: List[Bar], setup_type: str) -> float | None:
        if len(bars) < 2:
            return None

        recent_bars = bars[-5:]
        last_bar = recent_bars[-1]
        prior_bars = recent_bars[:-1]
        prior_high = max(bar.high for bar in prior_bars)

        if "breakout" in setup_type:
            return round(prior_high * 1.001, 2)

        if "reclaim" in setup_type:
            return round(prior_high * 0.998, 2)

        return round(last_bar.high * 1.001, 2)

    def _get_swing_trigger_price(self, bars: List[Bar], setup_type: str) -> float | None:
        if len(bars) < 2:
            return None

        recent_bars = bars[-5:]
        last_bar = recent_bars[-1]
        prior_bars = recent_bars[:-1]
        prior_high = max(bar.high for bar in prior_bars)

        if "breakout" in setup_type:
            return round(prior_high * 1.002, 2)

        if "reclaim" in setup_type:
            return round(prior_high * 0.999, 2)

        return round(last_bar.high * 1.002, 2)

    def _compute_catalyst_stack_bonus(
        self,
        events: List[CatalystEvent],
        catalyst_service,
    ) -> float:
        if not events:
            return 0.0

        scored_events: list[tuple[CatalystEvent, float]] = []
        for event in events:
            score = catalyst_service.score_event_strength(event)
            if score >= 15:
                scored_events.append((event, score))

        if not scored_events:
            return 0.0

        count = len(scored_events)
        categories = {event.category for event, _ in scored_events if getattr(event, "category", None)}

        bonus = 0.0

        if count >= 2:
            bonus += 5.0
        if count >= 3:
            bonus += 8.0
        if count >= 4:
            bonus += 10.0

        if len(categories) >= 2:
            bonus += 3.0
        if len(categories) >= 3:
            bonus += 5.0

        high_impact = [score for _, score in scored_events if score >= 25]
        if len(high_impact) >= 2:
            bonus += 4.0

        return min(bonus, 15.0)