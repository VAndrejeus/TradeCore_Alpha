import logging
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from app.clients.alpaca_market_data import AlpacaMarketDataClient
from app.clients.finnhub_news import FinnhubNewsClient
from app.config import Settings
from app.services.catalyst_service import CatalystService
from app.services.risk_service import RiskService
from app.services.sentiment_service import SentimentService
from app.services.signal_service import SignalService


EASTERN_TZ = ZoneInfo("America/New_York")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def ensure_data_dir(database_path: str) -> None:
    db_path = Path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)


def is_regular_market_open(now_et: datetime) -> bool:
    if now_et.weekday() >= 5:
        return False

    market_open = time(9, 30)
    market_close = time(16, 0)
    current_time = now_et.time()

    return market_open <= current_time < market_close


def get_session_mode(now_et: datetime) -> str:
    if is_regular_market_open(now_et):
        return "intraday"

    if now_et.weekday() >= 5:
        return "weekend_swing"

    return "after_hours_swing"


def print_startup_banner(settings: Settings, now_local: datetime, now_et: datetime, session_mode: str) -> None:
    print("=" * 72)
    print(settings.app_name)
    print("=" * 72)
    print(f"Scan Symbols: {', '.join(settings.scan_symbols)}")
    print(f"Account Size: ${settings.account_size:,.2f}")
    print(f"Risk/Trade : {settings.risk_per_trade_pct * 100:.2f}%")
    print(f"Max Position: {settings.max_position_pct * 100:.2f}%")
    print(f"Local Time: {now_local.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"ET Time   : {now_et.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Session Mode: {session_mode}")
    print("=" * 72)


def get_best_available_bars(
    alpaca: AlpacaMarketDataClient,
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

    primary_bars = alpaca.get_bars(symbol, primary_timeframe, limit=primary_limit)
    if len(primary_bars) >= 5:
        return primary_bars, primary_timeframe

    secondary_bars = alpaca.get_bars(symbol, secondary_timeframe, limit=secondary_limit)
    if len(secondary_bars) >= 5:
        return secondary_bars, secondary_timeframe

    return [], "none"


def format_status_label(status: str) -> str:
    mapping = {
        "ready": "READY",
        "watch": "WATCH",
        "reject": "REJECT",
    }
    return mapping.get(status, status.upper())


def format_setup_label(setup_type: str) -> str:
    return setup_type.replace("_", " ").title()


def format_trigger_line(trigger_price: float | None, status: str) -> str:
    if trigger_price is None:
        return "N/A"

    if status == "ready":
        return f"Ready above {trigger_price:.2f}"

    if status == "watch":
        return f"Watch for move above {trigger_price:.2f}"

    return f"Needs reclaim above {trigger_price:.2f}"


def run() -> None:
    settings = Settings.from_env()
    settings.validate()
    ensure_data_dir(settings.database_path)

    configure_logging(settings.log_level)

    now_local = datetime.now()
    now_et = datetime.now(EASTERN_TZ)
    session_mode = get_session_mode(now_et)

    print_startup_banner(settings, now_local, now_et, session_mode)

    alpaca = AlpacaMarketDataClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        trading_base_url=settings.alpaca_base_url,
        data_base_url=settings.alpaca_data_url,
        data_feed=settings.alpaca_data_feed,
    )

    finnhub = FinnhubNewsClient(
        api_key=settings.finnhub_api_key,
        base_url=settings.finnhub_base_url,
    )

    catalyst_service = CatalystService()
    sentiment_service = SentimentService()
    signal_service = SignalService()
    risk_service = RiskService()

    ready_ideas = []
    watch_ideas = []

    for symbol in settings.scan_symbols:
        print(f"\n--- {symbol} ---")

        raw_events = finnhub.get_company_news(symbol, settings.catalyst_lookback_minutes)
        events = catalyst_service.filter_events(raw_events)

        if not events:
            print("No valid catalysts")
            continue

        best_event = max(events, key=lambda e: catalyst_service.score_event_strength(e))
        catalyst_score = catalyst_service.score_event_strength(best_event)

        bars, bars_timeframe = get_best_available_bars(
            alpaca=alpaca,
            symbol=symbol,
            intraday_timeframe=settings.intraday_timeframe,
            swing_timeframe=settings.swing_timeframe,
            session_mode=session_mode,
        )

        if len(bars) < 5:
            print("Not enough bar data from preferred or fallback timeframe")
            continue

        sentiment = sentiment_service.score_price_reaction(bars)

        idea = signal_service.generate_trade_idea(
            symbol=symbol,
            events=events,
            bars=bars,
            sentiment_score=sentiment,
            catalyst_service=catalyst_service,
        )

        print(f"Bars used: {len(bars)} ({bars_timeframe})")
        print(f"Filtered catalysts: {len(events)}")
        print(f"Catalyst score: {catalyst_score:.1f}/35")
        print(f"Sentiment score: {sentiment:.1f}/25")
        print(f"Lead catalyst: {best_event.headline}")

        print("Top catalysts:")
        for event in events[:3]:
            strength = catalyst_service.score_event_strength(event)
            print(f"  - {strength:.1f}/35 | {event.headline}")

        if idea is None:
            print("Trade plan: none")
            continue

        trigger_price = signal_service.get_trigger_price(bars, idea.setup_type)

        position_plan = risk_service.build_position_plan(
            entry=idea.entry,
            stop=idea.stop,
            account_size=settings.account_size,
            risk_per_trade_pct=settings.risk_per_trade_pct,
            max_position_pct=settings.max_position_pct,
            bars=bars,
            atr_multiple=1.5,
            use_atr_stop=True,
        )

        print("Trade plan:")
        print(f"  Setup: {format_setup_label(idea.setup_type)}")
        print(f"  Status: {format_status_label(idea.status)}")
        print(f"  Confidence: {idea.confidence.title()}")
        print(f"  Trigger: {format_trigger_line(trigger_price, idea.status)}")
        print(f"  Total score: {idea.scores.total:.1f}")
        print(f"  Entry: {idea.entry:.2f}")
        print(f"  Stop: {idea.stop:.2f}")
        print(f"  Target 1: {idea.target_1:.2f}")
        print(f"  Target 2: {idea.target_2:.2f}")
        print(f"  Reward/Risk to Target 1: {idea.rr_target_1:.2f}")
        print(f"  Reward/Risk to Target 2: {idea.rr_target_2:.2f}")
        print(f"  Invalidation: {idea.invalidation}")

        if position_plan is not None:
            print("  Position sizing:")
            print(f"    Dollar risk budget: ${position_plan.dollar_risk:.2f}")
            print(f"    Risk per share: ${position_plan.risk_per_share:.2f}")
            print(f"    Shares by risk: {position_plan.shares_by_risk}")
            print(f"    Shares by capital cap: {position_plan.shares_by_capital}")
            print(f"    Final shares: {position_plan.shares_final}")
            print(f"    Capital required: ${position_plan.capital_required:.2f}")
            print(f"    Stop method: {position_plan.stop_method}")
            print(f"    ATR(5): ${position_plan.atr_value:.2f}")
            if position_plan.stop_method == "atr":
                print(f"    ATR stop: ${position_plan.atr_stop:.2f}")

        if idea.status == "ready":
            ready_ideas.append((idea, position_plan, trigger_price))
        elif idea.status == "watch":
            watch_ideas.append((idea, position_plan, trigger_price))

    print("\n" + "=" * 72)
    print("FINAL TRADE PLAN")
    print("=" * 72)

    if ready_ideas:
        print("\nREADY NOW")
        for idea, plan, trigger_price in sorted(ready_ideas, key=lambda x: x[0].scores.total, reverse=True):
            shares_text = plan.shares_final if plan is not None else 0
            trigger_text = f"{trigger_price:.2f}" if trigger_price is not None else "N/A"
            print(
                f"- {idea.symbol} | {format_setup_label(idea.setup_type)} | "
                f"Score {idea.scores.total:.1f} | Trigger {trigger_text} | "
                f"Entry {idea.entry:.2f} | Stop {idea.stop:.2f} | "
                f"Target 1 {idea.target_1:.2f} | Shares {shares_text}"
            )
    else:
        print("\nREADY NOW")
        print("- None")

    if watch_ideas:
        print("\nWATCH FOR TOMORROW")
        for idea, plan, trigger_price in sorted(watch_ideas, key=lambda x: x[0].scores.total, reverse=True):
            shares_text = plan.shares_final if plan is not None else 0
            trigger_text = f"{trigger_price:.2f}" if trigger_price is not None else "N/A"
            print(
                f"- {idea.symbol} | {format_setup_label(idea.setup_type)} | "
                f"Score {idea.scores.total:.1f} | Trigger {trigger_text} | "
                f"Entry {idea.entry:.2f} | Stop {idea.stop:.2f} | "
                f"Target 1 {idea.target_1:.2f} | Shares {shares_text}"
            )
    else:
        print("\nWATCH FOR TOMORROW")
        print("- None")

    print("\nScan complete.")


if __name__ == "__main__":
    run()