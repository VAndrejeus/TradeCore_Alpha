# Tradecore Alpha

Tradecore Alpha is a catalyst-driven trading decision engine that identifies high-probability stock setups by combining news catalysts, sentiment, technical structure, and risk management.

It is designed to produce **actionable trade plans**, not just signals.

---

## Overview

Tradecore Alpha evaluates stocks using four pillars:

1. **Catalysts** – News events weighted by recency, relevance, and credibility  
2. **Sentiment** – Price reaction and directional bias  
3. **Technicals** – Breakout, reclaim, and momentum structure  
4. **Risk** – ATR-based adaptive stops and position sizing  

The system outputs:
- Trade setups (READY / WATCH / REJECT)
- Entry, stop, and targets
- Risk-adjusted position sizing
- Next-day trigger levels

---

## Features

- Catalyst filtering with ownership and relevance scoring  
- Recency and source-weighted news scoring  
- Multi-catalyst stacking bonus  
- Session-aware logic (intraday vs swing)  
- ATR-based adaptive stop selection  
- Risk-based position sizing  
- Clean trade plan output  
- Watchlist and ready-to-trade separation  

---

## Setup

### 1. Clone project

git clone <your-repo-url>
cd TradeCore_Alpha
2. Install dependencies
pip install -r requirements.txt
3. Configure environment

Create a .env file in the root:

ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
ALPACA_DATA_URL=https://data.alpaca.markets

FINNHUB_API_KEY=your_key

ACCOUNT_SIZE=100000
RISK_PER_TRADE_PCT=0.01
MAX_POSITION_PCT=0.20

SCAN_SYMBOLS=NVDA,PLTR,AMD,SMCI,TSLA,RKLB,ASTS,CRWD,AMZN,MSFT
Running the Scanner
python -m app.main
Example Output
READY NOW
- AMZN | Swing Ready | Score 57.0 | Trigger 210.69 | Entry 208.39 | Stop 197.16 | Target 230.84 | Shares 95
- NVDA | Swing Ready | Score 53.5 | Trigger 174.96 | Entry 174.41 | Stop 162.64 | Target 197.95 | Shares 103

WATCH FOR TOMORROW
- TSLA | Swing Watch | Score 41.5 | Trigger 373.99
- MSFT | Swing Watch | Score 40.0 | Trigger 373.57
Trade Plan Logic
Status Definitions
READY
High conviction setup
Meets catalyst + sentiment + technical thresholds
Eligible for execution
WATCH
Developing setup
Requires confirmation (trigger break)
REJECT
Weak catalyst or poor structure
Not tradable
Trigger Levels
READY → “Ready above X”
WATCH → “Watch for move above X”
REJECT → “Needs reclaim above X”
Risk Engine

Tradecore Alpha uses adaptive stop selection:

Structure-based stop (support level)
ATR-based stop (volatility buffer)
Chooses the better (tighter, valid) stop

Position sizing is based on:

% account risk
max capital allocation
risk per share
Catalyst Scoring

Catalysts are scored based on:

Relevance to the company
Event type (earnings, deals, product launches, etc.)
Source credibility
Recency
Multi-catalyst stacking
Session Awareness

The system adapts automatically:

Session Mode	Behavior
Intraday	5Min bars, momentum
After-hours	Daily bars, swing
Weekend	Swing only
Current Capabilities
Multi-factor trade decision engine
Fully automated scanning pipeline
Real-time news + price integration
Risk-managed trade generation
Limitations
No execution layer (manual trading required)
No portfolio tracking yet
No market regime filter (planned)
Roadmap

Planned improvements:

Market regime filter (SPY trend gating)
Gap detection and open filtering
ATR trailing stops
Trade tracking and journaling
Auto execution via Alpaca
Disclaimer

This tool is for educational and research purposes only.
It does not constitute financial advice.
Trading involves risk.
