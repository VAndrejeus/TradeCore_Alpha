from __future__ import annotations

from dataclasses import dataclass

from app.clients.alpaca_market_data import AlpacaMarketDataClient
from app.clients.finnhub_news import FinnhubNewsClient
from app.models.watchlist import Watchlist
from app.services.catalyst_service import CatalystService
from app.services.risk_service import RiskService
from app.services.sentiment_service import SentimentService
from app.services.signal_service import SignalService


@dataclass
class ScanRow:
    symbol: str
    status: str
    setup: str
    score: float
    trigger: float | None
    entry: float | None
    stop: float | None
    target_1: float | None
    target_2: float | None
    shares: int
    catalyst: str
    timeframe: str
    confidence: str
    note: str = ""


class ScanService:
    def __init__(
        self,
        alpaca: AlpacaMarketDataClient,
        finnhub: FinnhubNewsClient,
        catalyst_service: CatalystService,
        sentiment_service: SentimentService,
        signal_service: SignalService,
        risk_service: RiskService,
    ) -> None:
        self.alpaca = alpaca
        self.finnhub = finnhub
        self.catalyst_service = catalyst_service
        self.sentiment_service = sentiment_service
        self.signal_service = signal_service
        self.risk_service = risk_service

    def run_watchlist_scan(
        self,
        watchlist: Watchlist,
        intraday_timeframe: str,
        swing_timeframe: str,
        session_mode: str,
        catalyst_lookback_minutes: int,
        account_size: float,
        risk_per_trade_pct: float,
        max_position_pct: float,
    ) -> list[ScanRow]:
        results: list[ScanRow] = []

        for item in watchlist.items:
            symbol = item.symbol.upper().strip()
            if not symbol:
                continue

            raw_events = self.finnhub.get_company_news(symbol, catalyst_lookback_minutes)
            events = self.catalyst_service.filter_events(raw_events)

            if not events:
                results.append(
                    ScanRow(
                        symbol=symbol,
                        status="no_catalyst",
                        setup="none",
                        score=0.0,
                        trigger=None,
                        entry=None,
                        stop=None,
                        target_1=None,
                        target_2=None,
                        shares=0,
                        catalyst="No valid catalysts",
                        timeframe="none",
                        confidence="none",
                        note=item.note,
                    )
                )
                continue

            best_event = max(events, key=lambda e: self.catalyst_service.score_event_strength(e))
            bars, timeframe_used = self._get_best_available_bars(
                symbol=symbol,
                intraday_timeframe=intraday_timeframe,
                swing_timeframe=swing_timeframe,
                session_mode=session_mode,
            )

            if len(bars) < 5:
                results.append(
                    ScanRow(
                        symbol=symbol,
                        status="no_data",
                        setup="none",
                        score=0.0,
                        trigger=None,
                        entry=None,
                        stop=None,
                        target_1=None,
                        target_2=None,
                        shares=0,
                        catalyst=best_event.headline,
                        timeframe="none",
                        confidence="none",
                        note=item.note,
                    )
                )
                continue

            sentiment = self.sentiment_service.score_price_reaction(bars)
            idea = self.signal_service.generate_trade_idea(
                symbol=symbol,
                events=events,
                bars=bars,
                sentiment_score=sentiment,
                catalyst_service=self.catalyst_service,
            )

            if idea is None:
                results.append(
                    ScanRow(
                        symbol=symbol,
                        status="reject",
                        setup="none",
                        score=0.0,
                        trigger=None,
                        entry=None,
                        stop=None,
                        target_1=None,
                        target_2=None,
                        shares=0,
                        catalyst=best_event.headline,
                        timeframe=timeframe_used,
                        confidence="none",
                        note=item.note,
                    )
                )
                continue

            trigger_price = self.signal_service.get_trigger_price(bars, idea.setup_type)
            position_plan = self.risk_service.build_position_plan(
                entry=idea.entry,
                stop=idea.stop,
                account_size=account_size,
                risk_per_trade_pct=risk_per_trade_pct,
                max_position_pct=max_position_pct,
                bars=bars,
                atr_multiple=1.5,
                use_atr_stop=True,
            )

            results.append(
                ScanRow(
                    symbol=symbol,
                    status=idea.status,
                    setup=idea.setup_type,
                    score=idea.scores.total,
                    trigger=trigger_price,
                    entry=idea.entry,
                    stop=idea.stop,
                    target_1=idea.target_1,
                    target_2=idea.target_2,
                    shares=position_plan.shares_final if position_plan else 0,
                    catalyst=best_event.headline,
                    timeframe=timeframe_used,
                    confidence=idea.confidence,
                    note=item.note,
                )
            )

        return sorted(results, key=lambda row: row.score, reverse=True)

    def _get_best_available_bars(
        self,
        symbol: str,
        intraday_timeframe: str,
        swing_timeframe: str,
        session_mode: str,
    ) -> tuple[list, str]:
        if session_mode == "intraday":
            primary_timeframe = intraday_timeframe
            secondary_timeframe = swing_timeframe
            primary_limit = 20
            secondary_limit = 10
        else:
            primary_timeframe = swing_timeframe
            secondary_timeframe = intraday_timeframe
            primary_limit = 10
            secondary_limit = 20

        primary_bars = self.alpaca.get_bars(symbol, primary_timeframe, limit=primary_limit)
        if len(primary_bars) >= 5:
            return primary_bars, primary_timeframe

        secondary_bars = self.alpaca.get_bars(symbol, secondary_timeframe, limit=secondary_limit)
        if len(secondary_bars) >= 5:
            return secondary_bars, secondary_timeframe

        return [], "none"