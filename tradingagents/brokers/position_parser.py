"""
Position file parser for TradingAgents.

This module provides utilities to parse position files exported from various
trading platforms (Tongdaxin, CSV, Excel) into a standardized format.

Supported formats:
- Tongdaxin exported files (.txt, .xls with GBK encoding)
- CSV files (GBK or UTF-8 encoding)
- Excel files (.xlsx, .xls)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Position:
    """Represents a stock position in the portfolio."""

    symbol: str  # 股票代码，如 "9988.HK"
    name: str = ""  # 股票名称
    quantity: int = 0  # 持仓数量（股）
    available: int = 0  # 可用数量
    cost_price: float = 0.0  # 成本价
    current_price: float = 0.0  # 当前价
    market_value: float = 0.0  # 市值
    profit_loss: float = 0.0  # 盈亏
    profit_loss_pct: float = 0.0  # 盈亏比例
    market: str = ""  # 市场：HK, SH, SZ

    def to_dict(self) -> dict:
        """Convert position to dictionary."""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "quantity": self.quantity,
            "available": self.available,
            "cost_price": self.cost_price,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "profit_loss": self.profit_loss,
            "profit_loss_pct": self.profit_loss_pct,
            "market": self.market,
        }


@dataclass
class AccountInfo:
    """Represents account information."""

    account_id: str  # 资金账号
    total_assets: float = 0.0  # 总资产
    cash: float = 0.0  # 可用资金
    market_value: float = 0.0  # 持仓市值
    profit_loss: float = 0.0  # 当日盈亏
    profit_loss_pct: float = 0.0  # 当日盈亏比例
    positions: list[Position] = field(default_factory=list)  # 持仓列表

    def to_dict(self) -> dict:
        """Convert account info to dictionary."""
        return {
            "account_id": self.account_id,
            "total_assets": self.total_assets,
            "cash": self.cash,
            "market_value": self.market_value,
            "profit_loss": self.profit_loss,
            "profit_loss_pct": self.profit_loss_pct,
            "positions": [p.to_dict() for p in self.positions],
        }


class PositionParser:
    """Parser for position files from various trading platforms."""

    def __init__(self, account_id: str = ""):
        """
        Initialize the position parser.

        Args:
            account_id: Optional account identifier
        """
        self.account_id = account_id or os.getenv("TRADING_ACCOUNT_ID", "")

    def get_positions_from_file(self, file_path: str) -> AccountInfo:
        """
        Parse positions from an exported file.

        Supports Tongdaxin exports, CSV, and Excel files.

        Args:
            file_path: Path to the exported positions file (CSV or Excel)

        Returns:
            AccountInfo with parsed positions
        """
        import pandas as pd

        file_path_lower = file_path.lower()

        # First, try to detect if this is a Tongdaxin exported file
        # Tongdaxin exports .xls/.txt files that are actually TSV with GBK encoding
        if file_path_lower.endswith((".xlsx", ".xls", ".txt")):
            # Try to read as TSV with GBK encoding first (Tongdaxin format)
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()

                # Check for position data markers (Chinese column names)
                # This works for both tab-separated and space-separated formats
                if '证券代码' in content or '证券名称' in content or '股票代码' in content:
                    result = self._parse_tdx_export(content)
                    if result.positions:
                        return result
            except (UnicodeDecodeError, UnicodeError):
                pass
            except Exception:
                pass

            # Try standard Excel parsing
            try:
                df = pd.read_excel(file_path, engine='openpyxl')
            except Exception:
                try:
                    df = pd.read_excel(file_path, engine='xlrd')
                except Exception:
                    # Last resort: try CSV parsing
                    try:
                        df = pd.read_csv(file_path, sep='\t', encoding='gbk')
                    except Exception:
                        df = pd.read_csv(file_path, encoding='gbk')
        elif file_path_lower.endswith(".csv"):
            # Try GBK encoding first for Chinese exports
            try:
                df = pd.read_csv(file_path, encoding='gbk')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

        # If we have a DataFrame, process it
        if 'df' in locals() and df is not None and len(df) > 0:
            return self._parse_dataframe(df)

        return AccountInfo(account_id=self.account_id)

    def _parse_tdx_export(self, content: str) -> AccountInfo:
        """Parse Tongdaxin exported position data.

        Tongdaxin exports are typically tab-separated or space-separated
        with Chinese column names and GBK encoding.
        """
        lines = content.strip().split('\n')

        # Find header line (contains column names)
        header_idx = -1
        for i, line in enumerate(lines):
            if '证券代码' in line or '证券名称' in line or '股票代码' in line:
                header_idx = i
                break

        if header_idx < 0:
            return AccountInfo(account_id=self.account_id)

        # Parse header
        header_line = lines[header_idx]
        if '\t' in header_line:
            headers = [self._clean_value(h) for h in header_line.split('\t')]
        else:
            headers = [self._clean_value(h) for h in header_line.split()]

        # Column mappings for Tongdaxin exports
        column_mappings = {
            "证券代码": "symbol",
            "股票代码": "symbol",
            "代码": "symbol",
            "证券名称": "name",
            "股票名称": "name",
            "名称": "name",
            "持仓数量": "quantity",
            "持仓": "quantity",
            "股份余额": "quantity",
            "股份昨余": "quantity",  # TDX format
            "实际数量": "quantity",  # TDX format
            "证券数量": "quantity",
            "股票余额": "quantity",
            "可用数量": "available",
            "可卖数量": "available",  # TDX format
            "可用": "available",
            "成本价": "cost_price",
            "买入均价": "cost_price",
            "持仓成本价": "cost_price",  # TDX format
            "持仓成本": "cost_price",
            "当前价": "current_price",
            "现价": "current_price",
            "最新价": "current_price",
            "市值": "market_value",
            "最新市值": "market_value",  # TDX format
            "盈亏": "profit_loss",
            "当日盈亏": "profit_loss",  # TDX format
            "浮动盈亏": "profit_loss",
            "持仓盈亏": "profit_loss",  # TDX format
            "盈亏比例": "profit_loss_pct",
            "盈亏比例(%)": "profit_loss_pct",  # TDX format
            "市场": "market",
        }

        # Map headers to column indices
        col_indices = {}
        for i, header in enumerate(headers):
            if header in column_mappings:
                col_indices[column_mappings[header]] = i

        # Parse data rows
        positions = []
        for line in lines[header_idx + 1:]:
            line = line.strip()
            if not line or line.startswith('-'):
                continue

            if '\t' in line:
                values = [self._clean_value(v) for v in line.split('\t')]
            else:
                values = [self._clean_value(v) for v in line.split()]

            if len(values) < 3:
                continue

            try:
                symbol = values[col_indices.get("symbol", 0)] if col_indices.get("symbol") is not None else ""
                if not symbol:
                    continue

                symbol = self._normalize_symbol(symbol)

                def get_value(key: str, default: str = "0") -> str:
                    idx = col_indices.get(key)
                    return values[idx] if idx is not None and idx < len(values) else default

                position = Position(
                    symbol=symbol,
                    name=get_value("name", ""),
                    quantity=int(float(get_value("quantity", "0"))),
                    available=int(float(get_value("available", get_value("quantity", "0")))),
                    cost_price=float(get_value("cost_price", "0")),
                    current_price=float(get_value("current_price", "0")),
                    market_value=float(get_value("market_value", "0")),
                    profit_loss=float(get_value("profit_loss", "0")),
                    profit_loss_pct=float(get_value("profit_loss_pct", "0")),
                    market=self._get_market_from_symbol(symbol),
                )

                # Calculate derived values if not provided
                if position.market_value == 0 and position.quantity > 0:
                    position.market_value = position.quantity * position.current_price

                positions.append(position)

            except Exception:
                continue

        return AccountInfo(
            account_id=self.account_id,
            positions=positions,
            market_value=sum(p.market_value for p in positions),
        )

    def _parse_dataframe(self, df) -> AccountInfo:
        """Parse a pandas DataFrame into AccountInfo."""
        import pandas as pd

        positions = []

        # Common column mappings for position exports
        column_mappings = {
            "股票代码": "symbol",
            "证券代码": "symbol",
            "代码": "symbol",
            "股票名称": "name",
            "证券名称": "name",
            "名称": "name",
            "持仓数量": "quantity",
            "持仓": "quantity",
            "股份余额": "quantity",
            "股份昨余": "quantity",  # TDX format
            "实际数量": "quantity",  # TDX format
            "证券数量": "quantity",
            "股票余额": "quantity",
            "可用数量": "available",
            "可卖数量": "available",  # TDX format
            "可用": "available",
            "成本价": "cost_price",
            "买入均价": "cost_price",
            "持仓成本价": "cost_price",  # TDX format
            "持仓成本": "cost_price",
            "当前价": "current_price",
            "现价": "current_price",
            "最新价": "current_price",
            "市值": "market_value",
            "最新市值": "market_value",  # TDX format
            "盈亏": "profit_loss",
            "当日盈亏": "profit_loss",  # TDX format
            "浮动盈亏": "profit_loss",
            "持仓盈亏": "profit_loss",  # TDX format
            "盈亏比例": "profit_loss_pct",
            "盈亏比例(%)": "profit_loss_pct",  # TDX format
            "市场": "market",
        }

        # Rename columns
        renamed_columns = {}
        for col in df.columns:
            col_stripped = str(col).strip()
            if col_stripped in column_mappings:
                renamed_columns[col] = column_mappings[col_stripped]

        df = df.rename(columns=renamed_columns)

        for _, row in df.iterrows():
            try:
                symbol = str(row.get("symbol", "")).strip()
                if not symbol:
                    continue

                # Normalize symbol format
                symbol = self._normalize_symbol(symbol)

                position = Position(
                    symbol=symbol,
                    name=str(row.get("name", "")).strip(),
                    quantity=int(float(row.get("quantity", 0) or 0)),
                    available=int(float(row.get("available", row.get("quantity", 0)) or 0)),
                    cost_price=float(row.get("cost_price", 0) or 0),
                    current_price=float(row.get("current_price", 0) or 0),
                    market_value=float(row.get("market_value", 0) or 0),
                    profit_loss=float(row.get("profit_loss", 0) or 0),
                    profit_loss_pct=float(row.get("profit_loss_pct", 0) or 0),
                    market=self._get_market_from_symbol(symbol),
                )

                # Calculate derived values if not provided
                if position.market_value == 0 and position.quantity > 0:
                    position.market_value = position.quantity * position.current_price

                positions.append(position)

            except Exception:
                continue

        return AccountInfo(
            account_id=self.account_id,
            positions=positions,
            market_value=sum(p.market_value for p in positions),
        )

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize stock symbol to TradingAgents format.

        TradingAgents uses format:
        - HK stocks: 9988.HK, 0700.HK (4-digit codes, with leading zero for codes < 1000)
        - Shanghai stocks: 600519.SH
        - Shenzhen stocks: 300750.SZ
        """
        if not symbol:
            return symbol

        symbol = symbol.strip()

        # Remove any suffixes like .SH, .SZ, .HK if present (will be re-added)
        base_symbol = symbol.upper().replace(".SH", "").replace(".SZ", "").replace(".HK", "")

        # Determine market from the original symbol or market field
        market = self._get_market_from_symbol(symbol)

        # Handle HK stocks (5-digit codes starting with 0)
        if market == "HK" or (len(base_symbol) == 5 and base_symbol.startswith("0")):
            # HK stock codes are 5 digits, but we use 4-digit format with leading zero
            code = base_symbol[-4:].zfill(4)
            return f"{code}.HK"

        # Handle Shanghai stocks (6xx, 60x, 68x, 9xx)
        if market == "SH" or base_symbol.startswith(("6", "9")):
            return f"{base_symbol}.SH"

        # Handle Shenzhen stocks (0xx, 3xx, 00xxxx)
        if market == "SZ" or base_symbol.startswith(("0", "3")):
            return f"{base_symbol}.SZ"

        # Default: return as-is with detected market
        return f"{base_symbol}.{market}" if market else base_symbol

    def _get_market_from_symbol(self, symbol: str) -> str:
        """Determine market from symbol format."""
        if not symbol:
            return ""

        symbol = symbol.upper()

        # Check for explicit market suffix
        if symbol.endswith(".HK"):
            return "HK"
        if symbol.endswith(".SH"):
            return "SH"
        if symbol.endswith(".SZ"):
            return "SZ"

        # Remove suffix for analysis
        base = symbol.replace(".SH", "").replace(".SZ", "").replace(".HK", "")

        # HK stocks: 5-digit codes starting with 0, 1, 2, 3, 4, 5, 6, 7, 8, 9
        # But typically 5-digit codes with leading zeros in Chinese systems
        if len(base) == 5 and base.startswith("0"):
            return "HK"
        # Common HK stock code ranges (without leading zeros)
        if len(base) <= 5 and base.isdigit():
            # Could be HK, check context
            pass

        # Shanghai: 6xx, 60x, 68x, 900xxx, 688xxx (STAR Market)
        if base.startswith(("6", "9")):
            return "SH"

        # Shenzhen: 0xx, 3xx, 00xxxx, 300xxx (ChiNext)
        if base.startswith(("0", "3")):
            return "SZ"

        # Default to Shanghai for unknown patterns
        return ""

    def _clean_value(self, value: str) -> str:
        """Clean a value from a CSV/Excel cell."""
        if not value:
            return ""
        value = str(value).strip()
        # Remove quotes
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        return value.strip()


# Backward compatibility alias
GuosenBroker = PositionParser
