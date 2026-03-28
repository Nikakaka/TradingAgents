from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class MarketInfo:
    canonical_ticker: str
    market: str
    region_label: str
    yfinance_symbol: str
    akshare_symbol: str | None


_SUFFIX_ALIASES = {
    "XSHG": "SH",
    "SHA": "SH",
    "SS": "SH",
    "SH": "SH",
    "XSHE": "SZ",
    "SHE": "SZ",
    "SZ": "SZ",
    "BJ": "BJ",
    "BSE": "BJ",
    "HK": "HK",
}

_CORPORATE_SUFFIXES = (
    "\u96c6\u56e2\u63a7\u80a1\u6709\u9650\u516c\u53f8",
    "\u96c6\u56e2\u80a1\u4efd\u6709\u9650\u516c\u53f8",
    "\u96c6\u56e2\u6709\u9650\u516c\u53f8",
    "\u63a7\u80a1\u6709\u9650\u516c\u53f8",
    "\u80a1\u4efd\u6709\u9650\u516c\u53f8",
    "\u6709\u9650\u516c\u53f8",
    "\u96c6\u56e2\u63a7\u80a1",
    "\u96c6\u56e2\u80a1\u4efd",
    "\u96c6\u56e2",
    "\u63a7\u80a1",
    "-W",
    "W",
)

_MARKET_INDEX_CACHE = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "dataflows", "data_cache")),
    "market_symbol_index.json",
)


def normalize_ticker_symbol(ticker: str) -> str:
    """Normalize common ticker inputs into a canonical cross-provider form."""
    raw = ticker.strip().upper()
    if not raw:
        return raw

    if raw.startswith(("SH", "SZ", "BJ", "HK")) and raw[2:].isdigit():
        market_prefix = raw[:2]
        digits = raw[2:]
        if market_prefix == "HK":
            return f"{digits.zfill(4)}.HK"
        return f"{digits.zfill(6)}.{market_prefix}"

    if "." in raw:
        base, suffix = raw.rsplit(".", 1)
        normalized_suffix = _SUFFIX_ALIASES.get(suffix, suffix)
        if normalized_suffix == "HK" and base.isdigit():
            return f"{str(int(base)).zfill(4)}.HK"
        if normalized_suffix in {"SH", "SZ", "BJ"} and base.isdigit():
            return f"{base.zfill(6)}.{normalized_suffix}"
        return f"{base}.{normalized_suffix}"

    if raw.isdigit():
        if len(raw) == 6:
            if raw.startswith(("6", "5", "9")):
                return f"{raw}.SH"
            if raw.startswith(("0", "1", "2", "3")):
                return f"{raw}.SZ"
            if raw.startswith(("4", "8")):
                return f"{raw}.BJ"
        if len(raw) <= 5:
            return f"{str(int(raw)).zfill(4)}.HK"

    return raw


def get_market_info(ticker: str) -> MarketInfo:
    canonical = normalize_ticker_symbol(ticker)

    market = "global"
    region_label = "global market"
    yfinance_symbol = canonical
    akshare_symbol = None

    if canonical.endswith(".HK"):
        market = "hk"
        region_label = "Hong Kong equity"
        yfinance_symbol = canonical
        akshare_symbol = canonical[:-3].zfill(5)
    elif canonical.endswith(".SH"):
        market = "cn_a"
        region_label = "China A-share (Shanghai)"
        yfinance_symbol = f"{canonical[:-3]}.SS"
        akshare_symbol = canonical[:-3]
    elif canonical.endswith(".SZ"):
        market = "cn_a"
        region_label = "China A-share (Shenzhen)"
        yfinance_symbol = canonical
        akshare_symbol = canonical[:-3]
    elif canonical.endswith(".BJ"):
        market = "cn_a"
        region_label = "China A-share (Beijing)"
        yfinance_symbol = canonical
        akshare_symbol = canonical[:-3]

    return MarketInfo(
        canonical_ticker=canonical,
        market=market,
        region_label=region_label,
        yfinance_symbol=yfinance_symbol,
        akshare_symbol=akshare_symbol,
    )


def build_instrument_context_text(ticker: str) -> str:
    """Describe the instrument so prompts preserve the intended listing."""
    info = get_market_info(ticker)
    return (
        f"The instrument to analyze is `{info.canonical_ticker}` ({info.region_label}). "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.HK`, `.SH`, `.SZ`, `.BJ`, `.TO`, `.L`, `.T`). "
        "If the instrument is a China or Hong Kong listing, do not silently replace it with a U.S. ADR or a different exchange listing."
    )


def get_default_news_queries(ticker: str) -> List[str]:
    """Return a small list of market-aware default news queries."""
    info = get_market_info(ticker)
    queries = [info.canonical_ticker]

    if info.market == "hk" and info.akshare_symbol:
        queries.append(info.akshare_symbol)
        queries.append(info.akshare_symbol.lstrip("0") or "0")
    elif info.market == "cn_a" and info.akshare_symbol:
        queries.append(info.akshare_symbol)
        queries.append(info.yfinance_symbol)
    else:
        queries.append(info.yfinance_symbol)

    deduped = []
    for query in queries:
        if query and query not in deduped:
            deduped.append(query)
    return deduped


def normalize_company_name(name: str) -> str:
    """Normalize company names for fuzzy ticker resolution."""
    normalized = "".join(ch for ch in name.strip().upper() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    for suffix in _CORPORATE_SUFFIXES:
        normalized = normalized.replace(suffix.upper(), "")
    return normalized


def _looks_like_ticker_input(user_input: str) -> bool:
    raw = user_input.strip()
    if not raw:
        return True
    return all(ch.isascii() and (ch.isalnum() or ch in "._-") for ch in raw)


def _build_symbol_index() -> list[dict]:
    import akshare as ak

    entries: list[dict] = []

    cn_df = ak.stock_zh_a_spot_em()
    for _, row in cn_df.iterrows():
        code = str(row.get("代码", "")).strip()
        name = str(row.get("名称", "")).strip()
        if code and name:
            entries.append(
                {
                    "market": "cn_a",
                    "code": code,
                    "name": name,
                    "canonical_ticker": normalize_ticker_symbol(code),
                    "name_key": normalize_company_name(name),
                }
            )

    hk_df = ak.stock_hk_spot_em()
    for _, row in hk_df.iterrows():
        code = str(row.get("代码", "")).strip()
        name = str(row.get("名称", "")).strip()
        if code and name:
            entries.append(
                {
                    "market": "hk",
                    "code": code,
                    "name": name,
                    "canonical_ticker": normalize_ticker_symbol(code),
                    "name_key": normalize_company_name(name),
                }
            )

    return entries


def load_symbol_index(force_refresh: bool = False) -> list[dict]:
    """Load cached CN/HK symbol index, building it on demand."""
    os.makedirs(os.path.dirname(_MARKET_INDEX_CACHE), exist_ok=True)

    if not force_refresh and os.path.exists(_MARKET_INDEX_CACHE):
        try:
            with open(_MARKET_INDEX_CACHE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            entries = payload.get("entries", [])
            if entries:
                return entries
        except Exception:
            pass

    entries = _build_symbol_index()
    with open(_MARKET_INDEX_CACHE, "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f, ensure_ascii=False)
    return entries


def search_symbol_candidates(
    user_input: str, symbol_index: list[dict] | None = None, limit: int = 8
) -> list[dict]:
    """Return ranked CN/HK symbol candidates for a company-name style query."""
    if _looks_like_ticker_input(user_input):
        canonical = normalize_ticker_symbol(user_input)
        return [{"canonical_ticker": canonical, "name": canonical, "market": get_market_info(canonical).market}]

    entries = symbol_index or load_symbol_index()
    query = normalize_company_name(user_input)
    if not query:
        return []

    ranked: list[tuple[int, dict]] = []
    for entry in entries:
        name_key = entry.get("name_key", "")
        if not name_key:
            continue
        score = None
        if name_key == query:
            score = 0
        elif name_key.startswith(query):
            score = 1
        elif query in name_key:
            score = 2

        if score is not None:
            ranked.append((score, entry))

    ranked.sort(key=lambda item: (item[0], len(item[1].get("name_key", "")), item[1].get("canonical_ticker", "")))

    deduped: list[dict] = []
    seen = set()
    for _, entry in ranked:
        ticker = entry.get("canonical_ticker")
        if ticker and ticker not in seen:
            deduped.append(entry)
            seen.add(ticker)
        if len(deduped) >= limit:
            break
    return deduped


def _resolve_from_symbol_index(user_input: str, symbol_index: list[dict]) -> str | None:
    candidates = search_symbol_candidates(user_input, symbol_index=symbol_index, limit=2)
    if len(candidates) == 1:
        return candidates[0]["canonical_ticker"]
    return None


def resolve_ticker_input(user_input: str, symbol_index: list[dict] | None = None) -> str:
    """Resolve ticker-like input or common CN/HK company names into a canonical ticker."""
    if _looks_like_ticker_input(user_input):
        return normalize_ticker_symbol(user_input)

    resolved = _resolve_from_symbol_index(user_input, symbol_index or load_symbol_index())
    if resolved:
        return resolved

    return normalize_ticker_symbol(user_input)
