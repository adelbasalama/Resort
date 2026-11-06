"""Optional Gemini educator adapter for reviewed recycling rules."""
import json
import os
from urllib import error, request

from app.domain.services import CoachProviderError


class GeminiCoach:
    def __init__(
        self,
        api_key,
        model="gemini-2.5-flash-lite",
        endpoint="https://generativelanguage.googleapis.com/v1beta/models",
        timeout=8,
    ):
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout

    def __call__(self, rule):
        body = {
            "systemInstruction": {
                "parts": [{
                    "text": (
                        "Explain the provided reviewed waste-sorting rule in plain "
                        "language. Never change the disposal decision. Use at most "
                        "100 words and return only the explanation."
                    )
                }]
            },
            "contents": [{
                "parts": [{
                    "text": (
                        "Item: %s\nCategory: %s\nBin: %s\nPreparation: %s\n"
                        "Official source: %s"
                        % (
                            rule.item_key,
                            rule.category,
                            rule.bin_label,
                            rule.preparation,
                            rule.source_url,
                        )
                    )
                }]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 140,
            },
        }
        endpoint = "%s/%s:generateContent" % (self.endpoint.rstrip("/"), self.model)
        http_request = request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                payload = json.load(response)
        except (error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise CoachProviderError("Gemini coach request failed") from exc

        try:
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise CoachProviderError("Gemini coach returned an invalid response") from exc
        if not isinstance(text, str) or not text.strip():
            raise CoachProviderError("Gemini coach returned empty text")
        return text.strip()


def configured_coach():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "REPLACE_WITH_GEMINI_API_KEY":
        return None
    return GeminiCoach(
        api_key,
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        timeout=float(os.environ.get("GEMINI_TIMEOUT_SECONDS", "8")),
    )
