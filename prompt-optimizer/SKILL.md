---
name: prompt-optimizer
description: >
  Dramatically reduces Claude token usage by pre-processing verbose or Korean-language prompts through a local Small Language Model (SLM) via Ollama before sending them to Claude. Use this skill whenever the user invokes /prompt-optimizer, mentions wanting to save tokens, reduce prompt cost, compress a prompt, or sends a long Korean prompt they want optimized first. Also trigger when the user says things like "토큰 절약", "프롬프트 최적화", "비용 줄이기", or asks to make a prompt more concise before running it. Korean text costs ~2-3x more tokens than English, and removing conversational filler can cut 40-70% of tokens — combined savings of 60-80% are typical.
---

# Prompt Optimizer

This skill pre-processes a verbose or Korean-language prompt through a local SLM (Ollama) to extract the core technical intent as a concise English prompt — before sending anything to Claude. The goal is maximum token reduction with zero loss of intent.

## Why this works

- Korean text uses ~2-3x more tokens than equivalent English
- Conversational filler ("안녕하세요", "혹시", "이것저것", "~같은데요") adds tokens without adding meaning
- A local SLM (Qwen 2.5 1.5B) running on Ollama is fast, free, and perfect for this compression step
- Combined savings: typically 60–80% fewer tokens sent to Claude

## Workflow

### Step 1: Parse the invocation

The user calls `/prompt-optimizer` followed by their prompt. Extract:

- **The prompt to optimize**: everything after `/prompt-optimizer` (and any flags)
- **`--model`** (optional): Ollama model to use, default `qwen2.5:1.5b`
- **`--dry-run`** (optional): if present, show the optimized prompt but do NOT execute it as a task
- **`--compare`** (optional): if present, show full before/after comparison including original prompt

Default behavior: show optimized result and execute the task immediately.

### Step 2: Estimate original token count

Calculate a rough estimate before optimization:

- Korean characters: ~1 token per 1.5 chars
- English characters: ~1 token per 4 chars
- Mixed text: count Korean and English portions separately

Display: `Original: ~{N} tokens ({len} chars)`

### Step 3: Try Ollama optimization

Run the helper script to call the local Ollama API:

```bash
python /c/Users/user/.claude/skills/prompt-optimizer/scripts/optimize.py \
  --prompt "{escaped_prompt}" \
  --model qwen2.5:1.5b
```

The script:

1. Checks if Ollama is running at `http://localhost:11434`
2. If available: sends prompt to SLM with the compression system prompt, returns JSON
3. If unavailable: exits with code 1 and message `OLLAMA_UNAVAILABLE`

The script returns JSON:

```json
{
  "optimized_english_prompt": "...",
  "keywords": ["keyword1", "keyword2"],
  "ollama_available": true
}
```

### Step 4: Handle Ollama unavailable (fallback)

If the script returns `OLLAMA_UNAVAILABLE` or fails, fall back to Claude's own compression:

Tell the user:

> "Ollama is not running locally. Falling back to Claude's built-in compression."

Then internally compress the prompt yourself:

- Translate to English if Korean
- Strip greetings, filler words, and background context that isn't directly needed
- Keep only the technical action, target, and constraints
- Produce a single concise English sentence or two

### Step 5: Show the optimization results

**Default output** (no `--compare` flag): show only the optimized prompt and savings summary.

```
 "{optimized_prompt}"
 Keywords: {keywords}
```

**With `--compare` flag**: show full before/after comparison.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PROMPT OPTIMIZER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Original  (~{N} tokens):
 "{original_prompt}"

 Optimized (~{M} tokens):
 "{optimized_prompt}"

 Keywords: {keywords}
 Savings:  ~{savings}% fewer tokens
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 6: Execute (only with --run)

If `--dry-run` was NOT specified (default), proceed to execute the optimized prompt as a normal Claude Code task — treat it exactly as if the user had typed the optimized prompt directly.

If `--dry-run` was specified, stop after showing the results and ask: "Want me to run this optimized prompt now?"

## Token estimation helper

For the savings display, compute:

- `original_tokens`: estimated from original text (Korean + English formula)
- `optimized_tokens`: estimated from optimized English text (÷4 chars)
- `savings_pct`: `round((1 - optimized_tokens / original_tokens) * 100)`

## Edge cases

- **Already concise English prompt**: still run it, the SLM may still trim further. Report honestly if savings are minimal (<10%).
- **Code blocks in the prompt**: preserve code exactly; only compress the surrounding natural language.
- **Very short prompts (<20 tokens)**: skip Ollama, note "Prompt is already minimal", and execute as-is.
- **Ollama returns invalid JSON**: fall back to Claude compression silently, note "SLM returned unexpected format, used Claude fallback."
- **Multiple sentences / long prompts**: the SLM handles these well; no need to chunk.
