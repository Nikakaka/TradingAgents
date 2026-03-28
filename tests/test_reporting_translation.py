import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tradingagents import reporting, web_server


class _ResponseWithListContent:
    def __init__(self, content):
        self.content = content


class ReportingTranslationTests(unittest.TestCase):
    def test_extracts_text_from_typed_content_blocks(self):
        response = _ResponseWithListContent(
            [
                {"type": "reasoning", "text": "ignore me"},
                {"type": "text", "text": "# 中文报告"},
                {"type": "output_text", "output_text": "这是一段翻译"},
            ]
        )

        extracted = reporting._extract_text_from_llm_response(response)

        self.assertEqual(extracted, "# 中文报告\n这是一段翻译")

    def test_translate_report_raises_with_provider_and_model_when_empty(self):
        class _EmptyLLM:
            def invoke(self, prompt):
                return _ResponseWithListContent([])

        class _EmptyClient:
            def get_llm(self):
                return _EmptyLLM()

        with patch("tradingagents.reporting.create_llm_client", return_value=_EmptyClient()):
            with self.assertRaisesRegex(ValueError, "provider='openai' model='gpt-test'"):
                reporting.translate_report_to_chinese(
                    "# Report",
                    {
                        "llm_provider": "openai",
                        "deep_thinker": "gpt-test",
                        "shallow_thinker": None,
                        "backend_url": None,
                    },
                )


class JobManagerTranslationFallbackTests(unittest.TestCase):
    def test_run_job_completes_when_translation_fails(self):
        final_state = {
            "market_report": "Market section",
            "risk_debate_state": {"judge_decision": "FINAL TRANSACTION PROPOSAL: **HOLD**"},
        }

        class _FakeGraphRunner:
            def stream(self, init_state, **kwargs):
                yield final_state

        class _FakePropagator:
            def create_initial_state(self, ticker, analysis_date):
                return {"ticker": ticker, "analysis_date": analysis_date}

            def get_graph_args(self, callbacks=None):
                return {}

        class _FakeTradingAgentsGraph:
            def __init__(self, selected_analysts, config=None, debug=None, callbacks=None):
                self.propagator = _FakePropagator()
                self.graph = _FakeGraphRunner()

        class _FakeStatsHandler:
            def get_stats(self):
                return {}

        manager = web_server.JobManager()
        manager._jobs["job1"] = {
            "id": "job1",
            "status": "queued",
            "created_at": web_server._iso_now(),
            "started_at": None,
            "completed_at": None,
            "payload": {
                "ticker": "AAPL",
                "analysts": ["market"],
                "translate_to_chinese": True,
            },
            "progress": {},
            "result": None,
            "error": None,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("tradingagents.web_server.StatsCallbackHandler", return_value=_FakeStatsHandler()):
                with patch("tradingagents.web_server.resolve_ticker_input", return_value="AAPL"):
                    with patch("tradingagents.web_server.TradingAgentsGraph", _FakeTradingAgentsGraph):
                        with patch("tradingagents.web_server.translate_report_to_chinese", side_effect=ValueError("Translation response was empty.")):
                            with patch("tradingagents.web_server.REPORTS_DIR", Path(temp_dir)):
                                manager._run_job("job1")

        job = manager._jobs["job1"]
        self.assertEqual(job["status"], "completed")
        self.assertIsNone(job["error"])
        self.assertIn("Chinese translation skipped", job["result"]["warning"])
        self.assertEqual(job["result"]["ticker"], "AAPL")


if __name__ == "__main__":
    unittest.main()
