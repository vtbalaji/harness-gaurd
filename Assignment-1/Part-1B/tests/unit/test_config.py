"""Configuration and pins (spec FR-020, FR-021; research.md R-10)."""

from __future__ import annotations

import pytest
from conftest import ENV_EXAMPLE_VALUES


def _write_env(tmp_path, text):
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_fr021_env_file_parsing_comments_blank_lines_and_quotes(tmp_path):
    """FR-021, R-10: `#` comments, blank lines, single/double quotes, no interpolation."""
    from order_agent import config

    path = _write_env(
        tmp_path,
        "# endpoints\n"
        "\n"
        "OLLAMA_URL='http://localhost:11434'\n"
        'AGENT_MODEL="qwen3.5:4b"\n'
        "AGENT_MODEL_DIGEST=d8b0f5e9760c\n"
        "   # indented comment\n"
        "JUDGE_URL=http://127.0.0.1:8081/v1/chat/completions\n"
        "JUDGE_MODEL=$AGENT_MODEL\n",
    )
    settings = config.load(env_file=path, environ={})
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.agent_model == "qwen3.5:4b"
    assert settings.agent_model_digest == "d8b0f5e9760c"
    assert settings.judge_url == "http://127.0.0.1:8081/v1/chat/completions"
    # No interpolation: the value is taken literally.
    assert settings.judge_model == "$AGENT_MODEL"


def test_fr021_process_environment_overrides_file(tmp_path):
    """FR-021, R-10: process environment variables override `.env` values."""
    from order_agent import config

    lines = "".join(f"{k}={v}\n" for k, v in ENV_EXAMPLE_VALUES.items())
    path = _write_env(tmp_path, lines)
    settings = config.load(env_file=path, environ={"JUDGE_MODEL": "other-judge"})
    assert settings.judge_model == "other-judge"
    assert settings.ollama_url == "http://localhost:11434"


def test_fr021_load_reads_process_environment_by_default(monkeypatch):
    """FR-021: with no `environ` argument the real process environment is read."""
    from order_agent import config

    for key, value in ENV_EXAMPLE_VALUES.items():
        monkeypatch.setenv(key, value)
    settings = config.load()
    assert settings.agent_model == "qwen3.5:4b"


@pytest.mark.parametrize("missing", sorted(ENV_EXAMPLE_VALUES))
def test_fr021_missing_required_key_raises_config_error_naming_it(missing):
    """FR-021, R-10: a missing required key is a ConfigError that names the key."""
    from order_agent import config

    values = {k: v for k, v in ENV_EXAMPLE_VALUES.items() if k != missing}
    with pytest.raises(config.ConfigError) as info:
        config.load(env_file=None, environ=values)
    assert missing in str(info.value)


def test_fr021_empty_value_counts_as_missing():
    """FR-021, R-10: no hidden defaults; an empty value is missing."""
    from order_agent import config

    values = dict(ENV_EXAMPLE_VALUES, JUDGE_MODEL="")
    with pytest.raises(config.ConfigError, match="JUDGE_MODEL"):
        config.load(env_file=None, environ=values)


def test_fr021_explicit_env_file_that_does_not_exist_is_config_error(tmp_path):
    """FR-021: an explicitly named env file must exist."""
    from order_agent import config

    with pytest.raises(config.ConfigError, match="not found"):
        config.load(env_file=tmp_path / "nope.env", environ=dict(ENV_EXAMPLE_VALUES))


def test_fr021_malformed_env_line_is_config_error(tmp_path):
    """FR-021: a line without `=` is reported, not silently skipped."""
    from order_agent import config

    path = _write_env(tmp_path, "OLLAMA_URL\n")
    with pytest.raises(config.ConfigError, match="line 1"):
        config.load(env_file=path, environ=dict(ENV_EXAMPLE_VALUES))


@pytest.mark.parametrize(
    "url", ["http://localhost:11434", "https://ollama.example:443", "HTTP://LOCALHOST:11434"]
)
def test_fr021_http_and_https_urls_are_accepted(url):
    """FR-021, R-9, R-10: http/https endpoints are accepted."""
    from order_agent import config

    settings = config.load(env_file=None, environ=dict(ENV_EXAMPLE_VALUES, OLLAMA_URL=url))
    assert settings.ollama_url == url


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "ftp://example.com/x", "data:,hello", "localhost:11434", "http://"],
)
@pytest.mark.parametrize("key", ["OLLAMA_URL", "JUDGE_URL"])
def test_fr021_non_http_urls_are_refused(key, url):
    """FR-021, R-9, R-10: `file:`, `ftp:`, `data:` and schemeless URLs are refused."""
    from order_agent import config

    with pytest.raises(config.ConfigError, match=key):
        config.load(env_file=None, environ=dict(ENV_EXAMPLE_VALUES, **{key: url}))


def test_fr020_pin_constants():
    """FR-020: the model, digest, runner version and quantisation pins are code constants."""
    from order_agent import config

    assert config.PINNED_MODEL == "qwen3.5:4b"
    assert config.PINNED_MODEL_DIGEST == "d8b0f5e9760c"
    assert config.PINNED_RUNNER_VERSION == "0.32.14"
    assert config.PINNED_QUANT == "Q4_K_M"


def test_fr020_generation_constants(settings):
    """FR-020, FR-023: generation settings, timeout, attempts and backoff are pinned in code."""
    assert settings.temperature == 0.1
    assert settings.seed == 42
    assert settings.num_predict == 700
    assert settings.think is False
    assert settings.format == "json"
    assert settings.timeout_s == 300
    assert settings.max_attempts == 3
    assert list(settings.backoff_s) == [5, 10]
    assert settings.max_chars == 20000


def test_fr020_settings_constants_cannot_be_set_from_environment():
    """FR-020: `.env` supplies only endpoints and identity; extra keys change nothing."""
    from order_agent import config

    settings = config.load(env_file=None, environ=dict(ENV_EXAMPLE_VALUES, TEMPERATURE="0.9"))
    assert settings.temperature == 0.1


@pytest.mark.parametrize(
    ("prompt_chars", "expected"), [(0, 4096), (8652, 4096), (8655, 4097), (30000, 11212)]
)
def test_fr020_num_ctx_formula(prompt_chars, expected):
    """FR-020: num_ctx = max(4096, prompt_chars // 3 + 700 + 512)."""
    from order_agent import config

    assert config.num_ctx(prompt_chars) == expected


def test_ac_5_6_pin_mismatches_empty_for_pinned_values(settings):
    """AC-5.6 precondition, R-10: the .env.example identity matches the pins."""
    from order_agent import config

    assert config.pin_mismatches(settings) == []


def test_ac_5_6_pin_mismatches_name_the_differing_keys():
    """AC-5.6 precondition, R-10: AGENT_MODEL / AGENT_MODEL_DIGEST mismatches are named."""
    from order_agent import config

    settings = config.load(
        env_file=None,
        environ=dict(ENV_EXAMPLE_VALUES, AGENT_MODEL="qwen3.5:9b", AGENT_MODEL_DIGEST="abc"),
    )
    mismatches = config.pin_mismatches(settings)
    assert len(mismatches) == 2
    assert "AGENT_MODEL" in mismatches[0] and "qwen3.5:9b" in mismatches[0]
    assert "AGENT_MODEL_DIGEST" in mismatches[1]
