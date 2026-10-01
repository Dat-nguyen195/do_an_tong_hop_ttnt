# SEMSYNTH Lite — Runnable / Kaggle / Gemini Improvement Review

## Verified status

- Original repository: 40 tests passed.
- Improved repository: 70 tests passed.
- Python syntax compilation passed for app, runner, source modules, and tests.
- Deterministic offline integration suite runs 3 ambiguity cases:
  - remove duplicates: correctly removes the order-destroying candidate and stops with two behaviorally indistinguishable order-preserving implementations;
  - sorting: converges to one candidate;
  - common elements: converges to one candidate.
- Gemini adapter is unit-tested with a fake SDK client. A live Gemini request was not executed because no user API key is available in the test environment.

## Changes made

1. Added direct `gemini` provider support to `LLMClient` using the `google-genai` SDK.
2. Added `GEMINI_API_KEY` and `gemini-3.8-flash` defaults for Kaggle/demo use.
3. Added Gemini to the Streamlit provider selector.
4. Added `--offline-suite`, `--top-k`, and `--max-questions` to the Kaggle runner.
5. Added a one-cell Kaggle + Gemini notebook and updated Kaggle instructions.
6. Increased automated coverage from 40 to 70 tests.
7. Fixed empty-test behavior so an empty suite is not reported as `passed_all=True`.
8. Hardened several obvious executor escape paths (`globals`, `__builtins__`, dunder attributes, etc.).
9. Improved default probe type inference for tuple/list and string-style parameter names.
10. Avoided asking a user to approve an exception/error as the intended output.
11. Added controller termination reasons such as `single_candidate`, `no_candidates`, `question_budget_exhausted`, and `no_distinguishing_question`.

## Main research/methodology issues still worth improving

### 1. The current question is behavioral I/O, not fully semantic natural language

The current generated question is structurally:

`For input {...}, should the function return Y?`

That is useful and formally grounded, but it is close to a test-case clarification. If the report claims the novelty is *semantic Yes/No questions* rather than test-case interaction, the implementation should add a semantic-naturalization layer.

Recommended minimal architecture:

1. Keep the current behavior partition as the source of truth.
2. Derive a short semantic property from the disagreement, e.g. “Should duplicate removal preserve first-occurrence order?”
3. Ask that semantic Yes/No question to the user.
4. Retain the candidate partition IDs computed from execution, so the LLM wording cannot alter filtering correctness.
5. Fall back to the existing input/output question if a semantic property cannot be generated reliably.

This keeps the mathematical information-gain idea unchanged while making the implementation match the stated novelty much better.

### 2. `baseline_cot.py` is currently better described as Direct-1

The generation prompt asks for a solution and returns only code. It does not implement an explicit chain-of-thought baseline. The README already labels the experiment `Direct-1`, which is more accurate.

Recommended choice: keep the code as Direct-1 and update the report terminology rather than claiming a CoT baseline that is not implemented.

### 3. Probe generation is still heuristic

The probe generator mutates a small set of seed values. It is lightweight and deterministic, but can miss semantic disagreements.

Recommended next step: add type-aware boundary templates before adding a heavy fuzzing dependency. Examples:

- lists: empty, singleton, duplicates, already sorted, reverse sorted, negatives;
- strings: empty, one character, repeated characters, case changes;
- numeric thresholds: zero, negative, equality boundary, just-below/just-above boundary.

Then score all discovered disagreements with the existing information-gain function.

### 4. Candidate correctness and synthesis success are different concepts

`SessionResult.success` means that a candidate remains available. It does not prove that the candidate is correct on hidden benchmark tests.

For experiments, report at least:

- candidate-generation success;
- convergence/termination reason;
- hidden-test pass rate;
- questions asked;
- LLM calls/tokens or API-call count;
- elapsed time.

### 5. Evaluation size

The 15-task dataset is fine as a pilot/course demonstration but is small for a strong empirical conclusion. Preserve it as a pilot set, then add a larger held-out ambiguity set if the final report makes statistical claims.

## Suggested test layers

- **Unit tests:** executor, provider adapters, candidate filtering, probe generation, question scoring.
- **Offline integration tests:** deterministic mock LLM, multiple ambiguity patterns.
- **Provider smoke test:** one Gemini call using a Kaggle Secret.
- **Benchmark evaluation:** Direct-1 vs matched Top-K vs SEMSYNTH, using hidden tests and equal model/sample budgets.
- **Regression tests:** every bug discovered during experiments becomes a permanent test case.

## Kaggle secret

Use `GEMINI_API_KEY` in Kaggle Secrets. Do not commit the key to `.env`, notebooks, Git history, or result files.
