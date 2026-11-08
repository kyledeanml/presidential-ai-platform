#!/usr/bin/env python3
"""
Presidential AI Platform HTTP Server & Mockup Web UI Host.
Zero-dependency multi-threaded server providing:
- Full Interactive Civic Web UI (/, /ui/styles.css, /ui/app.js)
- Stateful Conversational Persona Endpoint (POST /api/chat)
- Session Management (POST /api/session/reset)
- Platform Explorer Data (GET /api/policies, GET /api/status)
- Citizen Pulse & Outlier Synthesis (POST /api/synthesize)
"""

import argparse
import json
import logging
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# Ensure project root is importable regardless of working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.rag_engine import PolicyRAGEngine
from core.llm_client import GGUFModelClient
from core.conversation_engine import ConversationEngine
from analytics.outlier_detector import OutlierDetector
from analytics.synthesis_generator import SynthesisGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Initialize platform singletons
rag_engine = PolicyRAGEngine()
llm_client = GGUFModelClient()
outlier_detector = OutlierDetector(rag_engine)
conversation_engine = ConversationEngine(rag_engine, llm_client, outlier_detector)
synthesis_gen = SynthesisGenerator(str(PROJECT_ROOT / "reports"))

UI_DIR = PROJECT_ROOT / "ui"
SAMPLE_INTERACTIONS_FILE = PROJECT_ROOT / "data" / "sample_citizen_interactions.json"
LIVE_INTERACTIONS_FILE = PROJECT_ROOT / "data" / "live_interactions.json"

INTERACTIONS_LOG = []


def load_combined_interactions():
    interactions = []
    if SAMPLE_INTERACTIONS_FILE.exists():
        with open(SAMPLE_INTERACTIONS_FILE, "r", encoding="utf-8") as f:
            interactions.extend(json.load(f))
    for item in INTERACTIONS_LOG:
        interactions.append({
            "user_message": item["sanitized_message"],
            "state": item["state"],
            "topic_hint": item["category"],
            "is_outlier": item["is_outlier"],
        })
    return interactions


def log_interaction(record: dict):
    INTERACTIONS_LOG.append(record)
    try:
        with open(LIVE_INTERACTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(INTERACTIONS_LOG, f, indent=2)
    except Exception as exc:
        logger.warning("Could not persist live interaction: %s", exc)


class PresidentialRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.info("%s - %s", self.address_string(), fmt % args)

    def _send_bytes(self, content: bytes, status: int = 200, content_type: str = "application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: dict | list, status: int = 200):
        self._send_bytes(json.dumps(payload).encode("utf-8"), status=status)

    def do_OPTIONS(self):
        self._send_bytes(b"", status=200)

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            html_file = UI_DIR / "index.html"
            self._send_bytes(html_file.read_bytes(), content_type="text/html; charset=utf-8")
            return

        if path == "/ui/styles.css":
            css_file = UI_DIR / "styles.css"
            self._send_bytes(css_file.read_bytes(), content_type="text/css; charset=utf-8")
            return

        if path == "/ui/app.js":
            js_file = UI_DIR / "app.js"
            self._send_bytes(js_file.read_bytes(), content_type="application/javascript; charset=utf-8")
            return

        if path == "/api/policies":
            self._send_json(rag_engine.policies)
            return

        if path == "/api/status":
            all_items = load_combined_interactions()
            batch = outlier_detector.detect_batch_outliers(all_items)
            gguf_online = llm_client.check_connection()
            self._send_json({
                "status": "ok",
                "engine_mode": "GGUF Live Server" if gguf_online else "Built-in Persona Engine",
                "gguf_connected": gguf_online,
                "policy_count": len(rag_engine.policies),
                "total_dialogues": batch["total_analyzed"],
                "outlier_count": batch["outlier_count"],
                "live_session_turns": len(INTERACTIONS_LOG),
            })
            return

        self._send_json({"error": "Endpoint not found"}, status=404)

    def do_POST(self):
        path = urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body"}, status=400)
            return

        if path == "/api/chat":
            message = str(body.get("message", "")).strip()
            if not message:
                self._send_json({"error": "Message cannot be empty"}, status=400)
                return

            citizen_state = str(body.get("state", "National"))
            session_id = body.get("session_id")

            turn_result = conversation_engine.process_turn(
                raw_message=message,
                state=citizen_state,
                session_id=session_id,
            )

            if turn_result.get("log_to_telemetry"):
                log_interaction({
                    "sanitized_message": turn_result["sanitized_message"],
                    "state": citizen_state,
                    "is_outlier": turn_result["is_outlier"],
                    "category": turn_result["category"],
                    "sentiment": turn_result["sentiment"],
                    "pii_redacted": turn_result["pii_redacted"],
                })

            self._send_json(turn_result)
            return

        if path == "/api/session/reset":
            session_id = str(body.get("session_id", ""))
            session = conversation_engine.reset_session(session_id)
            self._send_json({"status": "reset", "session_id": session["session_id"]})
            return

        if path == "/api/synthesize":
            interactions = load_combined_interactions()
            batch_res = outlier_detector.detect_batch_outliers(interactions)
            briefing_res = synthesis_gen.generate_briefing(batch_res)
            self._send_json({
                "status": "success",
                "report_preview": briefing_res["content"],
                "markdown_file": briefing_res["markdown_path"],
                "metadata": briefing_res["data"],
            })
            return

        self._send_json({"error": "Endpoint not found"}, status=404)


def run(host: str = "127.0.0.1", port: int = 8000):
    httpd = ThreadingHTTPServer((host, port), PresidentialRequestHandler)
    print("======================================================================")
    print(f" 🏛️  48th Presidential AI Persona & Civic Pulse Server")
    print(f" 🌐 Web Mockup UI: http://{host}:{port}/")
    print(f" 🔌 API Endpoints: GET /api/status | POST /api/chat | POST /api/synthesize")
    print("======================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Presidential AI Platform Web UI & API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port number to listen on")
    args = parser.parse_args()
    run(host=args.host, port=args.port)
