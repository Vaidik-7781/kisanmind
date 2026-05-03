"""
KisanMind — Test Suite
Run: python -m pytest tests/ -v
or:  python tests/test_agents.py
"""

import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ═══════════════════════════════════════════════════════════
#   1. ORCHESTRATOR TESTS
# ═══════════════════════════════════════════════════════════

class TestOrchestrator(unittest.TestCase):

    def test_intent_classification_disease_keywords(self):
        from agents.orchestrator import classify_intent
        result = classify_intent("my tomato leaves have brown spots")
        self.assertEqual(result["intent"], "disease_detection")

    def test_intent_classification_weather(self):
        from agents.orchestrator import classify_intent
        result = classify_intent("what is the weather today")
        self.assertEqual(result["intent"], "weather")

    def test_intent_classification_price(self):
        from agents.orchestrator import classify_intent
        result = classify_intent("what is the mandi rate for wheat")
        self.assertEqual(result["intent"], "market_price")

    def test_intent_classification_finance(self):
        from agents.orchestrator import classify_intent
        result = classify_intent("how do I apply for PM-KISAN")
        self.assertEqual(result["intent"], "finance_subsidy")

    def test_intent_classification_greeting(self):
        from agents.orchestrator import classify_intent
        result = classify_intent("hello")
        self.assertEqual(result["intent"], "greeting")

    def test_intent_classification_image(self):
        from agents.orchestrator import classify_intent
        result = classify_intent("", has_image=True)
        self.assertEqual(result["intent"], "disease_detection")

    def test_commodity_extraction(self):
        from agents.orchestrator import _extract_commodity
        self.assertEqual(_extract_commodity("price of wheat today"), "wheat")
        self.assertEqual(_extract_commodity("tomato rate in mandi"), "tomato")
        self.assertIsNone(_extract_commodity("what is the weather"))

    def test_greeting_message_generated(self):
        from agents.orchestrator import _greeting_message
        with patch("agents.orchestrator.get_profile") as mock_profile:
            mock_profile.return_value = {"name": "Ramesh", "language": "hi", "location": None, "current_crops": [], "crop_history": [], "disease_events": []}
            msg = _greeting_message(12345)
            self.assertIn("KisanMind", msg)
            self.assertIn("Ramesh", msg)

    def test_help_message_has_all_commands(self):
        from agents.orchestrator import _help_message
        msg = _help_message()
        for cmd in ["/weather", "/price", "/plan", "/schemes", "/setlocation"]:
            self.assertIn(cmd, msg)


# ═══════════════════════════════════════════════════════════
#   2. TOOLS TESTS
# ═══════════════════════════════════════════════════════════

class TestWeatherTool(unittest.TestCase):

    @patch("tools.weather_tool.requests.get")
    def test_weather_returns_structure(self, mock_get):
        """Weather tool returns correct structure on success."""
        mock_curr = MagicMock()
        mock_curr.json.return_value = {
            "name": "Varanasi",
            "main":    {"temp": 32.5, "feels_like": 35.0, "humidity": 70},
            "weather": [{"description": "haze", "main": "Haze"}],
            "wind":    {"speed": 4.2},
            "rain":    {},
            "coord":   {"lat": 25.3, "lon": 82.97},
        }
        mock_fore = MagicMock()
        mock_fore.json.return_value = {"list": []}
        mock_get.side_effect = [mock_curr, mock_fore]

        from tools.weather_tool import get_current_weather
        result = get_current_weather(city="Varanasi")

        self.assertEqual(result["city"], "Varanasi")
        self.assertEqual(result["temperature"], 32.5)
        self.assertEqual(result["humidity"], 70)
        self.assertIn("alerts", result)

    def test_farm_alerts_high_humidity(self):
        from tools.weather_tool import _generate_farm_alerts
        current = {"main": {"humidity": 90, "temp": 28}}
        alerts = _generate_farm_alerts(current, [])
        self.assertTrue(any("HUMID" in a.upper() for a in alerts))

    def test_farm_alerts_heatwave(self):
        from tools.weather_tool import _generate_farm_alerts
        current = {"main": {"humidity": 50, "temp": 42}}
        alerts = _generate_farm_alerts(current, [])
        self.assertTrue(any("HEAT" in a.upper() for a in alerts))

    def test_farm_alerts_heavy_rain(self):
        from tools.weather_tool import _generate_farm_alerts
        current = {"main": {"humidity": 60, "temp": 25}}
        forecast = [{"date": "2026-05-01", "rain_mm": 35.0, "condition": "Rain", "min": 20, "max": 28}]
        alerts = _generate_farm_alerts(current, forecast)
        self.assertTrue(any("RAIN" in a.upper() for a in alerts))


class TestMandiTool(unittest.TestCase):

    def test_fallback_mock_returns_structure(self):
        from tools.mandi_tool import _fallback_mock
        result = _fallback_mock("wheat")
        self.assertEqual(result["commodity"], "wheat")
        self.assertGreater(result["avg_price"], 0)
        self.assertIn("recommendation", result)

    def test_price_base_known_crops(self):
        from tools.mandi_tool import _get_base_price
        self.assertEqual(_get_base_price("wheat"), 2200)
        self.assertEqual(_get_base_price("rice"), 2100)
        self.assertGreater(_get_base_price("unknown_crop"), 0)

    def test_safe_float_conversion(self):
        from tools.mandi_tool import _safe_float
        self.assertEqual(_safe_float("1,500"), 1500.0)
        self.assertEqual(_safe_float("2500"), 2500.0)
        self.assertEqual(_safe_float("N/A"), 0.0)

    def test_price_trend_returns_list(self):
        from tools.mandi_tool import get_price_trend
        trend = get_price_trend("wheat", days=7)
        self.assertEqual(len(trend), 7)
        for item in trend:
            self.assertIn("date", item)
            self.assertIn("price", item)
            self.assertGreater(item["price"], 0)


class TestVoiceTool(unittest.TestCase):

    def test_language_detection_hindi(self):
        from tools.voice_tool import detect_language_from_text
        hindi_text = "मेरी फसल में बीमारी है"
        self.assertEqual(detect_language_from_text(hindi_text), "hi")

    def test_language_detection_english(self):
        from tools.voice_tool import detect_language_from_text
        self.assertEqual(detect_language_from_text("hello how are you"), "en")

    def test_language_detection_telugu(self):
        from tools.voice_tool import detect_language_from_text
        telugu_text = "నా పంట"
        self.assertEqual(detect_language_from_text(telugu_text), "te")


# ═══════════════════════════════════════════════════════════
#   3. MEMORY TESTS
# ═══════════════════════════════════════════════════════════

class TestConversationMemory(unittest.TestCase):

    def setUp(self):
        from memory.conversation import clear_history
        clear_history(99999)  # use test ID

    def test_add_and_retrieve_messages(self):
        from memory.conversation import add_message, get_history
        add_message(99999, "user", "Hello")
        add_message(99999, "assistant", "Namaste!")
        history = get_history(99999)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "Hello")

    def test_history_trimmed_to_max_turns(self):
        from memory.conversation import add_message, get_history, clear_history
        from config.settings import MAX_HISTORY_TURNS
        clear_history(99998)
        # Add more than MAX turns
        for i in range(MAX_HISTORY_TURNS * 2 + 5):
            add_message(99998, "user", f"msg {i}")
            add_message(99998, "assistant", f"reply {i}")
        history = get_history(99998)
        self.assertLessEqual(len(history), MAX_HISTORY_TURNS * 2)

    def test_clear_history(self):
        from memory.conversation import add_message, get_history, clear_history
        add_message(99999, "user", "test")
        clear_history(99999)
        self.assertEqual(len(get_history(99999)), 0)

    def test_get_last_user_message(self):
        from memory.conversation import add_message, get_last_user_message, clear_history
        clear_history(99997)
        add_message(99997, "user", "first")
        add_message(99997, "assistant", "response")
        add_message(99997, "user", "second")
        self.assertEqual(get_last_user_message(99997), "second")


# ═══════════════════════════════════════════════════════════
#   4. PRICE FORECASTER TESTS
# ═══════════════════════════════════════════════════════════

class TestPriceForecaster(unittest.TestCase):

    def test_heuristic_forecast_structure(self):
        from models.price_forecaster import _heuristic_forecast
        result = _heuristic_forecast("wheat", 2200, 14)
        self.assertEqual(result["commodity"], "wheat")
        self.assertEqual(len(result["forecast"]), 14)
        self.assertIn(result["trend"], ["rising", "falling", "stable"])
        self.assertIn("best_sell_day", result)
        self.assertIn("recommendation", result)

    def test_forecast_prices_positive(self):
        from models.price_forecaster import _heuristic_forecast
        result = _heuristic_forecast("tomato", 1200, 7)
        for entry in result["forecast"]:
            self.assertGreater(entry["price"], 0)
            self.assertLessEqual(entry["lower"], entry["price"])
            self.assertGreaterEqual(entry["upper"], entry["price"])

    def test_detect_trend_rising(self):
        from models.price_forecaster import _detect_trend
        forecast = [{"price": 1000 + i * 50} for i in range(10)]
        self.assertEqual(_detect_trend(forecast), "rising")

    def test_detect_trend_falling(self):
        from models.price_forecaster import _detect_trend
        forecast = [{"price": 1000 - i * 50} for i in range(10)]
        self.assertEqual(_detect_trend(forecast), "falling")

    def test_detect_trend_stable(self):
        from models.price_forecaster import _detect_trend
        forecast = [{"price": 1000 + i} for i in range(10)]
        self.assertEqual(_detect_trend(forecast), "stable")

    def test_sell_recommendation_rising(self):
        from models.price_forecaster import _sell_recommendation
        rec = _sell_recommendation("rising", 2000, 2300, "2026-05-10")
        self.assertIn("WAIT", rec.upper())

    def test_sell_recommendation_falling(self):
        from models.price_forecaster import _sell_recommendation
        rec = _sell_recommendation("falling", 2000, 1800, "2026-05-10")
        self.assertIn("SELL", rec.upper())


# ═══════════════════════════════════════════════════════════
#   5. FINANCE AGENT TESTS
# ═══════════════════════════════════════════════════════════

class TestFinanceAgent(unittest.TestCase):

    def test_quick_match_pm_kisan(self):
        from agents.finance_agent import _quick_match
        result = _quick_match("how to apply for PM-KISAN")
        self.assertIsNotNone(result)
        self.assertIn("PM-KISAN", result["name"])

    def test_quick_match_pmfby(self):
        from agents.finance_agent import _quick_match
        result = _quick_match("crop insurance fasal bima")
        self.assertIsNotNone(result)
        self.assertIn("PMFBY", result["name"])

    def test_quick_match_kcc(self):
        from agents.finance_agent import _quick_match
        result = _quick_match("kisan credit card loan")
        self.assertIsNotNone(result)

    def test_quick_match_none(self):
        from agents.finance_agent import _quick_match
        result = _quick_match("tomato disease treatment")
        self.assertIsNone(result)

    def test_format_scheme_has_required_fields(self):
        from agents.finance_agent import _format_scheme, SCHEME_QUICK_REF
        text = _format_scheme(SCHEME_QUICK_REF["pm-kisan"], acres=2.0)
        self.assertIn("₹6,000", text)
        self.assertIn("Aadhaar", text)
        self.assertIn("pmkisan.gov.in", text)

    def test_all_schemes_summary(self):
        from agents.finance_agent import get_all_schemes_summary
        summary = get_all_schemes_summary()
        self.assertIn("PM-KISAN", summary)
        self.assertIn("PMFBY", summary)
        self.assertIn("1800-180-1551", summary)


# ═══════════════════════════════════════════════════════════
#   6. CROP PLAN AGENT TESTS
# ═══════════════════════════════════════════════════════════

class TestCropPlanAgent(unittest.TestCase):

    def test_get_current_season(self):
        from agents.crop_plan_agent import _get_current_season
        season = _get_current_season()
        self.assertIn(season, ["kharif", "rabi", "zaid"])

    def test_suitable_crops_for_rabi(self):
        from agents.crop_plan_agent import _get_suitable_crops
        crops = _get_suitable_crops("rabi", "loamy", [], [])
        names = [c["crop"] for c in crops]
        self.assertIn("wheat", names)

    def test_no_repeat_of_current_crops(self):
        from agents.crop_plan_agent import _get_suitable_crops
        current = [{"name": "wheat"}]
        crops = _get_suitable_crops("rabi", "loamy", [], current)
        names = [c["crop"] for c in crops]
        self.assertNotIn("wheat", names)

    def test_soil_match_black_soil(self):
        from agents.crop_plan_agent import _soil_match
        self.assertTrue(_soil_match("black", "cotton"))
        self.assertTrue(_soil_match("black", "soybean"))

    def test_fallback_recommendations(self):
        from agents.crop_plan_agent import _fallback_recommendations, _get_suitable_crops
        suitable = _get_suitable_crops("kharif", "loamy", [], [])
        text = _fallback_recommendations(suitable, "kharif", 2.0)
        self.assertIn("kharif", text.lower())
        self.assertIn("₹", text)


# ═══════════════════════════════════════════════════════════
#   7. MESSAGE FORMATTER TESTS
# ═══════════════════════════════════════════════════════════

class TestMessageFormatter(unittest.TestCase):

    def test_format_for_telegram_short(self):
        from interface.message_formatter import format_for_telegram
        text = "Hello farmer!"
        self.assertEqual(format_for_telegram(text), "Hello farmer!")

    def test_format_for_telegram_truncates_long(self):
        from interface.message_formatter import format_for_telegram
        long_text = "x" * 5000
        result = format_for_telegram(long_text)
        self.assertLessEqual(len(result), 4096 + 50)

    def test_split_long_message(self):
        from interface.message_formatter import split_long_message
        text = "\n".join(["line"] * 300)
        chunks = split_long_message(text, max_len=500)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 500)

    def test_strip_markdown(self):
        from interface.message_formatter import _strip_markdown
        text = "*Bold* and _italic_ and `code`"
        result = _strip_markdown(text)
        self.assertNotIn("*", result)
        self.assertNotIn("`", result)
        self.assertIn("Bold", result)
        self.assertIn("italic", result)

    def test_escalation_message_has_helpline(self):
        from interface.message_formatter import format_escalation_message
        msg = format_escalation_message({"confidence": 0.4, "issue_name": "Unknown"})
        self.assertIn("1800-180-1551", msg)
        self.assertIn("KVK", msg)

    def test_voice_trigger_keywords(self):
        from interface.message_formatter import should_respond_with_voice
        with patch("interface.message_formatter.get_profile") as mock_p:
            mock_p.return_value = {"language": "en"}
            result = should_respond_with_voice(12345, "bolo mujhe jawab do")
            self.assertTrue(result)

    def test_non_english_always_voice(self):
        from interface.message_formatter import should_respond_with_voice
        with patch("interface.message_formatter.get_profile") as mock_p:
            mock_p.return_value = {"language": "hi"}
            result = should_respond_with_voice(12345, "any text")
            self.assertTrue(result)


# ═══════════════════════════════════════════════════════════
#   8. KNOWLEDGE BASE TESTS
# ═══════════════════════════════════════════════════════════

class TestKnowledgeBase(unittest.TestCase):

    def test_seed_knowledge_valid_structure(self):
        from knowledge_base.ingest import SEED_KNOWLEDGE
        self.assertGreater(len(SEED_KNOWLEDGE), 10)
        for item in SEED_KNOWLEDGE:
            self.assertIn("text", item)
            self.assertIn("meta", item)
            self.assertIn("source", item["meta"])
            self.assertIn("category", item["meta"])
            self.assertGreater(len(item["text"]), 20)

    def test_chunk_text(self):
        from knowledge_base.ingest import _chunk_text
        text = "word " * 500
        chunks = _chunk_text(text, chunk_size=200, overlap=20)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertGreater(len(chunk), 100)

    def test_pesticide_json_valid(self):
        import json
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge_base", "pesticide_list.json")
        with open(path) as f:
            data = json.load(f)
        self.assertIn("banned_in_india", data)
        self.assertIn("approved_common", data)
        self.assertGreater(len(data["banned_in_india"]["pesticides"]), 5)
        self.assertIn("Endosulfan", data["banned_in_india"]["pesticides"])


# ═══════════════════════════════════════════════════════════
#   9. INTEGRATION SMOKE TESTS (no API calls)
# ═══════════════════════════════════════════════════════════

class TestIntegrationSmoke(unittest.TestCase):
    """Fast smoke tests that mock all external calls."""

    def test_full_text_route_advisory(self):
        from agents.orchestrator import classify_intent
        result = classify_intent("how do I treat aphids on mustard")
        self.assertIn(result["intent"], ["disease_detection", "advisory_general"])

    def test_full_text_route_market(self):
        from agents.orchestrator import classify_intent
        result = classify_intent("wheat mandi bhav")
        self.assertEqual(result["intent"], "market_price")
        self.assertEqual(result.get("commodity"), "wheat")

    def test_command_help_format(self):
        from agents.orchestrator import _help_message
        msg = _help_message()
        self.assertGreater(len(msg), 100)
        self.assertIn("/start", msg)

    def test_profile_format(self):
        from agents.orchestrator import _format_profile
        with patch("agents.orchestrator.get_profile") as mock_p:
            mock_p.return_value = {
                "name": "Ramesh", "location": {"city": "Varanasi"},
                "land_acres": 3, "soil_type": "loamy",
                "language": "hi", "current_crops": [{"name": "wheat"}],
            }
            msg = _format_profile(12345)
            self.assertIn("Ramesh", msg)
            self.assertIn("Varanasi", msg)
            self.assertIn("wheat", msg)


# ═══════════════════════════════════════════════════════════
#   RUNNER
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════╗")
    print("║     KisanMind — Test Suite               ║")
    print("╚══════════════════════════════════════════╝\n")

    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    test_classes = [
        TestOrchestrator,
        TestWeatherTool,
        TestMandiTool,
        TestVoiceTool,
        TestConversationMemory,
        TestPriceForecaster,
        TestFinanceAgent,
        TestCropPlanAgent,
        TestMessageFormatter,
        TestKnowledgeBase,
        TestIntegrationSmoke,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'='*45}")
    print(f"Tests run:    {result.testsRun}")
    print(f"Failures:     {len(result.failures)}")
    print(f"Errors:       {len(result.errors)}")
    print(f"Status:       {'✅ PASSED' if result.wasSuccessful() else '❌ FAILED'}")
    sys.exit(0 if result.wasSuccessful() else 1)
