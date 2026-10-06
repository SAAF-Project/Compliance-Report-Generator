"""
Model-agnostic LLM client layer.

The agent depends only on ``LLMClient.complete()``. Two providers are built in:

  anthropic  Native Anthropic Messages API (streaming, adaptive thinking).
  openai     Any OpenAI-compatible ``/chat/completions`` endpoint: OpenAI itself,
             Azure-style gateways, vLLM, Ollama, LiteLLM, LM Studio, and so on.

Both accept a custom ``base_url``. The openai provider uses only the standard
library, so no extra dependency is needed; the Anthropic SDK is imported lazily
and is only required when the anthropic provider is used.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional, Union
from urllib.parse import urlsplit

log = logging.getLogger("saaf.llm")

PROVIDERS = ("anthropic", "openai")
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass
class LLMResponse:
    """Provider-neutral result of one completion."""

    text: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    stop_reason: Optional[str] = None


class LLMError(Exception):
    """A provider call failed. ``retryable`` is True for 5xx and connection errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def validate_base_url(base_url: str) -> str:
    """Return base_url stripped of trailing slashes; raise ValueError if unusable."""
    parts = urlsplit(base_url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(
            f"Invalid base URL {base_url!r}: it must start with http:// or https:// "
            "and include a host."
        )
    if parts.username or parts.password:
        raise ValueError("Base URL must not embed credentials; use SAAF_API_KEY instead.")
    if parts.scheme == "http" and parts.hostname not in _LOOPBACK_HOSTS:
        log.warning(
            "Base URL %s is plain http on a non-local host: the API key and "
            "engagement data are sent unencrypted.", parts.hostname,
        )
    return base_url.strip().rstrip("/")


class AnthropicClient:
    """Native Anthropic Messages API, streamed, with adaptive thinking."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        base_url: str = "",
    ) -> None:
        import anthropic  # lazy: only needed for this provider

        self._anthropic = anthropic
        self.model = model
        kwargs = {"api_key": api_key, "timeout": timeout}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = anthropic.Anthropic(**kwargs)

    def complete(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        anthropic = self._anthropic
        try:
            full_text = ""
            thinking_chars = 0
            with self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                system=system,
                messages=[{"role": "user", "content": user}],
            ) as stream:
                for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and hasattr(event.delta, "type")
                    ):
                        if event.delta.type == "text_delta":
                            full_text += event.delta.text
                        elif event.delta.type == "thinking_delta":
                            thinking_chars += len(event.delta.thinking)
                final = stream.get_final_message()
        except anthropic.APIStatusError as e:
            raise LLMError(
                f"{e.message}", status_code=e.status_code, retryable=e.status_code >= 500
            ) from e
        except anthropic.APIConnectionError as e:
            raise LLMError(f"Connection error: {e}", retryable=True) from e

        if thinking_chars:
            log.debug("Thinking block: ~%d chars", thinking_chars)
        text_blocks = [b.text for b in final.content if b.type == "text"]
        return LLMResponse(
            text=text_blocks[-1] if text_blocks else full_text,
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
            stop_reason=final.stop_reason,
        )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow redirects: urllib would forward the Authorization header."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


class OpenAICompatibleClient:
    """OpenAI-style ``POST {base_url}/chat/completions`` over the standard library."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        base_url: str = "",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        base = validate_base_url(base_url or DEFAULT_OPENAI_BASE_URL)
        # Accept either a base URL (…/v1) or the full endpoint URL
        self.url = base if base.endswith("/chat/completions") else base + "/chat/completions"
        self._opener = urllib.request.build_opener(_NoRedirect)

    def complete(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self.url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
        )

        try:
            with self._opener.open(request, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", errors="replace").strip()
            raise LLMError(
                f"HTTP {e.code} from {self.url}: {detail or e.reason}",
                status_code=e.code,
                retryable=e.code >= 500,
            ) from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise LLMError(f"Connection error to {self.url}: {e}", retryable=True) from e
        except (ValueError, UnicodeDecodeError) as e:
            raise LLMError(f"Endpoint returned a non-JSON response: {e}") from e

        try:
            choice = payload["choices"][0]
            content = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            raise LLMError(
                "Endpoint response is not OpenAI chat-completions shaped "
                "(expected choices[0].message.content)."
            ) from e

        usage = payload.get("usage") or {}
        return LLMResponse(
            # Reasoning models may emit <think>…</think>; its braces would confuse JSON extraction
            text=_THINK_BLOCK.sub("", content).strip(),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            stop_reason=choice.get("finish_reason"),
        )


def create_client(config) -> Union[AnthropicClient, OpenAICompatibleClient]:
    """Build the client for config.provider (see config.Config)."""
    if config.provider == "anthropic":
        return AnthropicClient(
            api_key=config.api_key,
            model=config.model,
            timeout=config.timeout_seconds,
            base_url=config.base_url,
        )
    if config.provider == "openai":
        return OpenAICompatibleClient(
            api_key=config.api_key,
            model=config.model,
            timeout=config.timeout_seconds,
            base_url=config.base_url,
        )
    raise ValueError(f"Unknown provider {config.provider!r}; choose from {PROVIDERS}")
