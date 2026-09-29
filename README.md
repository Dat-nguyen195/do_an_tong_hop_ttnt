# SEMSYNTH Lite — Behavior-Guided Interactive Program Synthesis

SEMSYNTH Lite is a course/research prototype for resolving ambiguity in natural-language programming requests with low-friction **Yes/No clarification questions**.

The runnable loop is now:

```text
Natural-language task
        ↓
Generate Top-K candidate programs
        ↓
Execute candidates on behavioral probe inputs
        ↓
Find a high-information / balanced disagreement
        ↓
Ask a Yes/No behavioral clarification
        ↓
Filter candidate partition
        ↓
Repeat until no useful distinction remains
        ↓
Return current best candidate + full interaction log
```

## What is implemented

- ✅ OpenAI / OpenRouter unified LLM client
- ✅ real candidate sampling temperatures + duplicate removal
- ✅ deterministic offline mock mode for zero-key demos
- ✅ candidate execution and behavioral signatures
- ✅ distinguishing-input generation from seed inputs
- ✅ multi-output → binary Yes/No candidate partitioning
- ✅ balance score + binary information gain
- ✅ candidate filtering by clarification answer
- ✅ end-to-end SEMSYNTH controller
- ✅ Direct-1 and explicitly-labelled Oracle Best-of-K baselines
- ✅ stateful Streamlit demo
- ✅ Kaggle quickstart script and notebook
- ✅ subprocess execution, AST policy checks and timeout
- ✅ 40 automated tests covering the core loop

> **Execution safety note:** generated code runs in a fresh subprocess with an AST policy, isolated working directory and timeout. This is suitable process isolation for a local/course prototype; it is **not a hardened multi-tenant sandbox**.

---

## 1. Local quickstart

Python 3.10+ is recommended.

```bash
git clone <YOUR_REPOSITORY_URL> semsynth-lite
cd semsynth-lite
python -m pip install -r requirements.txt
```

### Zero-key smoke demo

```bash
python kaggle_run.py --offline
pytest -q
```

The offline demo deliberately uses an underspecified task (`Remove duplicate elements from a list.`), generates plausible competing implementations, asks a distinguishing Yes/No question, and filters candidates according to a simulated reference intent.

### Real LLM mode

Copy the environment template:

```bash
cp .env.example .env
```

Set one provider key in `.env`:

```dotenv
LLM_PROVIDER=openai
DEFAULT_MODEL=gpt-4o-mini
OPENAI_API_KEY=...
```

Then run:

```bash
python kaggle_run.py --provider openai --model gpt-4o-mini
```

OpenRouter is also supported:

```bash
python kaggle_run.py --provider openrouter --model <OPENROUTER_MODEL_NAME>
```

---

## 2. Kaggle — clone and run

Open a Kaggle notebook and enable Internet if you want to clone from GitHub or call a remote LLM API.

### Cell 1 — clone

```python
REPO_URL = "https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPOSITORY>.git"
!git clone {REPO_URL} semsynth-lite
%cd semsynth-lite
```

### Cell 2 — install

```python
!python -m pip install -q -r requirements.txt
```

### Cell 3A — offline full-loop demo, no secret required

```python
!python kaggle_run.py --offline
!pytest -q
```

### Cell 3B — real OpenAI mode

Add `OPENAI_API_KEY` under **Kaggle → Add-ons → Secrets**, then:

```python
from kaggle_secrets import UserSecretsClient
import os

os.environ["OPENAI_API_KEY"] = UserSecretsClient().get_secret("OPENAI_API_KEY")
os.environ["LLM_PROVIDER"] = "openai"
os.environ["DEFAULT_MODEL"] = "gpt-4o-mini"

!python kaggle_run.py --provider openai --model gpt-4o-mini
```

A notebook-ready version is included at:

```text
notebooks/kaggle_quickstart.ipynb
```

---

## 3. Run the Streamlit demo

```bash
streamlit run app.py
```

The UI supports:

- offline demo mode;
- real OpenAI/OpenRouter mode;
- Top-K configuration;
- stateful Yes/No clarification;
- candidate count tracking;
- current best code;
- interaction transcript.

---

## 4. Baselines

### Direct-1

```bash
python -m src.baseline_cot --limit 15
```

### Offline smoke mode

```bash
python -m src.baseline_cot --dry-run --limit 3
```

### Oracle Best-of-K upper bound

```bash
python -m src.baseline_cot --top-k 5 --limit 15
```

`Oracle-Best-of-K` selects the candidate using benchmark tests and is therefore an **upper bound**, not a deployable self-selection baseline. Keep that label in reports.

Results are written under `results/`.

---

## 5. Core modules

```text
src/
├── llm_client.py          unified API client + offline mock
├── code_executor.py       process isolation / AST policy / timeout
├── candidate_manager.py   candidate lifecycle and filtering
├── question_generator.py  probes, behavior groups, binary partitions
├── semsynth_controller.py end-to-end interactive controller
└── baseline_cot.py        Direct-1 / Oracle Best-of-K experiment runner
```

Important objects:

```python
from src.llm_client import LLMClient
from src.semsynth_controller import SEMSYNTHConfig, SEMSYNTHController

llm = LLMClient()
controller = SEMSYNTHController(
    llm,
    SEMSYNTHConfig(top_k=5, max_questions=4),
)

result = controller.run(
    description="Remove duplicate elements from a list.",
    function_name="remove_duplicates",
    params="xs",
    seed_inputs=[{"xs": [3, 1, 3, 2]}],
)

print(result.best_code)
print(result.questions_asked)
```

For reproducible automated evaluation, provide a controlled `answer_callback` rather than reading from stdin.

---

## 6. Clarification objective

For a binary candidate partition with `yes_n` and `no_n`, the implementation records:

```text
balance = 1 - |yes_n - no_n| / total
```

and binary entropy:

```text
H(p) = -p log2(p) - (1-p) log2(1-p)
```

A 50/50 partition has maximum balance and information gain. If a probe produces more than two outputs, SEMSYNTH evaluates binary properties of the form:

```text
Should this input return Y?
```

so a Yes/No question can still partition a multi-way disagreement.

---

## 7. Dataset and research hygiene

`config/dataset_sample.json` contains the original 15-task pilot dataset. `HE_008` is corrected to domain `list`.

For the final experiment, do **not** treat the existing gold clarification fields as automatically generated questions. A clean evaluation should distinguish:

1. **Gold/oracle clarification** — upper bound;
2. **generated clarification** — proposed method;
3. **Direct-1** — zero-interaction baseline;
4. **matched Top-K** — controls for extra LLM sampling budget.

The current 15 tasks are best treated as a pilot/debug set. Build a larger explicitly underspecified benchmark before making statistical claims.

---

## 8. Tests

```bash
pytest -q
```

The suite covers:

- dataset schema;
- executor success/failure behavior;
- unsafe import rejection;
- LLM code extraction;
- actual sampling-temperature propagation;
- candidate partition filtering;
- behavioral question generation;
- end-to-end offline SEMSYNTH loop;
- project structure.

---

## 9. Project tree

```text
.
├── app.py
├── kaggle_run.py
├── config/
│   └── dataset_sample.json
├── docs/
├── notebooks/
│   ├── KAGGLE_QUICKSTART.md
│   └── kaggle_quickstart.ipynb
├── src/
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

## License / purpose

Academic course/research prototype for the 2026–2027 semester.
