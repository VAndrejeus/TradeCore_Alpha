from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List

from app.models.market import CatalystEvent


HIGH_VALUE_KEYWORDS = [
    "contract",
    "agreement",
    "deal",
    "award",
    "order",
    "partnership",
    "collaboration",
    "expansion",
    "launch",
    "launches",
    "launched",
    "product",
    "approval",
    "guidance",
    "raises",
    "backlog",
    "customer",
    "wins",
    "selected",
    "procurement",
    "deployment",
    "rollout",
    "integrates",
    "integration",
    "supply",
    "pilot",
    "signs",
    "signed",
    "commercial",
    "acquisition",
    "acquires",
    "acquired",
    "platform",
    "model",
    "announces",
    "announced",
    "expands",
    "expand",
    "unveils",
    "opens",
    "preorder",
    "buys",
    "buyout",
    "nears",
]

NEGATIVE_KEYWORDS = [
    "downgrade",
    "lawsuit",
    "investigation",
    "fraud",
    "recall",
    "delay",
    "concern",
    "concerns",
    "probe",
    "antitrust",
    "falling",
    "lower",
    "denies",
    "reverse gains",
    "pulls back",
    "scrutiny",
]

LOW_VALUE_KEYWORDS = [
    "analyst",
    "price target",
    "opinion",
    "top stocks",
    "best stocks",
    "stock market today",
    "live coverage",
    "shares of",
    "prediction",
    "forecast",
    "valuation",
    "etf",
    "earnings season",
    "big growth",
    "millionaire maker",
    "motley fool",
    "investor place",
    "zacks",
    "worth your attention",
    "underwhelm",
    "poised to deliver",
    "lists its pecking order",
    "buy or sell",
    "a buy or sell",
    "time to buy",
    "buying the dip",
    "read this first",
    "stock debate",
    "undervalued stock",
]

ROUNDUP_PATTERNS = [
    r"\btop\b.*\bstocks\b",
    r"\bbest\b.*\bstocks\b",
    r"\b2 stocks\b",
    r"\b3 stocks\b",
    r"\b4 stocks\b",
    r"\b5 stocks\b",
    r"\bstock market today\b",
    r"\blive coverage\b",
    r"\bhere'?s everything\b",
    r"\binvestors need to know\b",
    r"\bearnings season\b",
    r"\bworth less than\b",
    r"\bpoised to deliver\b",
    r"\bworth your attention\b",
    r"\bunderwhelm\b",
    r"\bpecking order\b",
]

INDIRECT_PATTERNS = [
    r"\brival\b",
    r"\bmay be falling\b",
    r"\bresponse to\b",
    r"\bvoices concern\b",
    r"\bconcern over\b",
    r"\bafter\b.*\bacquisition\b",
    r"\bvs\.\b",
    r"\bversus\b",
    r"\breframe\b",
]

WEAK_CONTEXT_PATTERNS = [
    r"\bpowered by\b",
    r"\busing\b.*\b(microsoft|nvidia|amazon|tesla|amd|palantir)\b",
    r"\bon\b.*\b(microsoft|nvidia|amazon|tesla|amd|palantir)\b",
    r"\bwith\b.*\b(microsoft outlook|azure|nvidia gpu|nvidia b300|microsoft foundry)\b",
    r"\bfor\b.*\b(microsoft outlook|azure|nvidia gpu|nvidia b300|microsoft foundry)\b",
]

EDITORIAL_PATTERNS = [
    r"\bbuy or sell\b",
    r"\btime to buy\b",
    r"\bbuying the dip\b",
    r"\bread this first\b",
    r"\bundervalued stock\b",
    r"\bstock debate\b",
    r"\bwhat investors need to know\b",
    r"\bcould change everything\b",
    r"\bwhat'?s ahead\b",
    r"\bcould make\b",
    r"\btrim your hare\b",
    r"\bshould you buy\b",
    r"\bshould you sell\b",
    r"\bis .* a buy\b",
]

QUESTIONABLE_PREFIX_PATTERNS = [
    r"^can\s",
    r"^why\s",
    r"^how\s",
    r"^what\s",
    r"^should\s",
    r"^is\s",
    r"^are\s",
    r"^buying the dip\b",
]

SYMBOL_ALIASES = {
    "NVDA": ["nvidia", "nvidia corporation"],
    "PLTR": ["palantir", "palantir technologies"],
    "AMD": ["amd", "advanced micro devices"],
    "SMCI": ["super micro", "super micro computer", "smci"],
    "TSLA": ["tesla", "tesla inc"],
    "RKLB": ["rocket lab", "rocket lab usa", "rklb"],
    "ASTS": ["ast spacemobile", "ast space mobile", "asts"],
    "CRWD": ["crowdstrike", "crowdstrike holdings", "crwd"],
    "AMZN": ["amazon", "amazon.com", "amzn"],
    "MSFT": ["microsoft", "microsoft corporation", "msft"],
}

SECONDARY_PLATFORM_TERMS = {
    "MSFT": ["outlook", "azure", "foundry", "copilot"],
    "NVDA": ["cuda", "nemo", "gpu", "gpus", "b200", "b300"],
    "AMZN": ["aws", "fire tv", "kindle", "alexa"],
}

SOURCE_CREDIBILITY_SCORES = {
    "reuters": 5.0,
    "bloomberg": 5.0,
    "associated press": 4.5,
    "ap": 4.5,
    "the wall street journal": 4.5,
    "wsj": 4.5,
    "financial times": 4.5,
    "barrons": 4.0,
    "marketwatch": 3.5,
    "benzinga": 3.0,
    "seeking alpha": 2.5,
    "yahoo": 2.5,
    "investing.com": 2.5,
    "finnhub": 2.0,
}

PRIMARY_EVENT_BONUS_KEYWORDS = {
    "contract": 3.0,
    "guidance": 2.5,
    "partnership": 2.0,
    "product": 1.5,
    "expansion": 2.0,
}


class CatalystService:
    def filter_events(self, events: List[CatalystEvent]) -> List[CatalystEvent]:
        filtered: list[CatalystEvent] = []
        seen: set[str] = set()

        for event in events:
            if not self._is_symbol_relevant(event):
                continue

            event.category = self._classify(event)
            strength = self.score_event_strength(event)

            if strength < 10:
                continue

            dedupe_key = self._dedupe_key(event)
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            filtered.append(event)

        filtered.sort(key=self.score_event_strength, reverse=True)
        return filtered

    def score_event_strength(self, event: CatalystEvent) -> float:
        text = self._combined_text(event)
        headline = event.headline.lower()

        score = 0.0

        if event.category == "contract":
            score += 18
        elif event.category == "guidance":
            score += 16
        elif event.category == "partnership":
            score += 13
        elif event.category == "product":
            score += 10
        elif event.category == "expansion":
            score += 11
        else:
            score += 3

        if "multi-year" in text or "multiyear" in text:
            score += 5
        if "major" in text or "significant" in text:
            score += 3
        if "government" in text or "darpa" in text or "department of defense" in text:
            score += 5
        if "enterprise" in text:
            score += 3
        if "new customer" in text or "customer win" in text:
            score += 3
        if "launches" in text or "launched" in text or "unveils" in text:
            score += 2
        if "expands" in text or "expansion" in text:
            score += 2
        if "commercial agreement" in text or "commercial launch" in text:
            score += 4
        if "acquisition" in text or "acquires" in text or "acquired" in text or "buyout" in text or "buys" in text:
            score += 4

        if self._headline_starts_with_company(event):
            score += 4
        elif self._headline_mentions_company_early(event):
            score += 2

        if any(keyword in text for keyword in NEGATIVE_KEYWORDS):
            score -= 6

        if any(keyword in text for keyword in LOW_VALUE_KEYWORDS):
            score -= 10

        if self._looks_like_roundup(headline):
            score -= 12

        if self._looks_indirect(headline):
            score -= 5

        if self._looks_like_weak_context(headline):
            score -= 8

        if self._looks_like_commentary(headline):
            score -= 14

        score += self._score_source_credibility(event)
        score += self._score_recency(event)
        score += self._score_primary_event_quality(event)

        return max(0.0, min(score, 35.0))

    def _classify(self, event: CatalystEvent) -> str:
        text = self._combined_text(event)

        if any(word in text for word in ["contract", "award", "order", "procurement", "selected", "signed agreement"]):
            return "contract"

        if any(word in text for word in ["guidance", "raises forecast", "raises outlook", "revenue outlook"]):
            return "guidance"

        if any(word in text for word in ["partnership", "collaboration", "teams with", "integrates with", "alliance"]):
            return "partnership"

        if any(word in text for word in ["launch", "launches", "launched", "product", "model", "platform", "release", "unveils", "preorder"]):
            return "product"

        if any(word in text for word in ["expansion", "facility", "plant", "site", "capacity", "opens", "acquisition", "acquires", "acquired", "expand", "deal", "nears", "buys", "buyout"]):
            return "expansion"

        return "other"

    def _is_symbol_relevant(self, event: CatalystEvent) -> bool:
        symbol = event.symbol.upper()
        headline = event.headline.lower()

        if self._looks_like_roundup(headline):
            return False

        if any(keyword in headline for keyword in LOW_VALUE_KEYWORDS):
            return False

        if self._looks_like_commentary(headline):
            return False

        aliases = SYMBOL_ALIASES.get(symbol, [symbol.lower()])
        secondary_terms = SECONDARY_PLATFORM_TERMS.get(symbol, [])

        has_primary_alias = any(alias in headline for alias in aliases)
        has_secondary_only = any(term in headline for term in secondary_terms) and not has_primary_alias

        if not has_primary_alias:
            return False

        if has_secondary_only:
            return False

        if self._headline_is_primarily_about_other_company(symbol, headline):
            return False

        if self._headline_is_too_indirect(symbol, headline):
            return False

        if self._looks_like_weak_context(headline):
            return False

        if not self._headline_has_event_language(headline):
            return False

        if not self._has_strong_subject_ownership(symbol, headline):
            return False

        return True

    def _headline_has_event_language(self, headline: str) -> bool:
        return any(keyword in headline for keyword in HIGH_VALUE_KEYWORDS)

    def _headline_starts_with_company(self, event: CatalystEvent) -> bool:
        headline = event.headline.lower()
        aliases = SYMBOL_ALIASES.get(event.symbol.upper(), [event.symbol.lower()])
        return any(headline.startswith(alias) for alias in aliases)

    def _headline_mentions_company_early(self, event: CatalystEvent) -> bool:
        headline = event.headline.lower()
        aliases = SYMBOL_ALIASES.get(event.symbol.upper(), [event.symbol.lower()])
        first_segment = headline[:48]
        return any(alias in first_segment for alias in aliases)

    def _has_strong_subject_ownership(self, symbol: str, headline: str) -> bool:
        aliases = SYMBOL_ALIASES.get(symbol, [symbol.lower()])

        if any(headline.startswith(alias) for alias in aliases):
            return True

        first_clause = re.split(r"[:\-—,;]", headline, maxsplit=1)[0]
        if any(alias in first_clause for alias in aliases):
            return True

        early_segment = headline[:48]
        if any(alias in early_segment for alias in aliases) and self._headline_has_event_language(early_segment):
            return True

        return False

    def _headline_is_primarily_about_other_company(self, symbol: str, headline: str) -> bool:
        own_aliases = SYMBOL_ALIASES.get(symbol, [symbol.lower()])
        own_hits = sum(1 for alias in own_aliases if alias in headline)

        if own_hits == 0:
            return True

        other_hits = 0
        for other_symbol, aliases in SYMBOL_ALIASES.items():
            if other_symbol == symbol:
                continue
            if any(alias in headline for alias in aliases):
                other_hits += 1

        if other_hits >= 2 and not self._headline_starts_with_alias(headline, own_aliases):
            return True

        return False

    def _headline_is_too_indirect(self, symbol: str, headline: str) -> bool:
        own_aliases = SYMBOL_ALIASES.get(symbol, [symbol.lower()])

        if not self._headline_starts_with_alias(headline, own_aliases):
            if self._looks_indirect(headline):
                return True

        if "rival" in headline and not self._headline_starts_with_alias(headline, own_aliases):
            return True

        if "response to" in headline:
            return True

        if "soars" in headline or "surges" in headline:
            return True

        return False

    def _headline_starts_with_alias(self, headline: str, aliases: list[str]) -> bool:
        return any(headline.startswith(alias) for alias in aliases)

    def _looks_like_roundup(self, headline: str) -> bool:
        return any(re.search(pattern, headline) for pattern in ROUNDUP_PATTERNS)

    def _looks_indirect(self, headline: str) -> bool:
        return any(re.search(pattern, headline) for pattern in INDIRECT_PATTERNS)

    def _looks_like_weak_context(self, headline: str) -> bool:
        return any(re.search(pattern, headline) for pattern in WEAK_CONTEXT_PATTERNS)

    def _looks_like_commentary(self, headline: str) -> bool:
        if any(re.search(pattern, headline) for pattern in QUESTIONABLE_PREFIX_PATTERNS):
            return True

        if any(re.search(pattern, headline) for pattern in EDITORIAL_PATTERNS):
            return True

        if any(x in headline for x in [
            "calls",
            "says",
            "buy",
            "buys",
            "sell",
            "trader",
            "analyst",
            "price target",
        ]):
            return True

        commentary_markers = [
            "what's ahead",
            "could make",
            "could change everything",
            "worth",
            "buy or sell",
            "a buy or sell",
            "time to buy",
            "buying the dip",
            "read this first",
            "stock debate",
            "undervalued stock",
            "what investors need to know",
        ]
        return any(marker in headline for marker in commentary_markers)

    def _score_source_credibility(self, event: CatalystEvent) -> float:
        source_text = str(event.metadata.get("source", "")).strip().lower()
        if not source_text:
            return 0.0

        for source_name, score in SOURCE_CREDIBILITY_SCORES.items():
            if source_name in source_text:
                return score

        return 1.0

    def _score_recency(self, event: CatalystEvent) -> float:
        if not event.ts:
            return 0.0

        now_utc = datetime.now(timezone.utc)
        age_hours = (now_utc - event.ts).total_seconds() / 3600.0

        if age_hours <= 6:
            return 4.0
        if age_hours <= 24:
            return 3.0
        if age_hours <= 72:
            return 1.5
        if age_hours <= 168:
            return 0.5
        return 0.0

    def _score_primary_event_quality(self, event: CatalystEvent) -> float:
        headline = event.headline.lower()
        bonus = 0.0

        # =========================
        # BASE CATEGORY WEIGHTING
        # =========================
        if event.category == "contract":
            bonus += 4.0
        elif event.category == "guidance":
            bonus += 3.5
        elif event.category == "expansion":
            bonus += 3.0
        elif event.category == "partnership":
            bonus += 2.0
        elif event.category == "product":
            bonus += 1.0

        # =========================
        # 🚀 MAJOR DEAL BOOST
        # =========================
        if any(x in headline for x in [
            "deal", "acquisition", "acquires", "acquired",
            "buyout", "buys", "merger", "stake", "$", "billion"
        ]):
            bonus += 6.0

        # =========================
        # 🏛️ GOVERNMENT / STRATEGIC
        # =========================
        if any(x in headline for x in ["darpa", "government", "defense"]):
            bonus += 3.0

        # =========================
        # 🧠 BUSINESS IMPACT
        # =========================
        if any(x in headline for x in ["contract", "award", "order", "customer", "selected"]):
            bonus += 3.0

        # =========================
        # ❌ PRODUCT HYPE PENALTY (FINAL TUNE)
        # =========================
        if any(x in headline for x in [
            "final", "limited", "only", "edition", "exclusive"
        ]):
            bonus -= 6.0  # was 4.0

        if any(x in headline for x in [
            "making just",
            "only",
            "final model",
        ]):
            bonus -= 3.0

        # =========================
        # ❌ INDIRECT / NON-OWNERSHIP (FIX AMD)
        # =========================
        if any(x in headline for x in [
            "investment from",
            "backs",
            "invests in",
            "venture",
            "funding"
        ]):
            bonus -= 4.0

        # =========================
        # ❌ AWARD / RECOGNITION (FIX CRWD)
        # =========================
        if any(x in headline for x in [
            "named",
            "ranked",
            "customers’ choice",
            "leader in",
            "report"
        ]):
            bonus -= 5.0

        # =========================
        # ❌ COMMENTARY / WRAPPERS
        # =========================
        if any(x in headline for x in [
            "paid for itself",
            "stock jumps",
            "shares rise",
            "buy or sell",
            "time to buy"
        ]):
            bonus -= 6.0

        # =========================
        # ❌ SYMPATHY / SECTOR
        # =========================
        if any(x in headline for x in [
            "stocks surge",
            "sector",
            "rival",
            "vs",
            "versus"
        ]):
            bonus -= 4.0

        # =========================
        # 🧩 OWNERSHIP BOOST
        # =========================
        if self._headline_starts_with_company(event):
            bonus += 2.0

        return bonus

    def _dedupe_key(self, event: CatalystEvent) -> str:
        headline = re.sub(r"\s+", " ", event.headline.strip().lower())
        return f"{event.symbol}|{headline}"

    def _combined_text(self, event: CatalystEvent) -> str:
        related = str(event.metadata.get("related", "")).lower()
        return f"{event.headline} {event.summary} {related}".lower()