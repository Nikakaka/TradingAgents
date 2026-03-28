import unittest

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.model_registry import DEFAULT_PROVIDER, get_provider_defaults
from tradingagents.web_server import get_ui_options


class ModelRegistryTests(unittest.TestCase):
    def test_default_config_uses_registry_defaults(self):
        defaults = get_provider_defaults(DEFAULT_PROVIDER)

        self.assertEqual(DEFAULT_CONFIG["llm_provider"], defaults["provider"])
        self.assertEqual(DEFAULT_CONFIG["quick_think_llm"], defaults["quick_model"])
        self.assertEqual(DEFAULT_CONFIG["deep_think_llm"], defaults["deep_model"])
        self.assertEqual(DEFAULT_CONFIG["backend_url"], defaults["backend_url"])

    def test_web_defaults_follow_registry_defaults(self):
        defaults = get_provider_defaults(DEFAULT_PROVIDER)
        ui_defaults = get_ui_options()["defaults"]

        self.assertEqual(ui_defaults["provider"], defaults["provider"])
        self.assertEqual(ui_defaults["quick_model"], defaults["quick_model"])
        self.assertEqual(ui_defaults["deep_model"], defaults["deep_model"])


if __name__ == "__main__":
    unittest.main()
