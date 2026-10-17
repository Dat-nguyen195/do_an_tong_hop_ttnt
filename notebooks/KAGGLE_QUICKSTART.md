# SEMSYNTH: Kaggle one-cell execution

The **recommended notebook** is [`KAGGLE_ONE_CELL.ipynb`](KAGGLE_ONE_CELL.ipynb).

1. Push the contents of the **patch ZIP** over the same paths in your original GitHub repository. Keep all original unmodified files.
2. In Kaggle, enable **Internet** (required for GitHub clone), add a notebook, and paste the one code cell from `KAGGLE_ONE_CELL.ipynb`.
3. Set `REPO_URL` to your GitHub repository. The notebook installs the minimal dependencies, runs the automated tests, checks the environment, executes the experiment and writes `SEMSYNTH_RESULTS.zip` under `/kaggle/working/semsynth_results/<run-id>/`.
4. The default `MODE="offline"` needs **no API key, no GPU, and no training**. It runs **32 controlled synthetic task instances from eight template families**. These are correctness regressions, **not real-LLM efficacy claims**.
5. To use real candidate generation, set `MODE="real"`, enable Internet, set the `GEMINI_API_KEY` Kaggle Secret (or another supported provider secret), and set `MODEL` only if needed. Cloud provider availability/quotas have not been tested in this patch.
6. If Kaggle interrupts the run, execute the same notebook again with the same settings and retained `/kaggle/working` output. Completed task-method checkpoints are skipped. For a *new* Kaggle session, attach prior results and copy the matching run-id directory into the output folder first.

## Parallel, nonoverlapping Kaggle sessions

Set `NUM_SHARDS=2, SHARD_INDEX=0` in session A and `NUM_SHARDS=2, SHARD_INDEX=1` in session B. **Each session is independent**: it does not wait for the other or require shared storage. Both must use identical experiment settings and repository revision. Download their `SEMSYNTH_RESULTS.zip` files, then merge them locally with:

```bash
python scripts/merge_shards.py shard0.zip shard1.zip --output-dir results/merged
```

Do not interpret a partial shard's `pass_rate_on_completed` as a full-benchmark comparison. Check `completeness.json` for `all_complete: true` after merging.

## Commands without notebook

```bash
python -m pip install -r requirements-kaggle.txt
python -m pytest -q
python scripts/preflight.py --mode offline
python run_experiments.py --quick
python run_experiments.py --seed 3101 --max-minutes 600
python run_experiments.py --seed 3101 --num-shards 2 --shard-index 0
python run_experiments.py --seed 3101 --num-shards 2 --shard-index 1
```

The six methods are `direct1`, `first_valid`, `random`, `balanced`, `proposed`, and `oracle_upper_bound`. The oracle upper bound uses hidden evaluation outcomes to choose a candidate and is **not a deployable baseline**. All other methods share the same candidate pool per task, with held-out evaluation occurring only after selection.

## What is and is not measured

- `passed_all` is the separate held-out input test result. The controller's backward-compatible `success` means **a candidate exists**, not that it is correct.
- `proposed` enables semantic questions where execution justifies the wording plus probabilistic belief updates. Unknown/noisy responses are not human-evaluated in the offline data.
- `--simulated-flip-rate 0.1` is an optional error-injection stress test; it cannot simulate all human misunderstandings.
- Cached execution assumes deterministic pure functions, and process isolation is **not** a hardened security sandbox. Do not run arbitrary hostile code on public infrastructure.
- The 32 cases share only eight underlying templates. They are primarily a reproducible **software regression** benchmark; stronger empirical claims require genuinely independent tasks, rigorous annotation, human subjects, and real LLM repetitions.
