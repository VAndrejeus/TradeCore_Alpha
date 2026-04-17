import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=False)


def _get_env_str(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip()


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return [item.strip().upper() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class Settings:
    app_name: str
    environment: str

    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_base_url: str
    alpaca_data_url: str
    alpaca_data_feed: str
    alpaca_paper: bool

    finnhub_api_key: str
    finnhub_base_url: str

    scan_symbols: list[str]
    intraday_timeframe: str
    swing_timeframe: str
    catalyst_lookback_minutes: int

    min_total_score: float
    min_rr: float
    max_active_symbols: int

    account_size: float
    risk_per_trade_pct: float
    max_position_pct: float

    database_path: str
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=_get_env_str("APP_NAME", "Tradecore Alpha"),
            environment=_get_env_str("APP_ENV", "dev"),
            alpaca_api_key=_get_env_str("ALPACA_API_KEY"),
            alpaca_secret_key=_get_env_str("ALPACA_SECRET_KEY"),
            alpaca_base_url=_get_env_str("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
            alpaca_data_url=_get_env_str("ALPACA_DATA_URL", "https://data.alpaca.markets"),
            alpaca_data_feed=_get_env_str("ALPACA_DATA_FEED", "iex"),
            alpaca_paper=_get_env_bool("ALPACA_PAPER", True),
            finnhub_api_key=_get_env_str("FINNHUB_API_KEY"),
            finnhub_base_url=_get_env_str("FINNHUB_BASE_URL", "https://finnhub.io/api/v1"),
            scan_symbols=_get_env_list(
                "SCAN_SYMBOLS",
                ["NVDA", "PLTR", "AMD", "SMCI", "TSLA", "RKLB", "ASTS", "CRWD", "AMZN", "MSFT"],
            ),
            intraday_timeframe=_get_env_str("INTRADAY_TIMEFRAME", "5Min"),
            swing_timeframe=_get_env_str("SWING_TIMEFRAME", "1Day"),
            catalyst_lookback_minutes=_get_env_int("CATALYST_LOOKBACK_MINUTES", 1440),
            min_total_score=_get_env_float("MIN_TOTAL_SCORE", 75.0),
            min_rr=_get_env_float("MIN_RR", 2.0),
            max_active_symbols=_get_env_int("MAX_ACTIVE_SYMBOLS", 25),
            account_size=_get_env_float("ACCOUNT_SIZE", 10000.0),
            risk_per_trade_pct=_get_env_float("RISK_PER_TRADE_PCT", 0.01),
            max_position_pct=_get_env_float("MAX_POSITION_PCT", 0.20),
            database_path=_get_env_str("DATABASE_PATH", "data/tradecore_alpha.db"),
            log_level=_get_env_str("LOG_LEVEL", "INFO").upper(),
        )

    def validate(self) -> None:
        errors: list[str] = []

        if not self.alpaca_api_key:
            errors.append("Missing ALPACA_API_KEY")
        if not self.alpaca_secret_key:
            errors.append("Missing ALPACA_SECRET_KEY")
        if not self.finnhub_api_key:
            errors.append("Missing FINNHUB_API_KEY")
        if not self.scan_symbols:
            errors.append("SCAN_SYMBOLS cannot be empty")
        if self.min_total_score <= 0:
            errors.append("MIN_TOTAL_SCORE must be greater than 0")
        if self.min_rr <= 0:
            errors.append("MIN_RR must be greater than 0")
        if self.max_active_symbols <= 0:
            errors.append("MAX_ACTIVE_SYMBOLS must be greater than 0")
        if self.account_size <= 0:
            errors.append("ACCOUNT_SIZE must be greater than 0")
        if self.risk_per_trade_pct <= 0:
            errors.append("RISK_PER_TRADE_PCT must be greater than 0")
        if self.max_position_pct <= 0:
            errors.append("MAX_POSITION_PCT must be greater than 0")

        if errors:
            raise ValueError("Invalid configuration:\n- " + "\n- ".join(errors))