"""
providers.py – Tiny OpenAI-compatible LLM client using only urllib.request.

Configuration is resolved in this priority order:
  1. Explicit kwargs passed to chat_completion().
  2. Environment variables: SKELETON_API_KEY, SKELETON_BASE_URL, SKELETON_MODEL.
  3. A TOML config file at the path in env var SKELETON_CONFIG
     (default: skeleton_crew.toml in the current directory), under [provider].

TOML config example
───────────────────
[provider]
base_url = "https://api.openai.com/v1"
model    = "gpt-4o-mini"
api_key  = "sk-..."
timeout  = 30
"""

from __future__ import annotations

import json
import os
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ── exceptions ────────────────────────────────────────────────────────────────

class ProviderError(RuntimeError):
    """Raised when the provider call fails for any reason."""


# ── config loading ────────────────────────────────────────────────────────────

_DEFAULT_CONFIG_PATH = Path("skeleton_crew.toml")
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_TIMEOUT = 30


def _load_toml_provider_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as fh:
            data = tomllib.load(fh)
        return data.get("provider", {})
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def _resolve_config(
    base_url: str | None,
    model: str | None,
    api_key: str | None,
    timeout: int | None,
) -> tuple[str, str, str, int]:
    """Merge kwargs → env → toml → defaults and return (base_url, model, api_key, timeout)."""
    config_path = Path(os.environ.get("SKELETON_CONFIG", str(_DEFAULT_CONFIG_PATH)))
    toml_cfg = _load_toml_provider_config(config_path)

    resolved_base_url = (
        base_url
        or os.environ.get("SKELETON_BASE_URL")
        or toml_cfg.get("base_url")
        or _DEFAULT_BASE_URL
    )
    resolved_model = (
        model
        or os.environ.get("SKELETON_MODEL")
        or toml_cfg.get("model")
        or _DEFAULT_MODEL
    )
    resolved_api_key = (
        api_key
        or os.environ.get("SKELETON_API_KEY")
        or toml_cfg.get("api_key")
        or ""
    )
    resolved_timeout = int(
        timeout
        or os.environ.get("SKELETON_TIMEOUT", 0)
        or toml_cfg.get("timeout", 0)
        or _DEFAULT_TIMEOUT
    )
    return resolved_base_url, resolved_model, resolved_api_key, resolved_timeout


# ── API call ──────────────────────────────────────────────────────────────────

def chat_completion(
    prompt: str,
    *,
    system: str = "You are a helpful assistant.",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int | None = None,
    max_tokens: int = 512,
    temperature: float = 0.3,
) -> str:
    """Send a chat completion request and return the assistant's reply text.

    Raises ProviderError on any failure (network, auth, bad response).
    """
    resolved_base_url, resolved_model, resolved_api_key, resolved_timeout = _resolve_config(
        base_url, model, api_key, timeout
    )

    url = resolved_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens":  max_tokens,
        "temperature": temperature,
    }

    headers = {
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    if resolved_api_key:
        headers["Authorization"] = f"Bearer {resolved_api_key}"

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=resolved_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise ProviderError(f"HTTP {exc.code}: {raw[:300]}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"URL error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ProviderError(f"Request timed out after {resolved_timeout}s") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Invalid JSON response: {exc}") from exc

    # extract reply
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError(f"Unexpected response shape: {exc}\n{data}") from exc


# ── streaming (optional, non-buffered) ───────────────────────────────────────

def stream_chat_completion(
    prompt: str,
    *,
    system: str = "You are a helpful assistant.",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int | None = None,
) -> None:
    """Stream a chat completion, printing tokens as they arrive (stdout)."""
    import sys

    resolved_base_url, resolved_model, resolved_api_key, resolved_timeout = _resolve_config(
        base_url, model, api_key, timeout
    )

    url = resolved_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model":  resolved_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        "stream": True,
    }

    headers = {"Content-Type": "application/json"}
    if resolved_api_key:
        headers["Authorization"] = f"Bearer {resolved_api_key}"

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=resolved_timeout) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    delta = json.loads(chunk)["choices"][0]["delta"].get("content", "")
                    sys.stdout.write(delta)
                    sys.stdout.flush()
                except (KeyError, IndexError, json.JSONDecodeError):
                    pass
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        raise ProviderError(str(exc)) from exc
    sys.stdout.write("\n")
