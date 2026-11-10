"""
SAAF — Config provider / model / endpoint resolution (explicit arg > env > default).

Run with:
    python -m unittest tests.test_config -v
"""

from __future__ import annotations

import io
import sys
import unittest
from functools import partial
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config as config_module
from config import _PROVIDER_KEY_ENV, Config
from saaf.core.llm import PROVIDERS, OpenAICompatibleClient, create_client
from tests import endpoints as E


def _env(**kw):
    """Replace the whole environment so a developer's real keys never leak in."""
    return patch.dict("os.environ", kw, clear=True)


class TestConfigDefaults(unittest.TestCase):

    def test_default_is_anthropic_with_unchanged_model(self):
        with _env(ANTHROPIC_API_KEY="k"):
            c = Config()
        self.assertEqual((c.provider, c.model, c.base_url, c.api_key),
                         ("anthropic", "claude-opus-4-6", "", "k"))

    def test_missing_anthropic_key_raises(self):
        with _env(), self.assertRaises(EnvironmentError) as ctx:
            Config()
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))


class TestConfigProviders(unittest.TestCase):

    def test_openai_requires_a_model(self):
        with _env(OPENAI_API_KEY="k"), self.assertRaises(EnvironmentError) as ctx:
            Config(provider="openai")
        self.assertIn("--model", str(ctx.exception))

    def test_openai_uses_openai_key_env(self):
        with _env(OPENAI_API_KEY="ok"):
            c = Config(provider="openai", model="gpt-x")
        self.assertEqual(c.api_key, "ok")

    def test_openai_hosted_without_key_raises(self):
        with _env(), self.assertRaises(EnvironmentError):
            Config(provider="openai", model="gpt-x")

    def test_custom_endpoint_without_key_needs_explicit_opt_in(self):
        with _env(), self.assertRaises(EnvironmentError) as ctx:
            Config(provider="openai", model="llama3", base_url=E.LOCAL_OLLAMA_BASE)
        self.assertIn("--allow-no-api-key", str(ctx.exception))
        self.assertIn("SAAF_ALLOW_NO_API_KEY=1", str(ctx.exception))

    def test_anthropic_still_requires_key_with_custom_endpoint(self):
        with _env(), self.assertRaises(EnvironmentError):
            Config(base_url=E.ANTHROPIC_PROXY_BASE)

    def test_unknown_provider_rejected(self):
        with _env(), self.assertRaises(EnvironmentError):
            Config(provider="gemini")


class TestConfigPrecedence(unittest.TestCase):

    def test_env_vars_apply(self):
        with _env(SAAF_PROVIDER="OpenAI", SAAF_MODEL="m1", SAAF_BASE_URL=E.SLASHED_BASE,
                  SAAF_API_KEY="generic"):
            c = Config()
        self.assertEqual((c.provider, c.model, c.base_url, c.api_key),
                         ("openai", "m1", E.SLASHED_BASE.rstrip("/"), "generic"))

    def test_explicit_arguments_beat_env(self):
        with _env(SAAF_PROVIDER="anthropic", SAAF_MODEL="env-model", SAAF_BASE_URL=E.ENV_BASE,
                  ANTHROPIC_API_KEY="k"):
            c = Config(provider="openai", model="arg-model", base_url=E.ARG_BASE,
                       api_key="arg-key")
        self.assertEqual((c.provider, c.model, c.base_url, c.api_key),
                         ("openai", "arg-model", E.ARG_BASE, "arg-key"))

    def test_saaf_api_key_beats_provider_key(self):
        with _env(SAAF_API_KEY="generic", ANTHROPIC_API_KEY="specific"):
            self.assertEqual(Config().api_key, "generic")

    def test_invalid_base_url_raises_environment_error(self):
        with _env(ANTHROPIC_API_KEY="k"), self.assertRaises(EnvironmentError):
            Config(base_url="not-a-url")


class TestConfigKeylessOptIn(unittest.TestCase):

    LOCAL = dict(provider="openai", model="llama3", base_url=E.LOCAL_OLLAMA_BASE)

    def test_explicit_opt_in_allows_missing_key(self):
        with _env():
            c = Config(allow_no_api_key=True, **self.LOCAL)
        self.assertEqual((c.api_key, c.base_url), ("", E.LOCAL_OLLAMA_BASE))

    def test_env_values_that_enable(self):
        for value in ("1", "true", "YES", " on "):
            with self.subTest(value=value), _env(SAAF_ALLOW_NO_API_KEY=value):
                self.assertTrue(Config(**self.LOCAL).allow_no_api_key)

    def test_env_values_that_do_not_enable(self):
        for value in ("", "  ", "0", "false", "No", "off"):
            with self.subTest(value=value), _env(SAAF_ALLOW_NO_API_KEY=value), \
                 self.assertRaises(EnvironmentError):
                Config(**self.LOCAL)

    def test_unrecognised_env_value_is_rejected(self):
        with _env(SAAF_ALLOW_NO_API_KEY="maybe", OPENAI_API_KEY="k"), \
             self.assertRaises(EnvironmentError) as ctx:
            Config(**self.LOCAL)
        self.assertIn("SAAF_ALLOW_NO_API_KEY", str(ctx.exception))

    def test_non_boolean_argument_is_rejected(self):
        with _env(), self.assertRaises(EnvironmentError):
            Config(allow_no_api_key="false", **self.LOCAL)

    def test_opt_in_does_not_apply_to_hosted_openai(self):
        with _env(), self.assertRaises(EnvironmentError) as ctx:
            Config(provider="openai", model="m", allow_no_api_key=True)
        self.assertIn("only applies", str(ctx.exception))

    def test_opt_in_does_not_apply_to_anthropic(self):
        with _env(), self.assertRaises(EnvironmentError):
            Config(base_url=E.ANTHROPIC_PROXY_BASE, allow_no_api_key=True)

    def test_opt_in_is_harmless_when_a_key_is_present(self):
        with _env(SAAF_ALLOW_NO_API_KEY="1", ANTHROPIC_API_KEY="k"):
            self.assertEqual(Config().api_key, "k")

    def test_custom_endpoint_inherits_env_key_even_with_opt_in(self):
        """Credential routing policy: allow_no_api_key permits a missing key, no more."""
        with _env(OPENAI_API_KEY="inherited"):
            c = Config(allow_no_api_key=True, **self.LOCAL)
        self.assertEqual(c.api_key, "inherited")

    def test_keyless_config_builds_a_client(self):
        with _env():
            client = create_client(Config(allow_no_api_key=True, **self.LOCAL))
        self.assertIsInstance(client, OpenAICompatibleClient)
        self.assertEqual((client.api_key, client.url), ("", E.LOCAL_OLLAMA_ENDPOINT))


class TestConfigRepr(unittest.TestCase):

    def test_repr_does_not_contain_api_key(self):
        with _env():
            text = repr(Config(api_key="test-key"))
        self.assertNotIn("test-key", text)


class TestConfigBaseUrl(unittest.TestCase):

    def test_none_inherits_env(self):
        with _env(ANTHROPIC_API_KEY="k", SAAF_BASE_URL=E.ENV_BASE):
            self.assertEqual(Config(base_url=None).base_url, E.ENV_BASE)

    def test_explicit_empty_overrides_env(self):
        with _env(ANTHROPIC_API_KEY="k", SAAF_BASE_URL=E.ENV_BASE):
            self.assertEqual(Config(base_url="").base_url, "")

    def test_explicit_whitespace_overrides_env(self):
        with _env(ANTHROPIC_API_KEY="k", SAAF_BASE_URL=E.ENV_BASE):
            self.assertEqual(Config(base_url="   ").base_url, "")

    def test_explicit_empty_keeps_key_required_for_openai(self):
        with _env(SAAF_BASE_URL=E.ENV_BASE), self.assertRaises(EnvironmentError):
            Config(provider="openai", model="m", base_url="", allow_no_api_key=True)


class TestConfigBlankValues(unittest.TestCase):

    def test_blank_saaf_api_key_does_not_hide_provider_key(self):
        with _env(SAAF_API_KEY="   ", ANTHROPIC_API_KEY="specific"):
            self.assertEqual(Config().api_key, "specific")

    def test_blank_explicit_key_falls_through_to_env(self):
        with _env(SAAF_API_KEY="generic"):
            self.assertEqual(Config(api_key="  ").api_key, "generic")

    def test_only_blank_keys_count_as_missing(self):
        with _env(SAAF_API_KEY=" ", ANTHROPIC_API_KEY="\t"), self.assertRaises(EnvironmentError):
            Config()

    def test_key_is_stripped(self):
        with _env(ANTHROPIC_API_KEY=" k\n"):
            self.assertEqual(Config().api_key, "k")

    def test_blank_env_provider_uses_default(self):
        with _env(SAAF_PROVIDER="   ", ANTHROPIC_API_KEY="k"):
            self.assertEqual(Config().provider, "anthropic")

    def test_blank_explicit_provider_falls_through_to_env(self):
        with _env(SAAF_PROVIDER="openai", SAAF_MODEL="m", OPENAI_API_KEY="k"):
            self.assertEqual(Config(provider="  ").provider, "openai")

    def test_blank_env_model_uses_default(self):
        with _env(SAAF_MODEL="   ", ANTHROPIC_API_KEY="k"):
            self.assertEqual(Config().model, "claude-opus-4-6")

    def test_blank_model_with_no_default_is_missing(self):
        with _env(SAAF_MODEL=" ", OPENAI_API_KEY="k"), self.assertRaises(EnvironmentError) as ctx:
            Config(provider="openai", model=" ")
        self.assertIn("--model", str(ctx.exception))


class TestConfigProviderMetadata(unittest.TestCase):

    def test_every_provider_has_key_env_metadata(self):
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                self.assertIn(provider, _PROVIDER_KEY_ENV)

    def test_provider_without_metadata_is_a_configuration_error(self):
        with _env(), patch.object(config_module, "PROVIDERS", ("anthropic", "gemini")), \
             self.assertRaises(EnvironmentError) as ctx:
            Config(provider="gemini", model="m")
        self.assertIn("gemini", str(ctx.exception))


class TestConfigNumericValidation(unittest.TestCase):

    INVALID = [
        ("max_tokens", 0), ("max_tokens", -1), ("max_tokens", True), ("max_tokens", 1.5),
        ("max_tokens", "100"), ("max_tokens", None),
        ("max_retries", -1), ("max_retries", False), ("max_retries", 1.0), ("max_retries", "2"),
        ("timeout_seconds", 0), ("timeout_seconds", -1), ("timeout_seconds", True),
        ("timeout_seconds", "180"), ("timeout_seconds", float("nan")),
        ("timeout_seconds", float("inf")), ("timeout_seconds", 10 ** 400),
    ]

    def test_invalid_values_raise_environment_error(self):
        for name, value in self.INVALID:
            with self.subTest(name=name, value=value), _env(ANTHROPIC_API_KEY="k"), \
                 self.assertRaises(EnvironmentError) as ctx:
                Config(**{name: value})
            self.assertIn(name, str(ctx.exception))

    def test_boundary_values_are_accepted(self):
        with _env(ANTHROPIC_API_KEY="k"):
            c = Config(max_tokens=1, max_retries=0, timeout_seconds=0.5)
        self.assertEqual((c.max_tokens, c.max_retries, c.timeout_seconds), (1, 0, 0.5))

    def test_defaults_are_unchanged(self):
        with _env(ANTHROPIC_API_KEY="k"):
            c = Config()
        self.assertEqual((c.max_tokens, c.max_retries, c.timeout_seconds), (32000, 2, 180))


class TestCliConfigWiring(unittest.TestCase):
    """cli.main() with the real Config and a stubbed agent (no LLM calls)."""

    ARGV = ["saaf", "--company", "Acme", "--industry", "Healthcare", "--country", "US",
            "--listed-status", "Private", "--audit-topic", "Cybersecurity", "--yes"]

    def _main(self, *extra, config_cls=Config):
        """Return (exit code, the Config handed to the agent or None, stderr text)."""
        import cli
        err = io.StringIO()
        with patch.object(sys, "argv", self.ARGV + list(extra)), \
             patch.object(cli, "Config", config_cls), \
             patch.object(cli, "ComplianceAgent") as agent_cls, \
             patch.object(cli, "err_console", cli.Console(file=err, width=200)), \
             patch.object(cli, "console", cli.Console(file=io.StringIO())), \
             patch.object(cli, "render_report"):
            agent_cls.return_value.run.return_value = (MagicMock(), MagicMock())
            rc = cli.main()
        config = agent_cls.call_args.args[0] if agent_cls.called else None
        return rc, config, err.getvalue()

    def test_omitted_base_url_inherits_env(self):
        with _env(ANTHROPIC_API_KEY="k", SAAF_BASE_URL=E.ENV_BASE):
            rc, config, _ = self._main()
        self.assertEqual(rc, 0)
        self.assertEqual(config.base_url, E.ENV_BASE)

    def test_omitted_flags_reach_config_as_none(self):
        config_cls = MagicMock()
        with _env():
            self._main(config_cls=config_cls)
        config_cls.assert_called_once_with(
            provider=None, model=None, base_url=None, allow_no_api_key=False
        )

    def test_explicit_empty_base_url_overrides_env(self):
        with _env(ANTHROPIC_API_KEY="k", SAAF_BASE_URL=E.ENV_BASE):
            rc, config, _ = self._main("--base-url", "")
        self.assertEqual(rc, 0)
        self.assertEqual(config.base_url, "")

    def test_flag_enables_keyless_custom_endpoint(self):
        with _env():
            rc, config, _ = self._main("--provider", "openai", "--model", "llama3", "--base-url",
                                       E.LOCAL_OLLAMA_BASE, "--allow-no-api-key")
        self.assertEqual(rc, 0)
        self.assertEqual(config.api_key, "")

    def test_env_var_enables_keyless_custom_endpoint(self):
        with _env(SAAF_ALLOW_NO_API_KEY="1"):
            rc, config, _ = self._main("--provider", "openai", "--model", "llama3", "--base-url",
                                       E.LOCAL_OLLAMA_BASE)
        self.assertEqual(rc, 0)
        self.assertEqual(config.api_key, "")

    def test_keyless_without_opt_in_is_a_clean_error_naming_the_fix(self):
        with _env():
            rc, config, err = self._main("--provider", "openai", "--model", "llama3",
                                         "--base-url", E.LOCAL_OLLAMA_BASE)
        self.assertEqual(rc, 1)
        self.assertIsNone(config)
        self.assertIn("Configuration error", err)
        self.assertIn("--allow-no-api-key", err)
        self.assertIn("SAAF_ALLOW_NO_API_KEY=1", err)

    def test_invalid_numeric_setting_is_a_clean_configuration_error(self):
        with _env(ANTHROPIC_API_KEY="k"):
            rc, config, err = self._main(config_cls=partial(Config, max_tokens=-1))
        self.assertEqual(rc, 1)
        self.assertIsNone(config)
        self.assertIn("Configuration error", err)
        self.assertIn("max_tokens", err)


if __name__ == "__main__":
    unittest.main()
