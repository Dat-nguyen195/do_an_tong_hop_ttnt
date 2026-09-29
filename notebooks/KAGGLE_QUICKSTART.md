# Kaggle Quickstart

## Option A — clone and run without any API key

In a Kaggle notebook cell:

```bash
!git clone https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO>.git semsynth-lite
%cd semsynth-lite
!pip install -q -r requirements.txt
!python kaggle_run.py --offline
!pytest -q
```

This validates the full candidate → disagreement → Yes/No → filtering loop using the deterministic offline demo client.

## Option B — real LLM

1. Add `OPENAI_API_KEY` or `OPENROUTER_API_KEY` in **Kaggle → Add-ons → Secrets**.
2. Enable Internet for the notebook when the selected API requires it.
3. Export the secret, then run the script.

```python
from kaggle_secrets import UserSecretsClient
import os
os.environ["OPENAI_API_KEY"] = UserSecretsClient().get_secret("OPENAI_API_KEY")
```

```bash
!python kaggle_run.py --provider openai --model gpt-4o-mini
```

For OpenRouter, set `OPENROUTER_API_KEY` and use `--provider openrouter`.

## Notes

- `--offline` is a smoke/demo mode, **not** an experimental result.
- Generated code is executed in a subprocess with timeout and an AST policy. This is process isolation for a course/research demo, not a hardened multi-tenant sandbox.
- For a fair experiment, compare Direct-1, an explicitly labelled Best-of-K upper bound, and SEMSYNTH under matched candidate budgets.
