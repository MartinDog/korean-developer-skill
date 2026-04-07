#!/usr/bin/env python3
"""
prompt-optimizer helper: calls local Ollama API to compress a prompt.
Prints JSON result to stdout, or exits with code 1 printing OLLAMA_UNAVAILABLE.
"""

import argparse
import json
import sys

import requests


SYSTEM_PROMPT = """You are a prompt compression engine for a coding assistant.
Your only job: read the user's input (which may be Korean or English), extract the core technical intent, and return it as a minimal English prompt.

Rules:
1. Output ONLY valid JSON — no markdown, no explanation, no extra text.
2. Remove ALL of these: greetings, apologies, filler phrases, personal context, repetition.
3. Translate Korean to English.
4. Preserve: exact technical nouns, file names, error messages, code identifiers, and specific constraints.
5. The optimized_english_prompt must be a single actionable instruction in plain English.

JSON schema (use exactly this):
{
  "optimized_english_prompt": "<concise English instruction>",
  "keywords": ["<tech term 1>", "<tech term 2>"]
}"""


def check_ollama(base_url: str) -> bool:
    try:
        r = requests.get(base_url, timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def optimize(prompt: str, model: str, base_url: str) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "format": "json",
        "stream": False,
    }
    r = requests.post(f"{base_url}/api/chat", json=payload, timeout=30)
    r.raise_for_status()
    content = r.json()["message"]["content"]
    data = json.loads(content)
    data["ollama_available"] = True
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model", default="qwen3.5:2b")
    parser.add_argument("--base-url", default="http://localhost:11434")
    args = parser.parse_args()

    if not check_ollama(args.base_url):
        print("OLLAMA_UNAVAILABLE", file=sys.stderr)
        sys.exit(1)

    try:
        result = optimize(args.prompt, args.model, args.base_url)
        print(json.dumps(result, ensure_ascii=False))
    except json.JSONDecodeError:
        print("INVALID_JSON_RESPONSE", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
