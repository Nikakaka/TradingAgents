"""yfinance-based news data fetching functions."""

import yfinance as yf
import akshare as ak
from datetime import datetime
from dateutil.relativedelta import relativedelta
from tradingagents.market_utils import get_default_news_queries, get_market_info


def _extract_article_data(article: dict) -> dict:
    """Extract article data from yfinance news format (handles nested 'content' structure)."""
    # Handle nested content structure
    if "content" in article:
        content = article["content"]
        title = content.get("title", "No title")
        summary = content.get("summary", "")
        provider = content.get("provider", {})
        publisher = provider.get("displayName", "Unknown")

        # Get URL from canonicalUrl or clickThroughUrl
        url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        link = url_obj.get("url", "")

        # Get publish date
        pub_date_str = content.get("pubDate", "")
        pub_date = None
        if pub_date_str:
            try:
                pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return {
            "title": title,
            "summary": summary,
            "publisher": publisher,
            "link": link,
            "pub_date": pub_date,
        }
    else:
        # Fallback for flat structure
        return {
            "title": article.get("title", "No title"),
            "summary": article.get("summary", ""),
            "publisher": article.get("publisher", "Unknown"),
            "link": article.get("link", ""),
            "pub_date": None,
        }


def _get_company_name_aliases(ticker: str) -> list[str]:
    info = get_market_info(ticker)
    aliases: list[str] = []

    try:
        if info.market == "cn_a" and info.akshare_symbol:
            profile = ak.stock_individual_info_em(symbol=info.akshare_symbol)
            if profile is not None and not profile.empty:
                value_map = {
                    str(row["item"]).strip(): str(row["value"]).strip()
                    for _, row in profile.iterrows()
                }
                for key in ("股票简称", "股票名称"):
                    value = value_map.get(key)
                    if value:
                        aliases.append(value)
        elif info.market == "hk" and info.akshare_symbol:
            profile = ak.stock_hk_company_profile_em(symbol=info.akshare_symbol)
            if profile is not None and not profile.empty:
                row = profile.iloc[0]
                for key in ("公司名称", "英文名称"):
                    value = str(row.get(key, "")).strip()
                    if value:
                        aliases.append(value)
    except Exception:
        pass

    deduped: list[str] = []
    for alias in aliases:
        if alias and alias not in deduped:
            deduped.append(alias)
    return deduped


def get_news_yfinance(
    ticker: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    Retrieve news for a specific stock ticker using yfinance.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        Formatted string containing news articles
    """
    try:
        market_info = get_market_info(ticker)
        news = []

        # First try the provider-native ticker endpoint.
        stock = yf.Ticker(market_info.yfinance_symbol)
        try:
            news = stock.get_news(count=20) or []
        except Exception:
            news = []

        # For CN/HK names, ticker-only lookup often misses coverage; retry with search aliases.
        if not news:
            for query in get_default_news_queries(ticker) + _get_company_name_aliases(ticker):
                try:
                    search = yf.Search(query=query, news_count=20, enable_fuzzy_query=True)
                    if search.news:
                        news = search.news
                        break
                except Exception:
                    continue

        if not news:
            return f"No news found for {market_info.canonical_ticker}"

        # Parse date range for filtering
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        news_str = ""
        filtered_count = 0

        for article in news:
            data = _extract_article_data(article)

            # Filter by date if publish time is available
            if data["pub_date"]:
                pub_date_naive = data["pub_date"].replace(tzinfo=None)
                if not (start_dt <= pub_date_naive <= end_dt + relativedelta(days=1)):
                    continue

            news_str += f"### {data['title']} (source: {data['publisher']})\n"
            if data["summary"]:
                news_str += f"{data['summary']}\n"
            if data["link"]:
                news_str += f"Link: {data['link']}\n"
            news_str += "\n"
            filtered_count += 1

        if filtered_count == 0:
            return f"No news found for {market_info.canonical_ticker} between {start_date} and {end_date}"

        return f"## {market_info.canonical_ticker} News, from {start_date} to {end_date}:\n\n{news_str}"

    except Exception as e:
        return f"Error fetching news for {ticker}: {str(e)}"


def get_global_news_yfinance(
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 10,
) -> str:
    """
    Retrieve global/macro economic news using yfinance Search.

    Args:
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back
        limit: Maximum number of articles to return

    Returns:
        Formatted string containing global news articles
    """
    # Search queries for macro/global news
    search_queries = [
        "stock market economy",
        "Federal Reserve interest rates",
        "inflation economic outlook",
        "global markets trading",
    ]

    all_news = []
    seen_titles = set()

    try:
        for query in search_queries:
            search = yf.Search(
                query=query,
                news_count=limit,
                enable_fuzzy_query=True,
            )

            if search.news:
                for article in search.news:
                    # Handle both flat and nested structures
                    if "content" in article:
                        data = _extract_article_data(article)
                        title = data["title"]
                    else:
                        title = article.get("title", "")

                    # Deduplicate by title
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        all_news.append(article)

            if len(all_news) >= limit:
                break

        if not all_news:
            return f"No global news found for {curr_date}"

        # Calculate date range
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = curr_dt - relativedelta(days=look_back_days)
        start_date = start_dt.strftime("%Y-%m-%d")

        news_str = ""
        for article in all_news[:limit]:
            # Handle both flat and nested structures
            if "content" in article:
                data = _extract_article_data(article)
                title = data["title"]
                publisher = data["publisher"]
                link = data["link"]
                summary = data["summary"]
            else:
                title = article.get("title", "No title")
                publisher = article.get("publisher", "Unknown")
                link = article.get("link", "")
                summary = ""

            news_str += f"### {title} (source: {publisher})\n"
            if summary:
                news_str += f"{summary}\n"
            if link:
                news_str += f"Link: {link}\n"
            news_str += "\n"

        return f"## Global Market News, from {start_date} to {curr_date}:\n\n{news_str}"

    except Exception as e:
        return f"Error fetching global news: {str(e)}"
