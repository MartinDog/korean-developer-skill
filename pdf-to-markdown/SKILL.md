---
name: pdf-to-markdown
description: Convert PDF files into Markdown. Use this skill whenever the user asks to read, parse, extract, or convert .pdf files, or needs to process PDF documents (reports, forms, contracts, etc.). It provides both human-readable visual formatting and AI-optimized token-saving extraction.
---

# PDF to Markdown Converter

This skill allows you to convert PDF files (`.pdf`) into Markdown (`.md`) format.

Because PDFs often contain complex tables and layouts (especially Korean government forms, contracts, and reports), this skill provides two distinct conversion strategies. Your primary responsibility is to determine **who the end consumer of the output is** (Human vs. AI) and select the appropriate script.

## Step 1: Determine the End Consumer

Before running any script, analyze the user's intent to decide which conversion mode is required:

- **Choose Human Mode IF:** The user wants to read the document themselves, share it with other people, publish it, or explicitly requests to maintain the visual layout, tables, and structure of the original PDF.
- **Choose AI Mode IF:** The user wants _you_ (the AI) to read and understand the document, extract data from it, summarize it, use it for RAG (Retrieval-Augmented Generation), or explicitly mentions saving tokens/optimizing for AI.

If the intent is ambiguous, ask the user briefly: _"Do you need this formatted for human reading (preserving tables/layouts) or optimized for AI data extraction (saving tokens)?"_

## Step 2: Execute the Conversion

Based on your assessment, run the corresponding Python script. Both scripts output the `.md` file in the same directory as the original file unless specified otherwise.

### Mode A: Human-Readable Conversion

**Script:** `script/pdf_to_markdown_human.py`

This mode preserves the visual structure of the document, utilizing Markdown pipe tables and page separators to match the original PDF layout as closely as possible. Images are embedded as references if `pymupdf` is installed.

**Execution pattern:**

```bash
python script/pdf_to_markdown_human.py <path_to_input_file.pdf>
```

**Required packages:**

```bash
pip install pdfplumber Pillow
pip install pymupdf  # optional, for image extraction
```

### Mode B: AI-Optimized Conversion (Token Saving & Comprehension)

**Script:** `script/pdf_to_markdown_ai.py`

This mode destroys 2D visual formatting (like complex nested tables) and flattens the document into a 1D linear "Key: Value" text structure. It also translates confusing UI elements (like empty/checked checkboxes `[ ]`, `[v]`) into semantic tags (`[미선택]`, `[선택됨]`). Images are noted as `[이미지 N개]` instead of being embedded. This drastically reduces token count and prevents hallucination when you or other LLMs need to parse the document.

**Execution pattern:**

```bash
python script/pdf_to_markdown_ai.py <path_to_input_file.pdf>
```

**Required packages:**

```bash
pip install pdfplumber Pillow
pip install pymupdf  # optional, for image count reporting
```

## Step 3: Post-Processing

After the script completes successfully:

1. Confirm to the user that the file has been converted.
2. Provide the absolute path to the newly created `.md` file.
3. If executed in **AI Mode** for the purpose of answering a user's subsequent question, immediately read the generated `.md` file and proceed to answer their original query using the newly extracted context.

## Important Constraints

- Do not attempt to extract text from PDF files by reading raw bytes. Always use these conversion scripts first.
- If the conversion script fails, check if the file path contains spaces and ensure it is properly quoted in your bash command.
- For scanned PDFs (image-only, no embedded text), `pdfplumber` will extract little or no text. In that case, OCR tools (e.g., `pytesseract`, Adobe Acrobat) are required — inform the user.
