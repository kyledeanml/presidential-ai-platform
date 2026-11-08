"""
PII Scrubber for Citizen Data Privacy.
Redacts personal identifying information before saving interactions to telemetry/vector stores.
"""

import re
from typing import Dict, Tuple

class PIIScrubber:
    """Detects and redacts common PII entities using deterministic regex patterns."""

    PATTERNS: Dict[str, re.Pattern] = {
        "EMAIL": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'),
        "PHONE": re.compile(r'(\+?1[-.\s]?)?(\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b'),
        "SSN": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "CREDIT_CARD": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        "STREET_ADDRESS": re.compile(r'\b\d{1,5}\s+[A-Za-z0-9\.\s]+(?:\bStreet|\bSt|\bAvenue|\bAve|\bRoad|\bRd|\bBoulevard|\bBlvd|\bDrive|\bDr|\bLane|\bLn|\bTerrace|\bTer|\bWay|\bCourt|\bCt|\bPlace|\bPl)\b', re.IGNORECASE),
        "ZIP_CODE": re.compile(r'\b\d{5}(?:-\d{4})?\b'),
    }

    @classmethod
    def scrub(cls, text: str) -> Tuple[str, Dict[str, int]]:
        """
        Scrubs PII from input text.
        Returns:
            Tuple[sanitized_text, redacting_counts]
        """
        sanitized = text
        stats: Dict[str, int] = {}

        for pii_type, pattern in cls.PATTERNS.items():
            matches = list(pattern.finditer(sanitized))
            if matches:
                stats[pii_type] = len(matches)
                sanitized = pattern.sub(f"[{pii_type}_REDACTED]", sanitized)

        return sanitized, stats
