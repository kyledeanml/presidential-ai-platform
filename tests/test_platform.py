"""
End-to-End Unit Tests for the 48th Presidential AI Persona & Civic Pulse Platform.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.pii_scrubber import PIIScrubber
from core.rag_engine import PolicyRAGEngine
from core.llm_client import GGUFModelClient
from core.conversation_engine import ConversationEngine
from analytics.outlier_detector import OutlierDetector
from analytics.synthesis_generator import SynthesisGenerator


class TestPresidentialPlatform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag = PolicyRAGEngine()
        cls.llm = GGUFModelClient(endpoint_url="http://127.0.0.1:59999/v1/chat/completions")
        cls.detector = OutlierDetector(cls.rag)
        cls.engine = ConversationEngine(cls.rag, cls.llm, cls.detector)

    def test_greeting_and_overview_intents(self):
        res_hi = self.engine.process_turn("Hello!", state="OH", session_id="test-meta")
        self.assertEqual(res_hi["intent"], "greeting")
        self.assertFalse(res_hi["is_outlier"])
        self.assertFalse(res_hi["log_to_telemetry"])
        self.assertIn("Ohio", res_hi["response"])

        res_overview = self.engine.process_turn("What are your policies?", state="OH", session_id="test-meta")
        self.assertEqual(res_overview["intent"], "overview")
        self.assertIn("ECON-01", res_overview["response"])
        self.assertIn("TECH-02", res_overview["response"])

    def test_multi_turn_policy_and_followups(self):
        sid = "test-multiturn"
        turn1 = self.engine.process_turn(
            "Groceries and childcare costs are hurting our family budget. What is your plan?",
            state="MI",
            session_id=sid,
        )
        self.assertEqual(turn1["matched_policy"], "ECON-01")
        self.assertFalse(turn1["is_outlier"])
        self.assertTrue(turn1["log_to_telemetry"])
        self.assertIn("Middle-Class Re-Industrialization", turn1["response"])

        # Stateful follow-up on redlines without repeating the topic name
        turn2 = self.engine.process_turn("What are your redlines on this?", state="MI", session_id=sid)
        self.assertEqual(turn2["intent"], "followup_redlines")
        self.assertEqual(turn2["matched_policy"], "ECON-01")
        self.assertIn("Social Security", turn2["response"])

        # Stateful follow-up asking to elaborate
        turn3 = self.engine.process_turn("Tell me more about how that works", state="MI", session_id=sid)
        self.assertEqual(turn3["intent"], "followup_details")
        self.assertEqual(turn3["matched_policy"], "ECON-01")
        self.assertEqual(turn3["turn_count"], 3)

    def test_outlier_detection_and_zero_fabrication(self):
        turn = self.engine.process_turn(
            "John Deere software locks stop me from fixing my own tractor during harvest. Pass Right-to-Repair!",
            state="IA",
            session_id="test-outlier",
        )
        self.assertTrue(turn["is_outlier"])
        self.assertEqual(turn["matched_policy"], "OUTLIER-QUEUE")
        self.assertIn("National Policy Advisory Council", turn["response"])

        # Arbitrary novel topic not listed in emergent keywords
        turn_dst = self.engine.process_turn(
            "Should Congress abolish daylight saving time permanently?",
            state="AZ",
            session_id="test-outlier-dst",
        )
        self.assertTrue(turn_dst["is_outlier"])
        self.assertEqual(turn_dst["matched_policy"], "OUTLIER-QUEUE")

    def test_pii_scrubber(self):
        raw = "Contact me at jane.doe@example.com or 555-867-5309 at 124 Oak Avenue, SSN 123-45-6789."
        scrubbed, stats = PIIScrubber.scrub(raw)
        self.assertIn("[EMAIL_REDACTED]", scrubbed)
        self.assertIn("[PHONE_REDACTED]", scrubbed)
        self.assertIn("[STREET_ADDRESS_REDACTED]", scrubbed)
        self.assertIn("[SSN_REDACTED]", scrubbed)
        self.assertEqual(stats["EMAIL"], 1)
        self.assertEqual(stats["SSN"], 1)

    def test_batch_synthesis_report(self):
        sample_path = PROJECT_ROOT / "data" / "sample_citizen_interactions.json"
        interactions = json.loads(sample_path.read_text(encoding="utf-8"))
        batch = self.detector.detect_batch_outliers(interactions)
        self.assertEqual(batch["total_analyzed"], 12)
        self.assertEqual(batch["mainstream_count"], 8)
        self.assertEqual(batch["outlier_count"], 4)

        with tempfile.TemporaryDirectory() as tmpdir:
            synth = SynthesisGenerator(output_dir=tmpdir)
            report = synth.generate_briefing(batch)
            self.assertIn("CITIZEN PULSE REPORT", report["content"])
            self.assertTrue(Path(report["markdown_path"]).exists())

    def test_ui_assets_present(self):
        self.assertTrue((PROJECT_ROOT / "ui" / "index.html").exists())
        self.assertTrue((PROJECT_ROOT / "ui" / "styles.css").exists())
        self.assertTrue((PROJECT_ROOT / "ui" / "app.js").exists())


if __name__ == "__main__":
    unittest.main()
