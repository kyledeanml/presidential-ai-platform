"""
RAG Knowledge Base & Policy Grounding Engine.
Indexes official platform positions, verifies factual consistency,
and grounds AI responses strictly in verified policy data.
"""

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

class PolicyRAGEngine:
    def __init__(self, policy_dataset_path: Optional[str] = None):
        if policy_dataset_path is None:
            policy_dataset_path = str(Path(__file__).parent.parent / "data" / "policy_dataset.json")
        self.dataset_path = policy_dataset_path
        self.campaign_metadata: Dict[str, Any] = {}
        self.policies: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []
        self.idf: Dict[str, float] = {}
        self._load_and_index()

    def _stem(self, word: str) -> str:
        for suff in ['ing', 'ies', 'es', 'ed', 's', 'ment', 'tion']:
            if word.endswith(suff) and len(word) > len(suff) + 2:
                if suff == 'ies':
                    return word[:-3] + 'y'
                return word[:-len(suff)]
        return word

    def _tokenize(self, text: str) -> List[str]:
        raw_tokens = re.findall(r'\b[a-zA-Z0-9_-]{2,}\b', text.lower())
        stopwords = {
            "the", "and", "to", "of", "in", "for", "with", "is", "that", "on", "as", "by",
            "this", "an", "at", "it", "from", "be", "are", "or", "our", "you", "your", "my",
            "we", "will", "what", "how", "can", "do", "have", "about", "me", "am", "us", "up"
        }
        return [self._stem(t) for t in raw_tokens if t not in stopwords]

    def _load_and_index(self):
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.campaign_metadata = data.get("campaign_metadata", {})
        self.policies = data.get("policies", [])
        self.chunks = []

        # Index policy documents into granular chunks
        for policy in self.policies:
            policy_id = policy.get("id")
            category = policy.get("category")
            title = policy.get("title")
            summary = policy.get("summary")
            pillars = policy.get("key_pillars", [])
            talking_points = policy.get("talking_points", [])
            redlines = policy.get("redlines", [])
            faqs = policy.get("faq", [])

            # Summary Chunk
            full_text = f"{title}. {summary} Pillars: {' '.join(pillars)} Talking points: {' '.join(talking_points)}"
            self.chunks.append({
                "chunk_id": f"{policy_id}-MAIN",
                "policy_id": policy_id,
                "category": category,
                "title": title,
                "text": full_text,
                "pillars": pillars,
                "redlines": redlines,
                "tokens": self._tokenize(full_text)
            })

            # Pillar Chunks for high precision matching
            for i, pillar in enumerate(pillars):
                self.chunks.append({
                    "chunk_id": f"{policy_id}-PILLAR-{i+1}",
                    "policy_id": policy_id,
                    "category": category,
                    "title": f"{title} (Pillar {i+1})",
                    "text": pillar,
                    "pillars": pillars,
                    "redlines": redlines,
                    "tokens": self._tokenize(pillar)
                })

            # FAQ Chunks
            for i, faq in enumerate(faqs):
                faq_text = f"Q: {faq['question']} A: {faq['answer']}"
                self.chunks.append({
                    "chunk_id": f"{policy_id}-FAQ-{i+1}",
                    "policy_id": policy_id,
                    "category": category,
                    "title": f"{title} (FAQ: {faq['question']})",
                    "text": faq_text,
                    "pillars": pillars,
                    "redlines": redlines,
                    "tokens": self._tokenize(faq_text)
                })

        # Calculate BM25 IDF across all chunks
        doc_count = len(self.chunks)
        df = Counter()
        for c in self.chunks:
            for term in set(c["tokens"]):
                df[term] += 1

        self.idf = {
            term: math.log((doc_count - count + 0.5) / (count + 0.5) + 1.0)
            for term, count in df.items()
        }

    def _bm25_score(self, query_tokens: List[str], chunk: Dict[str, Any], avg_dl: float, k1: float = 1.5, b: float = 0.75) -> float:
        chunk_tokens = Counter(chunk["tokens"])
        dl = len(chunk["tokens"])
        score = 0.0

        for term in query_tokens:
            if term in chunk_tokens:
                freq = chunk_tokens[term]
                t_idf = self.idf.get(term, 0.5)
                numerator = freq * (k1 + 1)
                denominator = freq + k1 * (1 - b + b * (dl / max(avg_dl, 1.0)))
                score += t_idf * (numerator / denominator)

        return score

    def retrieve(self, query: str, top_k: int = 2, threshold: float = 1.5) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Retrieves relevant policy context for a query using BM25 ranking.
        Returns:
            Tuple[retrieved_chunks, is_confident]
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return [], False

        avg_dl = sum(len(c["tokens"]) for c in self.chunks) / max(len(self.chunks), 1)

        scored_chunks = []
        for chunk in self.chunks:
            score = self._bm25_score(query_tokens, chunk, avg_dl)
            if score > 0:
                scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        if not scored_chunks:
            return [], False

        best_score = scored_chunks[0][0]
        is_confident = best_score >= threshold

        top_results = []
        for score, chunk in scored_chunks[:top_k]:
            result = dict(chunk)
            result["score"] = round(score, 4)
            top_results.append(result)

        return top_results, is_confident

    def format_context_string(self, chunks: List[Dict[str, Any]]) -> str:
        if not chunks:
            return "No matching official campaign planks found."

        formatted = []
        for c in chunks:
            formatted.append(
                f"POLICY [{c['policy_id']}]: {c['category']} - {c['title']}\n"
                f"DETAILS: {c['text']}\n"
                f"REDLINES: {'; '.join(c.get('redlines', []))}"
            )
        return "\n\n".join(formatted)
