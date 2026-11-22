"""Configuration: `.env` loading, URL scheme check, pins and generation settings.

Spec FR-020, FR-021; research.md R-10. The pins and the generation settings are code constants:
`.env` supplies only the endpoints and the model identity, which is compared with the pins.
There are no hidden defaults: every required key must come from the `.env` file or the process
environment, and the process environment wins.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

# Pins (FR-020). AGENT_MODEL / AGENT_MODEL_DIGEST from the environment must equal these.
PINNED_MODEL = "qwen3.5:4b"
PINNED_MODEL_DIGEST = "d8b0f5e9760c"
PINNED_RUNNER_VERSION = "0.32.14"
PINNED_QUANT = "Q4_K_M"

# Generation settings (FR-020), retries (FR-023), guard limit (FR-017, CONFIRMED P-1.4).
TEMPERATURE = 0.1
SEED = 42
NUM_PREDICT = 700
THINK = False
FORMAT = "json"
TIMEOUT_S = 300
MAX_ATTEMPTS = 3
BACKOFF_S = (5, 10)
MAX_CHARS = 20000
NUM_CTX_FLOOR = 4096
NUM_CTX_MARGIN = 512
NUM_CTX_FORMULA = "max(4096, prompt_chars // 3 + num_predict + 512)"

# Judge settings (research.md R-12 rev 2).
JUDGE_TIMEOUT_S = 180
JUDGE_MAX_TOKENS = 600
JUDGE_DISABLE_THINKING = True

REQUIRED_KEYS = ("OLLAMA_URL", "AGENT_MODEL", "AGENT_MODEL_DIGEST", "JUDGE_URL", "JUDGE_MODEL")
URL_KEYS = ("OLLAMA_URL", "JUDGE_URL")


class ConfigError(Exception):
    """A configuration problem: missing key, bad URL scheme or unreadable env file (exit 78)."""


@dataclass(frozen=True)
class Settings:
    """Endpoints and identity from the environment, plus the pinned constants."""

    ollama_url: str
    agent_model: str
    agent_model_digest: str
    judge_url: str
    judge_model: str
    temperature: float = field(default=TEMPERATURE, init=False)
    seed: int = field(default=SEED, init=False)
    num_predict: int = field(default=NUM_PREDICT, init=False)
    think: bool = field(default=THINK, init=False)
    format: str = field(default=FORMAT, init=False)
    timeout_s: int = field(default=TIMEOUT_S, init=False)
    max_attempts: int = field(default=MAX_ATTEMPTS, init=False)
    backoff_s: tuple[int, ...] = field(default=BACKOFF_S, init=False)
    max_chars: int = field(default=MAX_CHARS, init=False)


def num_ctx(prompt_chars: int) -> int:
    """FR-020: `max(4096, prompt_chars // 3 + num_predict + 512)`."""
    return max(NUM_CTX_FLOOR, prompt_chars // 3 + NUM_PREDICT + NUM_CTX_MARGIN)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_env_file(path: Path) -> dict[str, str]:
    """Read `KEY=VALUE` lines: `#` comments and blank lines are skipped, one pair of matching
    single or double quotes is removed, and nothing is interpolated."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"env file not found: {path}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"env file unreadable: {path}: {exc}") from None
    values: dict[str, str] = {}
    for number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key:
            raise ConfigError(f"{path}: line {number} is not KEY=VALUE")
        values[key] = _unquote(value.strip())
    return values


def _check_url(key: str, url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        raise ConfigError(f"{key} must be an http or https URL with a host, got {url!r}")


def load(env_file: Path | str | None = None, environ: Mapping[str, str] | None = None) -> Settings:
    """Load the settings. `environ` defaults to the process environment and overrides the file."""
    values: dict[str, str] = {}
    if env_file is not None:
        values.update(parse_env_file(Path(env_file)))
    source = os.environ if environ is None else environ
    for key in REQUIRED_KEYS:
        if key in source:
            values[key] = source[key]
    for key in REQUIRED_KEYS:
        if not values.get(key):
            raise ConfigError(f"missing required configuration key {key} (set it in .env)")
    for key in URL_KEYS:
        _check_url(key, values[key])
    return Settings(
        ollama_url=values["OLLAMA_URL"],
        agent_model=values["AGENT_MODEL"],
        agent_model_digest=values["AGENT_MODEL_DIGEST"],
        judge_url=values["JUDGE_URL"],
        judge_model=values["JUDGE_MODEL"],
    )


def pin_mismatches(settings: Settings) -> list[str]:
    """R-10, AC-5.6: one message per identity value that differs from its pin."""
    mismatches = []
    if settings.agent_model != PINNED_MODEL:
        mismatches.append(
            f"AGENT_MODEL={settings.agent_model} differs from the pinned model {PINNED_MODEL}"
        )
    if settings.agent_model_digest != PINNED_MODEL_DIGEST:
        mismatches.append(
            f"AGENT_MODEL_DIGEST={settings.agent_model_digest} differs from the pinned digest "
            f"{PINNED_MODEL_DIGEST}"
        )
    return mismatches
