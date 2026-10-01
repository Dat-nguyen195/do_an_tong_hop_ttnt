# Kaggle Quickstart — Gemini / Offline

Enable **Internet** in the Kaggle notebook if you want to clone GitHub or call Gemini.

## One-cell Gemini run

1. Add a Kaggle secret named `GEMINI_API_KEY`.
2. Replace `REPO_URL` with your public GitHub repository URL.
3. Run this cell:

```python
import os, subprocess, sys
from pathlib import Path
from kaggle_secrets import UserSecretsClient

REPO_URL = "https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO>.git"
WORKDIR = Path("/kaggle/working/semsynth-lite")

if not WORKDIR.exists():
    subprocess.run(["git", "clone", REPO_URL, str(WORKDIR)], check=True)

os.chdir(WORKDIR)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], check=True)

os.environ["GEMINI_API_KEY"] = UserSecretsClient().get_secret("GEMINI_API_KEY")
os.environ["LLM_PROVIDER"] = "gemini"
os.environ["DEFAULT_MODEL"] = "gemini-3.8-flash"

subprocess.run([sys.executable, "-m", "pytest", "-q"], check=True)
subprocess.run([sys.executable, "kaggle_run.py", "--offline-suite"], check=True)
subprocess.run([
    sys.executable, "kaggle_run.py",
    "--provider", "gemini",
    "--model", "gemini-3.8-flash",
    "--top-k", "5",
    "--max-questions", "4",
], check=True)
```

## Offline only

```bash
!python kaggle_run.py --offline-suite
!pytest -q
```

No API key is required for this mode.

## Notes

- Keep `GEMINI_API_KEY` in Kaggle Secrets; do not hard-code it in the notebook or commit it.
- The offline suite is a deterministic smoke test, not an experimental benchmark result.
- Generated code is process-isolated with an AST policy and timeout, but this is not a hardened multi-tenant sandbox.
