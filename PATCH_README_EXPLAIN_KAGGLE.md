# SEMSYNTH: minimal Kaggle + explainability patch

This ZIP intentionally contains **only files changed or newly added** relative to the uploaded project (October 17, 2026 repository snapshot).

## Changed code

- `src/question_generator.py`: keeps the original semantic/balanced partition scoring, but adds a test-input-grounded explanation and question type; semantic wording is scoped to its observed input.
- `src/semsynth_controller.py`: optional `explain_questions` records question evidence, prior/posterior beliefs, and an answer-likelihood warning without modifying filtering or the chosen question.
- `run_experiments.py`: adds `proposed_explain` as a trace-only ablation; exports `explanations.jsonl` and explanation counts.
- `src/llm_client.py`: raises a useful error for empty Gemini code responses; increases code-generation output token budget and permits bounded retries for empty text.
- `scripts/preflight.py`: accepts manually supplied environment key; no Kaggle Secrets requirement.

## New Kaggle entry points

- `KAGGLE_PASTE_ONE_CELL.py`: paste into **one** Kaggle code cell.
- `notebooks/KAGGLE_ONE_CELL.ipynb`: equivalent notebook.
- `requirements-gemini-kaggle.txt`: minimal dependencies.
- `notebooks/KAGGLE_QUICKSTART.md`: instructions for GitHub or source-ZIP + patch-ZIP workflows.
- `tests/test_explainability_kaggle.py`: correctness and ablation parity checks (offline; no API key required).

## Installation

Overlay the patch ZIP on the project directory, preserving relative paths. Or attach **both ZIPs** to Kaggle: the one-cell runner applies the patch automatically. **Do not run this patch ZIP by itself**: it omits all files that did not change.

## Methodological scope

Only observed input/output evidence is claimed. Behavioral probes do not prove whole-function semantic equivalence. `proposed_explain` and `proposed` have the same inference and selection decisions; the experiment itself does not establish whether human users find the explanations easier to understand.
