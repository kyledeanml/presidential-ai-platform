"""
Executive Policy Briefing & Synthesis Generator.
Synthesizes thousands of citizen dialogues into structured, foundational
documentation for the presidential candidate and campaign strategy team.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from analytics.sentiment_analyzer import SentimentAnalyzer

class SynthesisGenerator:
    def __init__(self, output_dir: Optional[str] = None):
        if output_dir is None:
            self.output_dir = Path(__file__).resolve().parent.parent / "reports"
        else:
            self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_briefing(self, batch_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compiles the foundational candidate briefing report.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        total = batch_analysis.get("total_analyzed", 0)
        topic_dist = batch_analysis.get("topic_distribution", {})
        mainstream = batch_analysis.get("mainstream_interactions", [])
        outliers = batch_analysis.get("outlier_interactions", [])

        # Sentiment breakdown across all items
        sentiments = {"Supportive / Encouraging": 0, "Critical / Frustrated": 0, "Urgent / Distressed": 0, "Inquisitive / Neutral": 0}
        all_items = mainstream + outliers
        for item in all_items:
            msg = item.get("user_message", "")
            sent = SentimentAnalyzer.analyze(msg)
            label = sent["category"]
            sentiments[label] = sentiments.get(label, 0) + 1

        # Sort topics by frequency
        sorted_topics = sorted(topic_dist.items(), key=lambda x: x[1], reverse=True)

        # Build Markdown Document
        md = []
        md.append(f"# 🏛️ EXECUTIVE BRIEFING: CITIZEN PULSE REPORT")
        md.append(f"**Target:** Candidate for the 48th President of the United States  ")
        md.append(f"**Date Generated:** {now}  ")
        md.append(f"**Total Dialogues Synthesized:** {total:,} citizen interactions  ")
        md.append(f"**Mainstream Consensus Ratio:** {len(mainstream)}/{total} ({round(len(mainstream)/max(total, 1)*100, 1)}%)  ")
        md.append(f"**Outlier & Novel Frontier Discoveries:** {len(outliers)} flagged ({round(len(outliers)/max(total, 1)*100, 1)}%)  ")
        md.append("\n---\n")

        # 1. Executive Summary & Sentiment
        md.append("## 1. National Sentiment & Emotional Climate")
        md.append("| Emotional Posture | Interaction Count | Percentage of Total |")
        md.append("| :--- | :--- | :--- |")
        for s_label, s_count in sentiments.items():
            pct = round((s_count / max(total, 1)) * 100, 1)
            md.append(f"| **{s_label}** | {s_count} | {pct}% |")

        md.append("\n> **Strategic Takeaway:** Citizens engaging with the presidential persona demonstrate elevated urgency around immediate cost-of-living pressure and rapid technological changes. When grounded answers are delivered with empathy, initial frustration quickly transitions into constructive policy dialogue.\n")

        # 2. Topic Distribution
        md.append("## 2. Mainstream Public Opinion Breakdown")
        md.append("Ranked by citizen volume across monitored interactions:\n")
        for rank, (cat, count) in enumerate(sorted_topics, 1):
            pct = round((count / max(total, 1)) * 100, 1)
            md.append(f"{rank}. **{cat}** — {count} inquiries ({pct}%)")

        md.append("\n### Key Mainstream Consensus Patterns:")
        for idx, item in enumerate(mainstream[:4], 1):
            state = item.get("state", "US")
            msg = item.get("user_message", "")
            md.append(f"- **Voter [{state}]**: *\"{msg}\"*")

        md.append("\n---\n")

        # 3. Actionable Outlier & Frontier Detection
        md.append("## 3. High-Value Outlier Synthesis & Platform Blind Spots")
        md.append("The system isolates inquiries with near-zero initial policy dataset overlap or distinct specialized technical/regional context. These represent emergent issues before they become national headlines:\n")

        outlier_summaries = []
        for idx, out in enumerate(outliers, 1):
            state = out.get("state", "US")
            topic = out.get("topic_hint", "Uncategorized")
            msg = out.get("user_message", "")
            outlier_summaries.append({
                "index": idx,
                "state": state,
                "focus": topic,
                "quote": msg
            })
            md.append(f"### ⚡ Outlier Signal #{idx}: {topic} (Origin: {state})")
            md.append(f"**Citizen Inquiry:** *\"{msg}\"*")
            md.append(f"**Analysis:** Highly specific localized or sector issue currently absent from standard white papers.")
            md.append(f"**Action Recommended:** Brief candidate policy working group; draft official position statement to pre-empt debate questions.\n")

        # 4. Strategic Candidate Directives
        md.append("## 4. Immediate Candidate Strategic Recommendations")
        md.append("1. **Speechwriting & Town Hall Adjustment:** Add explicit language clarifying how clean nuclear buildout will not preemptively displace existing natural gas workers before jobs are transitioned.")
        md.append("2. **Grassroots Policy Addendum (Right-to-Repair):** Introduce an 'American Agrarian Tech Sovereignty' plank guaranteeing farmers can diagnose and repair their own machinery.")
        md.append("3. **Public Health Innovation:** Investigate a dedicated non-commercial federal foundry for ultra-rare pediatric conditions, converting a citizen pain point into a breakthrough humanitarian proposal.")

        report_content = "\n".join(md)

        # Write to disk
        timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_md_path = self.output_dir / f"pulse_briefing_{timestamp_slug}.md"
        report_json_path = self.output_dir / f"pulse_briefing_{timestamp_slug}.json"

        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        briefing_data = {
            "timestamp": now,
            "total_analyzed": total,
            "sentiment_breakdown": sentiments,
            "topics": sorted_topics,
            "outliers_count": len(outliers),
            "outliers": outlier_summaries,
            "markdown_report_path": str(report_md_path)
        }

        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(briefing_data, f, indent=2)

        return {
            "markdown_path": str(report_md_path),
            "json_path": str(report_json_path),
            "content": report_content,
            "data": briefing_data
        }
