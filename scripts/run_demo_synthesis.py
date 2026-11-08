#!/usr/bin/env python3
"""
Comprehensive Demonstration & Validation Script.
Executes end-to-end simulation:
1. Multi-Turn Conversational Flow (Greeting -> Policy Inquiry -> Redline Follow-up)
2. PII Scrubbing on raw citizen inputs
3. Outlier and Platform Blind-Spot Detection
4. Executive Pulse Briefing Generation
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.rag_engine import PolicyRAGEngine
from core.llm_client import GGUFModelClient
from core.conversation_engine import ConversationEngine
from analytics.outlier_detector import OutlierDetector
from analytics.synthesis_generator import SynthesisGenerator


def run_demonstration():
    print("=" * 72)
    print("🏛️  48TH PRESIDENTIAL AI PERSONA: CONVERSATION & PULSE SYNTHESIS DEMO")
    print("=" * 72)

    # 1. Initialize Engines
    print("\n[1/4] Initializing Policy RAG, GGUF Client, and Conversation Engine...")
    rag = PolicyRAGEngine()
    llm = GGUFModelClient()
    outlier_detector = OutlierDetector(rag)
    conv = ConversationEngine(rag, llm, outlier_detector)
    synthesis_gen = SynthesisGenerator()
    print(f"  ✓ Loaded {len(rag.policies)} policy planks ({len(rag.chunks)} indexed RAG chunks).")

    # 2. Multi-Turn Stateful Conversation (with PII Scrubbing)
    print("\n[2/4] Simulating Multi-Turn Citizen Town Hall Session (with PII Shield)...")
    session_id = "demo-citizen-oh"

    t1 = conv.process_turn("Hello!", state="OH", session_id=session_id)
    print(f"  Turn 1 [Greeting] -> Intent: {t1['intent']} | Logged to Telemetry: {t1['log_to_telemetry']}")

    raw_msg = (
        "Hi, I live at 742 Evergreen Terrace and my phone is 555-019-2834. "
        "Groceries and childcare costs are crushing our budget. How will your administration help?"
    )
    t2 = conv.process_turn(raw_msg, state="OH", session_id=session_id)
    print(f"  Turn 2 [Policy]   -> Matched: {t2['matched_policy']} | PII Redacted: {t2['pii_redacted']}")
    print(f"  Sanitized Input:  {t2['sanitized_message']}")
    print(f"  Persona Reply:\n    {t2['response'].splitlines()[0]}\n")

    t3 = conv.process_turn("What are your strict redlines on this?", state="OH", session_id=session_id)
    print(f"  Turn 3 [Followup] -> Intent: {t3['intent']} | Stayed on Plank: {t3['matched_policy']}")

    # 3. Outlier Detection on Unaddressed Grassroots Issue
    print("\n[3/4] Testing Outlier & Platform Blind-Spot Detection...")
    t4 = conv.process_turn(
        "John Deere software locks stop me from fixing my own tractor during harvest. We need Right-to-Repair!",
        state="IA",
        session_id="demo-citizen-ia",
    )
    print(f"  Flagged as Outlier: {t4['is_outlier']} | Route: {t4['matched_policy']}")

    # 4. Ingest Sample Interactions & Synthesize Foundational Executive Briefing
    print("\n[4/4] Synthesizing National Citizen Telemetry into Executive Pulse Report...")
    sample_file = PROJECT_ROOT / "data" / "sample_citizen_interactions.json"
    interactions = json.loads(sample_file.read_text(encoding="utf-8"))

    batch_res = outlier_detector.detect_batch_outliers(interactions)
    briefing = synthesis_gen.generate_briefing(batch_res)
    print(f"  ✓ Analyzed {batch_res['total_analyzed']} dialogues "
          f"({batch_res['mainstream_count']} mainstream, {batch_res['outlier_count']} outliers).")
    print(f"  ✓ Markdown Brief: {briefing['markdown_path']}")
    print("=" * 72)


if __name__ == "__main__":
    run_demonstration()
