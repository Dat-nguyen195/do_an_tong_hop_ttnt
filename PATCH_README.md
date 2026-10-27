# SEMSYNTH Lite — Kaggle-first patch (changed files only)

**Usage:** Extract this ZIP at your *original repository root*, overwriting files with matching paths. It is **not a complete standalone repository**. Push the merged repository to GitHub. The existing `config/dataset_sample.json` and course-report documents are intentionally unchanged.

## Default CPU-only execution

```bash
python -m pip install -r requirements-kaggle.txt
python -m pytest -q
python scripts/preflight.py --mode offline
python run_experiments.py --quick
python run_experiments.py
```

The default runs a 32-case synthetic, controlled regression set and six comparison methods without network, GPU or API keys. The one-cell Kaggle notebook is at `notebooks/KAGGLE_ONE_CELL.ipynb`. For parallel Kaggle sessions use `--num-shards 2 --shard-index 0` and `--num-shards 2 --shard-index 1`, then `scripts/merge_shards.py`.

**Change highlights:** AST candidate validity check, meaningful confidence status, execution-result LRU cache and cross-probe batching, round-robin multi-parameter probe generation, template-grounded semantic clarification, noise-aware Bayesian ranking, fair shared candidate pools, held-out task scoring, per-task atomic checkpoint/resume, manifest/config fingerprint, automatic completeness checks and ZIP export, offline preflight, and 23 new regression tests including eight synthetic task families.

**Known limitations:** The 32 benchmark records share eight templates, not 32 independent human-annotated tasks. Real provider availability/limits are unverified; runtime varies by Kaggle conditions. The `oracle_upper_bound` baseline uses held-out answers and cannot be deployed. Bayesian improvements are algorithmically implemented but no statistically significant accuracy advantage has been established. Use real tasks and LLM multi-seed trials before research claims. The executor uses isolated Python processes plus AST restrictions; it is **not** a hardened sandbox for adversarial code.
