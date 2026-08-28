from __future__ import annotations

import json
from urllib.parse import urlparse

import requests

from backend.app.core.config import (
    LLM_MAX_OUTPUT_TOKENS,
    LLM_RETRY_COUNT,
    LLM_TIMEOUT_SECONDS,
    LMSTUDIO_BASE_URL,
    LMSTUDIO_MODEL,
)


class LMStudioClient:
    def __init__(self, timeout: int | None = None) -> None:
        raw_base_url = (LMSTUDIO_BASE_URL or "http://127.0.0.1:1234/v1").rstrip("/")
        parsed = urlparse(raw_base_url)
        if parsed.path in {"", "/"}:
            raw_base_url = f"{raw_base_url}/v1"
        self.base_url = raw_base_url
        self.model = LMSTUDIO_MODEL or "google/gemma-4-e2b"
        self.timeout = timeout or LLM_TIMEOUT_SECONDS

    def _extract_content(self, data: dict) -> tuple[str, str, int]:
        choices = data.get("choices", [])
        first = choices[0] if choices else {}
        message = first.get("message", {}) if isinstance(first, dict) else {}
        delta = first.get("delta", {}) if isinstance(first, dict) else {}
        finish_reason = str(first.get("finish_reason", "unknown")) if isinstance(first, dict) else "unknown"
        reasoning_text = None
        if isinstance(message, dict):
            reasoning_text = message.get("reasoning_content") or message.get("reasoning")
        reasoning_len = len(reasoning_text) if isinstance(reasoning_text, str) else 0

        # reasoning_content is intentionally excluded to avoid storing chain-of-thought.
        candidates = [
            message.get("content"),
            delta.get("content"),
            first.get("text") if isinstance(first, dict) else None,
        ]
        for value in candidates:
            if isinstance(value, str) and value.strip():
                return value.strip(), finish_reason, reasoning_len
        return "", finish_reason, reasoning_len

    def generate_text(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        model: str | None = None,
        timeout: int | None = None,
        purpose: str | None = None,
        system_prompt: str | None = None,
        response_format: dict | None = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        resolved_max_tokens = max_tokens if max_tokens is not None else LLM_MAX_OUTPUT_TOKENS
        resolved_timeout = timeout if timeout is not None else self.timeout
        resolved_system_prompt = (
            system_prompt
            if system_prompt is not None
            else "너는 신중한 투자 리서치 보조 AI이다. 내부 추론을 출력하지 말고 최종 답변만 작성한다."
        )
        payload = {
            "model": model or self.model,
            "temperature": temperature,
            "max_tokens": resolved_max_tokens,
            "stream": False,
            "messages": [
                {"role": "system", "content": resolved_system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            retries = max(0, LLM_RETRY_COUNT)
            last_finish_reason = "unknown"
            for attempt in range(retries + 1):
                response = requests.post(url, json=payload, timeout=resolved_timeout)
                if response.status_code == 400:
                    body_text = response.text or ""
                    lowered = body_text.lower()
                    if "response_format" in payload and ("response_format" in lowered or "unsupported" in lowered or "json" in lowered):
                        payload.pop("response_format", None)
                        response = requests.post(url, json=payload, timeout=resolved_timeout)
                        if response.status_code != 400:
                            response.raise_for_status()
                            data = response.json()
                            content, finish_reason, reasoning_len = self._extract_content(data)
                            last_finish_reason = finish_reason
                            if content:
                                return content
                            print(
                                f"[LLM DEBUG] empty content after response_format fallback, "
                                f"purpose={purpose or 'unknown'}, finish_reason={finish_reason}, reasoning_len={reasoning_len}"
                            )
                            if finish_reason.lower() in {"length", "max_tokens"} and attempt < retries:
                                payload["max_tokens"] = self._expanded_max_tokens(payload.get("max_tokens"))
                            continue
                        body_text = response.text or ""
                        lowered = body_text.lower()
                    if "context" in lowered or "tokens" in lowered or "exceeds" in lowered:
                        raise RuntimeError(
                            f"LM Studio context size exceeded during {purpose or 'unknown'}. "
                            "limit을 줄이거나 긴 context 모델을 사용하세요."
                        )
                    raise RuntimeError(f"LM Studio API error during {purpose or 'unknown'}: 400 - {body_text[:300]}")

                response.raise_for_status()
                data = response.json()
                content, finish_reason, reasoning_len = self._extract_content(data)
                last_finish_reason = finish_reason
                if content:
                    return content

                print(
                    f"[LLM DEBUG] empty content attempt={attempt + 1}/{retries + 1}, "
                    f"purpose={purpose or 'unknown'}, finish_reason={finish_reason}, reasoning_len={reasoning_len}"
                )
                if finish_reason.lower() in {"length", "max_tokens"} and attempt < retries:
                    payload["max_tokens"] = self._expanded_max_tokens(payload.get("max_tokens"))

            raise RuntimeError(
                f"LM Studio returned empty content during {purpose or 'unknown'}. finish_reason={last_finish_reason}"
            )
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f"LM Studio server is not reachable during {purpose or 'unknown'}.") from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"LM Studio request timed out during {purpose or 'unknown'}. timeout을 늘리거나 입력량을 줄이세요."
            ) from exc
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(f"LM Studio API HTTP error during {purpose or 'unknown'}: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"LM Studio returned invalid JSON during {purpose or 'unknown'}") from exc

    @staticmethod
    def _expanded_max_tokens(value: object) -> int:
        """Give reasoning models room to emit final content after a length-only response."""
        try:
            current = max(1, int(value))
        except (TypeError, ValueError):
            current = LLM_MAX_OUTPUT_TOKENS
        return min(4096, max(current + 512, current * 2))
