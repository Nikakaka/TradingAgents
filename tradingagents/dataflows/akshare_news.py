"""Akshare-based news data fetching functions for Chinese A-shares."""

import os
import urllib.request
import logging
import time
from datetime import datetime

# Disable system proxy for akshare data fetching
def _disable_system_proxy():
    """Disable system proxy settings that may interfere with data fetching."""
    for key in list(os.environ.keys()):
        if 'proxy' in key.lower() and key.upper() not in ['NO_PROXY']:
            del os.environ[key]
    no_proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(no_proxy_handler)
    urllib.request.install_opener(opener)
    os.environ['NO_PROXY'] = '*'
    os.environ['no_proxy'] = '*'
    # Also disable requests library from reading system proxy settings
    import requests
    requests.Session.trust_env = False

_disable_system_proxy()

import akshare as ak

from tradingagents.market_utils import get_market_info

logger = logging.getLogger(__name__)

# Rate limit configuration
_AKSHARE_NEWS_DELAY = 1.0  # Delay between requests to avoid rate limiting
_last_akshare_news_request = 0.0


def _rate_limited_request():
    """Ensure minimum delay between Akshare requests."""
    global _last_akshare_news_request
    elapsed = time.time() - _last_akshare_news_request
    if elapsed < _AKSHARE_NEWS_DELAY:
        time.sleep(_AKSHARE_NEWS_DELAY - elapsed)
    _last_akshare_news_request = time.time()


def get_news_akshare(ticker: str, start_date: str, end_date: str) -> str:
    """
    Retrieve news for a Chinese A-share or HK stock ticker using Akshare (EastMoney).

    Args:
        ticker: Stock ticker symbol (e.g., "300750.SZ" for A-share, "0700.HK" for HK)
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        Formatted string containing news articles

    Raises:
        ValueError: If ticker is not a Chinese A-share or HK stock (to allow fallback to other vendors)
    """
    try:
        market_info = get_market_info(ticker)

        # Support Chinese A-shares and HK stocks
        if market_info.market not in ("cn_a", "hk"):
            raise ValueError(
                f"Akshare news only supports Chinese A-shares and HK stocks, got {ticker} ({market_info.market}). "
                f"Please use yfinance or alpha_vantage for other markets."
            )

        # Get the appropriate symbol format for akshare
        if market_info.market == "hk":
            # HK stocks use 5-digit code (e.g., "00700" for Tencent)
            symbol = market_info.akshare_symbol or ticker.split('.')[0].zfill(5)
        else:
            # A-shares use the code without exchange suffix
            symbol = market_info.akshare_symbol or ticker.split('.')[0]

        _rate_limited_request()

        # Try to get news from EastMoney via Akshare
        try:
            # stock_news_em returns news for a specific symbol
            df = ak.stock_news_em(symbol=symbol)
            if df is None or df.empty:
                return f"No news found for {ticker} from EastMoney"
        except Exception as e:
            logger.warning(f"Akshare stock_news_em failed for {symbol}: {e}")
            # Fallback to general market news
            return _get_general_market_news(ticker, start_date, end_date)

        # Parse date range for filtering
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # Parse and filter news
        news_items = []
        for _, row in df.iterrows():
            try:
                # Akshare returns columns: 关键词, 新闻标题, 新闻内容, 发布时间, 文章来源, 新闻链接
                pub_time_str = str(row.get("发布时间", "") or row.get("时间", "") or "")
                title = str(row.get("新闻标题", "") or row.get("标题", "") or "")
                content = str(row.get("新闻内容", "") or row.get("内容", "") or "")
                link = str(row.get("新闻链接", "") or row.get("链接", "") or "")
                source = str(row.get("文章来源", "") or row.get("来源", "") or "")

                if not title:
                    continue

                # Try to parse publish date
                pub_date = None
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"]:
                    try:
                        pub_date = datetime.strptime(pub_time_str.strip(), fmt)
                        break
                    except ValueError:
                        continue

                # Filter by date if we have a valid date
                if pub_date:
                    pub_date_naive = pub_date.replace(tzinfo=None) if pub_date.tzinfo else pub_date
                    if not (start_dt <= pub_date_naive <= end_dt):
                        continue

                news_items.append({
                    "title": title,
                    "content": content[:500] if len(content) > 500 else content,  # Truncate long content
                    "link": link,
                    "pub_date": pub_date,
                    "source": source,
                })

            except Exception as e:
                logger.debug(f"Failed to parse news row: {e}")
                continue

        if not news_items:
            return f"No news found for {ticker} between {start_date} and {end_date}"

        # Format output
        news_str = f"## {ticker} News (EastMoney), from {start_date} to {end_date}:\n\n"

        for item in news_items[:20]:  # Limit to 20 items
            news_str += f"### {item['title']}\n"
            if item.get('source'):
                news_str += f"Source: {item['source']}\n"
            if item['content']:
                news_str += f"{item['content']}\n"
            if item['link']:
                news_str += f"Link: {item['link']}\n"
            if item['pub_date']:
                news_str += f"Published: {item['pub_date'].strftime('%Y-%m-%d %H:%M')}\n"
            news_str += "\n"

        return news_str

    except ValueError:
        # Re-raise ValueError to allow fallback to other vendors
        raise
    except Exception as e:
        logger.error(f"Error fetching news for {ticker} from Akshare: {e}")
        return f"Error fetching news for {ticker}: {str(e)}"


def _get_general_market_news(ticker: str, start_date: str, end_date: str) -> str:
    """Get general market news as fallback (A-share or HK based on ticker)."""
    try:
        market_info = get_market_info(ticker)

        _rate_limited_request()

        # Get general stock market news from EastMoney
        try:
            # Use appropriate symbol based on market
            if market_info.market == "hk":
                news_symbol = "港股"  # HK stocks
            else:
                news_symbol = "A股"  # A-shares

            df = ak.stock_news_em(symbol=news_symbol)
            if df is None or df.empty:
                return f"No market news available for {ticker}"
        except Exception:
            # Last fallback: return a message about limited data
            return (
                f"Limited news data available for {ticker}. "
                f"The primary news source (EastMoney) is not responding. "
                f"Please consider checking financial news websites directly for the latest updates."
            )

        # Parse and format news (same logic as above)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        news_items = []
        for _, row in df.iterrows():
            try:
                pub_time_str = str(row.get("发布时间", "") or row.get("时间", "") or "")
                title = str(row.get("新闻标题", "") or row.get("标题", "") or "")
                content = str(row.get("新闻内容", "") or row.get("内容", "") or "")
                link = str(row.get("新闻链接", "") or row.get("链接", "") or "")

                if not title:
                    continue

                pub_date = None
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"]:
                    try:
                        pub_date = datetime.strptime(pub_time_str.strip(), fmt)
                        break
                    except ValueError:
                        continue

                if pub_date:
                    pub_date_naive = pub_date.replace(tzinfo=None) if pub_date.tzinfo else pub_date
                    if not (start_dt <= pub_date_naive <= end_dt):
                        continue

                news_items.append({
                    "title": title,
                    "content": content[:500] if len(content) > 500 else content,
                    "link": link,
                    "pub_date": pub_date,
                })

            except Exception:
                continue

        if not news_items:
            return f"No market news found for {ticker} between {start_date} and {end_date}"

        # Format output
        news_str = f"## A-Share Market News (EastMoney), from {start_date} to {end_date}:\n\n"
        news_str += f"*Note: Showing general A-share market news as specific news for {ticker} was unavailable.*\n\n"

        for item in news_items[:15]:
            news_str += f"### {item['title']}\n"
            if item['content']:
                news_str += f"{item['content']}\n"
            if item['link']:
                news_str += f"Link: {item['link']}\n"
            if item['pub_date']:
                news_str += f"Published: {item['pub_date'].strftime('%Y-%m-%d %H:%M')}\n"
            news_str += "\n"

        return news_str

    except Exception as e:
        logger.error(f"Error fetching general market news: {e}")
        return f"Error fetching news for {ticker}: {str(e)}"


def get_global_news_akshare(curr_date: str, look_back_days: int = 7, limit: int = 10) -> str:
    """
    Retrieve global/macro economic news for Chinese market using Akshare.

    Args:
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back
        limit: Maximum number of articles to return

    Returns:
        Formatted string containing global news articles
    """
    try:
        _rate_limited_request()

        # Try to get macro/market news from EastMoney
        try:
            # Get financial news from EastMoney
            df = ak.stock_news_em(symbol="财经")
            if df is None or df.empty:
                return f"No global news found for {curr_date}"
        except Exception as e:
            logger.warning(f"Akshare stock_news_em failed for macro news: {e}")
            return f"No global news available for {curr_date}"

        # Parse date range for filtering
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = curr_dt - __import__("datetime").timedelta(days=look_back_days)
        start_date = start_dt.strftime("%Y-%m-%d")

        news_items = []
        for _, row in df.iterrows():
            try:
                pub_time_str = str(row.get("发布时间", "") or row.get("时间", "") or "")
                title = str(row.get("新闻标题", "") or row.get("标题", "") or "")
                content = str(row.get("新闻内容", "") or row.get("内容", "") or "")
                link = str(row.get("新闻链接", "") or row.get("链接", "") or "")

                if not title:
                    continue

                pub_date = None
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"]:
                    try:
                        pub_date = datetime.strptime(pub_time_str.strip(), fmt)
                        break
                    except ValueError:
                        continue

                if pub_date:
                    pub_date_naive = pub_date.replace(tzinfo=None) if pub_date.tzinfo else pub_date
                    if not (start_dt <= pub_date_naive <= curr_dt):
                        continue

                news_items.append({
                    "title": title,
                    "content": content[:500] if len(content) > 500 else content,
                    "link": link,
                    "pub_date": pub_date,
                })

            except Exception:
                continue

        if not news_items:
            return f"No global news found for {curr_date}"

        # Format output
        news_str = f"## Global Market News (EastMoney), from {start_date} to {curr_date}:\n\n"

        for item in news_items[:limit]:
            news_str += f"### {item['title']}\n"
            if item['content']:
                news_str += f"{item['content']}\n"
            if item['link']:
                news_str += f"Link: {item['link']}\n"
            if item['pub_date']:
                news_str += f"Published: {item['pub_date'].strftime('%Y-%m-%d %H:%M')}\n"
            news_str += "\n"

        return news_str

    except Exception as e:
        logger.error(f"Error fetching global news from Akshare: {e}")
        return f"Error fetching global news: {str(e)}"
