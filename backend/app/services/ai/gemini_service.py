"""
gemini_service.py — Google Gemini AI Integration
==================================================
Security rules:
  - API keys are NEVER logged, printed, or included in exception messages.
  - Raw provider error messages (which may reveal key status, quota details,
    or internal model info) are NOT forwarded to the caller.
  - On any Gemini failure the service returns None so the calling code
    falls through to the Free AI Legal Engine fallback.
  - The only user-visible message from this module is the generic fallback
    text produced by the calling service; this module stays silent.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Safe provider error codes that map to specific actions
_QUOTA_CODES    = {429}        # quota / rate-limit — retry later
_AUTH_CODES     = {400, 401, 403}  # bad key / permissions — fall back silently
_SERVER_CODES   = {500, 502, 503}  # provider-side outage — fall back silently


def get_gemini_api_key() -> str:
    """
    Resolve the system Gemini API key.

    Resolution order:
      1. GEMINI_API_KEY environment variable
      2. settings.GEMINI_API_KEY (loaded from .env)
      3. Direct read of backend/.env (dev fallback)

    The key value is NEVER logged.
    """
    # 1. Environment variable
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key:
        return key

    # 2. Settings object
    key = getattr(settings, "GEMINI_API_KEY", "").strip()
    if key:
        return key

    # 3. Direct .env file read (dev convenience)
    env_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
    )
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass  # never log errors that might reveal path details

    return ""


class GeminiService:
    """
    Client for the Google Gemini generative AI API.

    On any failure this class returns None so callers can apply their own
    fallback logic. No raw provider error message is ever surfaced.
    """

    def __init__(
        self,
        api_key:    Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self._custom_key = api_key
        self.model_name  = model_name or getattr(settings, "GEMINI_MODEL_NAME", "gemini-2.0-flash")

    def get_active_key(self) -> str:
        return self._custom_key or get_gemini_api_key()

    def is_configured(self) -> bool:
        return bool(self.get_active_key())

    def generate_response(
        self,
        prompt:             str,
        system_instruction: Optional[str] = None,
        temperature:        float          = 0.2,
    ) -> Optional[str]:
        """
        Generate a text response from the Gemini API.

        Returns the generated text string on success, or None on any failure.
        Failures are logged at WARNING level with NO key value in the message.
        """
        key = self.get_active_key()
        if not key:
            logger.info("Gemini API key not configured — using fallback engine.")
            return None

        candidate_models = list(dict.fromkeys(filter(None, [
            self.model_name,
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ])))

        # ── 1. google-genai official SDK ──────────────────────────────────
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=key)
            config = types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=system_instruction or None,
            )
            for model in candidate_models:
                try:
                    response = client.models.generate_content(
                        model=model, contents=prompt, config=config
                    )
                    if response and response.text:
                        return response.text.strip()
                except Exception:
                    continue  # try next model silently
        except ImportError:
            pass

        # ── 2. google-generativeai SDK ────────────────────────────────────
        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=key)
            for model in candidate_models:
                try:
                    m = genai.GenerativeModel(
                        model_name=model,
                        system_instruction=system_instruction or None,
                    )
                    response = m.generate_content(
                        prompt,
                        generation_config=genai.types.GenerationConfig(temperature=temperature),
                    )
                    if response and response.text:
                        return response.text.strip()
                except Exception:
                    continue
        except ImportError:
            pass

        # ── 3. Direct REST API (urllib — no third-party dependencies) ────
        for model in candidate_models:
            result = self._rest_call(key, model, prompt, system_instruction, temperature)
            if result is not None:
                return result

        logger.warning("Gemini: all models exhausted — using fallback engine.")
        return None

    # ── REST helper ───────────────────────────────────────────────────────────

    def _rest_call(
        self,
        key:                str,
        model:              str,
        prompt:             str,
        system_instruction: Optional[str],
        temperature:        float,
    ) -> Optional[str]:
        """
        Single REST attempt for one model.

        Returns the text on success, None on any error.
        Provider error details are logged at DEBUG (never at INFO/WARNING)
        so they do NOT appear in production logs by default.
        Raw error bodies are NEVER returned to the caller.
        """
        url = (
            f"https://generativelanguage.googleapis.com"
            f"/v1beta/models/{model}:generateContent?key={key}"
        )

        if system_instruction:
            full_prompt = f"System Directive: {system_instruction}\n\nUser Question:\n{prompt}"
        else:
            full_prompt = prompt

        body = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 1024,
            },
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data       = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        text = parts[0].get("text", "").strip()
                        if text:
                            return text

        except urllib.error.HTTPError as exc:
            code = exc.code
            if code in _AUTH_CODES:
                # Key invalid / quota issues — log code only, never the key or body
                logger.warning("Gemini HTTP %d for model %s — falling back.", code, model)
            elif code in _QUOTA_CODES:
                logger.warning("Gemini rate-limited (HTTP %d) for model %s.", code, model)
            else:
                logger.debug("Gemini HTTP %d for model %s.", code, model)

        except Exception as exc:
            # Network error, timeout, JSON parse failure — safe to log type only
            logger.debug("Gemini REST error for model %s: %s", model, type(exc).__name__)

        return None


# Module-level singleton for convenience imports
gemini_service = GeminiService()
