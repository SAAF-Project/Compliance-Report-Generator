from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

from saaf.core.llm import PROVIDERS, validate_base_url

DEFAULT_PROVIDER = "anthropic"
_DEFAULT_MODELS = {"anthropic": "claude-opus-4-6"}
_PROVIDER_KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

_ALLOW_NO_API_KEY_ENV = "SAAF_ALLOW_NO_API_KEY"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"", "0", "false", "no", "off"}


def _first_nonblank(*values: str | None) -> str:
    """Return the first candidate that is not None or blank, stripped ("" if none)."""
    for value in values:
        if value is None:
            continue
        if not isinstance(value, str):
            raise EnvironmentError(
                f"Configuration values must be strings, got {type(value).__name__}."
            )
        value = value.strip()
        if value:
            return value
    return ""


def _env_flag(name: str) -> bool:
    """Parse a boolean environment variable; an unrecognised value is an error."""
    value = os.environ.get(name, "").strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise EnvironmentError(f"{name} must be one of 1/true/yes/on or 0/false/no/off.")


def _is_number(value: object, types: type | tuple[type, ...]) -> bool:
    # bool is a subclass of int, so it has to be rejected explicitly
    return isinstance(value, types) and not isinstance(value, bool)


def _is_finite(value: float) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:  # an int too large to convert to float
        return False


@dataclass
class Config:
    """
    LLM settings. Each of provider / model / base_url / api_key resolves in order:
    explicit argument, then environment variable, then default.

      provider  SAAF_PROVIDER   "anthropic" (default) or "openai" (any OpenAI-compatible API)
      model     SAAF_MODEL      default claude-opus-4-6 for anthropic; required for openai
      base_url  SAAF_BASE_URL   custom API endpoint
      api_key   SAAF_API_KEY, else ANTHROPIC_API_KEY / OPENAI_API_KEY for the provider

    Blank values: for provider, model and api_key, an empty or whitespace-only value counts
    as missing at each level, so a blank SAAF_API_KEY does not hide a valid provider key.

    base_url is different: None inherits SAAF_BASE_URL, while "" (or whitespace) explicitly
    selects the provider's own endpoint and ignores SAAF_BASE_URL.

    Keyless operation: a key is required unless allow_no_api_key is on, the provider is
    "openai" and base_url is non-empty. Turn it on with allow_no_api_key=True or
    SAAF_ALLOW_NO_API_KEY=1. The environment variable can only enable it, so
    allow_no_api_key=False does not override it. For any other provider or endpoint the
    setting has no effect and the key is still required.

    Credential routing (a deliberate policy): a custom base_url inherits the key like any
    other endpoint, so SAAF_API_KEY or the provider's key variable is sent to that endpoint
    if set, including when allow_no_api_key is on. allow_no_api_key permits a missing key;
    it does not suppress one. To keep a key away from a custom endpoint, unset those
    variables for that run.

    api_key is excluded from repr(). That does not cover direct access to config.api_key
    or dataclasses.asdict().

    Every invalid setting raises EnvironmentError, which the CLI reports as a
    configuration error.
    """

    api_key: str | None = field(default=None, repr=False)
    model: str | None = None
    provider: str | None = None
    base_url: str | None = None
    max_tokens: int = 32000
    max_retries: int = 2
    timeout_seconds: float = 180
    allow_no_api_key: bool = False

    def __post_init__(self):
        self._validate_numeric_settings()

        self.provider = _first_nonblank(
            self.provider, os.environ.get("SAAF_PROVIDER"), DEFAULT_PROVIDER
        ).lower()
        if self.provider not in PROVIDERS:
            raise EnvironmentError(
                f"Unknown provider {self.provider!r}. Choose from: {', '.join(PROVIDERS)}."
            )
        key_env = _PROVIDER_KEY_ENV.get(self.provider)
        if key_env is None:
            raise EnvironmentError(
                f"Provider {self.provider!r} has no API-key variable defined in config.py."
            )

        self.model = _first_nonblank(
            self.model, os.environ.get("SAAF_MODEL"), _DEFAULT_MODELS.get(self.provider)
        )
        if not self.model:
            raise EnvironmentError(
                f"No model set for provider {self.provider!r}. "
                "Pass --model or set SAAF_MODEL."
            )

        # Not _first_nonblank: an explicit "" must win over SAAF_BASE_URL
        base_url = (
            self.base_url if self.base_url is not None else os.environ.get("SAAF_BASE_URL", "")
        )
        if not isinstance(base_url, str):
            raise EnvironmentError(f"base_url must be a string, got {type(base_url).__name__}.")
        self.base_url = base_url.strip()
        if self.base_url:
            try:
                self.base_url = validate_base_url(self.base_url)
            except ValueError as e:
                raise EnvironmentError(str(e)) from e

        if not isinstance(self.allow_no_api_key, bool):
            raise EnvironmentError("allow_no_api_key must be True or False.")
        self.allow_no_api_key = self.allow_no_api_key or _env_flag(_ALLOW_NO_API_KEY_ENV)

        self.api_key = _first_nonblank(
            self.api_key, os.environ.get("SAAF_API_KEY"), os.environ.get(key_env)
        )
        keyless_possible = self.provider == "openai" and bool(self.base_url)
        if not self.api_key and not (keyless_possible and self.allow_no_api_key):
            raise EnvironmentError(self._missing_key_message(key_env, keyless_possible))

    def _missing_key_message(self, key_env: str, keyless_possible: bool) -> str:
        message = (
            f"{key_env} environment variable is not set (or set SAAF_API_KEY).\n"
            f"Set it with: export {key_env}=your-key-here"
        )
        if keyless_possible:
            message += (
                "\nIf this endpoint needs no key (e.g. a local server), pass "
                f"--allow-no-api-key or set {_ALLOW_NO_API_KEY_ENV}=1."
            )
        elif self.allow_no_api_key:
            message += (
                "\n--allow-no-api-key / allow_no_api_key only applies to the openai "
                "provider with a custom base URL."
            )
        return message

    def _validate_numeric_settings(self) -> None:
        if not _is_number(self.max_tokens, int) or self.max_tokens <= 0:
            raise EnvironmentError("max_tokens must be an integer greater than zero.")
        if not _is_number(self.max_retries, int) or self.max_retries < 0:
            raise EnvironmentError("max_retries must be an integer of zero or more.")
        if (
            not _is_number(self.timeout_seconds, (int, float))
            or not _is_finite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise EnvironmentError("timeout_seconds must be a finite number greater than zero.")
