import unittest

from tradingagents.market_utils import (
    build_instrument_context_text,
    get_default_news_queries,
    get_market_info,
    normalize_company_name,
    normalize_ticker_symbol,
    resolve_ticker_input,
    search_symbol_candidates,
)


class TickerSymbolHandlingTests(unittest.TestCase):
    def test_normalize_ticker_symbol_preserves_exchange_suffix(self):
        self.assertEqual(normalize_ticker_symbol(" cnc.to "), "CNC.TO")

    def test_normalize_ticker_symbol_infers_hk_from_numeric_code(self):
        self.assertEqual(normalize_ticker_symbol("700"), "0700.HK")

    def test_normalize_ticker_symbol_infers_a_share_suffix(self):
        self.assertEqual(normalize_ticker_symbol("600519"), "600519.SH")
        self.assertEqual(normalize_ticker_symbol("000001"), "000001.SZ")

    def test_build_instrument_context_mentions_exact_symbol(self):
        context = build_instrument_context_text("7203.T")
        self.assertIn("7203.T", context)
        self.assertIn("exchange suffix", context)

    def test_market_info_maps_shanghai_to_yfinance_suffix(self):
        info = get_market_info("600519")
        self.assertEqual(info.canonical_ticker, "600519.SH")
        self.assertEqual(info.yfinance_symbol, "600519.SS")
        self.assertEqual(info.akshare_symbol, "600519")

    def test_market_info_preserves_hk_symbol(self):
        info = get_market_info("9988.HK")
        self.assertEqual(info.canonical_ticker, "9988.HK")
        self.assertEqual(info.yfinance_symbol, "9988.HK")
        self.assertEqual(info.akshare_symbol, "09988")

    def test_default_news_queries_include_market_specific_aliases(self):
        self.assertEqual(
            get_default_news_queries("600519"),
            ["600519.SH", "600519", "600519.SS"],
        )
        self.assertEqual(
            get_default_news_queries("700"),
            ["0700.HK", "00700", "700"],
        )

    def test_normalize_company_name_strips_common_suffixes(self):
        self.assertEqual(normalize_company_name("\u817e\u8baf\u63a7\u80a1\u6709\u9650\u516c\u53f8"), "\u817e\u8baf")
        self.assertEqual(normalize_company_name("\u963f\u91cc\u5df4\u5df4\u96c6\u56e2\u63a7\u80a1\u6709\u9650\u516c\u53f8"), "\u963f\u91cc\u5df4\u5df4")

    def test_resolve_ticker_input_uses_symbol_index_for_company_names(self):
        symbol_index = [
            {"name_key": "\u817e\u8baf", "canonical_ticker": "0700.HK"},
            {"name_key": "\u8d35\u5dde\u8305\u53f0", "canonical_ticker": "600519.SH"},
            {"name_key": "\u963f\u91cc\u5df4\u5df4", "canonical_ticker": "9988.HK"},
        ]
        self.assertEqual(resolve_ticker_input("\u817e\u8baf\u63a7\u80a1\u6709\u9650\u516c\u53f8", symbol_index=symbol_index), "0700.HK")
        self.assertEqual(resolve_ticker_input("\u8d35\u5dde\u8305\u53f0", symbol_index=symbol_index), "600519.SH")
        self.assertEqual(resolve_ticker_input("\u963f\u91cc\u5df4\u5df4", symbol_index=symbol_index), "9988.HK")

    def test_search_symbol_candidates_returns_ranked_matches(self):
        symbol_index = [
            {"name_key": "\u5e73\u5b89\u94f6\u884c", "canonical_ticker": "000001.SZ", "name": "\u5e73\u5b89\u94f6\u884c", "market": "cn_a"},
            {"name_key": "\u4e2d\u56fd\u5e73\u5b89", "canonical_ticker": "601318.SH", "name": "\u4e2d\u56fd\u5e73\u5b89", "market": "cn_a"},
            {"name_key": "\u5e73\u5b89\u597d\u533b\u751f", "canonical_ticker": "1833.HK", "name": "\u5e73\u5b89\u597d\u533b\u751f", "market": "hk"},
        ]
        candidates = search_symbol_candidates("\u5e73\u5b89", symbol_index=symbol_index, limit=5)
        self.assertEqual(
            [item["canonical_ticker"] for item in candidates],
            ["000001.SZ", "1833.HK", "601318.SH"],
        )


if __name__ == "__main__":
    unittest.main()
