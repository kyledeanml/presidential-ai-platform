"""
Constituent Sentiment and Alignment Analyzer.
Evaluates emotional valence, urgency, and stance alignment of citizen inquiries.
"""

from typing import Dict

class SentimentAnalyzer:
    POSITIVE_WORDS = {
        "agree", "support", "best", "great", "love", "promising", "relief", "forward",
        "vision", "strength", "good", "hope", "thank", "pleased", "fantastic", "admire"
    }

    NEGATIVE_WORDS = {
        "fail", "barely", "afford", "crisis", "angry", "broken", "desperate", "worse",
        "expensive", "inflation", "destroy", "bad", "scared", "fear", "unfair", "collapse",
        "stop", "shut", "lost", "struggle", "terrible", "hardship"
    }

    URGENCY_WORDS = {
        "immediately", "urgent", "emergency", "now", "dying", "bankrupt", "eviction",
        "desperate", "before", "critical", "danger", "starving", "doubled", "soaring"
    }

    @classmethod
    def analyze(cls, text: str) -> Dict[str, any]:
        words = set(text.lower().split())
        pos_matches = words & cls.POSITIVE_WORDS
        neg_matches = words & cls.NEGATIVE_WORDS
        urg_matches = words & cls.URGENCY_WORDS

        pos_score = len(pos_matches)
        neg_score = len(neg_matches)
        urg_score = len(urg_matches)

        # Valence calculation (-1.0 to 1.0)
        total = pos_score + neg_score
        if total == 0:
            valence = 0.0
        else:
            valence = round((pos_score - neg_score) / total, 2)

        # Categorize label
        if urg_score > 0 and neg_score > 0:
            category = "Urgent / Distressed"
        elif neg_score > pos_score:
            category = "Critical / Frustrated"
        elif pos_score > neg_score:
            category = "Supportive / Encouraging"
        else:
            category = "Inquisitive / Neutral"

        return {
            "valence": valence,
            "category": category,
            "urgency_score": urg_score,
            "is_high_urgency": urg_score >= 1,
            "positive_keywords": list(pos_matches),
            "negative_keywords": list(neg_matches)
        }
