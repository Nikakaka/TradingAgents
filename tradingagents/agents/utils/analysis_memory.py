"""Analysis memory with historical calibration support.

Extends the existing FinancialSituationMemory with:
1. Analysis history storage (ticker, date, signal, confidence, outcome)
2. Accuracy calibration based on historical performance
3. Persistent storage in ~/.tradingagents/memory/
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# Default memory storage directory
_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")
_MEMORY_DIR = os.path.join(_TRADINGAGENTS_HOME, "memory")


@dataclass
class AnalysisRecord:
    """A single analysis record with outcome tracking."""

    ticker: str
    analysis_date: str
    signal: str  # buy, hold, sell
    confidence: float
    reasoning: str = ""
    price_at_analysis: Optional[float] = None
    outcome_5d: Optional[float] = None  # Price change % after 5 days
    outcome_20d: Optional[float] = None  # Price change % after 20 days
    was_correct: Optional[bool] = None  # Based on outcome vs signal
    recorded_at: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_name: str = "portfolio_manager"

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "AnalysisRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CalibrationResult:
    """Result of calibration calculation."""

    calibrated: bool
    calibration_factor: float = 1.0
    total_samples: int = 0
    accuracy: float = 0.5
    buy_accuracy: float = 0.5
    sell_accuracy: float = 0.5
    hold_accuracy: float = 0.5


class AnalysisMemory:
    """Memory system for storing analysis history and calibrating confidence.

    Features:
    1. Store analysis records with ticker, date, signal, confidence
    2. Track outcomes (price changes after 5d, 20d)
    3. Calculate accuracy per ticker and per signal type
    4. Provide calibration factors to adjust LLM confidence

    Storage: JSON files in ~/.tradingagents/memory/
    - analyses.json: All analysis records
    - outcomes.json: Records with outcome tracking
    """

    def __init__(self, memory_dir: str = None):
        """Initialize the analysis memory.

        Args:
            memory_dir: Directory for persistent storage. Defaults to ~/.tradingagents/memory/
        """
        self.memory_dir = Path(memory_dir or _MEMORY_DIR)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.analyses_file = self.memory_dir / "analyses.json"
        self.situations_memory = FinancialSituationMemory("situations")

        self._records: List[AnalysisRecord] = []
        self._load_records()

    def _load_records(self):
        """Load existing records from storage."""
        if self.analyses_file.exists():
            try:
                with open(self.analyses_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._records = [AnalysisRecord.from_dict(r) for r in data]
                logger.info(f"Loaded {len(self._records)} analysis records from {self.analyses_file}")
            except Exception as e:
                logger.warning(f"Failed to load analysis records: {e}")
                self._records = []

    def _save_records(self):
        """Persist records to storage."""
        try:
            with open(self.analyses_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self._records], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save analysis records: {e}")

    def record_analysis(
        self,
        ticker: str,
        analysis_date: str,
        signal: str,
        confidence: float,
        reasoning: str = "",
        price: Optional[float] = None,
        agent_name: str = "portfolio_manager",
    ) -> AnalysisRecord:
        """Record a new analysis.

        Args:
            ticker: Stock ticker symbol
            analysis_date: Date of analysis (YYYY-MM-DD)
            signal: Trading signal (buy, hold, sell)
            confidence: Confidence level (0-1)
            reasoning: Analysis reasoning
            price: Price at time of analysis
            agent_name: Name of the agent making the analysis

        Returns:
            The created AnalysisRecord
        """
        record = AnalysisRecord(
            ticker=ticker,
            analysis_date=analysis_date,
            signal=signal.lower(),
            confidence=min(1.0, max(0.0, confidence)),
            reasoning=reasoning[:500] if reasoning else "",  # Truncate long reasoning
            price_at_analysis=price,
            agent_name=agent_name,
        )
        self._records.append(record)
        self._save_records()
        logger.info(f"Recorded analysis: {ticker} {signal} (confidence={confidence:.2f})")
        return record

    def update_outcome(
        self,
        ticker: str,
        analysis_date: str,
        outcome_5d: Optional[float] = None,
        outcome_20d: Optional[float] = None,
        current_price: Optional[float] = None,
    ) -> Optional[AnalysisRecord]:
        """Update outcome for an existing analysis record.

        Args:
            ticker: Stock ticker symbol
            analysis_date: Date of the original analysis
            outcome_5d: Price change % after 5 trading days
            outcome_20d: Price change % after 20 trading days
            current_price: Current price (for calculating outcome if not provided)

        Returns:
            Updated AnalysisRecord or None if not found
        """
        # Find the record
        for record in reversed(self._records):
            if record.ticker == ticker and record.analysis_date == analysis_date:
                if outcome_5d is not None:
                    record.outcome_5d = outcome_5d
                if outcome_20d is not None:
                    record.outcome_20d = outcome_20d

                # Calculate if the analysis was correct
                record.was_correct = self._evaluate_correctness(
                    record.signal, record.outcome_5d, record.outcome_20d
                )

                self._save_records()
                logger.info(
                    f"Updated outcome for {ticker} {analysis_date}: "
                    f"5d={outcome_5d:.2%}%, 20d={outcome_20d:.2%}%, correct={record.was_correct}"
                )
                return record

        logger.warning(f"Analysis record not found: {ticker} {analysis_date}")
        return None

    def _evaluate_correctness(
        self,
        signal: str,
        outcome_5d: Optional[float],
        outcome_20d: Optional[float],
    ) -> Optional[bool]:
        """Evaluate if the analysis was correct based on outcome.

        Logic:
        - buy signal correct if price went up
        - sell signal correct if price went down
        - hold signal correct if price stayed relatively flat

        Returns:
            True if correct, False if incorrect, None if cannot determine
        """
        # Use 5d outcome if available, otherwise 20d
        outcome = outcome_5d if outcome_5d is not None else outcome_20d
        if outcome is None:
            return None

        # Threshold for "flat" movement (±2%)
        flat_threshold = 0.02

        if signal == "buy":
            # Buy signal correct if price went up
            return outcome > flat_threshold
        elif signal == "sell":
            # Sell signal correct if price went down
            return outcome < -flat_threshold
        else:  # hold
            # Hold signal correct if price stayed relatively flat
            return abs(outcome) <= flat_threshold

    def get_calibration(
        self,
        ticker: Optional[str] = None,
        signal: Optional[str] = None,
        agent_name: Optional[str] = None,
        min_samples: int = 5,
    ) -> CalibrationResult:
        """Calculate calibration factor based on historical accuracy.

        Args:
            ticker: Filter by ticker (optional)
            signal: Filter by signal type (optional)
            agent_name: Filter by agent name (optional)
            min_samples: Minimum samples required for calibration

        Returns:
            CalibrationResult with calibration factor
        """
        # Filter records
        filtered = self._records

        if ticker:
            filtered = [r for r in filtered if r.ticker == ticker]
        if signal:
            filtered = [r for r in filtered if r.signal == signal.lower()]
        if agent_name:
            filtered = [r for r in filtered if r.agent_name == agent_name]

        # Only consider records with outcomes
        with_outcomes = [r for r in filtered if r.was_correct is not None]

        if len(with_outcomes) < min_samples:
            return CalibrationResult(calibrated=False, total_samples=len(with_outcomes))

        # Calculate overall accuracy
        correct_count = sum(1 for r in with_outcomes if r.was_correct)
        accuracy = correct_count / len(with_outcomes)

        # Calculate per-signal accuracy
        buy_records = [r for r in with_outcomes if r.signal == "buy"]
        sell_records = [r for r in with_outcomes if r.signal == "sell"]
        hold_records = [r for r in with_outcomes if r.signal == "hold"]

        buy_accuracy = (
            sum(1 for r in buy_records if r.was_correct) / len(buy_records)
            if buy_records else 0.5
        )
        sell_accuracy = (
            sum(1 for r in sell_records if r.was_correct) / len(sell_records)
            if sell_records else 0.5
        )
        hold_accuracy = (
            sum(1 for r in hold_records if r.was_correct) / len(hold_records)
            if hold_records else 0.5
        )

        # Calibration factor: adjust confidence based on accuracy
        # If accuracy > 50%, confidence should be boosted
        # If accuracy < 50%, confidence should be reduced
        # Factor = accuracy / 0.5 (normalized to 50% baseline)
        # Clamp to reasonable range [0.5, 1.5]
        calibration_factor = max(0.5, min(1.5, accuracy / 0.5))

        return CalibrationResult(
            calibrated=True,
            calibration_factor=calibration_factor,
            total_samples=len(with_outcomes),
            accuracy=accuracy,
            buy_accuracy=buy_accuracy,
            sell_accuracy=sell_accuracy,
            hold_accuracy=hold_accuracy,
        )

    def get_ticker_history(
        self,
        ticker: str,
        limit: int = 10,
    ) -> List[AnalysisRecord]:
        """Get recent analysis history for a ticker.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of records to return

        Returns:
            List of AnalysisRecord sorted by date (most recent first)
        """
        records = [r for r in self._records if r.ticker == ticker]
        records.sort(key=lambda r: r.analysis_date, reverse=True)
        return records[:limit]

    def get_recent_analyses(self, days: int = 30) -> List[AnalysisRecord]:
        """Get analyses from the last N days that need outcome tracking.

        Args:
            days: Number of days to look back

        Returns:
            List of AnalysisRecord that may need outcome updates
        """
        from datetime import datetime, timedelta

        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return [
            r for r in self._records
            if r.analysis_date >= cutoff and r.was_correct is None
        ]

    def add_situations(self, situations_and_advice: List[Tuple[str, str]]):
        """Add situations to the BM25 memory for similarity matching."""
        self.situations_memory.add_situations(situations_and_advice)

    def get_similar_situations(self, current_situation: str, n_matches: int = 1) -> List[dict]:
        """Find similar historical situations using BM25."""
        return self.situations_memory.get_memories(current_situation, n_matches)

    def get_stats(self) -> Dict:
        """Get memory statistics."""
        total = len(self._records)
        with_outcomes = len([r for r in self._records if r.was_correct is not None])
        correct = sum(1 for r in self._records if r.was_correct is True)

        by_signal = {}
        for signal in ["buy", "hold", "sell"]:
            records = [r for r in self._records if r.signal == signal]
            with_out = [r for r in records if r.was_correct is not None]
            by_signal[signal] = {
                "total": len(records),
                "with_outcome": len(with_out),
                "correct": sum(1 for r in with_out if r.was_correct),
            }

        return {
            "total_analyses": total,
            "with_outcomes": with_outcomes,
            "overall_correct": correct,
            "by_signal": by_signal,
        }


class FinancialSituationMemory:
    """Memory system for storing and retrieving financial situations using BM25.

    This is the original implementation kept for backward compatibility.
    """

    def __init__(self, name: str, config: dict = None):
        """Initialize the memory system.

        Args:
            name: Name identifier for this memory instance
            config: Configuration dict (kept for API compatibility, not used for BM25)
        """
        self.name = name
        self.documents: List[str] = []
        self.recommendations: List[str] = []
        self.bm25 = None

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25 indexing.

        Simple whitespace + punctuation tokenization with lowercasing.
        """
        tokens = re.findall(r'\b\w+\b', text.lower())
        return tokens

    def _rebuild_index(self):
        """Rebuild the BM25 index after adding documents."""
        if self.documents:
            tokenized_docs = [self._tokenize(doc) for doc in self.documents]
            self.bm25 = BM25Okapi(tokenized_docs)
        else:
            self.bm25 = None

    def add_situations(self, situations_and_advice: List[Tuple[str, str]]):
        """Add financial situations and their corresponding advice.

        Args:
            situations_and_advice: List of tuples (situation, recommendation)
        """
        for situation, recommendation in situations_and_advice:
            self.documents.append(situation)
            self.recommendations.append(recommendation)

        self._rebuild_index()

    def get_memories(self, current_situation: str, n_matches: int = 1) -> List[dict]:
        """Find matching recommendations using BM25 similarity.

        Args:
            current_situation: The current financial situation to match against
            n_matches: Number of top matches to return

        Returns:
            List of dicts with matched_situation, recommendation, and similarity_score
        """
        if not self.documents or self.bm25 is None:
            return []

        query_tokens = self._tokenize(current_situation)
        scores = self.bm25.get_scores(query_tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_matches]

        results = []
        max_score = float(scores.max()) if len(scores) > 0 and scores.max() > 0 else 1.0

        for idx in top_indices:
            normalized_score = scores[idx] / max_score if max_score > 0 else 0
            results.append({
                "matched_situation": self.documents[idx],
                "recommendation": self.recommendations[idx],
                "similarity_score": normalized_score,
            })

        return results

    def clear(self):
        """Clear all stored memories."""
        self.documents = []
        self.recommendations = []
        self.bm25 = None


# Singleton instance for global access
_analysis_memory: Optional[AnalysisMemory] = None


def get_analysis_memory() -> AnalysisMemory:
    """Get the singleton AnalysisMemory instance."""
    global _analysis_memory
    if _analysis_memory is None:
        _analysis_memory = AnalysisMemory()
    return _analysis_memory


def record_analysis(
    ticker: str,
    analysis_date: str,
    signal: str,
    confidence: float,
    reasoning: str = "",
    price: Optional[float] = None,
    agent_name: str = "portfolio_manager",
) -> AnalysisRecord:
    """Convenience function to record an analysis."""
    return get_analysis_memory().record_analysis(
        ticker=ticker,
        analysis_date=analysis_date,
        signal=signal,
        confidence=confidence,
        reasoning=reasoning,
        price=price,
        agent_name=agent_name,
    )


def get_calibration(
    ticker: Optional[str] = None,
    signal: Optional[str] = None,
) -> CalibrationResult:
    """Convenience function to get calibration."""
    return get_analysis_memory().get_calibration(ticker=ticker, signal=signal)
