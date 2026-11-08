"""
Stateful Multi-Turn Conversational Engine for the 48th Presidential AI Persona.
Handles conversational intents (greetings, platform overview, follow-up questions,
policy deep-dives, redlines, pushback, and novel grassroots outliers) while
seamlessly bridging to a live GGUF llama-server endpoint when online.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.pii_scrubber import PIIScrubber
from core.rag_engine import PolicyRAGEngine
from core.llm_client import GGUFModelClient
from core.persona_prompt import PRESIDENTIAL_SYSTEM_PROMPT
from analytics.outlier_detector import OutlierDetector
from analytics.sentiment_analyzer import SentimentAnalyzer


STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "Washington, D.C."
}


class ConversationEngine:
    """Manages multi-turn citizen sessions, intent routing, and grounded responses."""

    GREETING_PATTERN = re.compile(
        r"^\s*(hi|hello|hey|howdy|greetings|good\s+(morning|afternoon|evening)|yo|sup)"
        r"(\s+(there|mr\.?\s*president|madam\s*president|candidate|persona|ai))?[!\.\?\s]*$",
        re.IGNORECASE,
    )
    HOW_ARE_YOU_PATTERN = re.compile(
        r"\b(how\s+are\s+you|how\'?s\s+it\s+going|how\s+is\s+the\s+campaign|nice\s+to\s+meet\s+you)\b",
        re.IGNORECASE,
    )
    IDENTITY_PATTERN = re.compile(
        r"\b(who\s+are\s+you|what\s+are\s+you|are\s+you\s+(an?\s+)?ai|are\s+you\s+real|"
        r"what\s+model|gguf|how\s+do\s+you\s+work)\b",
        re.IGNORECASE,
    )
    OVERVIEW_PATTERN = re.compile(
        r"(\b(what\s+(are|is)\s+your\s+(policies|platform|stances|agenda|priorities)|"
        r"what\s+do\s+you\s+(stand\s+for|believe\s+in)|list\s+(your\s+)?policies)\b"
        r"|^\s*(help|topics|menu)[!\.\?\s]*$)",
        re.IGNORECASE,
    )
    FAREWELL_PATTERN = re.compile(
        r"^\s*(thanks?|thank\s+you(\s+so\s+much|\s+very\s+much)?|bye|goodbye|have\s+a\s+good\s+(day|night)|"
        r"appreciate\s+it|got\s+it)[!\.\?\s]*$",
        re.IGNORECASE,
    )
    REDLINE_FOLLOWUP_PATTERN = re.compile(
        r"\b(redline|redlines|compromise|veto|won\'?t\s+you\s+do|non-negotiable|never\s+do)\b",
        re.IGNORECASE,
    )
    FOLLOWUP_PATTERN = re.compile(
        r"^(\s*(tell\s+me\s+more|elaborate|explain(\s+more|\s+that)?|go\s+deeper|more\s+details?|"
        r"what\s+else|why(\s+is\s+that)?|how\s+(will|does|would)\s+(that|this|it|you)\s+work|"
        r"how\s+(do|will)\s+you\s+(pay|fund)\s+(for\s+)?(that|it|this)|"
        r"can\s+congress\s+pass\s+(that|it|this)|what\s+are\s+the\s+(other\s+)?pillars)[!\.\?\s]*.*)$",
        re.IGNORECASE,
    )

    def __init__(
        self,
        rag_engine: PolicyRAGEngine,
        llm_client: GGUFModelClient,
        outlier_detector: OutlierDetector,
    ):
        self.rag = rag_engine
        self.llm = llm_client
        self.outlier_detector = outlier_detector
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.policies_by_id: Dict[str, Dict[str, Any]] = {
            p["id"]: p for p in self.rag.policies
        }

    def get_or_create_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        if not session_id or session_id not in self.sessions:
            new_id = session_id or f"sess-{uuid.uuid4().hex[:10]}"
            self.sessions[new_id] = {
                "session_id": new_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "history": [],
                "active_policy_id": None,
                "turn_count": 0,
            }
            return self.sessions[new_id]
        return self.sessions[session_id]

    def reset_session(self, session_id: str) -> Dict[str, Any]:
        self.sessions.pop(session_id, None)
        return self.get_or_create_session(session_id)

    def process_turn(
        self,
        raw_message: str,
        state: str = "National",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Processes a single conversational turn end-to-end:
        1. Scrubs PII
        2. Detects conversational intent vs. policy inquiry vs. follow-up vs. outlier
        3. Generates grounded response (live GGUF server if online, rich stateful engine otherwise)
        4. Updates session history and returns structured UI metadata
        """
        session = self.get_or_create_session(session_id)
        session["turn_count"] += 1

        sanitized_msg, pii_stats = PIIScrubber.scrub(raw_message.strip())
        sentiment = SentimentAnalyzer.analyze(sanitized_msg)
        gguf_online = self.llm.check_connection()

        # Classify conversational intent
        intent = self._classify_intent(sanitized_msg, session)

        #Conversational meta turns (greetings, thanks, who-are-you, platform overview)
        if intent in ("greeting", "how_are_you", "identity", "overview", "farewell"):
            reply = self._handle_meta_intent(intent, sanitized_msg, state, session, gguf_online)
            self._append_history(session, sanitized_msg, reply)
            return {
                "session_id": session["session_id"],
                "turn_count": session["turn_count"],
                "sanitized_message": sanitized_msg,
                "response": reply,
                "intent": intent,
                "matched_policy": session.get("active_policy_id") or "PLATFORM-OVERVIEW",
                "policy_details": self.policies_by_id.get(session.get("active_policy_id") or ""),
                "category": "Civic Dialogue",
                "rag_score": 0.0,
                "is_outlier": False,
                "log_to_telemetry": False,
                "sentiment": sentiment["category"],
                "valence": sentiment["valence"],
                "pii_redacted": pii_stats,
                "engine_mode": "GGUF Live Server" if gguf_online else "Built-in Persona Engine",
            }

        # Follow-up on the active policy in session
        if intent in ("followup_redlines", "followup_details") and session.get("active_policy_id"):
            active_pid = session["active_policy_id"]
            policy = self.policies_by_id[active_pid]
            reply = self._generate_policy_followup(
                intent, sanitized_msg, policy, state, session, gguf_online
            )
            self._append_history(session, sanitized_msg, reply)
            return {
                "session_id": session["session_id"],
                "turn_count": session["turn_count"],
                "sanitized_message": sanitized_msg,
                "response": reply,
                "intent": intent,
                "matched_policy": active_pid,
                "policy_details": self._summarize_policy(policy),
                "category": policy["category"],
                "rag_score": 8.5,
                "is_outlier": False,
                "log_to_telemetry": True,
                "sentiment": sentiment["category"],
                "valence": sentiment["valence"],
                "pii_redacted": pii_stats,
                "engine_mode": "GGUF Live Server" if gguf_online else "Built-in Persona Engine",
            }

        # Standard Policy RAG + Outlier Assessment
        retrieved_chunks, is_confident = self.rag.retrieve(sanitized_msg, top_k=2)
        outlier_info = self.outlier_detector.assess_interaction(sanitized_msg)
        is_outlier = outlier_info["is_outlier"]
        matched_pid = outlier_info["primary_matched_policy"]

        if not is_outlier and matched_pid in self.policies_by_id:
            session["active_policy_id"] = matched_pid
            policy = self.policies_by_id[matched_pid]
            reply = self._generate_grounded_policy_reply(
                sanitized_msg, policy, retrieved_chunks, sentiment, state, session, gguf_online
            )
            policy_summary = self._summarize_policy(policy)
        else:
            reply = self._generate_outlier_reply(
                sanitized_msg, outlier_info, sentiment, state, session, gguf_online
            )
            policy_summary = None

        self._append_history(session, sanitized_msg, reply)

        return {
            "session_id": session["session_id"],
            "turn_count": session["turn_count"],
            "sanitized_message": sanitized_msg,
            "response": reply,
            "intent": "outlier_inquiry" if is_outlier else "policy_inquiry",
            "matched_policy": "OUTLIER-QUEUE" if is_outlier else matched_pid,
            "policy_details": policy_summary,
            "category": outlier_info["matched_category"],
            "rag_score": outlier_info["rag_top_score"],
            "is_outlier": is_outlier,
            "log_to_telemetry": True,
            "sentiment": sentiment["category"],
            "valence": sentiment["valence"],
            "pii_redacted": pii_stats,
            "engine_mode": "GGUF Live Server" if gguf_online else "Built-in Persona Engine",
        }

    def _classify_intent(self, msg: str, session: Dict[str, Any]) -> str:
        word_count = len(msg.split())
        if self.GREETING_PATTERN.match(msg):
            return "greeting"
        if word_count <= 10 and self.FAREWELL_PATTERN.match(msg):
            return "farewell"
        if word_count <= 12 and self.HOW_ARE_YOU_PATTERN.search(msg):
            return "how_are_you"

        assessment = self.outlier_detector.assess_interaction(msg)
        has_specific_topic = bool(assessment["matched_planks"]) or assessment["has_emergent_signal"]

        if self.OVERVIEW_PATTERN.search(msg) and not has_specific_topic:
            return "overview"
        if word_count <= 14 and self.IDENTITY_PATTERN.search(msg) and not assessment["has_emergent_signal"]:
            # Avoid matching 'ai' in policy questions unless asking about persona identity
            if not assessment["matched_planks"] or re.search(r"\b(who\s+are\s+you|are\s+you\s+(an?\s+)?ai|what\s+model)\b", msg, re.I):
                return "identity"

        # Check if user is asking a short contextual follow-up without switching policy topics
        if session.get("active_policy_id") and not has_specific_topic:
            if self.REDLINE_FOLLOWUP_PATTERN.search(msg):
                return "followup_redlines"
            if self.FOLLOWUP_PATTERN.match(msg):
                return "followup_details"

        return "policy_or_outlier"

    def _append_history(self, session: Dict[str, Any], user_msg: str, assistant_msg: str):
        session["history"].append({"role": "user", "content": user_msg})
        session["history"].append({"role": "assistant", "content": assistant_msg})
        # Keep rolling window of last 12 messages
        if len(session["history"]) > 12:
            session["history"] = session["history"][-12:]

    def _summarize_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": policy["id"],
            "category": policy["category"],
            "title": policy["title"],
            "summary": policy["summary"],
            "key_pillars": policy.get("key_pillars", []),
            "redlines": policy.get("redlines", []),
        }

    def _state_phrase(self, state: str) -> str:
        if not state or state == "National" or state == "US":
            return "across the country"
        full_name = STATE_NAMES.get(state.upper(), state)
        return f"in {full_name}"

    def _handle_meta_intent(
        self,
        intent: str,
        msg: str,
        state: str,
        session: Dict[str, Any],
        gguf_online: bool,
    ) -> str:
        loc = self._state_phrase(state)

        if gguf_online:
            overview_ctx = "\n".join(
                f"- [{p['id']}] {p['category']}: {p['title']} — {p['summary']}"
                for p in self.rag.policies
            )
            messages = [
                {
                    "role": "system",
                    "content": PRESIDENTIAL_SYSTEM_PROMPT.format(
                        retrieved_context=overview_ctx, citizen_message=msg
                    ),
                },
                *session["history"][-6:],
                {"role": "user", "content": msg},
            ]
            return self.llm.generate_chat_completion(messages)

        if intent == "greeting":
            return (
                f"Hello, and welcome! It is an honor to speak with you. Whether you are raising a family, "
                f"running a small business, or studying {loc}, this Town Hall is built so every citizen "
                f"has a direct line to our campaign for the 48th Presidency.\n\n"
                f"You can ask me about our stances on **grocery & housing costs**, **healthcare & insulin**, "
                f"**AI & jobs**, **clean nuclear energy**, **banning congressional stock trading**, or **border security**—"
                f"or share a local issue your community is facing right now. What is top of mind for you today?"
            )

        if intent == "how_are_you":
            return (
                f"I am energized and grateful to be listening directly to citizens {loc}. "
                f"A presidential campaign shouldn't just be speeches from a podium—it should be a two-way "
                f"conversation where everyday concerns shape national priorities.\n\n"
                f"What issue affecting your household or community would you like to discuss?"
            )

        if intent == "identity":
            return (
                "I am the **Official AI Persona for the 48th Presidential Campaign**, designed to run on "
                "open-weights quantized **GGUF models** strictly grounded in our published policy dataset.\n\n"
                "**How this protects integrity and your privacy:**\n"
                "- **Zero Fabrication:** I only cite verified planks from our official platform and never invent off-the-cuff promises.\n"
                "- **Automatic PII Redaction:** Phone numbers, street addresses, emails, and SSNs are scrubbed before any feedback is analyzed.\n"
                "- **Citizen Pulse Synthesis:** Unaddressed local issues are flagged as outliers so our Policy Advisory Council can study them directly.\n\n"
                "Ask me about any policy area, or test me with a specific local concern!"
            )

        if intent == "overview":
            planks = "\n".join(
                f"- **{p['category']} (`{p['id']}`)**: {p['title']}"
                for p in self.rag.policies
            )
            return (
                "Our campaign platform—*Restoring the American Promise*—is built around six foundational pillars:\n\n"
                f"{planks}\n\n"
                "Which of these areas matters most to you right now, or is there an issue outside this list "
                "that you think Washington is overlooking?"
            )

        # farewell / gratitude
        return (
            f"Thank you for taking the time to engage in our democracy. Conversations with citizens {loc} "
            f"are what keep this campaign grounded in real life. Whenever another question or community concern comes up, "
            f"my door is always open!"
        )

    def _generate_policy_followup(
        self,
        intent: str,
        msg: str,
        policy: Dict[str, Any],
        state: str,
        session: Dict[str, Any],
        gguf_online: bool,
    ) -> str:
        context_str = (
            f"POLICY [{policy['id']}]: {policy['category']} - {policy['title']}\n"
            f"SUMMARY: {policy['summary']}\n"
            f"PILLARS: {'; '.join(policy.get('key_pillars', []))}\n"
            f"REDLINES: {'; '.join(policy.get('redlines', []))}"
        )
        if gguf_online:
            messages = [
                {
                    "role": "system",
                    "content": PRESIDENTIAL_SYSTEM_PROMPT.format(
                        retrieved_context=context_str, citizen_message=msg
                    ),
                },
                *session["history"][-6:],
                {"role": "user", "content": msg},
            ]
            return self.llm.generate_chat_completion(messages)

        if intent == "followup_redlines":
            redlines_bullets = "\n".join(f"- **{r}**" for r in policy.get("redlines", []))
            return (
                f"On **{policy['title']}** (`{policy['id']}`), leadership means drawing clear lines you refuse to cross. "
                f"Here are my non-negotiable redlines:\n\n"
                f"{redlines_bullets}\n\n"
                f"Every legislative package that reaches my desk in this area will be measured against those commitments. "
                f"Does that address your concern, or would you like to look at another plank?"
            )

        # Detailed follow-up on implementation / pillars / talking points
        pillars_bullets = "\n".join(f"{i}. {p}" for i, p in enumerate(policy.get("key_pillars", []), 1))
        quote = policy.get("talking_points", [""])[0]
        return (
            f"Digging deeper into **{policy['title']}** (`{policy['id']}`): {quote}\n\n"
            f"Specifically, our implementation roadmap rests on all four operational pillars:\n"
            f"{pillars_bullets}\n\n"
            f"We pair executive authority on day one with bipartisan congressional coalitions—focusing on measurable outcomes "
            f"for households {self._state_phrase(state)}. What part of this plan would have the biggest impact where you live?"
        )

    def _generate_grounded_policy_reply(
        self,
        msg: str,
        policy: Dict[str, Any],
        retrieved_chunks: List[Dict[str, Any]],
        sentiment: Dict[str, Any],
        state: str,
        session: Dict[str, Any],
        gguf_online: bool,
    ) -> str:
        context_str = self.rag.format_context_string(retrieved_chunks)
        if gguf_online:
            messages = [
                {
                    "role": "system",
                    "content": PRESIDENTIAL_SYSTEM_PROMPT.format(
                        retrieved_context=context_str, citizen_message=msg
                    ),
                },
                *session["history"][-6:],
                {"role": "user", "content": msg},
            ]
            return self.llm.generate_chat_completion(messages)

        loc = self._state_phrase(state)
        sent_cat = sentiment["category"]

        # 1. Sentiment-aware opening
        if sent_cat == "Urgent / Distressed":
            opener = (
                f"I hear the urgency in what you're sharing, and families {loc} shouldn't have to wait "
                f"for Washington to take this seriously."
            )
        elif sent_cat == "Critical / Frustrated":
            opener = (
                f"You raise a fair, tough point—and frankly, people {loc} have every right to be frustrated "
                f"with how this has been handled."
            )
        elif sent_cat == "Supportive / Encouraging":
            opener = (
                f"Thank you for that encouragement—it means a great deal to hear that this resonates {loc}, "
                f"and you're asking the exact right question on execution."
            )
        else:
            opener = f"That goes right to the heart of our **{policy['category']}** platform (`{policy['id']}`)."

        # 2. Check if an FAQ directly answers the question
        msg_lower = msg.lower()
        matched_faq_answer = None
        for faq in policy.get("faq", []):
            q_words = [
                w for w in re.findall(r"\b[a-z]{4,}\b", faq["question"].lower())
                if w not in {"will", "what", "your", "plan", "support", "actually"}
            ]
            if any(w in msg_lower for w in q_words):
                matched_faq_answer = faq["answer"]
                break

        core_body = matched_faq_answer if matched_faq_answer else policy["summary"]

        # 3. Select the most relevant pillars (up to 3)
        pillars = policy.get("key_pillars", [])
        scored_pillars = []
        for idx, p_text in enumerate(pillars):
            overlap = sum(1 for w in re.findall(r"\b[a-z]{4,}\b", p_text.lower()) if w in msg_lower)
            scored_pillars.append((overlap, -idx, p_text))
        scored_pillars.sort(reverse=True)
        selected_pillars = [item[2] for item in scored_pillars[:3]]
        pillar_block = "\n".join(f"- {p}" for p in selected_pillars)

        # 4. Include redline if user asks about shutting down / abolishing / raising age / redlines
        redline_note = ""
        redlines = policy.get("redlines", [])
        if redlines and any(
            kw in msg_lower
            for kw in ("shut down", "abolish", "retire", "bailout", "veto", "compromise", "force", "out of work")
        ):
            redline_note = f"\n\n**Firm Commitment:** {redlines[0]}"

        return (
            f"{opener}\n\n"
            f"Under **{policy['title']}**, here is where I stand: {core_body}\n\n"
            f"**Concrete Actions in Our Platform:**\n"
            f"{pillar_block}"
            f"{redline_note}\n\n"
            f"Would you like to dive deeper into how we implement this, or hear the strict redlines I've set on {policy['category'].lower()}?"
        )

    def _generate_outlier_reply(
        self,
        msg: str,
        outlier_info: Dict[str, Any],
        sentiment: Dict[str, Any],
        state: str,
        session: Dict[str, Any],
        gguf_online: bool,
    ) -> str:
        loc = self._state_phrase(state)
        if gguf_online:
            unaddressed_ctx = (
                "UNADDRESSED / EMERGENT CITIZEN CONCERN: No formalized legislative plank exists yet in the "
                "published dataset for this specific topic. Acknowledge honestly, state core governing values "
                "(worker dignity, constitutional integrity, long-term national resilience), and confirm it is "
                "logged for the National Policy Advisory Council."
            )
            messages = [
                {
                    "role": "system",
                    "content": PRESIDENTIAL_SYSTEM_PROMPT.format(
                        retrieved_context=unaddressed_ctx, citizen_message=msg
                    ),
                },
                *session["history"][-6:],
                {"role": "user", "content": msg},
            ]
            return self.llm.generate_chat_completion(messages)

        snippet = msg if len(msg) <= 95 else msg[:92].rsplit(" ", 1)[0] + "..."
        return (
            f"Thank you for bringing this forward—especially from your vantage point {loc}.\n\n"
            f"I want to be completely candid with you: **our published campaign platform does not yet have a "
            f"formalized legislative plank addressing this specific issue** (*\"{snippet}\"*), and as someone "
            f"running to be your 48th President, I refuse to invent off-the-cuff promises just to tell voters what they want to hear.\n\n"
            f"**Here is what happens next:**\n"
            f"1. **Flagged as an Emergent Priority:** I have tagged your message for our **National Policy Advisory Council** synthesis report so it is evaluated alongside emerging grassroots concerns.\n"
            f"2. **Our Guiding Yardstick:** When our policy working group assesses this, we apply three tests—protecting everyday working Americans over entrenched monopolies, safeguarding constitutional & community rights, and ensuring long-term national resilience.\n\n"
            f"If you'd like to share how this is affecting people on the ground {loc}, please tell me more—your testimony goes directly into our foundational assessment."
        )
