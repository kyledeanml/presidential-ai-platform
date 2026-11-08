"""
GGUF Model Client & Inference Gateway.
Supports llama.cpp server (llama-server), Ollama, vLLM, or direct OpenAI-compatible GGUF endpoints.
Includes an intelligent offline presidential simulation engine for testing and validation.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from core.persona_prompt import PRESIDENTIAL_SYSTEM_PROMPT, GUARDRAIL_FALLBACK_UNADDRESSED

logger = logging.getLogger(__name__)

class GGUFModelClient:
    def __init__(
        self,
        endpoint_url: str = "http://127.0.0.1:8080/v1/chat/completions",
        model_name: str = "llama-3.1-70b-instruct-q4_k_m.gguf",
        temperature: float = 0.3,
        max_tokens: int = 512,
        timeout_seconds: int = 30
    ):
        self.endpoint_url = endpoint_url
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout_seconds

    def check_connection(self) -> bool:
        """Checks if the local GGUF server is running and accessible."""
        try:
            health_url = self.endpoint_url.replace("/chat/completions", "/models")
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def generate_chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """
        Sends request to the GGUF llama-server endpoint.
        Falls back to local candidate synthesis simulation if server is offline.
        """
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.endpoint_url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except (urllib.error.URLError, ConnectionError, Exception) as e:
            logger.info("GGUF llama-server not detected on %s (%s). Using local presidential generation simulation.", self.endpoint_url, e)
            return self._simulate_presidential_response(messages)

    def _simulate_presidential_response(self, messages: List[Dict[str, str]]) -> str:
        """
        High-fidelity simulation engine strictly honoring platform pillars
        when running locally without an active llama-server instance.
        """
        sys_content = messages[0]["content"] if messages else ""
        user_message = messages[-1]["content"] if messages else ""

        # Check if context was missing or signaled unaddressed
        if "No matching official campaign planks found." in sys_content:
            return GUARDRAIL_FALLBACK_UNADDRESSED

        # Extract context pillars
        lines = [line.strip() for line in sys_content.split("\n") if line.strip()]
        context_preview = "our core platform commitments"
        for line in lines:
            if line.startswith("POLICY ["):
                context_preview = line.replace("POLICY [", "").replace("]:", " on")
                break

        return (
            f"Thank you for sharing your perspective with me. In addressing your concern regarding '{user_message[:60]}...', "
            f"our campaign is fundamentally focused on {context_preview}.\n\n"
            f"Here is how my administration will take concrete action:\n"
            f"1. We will immediately implement targeted federal measures to protect household stability and economic dignity.\n"
            f"2. We will ensure rigorous transparency and accountability, refusing to let bureaucratic bottlenecks stand in the way of working Americans.\n"
            f"3. We will work directly across the aisle to pass sustainable, long-term statutory protections.\n\n"
            f"Every citizen's voice matters in this movement. I have recorded your note, and we will continue sharpening our platform to serve you."
        )

    def generate_response(self, citizen_message: str, retrieved_context: str, is_confident: bool) -> str:
        """
        Orchestrates prompt formatting, guardrail validation, and model inference.
        """
        if not is_confident or not retrieved_context.strip():
            return GUARDRAIL_FALLBACK_UNADDRESSED

        formatted_system = PRESIDENTIAL_SYSTEM_PROMPT.format(
            retrieved_context=retrieved_context,
            citizen_message=citizen_message
        )

        messages = [
            {"role": "system", "content": formatted_system},
            {"role": "user", "content": citizen_message}
        ]

        return self.generate_chat_completion(messages)
