import argparse
import unittest

from scripts.generate_openclaw_watchlist import build_tasks
from tradingagents.default_config import DEFAULT_CONFIG


class OpenClawTaskDefaultsTests(unittest.TestCase):
    def test_generated_tasks_omit_central_default_model_fields(self):
        args = argparse.Namespace(
            preset="hk_internet",
            output=None,
            tickers="",
            tickers_file=None,
            provider=DEFAULT_CONFIG["llm_provider"],
            quick_model=DEFAULT_CONFIG["quick_think_llm"],
            deep_model=DEFAULT_CONFIG["deep_think_llm"],
            backend_url=DEFAULT_CONFIG["backend_url"],
            research_depth=1,
            analysts="market,social,news,fundamentals",
            analysis_date="today",
            skip_translation=False,
        )

        tasks = build_tasks(args)

        self.assertTrue(tasks)
        for task in tasks:
            self.assertNotIn("provider", task)
            self.assertNotIn("quick_model", task)
            self.assertNotIn("deep_model", task)
            self.assertNotIn("backend_url", task)

    def test_generated_tasks_keep_explicit_overrides(self):
        args = argparse.Namespace(
            preset="hk_internet",
            output=None,
            tickers="",
            tickers_file=None,
            provider="ollama",
            quick_model="gpt-oss:latest",
            deep_model="glm-4.7-flash:latest",
            backend_url="http://localhost:11434/v1",
            research_depth=1,
            analysts="market,social,news,fundamentals",
            analysis_date="today",
            skip_translation=False,
        )

        task = build_tasks(args)[0]

        self.assertEqual(task["provider"], "ollama")
        self.assertEqual(task["quick_model"], "gpt-oss:latest")
        self.assertEqual(task["deep_model"], "glm-4.7-flash:latest")
        self.assertEqual(task["backend_url"], "http://localhost:11434/v1")


if __name__ == "__main__":
    unittest.main()
