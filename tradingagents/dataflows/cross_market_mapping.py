"""
Cross-market stock mapping module.

This module provides functionality to identify stocks listed on multiple exchanges
and map their ticker symbols across markets:
- A-shares + H-shares (China A-share + Hong Kong)
- H-shares + US (Hong Kong + US ADRs)
"""

import logging
import pandas as pd
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Static mapping for HK stocks with US ADR listings
# Format: {HK_CODE: {"us_symbol": "XXX", "name": "公司名称"}}
HK_US_ADR_MAPPING = {
    # 互联网科技
    "09988": {"us_symbol": "BABA", "name": "阿里巴巴"},  # Alibaba
    "0700": {"us_symbol": "TCEHY", "name": "腾讯控股"},  # Tencent
    "09999": {"us_symbol": "NETEASE", "name": "网易"},  # NetEase
    "09618": {"us_symbol": "JD", "name": "京东集团"},  # JD.com
    "09961": {"us_symbol": "BIDU", "name": "百度"},  # Baidu
    "03690": {"us_symbol": "XPEV", "name": "小鹏汽车"},  # XPeng
    "09868": {"us_symbol": "LI", "name": "理想汽车"},  # Li Auto
    "09888": {"us_symbol": "BILI", "name": "哔哩哔哩"},  # Bilibili
    "02015": {"us_symbol": "BEKE", "name": "贝壳"},  # Beike
    "09626": {"us_symbol": "BZ", "name": "BOSS直聘"},  # BOSS Zhipin
    "06060": {"us_symbol": "ZH", "name": "知乎"},  # Zhihu
    "01810": {"us_symbol": "XIAOMI", "name": "小米集团"},  # Xiaomi (not direct ADR)
    "09926": {"us_symbol": "NIO", "name": "蔚来"},  # NIO (primary US listed)
    "02018": {"us_symbol": "ATHM", "name": "汽车之家"},  # Autohome
    "0772": {"us_symbol": "CNET", "name": "中国在线"},  # China Online
    "02020": {"us_symbol": "ANJY", "name": "安派科"},  # AnPac
    "03888": {"us_symbol": "SINA", "name": "新浪"},  # Sina (delisted, kept for reference)
    "09866": {"us_symbol": "NTES", "name": "网易"},  # NetEase alternative

    # 金融
    "02628": {"us_symbol": "LFC", "name": "中国人寿"},  # China Life
    "01339": {"us_symbol": "HKBN", "name": "中国人保"},  # PICC
    "02318": {"us_symbol": "CAC", "name": "中国平安"},  # Ping An
    "02601": {"us_symbol": "CHL", "name": "中国电信"},  # China Telecom
    "00762": {"us_symbol": "CHA", "name": "中国联通"},  # China Unicom
    "00941": {"us_symbol": "CHU", "name": "中国移动"},  # China Mobile
    "03988": {"us_symbol": "BACHF", "name": "中国银行"},  # Bank of China
    "01288": {"us_symbol": "ACGBY", "name": "农业银行"},  # AgBank

    # 能源
    "00857": {"us_symbol": "PTR", "name": "中国石油"},  # PetroChina
    "00386": {"us_symbol": "SNP", "name": "中国石化"},  # Sinopec
    "00902": {"us_symbol": "CEO", "name": "中海油"},  # CNOOC

    # 其他
    "01113": {"us_symbol": "DXTR", "name": "长江和记"},  # CK Hutchison
    "02007": {"us_symbol": "GWBFX", "name": "碧桂园"},  # Country Garden
}

# Static A+H stock mapping as fallback (updated 2024)
# Format: {HK_CODE: {"cn_code": "XXXXXX", "name": "公司名称"}}
AH_STOCK_MAPPING_STATIC = {
    # 银行金融
    "03988": {"cn_code": "601988", "name": "中国银行"},
    "01288": {"cn_code": "601288", "name": "农业银行"},
    "00939": {"cn_code": "601398", "name": "工商银行"},
    "00941": {"cn_code": "601939", "name": "建设银行"},
    "02628": {"cn_code": "601628", "name": "中国人寿"},
    "01339": {"cn_code": "601319", "name": "中国人保"},
    "02318": {"cn_code": "601318", "name": "中国平安"},
    "06837": {"cn_code": "601837", "name": "海通证券"},
    "06066": {"cn_code": "601688", "name": "华泰证券"},
    "06886": {"cn_code": "601788", "name": "光大证券"},
    "01398": {"cn_code": "601398", "name": "工商银行"},
    "03968": {"cn_code": "601968", "name": "招商银行"},

    # 能源化工
    "00857": {"cn_code": "601857", "name": "中国石油"},
    "00386": {"cn_code": "600028", "name": "中国石化"},
    "00902": {"cn_code": "600585", "name": "海螺水泥"},
    "00338": {"cn_code": "600688", "name": "上海石化"},
    "01033": {"cn_code": "600871", "name": "中石化油服"},
    "03996": {"cn_code": "601898", "name": "中煤能源"},
    "01898": {"cn_code": "601898", "name": "中煤能源"},
    "06186": {"cn_code": "601186", "name": "中国铁建"},
    "00323": {"cn_code": "600808", "name": "马钢股份"},
    "00347": {"cn_code": "000898", "name": "鞍钢股份"},
    "01053": {"cn_code": "601005", "name": "重庆钢铁"},

    # 基建地产
    "00390": {"cn_code": "600519", "name": "中国中铁"},
    "00669": {"cn_code": "601390", "name": "中国中铁"},
    "01800": {"cn_code": "601668", "name": "中国建筑"},
    "02866": {"cn_code": "601866", "name": "中远海发"},
    "01919": {"cn_code": "601919", "name": "中远海控"},
    "02883": {"cn_code": "601288", "name": "中海油服"},

    # 科技制造
    "00981": {"cn_code": "688981", "name": "中芯国际"},
    "01347": {"cn_code": "688347", "name": "华虹公司"},
    "02382": {"cn_code": "600584", "name": "长电科技"},
    "00268": {"cn_code": "002594", "name": "比亚迪"},
    "01345": {"cn_code": "688008", "name": "澜起科技"},

    # 通信
    "00762": {"cn_code": "600050", "name": "中国联通"},
    "00728": {"cn_code": "601727", "name": "中国电信"},
    "00941": {"cn_code": "600941", "name": "中国移动"},

    # 航空运输
    "00670": {"cn_code": "601111", "name": "中国国航"},
    "00696": {"cn_code": "600029", "name": "南方航空"},
    "01055": {"cn_code": "600115", "name": "东方航空"},
    "02888": {"cn_code": "601288", "name": "上汽集团"},

    # 医药
    "01093": {"cn_code": "600276", "name": "恒瑞医药"},
    "02196": {"cn_code": "002821", "name": "复星医药"},

    # 消费
    "01918": {"cn_code": "601888", "name": "中国中免"},
    "00588": {"cn_code": "601588", "name": "北辰实业"},
    "01211": {"cn_code": "601211", "name": "国泰君安"},

    # 电力
    "00991": {"cn_code": "601991", "name": "大唐发电"},
    "00902": {"cn_code": "600795", "name": "国电电力"},
    "01071": {"cn_code": "600886", "name": "国投电力"},

    # 其他
    "01618": {"cn_code": "601618", "name": "中国中冶"},
    "01766": {"cn_code": "601766", "name": "中国中车"},
    "01133": {"cn_code": "601633", "name": "长城汽车"},
    "02333": {"cn_code": "601233", "name": "长城汽车"},
    "02338": {"cn_code": "600104", "name": "上汽集团"},
    "01772": {"cn_code": "002460", "name": "赣锋锂业"},
    "09696": {"cn_code": "002466", "name": "天齐锂业"},
    "01989": {"cn_code": "001389", "name": "广合科技"},
    "02676": {"cn_code": "688052", "name": "纳芯微"},
    "02579": {"cn_code": "300919", "name": "中伟新材"},
    "06821": {"cn_code": "002821", "name": "凯莱英"},
    "00501": {"cn_code": "603501", "name": "豪威集团"},
    "03200": {"cn_code": "301200", "name": "大族数控"},
    "02009": {"cn_code": "601992", "name": "金隅集团"},
    "01528": {"cn_code": "601828", "name": "红星美凯龙"},
    "02016": {"cn_code": "601916", "name": "浙商银行"},
    "01812": {"cn_code": "000488", "name": "晨鸣纸业"},
    "00525": {"cn_code": "601333", "name": "广深铁路"},
    "00895": {"cn_code": "002672", "name": "东江环保"},
    "01375": {"cn_code": "601375", "name": "中原证券"},
    "03369": {"cn_code": "601326", "name": "秦港股份"},
    "02880": {"cn_code": "601880", "name": "辽港股份"},
    "06196": {"cn_code": "002936", "name": "郑州银行"},
}

# US to HK reverse mapping
US_HK_MAPPING = {
    v["us_symbol"]: {"hk_code": k, "name": v["name"]}
    for k, v in HK_US_ADR_MAPPING.items()
}

# CN to HK reverse mapping from static A+H data
CN_HK_MAPPING_STATIC = {
    v["cn_code"]: {"hk_code": k, "name": v["name"]}
    for k, v in AH_STOCK_MAPPING_STATIC.items()
}


@lru_cache(maxsize=1)
def get_ah_stock_mapping() -> pd.DataFrame:
    """
    Get A-share to H-share stock mapping from akshare.
    Falls back to static mapping if API fails.

    Returns:
        DataFrame with columns: 名称, H股代码, A股代码
    """
    try:
        import akshare as ak
        df = ak.stock_zh_ah_spot_em()
        logger.info(f"Loaded {len(df)} A+H stocks from akshare")
        return df[["名称", "H股代码", "A股代码"]]
    except Exception as e:
        logger.warning(f"Failed to load A+H stock mapping from API: {e}, using static fallback")
        # Return static mapping as DataFrame
        static_data = []
        for hk_code, info in AH_STOCK_MAPPING_STATIC.items():
            static_data.append({
                "名称": info["name"],
                "H股代码": hk_code,
                "A股代码": info["cn_code"]
            })
        return pd.DataFrame(static_data)


def normalize_hk_code(code: str) -> str:
    """
    Normalize Hong Kong stock code to 5-digit format.

    Args:
        code: Stock code in any format (e.g., "0700", "700", "0700.HK")

    Returns:
        Normalized 5-digit code (e.g., "0700")
    """
    if not code:
        return ""

    # Remove exchange suffix
    code = str(code).upper().strip()
    if ".HK" in code:
        code = code.replace(".HK", "")

    # Pad to 5 digits
    if code.isdigit():
        return code.zfill(5)
    return code


def normalize_cn_code(code: str) -> str:
    """
    Normalize China A-share stock code.

    Args:
        code: Stock code in any format (e.g., "600519", "600519.SH")

    Returns:
        Code without exchange suffix (e.g., "600519")
    """
    if not code:
        return ""

    code = str(code).upper().strip()
    for suffix in [".SH", ".SZ", ".BJ"]:
        code = code.replace(suffix, "")

    return code


def get_cross_market_tickers(ticker: str) -> dict:
    """
    Get all related tickers for a stock across markets.

    Args:
        ticker: Input ticker symbol (e.g., "600519.SH", "0700.HK", "BABA")

    Returns:
        Dictionary with market tickers and name:
        {
            "name": "公司名称",
            "primary": "0700.HK",
            "cn_a": "600519.SH",  # If A+H listed
            "hk": "0700.HK",      # If HK listed
            "us": "TCEHY"         # If US listed
        }
    """
    result = {
        "name": None,
        "primary": ticker,
        "cn_a": None,
        "hk": None,
        "us": None,
    }

    if not ticker:
        return result

    ticker = str(ticker).upper().strip()

    # Detect market type
    is_hk = ticker.endswith(".HK") or (ticker.isdigit() and len(ticker.zfill(5)) == 5 and not ticker.startswith(("6", "0", "3")))
    is_cn_a = ticker.endswith((".SH", ".SZ", ".BJ")) or (ticker.isdigit() and len(ticker) == 6 and ticker.startswith(("0", "3", "6")))
    is_us = ticker.isalpha() and not ticker.endswith((".HK", ".SH", ".SZ"))

    # Get A+H mapping from API (with static fallback)
    ah_df = get_ah_stock_mapping()
    use_static_ah = ah_df.empty

    def _find_cn_from_hk(hk_code: str) -> tuple:
        """Find CN code from HK code, using API or static fallback."""
        if not use_static_ah:
            match = ah_df[ah_df["H股代码"] == hk_code]
            if not match.empty:
                return normalize_cn_code(str(match.iloc[0]["A股代码"])), match.iloc[0]["名称"]
        # Use static fallback
        if hk_code in AH_STOCK_MAPPING_STATIC:
            return AH_STOCK_MAPPING_STATIC[hk_code]["cn_code"], AH_STOCK_MAPPING_STATIC[hk_code]["name"]
        return None, None

    def _find_hk_from_cn(cn_code: str) -> tuple:
        """Find HK code from CN code, using API or static fallback."""
        if not use_static_ah:
            match = ah_df[ah_df["A股代码"] == cn_code]
            if not match.empty:
                return normalize_hk_code(str(match.iloc[0]["H股代码"])), match.iloc[0]["名称"]
        # Use static fallback
        if cn_code in CN_HK_MAPPING_STATIC:
            return CN_HK_MAPPING_STATIC[cn_code]["hk_code"], CN_HK_MAPPING_STATIC[cn_code]["name"]
        return None, None

    if is_cn_a:
        # Input is A-share, find H-share
        cn_code = normalize_cn_code(ticker)
        result["cn_a"] = f"{cn_code}.SH" if cn_code.startswith("6") else f"{cn_code}.SZ"

        # Find in A+H mapping
        hk_code, name = _find_hk_from_cn(cn_code)
        if hk_code:
            result["hk"] = f"{hk_code}.HK"
            result["name"] = name

        # Check if also has US listing
        if result["hk"]:
            hk_code = normalize_hk_code(result["hk"].replace(".HK", ""))
            if hk_code in HK_US_ADR_MAPPING:
                result["us"] = HK_US_ADR_MAPPING[hk_code]["us_symbol"]

    elif is_hk:
        # Input is HK stock
        hk_code = normalize_hk_code(ticker.replace(".HK", ""))
        result["hk"] = f"{hk_code}.HK"

        # Find in A+H mapping
        cn_code, name = _find_cn_from_hk(hk_code)
        if cn_code:
            result["cn_a"] = f"{cn_code}.SH" if cn_code.startswith("6") else f"{cn_code}.SZ"
            result["name"] = name

        # Check US ADR mapping
        if hk_code in HK_US_ADR_MAPPING:
            result["us"] = HK_US_ADR_MAPPING[hk_code]["us_symbol"]
            if not result["name"]:
                result["name"] = HK_US_ADR_MAPPING[hk_code]["name"]

    elif is_us:
        # Input is US stock
        result["us"] = ticker

        # Find HK equivalent
        if ticker in US_HK_MAPPING:
            hk_code = US_HK_MAPPING[ticker]["hk_code"]
            result["hk"] = f"{hk_code}.HK"
            result["name"] = US_HK_MAPPING[ticker]["name"]

            # Check A+H mapping
            cn_code, name = _find_cn_from_hk(hk_code)
            if cn_code:
                result["cn_a"] = f"{cn_code}.SH" if cn_code.startswith("6") else f"{cn_code}.SZ"

    return result


def get_cross_market_summary(ticker: str) -> str:
    """
    Get a human-readable summary of cross-market listings.

    Args:
        ticker: Input ticker symbol

    Returns:
        Formatted string describing cross-market listings
    """
    info = get_cross_market_tickers(ticker)

    if not any([info["cn_a"], info["hk"], info["us"]]):
        return f"股票 {ticker} 未发现跨市场上市"

    lines = []
    if info["name"]:
        lines.append(f"股票名称: {info['name']}")

    market_list = []
    if info["cn_a"]:
        market_list.append(f"A股: {info['cn_a']}")
    if info["hk"]:
        market_list.append(f"港股: {info['hk']}")
    if info["us"]:
        market_list.append(f"美股: {info['us']}")

    lines.append("跨市场上市: " + " | ".join(market_list))

    return "\n".join(lines)


def has_cross_market_listing(ticker: str) -> bool:
    """
    Check if a stock is listed on multiple markets.

    Args:
        ticker: Input ticker symbol

    Returns:
        True if the stock is listed on multiple markets
    """
    info = get_cross_market_tickers(ticker)
    count = sum(1 for k in ["cn_a", "hk", "us"] if info[k])
    return count > 1


# Module-level cache refresh function
def refresh_ah_mapping():
    """Clear the cache and refresh A+H stock mapping."""
    get_ah_stock_mapping.cache_clear()
    logger.info("A+H stock mapping cache cleared")
