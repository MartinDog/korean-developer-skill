---
name: hanguel-to-markdown
description: Convert Korean Word Processor (.hwp, .hwpx) files into Markdown. Make sure to use this skill whenever the user asks to read, parse, extract, or convert .hwp or .hwpx files, mentions "Hancom" or "Hangul" documents, or needs to process Korean government/corporate forms. It provides both human-readable visual formatting and AI-optimized token-saving extraction.
---

# HWP/HWPX to Markdown Converter

This skill allows you to convert Hangul Word Processor files (`.hwp`, `.hwpx`) into Markdown (`.md`) format.

Because HWP files often contain complex tables and layouts (especially in Korean government or corporate forms), this skill provides two distinct conversion strategies. Your primary responsibility is to determine **who the end consumer of the output is** (Human vs. AI) and select the appropriate script.

## Step 1: Determine the End Consumer

Before running any script, analyze the user's intent to decide which conversion mode is required:

- **Choose Human Mode IF:** The user wants to read the document themselves, share it with other people, publish it, or explicitly requests to maintain the visual layout, tables, and structure of the original document.
- **Choose AI Mode IF:** The user wants _you_ (the AI) to read and understand the document, extract data from it, summarize it, use it for RAG (Retrieval-Augmented Generation), or explicitly mentions saving tokens/optimizing for AI.

If the intent is ambiguous, ask the user briefly: _"Do you need this formatted for human reading (preserving tables/layouts) or optimized for AI data extraction (saving tokens)?"_

## Step 2: Execute the Conversion

Based on your assessment, run the corresponding Python script. Both scripts will output the resulting `.md` file in the same directory as the original file unless specified otherwise.

### Mode A: Human-Readable Conversion

**Script:** `scripts/hwp_to_markdown_human.py`

This mode preserves the visual structure of the document, utilizing HTML tables and markdown formatting to match the original HWP file as closely as possible.

**Execution pattern:**

```bash
python scripts/hwp_to_markdown_human.py <path_to_input_file.hwp/hwpx>
```

### Mode B: AI-Optimized Conversion (Token Saving & Comprehension)

**Script:** `scripts/hwp_to_markdown_ai.py`

This mode destroys 2D visual formatting (like complex nested tables) and flattens the document into a 1D linear "Key: Value" text structure. It also translates confusing UI elements (like empty/checked checkboxes [ ], [v]) into semantic tags (e.g., [미선택], [선택됨]). This drastically reduces token count and prevents hallucination when you or other LLMs need to parse the document.

Execution pattern:

```bash
python scripts/hwp_to_markdown_ai.py <path_to_input_file.hwp/hwpx>
```

Step 3: Post-Processing
After the script completes successfully:

Confirm to the user that the file has been converted.

Provide the absolute path to the newly created .md file.

If executed in AI Mode for the purpose of answering a user's subsequent question, immediately read the generated .md file and proceed to answer their original query using the newly extracted context.

Important Constraints
Do not attempt to parse .hwp or .hwpx files as raw text. Always use these conversion scripts first.

If the conversion script fails, check if the file path contains spaces and ensure it is properly quoted in your bash command.
