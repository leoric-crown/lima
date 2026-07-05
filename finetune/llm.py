"""Minimal OpenAI-compatible chat client for llama-swap (stdlib only)."""

import json
import os
import urllib.request

BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:9292/v1")


def chat(
    messages: list[dict],
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    response_schema: dict | None = None,
    timeout: int = 600,
) -> str:
    """One chat completion; returns the assistant message content.

    response_schema enables llama.cpp schema-constrained (GBNF) decoding via
    the OpenAI-compatible response_format json_schema field.
    """
    body: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "extraction", "strict": True, "schema": response_schema},
        }
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]
