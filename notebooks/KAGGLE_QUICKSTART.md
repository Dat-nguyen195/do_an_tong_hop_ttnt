# SEMSYNTH Kaggle — one cell + manual Gemini key

1. Create a Kaggle notebook and turn **Internet ON** (Accelerator: None).
2. Upload both the **original** `do_an_tong_hop_ttnt-tydeptrai.zip` and this **changes-only** `SEMSYNTH_KAGGLE_EXPLAIN_PATCH.zip` as Kaggle inputs. Alternatively, set `REPO_URL` to an updated GitHub repo and optionally attach the patch ZIP.
3. Open `notebooks/KAGGLE_ONE_CELL.ipynb` (or paste the single code cell in `KAGGLE_PASTE_ONE_CELL.py`).
4. Type the Gemini API key when prompted (hidden input). You can instead assign `GEMINI_API_KEY = "..."` at the top, but then the notebook source contains your secret.
5. Keep `PROFILE = "pilot"` (eight tasks / eight template families) for the first real API run. Set `PROFILE = "smoke"` for a one-task connectivity check, or `PROFILE = "full"` to run the full 32-case synthetic benchmark. Keep the same profile/model/settings for checkpoint resume.
6. Download `/kaggle/working/SEMSYNTH_RESULTS.zip` from Kaggle Outputs. The archive includes `summary.csv`, `per_task.csv`, `runtime.csv`, `explanations.jsonl`, `runs.jsonl`, `manifest.json`, and `completeness.json`.

**Scope:** `proposed_explain` uses exactly the same question selection and Bayesian updates as `proposed`. Only the grounded explanation and decision trace are added. The clarity benefit cannot be established scientifically without a user study.

**Fairness:** The benchmark's reference code is used for simulated user responses and evaluation, never Gemini's prompts. The 32 cases belong to eight synthetic families. `oracle_upper_bound` is not a deployable baseline.

**API limits:** Calls to Gemini require external access, account permissions, and sufficient usage quota. A local patch check cannot guarantee those. The notebook does not silently switch from live Gemini to mocked generations.

**Checkpointing:** Re-running within a Kaggle session keeps `/kaggle/working/semsynth_results`, and completed task-method records are reused. Download results before closing the session. A fully fresh Kaggle session has no saved checkpoints unless you restore them.
