"""
Outlier and Emergent Issue Detector.
Identifies novel constituent concerns, unaddressed platform gaps,
and emerging grassroots policy proposals.
"""

import re
from typing import Any, Dict, List
from core.rag_engine import PolicyRAGEngine

class OutlierDetector:
    # Key core platform concept patterns
    PLATFORM_PATTERNS = {
        "ECON-01": [
            r"\bgrocer", r"\binflation\b", r"\btax", r"\bchildcare\b", r"\bhous",
            r"\bmortgage\b", r"\bovertime\b", r"\bwage", r"\bcost of living\b",
            r"\bhome\b", r"\bhomes\b", r"\binsurance\b"
        ],
        "TECH-02": [
            r"\bai\b", r"\bartificial intelligence\b", r"\bautomation\b",
            r"\bsemiconductor\b", r"\bbiometric\b", r"\bdeepfake\b",
            r"\bcopyright", r"\balgorithm"
        ],
        "HEALTH-03": [
            r"\bhealthcare\b", r"\bhealth\b", r"\bmedicare\b", r"\bprescription\b",
            r"\binsulin\b", r"\bhospital\b", r"\bcoverage\b", r"\bmental health\b"
        ],
        "ENERGY-04": [
            r"\bnuclear\b", r"\bsmr\b", r"\breactor", r"\bgrid\b", r"\belectric",
            r"\bpower plant\b", r"\bgas plant\b", r"\bclean energy\b", r"\bsolar\b"
        ],
        "GOV-05": [
            r"\bstock trading\b", r"\bcongressional stock\b", r"\bethic", r"\bsuper pac\b",
            r"\bcitizens united\b", r"\bterm limit", r"\blobby", r"\bcampaign finance\b"
        ],
        "SEC-06": [
            r"\bborder\b", r"\bborder patrol\b", r"\bimmigration\b", r"\basylum\b",
            r"\bfentanyl\b", r"\bsurveillance\b", r"\be-verify\b"
        ]
    }

    # Emergent frontier keywords that are not covered in the standard platform
    EMERGENT_FRONTIER_INDICATORS = [
        r"\bright-to-repair\b", r"\bcombine\b", r"\btractor\b", r"\bjohn deere\b",
        r"\brare disease\b", r"\bpediatric\b", r"\bbatten\b", r"\bcln2\b", r"\borphan drug\b",
        r"\blithium brine\b", r"\bgroundwater basin\b", r"\bclayton valley\b", r"\bhydrology\b",
        r"\borbital debris\b", r"\bspace debris\b", r"\blow earth orbit\b", r"\bkinetic debris\b",
        r"\bmega-constellation\b", r"\bsynthetic biology\b", r"\bdeep-sea mining\b"
    ]

    def __init__(self, rag_engine: PolicyRAGEngine):
        self.rag = rag_engine
        self._compiled_platform = {
            pid: [re.compile(p, re.IGNORECASE) for p in patterns]
            for pid, patterns in self.PLATFORM_PATTERNS.items()
        }
        self._compiled_emergent = [
            re.compile(p, re.IGNORECASE) for p in self.EMERGENT_FRONTIER_INDICATORS
        ]

    def assess_interaction(self, user_message: str) -> Dict[str, Any]:
        """
        Assesses an interaction for platform alignment and outlier status.
        """
        # Step 1: Check for explicit emergent frontier signals
        emergent_matches = [
            p.pattern for p in self._compiled_emergent if p.search(user_message)
        ]
        has_emergent_signal = len(emergent_matches) > 0

        # Step 2: Check matching against platform core patterns
        matched_planks = []
        for pid, patterns in self._compiled_platform.items():
            hits = [p.pattern for p in patterns if p.search(user_message)]
            if hits:
                matched_planks.append((pid, hits))

        # Step 3: BM25 RAG Retrieval
        retrieved_chunks, is_confident = self.rag.retrieve(user_message, top_k=2)
        top_score = retrieved_chunks[0]["score"] if retrieved_chunks else 0.0
        primary_policy = retrieved_chunks[0]["policy_id"] if retrieved_chunks else "NONE"
        category = retrieved_chunks[0]["category"] if retrieved_chunks else "Unclassified / Novel Frontier"

        # Determination: An outlier is an interaction with emergent unaddressed signals
        # or where no core platform plank directly addresses the constituent's concern
        is_outlier = has_emergent_signal or (len(matched_planks) == 0 and top_score < 4.5)

        if is_outlier:
            category = (
                f"Emergent Frontier / Novel ({primary_policy})"
                if primary_policy != "NONE"
                else "Unclassified / Novel Frontier"
            )

        return {
            "is_outlier": is_outlier,
            "has_emergent_signal": has_emergent_signal,
            "emergent_matches": emergent_matches,
            "matched_planks": [p[0] for p in matched_planks],
            "rag_top_score": top_score,
            "primary_matched_policy": primary_policy,
            "matched_category": category,
            "is_confident_rag": is_confident
        }

    def detect_batch_outliers(self, interactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Processes a batch of interactions and separates mainstream consensus from outliers.
        """
        mainstream = []
        outliers = []
        topic_counts: Dict[str, int] = {}

        for item in interactions:
            msg = item.get("user_message", "")
            assessment = self.assess_interaction(msg)
            enriched = {**item, **assessment}

            category = enriched["matched_category"]
            topic_counts[category] = topic_counts.get(category, 0) + 1

            if enriched["is_outlier"]:
                outliers.append(enriched)
            else:
                mainstream.append(enriched)

        return {
            "total_analyzed": len(interactions),
            "mainstream_count": len(mainstream),
            "outlier_count": len(outliers),
            "topic_distribution": topic_counts,
            "mainstream_interactions": mainstream,
            "outlier_interactions": outliers
        }
