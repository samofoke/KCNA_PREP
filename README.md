# KCNA_PREP

Interactive KCNA exam prep as a single-page quiz UI driven by a JSON dataset. Includes utilities to build the dataset from the official PDF.

## Quick Start

1) Open the quiz UI

- Open `kcna_prep.html` in a browser (no server required).
- Click “Upload JSON”, select a dataset (e.g., `kcna_from_pdf.json`).
- Pick Mode (Study, Practice, Mock), ordering (Sequential, Shuffled), and optional filters.
- Start the quiz, answer questions, check explanations, and review results.

2) Use the sample dataset

- `kcna_from_pdf.json` is a ready-to-use dataset built from the KCNA prep PDF.

## JSON Dataset Format

The UI expects a top-level object with `sections`, where each section contains `questions`. Minimal shape:

```json
{
  "source_file": "KCNA-exam-prep.pdf",
  "generated_at": "2025-09-02T14:56:32.878843",
  "sections": [
    {
      "section_key": "2.1",
      "title": "All Sections 1",
      "questions": [
        {
          "number": 1,
          "question": "…",
          "options": ["A …", "B …", "C …", "D …", "E …"],
          "answer": "C",
          "answerIndex": 2,
          "explanation": "…",
          "domain": "…",
          "competency": "…"
        }
      ]
    }
  ]
}
```

Notes:

- `answer` can be `A`–`E` and/or `answerIndex` as 0-based index; the UI uses `answerIndex` if present.
- `domain` and `competency` are optional but improve filtering and reporting.

## Build the JSON from the PDF

Scripts in `tools/` parse the KCNA prep PDF and generate or enrich a quiz dataset.

Prerequisites:

- Python 3.8+
- `pdftotext` from poppler (e.g., `apt-get install poppler-utils` or `brew install poppler`).

### End-to-end builder

Generates `kcna_from_pdf.json` directly from the PDF by parsing Quizzes and Solutions and merging them.

- Place the PDF at repo root as `KCNA-exam-prep.pdf`.
- Run:

```bash
python3 tools/build_kcna_from_pdf.py
```

Outputs:

- `KCNA-exam-prep.txt` (intermediate text extracted with layout)
- `kcna_from_pdf.json` (final dataset)

### Fill options into an existing JSON

If you already have a base JSON with questions/answers but missing options, you can fill options by parsing the PDF’s Quizzes section.

- Ensure you have a source JSON named `kcna_prep_qna_clean.json` at repo root.
- Place `KCNA-exam-prep.pdf` alongside it.
- Run:

```bash
python3 tools/fill_options_from_pdf.py
```

Outputs:

- `KCNA-exam-prep.txt` (intermediate)
- `kcna_prep_qna_clean.filled.json` (enriched with options; adds `answerIndex` where deducible)

## Features in `kcna_prep.html`

- Modes: Study (instant feedback), Practice (check per-question), Mock (exam-like flow, review at end)
- Ordering: Sequential or Shuffled
- Filters: domain/competency selection (when present in JSON)
- Progress: tracker, per-domain score, elapsed timer
- Review: detailed results with correct/incorrect marking and explanations
- Offline: all client-side; optional CDN for Chart.js

## Caveats

- PDF parsing is best-effort: review the generated JSON for line-break artifacts, hyphenated words, or occasional option mis-grouping.
- Filenames are significant in the scripts; use the defaults or adjust constants at the top of the scripts in `tools/`.

## Files

- `kcna_prep.html` — Quiz UI (open in browser)
- `kcna_from_pdf.json` — Sample dataset generated from the PDF
- `tools/build_kcna_from_pdf.py` — Build dataset from PDF (questions, options, answers, explanations)
- `tools/fill_options_from_pdf.py` — Fill missing options in an existing JSON using the PDF
